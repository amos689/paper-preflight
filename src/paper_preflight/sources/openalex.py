"""OpenAlex adapter — a secondary source (docs/spikes/S3-openalex.md).

OpenAlex records can be polluted (wrong DOI/year/title after merges), so they never anchor a
reference on their own. Their best uses: the free ``/works/doi:<doi>`` singleton for the
``is_retracted`` cross-check, and cheap OR-batch existence checks. Title search costs 10x more and
is only used with an API key (``OPENALEX_API_KEY``) or while the daily budget allows.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any
from urllib.parse import quote

from paper_preflight.cache import EntryKind
from paper_preflight.sources.base import SourceClient, SourcePolicy
from paper_preflight.sources.record import Person, SourceRecord, collapse

WORKS_URL = "https://api.openalex.org/works"
SELECT = "id,doi,title,publication_year,type,is_retracted,authorships,primary_location,ids"
BATCH = 50

POLICY = SourcePolicy(name="openalex", min_interval=1.0)


def _strip_doi(value: str | None) -> str | None:
    if not value:
        return None
    return value.lower().removeprefix("https://doi.org/")


def parse_work(item: dict[str, Any]) -> SourceRecord:
    work_id = str(item.get("id", "")).removeprefix("https://openalex.org/")
    authors: list[Person] = []
    for authorship in item.get("authorships") or []:
        # raw_author_name is what the publisher deposited; display_name is disambiguation output
        name = authorship.get("raw_author_name") or (authorship.get("author") or {}).get(
            "display_name"
        )
        if name:
            authors.append(Person.from_display(str(name)))
    year = item.get("publication_year")
    source = ((item.get("primary_location") or {}).get("source") or {}).get("display_name")
    identifiers = {"openalex": work_id}
    doi = _strip_doi(item.get("doi"))
    if doi:
        identifiers["doi"] = doi
    ids = item.get("ids") or {}
    if ids.get("pmid"):
        identifiers["pmid"] = str(ids["pmid"]).rsplit("/", 1)[-1]
    title = collapse(str(item.get("title") or item.get("display_name") or ""))
    status: set[str] = set()
    sources: list[str] = []
    if item.get("is_retracted"):
        status.add("retracted")
        sources.append("openalex:is_retracted")
    return SourceRecord(
        source="openalex",
        source_id=work_id,
        title=title,
        authors=tuple(authors),
        authors_complete=not item.get("is_authors_truncated", False),
        year=int(year) if year else None,
        years=frozenset({int(year)} if year else set()),
        venue=collapse(str(source)) if source else None,
        work_type=item.get("type"),
        identifiers=identifiers,
        status=frozenset(status),
        status_sources=tuple(sources),
        url=f"https://openalex.org/{work_id}",
    )


def _params(api_key: str | None, extra: dict[str, Any]) -> dict[str, Any]:
    params = dict(extra)
    if api_key:
        params["api_key"] = api_key  # stripped from cache keys
    return params


async def work_by_doi(
    client: SourceClient, doi: str, *, api_key: str | None = None
) -> SourceRecord | None:
    """Free singleton lookup (use the ``doi:`` form; the URL form is billed)."""
    fetched = await client.get_json(
        f"{WORKS_URL}/doi:{quote(doi.lower(), safe='/')}",
        params=_params(api_key, {"select": SELECT}),
    )
    return parse_work(fetched.data) if isinstance(fetched.data, dict) else None


async def works_by_doi(
    client: SourceClient, dois: Iterable[str], *, api_key: str | None = None
) -> dict[str, SourceRecord]:
    unique = list(dict.fromkeys(d.lower() for d in dois))
    found: dict[str, SourceRecord] = {}

    def classify(payload: Any) -> EntryKind:
        return EntryKind.SEARCH if (payload or {}).get("results") else EntryKind.NEGATIVE

    for start in range(0, len(unique), BATCH):
        chunk = unique[start : start + BATCH]
        params = _params(
            api_key,
            {"filter": "doi:" + "|".join(chunk), "select": SELECT, "per_page": len(chunk)},
        )
        fetched = await client.get_json(WORKS_URL, params=params, classify=classify)
        for item in (fetched.data or {}).get("results") or []:
            record = parse_work(item)
            if record.doi:
                found[record.doi] = record
    return found
