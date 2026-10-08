"""Read CSL-JSON: the items Zotero and Mendeley write into Word documents, and that they, Pandoc
and many other tools export as files.

Each item becomes a BibTeX entry, keyed by the item's ``id`` when that is a usable key (Better
BibTeX's "smith2020deep") and ``ref1``, ``ref2``, ... otherwise. The file is marked derived:
checked, never edited.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from dataclasses import replace
from pathlib import Path
from typing import Any

from paper_preflight.bib.parse import BibFile, BibIssue, parse_bib_text
from paper_preflight.textio import read_text

# CSL item types as BibTeX entry types; "article" is CSL's preprint or unpublished paper
_TYPES = {
    "article-journal": "article",
    "article-magazine": "article",
    "article-newspaper": "article",
    "review": "article",
    "review-book": "article",
    "paper-conference": "inproceedings",
    "book": "book",
    "chapter": "incollection",
    "entry-encyclopedia": "incollection",
    "entry-dictionary": "incollection",
    "thesis": "phdthesis",
    "report": "techreport",
    "manuscript": "unpublished",
}
_BOOK_PARTS = frozenset({"inproceedings", "incollection"})
_PLAIN_FIELDS = {
    "volume": "volume",
    "issue": "number",
    "page": "pages",
    "DOI": "doi",
    "URL": "url",
    "publisher": "publisher",
    "ISBN": "isbn",
    "ISSN": "issn",
    "PMID": "pmid",
    "PMCID": "pmcid",
    "edition": "edition",
    "genre": "type",
    "note": "note",
}
_IDENTIFIER_FIELDS = frozenset({"doi", "url", "eprint", "isbn", "issn", "pmid", "pmcid"})
# an id that is a citation key (Better BibTeX's "smith2020deep"), not Zotero's item URI or
# Mendeley's UUID
_KEY = re.compile(r"[A-Za-z][\w:.+-]{2,79}")
# an id that is the citation key by design (Pandoc's CSL files, Hayagriva): anything BibTeX
# could hold as a key
_CITATION_KEY = re.compile(r"[^\s,{}()\"#%'=\\]+")
_UUID = re.compile(r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}", re.I)
# Mendeley numbers the items of each citation afresh: every first item is "ITEM-1"
_MENDELEY_ITEM = re.compile(r"ITEM-\d+")
_TAG = re.compile(r"</?[a-z][^<>]*>", re.I)  # CSL's rich text: <i>, <b>, <sup>, <span ...>


def _text(value: Any) -> str:
    if isinstance(value, list):  # some exports give container-title as a list
        value = value[0] if value else ""
    return " ".join(_TAG.sub("", str(value or "")).split())


def _escape(value: str, identifier: bool = False) -> str:
    """Plain text as a BibTeX value (as the plain-text reader writes it)."""
    value = value.replace("\\", " ").replace("{", "(").replace("}", ")")
    return value if identifier else re.sub(r"([&%#_$])", r"\\\1", value)


def _person(name: dict[str, Any]) -> str:
    literal = _text(name.get("literal"))
    if literal:  # an organisation, kept whole
        return "{" + _escape(literal) + "}"
    family = " ".join(
        part for part in (_text(name.get("non-dropping-particle")), _text(name.get("family")))
        if part
    )  # fmt: skip
    given = " ".join(
        part for part in (_text(name.get("given")), _text(name.get("dropping-particle"))) if part
    )
    suffix = _text(name.get("suffix"))
    if not family:
        return _escape(given)
    parts = [family, suffix, given] if suffix else [family, given]
    return ", ".join(_escape(p) for p in parts if p)


def _year(date: Any) -> str:
    if not isinstance(date, dict):
        return ""
    parts = date.get("date-parts") or []
    if parts and parts[0] and str(parts[0][0]).strip().isdigit():
        return str(parts[0][0]).strip()
    found = re.search(r"\b(1[5-9]\d\d|20\d\d)\b", str(date.get("raw") or date.get("literal") or ""))
    return found.group(1) if found else ""


def csl_fields(item: dict[str, Any]) -> tuple[str, dict[str, str]]:
    """The BibTeX entry type and (escaped) field values of one CSL item."""
    entry_type = _TYPES.get(str(item.get("type") or ""), "misc")
    fields: dict[str, str] = {}
    title = _text(item.get("title"))
    if title:
        fields["title"] = _escape(title)
    for role, field in (("author", "author"), ("editor", "editor")):
        people = [p for p in item.get(role) or [] if isinstance(p, dict)]
        names = [n for n in (_person(p) for p in people) if n]
        if names:
            fields[field] = " and ".join(names)
    year = _year(item.get("issued")) or _year(item.get("original-date"))
    if year:
        fields["year"] = year
    container = _text(item.get("container-title")) or _text(item.get("event-title"))
    if not container and entry_type == "inproceedings":
        container = _text(item.get("event"))
    if container:
        fields["booktitle" if entry_type in _BOOK_PARTS else "journal"] = _escape(container)
    for name, field in _PLAIN_FIELDS.items():
        value = _text(item.get(name))
        if value and field not in fields:
            fields[field] = _escape(value, identifier=field in _IDENTIFIER_FIELDS)
    # Zotero writes an arXiv preprint as "article" with its number: "arXiv:2101.00001"
    number = _text(item.get("number"))
    if number:
        arxiv = re.search(r"arxiv:\s*(\S+)", number, re.I)
        if arxiv:
            fields.update(eprint=arxiv.group(1), archiveprefix="arXiv")
        elif entry_type == "techreport":
            fields["number"] = _escape(number)
    if entry_type == "techreport" and "publisher" in fields:
        fields["institution"] = fields.pop("publisher")
    return entry_type, fields


def _key(item: dict[str, Any], number: int, taken: set[str], keep: bool = False) -> str:
    candidate = str(item.get("id") or "")
    shaped = (_CITATION_KEY if keep else _KEY).fullmatch(candidate)
    # Zotero's item URIs, Mendeley's UUIDs and its "ITEM-1" are no citation keys either way
    usable = (
        shaped
        and "://" not in candidate
        and not _UUID.fullmatch(candidate)
        and not _MENDELEY_ITEM.fullmatch(candidate)
    )
    key = candidate if usable else f"ref{number}"
    while key in taken:
        key = f"{key}_{number}"
    taken.add(key)
    return key


def csl_entries(
    items: Iterable[dict[str, Any]],
    path: Path,
    encoding: str = "utf-8",
    *,
    lines: list[int] | None = None,
    keep_ids: bool = False,
) -> BibFile:
    """``lines``: where each item is in the source (a Word paragraph's number), else 1, 2, ...
    ``keep_ids``: the ids are the citation keys (a Pandoc or Typst bibliography), kept as written
    when BibTeX can hold them; otherwise only ids shaped like citation keys are kept."""
    result = BibFile(path=path, encoding=encoding, derived=True)
    taken: set[str] = set()
    for number, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            continue
        entry_type, fields = csl_fields(item)
        if not fields:
            continue
        key = _key(item, number, taken, keep_ids)
        body = ",\n".join(f"  {name} = {{{value}}}" for name, value in fields.items())
        line = lines[number - 1] if lines and number <= len(lines) else number
        for entry in parse_bib_text(f"@{entry_type}{{{key},\n{body}\n}}\n", path, encoding).entries:
            at_line = {name: replace(f, line=line) for name, f in entry.fields.items()}
            result.entries.append(replace(entry, fields=at_line, line=line))
    return result


def parse_csl_json_file(path: Path) -> BibFile:
    """A CSL-JSON file: a list of items, or an object holding them under "items"."""
    try:
        source = read_text(path)
        data = json.loads(source.text)
    except (OSError, ValueError) as exc:
        result = BibFile(path=path, encoding="unknown", derived=True)
        result.issues.append(BibIssue("unreadable", path, 1, None, str(exc)))
        return result
    items = data.get("items", [data]) if isinstance(data, dict) else data
    items = items if isinstance(items, list) else []
    return csl_entries(items, path, source.encoding, keep_ids=True)
