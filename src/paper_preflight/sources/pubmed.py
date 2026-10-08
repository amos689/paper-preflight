"""PubMed via NCBI E-utilities (``esummary``): the registry of PMIDs.

PubMed assigns PMIDs, so it is authoritative for them: a PMID it does not know does not exist
(REF002), and its record anchors an entry the way a DOI's record does. Its publication types
also mark retracted articles ("Retracted Publication", REF004). NCBI allows three requests per
second without an API key and ten with one (``NCBI_API_KEY``, sent as ``api_key``); up to 200
IDs fit in one request, and ``tool``/``email`` identify the caller. None of the three is part of
a cache key.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any

from paper_preflight.cache import EntryKind
from paper_preflight.sources.base import PartialUnavailable, SourceClient, SourcePolicy
from paper_preflight.sources.record import Person, SourceRecord, collapse, plain_title

ESUMMARY_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
BATCH = 200
TOOL = "paper-preflight"

POLICY = SourcePolicy(name="pubmed", min_interval=0.4, max_concurrency=1)
# with an API key: ten requests a second
KEYED_POLICY = SourcePolicy(name="pubmed", min_interval=0.11, max_concurrency=1)

_INITIALS = re.compile(r"^[A-Z]{1,4}$")
_PLACE = re.compile(r"\s*\([^)]*\)$")  # "Lancet (London, England)"


def parse_author(author: dict[str, Any]) -> Person | None:
    """PubMed writes "Walker-Smith JA": the family name, then the initials without dots."""
    name = collapse(str(author.get("name") or ""))
    if not name:
        return None
    if author.get("authtype") == "CollectiveName":
        return Person(family="", literal=name)
    parts = name.split()
    if len(parts) >= 2 and _INITIALS.match(parts[-1]):
        return Person(family=" ".join(parts[:-1]), given=" ".join(f"{c}." for c in parts[-1]))
    return Person.from_display(name)


def parse_summary(item: dict[str, Any]) -> SourceRecord:
    uid = str(item.get("uid", ""))
    title = collapse(str(item.get("title") or ""))
    if title.startswith("[") and title.rstrip(".").endswith("]"):
        title = title.rstrip(".")[1:-1]  # a translated title: [English title].
    title = plain_title(title.removesuffix("."))
    authors = tuple(
        person for a in item.get("authors") or [] if (person := parse_author(a)) is not None
    )
    match = re.match(r"\d{4}", str(item.get("pubdate") or item.get("epubdate") or ""))
    year = int(match.group(0)) if match else None
    identifiers = {"pmid": uid}
    for article_id in item.get("articleids") or []:
        kind, value = article_id.get("idtype"), str(article_id.get("value") or "").strip()
        if kind == "doi" and value:
            identifiers["doi"] = value.lower()
        elif kind == "pmc" and value:
            identifiers["pmcid"] = value.upper()
    venue = _PLACE.sub("", str(item.get("fulljournalname") or item.get("source") or "")) or None
    pubtypes = [str(t) for t in item.get("pubtype") or []]
    retracted = "Retracted Publication" in pubtypes
    return SourceRecord(
        source="pubmed",
        source_id=uid,
        title=title,
        authors=authors,
        authors_complete=True,
        year=year,
        years=frozenset({year} if year else set()),
        venue=venue,
        work_type="journal-article" if "Journal Article" in pubtypes else None,
        identifiers=identifiers,
        status=frozenset({"retracted"} if retracted else set()),
        status_sources=("pubmed:pubtype",) if retracted else (),
        url=f"https://pubmed.ncbi.nlm.nih.gov/{uid}/",
    )


async def by_pmids(
    client: SourceClient,
    pmids: Iterable[str],
    *,
    email: str | None = None,
    api_key: str | None = None,
) -> dict[str, SourceRecord]:
    """Records keyed by PMID. A PMID PubMed has no summary for is cached as "no such PMID"."""
    unique = list(dict.fromkeys(p.strip() for p in pmids if p.strip().isdigit()))

    def classify(payload: Any) -> EntryKind:
        return (
            EntryKind.POSITIVE
            if ((payload or {}).get("result") or {}).get("uids")
            else EntryKind.NEGATIVE
        )

    async def fetch_chunk(chunk: list[str]) -> dict[str, Any]:
        params = {"db": "pubmed", "id": ",".join(chunk), "retmode": "json", "tool": TOOL}
        if email:
            params["email"] = email
        if api_key:
            params["api_key"] = api_key
        fetched = await client.get_json(ESUMMARY_URL, params=params, classify=classify)
        result = (fetched.data or {}).get("result") or {}
        return {
            uid: result[uid]
            for uid in result.get("uids") or []
            if isinstance(result.get(uid), dict) and "error" not in result[uid]
        }

    try:
        items = await client.batch("pmid", unique, fetch_chunk, chunk_size=BATCH)
    except PartialUnavailable as partial:
        raise partial.with_found({k: parse_summary(v) for k, v in partial.found.items()}) from None
    return {pmid: parse_summary(item) for pmid, item in items.items()}


async def pmids_for_pmcids(
    client: SourceClient,
    pmcids: Iterable[str],
    *,
    email: str | None = None,
    api_key: str | None = None,
) -> dict[str, str | None]:
    """The PMID of each PMCID ("PMC3531190"), from PubMed Central's summaries.

    A PMCID PubMed Central has no summary for does not exist and is left out; one whose article
    has no PMID maps to None.
    """
    unique = list(dict.fromkeys(p.upper() for p in pmcids if re.fullmatch(r"PMC\d+", p.upper())))

    def classify(payload: Any) -> EntryKind:
        uids = ((payload or {}).get("result") or {}).get("uids")
        return EntryKind.META if uids else EntryKind.NEGATIVE

    async def fetch_chunk(chunk: list[str]) -> dict[str, Any]:
        params = {
            "db": "pmc",
            "id": ",".join(c.removeprefix("PMC") for c in chunk),
            "retmode": "json",
            "tool": TOOL,
        }
        if email:
            params["email"] = email
        if api_key:
            params["api_key"] = api_key
        fetched = await client.get_json(ESUMMARY_URL, params=params, classify=classify)
        result = (fetched.data or {}).get("result") or {}
        return {
            f"PMC{uid}": result[uid]
            for uid in result.get("uids") or []
            if isinstance(result.get(uid), dict) and "error" not in result[uid]
        }

    def pmid_of(item: dict[str, Any]) -> str | None:
        for article_id in item.get("articleids") or []:
            value = str(article_id.get("value") or "")
            if article_id.get("idtype") == "pmid" and value.isdigit() and value != "0":
                return value
        return None

    try:
        items = await client.batch(
            "pmc", unique, fetch_chunk, chunk_size=BATCH, kind=EntryKind.META
        )
    except PartialUnavailable as partial:
        raise partial.with_found({k: pmid_of(v) for k, v in partial.found.items()}) from None
    return {pmcid: pmid_of(item) for pmcid, item in items.items()}
