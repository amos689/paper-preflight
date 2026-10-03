"""Command-line interface for paper-preflight."""

from __future__ import annotations

import contextlib
import io
import locale
import os
import platform
import sys
from enum import StrEnum
from pathlib import Path
from typing import Annotated

import typer
from platformdirs import user_cache_dir
from rich.console import Console

from paper_preflight import __version__
from paper_preflight.findings import Severity

# Credentials are read from the environment only and are never printed.
CREDENTIAL_ENV_VARS = ("PAPER_PREFLIGHT_EMAIL", "OPENALEX_API_KEY", "S2_API_KEY", "NCBI_API_KEY")

# Exit codes (docs/adr/0002-verdicts-and-abstention.md).
EXIT_OK = 0
EXIT_FINDINGS = 1
EXIT_INCOMPLETE = 2
EXIT_USAGE = 3
EXIT_INTERNAL = 4

app = typer.Typer(
    name="paper-preflight",
    help="Pre-submission integrity gate for LaTeX papers.",
    no_args_is_help=True,
    add_completion=False,
    pretty_exceptions_enable=False,
)


class OutputFormat(StrEnum):
    TEXT = "text"
    JSON = "json"
    SARIF = "sarif"


class FailOn(StrEnum):
    ERROR = "error"
    WARNING = "warning"
    NEVER = "never"


class Lang(StrEnum):
    AUTO = "auto"
    EN = "en"
    ZH = "zh"


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"paper-preflight {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: Annotated[
        bool,
        typer.Option(
            "--version",
            callback=_version_callback,
            is_eager=True,
            help="Show the version and exit.",
        ),
    ] = False,
) -> None:
    """Verify every reference in a LaTeX paper against real scholarly records."""


def cache_dir() -> str:
    """Return the cache directory, honouring PAPER_PREFLIGHT_CACHE_DIR."""
    return os.environ.get("PAPER_PREFLIGHT_CACHE_DIR") or user_cache_dir(
        "paper-preflight", appauthor=False
    )


def resolve_lang(lang: Lang) -> str:
    if lang is not Lang.AUTO:
        return str(lang.value)
    configured = os.environ.get("PAPER_PREFLIGHT_LANG", "")
    if configured:
        return "zh" if configured.lower().startswith("zh") else "en"
    names = [locale.getlocale()[0] or "", os.environ.get("LANG", "")]
    return "zh" if any(n.lower().startswith(("zh", "chinese")) for n in names) else "en"


def _progress_message(language: str, offline: bool) -> str:
    if language == "zh":
        return "正在用本地缓存核查参考文献…" if offline else "正在向学术数据源核查参考文献…"
    if offline:
        return "Verifying references from the local cache…"
    return "Verifying references against Crossref, dblp, arXiv, DataCite and OpenAlex…"


def _safe_stdout() -> None:
    """Never crash on characters the console encoding cannot represent."""
    stream = sys.stdout
    if isinstance(stream, io.TextIOWrapper) and stream.errors == "strict":
        stream.reconfigure(errors="replace")


@app.command()
def check(
    path: Annotated[
        Path, typer.Argument(help="Project directory, main .tex file, or a .bib file.")
    ] = Path("."),
    main_file: Annotated[
        Path | None, typer.Option("--main", help="Main .tex file if it cannot be detected.")
    ] = None,
    bib: Annotated[
        list[Path] | None, typer.Option("--bib", help="Additional .bib file(s) to include.")
    ] = None,
    output_format: Annotated[
        OutputFormat, typer.Option("--format", "-f", help="Output format.")
    ] = OutputFormat.TEXT,
    output: Annotated[
        Path | None, typer.Option("--output", "-o", help="Write the report to a file.")
    ] = None,
    fail_on: Annotated[
        FailOn, typer.Option("--fail-on", help="Lowest severity that makes the exit code 1.")
    ] = FailOn.ERROR,
    lang: Annotated[Lang, typer.Option("--lang", help="Message language.")] = Lang.AUTO,
    max_findings: Annotated[
        int | None, typer.Option("--max-findings", help="Limit findings in JSON output.")
    ] = None,
    cite_command: Annotated[
        list[str] | None,
        typer.Option("--cite-command", help="Extra citation macro, e.g. --cite-command mycite."),
    ] = None,
    hide_info: Annotated[bool, typer.Option("--hide-info", help="Hide info findings.")] = False,
    offline: Annotated[
        bool,
        typer.Option(
            "--offline",
            help="Do not use the network: verify references from cached answers only.",
        ),
    ] = False,
) -> None:
    """Check a LaTeX project (or a .bib file) and report problems with its references."""
    from paper_preflight.check import VerifyOptions, run_check
    from paper_preflight.report.jsonout import render_json
    from paper_preflight.report.sarif import render_sarif
    from paper_preflight.report.text import render_text
    from paper_preflight.tex.project import ProjectError

    _safe_stdout()
    language = resolve_lang(lang)
    verify = VerifyOptions(offline=offline, cache_path=Path(cache_dir()) / "cache.sqlite3")
    progress = Console(stderr=True)
    status: contextlib.AbstractContextManager[object] = (
        progress.status(_progress_message(language, offline))
        if progress.is_terminal  # never animate into logs or CI output
        else contextlib.nullcontext()
    )
    try:
        with status:
            result = run_check(
                path, main=main_file, extra_bib=bib, cite_commands=cite_command, verify=verify
            )
    except ProjectError as exc:
        typer.echo(f"paper-preflight: {exc}", err=True)
        raise typer.Exit(EXIT_USAGE) from exc
    except Exception as exc:  # report, never dump a traceback at the user by default
        typer.echo(f"paper-preflight: internal error: {exc!r}", err=True)
        if os.environ.get("PAPER_PREFLIGHT_DEBUG"):
            raise
        raise typer.Exit(EXIT_INTERNAL) from exc

    if output_format in (OutputFormat.JSON, OutputFormat.SARIF):
        if output_format is OutputFormat.JSON:
            text = render_json(result, max_findings=max_findings)
        else:
            text = render_sarif(result)
        if output:
            output.write_text(text + "\n", encoding="utf-8")
        else:
            typer.echo(text)
    else:
        if output:
            with output.open("w", encoding="utf-8") as handle:
                render_text(result, Console(file=handle, width=100), language, not hide_info)
        else:
            render_text(result, Console(highlight=False), language, not hide_info)

    threshold = None if fail_on is FailOn.NEVER else Severity(fail_on.value)
    if result.has_blocking(threshold):
        raise typer.Exit(EXIT_FINDINGS)
    if not result.complete:
        raise typer.Exit(EXIT_INCOMPLETE)


@app.command()
def explain(
    rule_id: Annotated[
        str | None, typer.Argument(help="Rule ID such as REF003; omit it to list every rule.")
    ] = None,
    lang: Annotated[Lang, typer.Option("--lang", help="Message language.")] = Lang.AUTO,
) -> None:
    """Explain a rule: what it detects, its severity, its message and whether a fix is safe."""
    from paper_preflight.rules import RULES, describe

    _safe_stdout()
    language = resolve_lang(lang)
    if rule_id is None:
        for rule in sorted(RULES.values(), key=lambda r: r.id):
            typer.echo(f"{rule.id}  {rule.severity.value:<8} {rule.summary.get(language)}")
        return
    described = describe(rule_id)
    if described is None:
        typer.echo(f"paper-preflight: unknown rule '{rule_id}'", err=True)
        raise typer.Exit(EXIT_USAGE)
    zh = language == "zh"
    fix = described["fix"] or ("无" if zh else "none")
    labels = ("严重度", "消息", "修复") if zh else ("severity", "message", "fix")
    typer.echo(f"{described['rule']}  {described['name']}")
    typer.echo(described["summary"][language])
    typer.echo(f"{labels[0]}: {described['severity']}")
    typer.echo(f"{labels[1]}: {described['message_template'][language]}")
    typer.echo(f"{labels[2]}: {fix}")


@app.command()
def doctor(
    offline: Annotated[
        bool, typer.Option("--offline", help="Skip the connectivity check of each source.")
    ] = False,
) -> None:
    """Show the environment and whether each source answers (never prints secrets)."""
    rows = [
        ("paper-preflight", __version__),
        ("python", f"{sys.version.split()[0]} ({platform.python_implementation()})"),
        ("platform", platform.platform()),
        ("cache dir", cache_dir()),
    ]
    rows += [(name, "set" if os.environ.get(name) else "not set") for name in CREDENTIAL_ENV_VARS]
    width = max(len(label) for label, _ in rows)
    for label, value in rows:
        typer.echo(f"{label:<{width}}  {value}")
    if offline:
        return

    import asyncio

    from paper_preflight.connectivity import probe_sources
    from paper_preflight.verdict import source_name

    _safe_stdout()
    typer.echo("\nsources (one request each)")
    for probe in asyncio.run(probe_sources()):
        took = f"{probe.seconds:5.2f} s" if probe.seconds is not None else " " * 7
        typer.echo(f"  {source_name(probe.source):<17} {probe.status:<12} {took}  {probe.detail}")


@app.command()
def mcp(
    root: Annotated[
        Path, typer.Option("--root", help="Workspace root; the tools never read outside it.")
    ] = Path("."),
) -> None:
    """Run the MCP server on stdio for coding agents (needs the "mcp" extra)."""
    try:
        from paper_preflight.mcp_server import create_server
    except ImportError as exc:
        typer.echo(
            'paper-preflight: the MCP server needs the "mcp" extra: '
            'pip install "paper-preflight[mcp]"',
            err=True,
        )
        raise typer.Exit(EXIT_USAGE) from exc
    if not root.is_dir():
        typer.echo(f"paper-preflight: --root {root} is not a directory", err=True)
        raise typer.Exit(EXIT_USAGE)
    server = create_server(root, cache_path=Path(cache_dir()) / "cache.sqlite3")
    server.run(show_banner=False)  # stdout carries the protocol: nothing else may be printed


bib_app = typer.Typer(help="BibTeX helpers.", no_args_is_help=True)
app.add_typer(bib_app, name="bib")


@bib_app.command("fetch")
def bib_fetch(
    identifier: Annotated[
        str | None, typer.Argument(help="A DOI or arXiv ID (URLs and doi:/arXiv: prefixes work).")
    ] = None,
    title: Annotated[str | None, typer.Option("--title", help="Search by title instead.")] = None,
    author: Annotated[
        str | None, typer.Option("--author", help="With --title: author(s), BibTeX style.")
    ] = None,
    year: Annotated[int | None, typer.Option("--year", help="With --title: the year.")] = None,
    prefer: Annotated[
        str,
        typer.Option("--prefer", help="'published' (default) or 'preprint' for arXiv papers."),
    ] = "published",
    key: Annotated[str | None, typer.Option("--key", help="Citation key to use.")] = None,
    output_format: Annotated[
        OutputFormat, typer.Option("--format", "-f", help="'text' (BibTeX) or 'json'.")
    ] = OutputFormat.TEXT,
    offline: Annotated[
        bool, typer.Option("--offline", help="Answer from the local cache only.")
    ] = False,
) -> None:
    """Print a verified BibTeX entry for an identifier or a title. Never written from memory."""
    import asyncio
    import json

    from paper_preflight.bibtex import SOURCE_NAMES
    from paper_preflight.fetch import identifier_query, lookup, title_query, to_dict

    _safe_stdout()
    if (identifier is None) == (title is None) or prefer not in {"published", "preprint"}:
        typer.echo("paper-preflight: give either an identifier or --title", err=True)
        raise typer.Exit(EXIT_USAGE)
    query = identifier_query(identifier) if identifier else title_query(title or "", author, year)
    if query is None:
        typer.echo(f"paper-preflight: '{identifier}' is not a DOI or an arXiv ID", err=True)
        raise typer.Exit(EXIT_USAGE)

    cache_path = Path(cache_dir()) / "cache.sqlite3"
    prefer_published = prefer == "published"
    result = asyncio.run(
        lookup(query, cache_path=cache_path, offline=offline, prefer_published=prefer_published)
    )
    payload = to_dict(result, key=key)
    bibtex = payload["bibtex"]

    if output_format is OutputFormat.JSON:
        typer.echo(json.dumps(payload, ensure_ascii=False, indent=2))
    elif result.record is not None and bibtex is not None:
        typer.echo(bibtex, nl=False)
        if result.record.status:  # retracted, withdrawn, expression of concern, correction
            notices = ", ".join(sorted(result.record.status)).replace("_", " ")
            typer.echo(f"warning: this work is marked {notices} by its registry", err=True)
        if result.preprint is not None:
            typer.echo(
                f"note: arXiv {result.preprint.source_id} was published "
                f"({result.record.venue or 'venue unknown'}, {result.record.year}); this is the "
                "published version with the eprint kept. Use --prefer preprint for the preprint.",
                err=True,
            )
    elif result.status == "ambiguous":
        typer.echo("paper-preflight: several works match; give --author or --year:", err=True)
        for c in result.candidates:
            source = SOURCE_NAMES.get(c.source, c.source)
            typer.echo(f"  {c.title} ({c.year or 'n.d.'}) [{source} {c.source_id}]", err=True)
    else:
        why = result.detail or (
            "a source was unavailable: "
            + ", ".join(f"{s} ({r})" for s, r in result.unavailable.items())
            if result.status == "unavailable"
            else "no source has it"
        )
        typer.echo(f"paper-preflight: not found ({why})", err=True)

    if result.status == "found":
        return
    raise typer.Exit(EXIT_INCOMPLETE if result.status == "unavailable" else EXIT_FINDINGS)
