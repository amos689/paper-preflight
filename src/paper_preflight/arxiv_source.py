"""``check arxiv:<id>``: an arXiv paper's source, downloaded for one check.

The source is arXiv's e-print: a tarball, a single gzipped .tex file, or the PDF when the
authors submitted no source. It is fetched once, at the user's request, through
export.arxiv.org (arXiv's address for programs), unpacked into a temporary folder that is
removed when the run ends, and never kept or passed on.
"""

from __future__ import annotations

import gzip
import io
import re
import tarfile
from pathlib import Path

import httpx

from paper_preflight import __version__

EPRINT = "https://export.arxiv.org/e-print/"
HEADERS = {
    "User-Agent": f"paper-preflight/{__version__} (https://github.com/amos689/paper-preflight)"
}
MAX_BYTES = 100_000_000  # arXiv's own limit for a submission's source is 50 MB
_ID = re.compile(r"(?:\d{4}\.\d{4,5}|[a-z][a-z-]*(?:\.[A-Z]{2})?/\d{7})(?:v\d+)?")


class ArxivSourceError(Exception):
    """The paper or its source could not be had."""


def arxiv_target(target: str) -> str | None:
    """The arXiv ID in "arxiv:2607.06922" (or "arXiv:hep-th/9901001v2"), else None."""
    if not target.lower().startswith("arxiv:"):
        return None
    identifier = target[len("arxiv:") :].strip()
    if not _ID.fullmatch(identifier):
        raise ArxivSourceError(f"not an arXiv ID: {identifier!r}")
    return identifier


def fetch(identifier: str, folder: Path, client: httpx.Client | None = None) -> Path:
    """Download the paper's source into ``folder``; the path to check (the folder or a PDF)."""
    own = client is None
    http = client or httpx.Client(headers=HEADERS, timeout=60, follow_redirects=True)
    try:
        response = http.get(EPRINT + identifier)
    except httpx.HTTPError as exc:
        raise ArxivSourceError(f"arXiv could not be reached: {exc}") from exc
    finally:
        if own:
            http.close()
    return store(identifier, response.status_code, response.content, folder)


def store(identifier: str, status: int, content: bytes, folder: Path) -> Path:
    """Unpack a downloaded e-print into ``folder``; the path to check (the folder or a PDF)."""
    if status == 404:
        raise ArxivSourceError(f"arXiv has no paper {identifier}")
    if status != 200:
        raise ArxivSourceError(f"arXiv answered HTTP {status} for {identifier}")
    if len(content) > MAX_BYTES:
        raise ArxivSourceError(f"the source of {identifier} is larger than {MAX_BYTES} bytes")
    folder.mkdir(parents=True, exist_ok=True)
    if content[:5] == b"%PDF-":  # no source was submitted: the PDF is all there is
        pdf = folder / f"{identifier.replace('/', '_')}.pdf"
        pdf.write_bytes(content)
        return pdf
    unpack(content, folder)
    if not any(folder.rglob("*.tex")):
        raise ArxivSourceError(f"the source of {identifier} has no .tex file")
    return folder


def unpack(content: bytes, folder: Path) -> None:
    """A tarball (gzipped or not), or one gzipped .tex file. A tarball with a file that would
    land outside the folder (an absolute path, "..") is refused."""
    try:
        with tarfile.open(fileobj=io.BytesIO(content), mode="r:*") as archive:
            members = archive.getmembers()
            if any(Path(m.name).is_absolute() or ".." in Path(m.name).parts for m in members):
                raise ArxivSourceError("the source has a file outside its own folder")
            # plain files and folders only: no links or devices
            plain = [m for m in members if m.isfile() or m.isdir()]
            if hasattr(tarfile, "data_filter"):
                archive.extractall(folder, members=plain, filter="data")
            else:  # Python 3.11 before 3.11.4
                archive.extractall(folder, members=plain)
        return
    except tarfile.ReadError:
        pass
    data = gzip.decompress(content) if content[:2] == b"\x1f\x8b" else content
    (folder / "main.tex").write_bytes(data)
