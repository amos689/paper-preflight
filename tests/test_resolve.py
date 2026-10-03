from pathlib import Path

import httpx
import pytest

from paper_preflight.bib.parse import parse_bib_file, parse_bib_text
from paper_preflight.cache import Cache
from paper_preflight.resolve import Evidence, Sources, resolve
from paper_preflight.sources import base
from paper_preflight.sources.base import SourcePolicy

from .fake_web import FakeWeb

DEMO = Path(__file__).parent.parent / "examples" / "demo-paper" / "refs.bib"
KEYS = [
    "he2016deep", "devlin2019bert", "wakefield1998ileal", "tacl2019example", "he2015residual",
    "hendrycks2016gelu", "lindqvist2024quantum", "goodfellow2016deep",
]  # fmt: skip


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture(autouse=True)
def fast(monkeypatch: pytest.MonkeyPatch) -> None:
    async def instant(_: float) -> None:
        return None

    monkeypatch.setattr(base.asyncio, "sleep", instant)
    original_init = base.SourceClient.__init__

    def init(
        self: base.SourceClient, policy: SourcePolicy, *args: object, **kwargs: object
    ) -> None:
        policy.min_interval = 0.0
        original_init(self, policy, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(base.SourceClient, "__init__", init)


async def run(web: FakeWeb) -> dict[str, Evidence]:
    entries = [e for e in parse_bib_file(DEMO).entries if e.key in KEYS]
    async with httpx.AsyncClient(transport=httpx.MockTransport(web)) as http:
        sources = Sources.create(http, Cache(None), environ={})
        return await resolve(entries, sources)


@pytest.fixture
async def evidence() -> dict[str, Evidence]:
    return await run(FakeWeb())


def sources_of(item: Evidence) -> set[str]:
    return {r.source for r in item.anchored}


@pytest.mark.anyio
async def test_doi_anchored_entries(evidence: dict[str, Evidence]) -> None:
    resnet = evidence["he2016deep"]
    assert sources_of(resnet) == {"crossref"}
    assert resnet.anchored[0].doi == "10.1109/cvpr.2016.90"
    assert resnet.doi_agency["10.1109/cvpr.2016.90"].agency == "Crossref"
    assert not resnet.candidates  # anchored entries are not searched by title
    # the wrong DOI on the BERT entry anchors it to the ResNet record: the verdict layer sees it
    assert evidence["devlin2019bert"].anchored[0].doi == "10.1109/cvpr.2016.90"
    # the escaped DOI was unescaped during extraction, so it resolves
    assert evidence["tacl2019example"].anchored[0].doi == "10.1162/tacl_a_00276"


@pytest.mark.anyio
async def test_retraction_evidence_from_two_sources(evidence: dict[str, Evidence]) -> None:
    wakefield = evidence["wakefield1998ileal"]
    assert "retracted" in wakefield.anchored[0].status
    assert any("retracted" in r.status for r in wakefield.status_records)


@pytest.mark.anyio
async def test_arxiv_entries_and_published_versions(evidence: dict[str, Evidence]) -> None:
    preprint = evidence["he2015residual"]
    assert sources_of(preprint) == {"arxiv"}
    assert [r.source_id for r in preprint.published_versions] == ["conf/cvpr/HeZRS16"]
    gelu = evidence["hendrycks2016gelu"]
    assert sources_of(gelu) == {"arxiv"}
    assert gelu.published_versions == []


@pytest.mark.anyio
async def test_unanchored_entries_are_searched(evidence: dict[str, Evidence]) -> None:
    fabricated = evidence["lindqvist2024quantum"]
    assert fabricated.anchored == []
    assert fabricated.searched == {"dblp", "crossref"}
    assert fabricated.negative == {"dblp", "crossref"}
    assert fabricated.candidates == []
    assert fabricated.unavailable == {}
    book = evidence["goodfellow2016deep"]
    # "Deep Learning" is too short to search for meaningfully: no search, no negative answer
    assert book.searched == set()
    assert book.negative == set()


@pytest.mark.anyio
async def test_bot_wall_is_recorded_as_unavailable_not_negative() -> None:
    web = FakeWeb()
    web.fail("sparql.dblp.org", "html")
    evidence = await run(web)
    fabricated = evidence["lindqvist2024quantum"]
    assert fabricated.unavailable == {"dblp": "challenge"}
    assert "dblp" not in fabricated.negative
    assert fabricated.negative == {"crossref"}


@pytest.mark.anyio
async def test_first_definition_of_a_duplicate_key_wins_across_files() -> None:
    # \bibliography{a,b}: BibTeX keeps the definition from a.bib and ignores the one in b.bib
    first = parse_bib_text("@article{k, title = {The First Title}, year = 2020}", Path("a.bib"))
    second = parse_bib_text("@misc{k, title = {The Second Title}, year = 2021}", Path("b.bib"))
    async with httpx.AsyncClient(transport=httpx.MockTransport(FakeWeb())) as http:
        evidence = await resolve(
            first.entries + second.entries, Sources.create(http, Cache(None), environ={})
        )
    assert evidence["k"].info.title == "The First Title"
    assert evidence["k"].info.year == 2020


@pytest.mark.anyio
async def test_rate_limited_doi_routing_falls_back_to_crossref() -> None:
    web = FakeWeb()
    web.fail("doi.org/doiRA", "429")
    evidence = await run(web)
    resnet = evidence["he2016deep"]
    assert resnet.unavailable == {"doiorg": "rate_limited"}
    assert resnet.anchored[0].doi == "10.1109/cvpr.2016.90"  # Crossref was asked directly
