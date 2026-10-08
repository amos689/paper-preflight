"""Project settings: paper-preflight.toml or [tool.paper-preflight] in pyproject.toml (D2)."""

import json
import shutil
from pathlib import Path

import pytest
from typer.testing import CliRunner

from paper_preflight.cli import EXIT_FINDINGS, EXIT_OK, EXIT_USAGE, app
from paper_preflight.config import ConfigError, find_config, load_config
from paper_preflight.findings import Severity

from .fake_web import FakeWeb

DEMO = Path(__file__).resolve().parent.parent / "examples" / "demo-paper"
runner = CliRunner()


def test_settings_from_their_own_file(tmp_path: Path) -> None:
    path = tmp_path / "paper-preflight.toml"
    path.write_text(
        'ignore-rules = ["ref016"]\nignore-keys = ["draft*"]\n'
        'severity = { REF015 = "info" }\ndisable-sources = ["S2"]\nfail-on = "warning"\n',
        encoding="utf-8",
    )
    config = load_config(path)
    assert config.ignore_rules == {"REF016"}
    assert config.ignore_keys == ("draft*",)
    assert config.severity == {"REF015": Severity.INFO}
    assert config.disable_sources == {"s2"}
    assert config.fail_on == "warning"


def test_settings_in_pyproject_and_where_they_are_found(tmp_path: Path) -> None:
    project = tmp_path / "repo"
    paper = project / "papers" / "nips"
    paper.mkdir(parents=True)
    (project / ".git").mkdir()
    (project / "pyproject.toml").write_text(
        '[project]\nname = "x"\n[tool.paper-preflight]\nignore-rules = ["CIT003"]\n',
        encoding="utf-8",
    )
    assert find_config(paper) == project / "pyproject.toml"
    assert load_config(project / "pyproject.toml").ignore_rules == {"CIT003"}
    (paper / "paper-preflight.toml").write_text("", encoding="utf-8")  # the nearest wins
    assert find_config(paper / "main.tex") == paper / "paper-preflight.toml"
    # not above a repository's root
    (tmp_path / "paper-preflight.toml").write_text("", encoding="utf-8")
    (project / "pyproject.toml").write_text('[project]\nname = "x"\n', encoding="utf-8")
    (paper / "paper-preflight.toml").unlink()
    assert find_config(paper) is None


@pytest.mark.parametrize(
    ("text", "complaint"),
    [
        ("ignore = []", "unknown setting(s) ignore"),
        ('ignore-rules = ["REF999"]', "unknown rule(s) REF999"),
        ('severity = { REF015 = "low" }', "error, warning or info"),
        ('disable-sources = ["crossref"]', "crossref cannot be turned off"),
        ('fail-on = "always"', "fail-on must be"),
        ('ignore-keys = "draft"', "must be a list of strings"),
        ("ignore-rules = [", "not valid TOML"),
    ],
)
def test_mistakes_are_errors(tmp_path: Path, text: str, complaint: str) -> None:
    path = tmp_path / "paper-preflight.toml"
    path.write_text(text + "\n", encoding="utf-8")
    with pytest.raises(ConfigError, match=complaint.replace("(", r"\(").replace(")", r"\)")):
        load_config(path)


def test_the_check_command_applies_them(recorded_web: FakeWeb, tmp_path: Path, fast: None) -> None:
    paper = tmp_path / "demo"
    shutil.copytree(DEMO, paper)
    (paper / ".git").mkdir()
    out = tmp_path / "r.json"
    plain = runner.invoke(app, ["check", str(paper), "-f", "json", "-o", str(out)])
    assert plain.exit_code == EXIT_FINDINGS
    rules = {f["rule"] for f in json.loads(out.read_text("utf-8"))["findings"]}
    assert {"REF003", "CIT001"} <= rules
    (paper / "paper-preflight.toml").write_text(
        'ignore-rules = ["REF003"]\nignore-keys = ["nonexistent*"]\n'
        'severity = { REF001 = "info", REF004 = "warning" }\nfail-on = "never"\n',
        encoding="utf-8",
    )
    configured = runner.invoke(app, ["check", str(paper), "-f", "json", "-o", str(out)])
    assert configured.exit_code == EXIT_OK  # fail-on = "never"
    payload = json.loads(out.read_text("utf-8"))
    findings = payload["findings"]
    assert not any(f["rule"] == "REF003" for f in findings)
    assert not any(f["key"] == "nonexistent2023" for f in findings)  # its CIT001 too
    assert {f["severity"] for f in findings if f["rule"] == "REF001"} == {"info"}
    assert any(note.startswith("settings: ") for note in payload["run"]["notes"])
    # the command line wins over the settings
    strict = runner.invoke(app, ["check", str(paper), "--fail-on", "warning", "-o", str(out)])
    assert strict.exit_code == EXIT_FINDINGS
    (paper / "paper-preflight.toml").write_text('ignore-rules = ["REF999"]\n', encoding="utf-8")
    broken = runner.invoke(app, ["check", str(paper)])
    assert broken.exit_code == EXIT_USAGE
    assert "REF999" in broken.output
