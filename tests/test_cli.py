import pytest
from typer.testing import CliRunner

from paper_preflight import __version__
from paper_preflight.cli import app, progress_text

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
    assert "严重度: 错误" in zh.output  # the severity and the fix in Chinese too
    assert "修复: 无" in zh.output
    assert "{sources}" in zh.output
    assert "_zh}" not in zh.output  # internal placeholder names stay internal
    # what it checks, when it can be wrong and what to do: docs/rules/REF003.md's text
    assert "When it can be wrong" in en.output
    assert "every source answered" in en.output
    assert "什么时候可能误报" in zh.output
    assert "docs/rules/REF003.md" in en.output


def test_explain_lists_every_rule_and_rejects_unknown_ones() -> None:
    from paper_preflight.rules import RULES

    listing = runner.invoke(app, ["explain", "--lang", "en"])
    assert listing.exit_code == 0
    assert all(rule_id in listing.output for rule_id in RULES)
    unknown = runner.invoke(app, ["explain", "XYZ999"])
    assert unknown.exit_code == 3


@pytest.mark.parametrize(
    ("language", "done", "seconds", "expected"),
    [
        ("en", 12, 18.0, "Checking (searching by title 12/40, about 42 s left)"),
        ("en", 0, 0.0, "Checking (searching by title 0/40)"),  # no estimate before the first
        ("en", 40, 60.0, "Checking (searching by title 40/40)"),
        ("zh", 10, 10.0, "Checking（按标题检索 10/40，约剩 30 秒）"),
    ],
)
def test_progress_text(language: str, done: int, seconds: float, expected: str) -> None:
    assert progress_text("Checking", language, "title", done, 40, seconds) == expected
