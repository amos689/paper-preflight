"""doi.org: registration-agency routing (doiRA), handle existence checks, content negotiation.

One ``doiRA`` call answers, in input order, which registration agency (Crossref, DataCite,
mEDRA, JaLC, KISTI, CNKI, ISTIC, ...) owns each DOI, or that the DOI does not exist
(docs/spikes/S4-arxiv-datacite-doiorg.md). That single call decides how every DOI is verified.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

from paper_preflight.cache import EntryKind
from paper_preflight.sources.base import (
    PartialUnavailable,
    SourceClient,
    SourcePolicy,
    SourceUnavailable,
)
from paper_preflight.sources.record import Person, SourceRecord, collapse, plain_title

DOIRA_URL = "https://doi.org/doiRA/"
HANDLE_URL = "https://doi.org/api/handles/"
DOI_URL = "https://doi.org/"
CHUNK = 25  # keeps request URLs well under common length limits

POLICY = SourcePolicy(name="doiorg", min_interval=1.0)

DOES_NOT_EXIST = "DOES_NOT_EXIST"


@dataclass(frozen=True)
class AgencyAnswer:
    doi: str
    agency: str | None  # "Crossref", "DataCite", ... or None when the DOI does not exist
    exists: bool


def parse_doira(payload: Any) -> list[AgencyAnswer]:
    answers: list[AgencyAnswer] = []
    for item in payload or []:
        doi = str(item.get("DOI", ""))
        agency = item.get("RA")
        if agency:
            answers.append(AgencyAnswer(doi, str(agency), True))
        elif "does not exist" in str(item.get("status", "")).lower():
            answers.append(AgencyAnswer(doi, None, False))
    return answers


async def registration_agencies(
    client: SourceClient, dois: Iterable[str]
) -> dict[str, AgencyAnswer]:
    """Map each (lower-cased) DOI to its registration agency answer."""
    unique = list(dict.fromkeys(d.lower() for d in dois))

    def classify(_: Any) -> EntryKind:
        return EntryKind.META

    async def fetch_chunk(chunk: list[str]) -> dict[str, Any]:
        path = ",".join(quote(d, safe="/") for d in chunk)
        fetched = await client.get_json(DOIRA_URL + path, classify=classify)
        return {str(item.get("DOI", "")).lower(): item for item in fetched.data or []}

    try:
        items = await client.batch("doira", unique, fetch_chunk, chunk_size=CHUNK,
                                   kind=EntryKind.META)  # fmt: skip
    except PartialUnavailable as partial:
        raise partial.with_found(await _answers(client, partial.found)) from None
    return await _answers(client, items)


async def _answers(client: SourceClient, items: dict[str, Any]) -> dict[str, AgencyAnswer]:
    payload = list(items.values())
    result = {answer.doi.lower(): answer for answer in parse_doira(payload)}
    # doiRA answers a bare "Error" for DOIs whose prefix is not registered at all (a made-up
    # 10.77771/... in HALLMARK). That word alone proves nothing, so the Handle API decides.
    for doi in unclear_dois(payload):
        try:
            exists = await handle_exists(client, doi)
        except SourceUnavailable:
            continue  # stays unknown: an unanswered check is not a negative
        if exists is False:
            result[doi] = AgencyAnswer(doi, None, False)
    return result


def unclear_dois(payload: Any) -> list[str]:
    """DOIs for which doiRA gave neither an agency nor "DOI does not exist"."""
    unclear: list[str] = []
    for item in payload or []:
        status = str(item.get("status", "")).lower()
        if not item.get("RA") and status and "does not exist" not in status:
            unclear.append(str(item.get("DOI", "")).lower())
    return unclear


async def handle_exists(client: SourceClient, doi: str) -> bool | None:
    """Ask the Handle API whether a DOI exists; None when the answer is unclear.

    404 means the handle does not exist; 400 with "That prefix doesn't live here" (responseCode
    301) means the prefix is not registered with the DOI system, so no DOI under it exists.
    """
    fetched = await client.get_json(
        HANDLE_URL + quote(doi, safe="/"), params={"type": "URL"}, negative_statuses=(404, 400)
    )
    if fetched.data is None:
        return False
    code = fetched.data.get("responseCode") if isinstance(fetched.data, dict) else None
    return True if code == 1 else (False if code == 100 else None)


def parse_csl(doi: str, csl: dict[str, Any], agency: str) -> SourceRecord:
    """Normalise a CSL-JSON record from doi.org content negotiation."""
    title = csl.get("title") or ""
    if isinstance(title, list):
        title = title[0] if title else ""
    authors = tuple(
        Person(literal=collapse(a["literal"]), family=collapse(a["literal"]))
        if "literal" in a
        else Person.from_parts(a.get("given"), a.get("family"))
        for a in csl.get("author", [])
    )
    year = None
    for key in ("issued", "published-print", "published-online", "created"):
        parts = (csl.get(key) or {}).get("date-parts") or [[None]]
        if parts and parts[0] and parts[0][0]:
            year = int(parts[0][0])
            break
    container = csl.get("container-title") or None
    if isinstance(container, list):
        container = container[0] if container else None
    return SourceRecord(
        source=f"doiorg:{agency.lower()}",
        source_id=doi.lower(),
        title=plain_title(str(title)),
        authors=authors,
        year=year,
        years=frozenset({year} if year else set()),
        venue=container,
        work_type=csl.get("type"),
        identifiers={"doi": doi.lower()},
        volume=str(csl["volume"]) if csl.get("volume") else None,
        issue=str(csl["issue"]) if csl.get("issue") else None,
        pages=str(csl["page"]) if csl.get("page") else None,
        publisher=csl.get("publisher"),
        url=DOI_URL + doi,
    )


async def csl_record(client: SourceClient, doi: str, agency: str) -> SourceRecord | None:
    """Content negotiation fallback for agencies without a dedicated adapter."""
    fetched = await client.get_json(
        DOI_URL + quote(doi, safe="/"),
        headers={"Accept": "application/vnd.citationstyles.csl+json"},
    )
    if not isinstance(fetched.data, dict):
        return None
    return parse_csl(doi, fetched.data, agency)
