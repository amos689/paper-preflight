"""Render a verified source record as a BibTeX entry (used by `bib fetch`).

Every field comes from the record. Nothing is completed from memory or guessed: a field the
record does not have is left out, and an author list the source truncated ends in "and others".
A comment above the entry names the record it came from, so the entry can be traced.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import date

from paper_preflight.bib.normalize import fold
from paper_preflight.sources.record import Person, SourceRecord

# Crossref / CSL / DataCite / dblp work types -> BibTeX entry types
ENTRY_TYPES = {
    "journal-article": "article", "article-journal": "article", "article": "article",
    "journalarticle": "article",
    "proceedings-article": "inproceedings", "paper-conference": "inproceedings",
    "inproceedings": "inproceedings", "conferencepaper": "inproceedings",
    "book": "book", "monograph": "book", "edited-book": "book",
    "book-chapter": "incollection", "chapter": "incollection", "incollection": "incollection",
    "bookchapter": "incollection",
    "dissertation": "phdthesis", "thesis": "phdthesis", "phdthesis": "phdthesis",
    "report": "techreport", "techreport": "techreport",
}  # fmt: skip
SOURCE_NAMES = {
    "crossref": "Crossref", "datacite": "DataCite", "doiorg": "doi.org", "arxiv": "arXiv",
    "dblp": "dblp", "openalex": "OpenAlex", "s2": "Semantic Scholar", "pubmed": "PubMed",
}  # fmt: skip
_STOPWORDS = {
    "a",
    "an",
    "the",
    "on",
    "of",
    "for",
    "in",
    "to",
    "towards",
    "toward",
    "with",
    "and",
    "retracted",
    "withdrawn",
}  # Crossref prefixes retracted titles with "RETRACTED:"
_SPECIAL = {"&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#", "_": r"\_"}


def entry_type(record: SourceRecord) -> str:
    if is_arxiv_preprint(record):
        return "misc"
    return ENTRY_TYPES.get((record.work_type or "").lower(), "misc")


def is_arxiv_preprint(record: SourceRecord) -> bool:
    venue = (record.venue or "").lower()
    return (
        record.source == "arxiv"
        or record.work_type in {"preprint", "posted-content", "informal"}
        or venue in {"arxiv", "corr"}
    )


def escape(text: str) -> str:
    return "".join(_SPECIAL.get(char, char) for char in text)


def protect_title(title: str) -> str:
    """Brace words whose capitals BibTeX styles must keep ("{BERT}", "{ImageNet}", "{GELUs})"."""
    words = []
    for word in escape(title).split(" "):
        letters = [c for c in word if c.isalpha()]
        if len(letters) > 1 and any(c.isupper() for c in letters[1:]):
            word = "{" + word + "}"
        words.append(word)
    return " ".join(words)


def _ascii_word(text: str) -> str:
    folded = unicodedata.normalize("NFKD", fold(text))
    return re.sub(r"[^a-z0-9]", "", folded.encode("ascii", "ignore").decode())


def citation_key(record: SourceRecord) -> str:
    """``surname + year + first significant title word``, like ``he2016deep``."""
    first = record.authors[0] if record.authors else None
    surname = ""
    if first is not None:
        words = re.findall(r"[^\s-]+", first.literal or first.family)
        surname = _ascii_word(words[-1]) if words else ""
    title_words = [_ascii_word(w) for w in re.findall(r"[\w'-]+", record.title)]
    word = next((w for w in title_words if w and w not in _STOPWORDS), "")
    return f"{surname or 'anon'}{record.year or ''}{word}"


def _person(person: Person) -> str:
    if person.literal:
        return "{" + escape(person.literal) + "}"
    if person.given:
        return f"{escape(person.family)}, {escape(person.given)}"
    return escape(person.family)


def format_authors(record: SourceRecord) -> str:
    """The record's authors as a BibTeX author field ("Family, Given and ... [and others]")."""
    names = [_person(p) for p in record.authors]
    if names and not record.authors_complete:
        names.append("others")
    return " and ".join(names)


def _pages(pages: str) -> str:
    return re.sub(r"\s*[-–—]+\s*", "--", pages.strip())


def render(record: SourceRecord, *, key: str | None = None, today: date | None = None) -> str:
    """The record as a BibTeX entry, preceded by a comment naming where it came from."""
    kind = entry_type(record)
    fields: list[tuple[str, str]] = [("title", protect_title(record.title))]
    if record.authors:
        fields.append(("author", format_authors(record)))
    venue = escape(record.venue) if record.venue else None
    if venue and kind == "article":
        fields.append(("journal", venue))
    elif venue and kind in {"inproceedings", "incollection"}:
        fields.append(("booktitle", venue))
    if record.year:
        fields.append(("year", str(record.year)))
    if record.volume:
        fields.append(("volume", escape(record.volume)))
    if record.issue:
        fields.append(("number", escape(record.issue)))
    if record.pages:
        fields.append(("pages", _pages(record.pages)))
    if record.publisher and kind in {"book", "incollection", "phdthesis", "techreport"}:
        fields.append(("publisher", escape(record.publisher)))
    doi = record.doi
    if doi and not doi.startswith("10.48550/"):
        fields.append(("doi", doi))
    arxiv_id = record.identifiers.get("arxiv")
    if arxiv_id:
        fields += [("eprint", arxiv_id), ("archivePrefix", "arXiv")]
    if not doi and not arxiv_id and record.url:
        fields.append(("url", record.url))

    source = SOURCE_NAMES.get(record.source, record.source)
    stamp = (today or date.today()).isoformat()
    width = max(len(name) for name, _ in fields)
    lines = [
        f"% Verified with paper-preflight against {source} ({record.source_id}), {stamp}",
        f"@{kind}{{{key or citation_key(record)},",
    ]
    lines += [f"  {name:<{width}} = {{{value}}}," for name, value in fields]
    lines.append("}")
    return "\n".join(lines) + "\n"
