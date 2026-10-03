"""Crossref REST API adapter (docs/spikes/S2-crossref.md).

* Known DOIs are fetched in batches with ``filter=doi:a,doi:b`` (list pool: 1 request/s).
* ``query.bibliographic`` is used only for references without identifiers; its relevance score
  is never treated as a confidence (fake ``posted-content`` duplicates rank first).
* Retraction/correction status comes from ``updated-by`` (currently sourced from Retraction
  Watch) and from a ``RETRACTED:`` title prefix.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from paper_preflight.cache import EntryKind
from paper_preflight.sources.base import PartialUnavailable, SourceClient, SourcePolicy
from paper_preflight.sources.record import Person, SourceRecord, collapse, plain_title

WORKS_URL = "https://api.crossref.org/works"
BATCH = 20
SELECT = ",".join(
    [
        "DOI", "title", "subtitle", "type", "author", "issued", "published-print",
        "published-online", "container-title", "event", "updated-by", "relation", "volume",
        "issue", "page", "publisher", "member", "prefix", "URL",
    ]
)  # fmt: skip

POLICY = SourcePolicy(name="crossref", min_interval=1.0, max_concurrency=1)

UPDATE_STATUS = {
    "retraction": "retracted",
    "removal": "retracted",
    "partial_retraction": "partial_retraction",
    "withdrawal": "withdrawn",
    "expression_of_concern": "expression_of_concern",
    "correction": "correction",
    "corrigendum": "correction",
    "erratum": "correction",
}


def _year(item: dict[str, Any], key: str) -> int | None:
    parts = (item.get(key) or {}).get("date-parts") or [[None]]
    if parts and parts[0] and parts[0][0]:
        return int(parts[0][0])
    return None


def parse_work(item: dict[str, Any]) -> SourceRecord:
    doi = str(item.get("DOI", "")).lower()
    titles = item.get("title") or [""]
    title = plain_title(str(titles[0]))
    subtitles = [plain_title(str(s)) for s in item.get("subtitle") or [] if s]
    alt_titles = tuple(f"{title}: {s}" for s in subtitles)

    authors: list[Person] = []
    for author in item.get("author") or []:
        if "family" in author or "given" in author:
            authors.append(Person.from_parts(author.get("given"), author.get("family")))
        elif author.get("name"):
            name = collapse(str(author["name"]))
            authors.append(Person(family=name, literal=name))

    years = {
        y for y in (_year(item, k) for k in ("issued", "published-print", "published-online")) if y
    }
    venue = None
    containers = item.get("container-title") or []
    if containers:
        venue = collapse(str(containers[0]))
    elif (item.get("event") or {}).get("name"):
        venue = collapse(str(item["event"]["name"]))

    status: set[str] = set()
    status_sources: list[str] = []
    for update in item.get("updated-by") or []:
        flag = UPDATE_STATUS.get(str(update.get("type", "")).lower())
        if flag:
            status.add(flag)
            source = update.get("source", "unknown")
            status_sources.append(f"crossref:{source}:{update.get('DOI', '')}")
    if title.upper().startswith("RETRACTED"):
        status.add("retracted")
        status_sources.append("crossref:title-prefix")

    relations: dict[str, tuple[str, ...]] = {}
    for kind, targets in (item.get("relation") or {}).items():
        ids = tuple(str(t.get("id", "")).lower() for t in targets if t.get("id"))
        if ids:
            relations[kind] = ids

    identifiers = {"doi": doi}
    if item.get("prefix"):
        identifiers["doi_prefix"] = str(item["prefix"])
    if item.get("member"):
        identifiers["crossref_member"] = str(item["member"])

    return SourceRecord(
        source="crossref",
        source_id=doi,
        title=title,
        authors=tuple(authors),
        year=_year(item, "issued") or (min(years) if years else None),
        years=frozenset(years),
        venue=venue,
        work_type=item.get("type"),
        identifiers=identifiers,
        alt_titles=alt_titles,
        status=frozenset(status),
        status_sources=tuple(status_sources),
        relations=relations,
        volume=str(item["volume"]) if item.get("volume") else None,
        issue=str(item["issue"]) if item.get("issue") else None,
        pages=str(item["page"]) if item.get("page") else None,
        publisher=item.get("publisher"),
        url=item.get("URL"),
    )


def parse_work_list(payload: Any) -> list[SourceRecord]:
    message = (payload or {}).get("message") or {}
    return [parse_work(item) for item in message.get("items") or []]


def _params(extra: dict[str, Any], mailto: str | None) -> dict[str, Any]:
    params = dict(extra)
    if mailto:
        params["mailto"] = mailto  # polite pool; stripped from cache keys
    return params


def _classify_list(payload: Any) -> EntryKind:
    items = ((payload or {}).get("message") or {}).get("items") or []
    return EntryKind.SEARCH if items else EntryKind.NEGATIVE


async def works_by_doi(
    client: SourceClient, dois: Iterable[str], *, mailto: str | None = None
) -> dict[str, SourceRecord]:
    """Fetch Crossref records for DOIs (case-insensitive). Missing DOIs are simply absent."""
    unique = list(dict.fromkeys(d.lower() for d in dois))

    async def fetch_chunk(chunk: list[str]) -> dict[str, Any]:
        params = _params(
            {
                "filter": ",".join(f"doi:{d}" for d in chunk),
                "rows": len(chunk),
                "select": SELECT,
            },
            mailto,
        )
        fetched = await client.get_json(WORKS_URL, params=params, classify=_classify_list)
        items = ((fetched.data or {}).get("message") or {}).get("items") or []
        return {str(item.get("DOI", "")).lower(): item for item in items}

    try:
        items = await client.batch("works", unique, fetch_chunk, chunk_size=BATCH)
    except PartialUnavailable as partial:
        raise partial.with_found(_records(partial.found)) from None
    return _records(items)


def _records(items: dict[str, Any]) -> dict[str, SourceRecord]:
    return {doi: parse_work(item) for doi, item in items.items()}


async def search_bibliographic(
    client: SourceClient, query: str, *, rows: int = 10, mailto: str | None = None
) -> list[SourceRecord]:
    """Free-text bibliographic search (title + first authors + year work best)."""
    params = _params({"query.bibliographic": query, "rows": rows, "select": SELECT}, mailto)
    fetched = await client.get_json(WORKS_URL, params=params, classify=_classify_list)
    return parse_work_list(fetched.data)
