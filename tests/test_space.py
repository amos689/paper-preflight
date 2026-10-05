"""The Hugging Face Space's runner (space/runner.py), offline."""

import json
import sys
import zipfile
from pathlib import Path

import pytest

from paper_preflight.check import VerifyOptions

sys.path.insert(0, str(Path(__file__).parent.parent / "space"))
import runner

DEMO = Path(__file__).parent.parent / "examples" / "demo-paper"
REFERENCES = (
    "[1] A. Vaswani, N. Shazeer, N. Parmar, et al. Attention is all you need. In Advances in "
    "Neural Information Processing Systems, 2017.\n\n"
    "[2] D. P. Kingma and J. Ba. Adam: A method for stochastic optimization. arXiv preprint "
    "arXiv:1412.6980, 2014.\n"
)


def offline(tmp_path: Path) -> VerifyOptions:
    return VerifyOptions(offline=True, cache_path=tmp_path / "cache.sqlite3")


def test_pasted_references_are_checked(tmp_path: Path) -> None:
    outcome = runner.check(pasted=REFERENCES, verify=offline(tmp_path), show_info=True)
    payload = json.loads(outcome.json)
    assert [r["key"] for r in payload["references"]] == ["ref1", "ref2"]
    assert "paper-preflight" in outcome.text
    assert json.loads(outcome.sarif)["version"] == "2.1.0"
    assert all(len(row) == 4 for row in outcome.rows)


def test_a_zipped_project_is_checked_from_its_main_file(tmp_path: Path) -> None:
    archive = tmp_path / "project.zip"
    with zipfile.ZipFile(archive, "w") as zipped:
        for path in DEMO.rglob("*"):
            if path.is_file():
                zipped.write(path, f"paper/{path.relative_to(DEMO).as_posix()}")
    outcome = runner.check(upload=archive, verify=offline(tmp_path))
    assert any(row[1] == "CIT001" for row in outcome.rows)  # the demo's undefined key
    assert "main.tex" in outcome.text


@pytest.mark.parametrize("name", ["../evil.tex", "/etc/evil.tex"])
def test_an_archive_cannot_write_outside_its_folder(tmp_path: Path, name: str) -> None:
    archive = tmp_path / "bad.zip"
    with zipfile.ZipFile(archive, "w") as zipped:
        zipped.writestr(name, "x")
    with pytest.raises(runner.InputError, match="unsafe path"):
        runner.prepare(tmp_path / "work", upload=archive)


def test_a_project_without_main_file_uses_its_only_bib(tmp_path: Path) -> None:
    folder = tmp_path / "p"
    (folder / "sub").mkdir(parents=True)
    (folder / "sub" / "refs.bib").write_text("@misc{a, title={T}}", encoding="utf-8")
    assert runner._project_target(folder) == folder / "sub" / "refs.bib"
    (folder / "other.bib").write_text("@misc{b, title={U}}", encoding="utf-8")
    with pytest.raises(runner.InputError, match=r"main \.tex"):
        runner._project_target(folder)


def test_inputs_the_demo_refuses(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(runner.InputError, match="arXiv ID"):
        runner.check(arxiv="not an id", verify=offline(tmp_path))
    with pytest.raises(runner.InputError, match="Give an arXiv ID"):
        runner.check(verify=offline(tmp_path))
    odd = tmp_path / "notes.docx"
    odd.write_bytes(b"x")
    with pytest.raises(runner.InputError, match="not supported"):
        runner.check(upload=odd, verify=offline(tmp_path))
    monkeypatch.setattr(runner, "MAX_ENTRIES", 1)
    with pytest.raises(runner.InputError, match="at most 1"):
        runner.check(pasted=REFERENCES, verify=offline(tmp_path))


@pytest.mark.parametrize(
    "given",
    [
        "1706.03762",
        "arXiv:1706.03762",
        "https://arxiv.org/abs/1706.03762v2",
        "arxiv.org/pdf/1706.03762.pdf",
    ],
)
def test_arxiv_ids_are_read_from_links(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, given: str
) -> None:
    fetched: list[str] = []

    def fake_fetch(identifier: str, folder: Path) -> Path:
        fetched.append(identifier)
        return folder

    monkeypatch.setattr(runner.arxiv_source, "fetch", fake_fetch)
    runner.prepare(tmp_path, arxiv=given)
    assert fetched == [given.split("/")[-1].removesuffix(".pdf").removeprefix("arXiv:")]
