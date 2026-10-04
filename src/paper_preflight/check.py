"""The `check` pipeline: load the project, run checks, produce a result for reporters."""

from __future__ import annotations

import asyncio
import time
from collections import Counter
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import httpx

from paper_preflight import __version__
from paper_preflight.bib.bbl import parse_bbl_file
from paper_preflight.bib.parse import BibEntry, BibFile, parse_bib_file
from paper_preflight.bib.pdftext import parse_pdf_file
from paper_preflight.bib.plaintext import parse_plaintext_file
from paper_preflight.cache import Cache
from paper_preflight.findings import Finding, Location, Severity, sort_findings
from paper_preflight.hygiene import (
    HygieneInput,
    bib_paths_for,
    check_hygiene_tracked,
    unused_suppressions,
)
from paper_preflight.resolve import Evidence, Sources, resolve
from paper_preflight.rules import make_finding
from paper_preflight.sources.base import SourceStats
from paper_preflight.tex.auxdata import find_build_data
from paper_preflight.tex.cites import command_table
from paper_preflight.tex.project import TexProject, load_project
from paper_preflight.verdict import Assessment, Reason, Verdict, assess_all, run_findings


@dataclass(frozen=True)
class VerifyOptions:
    """How to verify references against scholarly sources (online by default)."""

    offline: bool = False  # answer from the cache only; never touch the network
    refresh: bool = False  # ask every source again instead of answering from the cache
    cache_path: Path | None = None  # None = an in-memory cache for this run only
    environ: Mapping[str, str] | None = None  # credentials; defaults to os.environ
    current_year: int | None = None
    # told (stage, done, total) while the slow stages run: "title" searches, Semantic Scholar's
    # "rescue"; the CLI shows it, the MCP server sends it as progress notifications
    progress: Callable[[str, int, int], None] | None = field(default=None, compare=False)


def make_transport() -> httpx.AsyncBaseTransport | None:
    """The HTTP transport for source requests. Tests replace it with a recorded web."""
    return None


@dataclass
class CheckResult:
    root: Path
    main: Path | None
    bib_files: list[BibFile]
    findings: list[Finding]
    cited_keys: int
    entries: int
    used_build_data: str | None  # ".aux"/".bcf" file used for the cited-key set, if any
    complete: bool = True
    notes: list[str] = field(default_factory=list)
    started_at: float = 0.0
    finished_at: float = 0.0
    tool_version: str = __version__
    verification: str = "skipped"  # "online" | "offline" | "skipped"
    verdicts: dict[str, Assessment] = field(default_factory=dict)
    unverified_offline: int = 0  # references without a cached answer in offline mode
    sources: dict[str, SourceStats] = field(default_factory=dict)  # what each source answered

    def count(self, severity: Severity) -> int:
        return sum(1 for f in self.findings if f.severity is severity)

    def verdict_counts(self) -> dict[str, int]:
        counts = Counter(a.verdict.value for a in self.verdicts.values())
        return {v.value: counts.get(v.value, 0) for v in Verdict}

    def has_blocking(self, fail_on: Severity | None) -> bool:
        if fail_on is None:
            return False
        return any(f.severity.rank >= fail_on.rank for f in self.findings)


# a reference list given on its own: BibTeX, a compiled bibliography, plain text or a PDF
_READERS: dict[str, Callable[[Path], BibFile]] = {
    ".bib": parse_bib_file,
    ".bbl": parse_bbl_file,
    ".txt": parse_plaintext_file,
    ".pdf": parse_pdf_file,
}


def run_check(
    target: Path,
    *,
    main: Path | None = None,
    extra_bib: list[Path] | None = None,
    cite_commands: list[str] | None = None,
    verify: VerifyOptions | None = None,
) -> CheckResult:
    """Run the checks. Without ``verify`` only the offline citation-hygiene rules run."""
    started = time.time()
    extra = [p.resolve() for p in (extra_bib or [])]
    target = target.resolve()

    if target.is_file() and target.suffix.lower() in _READERS:
        first = _READERS[target.suffix.lower()](target)
        bib_files = [first, *(parse_bib_file(p) for p in extra if p != target)]
        findings, used = check_hygiene_tracked(HygieneInput(bib_files=bib_files))
        result = CheckResult(
            root=target.parent,
            main=None,
            bib_files=bib_files,
            findings=findings,
            cited_keys=0,
            entries=sum(len(b.entries) for b in bib_files),
            used_build_data=None,
            started_at=started,
        )
        to_verify = first_definitions(bib_files)
    else:
        project: TexProject = load_project(
            target,
            main=main.resolve() if main else None,
            commands=command_table(cite_commands or []),
        )
        build = find_build_data(project.main, project.files)
        cited = set(build.cited_keys) if build else project.cited_keys()
        nocite_all = project.nocite_all or bool(build and build.nocite_all)
        bib_paths = bib_paths_for(project, extra)
        bib_files = [parse_bib_file(p) for p in bib_paths]
        compiled = None if bib_files else _compiled_bibliography(project.main)
        if compiled is not None:
            bib_files = [parse_bbl_file(compiled)]
        undeclared = None
        if not bib_files and not project.bib_resources:
            undeclared = _only_bib_file(project.main)
            if undeclared is not None:
                bib_files = [parse_bib_file(undeclared)]
        findings, used = check_hygiene_tracked(
            HygieneInput(
                bib_files=bib_files,
                project=project,
                build_data=build,
                cited_keys=cited,
                nocite_all=nocite_all,
            )
        )
        if compiled is not None:
            # the .bib files are not here (an arXiv source, say): the .bbl stands in for them
            findings = [f for f in findings if f.rule_id != "CIT005"]
        elif not project.bib_resources and not extra:
            findings.append(
                make_finding(
                    "CIT005", Location(project.main, 1, 1), path="(no \\bibliography found)"
                )
            )
        result = CheckResult(
            root=project.root,
            main=project.main,
            bib_files=bib_files,
            findings=findings,
            cited_keys=len(cited),
            entries=sum(len(b.entries) for b in bib_files),
            used_build_data=build.source.name if build else None,
            started_at=started,
        )
        # only references that appear in the PDF are verified
        to_verify = first_definitions(bib_files, None if nocite_all else cited)

        if compiled is not None:
            result.notes.append(
                f"References read from {compiled.name}: no .bib file was found. "
                "Fixes are not proposed for a compiled bibliography."
            )
        if undeclared is not None:
            result.notes.append(
                f"References read from {undeclared.name}, the only .bib file next to the main "
                "file: the LaTeX source declares no bibliography (CIT005)."
            )

    if verify is not None:
        _verify_into(result, to_verify, verify)
    result.findings.extend(_unused_suppressions(result, used))
    result.findings = sort_findings(result.findings)
    result.finished_at = time.time()
    return result


# Citation rules that need the LaTeX project: a .bib-only run cannot have triggered them.
_PROJECT_RULES = frozenset({"CIT001", "CIT003", "CIT005"})


def _unused_suppressions(result: CheckResult, used: set[tuple[str, str]]) -> list[Finding]:
    """CFG001 for suppressions that dropped nothing, among the rules that ran on their entry."""
    used = used | {(key, rule) for key, a in result.verdicts.items() for rule in a.suppressed}

    def judged(entry: BibEntry, rule: str) -> bool:
        if rule.startswith("TEX") or rule in _PROJECT_RULES:
            return result.main is not None
        if rule.startswith("CIT"):
            return True
        if rule.startswith("REF"):
            # only a complete online run has asked every source about every verified entry:
            # offline answers and outages may leave some reference rules unrun
            online = result.verification == "online" and result.complete
            return online and entry.key in result.verdicts
        return False  # RUN001 and CFG001 are not about one entry

    return unused_suppressions(first_definitions(result.bib_files), used, judged)


def _compiled_bibliography(main: Path) -> Path | None:
    """The .bbl LaTeX left for the main file (or the only one in its folder), if any."""
    same_name = main.with_suffix(".bbl")
    if same_name.is_file():
        return same_name
    others = sorted(main.parent.glob("*.bbl"))
    return others[0] if len(others) == 1 else None


def _only_bib_file(main: Path) -> Path | None:
    """The one .bib next to a main file that declares no bibliography, if there is one: a
    source that forgot its \\bibliography line (arXiv 2607.20215v1) still has its references."""
    found = sorted(main.parent.glob("*.bib"))
    return found[0] if len(found) == 1 else None


def first_definitions(bib_files: Iterable[BibFile], keys: set[str] | None = None) -> list[BibEntry]:
    """Entries BibTeX would use: the first definition of each key, optionally only ``keys``."""
    seen: set[str] = set()
    entries: list[BibEntry] = []
    for bib in bib_files:
        for entry in bib.entries:
            if entry.key in seen:
                continue
            seen.add(entry.key)
            if keys is None or entry.key in keys:
                entries.append(entry)
    return entries


async def verify_entries(
    entries: list[BibEntry], options: VerifyOptions
) -> tuple[dict[str, Evidence], dict[str, Assessment], dict[str, SourceStats]]:
    """Gather evidence for ``entries`` and assess each one (docs/adr/0002, 0003).

    Also returns what each source did: requests, cache hits, negatives, unavailability.
    """
    cache = Cache(options.cache_path)
    try:
        # doi.org answers content negotiation with a redirect to the registration agency
        async with httpx.AsyncClient(transport=make_transport(), follow_redirects=True) as http:
            environ = dict(options.environ) if options.environ is not None else None
            sources = Sources.create(
                http, cache, offline=options.offline, environ=environ,
                fresh_after=time.time() if options.refresh else None,
            )  # fmt: skip
            sources.progress = options.progress
            evidence = await resolve(entries, sources)
            stats = {client.name: client.stats for client in sources.all_clients()}
    finally:
        cache.close()
    year = options.current_year or datetime.now().year
    return evidence, assess_all(entries, evidence, current_year=year), stats


def _verify_into(result: CheckResult, entries: list[BibEntry], options: VerifyOptions) -> None:
    result.verification = "offline" if options.offline else "online"
    if not entries:
        return
    evidence, verdicts, stats = asyncio.run(verify_entries(entries, options))
    result.verdicts = verdicts
    result.sources = stats
    # Offline is the user's choice, not a failing source: references without a cached answer
    # are counted once (reporters show the number) instead of one REF090 line each, and they
    # do not make the run incomplete.
    offline_only = {k for k, a in verdicts.items() if a.reasons == (Reason.OFFLINE_MODE,)}
    result.unverified_offline = len(offline_only)
    for key, assessment in verdicts.items():
        result.findings.extend(
            f for f in assessment.findings if not (key in offline_only and f.rule_id == "REF090")
        )
    result.findings.extend(run_findings(evidence))
    result.complete = not any(
        reason != "offline" for item in evidence.values() for reason in item.unavailable.values()
    )
