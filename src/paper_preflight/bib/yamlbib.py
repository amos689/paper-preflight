"""Read YAML bibliographies: Typst's Hayagriva format and Pandoc's CSL YAML.

Hayagriva keys each entry by its citation key, with fields such as ``type``, ``title``,
``author``, ``date``, ``parent`` (the journal or proceedings it appeared in) and
``serial-number`` (``doi``, ``arxiv``, ``isbn`` ...). CSL YAML is CSL-JSON written as YAML, a
list of items or a ``references:`` list. Both become BibTeX entries through the CSL reader; the
file is marked derived: checked, never edited.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from paper_preflight.bib.csl import csl_entries
from paper_preflight.bib.parse import BibFile, BibIssue
from paper_preflight.textio import read_text

# Hayagriva's entry types (and the parent's) as CSL types
_TYPES = {
    "article": "article-journal",
    "book": "book",
    "chapter": "chapter",
    "anthos": "chapter",
    "thesis": "thesis",
    "report": "report",
    "web": "webpage",
    "blog": "post-weblog",
    "repository": "software",
    "manuscript": "manuscript",
    "proceedings": "paper-conference",
    "conference": "paper-conference",
    "reference": "entry-encyclopedia",
}
_TOP_KEY = re.compile(r"^([^\s#:][^:]*?):\s*(?:#.*)?$", re.M)


def _text(value: Any) -> str:
    if isinstance(value, dict):  # Hayagriva's formattable strings: {value: ..., short: ...}
        value = value.get("value", "")
    if isinstance(value, list):
        value = value[0] if value else ""
    return " ".join(str(value or "").split())


def _names(value: Any) -> list[dict[str, str]]:
    people = value if isinstance(value, list) else [value] if value else []
    names = []
    for person in people:
        if isinstance(person, dict):  # {name: Family, given-name: Given}
            family = _text(person.get("name"))
            given = _text(person.get("given-name"))
            names.append({"family": family, "given": given} if given else {"literal": family})
            continue
        family, _, given = str(person).partition(",")
        names.append(
            {"family": family.strip(), "given": given.strip()} if given else {"literal": family}
        )
    return [n for n in names if any(n.values())]


def _year(value: Any) -> str:
    found = re.search(r"(?<!\d)(1[5-9]\d\d|20\d\d)(?!\d)", str(value or ""))
    return found.group(1) if found else ""


def hayagriva_item(key: str, entry: dict[str, Any]) -> dict[str, Any]:
    parent = entry.get("parent")
    if isinstance(parent, list):
        parent = parent[0] if parent else None
    parent = parent if isinstance(parent, dict) else {}
    kind = str(entry.get("type") or "misc").lower()
    parent_kind = str(parent.get("type") or "").lower()
    csl_type = _TYPES.get(kind, "article")
    if kind == "article" and parent_kind in {"proceedings", "conference"}:
        csl_type = "paper-conference"
    elif kind == "article" and parent_kind not in {"", "periodical", "newspaper"}:
        csl_type = "article"
    serial = entry.get("serial-number") or {}
    serial = serial if isinstance(serial, dict) else {"doi": serial}
    item: dict[str, Any] = {
        "id": key,
        "type": csl_type,
        "title": _text(entry.get("title")),
        "author": _names(entry.get("author")),
        "editor": _names(entry.get("editor") or parent.get("editor")),
        "container-title": _text(parent.get("title")),
        "volume": _text(entry.get("volume") or parent.get("volume")),
        "issue": _text(entry.get("issue") or parent.get("issue")),
        "page": _text(entry.get("page-range")),
        "publisher": _text(entry.get("publisher") or parent.get("publisher")),
        "DOI": _text(serial.get("doi")),
        "URL": _text(entry.get("url")),
        "ISBN": _text(serial.get("isbn")),
    }
    if serial.get("arxiv"):
        item["number"] = f"arXiv:{_text(serial['arxiv'])}"
    year = _year(entry.get("date") or parent.get("date"))
    if year:
        item["issued"] = {"date-parts": [[int(year)]]}
    return {k: v for k, v in item.items() if v}


def parse_yaml_bibliography(path: Path) -> BibFile:
    try:
        source = read_text(path)
        data = yaml.safe_load(source.text)
    except (OSError, yaml.YAMLError) as exc:
        result = BibFile(path=path, encoding="unknown", derived=True)
        result.issues.append(BibIssue("unreadable", path, 1, None, str(exc)))
        return result
    if isinstance(data, dict) and isinstance(data.get("references"), list):
        data = data["references"]  # Pandoc's CSL YAML front matter
    if isinstance(data, list):  # CSL YAML: CSL-JSON items written as YAML
        items = [i for i in data if isinstance(i, dict)]
        return csl_entries(items, path, source.encoding, keep_ids=True)
    if not isinstance(data, dict):
        return BibFile(path=path, encoding=source.encoding, derived=True)
    lines = {m.group(1).strip("'\""): source.text.count("\n", 0, m.start()) + 1
             for m in _TOP_KEY.finditer(source.text)}  # fmt: skip
    keys = [str(k) for k, v in data.items() if isinstance(v, dict)]
    items = [hayagriva_item(k, data[k]) for k in keys]
    return csl_entries(
        items, path, source.encoding, lines=[lines.get(k, 1) for k in keys], keep_ids=True
    )
