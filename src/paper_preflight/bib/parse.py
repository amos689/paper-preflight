"""Parse .bib files into entries that keep exact source positions.

bibtexparser v2 is used only for splitting the file into blocks (with an empty middleware stack).
Value processing is our own so that entries recovered from failed blocks (duplicate fields,
duplicate keys) are treated exactly like normal ones:

* ``@string`` macros and the standard month macros are resolved, ``#`` concatenation is applied;
* the enclosing braces/quotes are removed (``value``), and a plain-Unicode version with LaTeX
  markup decoded is produced (``text``);
* for duplicate fields the **first** occurrence wins and duplicate keys keep the **first** entry,
  matching BibTeX's own behaviour.
"""

from __future__ import annotations

import html
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

from bibtexparser.entrypoint import parse_string
from bibtexparser.model import (
    DuplicateBlockKeyBlock,
    DuplicateFieldKeyBlock,
    Entry,
    ParsingFailedBlock,
    String,
)
from pylatexenc import latex2text, latexwalker, macrospec

from paper_preflight.sources.record import MARKUP_TAG_RE
from paper_preflight.textio import read_text

logging.getLogger("bibtexparser").setLevel(logging.CRITICAL)  # we report problems ourselves

MONTH_MACROS = {
    "jan": "January", "feb": "February", "mar": "March", "apr": "April", "may": "May",
    "jun": "June", "jul": "July", "aug": "August", "sep": "September", "oct": "October",
    "nov": "November", "dec": "December",
}  # fmt: skip

# Fields whose values are identifiers or URLs: only unescape, never interpret as LaTeX.
VERBATIM_FIELDS = frozenset(
    {"doi", "url", "eprint", "isbn", "issn", "pmid", "pmcid", "arxivid", "file", "urldate"}
)

_SUPPRESSION_RE = re.compile(
    r"%\s*preflight:\s*ignore\[(?P<rules>[A-Za-z0-9_,\s]+)\](?:\s+reason\s*=\s*\"(?P<reason>[^\"]*)\")?"
)
_SIMPLE_ESCAPES_RE = re.compile(r"\\([_%&#$])")

# Macros the default context does not know, seen in real .bib files (ADS exports).
_WALKER_CONTEXT = latexwalker.get_default_latex_context_db()
_WALKER_CONTEXT.add_context_category(
    "paper-preflight", prepend=True, macros=[macrospec.MacroSpec("raisebox", "{[[{")]
)
_TEXT_CONTEXT = latex2text.get_default_latex_context_db()
# Text-style macros whose argument the default context drops ("\texttt{torch}" lost its word;
# a real paper's chapter title was set in \textup{...})
_KEEP_ARGUMENT = ("textup", "textmd", "textsf", "texttt", "mbox")
# AASTeX's journal macros, as NASA ADS exports them (journal = {\aap}): the journals they stand
# for, which were lost (an A&A 1993 article was then sought as a journal-less work; heldout21)
AAS_JOURNALS = {
    "aj": "The Astronomical Journal", "apj": "The Astrophysical Journal",
    "apjl": "The Astrophysical Journal Letters",
    "apjs": "The Astrophysical Journal Supplement Series",
    "aap": "Astronomy and Astrophysics", "aaps": "Astronomy and Astrophysics Supplement Series",
    "aapr": "Astronomy and Astrophysics Review",
    "araa": "Annual Review of Astronomy and Astrophysics",
    "mnras": "Monthly Notices of the Royal Astronomical Society",
    "pasp": "Publications of the Astronomical Society of the Pacific",
    "pasj": "Publications of the Astronomical Society of Japan",
    "pasa": "Publications of the Astronomical Society of Australia",
    "apss": "Astrophysics and Space Science", "nat": "Nature", "icarus": "Icarus",
    "jcap": "Journal of Cosmology and Astroparticle Physics", "solphys": "Solar Physics",
    "ssr": "Space Science Reviews", "nar": "New Astronomy Reviews", "na": "New Astronomy",
    "prd": "Physical Review D", "prl": "Physical Review Letters", "physrep": "Physics Reports",
    "actaa": "Acta Astronomica", "baas": "Bulletin of the American Astronomical Society",
    "psj": "The Planetary Science Journal", "procspie": "Proceedings of the SPIE",
}  # fmt: skip
_TEXT_CONTEXT.add_context_category(
    "paper-preflight",
    prepend=True,
    macros=[
        latex2text.MacroTextSpec("raisebox", simplify_repl="%(4)s"),  # its text only
        *(latex2text.MacroTextSpec(name, simplify_repl="%(1)s") for name in _KEEP_ARGUMENT),
        *(
            latex2text.MacroTextSpec(name, simplify_repl=title)
            for name, title in AAS_JOURNALS.items()
        ),
    ],
)
_latex2text = latex2text.LatexNodes2Text(
    math_mode="text", strict_latex_spaces=True, latex_context=_TEXT_CONTEXT
)


@dataclass(frozen=True)
class Suppression:
    rules: frozenset[str]
    reason: str | None
    line: int


@dataclass(frozen=True)
class BibField:
    name: str  # lower-case field name
    raw: str  # the value exactly as written (braces, quotes, macros, #)
    value: str  # macros resolved, concatenated, outer braces/quotes removed (LaTeX kept)
    text: str  # plain Unicode with LaTeX markup decoded
    line: int  # 1-based line of the field


@dataclass
class BibEntry:
    key: str
    entry_type: str  # lower-case, e.g. "article"
    fields: dict[str, BibField]
    file: Path
    line: int  # 1-based line of "@type{key,"
    raw: str
    suppressions: tuple[Suppression, ...] = ()
    duplicate_fields: tuple[str, ...] = ()

    def text(self, name: str) -> str | None:
        f = self.fields.get(name)
        return f.text if f is not None else None

    def suppressed(self, rule: str) -> Suppression | None:
        for suppression in self.suppressions:
            if rule in suppression.rules:
                return suppression
        return None


@dataclass(frozen=True)
class BibIssue:
    kind: str  # "syntax_error" | "duplicate_key" | "duplicate_field" | "unreadable"
    file: Path
    line: int
    key: str | None
    detail: str


@dataclass
class BibFile:
    path: Path
    encoding: str
    entries: list[BibEntry] = field(default_factory=list)
    issues: list[BibIssue] = field(default_factory=list)
    derived: bool = False  # read from a compiled .bbl: checked, but never edited


def _split_concatenation(raw: str) -> list[str]:
    parts: list[str] = []
    depth = 0
    in_quotes = False
    current: list[str] = []
    i = 0
    while i < len(raw):
        ch = raw[i]
        if ch == "\\":
            current.append(raw[i : i + 2])
            i += 2
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
        elif ch == '"' and depth == 0:
            in_quotes = not in_quotes
        elif ch == "#" and depth == 0 and not in_quotes:
            parts.append("".join(current))
            current = []
            i += 1
            continue
        current.append(ch)
        i += 1
    parts.append("".join(current))
    return parts


def resolve_value(raw: str, strings: dict[str, str]) -> str:
    """Resolve macros and ``#`` concatenation; remove the enclosing braces or quotes."""
    pieces: list[str] = []
    for part in _split_concatenation(raw):
        token = part.strip()
        if len(token) >= 2 and (token[0], token[-1]) in (("{", "}"), ('"', '"')):
            pieces.append(token[1:-1])
        elif token.isdigit():
            pieces.append(token)
        elif token.lower() in strings:
            pieces.append(strings[token.lower()])
        else:
            pieces.append(token)  # undefined macro: keep its name, BibTeX would warn
    return "".join(pieces)


def unescape_identifier(value: str) -> str:
    """Undo LaTeX escaping in identifiers and URLs: ``10.1162/tacl\\_a\\_00276`` → ``..._a_...``."""
    return _SIMPLE_ESCAPES_RE.sub(r"\1", value).replace("{", "").replace("}", "").strip()


_HTML_ENTITY_RE = re.compile(r"&(?:#\d+|#x[0-9a-fA-F]+|[a-zA-Z]+);")
_LATEX_SPECIAL = {"&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#", "_": r"\_"}


def _decode_entity(match: re.Match[str]) -> str:
    """An HTML entity as the character it stands for, escaped if LaTeX treats it specially."""
    char = html.unescape(match.group(0))
    return _LATEX_SPECIAL.get(char, char)


_IFMMODE_RE = re.compile(r"\\ifmmode\s*(?P<math>.*?)\\else\s*(?P<text>.*?)\\fi(?:\{\})?", re.S)
_UTF_RE = re.compile(r"\\UTF\{([0-9A-Fa-f]{4,6})\}")
_HREF_RE = re.compile(r"\\href\s*(?=\{)")
# Fields that carry links; elsewhere a link prints as its text alone
LINK_FIELDS = frozenset({"note", "howpublished", "addendum", "annote", "annotation"})


def _group_end(value: str, start: int) -> int | None:
    """The index just past the braced group that opens at ``value[start]``."""
    depth = 0
    i = start
    while i < len(value):
        if value[i] == "\\":
            i += 2  # an escaped brace does not count
            continue
        if value[i] == "{":
            depth += 1
        elif value[i] == "}":
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    return None


def _unlink(value: str, keep_url: bool) -> str:
    """``\\href{URL}{text}`` as the text it prints, followed by ``\\url{URL}`` if ``keep_url``.

    pylatexenc reads \\href without its arguments and fails, and the fallback ran the URL into
    the text: a paper whose titles were all links was searched by its URLs (heldout18)."""
    out: list[str] = []
    pos = 0
    for match in _HREF_RE.finditer(value):
        if match.start() < pos:
            continue
        url_end = _group_end(value, match.end())
        if url_end is None:
            break
        text_start = len(value) - len(value[url_end:].lstrip())
        text_end = _group_end(value, text_start) if value.startswith("{", text_start) else None
        if text_end is None:
            continue
        text = value[text_start + 1 : text_end - 1]
        # a percent-encoded link must not read as a comment in \url
        url = re.sub(r"(?<!\\)%", r"\\%", value[match.end() + 1 : url_end - 1])
        out += [value[pos : match.start()], f"{text} \\url{{{url}}}" if keep_url else text]
        pos = text_end
    return "".join(out) + value[pos:]


def latex_to_text(value: str, *, keep_links: bool = False) -> str:
    # BibTeX copied from web pages carries HTML entities ("Francesco d&apos;Amore" in a dblp-
    # scraped HALLMARK entry); decode them first, or "&" reaches LaTeX as an alignment tab.
    value = _HTML_ENTITY_RE.sub(_decode_entity, value)
    if "\\href" in value:
        value = _unlink(value, keep_links)
    value = MARKUP_TAG_RE.sub("", value)  # ADS: "<ASTROBJ>NGC 1068</ASTROBJ>"
    # APS: "\ifmmode \check{S}\else \v{S}\fi{}upi\ifmmode \acute{c}\else \'{c}\fi{}" is Šupić
    value = _IFMMODE_RE.sub(lambda m: m["text"], value)
    # ADS: "z$_{phot}$ \UTF{2243} 7.6" is "≃" (AASTeX's macro for a character by its code point)
    value = _UTF_RE.sub(lambda m: chr(int(m[1], 16)), value)
    try:
        text = _latex2text.latex_to_text(value, latex_context=_WALKER_CONTEXT)
    except Exception:  # pylatexenc can fail on malformed input; fall back
        text = value.replace("{", "").replace("}", "")
    return " ".join(text.split())


def _suppressions_above(lines: list[str], entry_line: int) -> tuple[Suppression, ...]:
    """Collect ``% preflight: ignore[...]`` comments directly above an entry (1-based line)."""
    found: list[Suppression] = []
    index = entry_line - 2  # 0-based index of the line above the entry
    while index >= 0 and lines[index].lstrip().startswith("%"):
        match = _SUPPRESSION_RE.search(lines[index])
        if match:
            rules = frozenset(
                r.strip().upper() for r in match.group("rules").split(",") if r.strip()
            )
            found.append(Suppression(rules, match.group("reason"), index + 1))
        index -= 1
    return tuple(reversed(found))


def _build_entry(
    raw_entry: Entry, strings: dict[str, str], path: Path, lines: list[str]
) -> tuple[BibEntry, list[str]]:
    fields: dict[str, BibField] = {}
    duplicates: list[str] = []
    for f in raw_entry.fields:
        name = f.key.lower()
        if name in fields:
            duplicates.append(name)
            continue
        raw_value = str(f.value)
        value = resolve_value(raw_value, strings)
        if name in VERBATIM_FIELDS:
            text = unescape_identifier(value)
        else:
            text = latex_to_text(value, keep_links=name in LINK_FIELDS)
        field_line = _line(f.start_line, _line(raw_entry.start_line, 1))
        fields[name] = BibField(name, raw_value, value, text, field_line)
    line = _line(raw_entry.start_line, 1)
    entry = BibEntry(
        key=raw_entry.key,
        entry_type=raw_entry.entry_type.lower(),
        fields=fields,
        file=path,
        line=line,
        raw=raw_entry.raw or "",
        suppressions=_suppressions_above(lines, line),
        duplicate_fields=tuple(duplicates),
    )
    return entry, duplicates


def parse_bib_text(text: str, path: Path, encoding: str = "utf-8") -> BibFile:
    library = parse_string(text, parse_stack=[])
    result = BibFile(path=path, encoding=encoding)
    lines = text.splitlines()
    strings = dict(MONTH_MACROS)
    for block in library.blocks:
        if isinstance(block, String):
            strings[block.key.lower()] = resolve_value(str(block.value), strings)

    seen_keys: dict[str, int] = {}
    raw_entries: list[Entry] = []
    for block in library.blocks:
        if isinstance(block, Entry):
            raw_entries.append(block)
        elif isinstance(block, (DuplicateFieldKeyBlock, DuplicateBlockKeyBlock)):
            recovered = block.ignore_error_block
            if isinstance(recovered, Entry):
                raw_entries.append(recovered)
        elif isinstance(block, ParsingFailedBlock):
            line = _line(block.start_line, 1)
            result.issues.append(BibIssue("syntax_error", path, line, None, _short(block.error)))

    for raw_entry in sorted(raw_entries, key=lambda e: e.start_line or 0):
        entry, duplicates = _build_entry(raw_entry, strings, path, lines)
        for name in duplicates:
            result.issues.append(BibIssue("duplicate_field", path, entry.line, entry.key, name))
        if entry.key in seen_keys:
            result.issues.append(
                BibIssue("duplicate_key", path, entry.line, entry.key, str(seen_keys[entry.key]))
            )
            continue
        seen_keys[entry.key] = entry.line
        result.entries.append(entry)
    return result


def _line(zero_based: int | None, default: int) -> int:
    """Convert bibtexparser's 0-based line numbers to 1-based ones."""
    return zero_based + 1 if zero_based is not None else default


def _short(error: object) -> str:
    message = str(error).strip().splitlines()
    return message[0] if message else "syntax error"


def parse_bib_file(path: Path) -> BibFile:
    try:
        source = read_text(path)
    except OSError as exc:
        result = BibFile(path=path, encoding="unknown")
        result.issues.append(BibIssue("unreadable", path, 1, None, str(exc)))
        return result
    return parse_bib_text(source.text, path, source.encoding)
