import pytest
from typer.testing import CliRunner

from paper_preflight import __version__
from paper_preflight.cli import app

from .fake_web import FakeWeb

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


def sources_section(output: str) -> dict[str, str]:
    lines = output.split("sources (one request each)\n", 1)[1].splitlines()
    return {line.split()[0]: line.split()[1] for line in lines if line.strip()}


def test_doctor_checks_every_source(recorded_web: FakeWeb) -> None:
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0
    status = sources_section(result.output)
    for source in ("doi.org", "Crossref", "DataCite", "arXiv", "dblp", "OpenAlex"):
        assert status[source] == "ok", result.output
    assert "Semantic Scholar" not in status or "skipped" in result.output  # no key: no request
    assert not [r for r in recorded_web.requests if r.url.host == "api.semanticscholar.org"]
    assert "public pool (no email set)" in result.output


def test_doctor_reports_why_a_source_is_unavailable(recorded_web: FakeWeb) -> None:
    recorded_web.fail("sparql.dblp.org", "html")
    recorded_web.fail("export.arxiv.org", "429")
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0
    assert "challenge" in next(line for line in result.output.splitlines() if "dblp" in line)
    assert "rate_limited" in next(line for line in result.output.splitlines() if "arXiv " in line)


def test_doctor_offline_makes_no_request(recorded_web: FakeWeb) -> None:
    result = runner.invoke(app, ["doctor", "--offline"])
    assert result.exit_code == 0
    assert "sources" not in result.output
    assert recorded_web.requests == []


def test_doctor_probes_semantic_scholar_with_a_key_without_printing_it(
    recorded_web: FakeWeb, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("S2_API_KEY", "s2-secret-value")
    result = runner.invoke(app, ["doctor"])
    assert "s2-secret-value" not in result.output
    (request,) = [r for r in recorded_web.requests if r.url.host == "api.semanticscholar.org"]
    assert request.headers["x-api-key"] == "s2-secret-value"


def test_explain_a_rule_in_both_languages() -> None:
    en = runner.invoke(app, ["explain", "ref003", "--lang", "en"])
    assert en.exit_code == 0
    assert "REF003  not-found" in en.output
    assert "severity: error" in en.output
    zh = runner.invoke(app, ["explain", "REF003", "--lang", "zh"])
    assert "所有来源均未找到该文献" in zh.output
    assert "{sources}" in zh.output
    assert "_zh}" not in zh.output  # internal placeholder names stay internal


def test_explain_lists_every_rule_and_rejects_unknown_ones() -> None:
    from paper_preflight.rules import RULES

    listing = runner.invoke(app, ["explain", "--lang", "en"])
    assert listing.exit_code == 0
    assert all(rule_id in listing.output for rule_id in RULES)
    unknown = runner.invoke(app, ["explain", "XYZ999"])
    assert unknown.exit_code == 3
