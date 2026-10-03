"""Check the demo paper against the live sources and compare with examples/demo-paper/EXPECTED.md.

Recorded responses cannot notice a source changing under us, or a request it no longer accepts
(#62 sent Crossref a `select` field it rejects, and every Crossref lookup failed). This runs the
real check with an empty cache and compares every "online" row of EXPECTED.md:

    uv run python evals/live_smoke.py

A run with an unavailable source (RUN001) is retried once after a pause; if a source is still
down, the script fails and names it. `.github/workflows/live.yml` runs it weekly and on pull
requests that touch the sources.
"""

from __future__ import annotations

import re
import sys
import tempfile
import time
from pathlib import Path

from paper_preflight.check import CheckResult, VerifyOptions, run_check

DEMO = Path(__file__).resolve().parent.parent / "examples" / "demo-paper"
ROW = re.compile(r"^\| `(?P<key>[^`]+)`[^|]*\|[^|]*\| (?P<expected>[^|]+) \| online \|")
METADATA_RULES = {"REF010", "REF011", "REF012", "REF013", "REF014"}


def expectations() -> list[tuple[str, str]]:
    """(key, expected) for every online row: a rule ID, or "clean" / "no metadata finding"."""
    rows = []
    for line in (DEMO / "EXPECTED.md").read_text(encoding="utf-8").splitlines():
        match = ROW.match(line)
        if match:
            expected = match["expected"].strip()
            rule = re.match(r"(REF\d{3})", expected)
            if rule:
                rows.append((match["key"], rule.group(1)))
            elif "no metadata finding" in expected:
                rows.append((match["key"], "no metadata finding"))
            else:
                rows.append((match["key"], "clean"))
    return rows


def run() -> CheckResult:
    with tempfile.TemporaryDirectory() as tmp:
        return run_check(DEMO, verify=VerifyOptions(cache_path=Path(tmp) / "cache.sqlite3"))


def problems(result: CheckResult) -> list[str]:
    found: dict[str, set[str]] = {}
    for finding in result.findings:
        if finding.key:
            found.setdefault(finding.key, set()).add(finding.rule_id)
    serious = {
        f.key
        for f in result.findings
        if f.key and f.rule_id.startswith("REF") and f.severity.value in {"warning", "error"}
    }
    out = []
    for key, expected in expectations():
        rules = found.get(key, set())
        if expected == "clean" and key in serious:
            out.append(f"{key}: expected no finding, got {sorted(rules)}")
        elif expected == "no metadata finding" and rules & METADATA_RULES:
            out.append(f"{key}: expected no metadata finding, got {sorted(rules)}")
        elif expected.startswith("REF") and expected not in rules:
            out.append(f"{key}: expected {expected}, got {sorted(rules) or 'nothing'}")
    return out


def unavailable(result: CheckResult) -> list[str]:
    run_findings = [f for f in result.findings if f.rule_id == "RUN001"]
    return [f.message.get("en") for f in run_findings]


def main() -> None:
    result = run()
    if unavailable(result):
        print("a source was unavailable; retrying in 60 s:", *unavailable(result), sep="\n  ")
        time.sleep(60)
        result = run()
    failures = [f"source unavailable: {message}" for message in unavailable(result)]
    failures += problems(result)
    verdicts = {key: a.verdict.value for key, a in sorted(result.verdicts.items())}
    print("verdicts:", ", ".join(f"{k}={v}" for k, v in verdicts.items()))
    if failures:
        print("FAILED", *failures, sep="\n  ")
        sys.exit(1)
    print(f"ok: all {len(expectations())} online rows of EXPECTED.md hold against the live sources")


if __name__ == "__main__":
    main()
