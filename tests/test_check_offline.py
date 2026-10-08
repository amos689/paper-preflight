import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from paper_preflight.check import run_check
from paper_preflight.cli import EXIT_FINDINGS, EXIT_OK, EXIT_USAGE, app
from paper_preflight.findings import Finding

runner = CliRunner()

# the CLI now verifies references too (against the recorded web, see conftest.py)
pytestmark = pytest.mark.usefixtures("fast")

MAIN = r"""\documentclass{article}
\begin{document}
See \citep{good, missing_key} and \citet{good}.
Also \cite{dup1}, \cite{dup2}, \cite{arx1, arx2} and \cite{noauthor}.
\cite{suppressed}
\input{nowhere}
\bibliography{refs}
\end{document}
"""

REFS = r"""@article{good,
  author = {Doe, Jane},
  title = {A Perfectly Fine Paper About Testing},
  journal = {Journal of Tests},
  year = {2020},
}

@article{dup1,
  author = {Roe, Richard}, title = {Same DOI One}, journal = {J}, year = {2021},
  doi = {10.1234/ABC.5},
}

@article{dup2,
  author = {Roe, Richard}, title = {Same DOI Two}, journal = {J}, year = {2021},
  doi = {https://doi.org/10.1234/abc.5},
}

@misc{arx1, author = {A, B}, title = {Preprint}, eprint = {2101.00001}}
@misc{arx2, author = {A, B}, title = {Preprint again},
  journal = {arXiv preprint arXiv:2101.00001v2}}

@article{noauthor, title = {Missing Many Fields}}

@article{unused, author = {X, Y}, title = {Never Cited}, journal = {J}, year = {2000}}

% preflight: ignore[CIT006] reason="intentionally sparse"
@article{suppressed, title = {Also Sparse}}

@article{good, title = {Duplicate key}}
"""


@pytest.fixture
def project(tmp_path: Path) -> Path:
    root = tmp_path / "paper"
    root.mkdir()
    (root / "main.tex").write_text(MAIN, encoding="utf-8")
    (root / "refs.bib").write_text(REFS, encoding="utf-8")
    return root


def rules_of(path: Path) -> list[tuple[str, str | None]]:
    result = run_check(path)
    return [(f.rule_id, f.key) for f in result.findings]


def test_hygiene_findings(project: Path) -> None:
    found = rules_of(project)
    assert ("CIT001", "missing_key") in found
    assert ("CIT002", "good") in found
    assert ("CIT003", "unused") in found
    assert ("CIT004", "dup2") in found  # same DOI as dup1 (case and prefix differ)
    assert ("CIT004", "arx2") in found  # same arXiv ID as arx1 (version ignored)
    assert ("CIT006", "noauthor") in found
    assert ("CIT006", "suppressed") not in found  # suppressed by comment
    assert ("TEX001", None) in found
    # errors come first
    severities = [f.severity.value for f in run_check(project).findings]
    assert severities == sorted(severities, key={"error": 0, "warning": 1, "info": 2}.get)


def test_chapters_of_one_book_may_share_its_doi(tmp_path: Path) -> None:
    refs = tmp_path / "refs.bib"
    refs.write_text(
        "@incollection{a, title={Machine Learning Techniques}, booktitle={Information and "
        "Knowledge Organisation in Digital Humanities}, doi={10.4324/9781003131816}, year=2021}\n"
        "@incollection{b, title={Linked Data Strategies}, booktitle={Information and "
        "Knowledge Organisation in Digital Humanities}, doi={10.4324/9781003131816}, year=2021}\n"
        "@incollection{c, title={Linked Data Strategies}, booktitle={Information and "
        "Knowledge Organisation in Digital Humanities}, doi={10.4324/9781003131816}, year=2021}\n",
        encoding="utf-8",
    )
    found = rules_of(refs)
    assert ("CIT004", "b") not in found  # another chapter
    assert ("CIT004", "c") in found  # the same chapter twice


def test_undefined_key_reports_all_sites(tmp_path: Path) -> None:
    (tmp_path / "main.tex").write_text(
        "\\documentclass{article}\\begin{document}\n\\cite{x}\n\\cite{x}\n"
        "\\bibliography{r}\\end{document}",
        encoding="utf-8",
    )
    (tmp_path / "r.bib").write_text("", encoding="utf-8")
    (finding,) = [f for f in run_check(tmp_path).findings if f.rule_id == "CIT001"]
    assert finding.location is not None
    assert finding.location.line == 2
    assert [r.line for r in finding.related] == [3]
    assert finding.data["count"] == 2


def test_cli_text_output_and_exit_codes(project: Path) -> None:
    result = runner.invoke(app, ["check", str(project), "--lang", "en"])
    assert result.exit_code == EXIT_FINDINGS
    assert "CIT001" in result.output
    assert "refs.bib:" in result.output
    zh = runner.invoke(app, ["check", str(project), "--lang", "zh"])
    assert "未在任何参考文献文件中定义" in zh.output
    never = runner.invoke(app, ["check", str(project), "--fail-on", "never"])
    assert never.exit_code == EXIT_OK


def test_cli_json_output(project: Path, tmp_path: Path) -> None:
    out = tmp_path / "report.json"
    result = runner.invoke(
        app,
        ["check", str(project), "--format", "json", "--output", str(out), "--max-findings", "2"],
    )
    assert result.exit_code == EXIT_FINDINGS
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "0.1"
    assert payload["project"]["main"] == "main.tex"
    assert payload["project"]["bib_files"] == ["refs.bib"]
    assert len(payload["findings"]) == 2
    assert payload["pagination"]["truncated"] is True
    first = payload["findings"][0]
    assert first["severity"] == "error"
    assert first["id"].startswith("f-")
    assert set(first["message"]) == {"en", "zh"}


def test_bib_only_mode(project: Path) -> None:
    found = rules_of(project / "refs.bib")
    assert ("CIT001", "missing_key") not in found  # no LaTeX sources in bib-only mode
    assert ("CIT003", "unused") not in found
    assert ("CIT002", "good") in found


def test_usage_error_exit_code(tmp_path: Path) -> None:
    result = runner.invoke(app, ["check", str(tmp_path)])
    assert result.exit_code == EXIT_USAGE


def test_fingerprints_are_stable_when_lines_move(project: Path) -> None:
    before = {f.fingerprint for f in run_check(project).findings if f.rule_id == "CIT003"}
    refs = project / "refs.bib"
    refs.write_text("\n\n\n" + refs.read_text(encoding="utf-8"), encoding="utf-8")
    after = {f.fingerprint for f in run_check(project).findings if f.rule_id == "CIT003"}
    assert before == after


def unused(findings: list[Finding]) -> list[tuple[str | None, str, int]]:
    return sorted(
        (f.key, f.data["rule"], f.location.line if f.location else 0)
        for f in findings
        if f.rule_id == "CFG001"
    )


SUPPRESSIONS = """% preflight: ignore[CIT006, CIT004] reason="sparse on purpose"
@article{a, title = {Sparse}}

% preflight: ignore[REF003, CIT0006]
@article{b, author = {Doe, Jane}, title = {A Perfectly Fine Paper About Testing},
  journal = {J}, year = {2020}}
"""


def test_unused_suppressions_are_reported(tmp_path: Path) -> None:
    root = tmp_path / "paper"
    root.mkdir()
    (root / "main.tex").write_text(
        r"\documentclass{article}\begin{document}\cite{a,b}\bibliography{refs}\end{document}",
        encoding="utf-8",
    )
    (root / "refs.bib").write_text(SUPPRESSIONS, encoding="utf-8")
    # CIT006 dropped a finding and CIT004 did not; REF003 never ran (nothing was verified);
    # CIT0006 is no rule at all
    assert unused(run_check(root).findings) == [("a", "CIT004", 1), ("b", "CIT0006", 4)]


def test_project_rules_are_not_judged_on_a_bib_file_alone(tmp_path: Path) -> None:
    bib = tmp_path / "refs.bib"
    bib.write_text(
        "% preflight: ignore[CIT003]\n"
        "@article{a, author = {Doe, Jane}, title = {T}, journal = {J}, year = {2020}}\n",
        encoding="utf-8",
    )
    assert unused(run_check(bib).findings) == []


def test_the_only_bib_stands_in_for_a_missing_bibliography_command(tmp_path: Path) -> None:
    # arXiv 2607.20215v1: a \bibliographystyle, a .bib next to the main file, no \bibliography
    (tmp_path / "main.tex").write_text(
        "\\documentclass{article}\\bibliographystyle{plain}"
        "\\begin{document}\\cite{a}\\cite{missing}\\end{document}\n",
        encoding="utf-8",
    )
    entry = "@article{{{key}, author = {{Doe, Jane}}, title = {{T}}, year = {{2020}}}}\n"
    (tmp_path / "refs.bib").write_text(entry.format(key="a"), encoding="utf-8")
    result = run_check(tmp_path)
    rules = {(f.rule_id, f.key) for f in result.findings}
    assert result.entries == 1
    assert ("CIT001", "missing") in rules  # cited, in no bibliography
    assert ("CIT001", "a") not in rules
    assert any(f.rule_id == "CIT005" for f in result.findings)  # the source still lacks it
    assert any("refs.bib" in note for note in result.notes)

    # two .bib files: which one LaTeX would have used is unknown
    (tmp_path / "other.bib").write_text(entry.format(key="b"), encoding="utf-8")
    result = run_check(tmp_path)
    assert result.entries == 0
    assert result.notes == []
