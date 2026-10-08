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

import asyncio
import tempfile
from pathlib import Path
from typing import Annotated, Any, Literal

from fastmcp import Context, FastMCP
from fastmcp.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import Field

from paper_preflight import __version__
from paper_preflight.check import CheckResult, VerifyOptions, run_check
from paper_preflight.config import Config, ConfigError, find_config, load_config
from paper_preflight.fetch import identifier_query, lookup, title_query, to_dict
from paper_preflight.findings import Severity
from paper_preflight.fixes import edits, plan
from paper_preflight.rules import RULES, describe
from paper_preflight.tex.project import ProjectError

# Parameter descriptions shared by several tools.
PATH = Field(
    description="A LaTeX project folder or .tex file, a Markdown, Quarto or Typst manuscript "
    "(.md, .qmd, .typ), a Word manuscript (.docx), or a reference list (.bib, .bbl, .json, .ris, "
    ".yml, .txt, .pdf), relative to the workspace root (default: the root itself)."
)
OFFLINE = Field(
    description="true: answer only from the local cache and never touch the network (references "
    "not cached yet come back as unverified)."
)

MAX_PASSAGES = 20  # preflight_cited_passages returns at most this many passages per claim
PASSAGE_CHARS = 1500  # and cuts each one to this length

INSTRUCTIONS = """\
paper-preflight checks the references of a LaTeX paper against real scholarly records
(Crossref, dblp, arXiv, DataCite, OpenAlex). It never uses an LLM to judge and abstains when
unsure. Run preflight_check before declaring a paper finished or ready to submit; fix every
error, and ask the user about references reported as "cannot determine" instead of guessing.
Never write a BibTeX entry from memory: get it with preflight_bib_lookup.
To see whether a cited work supports the sentence citing it, read preflight_cited_passages and
judge conservatively: confirm only with a quoted passage, and never call a citation wrong.
"""


def _settings(target: Path) -> Config:
    """The project's settings, found from the checked path up (paper-preflight.toml or
    pyproject.toml); a mistake in them is the agent's to report, as the CLI's is."""
    found = find_config(target)
    if found is None:
        return Config()
    try:
        return load_config(found)
    except ConfigError as error:
        raise ToolError(str(error)) from error


def _inside(root: Path, path: str) -> Path:
    target = (root / path).resolve()
    if not target.is_relative_to(root):
        raise ToolError(f"'{path}' is outside the workspace root; give a path inside it.")
    if not target.exists():
        raise ToolError(f"'{path}' does not exist in the workspace.")
    return target


def _relative(root: Path, path: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


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


_STAGE_MESSAGES = {"title": "References searched by title:", "rescue": "Asked Semantic Scholar:"}


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
    # cited works' text (arXiv sources, PDFs) for preflight_cited_passages, next to the cache
    support_folder = (cache_path.parent if cache_path else Path(tempfile.gettempdir())) / "support"
    server = FastMCP("paper-preflight", instructions=INSTRUCTIONS, version=__version__)

    @server.tool(
        annotations=ToolAnnotations(
            title="Check a paper's references",
            read_only_hint=True,
            idempotent_hint=True,
            open_world_hint=True,
        )
    )
    async def preflight_check(
        ctx: Context,
        path: Annotated[str, PATH] = ".",
        offline: Annotated[bool, OFFLINE] = False,
        max_findings: Annotated[
            int, Field(description="How many findings to return in this call (at least 1).")
        ] = 20,
        offset: Annotated[
            int,
            Field(description="Where to start in the findings: 0 first, then `next_offset`."),
        ] = 0,
        include_info: Annotated[
            bool, Field(description="Also return info findings (suggestions), not only errors.")
        ] = False,
        lang: Annotated[
            Literal["en", "zh"], Field(description="Language of the messages: English or Chinese.")
        ] = "en",
    ) -> dict[str, Any]:
        """Verify every cited reference of a LaTeX project (or a .bib file) against real
        scholarly records, and check citation keys and the bibliography.

        Returns a summary (error/warning counts, one verdict per reference, whether the run was
        complete) and the findings, most severe first, `max_findings` at a time; call again
        with `offset=next_offset` for more. `complete: false` means a source was unavailable,
        so the paper cannot be declared clean yet. `offline: true` answers from the local cache
        only. The first run of a paper may take a minute or two (progress is reported while the
        references are searched); later runs are served from the cache.

        Use this first, on the whole paper. Use `preflight_explain` to understand a finding,
        `preflight_bib_fix` to get the corrections as a diff, and `preflight_bib_lookup` to get a
        single entry.
        """
        target = _inside(root, path)
        loop = asyncio.get_running_loop()

        def report(stage: str, done: int, total: int) -> None:
            message = f"{_STAGE_MESSAGES.get(stage, stage)} {done}/{total}"
            asyncio.run_coroutine_threadsafe(ctx.report_progress(done, total, message), loop)

        settings = _settings(target)
        verify = VerifyOptions(
            offline=offline, cache_path=cache_path, progress=report,
            disabled_sources=settings.disable_sources,
        )  # fmt: skip
        try:
            result = await asyncio.to_thread(run_check, target, verify=verify, config=settings)
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
    def preflight_explain(
        rule_id: Annotated[
            str,
            Field(description="A rule ID as it appears in a finding, such as REF003 or CIT001."),
        ],
    ) -> dict[str, Any]:
        """Explain a paper-preflight rule (for example REF003 or CIT001): what it detects, its
        default severity, the message template and whether a fix can be applied safely. Use it
        when a finding from `preflight_check` is unclear; it does not look at the paper."""
        described = describe(rule_id)
        if described is None:
            raise ToolError(f"Unknown rule '{rule_id}'. Known rules: {', '.join(sorted(RULES))}.")
        return described

    @server.tool(
        annotations=ToolAnnotations(
            title="Get verified BibTeX",
            read_only_hint=True,
            idempotent_hint=True,
            open_world_hint=True,
        )
    )
    def preflight_bib_lookup(
        identifier: Annotated[
            str | None,
            Field(
                description="A DOI (10.xxxx/...) or an arXiv ID (2401.01234). Give this or `title`."
            ),
        ] = None,
        title: Annotated[
            str | None, Field(description="The work's title, when there is no identifier.")
        ] = None,
        author: Annotated[
            str | None, Field(description="An author's family name, to narrow a title search.")
        ] = None,
        year: Annotated[
            int | None, Field(description="The publication year, to narrow a title search.")
        ] = None,
        prefer: Annotated[
            Literal["published", "preprint"],
            Field(description="For a preprint that has been published: which version to return."),
        ] = "published",
        offline: Annotated[bool, OFFLINE] = False,
    ) -> dict[str, Any]:
        """Get a BibTeX entry for a DOI, an arXiv ID or a title, built from the registry record
        instead of written from memory. Give `identifier`, or `title` (with `author` and `year`
        when you know them).

        `status` is "found" (use `bibtex` as is), "ambiguous" (several works match: pick from
        `candidates` with the user, or retry with author/year), "not_found" (ask the user for
        the source; do not invent one) or "unavailable" (a source did not answer; retry later).
        A published preprint comes back as its published version with the eprint kept;
        `status_flags` lists notices such as "retracted".

        Use it when adding or replacing one entry; to check a whole bibliography use
        `preflight_check`.
        """
        if (identifier is None) == (title is None):
            raise ToolError("Give either `identifier` or `title`.")
        if identifier is not None:
            query = identifier_query(identifier)
        else:
            query = title_query(title or "", author, year)
        if query is None:
            raise ToolError(f"'{identifier}' is not a DOI or an arXiv ID.")
        prefer_published = prefer == "published"
        result = asyncio.run(
            lookup(query, cache_path=cache_path, offline=offline, prefer_published=prefer_published)
        )
        return to_dict(result)

    @server.tool(
        annotations=ToolAnnotations(
            title="Propose fixes for a bibliography",
            read_only_hint=True,
            idempotent_hint=True,
            open_world_hint=True,
        )
    )
    def preflight_bib_fix(
        path: Annotated[str, PATH] = ".",
        level: Annotated[
            Literal["safe", "unsafe"],
            Field(
                description="safe: only broken identifiers and missing DOIs; unsafe: also "
                "authors, title, year and venue from the record."
            ),
        ] = "safe",
        keys: Annotated[
            list[str] | None,
            Field(description="Only these citation keys (default: every key with a fix)."),
        ] = None,
        offline: Annotated[bool, OFFLINE] = False,
    ) -> dict[str, Any]:
        """Propose edits to the .bib files, taken from the verified records, as a unified diff.
        Nothing is written: apply the diff with your own editing tools.

        `level="safe"` only fixes identifiers written so that links break and adds DOIs the
        registry has; `level="unsafe"` also rewrites authors, title, year and venue from the
        record, removes identifiers that point to another work and cites a preprint as its
        published version (keeping the eprint). Show unsafe diffs to the user
        before applying them. References nobody could find are never "fixed".

        Use it after `preflight_check` has reported errors or warnings in the bibliography.
        """
        target = _inside(root, path)
        try:
            result = run_check(target, verify=VerifyOptions(offline=offline, cache_path=cache_path))
        except ProjectError as error:
            raise ToolError(str(error)) from error
        fixes = plan(
            result.findings, result.bib_files, level=level, keys=set(keys) if keys else None
        )
        file_edits = edits(result.bib_files, fixes)
        return {
            "fixes": [
                {
                    "file": _relative(root, f.file),
                    "key": f.key,
                    "rule": f.rule,
                    "field": f.field,
                    "action": f.action,
                    "old": f.old,
                    "new": f.new,
                    "level": f.level,
                }
                for f in fixes
            ],
            "diff": "".join(edit.diff(root) for edit in file_edits),
        }

    @server.tool(
        annotations=ToolAnnotations(
            title="Find the passages a citation rests on",
            read_only_hint=True,
            idempotent_hint=True,
            open_world_hint=True,
        )
    )
    async def preflight_cited_passages(
        key: Annotated[str, Field(description="The citation key whose citing sentences to trace.")],
        path: Annotated[str, PATH] = ".",
        max_passages: Annotated[
            int,
            Field(description="Passages to return per citing sentence, best first (1 to 20)."),
        ] = 8,
        offline: Annotated[bool, OFFLINE] = False,
    ) -> dict[str, Any]:
        """For each sentence of the paper that cites `key`: the claim it makes and the passages
        of the cited work ranked best for that claim, for you to judge whether the work supports
        it. The first call downloads the work's text (its arXiv source, an open-access full text
        or PDF, or else its abstract) into the local cache.

        Judge each claim conservatively. Say "confirmed" only when a passage states it (quote
        the passage word for word) or, for a citation set right after a name such as
        "Adam \\cite{...}", when `name_in_title` is true. Otherwise say "could not confirm",
        with the reason: no text, only the abstract, or no passage says it. Never call a
        citation wrong or invented on this evidence: the text may say it in other words, or be
        only an abstract. `evidence.level` is "full_text", "abstract" or "none".

        Use it only after `preflight_check` has verified that the work exists; it answers
        whether a real work supports a sentence, not whether the reference is correct.
        """
        from paper_preflight.support.judge import name_in_title
        from paper_preflight.support.retrieve import rank
        from paper_preflight.support.run import gather

        target = _inside(root, path)
        try:
            found = await asyncio.to_thread(
                gather, target, cache_path=cache_path, folder=support_folder, offline=offline,
                keys={key},
            )  # fmt: skip
        except ProjectError as error:
            raise ToolError(str(error)) from error
        if key not in found.check.verdicts:
            raise ToolError(f"'{key}' is not a cited key of this paper.")
        if key in found.skipped:
            return {"key": key, "skipped": found.skipped[key], "citations": []}
        evidence = found.evidence[key]
        title = found.titles.get(key, "")
        top = max(1, min(max_passages, MAX_PASSAGES))
        return {
            "key": key,
            "title": title,
            "evidence": {
                "level": evidence.level,
                "source": evidence.source,
                "notes": list(evidence.notes),
            },
            "citations": [
                {
                    "file": _relative(root, sentence.file),
                    "line": sentence.line,
                    "sentence": sentence.sentence,
                    "claim": sentence.claim,
                    "name": sentence.name or None,
                    "name_in_title": name_in_title(sentence.name, title),
                    "passages": [
                        {"index": hit.index, "text": _clip(evidence.passages[hit.index])}
                        for hit in rank(sentence.claim, evidence.passages, top=top)
                    ],
                }
                for sentence in found.sentences
                if sentence.key == key
            ],
        }

    return server


def _clip(text: str, limit: int = PASSAGE_CHARS) -> str:
    """A passage cut at a word boundary to ``limit`` characters, marked with an ellipsis."""
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(" ", 1)[0] + " …"
