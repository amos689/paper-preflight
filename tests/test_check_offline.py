import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from paper_preflight.check import run_check
from paper_preflight.cli import EXIT_FINDINGS, EXIT_OK, EXIT_USAGE, app

runner = CliRunner()

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
