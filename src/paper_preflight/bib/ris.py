"""Read RIS (.ris): the export format of EndNote, Zotero, Mendeley, Web of Science and most
publishers' "download citation" buttons.

Each record (``TY  -`` to ``ER  -``) becomes a BibTeX entry through the CSL reader, at the line
of its ``TY`` tag; the file is marked derived: checked, never edited.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from paper_preflight.bib.csl import csl_entries
from paper_preflight.bib.parse import BibFile, BibIssue
from paper_preflight.textio import read_text

_TAG = re.compile(r"^([A-Z][A-Z0-9])  -\s?(.*)$")
# RIS reference types as CSL types
_TYPES = {
    "JOUR": "article-journal",
    "EJOUR": "article-journal",
    "JFULL": "article-journal",
    "MGZN": "article-magazine",
    "NEWS": "article-newspaper",
    "CONF": "paper-conference",
    "CPAPER": "paper-conference",
    "BOOK": "book",
    "EBOOK": "book",
    "EDBOOK": "book",
    "CHAP": "chapter",
    "ECHAP": "chapter",
    "THES": "thesis",
    "RPRT": "report",
    "UNPB": "manuscript",
    "ELEC": "webpage",
    "WEB": "webpage",
    "BLOG": "post-weblog",
    "DATA": "dataset",
    "COMP": "software",
}
_YEAR = re.compile(r"(1[5-9]\d\d|20\d\d)")


def _name(text: str) -> dict[str, str]:
    family, _, given = text.partition(",")
    if not given:
        return {"literal": text.strip()}
    given = given.split(",")[0]  # "Smith, John, Jr." keeps the given name
    return {"family": family.strip(), "given": given.strip()}


def _item(tags: list[tuple[str, str]], number: int) -> dict[str, Any]:
    values: dict[str, list[str]] = {}
    for tag, value in tags:
        if value.strip():
            values.setdefault(tag, []).append(value.strip())

    def first(*names: str) -> str:
        for name in names:
            if values.get(name):
                return values[name][0]
        return ""

    kind = _TYPES.get(first("TY").upper(), "article")
    item: dict[str, Any] = {
        "id": first("ID") or f"ref{number}",
        "type": kind,
        "title": first("TI", "T1", "CT", "BT" if kind == "book" else ""),
        "author": [_name(a) for a in values.get("AU", []) + values.get("A1", [])],
        "editor": [_name(a) for a in values.get("ED", []) + values.get("A2", [])]
        if kind != "chapter"
        else [],
        "container-title": first("T2", "JF", "JO", "JA", "BT" if kind == "chapter" else ""),
        "volume": first("VL"),
        "issue": first("IS", "CP"),
        "DOI": first("DO"),
        "URL": first("UR", "L2"),
        "publisher": first("PB"),
        "ISBN": first("SN") if kind in {"book", "chapter"} else "",
        "ISSN": first("SN") if kind not in {"book", "chapter"} else "",
    }
    start, end = first("SP"), first("EP")
    if start:
        item["page"] = f"{start}-{end}" if end and end != start else start
    year = _YEAR.search(first("PY", "Y1", "DA"))
    if year:
        item["issued"] = {"date-parts": [[int(year.group(1))]]}
    return {k: v for k, v in item.items() if v}


def parse_ris_text(text: str, path: Path, encoding: str = "utf-8") -> BibFile:
    items: list[dict[str, Any]] = []
    lines: list[int] = []
    tags: list[tuple[str, str]] = []
    started = 0
    for number, line in enumerate(text.splitlines(), start=1):
        match = _TAG.match(line.rstrip())
        if match is None:
            if tags and line.strip():  # a value continued on the next line
                tag, value = tags[-1]
                tags[-1] = (tag, f"{value} {line.strip()}")
            continue
        tag, value = match.groups()
        if tag == "TY":
            tags, started = [(tag, value)], number
        elif tag == "ER":
            if tags:
                items.append(_item(tags, len(items) + 1))
                lines.append(started)
            tags = []
        elif tags:
            tags.append((tag, value))
    if tags:  # a last record without "ER  -"
        items.append(_item(tags, len(items) + 1))
        lines.append(started)
    return csl_entries(items, path, encoding, lines=lines, keep_ids=True)


def parse_ris_file(path: Path) -> BibFile:
    try:
        source = read_text(path)
    except OSError as exc:
        result = BibFile(path=path, encoding="unknown", derived=True)
        result.issues.append(BibIssue("unreadable", path, 1, None, str(exc)))
        return result
    return parse_ris_text(source.text, path, source.encoding)
