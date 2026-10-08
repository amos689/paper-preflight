"""The Python API: check a paper or a reference list from code (D3 in the sixth-round plan).

    import paper_preflight

    report = paper_preflight.check_paper("paper/")       # online, with the user's cache
    report.complete                                       # did every source needed answer?
    for ref in report.references:                         # one per checked reference
        print(ref.key, ref.verdict, ref.reasons)
    for finding in report.findings:                       # every finding, errors first
        print(finding.rule, finding.severity, finding.message)
    report.blocking("warning")                            # as the CLI's exit code 1
    report.to_dict()                                      # the JSON report (docs/schema)

The objects are plain, frozen dataclasses with strings for enumerations, so they stay stable
across releases as the JSON report does: fields may be added, none removed or changed in
meaning without a new major version.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from paper_preflight.check import CheckResult, VerifyOptions, run_check
from paper_preflight.config import Config, find_config, load_config
from paper_preflight.findings import Severity

Language = Literal["en", "zh"]


@dataclass(frozen=True)
class Finding:
    rule: str  # "REF003"
    severity: str  # "error" | "warning" | "info"
    message: str  # in the language asked for
    key: str | None  # the BibTeX key, when the finding is about an entry
    field: str | None  # the field, when it is about one field
    file: str | None  # where it is, relative to the checked path when inside it
    line: int | None
    id: str  # stable across runs and line moves


@dataclass(frozen=True)
class MatchedRecord:
    source: str  # "crossref", "dblp", "arxiv", ...
    id: str
    title: str
    year: int | None
    venue: str | None
    doi: str | None


@dataclass(frozen=True)
class Reference:
    key: str
    verdict: str  # "verified" | "metadata_mismatch" | "identifier_conflict" | "not_found" | ...
    reasons: tuple[str, ...]  # why it could not be judged ("GREY_LITERATURE", "TOO_NEW", ...)
    matched: MatchedRecord | None  # the record it was compared with
    findings: tuple[Finding, ...]


@dataclass(frozen=True)
class Report:
    path: Path
    complete: bool  # False when a source needed did not answer: results may change later
    verification: str  # "online" | "offline" | "skipped"
    references: tuple[Reference, ...]
    findings: tuple[Finding, ...]
    result: CheckResult  # everything, as the CLI's reporters see it (not a stable API)

    def blocking(self, fail_on: str = "error") -> bool:
        """Whether a finding at or above ``fail_on`` ("error", "warning") was reported."""
        return self.result.has_blocking(Severity(fail_on))

    def to_dict(self) -> dict[str, Any]:
        """The JSON report, as ``check --format json`` writes it."""
        from paper_preflight.report.jsonout import to_json_dict

        return to_json_dict(self.result)


def check_paper(
    path: str | Path,
    *,
    online: bool = True,
    cache: str | Path | None = "default",
    settings: str | Path | Literal["find"] | None = "find",
    main: str | Path | None = None,
    extra_bib: Sequence[str | Path] = (),
    language: Language = "en",
) -> Report:
    """Check a LaTeX project, a manuscript or a reference list, as ``paper-preflight check``.

    ``online``: verify the references against the sources (else only the offline citation
    rules run). ``cache``: the answer cache, "default" for the user's own (as the CLI's), a
    path, or None for one in memory. ``settings``: "find" looks for the project's settings
    file as the CLI does, a path names one, None uses none.
    """
    target = Path(path)
    config = _config(target, settings)
    verify = None
    if online:
        verify = VerifyOptions(
            cache_path=_cache_path(cache), disabled_sources=config.disable_sources
        )
    result = run_check(
        target,
        main=Path(main) if main is not None else None,
        extra_bib=[Path(b) for b in extra_bib],
        verify=verify,
        config=config,
    )
    findings = tuple(_finding(f, result.root, language) for f in result.findings)
    by_id = {f.id: f for f in findings}
    references = tuple(
        Reference(
            key=a.key,
            verdict=a.verdict.value,
            reasons=tuple(r.value for r in a.reasons),
            matched=None
            if a.record is None
            else MatchedRecord(
                a.record.source,
                a.record.source_id,
                a.record.title,
                a.record.year,
                a.record.venue,
                a.record.doi,
            ),
            findings=tuple(by_id[f.fingerprint] for f in a.findings if f.fingerprint in by_id),
        )
        for a in result.verdicts.values()
    )
    return Report(
        path=target,
        complete=result.complete,
        verification=result.verification,
        references=references,
        findings=findings,
        result=result,
    )


def _config(target: Path, settings: str | Path | None) -> Config:
    if settings is None:
        return Config()
    if settings == "find":
        found = find_config(target)
        return load_config(found) if found is not None else Config()
    return load_config(Path(settings))


def _cache_path(cache: str | Path | None) -> Path | None:
    if cache is None:
        return None
    if cache == "default":
        from paper_preflight.cli import cache_dir

        return Path(cache_dir()) / "cache.sqlite3"
    return Path(cache)


def _finding(finding: Any, root: Path, language: Language) -> Finding:
    location = finding.location
    file = None
    if location is not None:
        try:
            file = location.file.relative_to(root).as_posix()
        except ValueError:
            file = location.file.as_posix()
    return Finding(
        rule=finding.rule_id,
        severity=finding.severity.value,
        message=finding.message.zh if language == "zh" else finding.message.en,
        key=finding.key,
        field=finding.field,
        file=file,
        line=location.line if location is not None else None,
        id=finding.fingerprint,
    )
