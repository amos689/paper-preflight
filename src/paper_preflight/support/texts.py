"""A cited work's text, from the forms the sources give it in.

* OpenAlex keeps abstracts as an inverted index (word → positions): :func:`inverted_abstract`.
* Europe PMC serves open-access full text as JATS XML: :func:`jats_passages` keeps the abstract
  first, then the body's paragraphs, and leaves out the reference list, tables and figures'
  graphics (their captions stay).
* Crossref abstracts are JATS fragments: :func:`jats_fragment_text`.
* :func:`incomplete` says why a text is no full text: a publisher's paywall page, a first page
  only, an extraction that came out empty.
"""

from __future__ import annotations

import html
import re
import xml.etree.ElementTree as ET
from pathlib import Path

MIN_FULL_TEXT_CHARS = 5_000  # a full paper has more; a landing page or first page has less
_PAYWALL = re.compile(
    r"access through your institution|purchase (?:this )?(?:article|pdf)|buy (?:this )?article"
    r"|log ?in to (?:view|access|read)|subscribe to (?:read|access|view)|rent this article"
    r"|get access|institutional login",
    re.IGNORECASE,
)


def inverted_abstract(index: dict[str, list[int]] | None) -> str:
    """OpenAlex's ``abstract_inverted_index`` as text."""
    if not index:
        return ""
    places = {position: word for word, positions in index.items() for position in positions}
    return " ".join(places[i] for i in sorted(places))


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _text(element: ET.Element) -> str:
    """An element's text without that of skipped children (formulas, tables), but with what
    follows them."""
    parts: list[str] = []

    def walk(node: ET.Element) -> None:
        parts.append(node.text or "")
        for child in node:
            if _local(child.tag) not in _SKIPPED:
                walk(child)
            parts.append(child.tail or "")

    walk(element)
    return " ".join("".join(parts).split())


# JATS elements whose text is not prose for evidence
_SKIPPED = frozenset({"ref-list", "table", "graphic", "inline-graphic", "media", "disp-formula",
                      "tex-math", "mml:math", "math", "fn-group", "ack", "glossary"})  # fmt: skip


_NAMED_ENTITY = re.compile(r"&(?!(?:amp|lt|gt|quot|apos);)[a-zA-Z][a-zA-Z0-9]*;")


def jats_passages(xml_text: str) -> list[str]:
    """The abstract (one passage) and the body's paragraphs of a JATS article."""
    # HTML entities XML does not know ("&nbsp;") would stop the parser
    xml_text = _NAMED_ENTITY.sub(lambda m: html.unescape(m.group(0)), xml_text)
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []
    abstract = " ".join(
        _text(p)
        for element in root.iter()
        if _local(element.tag) == "abstract"
        for p in element.iter()
        if _local(p.tag) == "p"
    )
    passages = [abstract] if abstract else []
    body = next((e for e in root.iter() if _local(e.tag) == "body"), None)
    if body is None:
        return passages

    def walk(element: ET.Element) -> None:
        name = _local(element.tag)
        if name in _SKIPPED:
            return
        if name in {"p", "title"} or (name == "caption" and len(element) == 0):
            text = _text(element)
            if text:
                passages.append(text)
            return
        for child in element:
            walk(child)

    walk(body)
    return passages


def jats_fragment_text(fragment: str) -> str:
    """A JATS fragment's text (Crossref's ``abstract``: "<jats:p>...</jats:p>")."""
    text = re.sub(r"<[^>]+>", " ", fragment)
    text = html.unescape(text)
    text = re.sub(r"^\s*abstract\b[:.]?\s*", "", " ".join(text.split()), flags=re.IGNORECASE)
    return text


PASSAGE_WORDS = 150
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9(\[])")


def passages_of(text: str, size: int = PASSAGE_WORDS) -> list[str]:
    """Running text cut into passages of about ``size`` words, at sentence ends."""
    passages: list[str] = []
    current: list[str] = []
    count = 0
    for sentence in _SENTENCE_END.split(" ".join(text.split())):
        current.append(sentence)
        count += len(sentence.split())
        if count >= size:
            passages.append(" ".join(current))
            current, count = [], 0
    if current:
        passages.append(" ".join(current))
    return passages


def pdf_passages(path: Path) -> list[str]:
    """A PDF's prose before its reference list, as passages (needs the ``pdf`` extra).

    Lines broken with a hyphen are joined ("conver-" + "gence" is "convergence").
    """
    from paper_preflight.bib.pdftext import body_lines, pdf_text

    text = "\n".join(body_lines(pdf_text(path)))
    text = re.sub(r"(?<=[a-z])-\n(?=[a-z])", "", text)
    return passages_of(text)


def incomplete(passages: list[str]) -> str | None:
    """Why a supposed full text is not one, or None when it can stand as the work's text."""
    text = " ".join(passages)
    if not text.strip():
        return "no text could be extracted"
    if _PAYWALL.search(text[:3000]):
        return "a publisher's access page, not the article"
    if len(text) < MIN_FULL_TEXT_CHARS:
        return "too short for a full article (a first page or a landing page)"
    return None
