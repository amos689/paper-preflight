"""MCP server: paper-preflight as tools for coding agents (plan, appendix E).

    paper-preflight mcp            # stdio; needs the extra: pip install "paper-preflight[mcp]"

Design rules:

* Few, coarse tools. ``preflight_check`` verifies a project; ``preflight_explain`` explains a
  rule. Both are read-only: nothing in the workspace is written. (The local response cache under
  the user cache directory is the only state, exactly as for the CLI.)
* Paths resolve inside the workspace root (the directory the server was started in, or
  ``--root``); anything outside is refused.
* Bounded output. Findings come most severe first, ``max_findings`` at a time; ``next_offset``
  pages through the rest, so an agent never receives a 50k-token report it did not ask for.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from mcp.types import ToolAnnotations

from paper_preflight import __version__
from paper_preflight.check import CheckResult, VerifyOptions, run_check
from paper_preflight.findings import Severity
from paper_preflight.rules import RULES
from paper_preflight.tex.project import ProjectError

INSTRUCTIONS = """\
paper-preflight checks the references of a LaTeX paper against real scholarly records
(Crossref, dblp, arXiv, DataCite, OpenAlex). It never uses an LLM to judge and abstains when
unsure. Run preflight_check before declaring a paper finished or ready to submit; fix every
error, and ask the user about references reported as "cannot determine" instead of guessing.
"""

DOCS_URL = "https://github.com/amos689/paper-preflight"


def _inside(root: Path, path: str) -> Path:
    target = (root / path).resolve()
    if not target.is_relative_to(root):
        raise ToolError(f"'{path}' is outside the workspace root; give a path inside it.")
    if not target.exists():
        raise ToolError(f"'{path}' does not exist in the workspace.")
    return target


def _finding(finding: Any, root: Path, lang: str) -> dict[str, Any]:
    location = finding.location
    return {
        "id": finding.fingerprint,
        "rule": finding.rule_id,
        "severity": finding.severity.value,
        "key": finding.key,
        "field": finding.field,
        "location": f"{location.display(root)}" if location is not None else None,
        "message": finding.message.get(lang),
    }


def _summary(result: CheckResult) -> dict[str, Any]:
    return {
        "errors": result.count(Severity.ERROR),
        "warnings": result.count(Severity.WARNING),
        "infos": result.count(Severity.INFO),
        "complete": result.complete,
        "verification": result.verification,
        "verdicts": result.verdict_counts(),
        "unverified_offline": result.unverified_offline,
    }


def create_server(root: Path, cache_path: Path | None = None) -> FastMCP:
    root = root.resolve()
    server = FastMCP("paper-preflight", instructions=INSTRUCTIONS, version=__version__)

    @server.tool(
        annotations=ToolAnnotations(
            title="Check a paper's references",
            read_only_hint=True,
            idempotent_hint=True,
            open_world_hint=True,
        )
    )
    def preflight_check(
        path: str = ".",
        offline: bool = False,
        max_findings: int = 20,
        offset: int = 0,
        include_info: bool = False,
        lang: Literal["en", "zh"] = "en",
    ) -> dict[str, Any]:
        """Verify every cited reference of a LaTeX project (or a .bib file) against real
        scholarly records, and check citation keys and the bibliography.

        Returns a summary (error/warning counts, one verdict per reference, whether the run was
        complete) and the findings, most severe first, `max_findings` at a time; call again
        with `offset=next_offset` for more. `complete: false` means a source was unavailable,
        so the paper cannot be declared clean yet. `offline: true` answers from the local cache
        only. The first run of a paper may take a minute; later runs are served from the cache.
        """
        target = _inside(root, path)
        try:
            result = run_check(target, verify=VerifyOptions(offline=offline, cache_path=cache_path))
        except ProjectError as error:
            raise ToolError(str(error)) from error
        findings = [f for f in result.findings if include_info or f.severity is not Severity.INFO]
        page = findings[offset : offset + max(1, max_findings)]
        next_offset = offset + len(page)
        return {
            "summary": _summary(result),
            "findings": [_finding(f, root, lang) for f in page],
            "returned": len(page),
            "total": len(findings),
            "next_offset": next_offset if next_offset < len(findings) else None,
        }

    @server.tool(
        annotations=ToolAnnotations(
            title="Explain a rule",
            read_only_hint=True,
            idempotent_hint=True,
            open_world_hint=False,
        )
    )
    def preflight_explain(rule_id: str) -> dict[str, Any]:
        """Explain a paper-preflight rule (for example REF003 or CIT001): what it detects, its
        default severity, the message template and whether a fix can be applied safely."""
        rule = RULES.get(rule_id.strip().upper())
        if rule is None:
            raise ToolError(f"Unknown rule '{rule_id}'. Known rules: {', '.join(sorted(RULES))}.")
        return {
            "rule": rule.id,
            "name": rule.name,
            "severity": rule.severity.value,
            "summary": {"en": rule.summary.en, "zh": rule.summary.zh},
            "message_template": {"en": rule.template.en, "zh": rule.template.zh},
            "fix": rule.fix.value if rule.fix else None,
            "docs": DOCS_URL,
        }

    return server
