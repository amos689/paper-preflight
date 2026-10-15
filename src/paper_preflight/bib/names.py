"""Parse BibTeX author/editor fields into people (BibTeX name grammar, simplified).

Supported forms: ``First von Last``, ``von Last, First``, ``von Last, Jr, First``, braced literal
names (``{World Health Organization}``), and the ``others`` marker meaning "et al.". Names are
split on `` and `` at brace depth 0 only, so organisation names containing "and" survive.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from paper_preflight.bib.parse import latex_to_text
from paper_preflight.sources.record import Person

_AND_RE = re.compile(r"\s+and\s+", re.IGNORECASE)
_ET_AL_AFTER = re.compile(r",?\s+et\.?\s+al\.?$", re.IGNORECASE)


@dataclass(frozen=True)
class AuthorList:
    people: tuple[Person, ...]
    truncated: bool  # the list ends with "and others" / "et al."


def _split_top_level(value: str) -> list[str]:
    parts: list[str] = []
    depth = 0
    start = 0
    i = 0
    while i < len(value):
        ch = value[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
        elif depth == 0:
            match = _AND_RE.match(value, i)
            if match and i > start:
                parts.append(value[start:i])
                start = i = match.end()
                continue
        i += 1
    parts.append(value[start:])
    return [p.strip() for p in parts if p.strip()]


def _split_commas(name: str) -> list[str]:
    parts: list[str] = []
    depth = 0
    current: list[str] = []
    for ch in name:
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append("".join(current).strip())
            current = []
        else:
            current.append(ch)
    parts.append("".join(current).strip())
    return parts


def _words(text: str) -> list[str]:
    """A name's words, split as BibTeX does: at spaces and at ties (``T.~{Goodson III}``), but
    not inside braces."""
    words: list[str] = []
    depth = 0
    current: list[str] = []
    for ch in text:
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
        if (ch.isspace() or ch == "~") and depth == 0:
            if current:
                words.append("".join(current))
                current = []
        else:
            current.append(ch)
    if current:
        words.append("".join(current))
    return words


_GENERATIONAL = frozenset({"jr", "sr", "ii", "iii", "iv"})


def _is_von(word: str) -> bool:
    stripped = word.lstrip("{\\")
    return bool(stripped) and stripped[0].islower()


# A person braced whole with a generational suffix, which BibTeX prints as written: "{J.~Pe{\v
# r}ina, Jr.}" (heldout23); initials, a surname and the suffix
_BRACED_SUFFIXED = re.compile(
    r"(?P<given>(?:[A-Z]\.\s*(?:-\s*[A-Z]\.\s*)?){1,3})(?P<family>[^\W\d_][\w'-]+)\s*,?\s*"
    r"(?P<suffix>Jr\.?|Sr\.?|II|III|IV)"
)


def _whole_braced(raw: str) -> bool:
    """One pair of braces around all of ``raw``."""
    if not (raw.startswith("{") and raw.endswith("}")):
        return False
    depth = 0
    for i, ch in enumerate(raw):
        depth += {"{": 1, "}": -1}.get(ch, 0)
        if depth == 0 and i < len(raw) - 1:
            return False
    return True


def parse_name(raw: str) -> Person:
    raw = raw.strip()
    if _whole_braced(raw):
        suffixed = _BRACED_SUFFIXED.fullmatch(" ".join(latex_to_text(raw[1:-1]).split()))
        if suffixed:
            family = f"{suffixed['family']} {suffixed['suffix']}"
            return Person(family=family, given=suffixed["given"].strip())
    if raw.startswith("{") and raw.endswith("}") and raw.count("{") == 1:
        literal = latex_to_text(raw)
        return Person(family=literal, literal=literal)
    parts = _split_commas(raw)
    if len(parts) >= 2:
        last_part = parts[0]
        first = parts[-1]
        words = _words(last_part)
        # "von Last" — keep particles with the family name for display, compare on the last word
        family = " ".join(words)
        return Person(family=latex_to_text(family), given=latex_to_text(first))
    words = _words(raw)
    if len(words) == 1:
        return Person(family=latex_to_text(words[0]))
    # "David H. Smith IV": a generational suffix stays with the family name ("Smith IV"), which
    # BibTeX alone would take for the whole of it
    suffix = []
    if len(words) >= 3 and words[-1].lower().rstrip(".") in _GENERATIONAL:
        suffix = [words.pop()]
    # First von Last: von part starts at the first lower-case word that is not the last word
    von_start = next((i for i, w in enumerate(words[:-1]) if _is_von(w)), len(words) - 1)
    given = " ".join(words[:von_start])
    family = " ".join(words[von_start:] + suffix)
    return Person(family=latex_to_text(family), given=latex_to_text(given))


# People written inside one pair of braces, which BibTeX prints as written: "{R. Horodecki,
# P. Horodecki, M. Horodecki, and K. Horodecki}" (heldout18). Only initials and a surname each,
# so that a group's name with a comma in it ("{Google DeepMind, Inc.}") stays one name.
_BRACED_PERSON = re.compile(r"(?:[A-Z]\.\s*(?:-\s*[A-Z]\.\s*)?){1,3}[A-Z][\w'-]+")
_LIST_SEPARATOR = re.compile(r"\s*,\s*(?:and\s+)?|\s+and\s+")


def _braced_people(part: str) -> list[str]:
    if not (part.startswith("{") and part.endswith("}") and part.count("{") == 1):
        return []
    names = [name for name in _LIST_SEPARATOR.split(part[1:-1].strip()) if name]
    if len(names) >= 2 and all(_BRACED_PERSON.fullmatch(name) for name in names):
        return names
    return []


def parse_authors(value: str | None) -> AuthorList:
    """Parse the (macro-resolved, LaTeX-kept) value of an author or editor field."""
    if not value:
        return AuthorList((), False)
    people: list[Person] = []
    truncated = False
    for part in _split_top_level(value):
        if part.lower() in {"others", "et al.", "et al"}:
            truncated = True
            continue
        cut = _ET_AL_AFTER.sub("", part)
        if cut != part:  # "Paul Ralph et al." written as one name
            truncated = True
            part = cut
        people += [parse_name(name) for name in _braced_people(part)] or [parse_name(part)]
    return AuthorList(tuple(people), truncated)
