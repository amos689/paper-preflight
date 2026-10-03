"""Command-line interface for paper-preflight."""

from __future__ import annotations

import os
import platform
import sys
from typing import Annotated

import typer
from platformdirs import user_cache_dir

from paper_preflight import __version__

# Credentials are read from the environment only and are never printed.
CREDENTIAL_ENV_VARS = ("PAPER_PREFLIGHT_EMAIL", "OPENALEX_API_KEY", "S2_API_KEY", "NCBI_API_KEY")

app = typer.Typer(
    name="paper-preflight",
    help="Pre-submission integrity gate for LaTeX papers.",
    no_args_is_help=True,
    add_completion=False,
)


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
