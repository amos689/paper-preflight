"""Machine-readable JSON report (schema version 0.1; agents and scripts consume this)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from paper_preflight.check import CheckResult
from paper_preflight.findings import Severity
from paper_preflight.verdict import Assessment

SCHEMA_VERSION = "0.1"


def _iso(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, tz=UTC).isoformat(timespec="seconds")


def to_json_dict(
    result: CheckResult, *, max_findings: int | None = None, offset: int = 0
) -> dict[str, Any]:
    findings = result.findings[offset:]
    truncated = max_findings is not None and len(findings) > max_findings
    if max_findings is not None:
        findings = findings[:max_findings]
    base = result.root
    reported = {f.fingerprint for f in result.findings}
    return {
        "schema_version": SCHEMA_VERSION,
        "tool": {"name": "paper-preflight", "version": result.tool_version},
        "run": {
            "complete": result.complete,
            "started_at": _iso(result.started_at),
            "finished_at": _iso(result.finished_at),
            "build_data": result.used_build_data,
            "notes": result.notes,
        },
        "project": {
            "root": base.as_posix(),
            "main": result.main.relative_to(base).as_posix() if result.main else None,
            "bib_files": [_rel(b.path, base) for b in result.bib_files],
            "entries": result.entries,
            "cited_keys": result.cited_keys,
        },
        "summary": {
            "errors": result.count(Severity.ERROR),
            "warnings": result.count(Severity.WARNING),
            "infos": result.count(Severity.INFO),
            "total_findings": len(result.findings),
        },
        "verification": {
            "mode": result.verification,
            "verdicts": result.verdict_counts(),
            "unverified_offline": result.unverified_offline,
        },
        "references": [_reference(a, reported) for a in result.verdicts.values()],
        "findings": [f.to_dict(base) for f in findings],
        "pagination": {
            "offset": offset,
            "returned": len(findings),
            "truncated": truncated,
        },
    }


def _reference(assessment: Assessment, reported: set[str]) -> dict[str, Any]:
    record = assessment.record
    return {
        "key": assessment.key,
        "verdict": assessment.verdict.value,
        "reasons": [r.value for r in assessment.reasons],
        "flags": sorted(assessment.flags),
        "matched": None
        if record is None
        else {
            "source": record.source,
            "id": record.source_id,
            "title": record.title,
            "year": record.year,
            "venue": record.venue,
            "doi": record.doi,
        },
        "findings": [f.fingerprint for f in assessment.findings if f.fingerprint in reported],
    }


def _rel(path: Any, base: Any) -> str:
    try:
        return str(path.relative_to(base).as_posix())
    except ValueError:
        return str(path.as_posix())


def render_json(result: CheckResult, *, max_findings: int | None = None, offset: int = 0) -> str:
    payload = to_json_dict(result, max_findings=max_findings, offset=offset)
    return json.dumps(payload, ensure_ascii=False, indent=2)
