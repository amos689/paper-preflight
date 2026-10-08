"""Read the references of a Word manuscript (.docx).

A .docx is a zip of XML. The references are taken from the first of these that has any:

* the citations a reference manager wrote into the text as field codes. Zotero and Mendeley
  write CSL-JSON ("ADDIN ZOTERO_ITEM CSL_CITATION {...}", "ADDIN CSL_CITATION {...}"); EndNote
  writes its XML ("ADDIN EN.CITE <EndNote>...", or base64 in the field's data for
  "ADDIN EN.CITE.DATA"). These are the references as the manager holds them: exact fields,
  identifiers included;
* Word's own source manager (``customXml/item*.xml``, ``<b:Sources>``);
* the reference list as typed: the paragraphs in Word's "Bibliography" style, or those after a
  "References" heading, read with the plain-text reader.

Positions are paragraph numbers. The file is marked derived: checked, never edited.
"""

from __future__ import annotations

import base64
import binascii
import json
import re
import zipfile
from dataclasses import replace
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from paper_preflight.bib.csl import csl_entries
from paper_preflight.bib.parse import BibFile, BibIssue
from paper_preflight.bib.plaintext import parse_plaintext

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
B = "{http://schemas.openxmlformats.org/officeDocument/2006/bibliography}"
MAX_PART = 64 * 1024 * 1024  # bytes of XML read from one part of the zip
_REFERENCE_HEADING = re.compile(
    r"^(?:\d+\.?\s*|[ivx]+\.\s*)?(?:references?|bibliography|works cited|literature cited|"
    r"reference list|references cited|cited literature|参考文献)\s*:?$",
    re.I,
)
_CSL_FIELD = re.compile(r"\bADDIN\s+(?:ZOTERO_ITEM\s+)?CSL_CITATION\b")
_ENDNOTE_FIELD = re.compile(r"\bADDIN\s+EN\.CITE(\.DATA)?\b")


class _Field:
    def __init__(self, paragraph: int, data: str) -> None:
        self.paragraph = paragraph
        self.instruction: list[str] = []
        self.data = data


def _xml(archive: zipfile.ZipFile, name: str) -> ET.Element | None:
    info = archive.getinfo(name)
    if info.file_size > MAX_PART:
        raise ValueError(f"{name} is larger than {MAX_PART // (1024 * 1024)} MB")
    raw = archive.read(name)
    if b"<!DOCTYPE" in raw or b"<!ENTITY" in raw:
        raise ValueError(f"{name} declares a DTD, which a Word document never needs")
    return ET.fromstring(raw)


def _paragraphs_and_fields(
    root: ET.Element,
) -> tuple[list[tuple[str, str]], list[tuple[int, str, str]]]:
    """Each paragraph's (style, text), and each field's (paragraph, instruction, data)."""
    paragraphs: list[tuple[str, str]] = []
    fields: list[tuple[int, str, str]] = []
    open_fields: list[_Field] = []
    text: list[str] = []
    style = ""
    in_tables = {id(p) for table in root.iter(f"{W}tbl") for p in table.iter(f"{W}p")}
    for element in root.iter():
        tag = element.tag
        if tag == f"{W}p":
            if paragraphs or text or style:
                paragraphs.append((style, "".join(text)))
            text, style = [], (IN_TABLE if id(element) in in_tables else "")
        elif tag == f"{W}pStyle":
            if style != IN_TABLE:
                style = element.get(f"{W}val", "")
        elif tag == f"{W}t":
            text.append(element.text or "")
        elif tag in {f"{W}tab", f"{W}br"}:
            text.append(" ")
        elif tag == f"{W}fldChar":
            kind = element.get(f"{W}fldCharType")
            if kind == "begin":
                data = element.find(f"{W}fldData")
                open_fields.append(
                    _Field(len(paragraphs) + 1, (data.text or "") if data is not None else "")
                )
            elif kind == "end" and open_fields:
                done = open_fields.pop()
                fields.append((done.paragraph, "".join(done.instruction), done.data))
        elif tag == f"{W}instrText" and open_fields:
            open_fields[-1].instruction.append(element.text or "")
        elif tag == f"{W}fldSimple":
            fields.append((len(paragraphs) + 1, element.get(f"{W}instr", ""), ""))
    paragraphs.append((style, "".join(text)))
    return paragraphs, fields


def _csl_items(instruction: str) -> list[dict[str, Any]]:
    start = instruction.find("{")
    if start < 0:
        return []
    try:
        data, _ = json.JSONDecoder().raw_decode(instruction[start:])
    except ValueError:
        return []
    items = []
    for cited in data.get("citationItems") or []:
        item = cited.get("itemData") if isinstance(cited, dict) else None
        if isinstance(item, dict):
            uris = cited.get("uris") or [cited.get("uri")]
            identity = str(uris[0] or item.get("id") or "")
            if not identity or re.fullmatch(r"ITEM-\d+", identity):
                # Mendeley's "ITEM-1" names a place in one citation, not a work: the work is
                # what the record says
                identity = json.dumps([item.get(k) for k in ("DOI", "title", "issued", "author")])
            items.append({**item, "_identity": identity})
    return items


# EndNote's reference types as CSL types
_ENDNOTE_TYPES = {
    "journal article": "article-journal",
    "conference proceedings": "paper-conference",
    "conference paper": "paper-conference",
    "book": "book",
    "edited book": "book",
    "book section": "chapter",
    "thesis": "thesis",
    "report": "report",
    "web page": "webpage",
    "electronic article": "article-journal",
    "dataset": "dataset",
    "computer program": "software",
}


def _text_of(element: ET.Element | None) -> str:
    return " ".join("".join(element.itertext()).split()) if element is not None else ""


def _name(text: str) -> dict[str, str]:
    family, _, given = text.partition(",")
    return {"family": family.strip(), "given": given.strip()} if given else {"literal": text}


def _endnote_items(xml: str) -> list[dict[str, Any]]:
    start = xml.find("<EndNote")
    if start < 0 or "<!DOCTYPE" in xml or "<!ENTITY" in xml:
        return []
    try:
        root = ET.fromstring(xml[start:])
    except ET.ParseError:
        return []
    items = []
    for record in root.iter("record"):
        ref_type = record.find("ref-type")
        kind = _ENDNOTE_TYPES.get(
            (ref_type.get("name", "") if ref_type is not None else "").lower(), "article"
        )
        container = _text_of(record.find("titles/secondary-title")) or _text_of(
            record.find("periodical/full-title")
        )
        year = _text_of(record.find("dates/year"))
        item: dict[str, Any] = {
            "type": kind,
            "title": _text_of(record.find("titles/title")),
            "author": [_name(_text_of(a)) for a in record.findall("contributors/authors/author")],
            "container-title": container,
            "volume": _text_of(record.find("volume")),
            "issue": _text_of(record.find("number")),
            "page": _text_of(record.find("pages")),
            "DOI": _text_of(record.find("electronic-resource-num")),
            "URL": _text_of(record.find("urls/related-urls/url")),
            "ISBN": _text_of(record.find("isbn")),
            "publisher": _text_of(record.find("publisher")),
            "_identity": "endnote:" + _text_of(record.find("rec-number")),
        }
        if year[:4].isdigit():
            item["issued"] = {"date-parts": [[int(year[:4])]]}
        items.append({k: v for k, v in item.items() if v})
    return items


def _endnote_data(instruction: str, data: str) -> str:
    """EN.CITE carries its XML in the instruction; EN.CITE.DATA in the field's base64 data."""
    match = _ENDNOTE_FIELD.search(instruction)
    if match is None:
        return ""
    if not match.group(1):
        return instruction[match.end() :]
    try:
        decoded = base64.b64decode("".join(data.split()), validate=False)
    except (binascii.Error, ValueError):
        return ""
    for encoding in ("utf-8", "utf-16"):
        try:
            return decoded.decode(encoding)
        except UnicodeDecodeError:
            continue
    return ""


# Word's source types as CSL types
_WORD_TYPES = {
    "JournalArticle": "article-journal",
    "ArticleInAPeriodical": "article-magazine",
    "ConferenceProceedings": "paper-conference",
    "Book": "book",
    "BookSection": "chapter",
    "Report": "report",
    "InternetSite": "webpage",
    "DocumentFromInternetSite": "webpage",
    "ElectronicSource": "webpage",
}


def _word_source(source: ET.Element) -> dict[str, Any]:
    def get(name: str) -> str:
        return _text_of(source.find(f"{B}{name}"))

    people: list[dict[str, str]] = []
    for person in source.iterfind(f"{B}Author/{B}Author/{B}NameList/{B}Person"):
        given = (_text_of(person.find(f"{B}First")), _text_of(person.find(f"{B}Middle")))
        people.append(
            {"family": _text_of(person.find(f"{B}Last")), "given": " ".join(g for g in given if g)}
        )
    corporate = _text_of(source.find(f"{B}Author/{B}Author/{B}Corporate"))
    if corporate:
        people.append({"literal": corporate})
    container = (
        get("JournalName") or get("ConferenceName") or get("BookTitle") or get("PeriodicalTitle")
    )
    item: dict[str, Any] = {
        "id": get("Tag"),
        "type": _WORD_TYPES.get(get("SourceType"), "article"),
        "title": get("Title"),
        "author": people,
        "container-title": container,
        "volume": get("Volume"),
        "issue": get("Issue"),
        "page": get("Pages"),
        "DOI": get("DOI"),
        "URL": get("URL"),
        "publisher": get("Publisher"),
        "_identity": "word:" + get("Tag"),
    }
    year = get("Year")
    if year[:4].isdigit():
        item["issued"] = {"date-parts": [[int(year[:4])]]}
    return {k: v for k, v in item.items() if v}


def _word_sources(root: ET.Element) -> list[dict[str, Any]]:
    return [_word_source(source) for source in root.iter(f"{B}Source")]


def _typed_list(paragraphs: list[tuple[str, str]]) -> list[tuple[int, str]]:
    """The reference list as typed: Word's "Bibliography" paragraphs, or those after a
    "References" heading. Headings are often only bold text, so the list also ends at a table,
    a caption ("Figure 1."), a section that follows references (Appendix, Funding ...), or
    three paragraphs in a row with no year or identifier; only paragraphs with one are kept."""
    styled = [(n, t) for n, (s, t) in enumerate(paragraphs, 1) if s.lower() == "bibliography"]
    if styled:
        return [(n, t) for n, t in styled if t.strip()]
    heading = next(
        (n for n, (_, text) in enumerate(paragraphs, 1) if _REFERENCE_HEADING.match(text.strip())),
        None,
    )
    if heading is None:
        return []
    found: list[tuple[int, str]] = []
    without = 0
    for number, (style, line) in enumerate(paragraphs[heading:], heading + 1):
        text = line.strip()
        if not text:
            continue
        ends = (
            style == IN_TABLE
            or style.lower().startswith(("heading", "title", "caption"))
            or _AFTER_REFERENCES.match(text)
        )
        if ends:
            if found:
                break
            continue  # a table or caption is never a reference
        if _REFERENCE_MARK.search(text):
            found.append((number, line))
            without = 0
        else:
            without += 1
            if without >= 3 and found:
                break
    return found


IN_TABLE = "\x00table"  # the style given to a paragraph in a table
# what follows a reference list in a manuscript
_AFTER_REFERENCES = re.compile(
    r"^(?:(?:fig(?:ure)?|table|scheme|plate)s?\.?\s*[S\d]|appendi(?:x|ces)\b|supplementary\b|"
    r"supporting information\b|acknowledge?ments?\b|funding\b|author contributions?\b|"
    r"conflicts? of interest\b|competing interests?\b|data availability\b|abbreviations\b|"
    r"figure captions?\b|tables?$|figures?$)",
    re.I,
)
# a reference has a year or an identifier
_REFERENCE_MARK = re.compile(r"(?<!\d)(?:1[5-9]|20)\d\d(?!\d)|\b10\.\d{4,9}/|arxiv|https?://", re.I)


def parse_docx_file(path: Path) -> BibFile:
    try:
        with zipfile.ZipFile(path) as archive:
            document = _xml(archive, "word/document.xml")
            custom = [
                _xml(archive, name)
                for name in archive.namelist()
                if re.fullmatch(r"customXml/item\d+\.xml", name)
            ]
    except (OSError, KeyError, ValueError, zipfile.BadZipFile, ET.ParseError) as exc:
        result = BibFile(path=path, encoding="unknown", derived=True)
        result.issues.append(BibIssue("unreadable", path, 1, None, str(exc)))
        return result
    paragraphs, fields = _paragraphs_and_fields(document) if document is not None else ([], [])

    items: list[dict[str, Any]] = []
    lines: list[int] = []
    seen: set[str] = set()

    def add(found: list[dict[str, Any]], paragraph: int) -> None:
        for item in found:
            identity = item.pop("_identity", "") or json.dumps(item, sort_keys=True)
            if identity in seen:
                continue
            seen.add(identity)
            items.append(item)
            lines.append(paragraph)

    for paragraph, instruction, data in fields:
        if _CSL_FIELD.search(instruction):
            add(_csl_items(instruction), paragraph)
        elif _ENDNOTE_FIELD.search(instruction):
            add(_endnote_items(_endnote_data(instruction, data)), paragraph)
    if not items:
        for root in custom:
            if root is not None and root.tag == f"{B}Sources":
                add(_word_sources(root), 1)
    if items:
        return csl_entries(items, path, lines=lines)

    typed = _typed_list(paragraphs)
    parsed = parse_plaintext("\n".join(text for _, text in typed), path)
    numbers = [n for n, _ in typed]
    result = BibFile(path=path, encoding="utf-8", derived=True, issues=parsed.issues)
    for entry in parsed.entries:
        line = numbers[entry.line - 1] if 0 < entry.line <= len(numbers) else entry.line
        at = {name: replace(f, line=line) for name, f in entry.fields.items()}
        result.entries.append(replace(entry, fields=at, line=line))
    return result
