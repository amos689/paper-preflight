"""`bib fetch`: verified BibTeX for an identifier or a title, never written from memory.

The query becomes a one-entry bibliography and goes through the same resolver and verdict engine
as `check`, so every guard applies: an identifier must resolve at its registration agency, and a
title must bind to exactly one work (ambiguous matches are listed, not chosen).

A cited preprint that has been published is returned as the published version with its
``eprint`` kept, as REF015 recommends; ``prefer_published=False`` returns the preprint itself.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, replace
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx

from paper_preflight import check
from paper_preflight.bib.ids import normalize_doi
from paper_preflight.bib.parse import parse_bib_text
from paper_preflight.bibtex import render
from paper_preflight.cache import Cache
from paper_preflight.match import title_score
from paper_preflight.resolve import Evidence, Sources, resolve
from paper_preflight.sources.record import SourceRecord
from paper_preflight.verdict import SOURCE_PRIORITY, assess, is_preprint

_ARXIV_RE = re.compile(
    r"^(?:arxiv:|https?://arxiv\.org/(?:abs|pdf)/)?"
    r"(\d{4}\.\d{4,5}|[a-z][a-z-]+(?:\.[A-Z]{2})?/\d{7})(v\d+)?(?:\.pdf)?$",
    re.IGNORECASE,
)


@dataclass
class FetchResult:
    status: str  # "found" | "not_found" | "ambiguous" | "unavailable" | "invalid"
    record: SourceRecord | None = None
    preprint: SourceRecord | None = None  # set when a published version replaces it
    candidates: list[SourceRecord] = field(default_factory=list)
    unavailable: dict[str, str] = field(default_factory=dict)
    detail: str = ""


def _clean(text: str) -> str:
    return " ".join(text.replace("{", "").replace("}", "").split())


def identifier_query(identifier: str) -> str | None:
    """A one-entry bibliography for a DOI or arXiv ID (URLs and prefixes accepted)."""
    text = identifier.strip()
    arxiv = _ARXIV_RE.match(text)
    if arxiv:
        return f"@misc{{query, eprint = {{{arxiv.group(1)}}}, archivePrefix = {{arXiv}}}}"
    doi = normalize_doi(text)
    if doi is not None:
        return f"@misc{{query, doi = {{{doi}}}}}"
    return None


def title_query(title: str, author: str | None = None, year: int | None = None) -> str:
    fields = [f"title = {{{_clean(title)}}}"]
    if author:
        fields.append(f"author = {{{_clean(author)}}}")
    if year:
        fields.append(f"year = {{{year}}}")
    # @article is not grey literature, so dblp and Crossref are both searched
    return "@article{query, " + ", ".join(fields) + "}"


def _published(evidence: Evidence, preprint: SourceRecord) -> SourceRecord | None:
    for version in evidence.published_versions:
        same = title_score(preprint.title, version.title) >= 0.9
        if same or preprint.title in version.alt_titles:
            arxiv_id = preprint.identifiers.get("arxiv", "")
            return replace(version, identifiers={**version.identifiers, "arxiv": arxiv_id})
    return None


async def fetch(query: str, sources: Sources, *, prefer_published: bool = True) -> FetchResult:
    (entry,) = parse_bib_text(query, Path("query.bib")).entries
    evidence = (await resolve([entry], sources))["query"]
    unavailable = dict(evidence.unavailable)
    by_identifier = bool(evidence.identifiers)

    if by_identifier:
        dead = [a for a in evidence.doi_agency.values() if not a.exists]
        if dead or evidence.arxiv_missing:
            return FetchResult("not_found", detail="the identifier does not exist")
        records = evidence.anchored
        if not records:
            status = "unavailable" if unavailable else "not_found"
            return FetchResult(status, unavailable=unavailable)
        best = min(records, key=lambda r: (is_preprint(r), SOURCE_PRIORITY.get(r.source, 9)))
    else:
        result = assess(entry, evidence, current_year=datetime.now().year)
        if result.record is None:
            if evidence.candidates:
                distinct: dict[str, SourceRecord] = {}
                for candidate in evidence.candidates:
                    distinct.setdefault(candidate.title.lower(), candidate)
                return FetchResult("ambiguous", candidates=list(distinct.values())[:5])
            status = "unavailable" if unavailable else "not_found"
            return FetchResult(status, unavailable=unavailable)
        best = result.record

    if prefer_published and is_preprint(best):
        published = _published(evidence, best)
        if published is not None:
            return FetchResult("found", record=published, preprint=best, unavailable=unavailable)
    return FetchResult("found", record=best, unavailable=unavailable)


async def lookup(
    query: str, *, cache_path: Path | None, offline: bool = False, prefer_published: bool = True
) -> FetchResult:
    """`fetch` with its own HTTP client and cache, as the CLI and the MCP server use it."""
    cache = Cache(cache_path)
    try:
        transport = check.make_transport()
        async with httpx.AsyncClient(transport=transport, follow_redirects=True) as http:
            sources = Sources.create(http, cache, offline=offline)
            return await fetch(query, sources, prefer_published=prefer_published)
    finally:
        cache.close()


def to_dict(result: FetchResult, key: str | None = None) -> dict[str, Any]:
    """The result as plain data: the BibTeX, where it came from, or why there is none."""
    record = result.record
    return {
        "status": result.status,
        "bibtex": render(record, key=key) if record is not None else None,
        "source": record.source if record else None,
        "source_id": record.source_id if record else None,
        "published_version_of": result.preprint.source_id if result.preprint else None,
        "status_flags": sorted(record.status) if record else [],
        "candidates": [
            {"title": c.title, "year": c.year, "source": c.source, "id": c.source_id}
            for c in result.candidates
        ],
        "unavailable": result.unavailable,
        "detail": result.detail,
    }
