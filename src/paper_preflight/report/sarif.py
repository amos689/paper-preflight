"""SARIF 2.1.0 output for GitHub code scanning, reviewdog and other CI tools (ADR-0007).

Artifact URIs are relative to ``uri_base`` (default: the current working directory, which is the
repository root when running in CI) and percent-encoded, so non-ASCII paths stay valid URIs.
Deduplication across runs uses ``partialFingerprints`` derived from rule + BibTeX key + field,
which survive reordering of entries (line hashes would not).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote

from paper_preflight import __version__
from paper_preflight.check import CheckResult
from paper_preflight.findings import Finding, Location, Severity
from paper_preflight.rules import RULES

SARIF_SCHEMA = "https://json.schemastore.org/sarif-2.1.0.json"
INFORMATION_URI = "https://github.com/paper-preflight/paper-preflight"
_LEVEL = {Severity.ERROR: "error", Severity.WARNING: "warning", Severity.INFO: "note"}


def _uri(path: Path, base: Path) -> tuple[str, bool]:
    """Return (uri, relative_to_base)."""
    try:
        relative = path.resolve().relative_to(base.resolve())
        return quote(relative.as_posix(), safe="/"), True
    except ValueError:
        return path.resolve().as_uri(), False


def _physical(location: Location, base: Path) -> dict[str, Any]:
    uri, relative = _uri(location.file, base)
    artifact: dict[str, Any] = {"uri": uri}
    if relative:
        artifact["uriBaseId"] = "SRCROOT"
    return {
        "artifactLocation": artifact,
        "region": {"startLine": location.line, "startColumn": location.column},
    }


def _result(finding: Finding, rule_index: dict[str, int], base: Path) -> dict[str, Any]:
    result: dict[str, Any] = {
        "ruleId": finding.rule_id,
        "ruleIndex": rule_index[finding.rule_id],
        "level": _LEVEL[finding.severity],
        "message": {"text": finding.message.en},
        "partialFingerprints": {"paperPreflight/v1": finding.fingerprint},
        "properties": {"messageZh": finding.message.zh},
    }
    if finding.location is not None:
        result["locations"] = [{"physicalLocation": _physical(finding.location, base)}]
    if finding.related:
        result["relatedLocations"] = [
            {"id": i, "physicalLocation": _physical(loc, base)}
            for i, loc in enumerate(finding.related, start=1)
        ]
    if finding.key:
        result["properties"]["bibKey"] = finding.key
    if finding.field:
        result["properties"]["bibField"] = finding.field
    return result


def to_sarif_dict(result: CheckResult, uri_base: Path | None = None) -> dict[str, Any]:
    base = (uri_base or Path.cwd()).resolve()
    used = sorted({f.rule_id for f in result.findings})
    rule_index = {rule_id: i for i, rule_id in enumerate(used)}
    rules = []
    for rule_id in used:
        rule = RULES[rule_id]
        rules.append(
            {
                "id": rule.id,
                "name": rule.name,
                "shortDescription": {"text": rule.summary.en},
                "helpUri": f"{INFORMATION_URI}/blob/main/docs/rules/{rule.id}.md",
                "defaultConfiguration": {"level": _LEVEL[rule.severity]},
                "properties": {"tags": ["references", rule.id[:3].lower()]},
            }
        )
    finished = datetime.fromtimestamp(result.finished_at or 0, tz=UTC)
    return {
        "$schema": SARIF_SCHEMA,
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "paper-preflight",
                        "version": __version__,
                        "informationUri": INFORMATION_URI,
                        "rules": rules,
                    }
                },
                "columnKind": "unicodeCodePoints",
                "originalUriBaseIds": {"SRCROOT": {"uri": base.as_uri().rstrip("/") + "/"}},
                "invocations": [
                    {
                        "executionSuccessful": True,
                        "endTimeUtc": finished.isoformat(timespec="seconds").replace("+00:00", "Z"),
                        "properties": {"complete": result.complete},
                    }
                ],
                "results": [_result(f, rule_index, base) for f in result.findings],
            }
        ],
    }


def render_sarif(result: CheckResult, uri_base: Path | None = None) -> str:
    return json.dumps(to_sarif_dict(result, uri_base), ensure_ascii=False, indent=2)
