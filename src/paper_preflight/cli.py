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
def doctor() -> None:
    """Show environment information useful for bug reports (never prints secrets)."""
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
