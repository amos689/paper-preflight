"""What the Hugging Face Space runs: one check of what a visitor gave, in a folder deleted after.

A visitor gives an arXiv ID, a file (.bib, .bbl, .tex, .txt, .pdf, or a .zip of a LaTeX project
such as Overleaf's "Download source"), or pasted references. :func:`check` prepares the input in
a temporary folder, runs the same check as ``paper-preflight check``, and returns the report as
text, a table, JSON, SARIF and the ``bib fix --level unsafe`` diff. Nothing is kept but the
answers of the scholarly sources, in the cache.

This module does not import Gradio, so it can be tested without it.
"""

from __future__ import annotations

import io
import os
import re
import shutil
import tempfile
import zipfile
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

from rich.console import Console

from paper_preflight import arxiv_source
from paper_preflight.check import CheckResult, VerifyOptions, run_check
from paper_preflight.fixes import edits, plan
from paper_preflight.report.jsonout import render_json
from paper_preflight.report.sarif import render_sarif
from paper_preflight.report.text import render_text
from paper_preflight.tex.project import ProjectError, find_main_file

MAX_UPLOAD_BYTES = 20_000_000
MAX_ZIP_FILES = 2_000
MAX_UNZIPPED_BYTES = 80_000_000
MAX_ENTRIES = 300
MAX_PASTED_CHARS = 200_000
FILE_SUFFIXES = {".bib", ".bbl", ".txt", ".pdf", ".tex", ".zip"}
CACHE = Path(os.environ.get("PAPER_PREFLIGHT_CACHE_DIR", tempfile.gettempdir())) / "space.sqlite3"
# "arXiv:1706.03762", "https://arxiv.org/abs/1706.03762v2", "arxiv.org/pdf/1706.03762.pdf"
_ARXIV_PREFIX = re.compile(r"^(?:arxiv:|(?:https?://)?(?:www\.)?arxiv\.org/(?:abs|pdf)/)", re.I)


class InputError(ValueError):
    """The input cannot be checked; the message says why, for the visitor."""


@dataclass
class Outcome:
    summary: str
    text: str
    rows: list[list[str]] = field(default_factory=list)  # severity, rule, where, message
    json: str = ""
    sarif: str = ""
    diff: str = ""


def _safe_extract(archive: Path, folder: Path) -> None:
    """Unzip without leaving the folder, following links or filling the disk."""
    try:
        with zipfile.ZipFile(archive) as zipped:
            members = [m for m in zipped.infolist() if not m.is_dir()]
            if len(members) > MAX_ZIP_FILES:
                raise InputError(f"The archive has more than {MAX_ZIP_FILES} files.")
            if sum(m.file_size for m in members) > MAX_UNZIPPED_BYTES:
                raise InputError("The archive is larger than 80 MB unpacked.")
            for member in members:
                name = PurePosixPath(member.filename.replace("\\", "/"))
                if name.is_absolute() or ".." in name.parts or (member.external_attr >> 28) == 0xA:
                    raise InputError(f"The archive holds an unsafe path: {member.filename}")
                target = folder.joinpath(*name.parts)
                target.parent.mkdir(parents=True, exist_ok=True)
                with zipped.open(member) as source, target.open("wb") as out:
                    shutil.copyfileobj(source, out)
    except zipfile.BadZipFile as exc:
        raise InputError("The file is not a valid .zip archive.") from exc


def _project_target(folder: Path) -> Path:
    """The main .tex file of an unpacked project (in the top folder, or the shallowest folder
    that has one: archives often wrap the project in a folder), else its only .bib or .bbl."""
    folders = sorted({p.parent for p in folder.rglob("*.tex")}, key=lambda p: len(p.parts))
    for candidate in [folder, *folders]:
        try:
            return find_main_file(candidate)
        except ProjectError:
            continue
    for suffix in (".bib", ".bbl"):
        found = sorted(folder.rglob(f"*{suffix}"))
        if len(found) == 1:
            return found[0]
    raise InputError(
        "No main .tex file (with \\documentclass and \\begin{document}) or single .bib file "
        "was found in the archive."
    )


def prepare(folder: Path, *, arxiv: str = "", upload: Path | None = None, pasted: str = "") -> Path:
    """The path to check, set up inside ``folder``."""
    if arxiv.strip():
        given = _ARXIV_PREFIX.sub("", arxiv.strip()).removesuffix(".pdf")
        try:
            identifier = arxiv_source.arxiv_target(f"arxiv:{given}")
            assert identifier is not None
            return arxiv_source.fetch(identifier, folder / identifier.replace("/", "_"))
        except arxiv_source.ArxivSourceError as exc:
            raise InputError(f"{exc} (an arXiv ID looks like 1706.03762)") from exc
    if upload is not None:
        suffix = upload.suffix.lower()
        if suffix not in FILE_SUFFIXES:
            raise InputError(
                f"'{suffix}' files are not supported: give one of {sorted(FILE_SUFFIXES)}."
            )
        if upload.stat().st_size > MAX_UPLOAD_BYTES:
            raise InputError("The file is larger than 20 MB.")
        if suffix == ".zip":
            _safe_extract(upload, folder / "project")
            return _project_target(folder / "project")
        copy = folder / upload.name
        shutil.copyfile(upload, copy)
        return copy
    if pasted.strip():
        if len(pasted) > MAX_PASTED_CHARS:
            raise InputError("The pasted text is longer than 200,000 characters.")
        path = folder / "references.txt"
        path.write_text(pasted, encoding="utf-8")
        return path
    raise InputError("Give an arXiv ID, a file, or pasted references.")


def _outcome(result: CheckResult, lang: str, show_info: bool) -> Outcome:
    buffer = io.StringIO()
    render_text(result, Console(file=buffer, width=100, color_system=None), lang, show_info)
    rows = [
        [
            f.severity.value,
            f.rule_id,
            f.location.display(result.root) if f.location else "",
            f.message.get(lang),
        ]
        for f in result.findings
        if show_info or f.severity.value != "info"
    ]
    fixes = plan(result.findings, result.bib_files, level="unsafe")
    diff = "".join(e.diff(result.root) for e in edits(result.bib_files, fixes))
    lines = buffer.getvalue().rstrip().splitlines()
    return Outcome(
        summary="\n".join(lines[-2:]) if len(lines) >= 2 else "",
        text="\n".join(lines),
        rows=rows,
        json=render_json(result),
        sarif=render_sarif(result, uri_base=result.root),
        diff=diff,
    )


def check(
    *, arxiv: str = "", upload: Path | None = None, pasted: str = "", lang: str = "en",
    show_info: bool = False, verify: VerifyOptions | None = None,
) -> Outcome:  # fmt: skip
    """Check what the visitor gave. Raises :class:`InputError` with a message for them."""
    folder = Path(tempfile.mkdtemp(prefix="preflight-space-"))
    try:
        target = prepare(folder, arxiv=arxiv, upload=upload, pasted=pasted)
        try:
            counted = run_check(target)  # offline: parsing and citation keys only
        except ProjectError as exc:
            raise InputError(str(exc)) from exc
        if counted.entries > MAX_ENTRIES:
            raise InputError(
                f"{counted.entries} references; the online demo checks at most {MAX_ENTRIES}. "
                "Install paper-preflight to check more: pip install paper-preflight"
            )
        if counted.entries == 0:
            raise InputError("No references were found in the input.")
        result = run_check(target, verify=verify or VerifyOptions(cache_path=CACHE))
        return _outcome(result, lang, show_info)
    finally:
        shutil.rmtree(folder, ignore_errors=True)
