"""``support``: for every citation of a LaTeX paper, does the cited work support the claim?

1. The references are checked as ``check`` does; only works bound to a record (verified, or
   with metadata problems) are looked at: a work that may not exist has no text to read.
2. Every citation's sentence and claim are read from the LaTeX (S1).
3. Each cited work's text is fetched once (S2): the entry's own arXiv ID first (the version it
   cites), then the record's identifiers.
4. Each claim is judged against the passages ranked for it (S3, S5).
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

import httpx

from paper_preflight import check as check_module
from paper_preflight.bib.ids import extract_identifiers
from paper_preflight.bib.parse import BibEntry
from paper_preflight.cache import Cache
from paper_preflight.check import CheckResult, VerifyOptions, run_check
from paper_preflight.resolve import Sources
from paper_preflight.support.evidence import Evidence, EvidenceFetcher, Work
from paper_preflight.support.judge import Judgement, Verifier, judge
from paper_preflight.support.sentences import CitationSentence, citation_sentences
from paper_preflight.tex.project import load_project
from paper_preflight.verdict import Assessment, Verdict

CHECKABLE = frozenset({Verdict.VERIFIED, Verdict.METADATA_MISMATCH})


@dataclass(frozen=True)
class SupportItem:
    citation: CitationSentence
    judgement: Judgement
    evidence: Evidence


@dataclass
class SupportResult:
    items: list[SupportItem] = field(default_factory=list)
    # cited keys left out, and why: "not verified (not_found)", "no identifier"
    skipped: dict[str, str] = field(default_factory=dict)
    check: CheckResult | None = None


def work_for(entry: BibEntry | None, assessment: Assessment) -> Work | None:
    """The identifiers to fetch a cited work's text by: the entry's arXiv ID (the version it
    cites) before the bound record's."""
    record = assessment.record
    own = {i.scheme: i.value for i in extract_identifiers(entry)} if entry else {}
    ids = record.identifiers if record else {}
    arxiv = own.get("arxiv") or ids.get("arxiv")
    doi = (record.doi if record else None) or own.get("doi")
    if doi and doi.startswith("10.48550/arxiv."):
        arxiv, doi = arxiv or doi.removeprefix("10.48550/arxiv."), None
    pmcid = ids.get("pmcid") or own.get("pmcid")
    if not (arxiv or doi or pmcid):
        return None
    return Work(doi=doi, arxiv=arxiv, pmcid=pmcid)


@dataclass
class Gathered:
    """What a claim is judged on: each citation's sentence and its cited work's text."""

    check: CheckResult
    sentences: list[CitationSentence]
    evidence: dict[str, Evidence]  # by key
    titles: dict[str, str]  # the bound record's title, by key
    skipped: dict[str, str]


def gather(
    target: Path,
    *,
    cache_path: Path | None,
    folder: Path,
    offline: bool = False,
    environ: dict[str, str] | None = None,
    keys: set[str] | None = None,
) -> Gathered:
    """Steps 1-3: check the references, read the citation sentences and fetch the cited works'
    text (only for ``keys``, when given)."""
    checked = run_check(
        target, verify=VerifyOptions(cache_path=cache_path, offline=offline, environ=environ)
    )
    entries = {e.key: e for b in checked.bib_files for e in b.entries}
    skipped: dict[str, str] = {}
    works: dict[str, Work] = {}
    for key, assessment in checked.verdicts.items():
        if keys is not None and key not in keys:
            continue
        if assessment.verdict not in CHECKABLE:
            skipped[key] = f"not verified ({assessment.verdict.value})"
        elif (work := work_for(entries.get(key), assessment)) is None:
            skipped[key] = "no identifier to find its text by"
        else:
            works[key] = work
    sentences = _once(s for s in citation_sentences(load_project(target)) if s.key in works)
    evidence = asyncio.run(_fetch(works, cache_path, folder, offline=offline, environ=environ))
    titles = {
        key: record.title
        for key in works
        if (record := checked.verdicts[key].record) is not None and record.title
    }
    return Gathered(checked, sentences, evidence, titles, skipped)


def run_support(
    target: Path,
    verifier: Verifier,
    *,
    cache_path: Path | None,
    folder: Path,
    offline: bool = False,
    environ: dict[str, str] | None = None,
) -> SupportResult:
    found = gather(target, cache_path=cache_path, folder=folder, offline=offline, environ=environ)
    result = SupportResult(skipped=found.skipped, check=found.check)
    for sentence in found.sentences:
        evidence = found.evidence[sentence.key]
        judgement = judge(
            sentence.claim, evidence, verifier,
            name=sentence.name, title=found.titles.get(sentence.key, ""),
        )  # fmt: skip
        result.items.append(SupportItem(sentence, judgement, evidence))
    return result


def _once(sentences: Iterable[CitationSentence]) -> list[CitationSentence]:
    """Each claim once per cited work: a sentence may cite the same work twice."""
    seen: set[tuple[str, Path, str]] = set()
    out = []
    for sentence in sentences:
        if (sentence.key, sentence.file, sentence.claim) not in seen:
            seen.add((sentence.key, sentence.file, sentence.claim))
            out.append(sentence)
    return out


async def _fetch(
    works: dict[str, Work],
    cache_path: Path | None,
    folder: Path,
    *,
    offline: bool,
    environ: dict[str, str] | None,
) -> dict[str, Evidence]:
    cache = Cache(cache_path)
    found: dict[Work, Evidence] = {}
    try:
        async with httpx.AsyncClient(
            transport=check_module.make_transport(), follow_redirects=True
        ) as http:
            sources = Sources.create(http, cache, offline=offline, environ=environ)
            fetcher = EvidenceFetcher(http, sources, cache, folder, offline=offline)
            for work in dict.fromkeys(works.values()):
                found[work] = await fetcher.evidence(work)
    finally:
        cache.close()
    return {key: found[work] for key, work in works.items()}
