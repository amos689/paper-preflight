"""A cited work's text, for judging whether it supports a citation.

The richest text that can be had, in this order:

1. arXiv: the paper's LaTeX source, or its PDF when it was submitted without source;
2. Europe PMC: the open-access full text (JATS) of a paper in PubMed Central;
3. an open-access PDF that OpenAlex lists for the DOI;
4. the abstract: OpenAlex, Semantic Scholar (with a key), Crossref.

A supposed full text that is a publisher's access page, a first page or an empty extraction
(:func:`paper_preflight.support.texts.incomplete`) is not used, and the next source is tried;
each failure is kept as a note. Every :class:`Evidence` says what it is: ``full_text``,
``abstract`` or ``none``; an abstract can confirm a claim but leaves most of a paper out.

Downloads (arXiv sources, PDFs) stay in a local folder under the cache directory.
"""

from __future__ import annotations

import asyncio
import hashlib
import re
import time
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx

from paper_preflight import arxiv_source
from paper_preflight.bib.pdftext import PdfUnavailable
from paper_preflight.cache import Cache
from paper_preflight.resolve import Sources
from paper_preflight.sources.base import SourceClient, SourcePolicy, SourceUnavailable
from paper_preflight.support.sentences import document_abstract, document_paragraphs
from paper_preflight.support.texts import (
    incomplete,
    inverted_abstract,
    jats_fragment_text,
    jats_passages,
    passages_of,
    pdf_passages,
)
from paper_preflight.tex.project import ProjectError, find_main_file, load_project

FULL_TEXT, ABSTRACT, NONE = "full_text", "abstract", "none"
EPRINT_INTERVAL = 3.5  # arXiv asks for one request every three seconds
MAX_PDF_BYTES = 40_000_000
EUROPEPMC = "https://www.ebi.ac.uk/europepmc/webservices/rest"
EUROPEPMC_POLICY = SourcePolicy(name="europepmc", min_interval=0.25, max_concurrency=1)
OPENALEX_WORK = "https://api.openalex.org/works/doi:{doi}"
OPENALEX_SELECT = "id,doi,ids,abstract_inverted_index,best_oa_location"
S2_PAPER = "https://api.semanticscholar.org/graph/v1/paper/{id}"
CROSSREF_WORK = "https://api.crossref.org/works/{doi}"
NO_PDF_READER = "a PDF, which needs the pdf extra to read: pip install 'paper-preflight[pdf]'"


@dataclass(frozen=True)
class Work:
    """What identifies a cited work: any of these."""

    doi: str | None = None
    arxiv: str | None = None
    pmcid: str | None = None


@dataclass(frozen=True)
class Evidence:
    level: str  # FULL_TEXT | ABSTRACT | NONE
    source: str  # where the text came from ("arXiv source", "Europe PMC", ...)
    passages: tuple[str, ...] = ()  # the abstract first, when known
    notes: tuple[str, ...] = field(default=())  # why richer sources were not used


def _with_abstract(abstract: str, passages: list[str]) -> tuple[str, ...]:
    body = [p for p in passages if p and p != abstract]
    return tuple([abstract, *body] if abstract else body)


MIN_PASSAGE_WORDS = 4  # headings ("Method") and stray labels carry no claim


def _chunked(paragraphs: list[str]) -> list[str]:
    """Paragraphs, long ones cut into passages at sentence ends; headings left out."""
    return [
        passage
        for paragraph in paragraphs
        for passage in passages_of(paragraph)
        if len(passage.split()) >= MIN_PASSAGE_WORDS
    ]


class EvidenceFetcher:
    """Finds the text of cited works; one per run (it paces arXiv and keeps the downloads)."""

    def __init__(
        self,
        http: httpx.AsyncClient,
        sources: Sources,
        cache: Cache,
        folder: Path,
        *,
        offline: bool = False,
    ) -> None:
        self.http = http
        self.sources = sources
        self.folder = folder
        self.offline = offline
        self.europepmc = SourceClient(replace(EUROPEPMC_POLICY), http, cache, offline=offline)
        self._last_eprint = 0.0

    async def evidence(self, work: Work) -> Evidence:
        notes: list[str] = []
        doi = work.doi or (f"10.48550/arxiv.{work.arxiv}".lower() if work.arxiv else None)
        record = await self._openalex(doi) if doi else None
        abstract = inverted_abstract((record or {}).get("abstract_inverted_index"))
        if work.arxiv:
            found = await self._arxiv(work.arxiv)
            if isinstance(found, tuple):
                source, passages, own_abstract = found
                return Evidence(
                    FULL_TEXT, source, _with_abstract(abstract or own_abstract, passages),
                    tuple(notes),
                )  # fmt: skip
            notes.append(f"arXiv: {found}")
        pmcid = work.pmcid or _pmcid(record) or await self._pmcid_for(record)
        if pmcid:
            found_text = await self._europepmc_text(pmcid)
            if isinstance(found_text, list):
                return Evidence(
                    FULL_TEXT, "Europe PMC", _with_abstract("", found_text), tuple(notes)
                )
            notes.append(f"Europe PMC: {found_text}")
        pdf_url = ((record or {}).get("best_oa_location") or {}).get("pdf_url")
        if pdf_url:
            found_pdf = await self._pdf(pdf_url)
            if isinstance(found_pdf, list):
                return Evidence(
                    FULL_TEXT, "open-access PDF", _with_abstract(abstract, found_pdf), tuple(notes)
                )
            notes.append(f"open-access PDF: {found_pdf}")
        source = "OpenAlex abstract"
        if not abstract and (work.doi or work.arxiv):
            abstract, source = await self._s2_abstract(work), "Semantic Scholar abstract"
        if not abstract and work.doi:
            abstract, source = await self._crossref_abstract(work.doi), "Crossref abstract"
        if abstract:
            return Evidence(ABSTRACT, source, (abstract,), tuple(notes))
        return Evidence(NONE, "", (), tuple(notes))

    # ------------------------------------------------------------ sources

    async def _get_json(self, client: SourceClient | None, url: str, **kwargs: Any) -> Any:
        if client is None:
            return None
        try:
            return (await client.get_json(url, **kwargs)).data
        except SourceUnavailable:
            return None

    async def _openalex(self, doi: str) -> dict[str, Any] | None:
        params: dict[str, Any] = {"select": OPENALEX_SELECT}
        if self.sources.openalex_key:
            params["api_key"] = self.sources.openalex_key
        data = await self._get_json(
            self.sources.openalex, OPENALEX_WORK.format(doi=quote(doi.lower(), safe="/")),
            params=params,
        )  # fmt: skip
        return data if isinstance(data, dict) else None

    async def _s2_abstract(self, work: Work) -> str:
        if self.sources.s2 is None or not self.sources.s2_key:
            return ""
        paper = f"DOI:{work.doi}" if work.doi else f"ARXIV:{work.arxiv}"
        data = await self._get_json(
            self.sources.s2, S2_PAPER.format(id=quote(paper, safe=":/")),
            params={"fields": "abstract"}, headers={"x-api-key": self.sources.s2_key},
        )  # fmt: skip
        return " ".join(str((data or {}).get("abstract") or "").split())

    async def _crossref_abstract(self, doi: str) -> str:
        params = {"mailto": self.sources.mailto} if self.sources.mailto else None
        data = await self._get_json(
            self.sources.crossref, CROSSREF_WORK.format(doi=quote(doi, safe="/")), params=params
        )
        fragment = ((data or {}).get("message") or {}).get("abstract") or ""
        return jats_fragment_text(str(fragment)) if fragment else ""

    async def _pmcid_for(self, record: dict[str, Any] | None) -> str | None:
        """The PubMed Central ID of a PubMed paper OpenAlex knows only by its PMID (Europe
        PMC's search; MIMIC-III, 10.1038/sdata.2016.35, is PMC4878278)."""
        pmid = re.search(r"\d+$", str(((record or {}).get("ids") or {}).get("pmid") or ""))
        if pmid is None:
            return None
        data = await self._get_json(
            self.europepmc, f"{EUROPEPMC}/search",
            params={"query": f"EXT_ID:{pmid.group(0)} AND SRC:MED", "format": "json",
                    "resultType": "lite"},
        )  # fmt: skip
        results = ((data or {}).get("resultList") or {}).get("result") or []
        open_access = [r for r in results if r.get("isOpenAccess") == "Y" and r.get("pmcid")]
        return str(open_access[0]["pmcid"]) if open_access else None

    async def _europepmc_text(self, pmcid: str) -> list[str] | str:
        try:
            fetched = await self.europepmc.get_text(f"{EUROPEPMC}/{pmcid}/fullTextXML")
        except SourceUnavailable as error:
            return f"unavailable ({error.reason.value})"
        if not fetched.data:
            return "no open-access full text"
        passages = _chunked(jats_passages(str(fetched.data)))
        return incomplete(passages) or passages

    async def _arxiv(self, arxiv_id: str) -> tuple[str, list[str], str] | str:
        """("arXiv source" or "arXiv PDF", passages, the source's abstract), or why not."""
        folder = self.folder / "arxiv" / re.sub(r"[^\w.-]", "_", arxiv_id)
        if not folder.exists():
            if self.offline:
                return "not downloaded (offline)"
            wait = self._last_eprint + EPRINT_INTERVAL - time.monotonic()
            if wait > 0:
                await asyncio.sleep(wait)
            try:
                response = await self.http.get(
                    arxiv_source.EPRINT + arxiv_id, headers=arxiv_source.HEADERS, timeout=60
                )
                arxiv_source.store(arxiv_id, response.status_code, response.content, folder)
            except httpx.HTTPError as error:
                return f"could not be downloaded ({type(error).__name__})"
            except arxiv_source.ArxivSourceError as error:
                return str(error)
            finally:
                self._last_eprint = time.monotonic()
        pdfs = sorted(folder.glob("*.pdf"))
        if any(folder.rglob("*.tex")):
            try:
                project = load_project(folder, main=_main_file(folder))
            except ProjectError as error:
                return f"its source could not be read ({error})"
            passages = _chunked(document_paragraphs(project))
            reason = incomplete(passages)
            return reason if reason else ("arXiv source", passages, document_abstract(project))
        if pdfs:
            try:
                passages = pdf_passages(pdfs[0])
            except PdfUnavailable:
                return NO_PDF_READER
            reason = incomplete(passages)
            return reason if reason else ("arXiv PDF", passages, "")
        return "nothing readable in its source"

    async def _pdf(self, url: str) -> list[str] | str:
        path = self.folder / "pdf" / f"{hashlib.sha1(url.encode()).hexdigest()}.pdf"
        if not path.exists():
            if self.offline:
                return "not downloaded (offline)"
            try:
                response = await self.http.get(
                    url, headers=arxiv_source.HEADERS, follow_redirects=True, timeout=60
                )
            except httpx.HTTPError as error:
                return f"could not be downloaded ({type(error).__name__})"
            content = response.content
            if response.status_code != 200 or content[:5] != b"%PDF-":
                return f"not a PDF (HTTP {response.status_code})"
            if len(content) > MAX_PDF_BYTES:
                return "larger than 40 MB"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        try:
            passages = pdf_passages(path)
        except PdfUnavailable:
            return NO_PDF_READER
        return incomplete(passages) or passages


def _main_file(folder: Path) -> Path | None:
    """The main file of an arXiv source: what ``check`` would pick, else the largest file with
    a document body anywhere in the source (sources with several candidates, or the main file
    in a subfolder)."""
    try:
        return find_main_file(folder)
    except ProjectError:
        pass
    body = r"\begin{document}"
    bodies = [p for p in folder.rglob("*.tex") if body in p.read_text("utf-8", "ignore")]
    candidates = bodies or list(folder.rglob("*.tex"))
    return max(candidates, key=lambda p: p.stat().st_size) if candidates else None


def _pmcid(record: dict[str, Any] | None) -> str | None:
    """OpenAlex's PubMed Central ID ("https://www.ncbi.nlm.nih.gov/pmc/articles/PMC123")."""
    link = str(((record or {}).get("ids") or {}).get("pmcid") or "")
    match = re.search(r"PMC\d+", link)
    return match.group(0) if match else None
