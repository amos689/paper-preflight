"""Semantic Scholar Graph API adapter: an optional rescue source (docs/spikes/S5).

* Used only with an API key (``S2_API_KEY``), sent as the ``x-api-key`` header: it is never part
  of a cache key, a log line or a report. Anonymous access failed 35% of the time in spike S5.
* The licence forbids redistributing responses, so cached answers are marked non-exportable and
  the tests use synthetic data, never recorded responses.
* S2's ``year`` follows the earliest version of a paper (ResNet comes back as 2015) and its
  ``publicationTypes`` are unreliable, so records carry neither: an S2 record can confirm that a
  work exists and who wrote it, never that a year or a type is wrong.
* A 404 ("Title match not found") is a definite "not in S2"; S2 is still never *required* for
  a "not found" verdict.
"""

from __future__ import annotations

from typing import Any

from paper_preflight.cache import EntryKind
from paper_preflight.sources.base import SourceClient, SourcePolicy
from paper_preflight.sources.record import Person, SourceRecord, collapse

API = "https://api.semanticscholar.org/graph/v1"
FIELDS = "title,authors,venue,externalIds,publicationVenue"

# S2's terms for API keys: "1 request per second, cumulative across all endpoints ... set your
# rate limit to below this threshold". One connection and >= 1.1 s between request starts
# (plus up to 10% jitter) keeps a run at about 0.85 requests/s; retries are paced the same way.
# Two runs at the same time share the key and could exceed it together. S2's 429 carries no
# Retry-After, so the client backs off on its own.
POLICY = SourcePolicy(
    name="s2",
    min_interval=1.1,
    max_concurrency=1,
    timeout=15.0,
    rate_limit_retries=3,
    backoff=2.0,
    exportable=False,
)


def parse_paper(data: dict[str, Any]) -> SourceRecord | None:
    paper_id = data.get("paperId")
    title = collapse(str(data.get("title") or ""))
    if not paper_id or not title:
        return None
    external = data.get("externalIds") or {}
    identifiers = {"s2": str(paper_id)}
    doi = str(external.get("DOI") or "").lower()
    if doi.startswith("10.48550/arxiv."):
        identifiers["arxiv_doi"] = doi  # the arXiv DataCite DOI is not a venue DOI (spike S5)
    elif doi:
        identifiers["doi"] = doi
    for name, key in (("ArXiv", "arxiv"), ("DBLP", "dblp"), ("PubMed", "pmid"), ("ACL", "acl")):
        if external.get(name):
            identifiers[key] = str(external[name])
    venue = (data.get("publicationVenue") or {}).get("name") or data.get("venue") or None
    authors = tuple(
        Person.from_display(collapse(str(author["name"])))
        for author in data.get("authors") or []
        if author.get("name")
    )
    return SourceRecord(
        source="s2",
        source_id=str(paper_id),
        title=title,
        authors=authors,
        venue=collapse(str(venue)) if venue else None,
        identifiers=identifiers,
    )


def _classify(payload: Any) -> EntryKind:
    return EntryKind.SEARCH if (payload or {}).get("data") else EntryKind.NEGATIVE


async def search_match(client: SourceClient, title: str, api_key: str) -> SourceRecord | None:
    """S2's single best title match, or None when S2 has no such title (HTTP 404)."""
    fetched = await client.get_json(
        f"{API}/paper/search/match",
        params={"query": title, "fields": FIELDS},
        headers={"x-api-key": api_key},
        classify=_classify,
    )
    for item in (fetched.data or {}).get("data") or []:
        record = parse_paper(item)
        if record is not None:
            return record
    return None
