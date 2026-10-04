"""``check arxiv:<id>``: an arXiv paper's source, downloaded for one check."""

import gzip
import io
import tarfile
from pathlib import Path

import httpx
import pytest
from typer.testing import CliRunner

from paper_preflight.arxiv_source import ArxivSourceError, arxiv_target, fetch
from paper_preflight.cli import EXIT_USAGE, app

TEX = rb"\documentclass{article}\begin{document}\cite{a}\bibliography{refs}\end{document}"
BIB = b"@article{a, title={A Title of Some Length}, author={Smith, Ann}, year={2020}}\n"


def tarball(files: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        for name, data in files.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            archive.addfile(info, io.BytesIO(data))
    return buffer.getvalue()


def client(content: bytes, status: int = 200) -> httpx.Client:
    seen: list[str] = []

    def answer(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        return httpx.Response(status, content=content)

    http = httpx.Client(transport=httpx.MockTransport(answer))
    http.seen = seen  # type: ignore[attr-defined]
    return http


@pytest.mark.parametrize(
    ("target", "identifier"),
    [
        ("arxiv:2607.06922", "2607.06922"),
        ("arXiv:2607.06922v2", "2607.06922v2"),
        ("arxiv:hep-th/9901001", "hep-th/9901001"),
        ("refs.bib", None),
    ],
)
def test_arxiv_target(target: str, identifier: str | None) -> None:
    assert arxiv_target(target) == identifier


@pytest.mark.parametrize("target", ["arxiv:", "arxiv:2607", "arxiv:../etc/passwd", "arxiv:1 2"])
def test_not_an_arxiv_id(target: str) -> None:
    with pytest.raises(ArxivSourceError):
        arxiv_target(target)


def test_a_tarball_is_unpacked(tmp_path: Path) -> None:
    http = client(tarball({"main.tex": TEX, "refs.bib": BIB}))
    path = fetch("2607.06922", tmp_path / "src", http)
    assert path == tmp_path / "src"
    assert (path / "refs.bib").read_bytes() == BIB
    assert http.seen == ["https://export.arxiv.org/e-print/2607.06922"]  # type: ignore[attr-defined]


def test_nothing_is_written_outside_the_folder(tmp_path: Path) -> None:
    http = client(tarball({"main.tex": TEX, "../escape.tex": TEX}))
    with pytest.raises(ArxivSourceError, match="outside"):
        fetch("2607.06922", tmp_path / "src", http)
    assert not (tmp_path / "escape.tex").exists()


def test_a_single_gzipped_tex_file(tmp_path: Path) -> None:
    path = fetch("2607.06922", tmp_path / "src", client(gzip.compress(TEX)))
    assert (path / "main.tex").read_bytes() == TEX


def test_a_paper_without_source_is_its_pdf(tmp_path: Path) -> None:
    path = fetch("2607.06922", tmp_path / "src", client(b"%PDF-1.4\n..."))
    assert path.suffix == ".pdf"


def test_no_such_paper(tmp_path: Path) -> None:
    with pytest.raises(ArxivSourceError, match="no paper"):
        fetch("2607.99999", tmp_path / "src", client(b"", status=404))


def test_offline_is_refused() -> None:
    result = CliRunner().invoke(app, ["check", "arxiv:2607.06922", "--offline"])
    assert result.exit_code == EXIT_USAGE
