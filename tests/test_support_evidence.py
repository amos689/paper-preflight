"""Finding a cited work's text: arXiv source, Europe PMC, open-access PDF, abstract."""

import io
import tarfile
from pathlib import Path

import httpx
import pytest

from paper_preflight.cache import Cache
from paper_preflight.resolve import Sources
from paper_preflight.support.evidence import ABSTRACT, FULL_TEXT, NONE, EvidenceFetcher, Work

BODY = " ".join(f"Sentence {i} of the method section explains one more detail." for i in range(120))
JATS = (
    "<article><front><article-meta><abstract><p>An abstract from PMC.</p></abstract>"
    f"</article-meta></front><body><sec><p>{BODY}</p></sec></body></article>"
)
LATEX = (
    "\\documentclass{article}\\begin{document}\\begin{abstract}A LaTeX abstract.\\end{abstract}"
    f"\n\n\\section{{Method}}\n{BODY}\n\\end{{document}}\n"
)
OPENALEX = {
    "10.1/pmc": {"id": "W1", "ids": {"pmcid": "https://www.ncbi.nlm.nih.gov/pmc/articles/PMC42"}},
    "10.1/paywall": {
        "id": "W2",
        "abstract_inverted_index": {"Short": [0], "abstract.": [1]},
        "best_oa_location": {"pdf_url": "https://publisher.example/paper.pdf"},
    },
    "10.1/crossref": {"id": "W3"},
    "10.1/pmid-only": {"id": "W5", "ids": {"pmid": "https://pubmed.ncbi.nlm.nih.gov/27219127"}},
    "10.48550/arxiv.2101.00001": {
        "id": "W4", "abstract_inverted_index": {"OpenAlex": [0], "abstract.": [1]},
    },
}  # fmt: skip


def eprint() -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        data = LATEX.encode()
        info = tarfile.TarInfo("main.tex")
        info.size = len(data)
        archive.addfile(info, io.BytesIO(data))
    return buffer.getvalue()


def web(request: httpx.Request) -> httpx.Response:
    url = str(request.url)
    if request.url.host == "api.openalex.org":
        doi = request.url.path.split("doi:", 1)[1]
        record = OPENALEX.get(doi)
        return httpx.Response(200, json=record) if record else httpx.Response(404, json={})
    if request.url.host == "www.ebi.ac.uk" and "PMC42" in url:
        return httpx.Response(200, text=JATS)
    if request.url.host == "www.ebi.ac.uk" and request.url.path.endswith("/search"):
        found = {"pmid": "27219127", "pmcid": "PMC42", "isOpenAccess": "Y"}
        return httpx.Response(200, json={"resultList": {"result": [found]}})
    if request.url.host == "publisher.example":
        return httpx.Response(200, text="<html>Access through your institution</html>")
    if request.url.host == "api.crossref.org" and "10.1/crossref" in url:
        message = {"abstract": "<jats:p>A Crossref abstract.</jats:p>"}
        return httpx.Response(200, json={"message": message})
    if request.url.host == "export.arxiv.org" and "e-print/2101.00001" in url:
        return httpx.Response(200, content=eprint())
    return httpx.Response(404, json={})


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


async def evidence_for(work: Work, folder: Path) -> object:
    transport = httpx.MockTransport(web)
    async with httpx.AsyncClient(transport=transport) as http:
        sources = Sources.create(http, Cache(None), environ={})
        fetcher = EvidenceFetcher(http, sources, Cache(None), folder)
        return await fetcher.evidence(work)


@pytest.mark.anyio
async def test_an_arxiv_paper_is_read_from_its_source(tmp_path: Path) -> None:
    found = await evidence_for(Work(arxiv="2101.00001"), tmp_path)
    assert (found.level, found.source) == (FULL_TEXT, "arXiv source")
    assert found.passages[0] == "OpenAlex abstract."  # the registry's abstract first
    # then the source's own text, without its "Method" heading
    assert found.passages[1].startswith("Sentence 0 of the method section")
    assert (tmp_path / "arxiv" / "2101.00001" / "main.tex").exists()  # kept for the next run


@pytest.mark.anyio
async def test_a_pubmed_central_paper_is_read_from_europe_pmc(tmp_path: Path) -> None:
    found = await evidence_for(Work(doi="10.1/pmc"), tmp_path)
    assert (found.level, found.source) == (FULL_TEXT, "Europe PMC")
    assert found.passages[0] == "An abstract from PMC."


@pytest.mark.anyio
async def test_a_pubmed_paper_is_found_in_pmc_by_its_pmid(tmp_path: Path) -> None:
    # OpenAlex gives MIMIC-III's PMID but not its PMCID
    found = await evidence_for(Work(doi="10.1/pmid-only"), tmp_path)
    assert (found.level, found.source) == (FULL_TEXT, "Europe PMC")


@pytest.mark.anyio
async def test_a_paywall_page_is_no_full_text(tmp_path: Path) -> None:
    found = await evidence_for(Work(doi="10.1/paywall"), tmp_path)
    assert (found.level, found.source, found.passages) == (
        ABSTRACT, "OpenAlex abstract", ("Short abstract.",)
    )  # fmt: skip
    assert found.notes == ("open-access PDF: not a PDF (HTTP 200)",)


@pytest.mark.anyio
async def test_the_abstract_falls_back_to_crossref_and_then_to_nothing(tmp_path: Path) -> None:
    found = await evidence_for(Work(doi="10.1/crossref"), tmp_path)
    assert (found.level, found.passages) == (ABSTRACT, ("A Crossref abstract.",))
    nothing = await evidence_for(Work(doi="10.1/unknown"), tmp_path)
    assert (nothing.level, nothing.passages) == (NONE, ())
