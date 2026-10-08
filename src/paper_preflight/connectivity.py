"""`doctor` connectivity probes: one cheap, uncached request per source.

Each probe goes through the same client as a real check, so a bot wall, a rate limit or a
timeout is reported exactly as `check` would see it. Nothing is cached and no credential is
ever printed; Semantic Scholar is probed only when a key is set, because it is never used
without one.
"""

from __future__ import annotations

import asyncio
import os
import time
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, replace
from typing import Any

import httpx

from paper_preflight import check
from paper_preflight.cache import Cache
from paper_preflight.sources import (
    arxiv,
    crossref,
    datacite,
    dblp,
    doiorg,
    openalex,
    openlibrary,
    pubmed,
    semanticscholar,
    software,
    web,
)
from paper_preflight.sources.base import SourceClient, SourcePolicy, SourceUnavailable

KNOWN_DOI = "10.1109/cvpr.2016.90"  # ResNet, CVPR 2016: registered with Crossref
KNOWN_ARXIV = "1706.03762"  # Attention Is All You Need
KNOWN_PMID = "9500320"  # Wakefield et al., Lancet 1998


@dataclass(frozen=True)
class Probe:
    source: str
    status: str  # "ok" | "unavailable" | "skipped"
    detail: str = ""
    seconds: float | None = None


Call = Callable[[SourceClient], Awaitable[Any]]


def _calls(env: Mapping[str, str]) -> list[tuple[SourcePolicy, Call | None, str]]:
    mailto = env.get("PAPER_PREFLIGHT_EMAIL") or None
    openalex_key = env.get("OPENALEX_API_KEY") or None
    s2_key = env.get("S2_API_KEY") or None
    github_token = env.get("GITHUB_TOKEN") or None
    ncbi_key = env.get("NCBI_API_KEY") or None
    s2_call: Call | None = None
    if s2_key:
        key = s2_key

        def s2_call(c: SourceClient) -> Awaitable[Any]:
            return semanticscholar.search_match(c, "Attention Is All You Need", key)

    return [
        (doiorg.POLICY, lambda c: doiorg.registration_agencies(c, [KNOWN_DOI]), ""),
        (
            crossref.POLICY,
            lambda c: crossref.works_by_doi(c, [KNOWN_DOI], mailto=mailto),
            "polite pool requested (email set)" if mailto else "public pool (no email set)",
        ),
        (datacite.POLICY, lambda c: datacite.dois(c, [f"10.48550/arxiv.{KNOWN_ARXIV}"]), ""),
        (arxiv.POLICY, lambda c: arxiv.by_ids(c, [KNOWN_ARXIV]), ""),
        (dblp.POLICY, lambda c: dblp.by_dois(c, [KNOWN_DOI]), ""),
        (
            openalex.POLICY,
            lambda c: openalex.work_by_doi(c, KNOWN_DOI, api_key=openalex_key),
            "with API key" if openalex_key else "without API key",
        ),
        (
            pubmed.KEYED_POLICY if ncbi_key else pubmed.POLICY,
            lambda c: pubmed.by_pmids(c, [KNOWN_PMID], email=mailto, api_key=ncbi_key),
            "with API key" if ncbi_key else "without API key (3 requests a second)",
        ),
        (semanticscholar.POLICY, s2_call, "" if s2_key else "S2_API_KEY not set"),
        (
            openlibrary.POLICY,
            lambda c: openlibrary.search_books(c, "Matrix Computations", "Golub", mailto=mailto),
            "books without a DOI",
        ),
        (
            software.GITHUB_POLICY,
            lambda c: software.github_repo(c, "python/cpython", token=github_token),
            "with token" if github_token else "without token (60 requests an hour)",
        ),
        (software.PYPI_POLICY, lambda c: software.pypi_package(c, "numpy"), ""),
        (software.CRAN_POLICY, lambda c: software.cran_package(c, "ggplot2"), ""),
        (web.WAYBACK_POLICY, lambda c: web.archived(c, "https://arxiv.org/"), ""),
    ]


async def _probe(
    http: httpx.AsyncClient, policy: SourcePolicy, call: Call | None, note: str
) -> Probe:
    if call is None:
        return Probe(policy.name, "skipped", note)
    # one attempt, no pacing and no retries: this is a reachability check, not a lookup
    client = SourceClient(
        replace(policy, min_interval=0.0, retries=0, rate_limit_retries=0), http, Cache(None)
    )
    started = time.monotonic()
    try:
        await call(client)
    except SourceUnavailable as error:
        detail = error.reason.value + (f" ({error.detail})" if error.detail else "")
        return Probe(policy.name, "unavailable", detail, time.monotonic() - started)
    return Probe(policy.name, "ok", note, time.monotonic() - started)


async def probe_sources(environ: Mapping[str, str] | None = None) -> list[Probe]:
    env = environ if environ is not None else os.environ
    async with httpx.AsyncClient(transport=check.make_transport(), follow_redirects=True) as http:
        return list(
            await asyncio.gather(
                *(_probe(http, policy, call, note) for policy, call, note in _calls(env))
            )
        )
