import pytest
from typer.testing import CliRunner

from paper_preflight import __version__
from paper_preflight.cli import app

runner = CliRunner()


def test_version() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.output


def test_doctor_never_prints_secret_values(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENALEX_API_KEY", "super-secret-value")
    monkeypatch.setenv("PAPER_PREFLIGHT_CACHE_DIR", "/tmp/ppf-cache")
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0
    assert "super-secret-value" not in result.output
    assert "OPENALEX_API_KEY" in result.output
    assert "/tmp/ppf-cache" in result.output
