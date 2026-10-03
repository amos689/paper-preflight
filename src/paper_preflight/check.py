"""The `check` pipeline: load the project, run checks, produce a result for reporters."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path

from paper_preflight import __version__
from paper_preflight.bib.parse import BibFile, parse_bib_file
from paper_preflight.findings import Finding, Location, Severity, sort_findings
from paper_preflight.hygiene import HygieneInput, bib_paths_for, check_hygiene
from paper_preflight.rules import make_finding
from paper_preflight.tex.auxdata import find_build_data
from paper_preflight.tex.cites import command_table
from paper_preflight.tex.project import TexProject, load_project


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

    def count(self, severity: Severity) -> int:
        return sum(1 for f in self.findings if f.severity is severity)

    def has_blocking(self, fail_on: Severity | None) -> bool:
        if fail_on is None:
            return False
        return any(f.severity.rank >= fail_on.rank for f in self.findings)


def run_check(
    target: Path,
    *,
    main: Path | None = None,
    extra_bib: list[Path] | None = None,
    cite_commands: list[str] | None = None,
) -> CheckResult:
    """Run all offline checks. Online reference verification is added in a later milestone."""
    started = time.time()
    extra = [p.resolve() for p in (extra_bib or [])]
    target = target.resolve()

    if target.is_file() and target.suffix.lower() == ".bib":
        bib_files = [parse_bib_file(target), *(parse_bib_file(p) for p in extra if p != target)]
        findings = check_hygiene(HygieneInput(bib_files=bib_files))
        return CheckResult(
            root=target.parent,
            main=None,
            bib_files=bib_files,
            findings=sort_findings(findings),
            cited_keys=0,
            entries=sum(len(b.entries) for b in bib_files),
            used_build_data=None,
            started_at=started,
            finished_at=time.time(),
        )

    project: TexProject = load_project(
        target, main=main.resolve() if main else None, commands=command_table(cite_commands or [])
    )
    build = find_build_data(project.main, project.files)
    cited = set(build.cited_keys) if build else project.cited_keys()
    nocite_all = project.nocite_all or bool(build and build.nocite_all)
    bib_paths = bib_paths_for(project, extra)
    bib_files = [parse_bib_file(p) for p in bib_paths]
    findings = check_hygiene(
        HygieneInput(
            bib_files=bib_files,
            project=project,
            build_data=build,
            cited_keys=cited,
            nocite_all=nocite_all,
        )
    )
    if not project.bib_resources and not extra:
        findings.append(
            make_finding("CIT005", Location(project.main, 1, 1), path="(no \\bibliography found)")
        )
    return CheckResult(
        root=project.root,
        main=project.main,
        bib_files=bib_files,
        findings=sort_findings(findings),
        cited_keys=len(cited),
        entries=sum(len(b.entries) for b in bib_files),
        used_build_data=build.source.name if build else None,
        started_at=started,
        finished_at=time.time(),
    )
