from pathlib import Path

import httpx
import pytest

from paper_preflight.bib.parse import parse_bib_file, parse_bib_text
from paper_preflight.cache import Cache
from paper_preflight.resolve import Evidence, Sources, resolve

from .fake_web import FakeWeb

DEMO = Path(__file__).parent.parent / "examples" / "demo-paper" / "refs.bib"
KEYS = [
    "he2016deep", "devlin2019bert", "wakefield1998ileal", "tacl2019example", "he2015residual",
    "hendrycks2016gelu", "lindqvist2024quantum", "goodfellow2016deep",
]  # fmt: skip


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


pytestmark = pytest.mark.usefixtures("fast")


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


@pytest.mark.anyio
async def test_arxiv_outage_uses_datacite_records() -> None:
    web = FakeWeb()
    web.fail("export.arxiv.org", "429")
    evidence = await run(web)
    gelu = evidence["hendrycks2016gelu"]
    assert sources_of(gelu) == {"datacite"}
    assert gelu.anchored[0].work_type == "preprint"
    assert gelu.unavailable == {"arxiv": "rate_limited"}  # still reported: no withdrawal check
    assert gelu.arxiv_missing == []  # an outage never makes an ID "missing"
    assert gelu.candidates == []  # anchored, so not searched by title
    assert sources_of(evidence["he2015residual"]) == {"datacite"}
    datacite_calls = [r for r in web.requests if r.url.host == "api.datacite.org"]
    assert len(datacite_calls) == 1  # both preprints in one batch


@pytest.mark.anyio
async def test_versioned_arxiv_doi_resolves_without_its_version() -> None:
    # HALLMARK has VALID entries written like this; doi.org answers 404 for the versioned form
    bib = "@misc{gelu, title={Gaussian Error Linear Units (GELUs)}, author={Hendrycks, Dan}, "
    bib += "year={2016}, doi={10.48550/arXiv.1606.08415v3}}"
    entries = parse_bib_text(bib, Path("refs.bib")).entries
    async with httpx.AsyncClient(transport=httpx.MockTransport(FakeWeb())) as http:
        evidence = await resolve(entries, Sources.create(http, Cache(None), environ={}))
    gelu = evidence["gelu"]
    assert gelu.doi_agency["10.48550/arxiv.1606.08415"].exists
    assert "datacite" in sources_of(gelu)


@pytest.mark.anyio
async def test_version_titles_are_fetched_only_when_the_latest_title_disagrees() -> None:
    # GELU's v1 and v2 were titled differently; an entry may cite either
    v1_title = (
        "Bridging Nonlinearities and Stochastic Regularizers with Gaussian Error Linear Units"
    )
    bib = f"@misc{{old, title={{{v1_title}}}, author={{Hendrycks, Dan and Gimpel, Kevin}}, "
    bib += "year={2016}, eprint={1606.08415}, archivePrefix={arXiv}}"
    web = FakeWeb()
    async with httpx.AsyncClient(transport=httpx.MockTransport(web)) as http:
        evidence = await resolve(
            parse_bib_text(bib, Path("refs.bib")).entries,
            Sources.create(http, Cache(None), environ={}),
        )
    (record,) = [r for r in evidence["old"].anchored if r.source == "arxiv"]
    assert v1_title in record.alt_titles
    arxiv_calls = [r for r in web.requests if r.url.host == "export.arxiv.org"]
    assert len(arxiv_calls) == 2  # the batch, then the versions of this one paper

    current = await run(FakeWeb())  # the demo cites GELU by its current title
    (gelu,) = [r for r in current["hendrycks2016gelu"].anchored if r.source == "arxiv"]
    assert gelu.alt_titles == ()  # no extra request when the latest title matches
