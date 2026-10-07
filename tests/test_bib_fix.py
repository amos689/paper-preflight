"""`bib fix` against the recorded web (conftest.py)."""

import json
import shutil
from pathlib import Path

import pytest
from typer.testing import CliRunner, Result

from paper_preflight.bib.parse import parse_bib_text
from paper_preflight.cli import EXIT_OK, app
from paper_preflight.fixes import Fix, apply

DEMO = Path(__file__).parent.parent / "examples" / "demo-paper"
runner = CliRunner()
pytestmark = pytest.mark.usefixtures("fast")


@pytest.fixture
def paper(tmp_path: Path) -> Path:
    target = tmp_path / "paper"
    shutil.copytree(DEMO, target)
    return target


def fix(*args: str) -> Result:
    return runner.invoke(app, ["bib", "fix", *args])


def test_safe_level_fixes_only_what_cannot_change_the_work(paper: Path) -> None:
    before = (paper / "refs.bib").read_bytes()
    result = fix(str(paper))
    assert result.exit_code == EXIT_OK
    assert "-  doi     = {10.1162/tacl\\_a\\_00276}," in result.stdout
    assert "+  doi     = {10.1162/tacl_a_00276}," in result.stdout
    assert "year      = {2015}" not in result.stdout  # an unsafe fix
    assert "--apply" in result.stderr
    assert (paper / "refs.bib").read_bytes() == before  # a diff only: nothing written


def test_unsafe_level_rewrites_from_the_record(paper: Path) -> None:
    result = fix(str(paper), "--level", "unsafe")
    assert "+  year      = {2015}," in result.stdout  # Adam: ICLR 2015
    assert "-  doi       = {10.1109/CVPR.2016.90}," in result.stdout  # BERT's DOI is ResNet's


def test_apply_and_check_again(paper: Path) -> None:
    applied = fix(str(paper), "--level", "unsafe", "--apply")
    assert applied.exit_code == EXIT_OK
    assert "written" in applied.stderr
    check = runner.invoke(app, ["check", str(paper), "--format", "json", "--fail-on", "never"])
    rules = {(f["rule"], f["key"]) for f in json.loads(check.stdout)["findings"]}
    for fixed in [("REF017", "tacl2019example"), ("REF013", "kingma2015adam"),
                  ("REF001", "devlin2019bert")]:  # fmt: skip
        assert fixed not in rules, fixed
    assert ("REF003", "lindqvist2024quantum") in rules  # never "fixed": only the user can


def test_keys_and_json(paper: Path) -> None:
    result = fix(str(paper), "--level", "unsafe", "--keys", "kingma2015adam", "--format", "json")
    payload = json.loads(result.stdout)
    assert payload["applied"] is False
    (only,) = payload["fixes"]
    assert (only["key"], only["field"], only["old"], only["new"]) == (
        "kingma2015adam", "year", "{2016}", "2015",
    )  # fmt: skip
    assert only["level"] == "unsafe"


def test_a_missing_doi_is_added(tmp_path: Path) -> None:
    bib = tmp_path / "refs.bib"
    bib.write_text(
        "@inproceedings{he2016deep,\n"
        "  title     = {Deep Residual Learning for Image Recognition},\n"
        "  author    = {He, Kaiming and Zhang, Xiangyu and Ren, Shaoqing and Sun, Jian},\n"
        "  year      = {2016}\n"
        "}\n",
        encoding="utf-8",
    )
    result = fix(str(bib), "--apply")
    assert result.exit_code == EXIT_OK
    text = bib.read_text(encoding="utf-8")
    assert "  year      = {2016},\n  doi = {10.1109/cvpr.2016.90},\n}" in text
    (entry,) = parse_bib_text(text, bib).entries
    assert entry.text("doi") == "10.1109/cvpr.2016.90"


def test_line_endings_and_untouched_bytes_are_kept(tmp_path: Path) -> None:
    text = (
        "% a comment that must survive\r\n"
        "@article{a,\r\n  title = {X},\r\n"
        "  doi = {10.1162/tacl\\_a\\_00276},\r\n  year = {2019}\r\n}\r\n"
    )
    entries = parse_bib_text(text, tmp_path / "x.bib").entries
    fixes = [
        Fix(
            tmp_path / "x.bib",
            "a",
            "REF017",
            "doi",
            "replace",
            "{10.1162/tacl\\_a\\_00276}",
            "10.1162/tacl_a_00276",
            "safe",
        ),
        Fix(tmp_path / "x.bib", "a", "REF013", "year", "replace", "{2019}", "2020", "unsafe"),
    ]
    new = apply(text, entries, fixes, "\r\n")
    assert new == text.replace("tacl\\_a\\_00276", "tacl_a_00276").replace("2019", "2020")
    assert "\n" not in new.replace("\r\n", "")  # still CRLF everywhere


def test_advice_is_never_written_into_the_file(tmp_path: Path) -> None:
    # REF017's "(remove or correct the field)" is advice for a person, not a value: an invalid
    # DOI or arXiv ID is left as it is, while an ID with its subject class is corrected
    bib = tmp_path / "refs.bib"
    bib.write_text(
        "@misc{z,\n  title = {Instruction-Following Evaluation for Large Language Models},\n"
        "  eprinttype = {arxiv},\n  eprint = {2311.07911 [cs]},\n  doi = {not a doi}\n}\n"
        "@misc{y,\n  title = {Something},\n  eprinttype = {arxiv},\n  eprint = {1706.0376x}\n}\n",
        encoding="utf-8",
    )
    result = fix(str(bib), "--apply", "--offline")
    assert result.exit_code == EXIT_OK
    text = bib.read_text(encoding="utf-8")
    assert "eprint = {2311.07911}," in text
    assert "doi = {not a doi}" in text
    assert "eprint = {1706.0376x}" in text
    assert "(" not in text
