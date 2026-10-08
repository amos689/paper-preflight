"""Semantic Scholar as an optional rescue source.

All S2 data in these tests is SYNTHETIC: the S2 API licence forbids storing real responses.
"""

import sqlite3
from pathlib import Path
from typing import Any

import httpx
import pytest

from paper_preflight.bib.parse import parse_bib_file, parse_bib_text
from paper_preflight.cache import Cache
from paper_preflight.resolve import Evidence, Sources, resolve
from paper_preflight.sources.semanticscholar import POLICY, parse_paper
from paper_preflight.verdict import Assessment, Verdict, assess_all, run_findings

from .fake_web import FakeWeb

DEMO = Path(__file__).parent.parent / "examples" / "demo-paper" / "refs.bib"
KEYS = {"lindqvist2024quantum", "goodfellow2016deep", "he2016deep"}
FABRICATED = "Quantum Gradient Folding for Sparse Mixture-of-Experts Transformers"
KEY = "synthetic-test-key"

pytestmark = pytest.mark.usefixtures("fast")


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def synthetic_paper(**external: str) -> dict[str, Any]:
    return {
        "paperId": "0000synthetic",
        "title": FABRICATED,
        "venue": "NeurIPS",
        "publicationVenue": {"name": "Neural Information Processing Systems"},
        "externalIds": external,
        "authors": [{"name": "Aurelio Lindqvist"}, {"name": "Tamsin Okonkwo-Reyes"}],
    }


async def run(
    web: FakeWeb, environ: dict[str, str], cache: Cache | None = None
) -> tuple[dict[str, Evidence], dict[str, Assessment]]:
    entries = [e for e in parse_bib_file(DEMO).entries if e.key in KEYS]
    async with httpx.AsyncClient(transport=httpx.MockTransport(web)) as http:
        sources = Sources.create(http, cache or Cache(None), environ=environ)
        evidence = await resolve(entries, sources)
    return evidence, assess_all(entries, evidence, current_year=2026)


def s2_requests(web: FakeWeb) -> list[httpx.Request]:
    return [r for r in web.requests if r.url.host == "api.semanticscholar.org"]


def test_policy_stays_below_the_keyed_rate_limit() -> None:
    # S2's terms for API keys: 1 request per second across all endpoints; stay below it.
    assert POLICY.max_concurrency == 1
    assert POLICY.min_interval > 1.0
    assert POLICY.exportable is False  # the licence forbids redistributing responses


def test_parse_paper() -> None:
    record = parse_paper(
        synthetic_paper(DOI="10.48550/arXiv.2401.00001", ArXiv="2401.00001", DBLP="conf/x/L24")
    )
    assert record is not None
    assert record.identifiers == {
        "s2": "0000synthetic", "arxiv_doi": "10.48550/arxiv.2401.00001",
        "arxiv": "2401.00001", "dblp": "conf/x/L24",
    }  # fmt: skip
    assert record.doi is None  # an arXiv DataCite DOI is not a venue DOI
    assert record.all_years == frozenset()  # S2's year follows the earliest version: unused
    assert [p.family for p in record.authors] == ["Lindqvist", "Okonkwo-Reyes"]
    assert record.venue == "Neural Information Processing Systems"
    assert parse_paper({"paperId": "x", "title": ""}) is None


@pytest.mark.anyio
async def test_without_a_key_s2_is_never_asked() -> None:
    web = FakeWeb()
    await run(web, environ={})
    assert s2_requests(web) == []


@pytest.mark.anyio
async def test_s2_answering_no_is_named_in_not_found() -> None:
    web = FakeWeb()
    evidence, verdicts = await run(web, environ={"S2_API_KEY": KEY})
    (request,) = s2_requests(web)  # only the entry nobody else found; short titles are skipped
    assert request.headers["x-api-key"] == KEY
    assert KEY not in str(request.url)
    assert {"s2", "dblp", "crossref"} <= evidence["lindqvist2024quantum"].negative
    fabricated = verdicts["lindqvist2024quantum"]
    assert fabricated.verdict is Verdict.NOT_FOUND
    (finding,) = fabricated.findings
    assert "Crossref, dblp and Semantic Scholar" in finding.message.en
    assert "Crossref、dblp 和 Semantic Scholar" in finding.message.zh


@pytest.mark.anyio
async def test_s2_rescues_a_work_the_other_sources_missed() -> None:
    web = FakeWeb()
    web.s2_papers[FABRICATED.lower()] = synthetic_paper()
    _, verdicts = await run(web, environ={"S2_API_KEY": KEY})
    rescued = verdicts["lindqvist2024quantum"]
    assert rescued.verdict is Verdict.VERIFIED  # title and authors agree; S2 has no year to check
    assert rescued.record is not None
    assert rescued.record.source == "s2"


VISION = (
    "Vision: A Computational Investigation into the Human Representation and Processing of "
    "Visual Information"
)
BOOKS = f"""
@book{{marr1982vision,
  title = {{{VISION}}},
  author = {{Marr, David}},
  year = {{1982}},
  publisher = {{W. H. Freeman}},
}}
@article{{guest2006many,
  title = {{How many interviews are enough? An experiment with data saturation and variability}},
  author = {{Guest, Greg and Bunce, Arwen and Johnson, Laura}},
  journal = {{Field Methods}},
  volume = {{18}},
  pages = {{59--82}},
  year = {{2006}},
}}
"""
# Crossref keeps a subtitle apart from the title (both records as Crossref has them)
MIT_PRESS_VISION = {
    "DOI": "10.7551/mitpress/9780262514620.001.0001", "type": "monograph", "title": ["Vision"],
    "subtitle": [VISION.partition(": ")[2]], "author": [{"given": "David", "family": "Marr"}],
    "issued": {"date-parts": [[2010, 7, 9]]}, "publisher": "The MIT Press",
}  # fmt: skip
FIELD_METHODS = {
    "DOI": "10.1177/1525822x05279903", "type": "journal-article",
    "title": ["How Many Interviews Are Enough?"],
    "subtitle": ["An Experiment with Data Saturation and Variability"],
    "author": [{"given": "Greg", "family": "Guest"}, {"given": "Arwen", "family": "Bunce"},
               {"given": "Laura", "family": "Johnson"}],
    "issued": {"date-parts": [[2006, 2]]}, "container-title": ["Field Methods"],
    "volume": "18", "page": "59-82",
}  # fmt: skip


@pytest.mark.anyio
async def test_a_record_found_by_its_subtitle_does_not_stop_the_rescue() -> None:
    web = FakeWeb()
    web.crossref_search = {"Vision": [MIT_PRESS_VISION], "interviews": [FIELD_METHODS]}
    web.s2_papers[VISION.lower()] = {  # SYNTHETIC
        "paperId": "0000synthetic", "title": VISION, "authors": [{"name": "David Marr"}],
    }  # fmt: skip
    entries = parse_bib_text(BOOKS, Path("refs.bib")).entries
    async with httpx.AsyncClient(transport=httpx.MockTransport(web)) as http:
        sources = Sources.create(http, Cache(None), environ={"S2_API_KEY": KEY})
        evidence = await resolve(entries, sources)
    verdicts = assess_all(entries, evidence, current_year=2026)
    # Crossref's record of the article is its title and subtitle as the entry cites them
    guest = verdicts["guest2006many"]
    assert guest.verdict is Verdict.VERIFIED
    assert guest.record is not None
    assert guest.record.doi == "10.1177/1525822x05279903"
    # MIT Press's 2010 edition does not hide Marr's 1982 book from Semantic Scholar
    assert evidence["marr1982vision"].by_subtitle
    marr = verdicts["marr1982vision"]
    assert marr.verdict is Verdict.VERIFIED
    assert marr.record is not None
    assert marr.record.source == "s2"


@pytest.mark.anyio
async def test_s2_outage_never_blocks_a_verdict() -> None:
    web = FakeWeb()
    web.fail("api.semanticscholar.org", "429")
    evidence, verdicts = await run(web, environ={"S2_API_KEY": KEY})
    item = evidence["lindqvist2024quantum"]
    assert item.optional_unavailable == {"s2": "rate_limited"}
    assert item.unavailable == {}
    assert len(s2_requests(web)) == 1 + POLICY.rate_limit_retries  # backed off, then gave up
    assert verdicts["lindqvist2024quantum"].verdict is Verdict.NOT_FOUND
    assert run_findings(evidence) == []  # an optional source does not make the run incomplete


@pytest.mark.anyio
async def test_s2_answers_are_cached_locally_but_never_exported(tmp_path: Path) -> None:
    cache = Cache(tmp_path / "cache.sqlite3")
    try:
        await run(FakeWeb(), environ={"S2_API_KEY": KEY}, cache=cache)
        stored = cache.stats()
        exported = cache.export()
    finally:
        cache.close()
    assert "s2" in stored
    assert all(item["source"] != "s2" for item in exported)
    with sqlite3.connect(tmp_path / "cache.sqlite3") as db:
        s2_rows = db.execute("SELECT key, payload FROM entries WHERE source = 's2'").fetchall()
    assert s2_rows
    assert all(KEY not in key and KEY not in payload for key, payload in s2_rows)
