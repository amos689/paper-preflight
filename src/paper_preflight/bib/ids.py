"""Extract and validate persistent identifiers from BibTeX entries.

Identifiers are the strongest anchors for verification (ADR-0003), so extraction is careful about
where a value comes from and never invents one:

* DOI — ``doi`` field (with or without ``https://doi.org/`` or ``doi:`` prefixes), DOI URLs in
  ``url``/``note``/``howpublished``; DataCite arXiv DOIs (10.48550/arXiv.*) also yield an arXiv ID.
* arXiv — ``eprint`` (unless ``archiveprefix``/``eprinttype`` names another archive),
  ``journal = {arXiv preprint arXiv:1706.03762}`` (Google Scholar style), arxiv.org URLs, notes.
* PMID / PMCID, ISBN (checksum-validated), ISSN (checksum-validated).
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass

from paper_preflight.bib.parse import BibEntry

# Modern DOIs: 10.<registrant>/<suffix>. The suffix may contain almost anything; we stop at
# whitespace, quotes, braces, a lone angle bracket and trailing punctuation. Wiley's old SICI
# DOIs keep a bracketed part: 10.1002/1097-0347(200103)23:3<230::AID-HED1023>3.0.CO;2-V.
_DOI_RE = re.compile(r"\b(10\.\d{4,9}/(?:[^\s\"<>{}]|<[^\s\"<>{}]+>)+)", re.IGNORECASE)
_DOI_PREFIX_RE = re.compile(r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)", re.IGNORECASE)
_NEW_ARXIV_RE = re.compile(r"(?<![\d.])(\d{4}\.\d{4,5})(v\d+)?(?![\d])")
_OLD_ARXIV_RE = re.compile(r"\b([a-z][a-z-]+(?:\.[A-Z]{2})?/\d{7})(v\d+)?\b")
_ARXIV_CONTEXT_RE = re.compile(r"arxiv", re.IGNORECASE)
_ARXIV_DOI_RE = re.compile(r"^10\.48550/arxiv\.(.+)$", re.IGNORECASE)
_ARXIV_DOI_VERSION_RE = re.compile(r"v\d+$", re.IGNORECASE)
_PMCID_RE = re.compile(r"\bPMC\d{4,9}\b", re.IGNORECASE)
_TRAILING_PUNCTUATION = ".,;:)]}/"
ACM_UNREGISTERED = "10.5555/"


@dataclass(frozen=True)
class Identifier:
    scheme: str  # "doi" | "arxiv" | "pmid" | "pmcid" | "isbn" | "issn"
    value: str  # normalised (DOIs lower-cased, arXiv without version, ISBN digits only)
    field: str  # BibTeX field it came from
    version: str | None = None  # arXiv version, e.g. "v2"
    raw: str = ""

    def __str__(self) -> str:
        return f"{self.scheme}:{self.value}{self.version or ''}"


_CLOSING = {")": "(", "]": "[", "}": "{"}


def _trim(doi: str) -> str:
    """The DOI without punctuation that ends the sentence around it: "(see 10.1/x)." loses ")."
    but ASCE's "10.1061/(ASCE)1084-0702(2008)13:1(6)" keeps the parenthesis it opened."""
    while doi and doi[-1] in _TRAILING_PUNCTUATION:
        last = doi[-1]
        if last in _CLOSING and doi.count(_CLOSING[last]) >= doi.count(last):
            break
        doi = doi[:-1]
    return doi


def normalize_doi(value: str) -> str | None:
    """Return a normalised DOI or None if ``value`` contains no DOI."""
    candidate = _DOI_PREFIX_RE.sub("", value.strip())
    match = _DOI_RE.search(candidate)
    if not match:
        return None
    doi = _trim(match.group(1)).lower()
    # arXiv DOIs are registered without a version: doi.org answers 404 for "...2602.12139v1"
    # (seen in HALLMARK's VALID entries), so the version suffix is not part of the DOI.
    if _ARXIV_DOI_RE.match(doi):
        doi = _ARXIV_DOI_VERSION_RE.sub("", doi)
    return doi


def is_valid_doi_syntax(value: str) -> bool:
    return bool(re.fullmatch(r"10\.\d{4,9}/\S+", value))


def _arxiv_in(text: str, require_context: bool) -> tuple[str, str | None] | None:
    if require_context and not _ARXIV_CONTEXT_RE.search(text):
        return None
    match = _NEW_ARXIV_RE.search(text) or _OLD_ARXIV_RE.search(text)
    if not match:
        return None
    return match.group(1), match.group(2)


def _isbn_digits(value: str) -> str | None:
    digits = re.sub(r"[\s-]", "", value).upper()
    if re.fullmatch(r"\d{9}[\dX]", digits):
        total = sum((10 - i) * (10 if c == "X" else int(c)) for i, c in enumerate(digits))
        return digits if total % 11 == 0 else None
    if re.fullmatch(r"97[89]\d{10}", digits):
        total = sum((1 if i % 2 == 0 else 3) * int(c) for i, c in enumerate(digits))
        return digits if total % 10 == 0 else None
    return None


def _issn(value: str) -> str | None:
    match = re.search(r"\b(\d{4})-?(\d{3}[\dXx])\b", value)
    if not match:
        return None
    digits = (match.group(1) + match.group(2)).upper()
    total = sum((8 - i) * int(c) for i, c in enumerate(digits[:7]))
    check = (11 - total % 11) % 11
    expected = "X" if check == 10 else str(check)
    return f"{digits[:4]}-{digits[4:]}" if digits[7] == expected else None


def extract_identifiers(entry: BibEntry) -> list[Identifier]:
    """Return all identifiers found in an entry, most authoritative fields first, deduplicated."""
    found: list[Identifier] = []

    def add(identifier: Identifier) -> None:
        if all((i.scheme, i.value) != (identifier.scheme, identifier.value) for i in found):
            found.append(identifier)

    def add_doi(text: str, field: str) -> None:
        doi = normalize_doi(text)
        if doi is None:
            return
        # the RFC Editor writes "10.17487/RFC0791"; Crossref files it as 10.17487/rfc791
        doi = _RFC_PADDING.sub("", doi)
        add(Identifier("doi", doi, field, raw=text))
        arxiv_doi = _ARXIV_DOI_RE.match(doi)
        if arxiv_doi:
            # read the arXiv ID from the text as written, so a version suffix is kept
            written = re.search(r"10\.48550/arxiv\.(\S+)", text, re.IGNORECASE)
            arxiv = _arxiv_in((written or arxiv_doi).group(1), require_context=False)
            if arxiv:
                add(Identifier("arxiv", arxiv[0], field, arxiv[1], raw=text))

    doi_field = entry.text("doi")
    if doi_field:
        add_doi(doi_field, "doi")

    archive = (entry.text("archiveprefix") or entry.text("eprinttype") or "").strip().lower()
    eprint = entry.text("eprint")
    if eprint:
        if archive in ("", "arxiv"):
            arxiv = _arxiv_in(eprint, require_context=False)
            if arxiv:
                add(Identifier("arxiv", arxiv[0], "eprint", arxiv[1], raw=eprint))
        elif archive in ("pubmed", "pmid") and eprint.strip().isdigit():
            add(Identifier("pmid", eprint.strip(), "eprint", raw=eprint))

    for field in ("journal", "booktitle", "url", "note", "howpublished", "publisher"):
        value = entry.text(field)
        if not value:
            continue
        if field in ("url", "note", "howpublished") and "doi" in value.lower():
            doi = normalize_doi(value)
            # ACM's own 10.5555 numbers are registered with no agency: a Digital Library link
            # carrying one (dl.acm.org/doi/10.5555/3666122.3666563) is a working page, not a
            # DOI to look up. A doi field holding one is still checked.
            unregistered = bool(doi and doi.startswith(ACM_UNREGISTERED))
            # a publisher's page for the doi field's DOI, with more path after it
            # (academic.oup.com/bib/article/doi/10.1093/bib/bbw110/2562646/A-review-of...)
            known = normalize_doi(doi_field) if doi_field else None
            page = bool(doi and known and doi.startswith(known + "/"))
            if not unregistered and not page:
                add_doi(value, field)
        arxiv = _arxiv_in(value, require_context=True)
        if arxiv:
            add(Identifier("arxiv", arxiv[0], field, arxiv[1], raw=value))

    if not any(i.scheme == "doi" for i in found):
        rfc = _rfc_number(entry)
        if rfc is not None:
            # every RFC has a DOI from the RFC Editor: RFC 791 is 10.17487/RFC0791, which
            # Crossref files as 10.17487/rfc791
            number, field, raw = rfc
            add(Identifier("doi", f"10.17487/rfc{number}", field, raw=raw))

    pmid = entry.text("pmid")
    if pmid and pmid.strip().isdigit():
        add(Identifier("pmid", pmid.strip(), "pmid", raw=pmid))
    pmcid_text = entry.text("pmcid")
    if pmcid_text:
        match = _PMCID_RE.search(pmcid_text)
        if match:
            add(Identifier("pmcid", match.group(0).upper(), "pmcid", raw=pmcid_text))
    isbn_text = entry.text("isbn")
    if isbn_text:
        for part in re.split(r"[,;]", isbn_text):
            digits = _isbn_digits(part)
            if digits:
                add(Identifier("isbn", digits, "isbn", raw=part.strip()))
    issn_text = entry.text("issn")
    if issn_text:
        issn = _issn(issn_text)
        if issn:
            add(Identifier("issn", issn, "issn", raw=issn_text))
    return found


_RFC_PADDING = re.compile(r"(?<=^10\.17487/rfc)0+(?=\d)")
# "RFC 2616", "RFC2616", "Request for Comments 2616"; rfc-editor.org/rfc/rfc2616,
# ietf.org/rfc/rfc2616.txt, datatracker.ietf.org/doc/html/rfc2616
_RFC_TEXT = re.compile(r"\b(?:RFC|Request\s+for\s+Comments)[\s:#-]*(\d{1,5})\b", re.I)
_RFC_URL = re.compile(r"(?:rfc-editor\.org|ietf\.org)/\S*?\brfc(\d{1,5})\b", re.I)


def _rfc_number(entry: BibEntry) -> tuple[int, str, str] | None:
    """An RFC's number, the field that gives it and the text as written."""
    kind = " ".join(entry.text(f) or "" for f in ("type", "series", "institution", "publisher"))
    number = (entry.text("number") or "").strip()
    if number.isdigit() and re.search(r"\b(?:RFC|Request for Comments)\b", kind, re.I):
        return int(number), "number", number
    for field in ("howpublished", "series", "number", "note", "journal", "booktitle"):
        text = entry.text(field) or ""
        if field in {"note", "journal", "booktitle"} and len(text) > 40:
            continue  # a note that mentions an RFC is not one that names the entry as it
        match = _RFC_TEXT.search(text)
        if match:
            return int(match.group(1)), field, match.group(0)
    url = entry.text("url") or ""
    match = _RFC_URL.search(url)
    if match:
        return int(match.group(1)), "url", url
    return None


def first(identifiers: Iterable[Identifier], scheme: str) -> Identifier | None:
    return next((i for i in identifiers if i.scheme == scheme), None)
