"""The Python API (D3): paper_preflight.check_paper() and its plain, frozen results."""

import dataclasses
from pathlib import Path

import paper_preflight

from .fake_web import FakeWeb

DEMO = Path(__file__).resolve().parent.parent / "examples" / "demo-paper"


def test_the_demo_paper_from_code(recorded_web: FakeWeb, tmp_path: Path, fast: None) -> None:
    report = paper_preflight.check_paper(DEMO, cache=tmp_path / "c.sqlite3", settings=None)
    assert isinstance(report, paper_preflight.Report)
    assert report.complete
    assert report.verification == "online"
    refs = {r.key: r for r in report.references}
    assert refs["he2016deep"].verdict == "verified"
    assert refs["he2016deep"].matched is not None
    assert refs["he2016deep"].matched.source == "crossref"
    conflict = refs["devlin2019bert"]
    assert conflict.verdict == "identifier_conflict"
    assert "REF001" in {f.rule for f in conflict.findings}
    assert refs["goodfellow2016deep"].verdict == "verified"  # by Open Library
    rules = [f.rule for f in report.findings]
    assert "CIT001" in rules  # citation rules too
    assert report.findings[0].severity == "error"  # errors first
    assert report.blocking("error")
    assert report.to_dict()["schema_version"] == "0.1"
    # frozen, plain values
    assert dataclasses.is_dataclass(report.references[0])
    first = report.findings[0]
    assert isinstance(first.message, str)
    assert first.file is not None


def test_offline_rules_only_and_messages_in_chinese(tmp_path: Path) -> None:
    report = paper_preflight.check_paper(DEMO, online=False, settings=None, language="zh")
    assert report.verification == "skipped"
    assert report.references == ()
    undefined = next(f for f in report.findings if f.rule == "CIT001")
    assert "引用键" in undefined.message
    assert undefined.file == "main.tex"
    assert undefined.line is not None


def test_settings_are_found_or_given(tmp_path: Path) -> None:
    (tmp_path / "refs.bib").write_text(
        "@article{a, title={T}, year=2020}\n@article{a, title={U}, year=2021}\n",
        encoding="utf-8",
    )
    (tmp_path / ".git").mkdir()
    noisy = paper_preflight.check_paper(tmp_path / "refs.bib", online=False)
    assert "CIT002" in {f.rule for f in noisy.findings}  # a duplicate key
    (tmp_path / "paper-preflight.toml").write_text('ignore-rules = ["CIT002"]\n', "utf-8")
    quiet = paper_preflight.check_paper(tmp_path / "refs.bib", online=False)
    assert "CIT002" not in {f.rule for f in quiet.findings}
    unset = paper_preflight.check_paper(tmp_path / "refs.bib", online=False, settings=None)
    assert "CIT002" in {f.rule for f in unset.findings}
