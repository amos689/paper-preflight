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
    words: list[str] = []
    depth = 0
    current: list[str] = []
    for ch in text:
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
        if ch.isspace() and depth == 0:
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


def parse_name(raw: str) -> Person:
    raw = raw.strip()
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
        people.append(parse_name(part))
    return AuthorList(tuple(people), truncated)
