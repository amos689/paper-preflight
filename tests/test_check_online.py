"""`check` with reference verification, against the recorded web (see conftest.py)."""

import json
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner, Result

from paper_preflight.cli import EXIT_FINDINGS, EXIT_INCOMPLETE, EXIT_OK, app

from .fake_web import FakeWeb

DEMO = Path(__file__).parent.parent / "examples" / "demo-paper"
CITED = {
    "vaswani2017attention", "he2016deep", "he2015residual", "devlin2019bert", "kingma2015adam",
    "hendrycks2016gelu", "lindqvist2024quantum", "wakefield1998ileal", "goodfellow2016deep",
    "zhou2016ml", "tacl2019example",
}  # fmt: skip

runner = CliRunner()
pytestmark = pytest.mark.usefixtures("fast")


def check(*args: str) -> Result:
    return runner.invoke(app, ["check", *args])


def check_json(tmp_path: Path, *args: str) -> tuple[Result, dict[str, Any]]:
    out = tmp_path / "report.json"
    result = check(*args, "--format", "json", "--output", str(out))
    return result, json.loads(out.read_text(encoding="utf-8"))


def test_demo_paper_text_report() -> None:
    result = check(str(DEMO), "--lang", "en")
    assert result.exit_code == EXIT_FINDINGS
    for rule in ("CIT001", "REF001", "REF003", "REF004", "REF013", "REF015"):
        assert rule in result.output
    assert "References: 6 verified" in result.output
    zh = check(str(DEMO), "--lang", "zh")
    assert "参考文献核查：已核实 6" in zh.output


def test_demo_paper_json_references(tmp_path: Path) -> None:
    result, payload = check_json(tmp_path, str(DEMO))
    assert result.exit_code == EXIT_FINDINGS
    assert payload["run"]["complete"] is True
    assert payload["verification"] == {
        "mode": "online",
        "verdicts": {
            "verified": 6, "metadata_mismatch": 1, "identifier_conflict": 1, "not_found": 1,
            "cannot_determine": 2,
        },
        "unverified_offline": 0,
    }  # fmt: skip
    refs = {r["key"]: r for r in payload["references"]}
    assert set(refs) == CITED  # only references that appear in the PDF are verified
    assert refs["devlin2019bert"]["verdict"] == "identifier_conflict"
    assert refs["vaswani2017attention"]["matched"]["id"] == "conf/nips/VaswaniSPUJGKP17"
    assert refs["goodfellow2016deep"]["reasons"] == ["GREY_LITERATURE"]
    assert refs["he2015residual"]["flags"] == ["preprint_published"]
    reported = {f["id"] for f in payload["findings"]}
    assert refs["devlin2019bert"]["findings"]
    assert set(refs["devlin2019bert"]["findings"]) <= reported


def test_offline_run_replays_the_cache(tmp_path: Path, recorded_web: FakeWeb) -> None:
    _, online = check_json(tmp_path, str(DEMO))
    asked = len(recorded_web.requests)
    assert asked > 0
    _, offline = check_json(tmp_path, str(DEMO), "--offline")
    assert len(recorded_web.requests) == asked  # not a single request in offline mode
    assert offline["verification"]["mode"] == "offline"
    assert offline["verification"]["unverified_offline"] == 0
    assert offline["references"] == online["references"]
    assert offline["findings"] == online["findings"]


def test_offline_without_cache_neither_fails_nor_floods(
    tmp_path: Path, recorded_web: FakeWeb
) -> None:
    result, payload = check_json(tmp_path, str(DEMO), "--offline", "--fail-on", "never")
    assert recorded_web.requests == []
    assert result.exit_code == EXIT_OK  # offline was asked for; no source failed
    assert payload["run"]["complete"] is True
    # the two books stay "cannot determine" for their own reasons; the rest are just unverified
    assert payload["verification"]["unverified_offline"] == len(CITED) - 2
    rules = [f["rule"] for f in payload["findings"]]
    assert rules.count("REF090") == 2
    assert "RUN001" not in rules
    assert "REF003" not in rules


def test_source_outage_makes_the_run_incomplete(tmp_path: Path, recorded_web: FakeWeb) -> None:
    recorded_web.fail("sparql.dblp.org", "html")
    result, payload = check_json(tmp_path, str(DEMO), "--fail-on", "never")
    assert result.exit_code == EXIT_INCOMPLETE
    assert payload["run"]["complete"] is False
    assert "RUN001" in [f["rule"] for f in payload["findings"]]
    refs = {r["key"]: r for r in payload["references"]}
    assert refs["lindqvist2024quantum"]["verdict"] == "cannot_determine"
    # blocking findings rest on positive evidence and take precedence over incompleteness
    assert check(str(DEMO)).exit_code == EXIT_FINDINGS


def test_bib_only_mode_verifies_every_entry(tmp_path: Path) -> None:
    _, payload = check_json(tmp_path, str(DEMO / "refs.bib"))
    keys = {r["key"] for r in payload["references"]}
    assert keys == CITED | {"lecun1998gradient"}  # no LaTeX: everything in the file counts


def test_offline_after_adding_an_entry_keeps_every_other_verdict(tmp_path: Path) -> None:
    # Answers are cached per identifier, so one new entry does not invalidate its batch
    # companions: before, every DOI lookup of the bibliography missed the cache offline.
    bib = tmp_path / "refs.bib"
    bib.write_text((DEMO / "refs.bib").read_text(encoding="utf-8"), encoding="utf-8")
    _, online = check_json(tmp_path, str(bib))
    added = [
        "",
        "@article{added2025new, title = {A Newly Added Paper With A Long Title},",
        "  author = {Doe, Jane}, year = {2025}, doi = {10.1109/CVPR.2016.91}}",
        "",
    ]
    with bib.open("a", encoding="utf-8") as handle:
        handle.write("\n".join(added))
    _, offline = check_json(tmp_path, str(bib), "--offline")
    before = {r["key"]: r["verdict"] for r in online["references"]}
    after = {r["key"]: r["verdict"] for r in offline["references"]}
    assert {k: after[k] for k in before} == before
    assert after["added2025new"] == "cannot_determine"
    assert offline["verification"]["unverified_offline"] == 1


def test_offline_after_adding_a_preprint_keeps_published_versions(tmp_path: Path) -> None:
    # dblp's batch lookups (arXiv DOI -> CoRR record -> published version) are cached per item
    # too, so a new preprint does not hide the published versions of the others offline.
    bib = tmp_path / "refs.bib"
    bib.write_text((DEMO / "refs.bib").read_text(encoding="utf-8"), encoding="utf-8")
    _, online = check_json(tmp_path, str(bib))
    added = [
        "",
        "@misc{added2025preprint, title = {A Newly Added Preprint With A Long Title},",
        "  author = {Doe, Jane}, year = {2025}, eprint = {2501.00001}, archiveprefix = {arXiv}}",
        "",
    ]
    with bib.open("a", encoding="utf-8") as handle:
        handle.write("\n".join(added))
    _, offline = check_json(tmp_path, str(bib), "--offline")
    before = {r["key"]: r["flags"] for r in online["references"]}
    after = {r["key"]: r["flags"] for r in offline["references"]}
    assert before["he2015residual"] == ["preprint_published"]
    assert {k: after[k] for k in before} == before
    assert "REF015" in [f["rule"] for f in offline["findings"]]


def test_unused_reference_suppressions_need_a_complete_online_run(tmp_path: Path) -> None:
    bib = tmp_path / "refs.bib"
    text = (DEMO / "refs.bib").read_text(encoding="utf-8")
    for key in ("he2016deep", "kingma2015adam"):
        text = text.replace(
            f"@inproceedings{{{key},", f"% preflight: ignore[REF013]\n@inproceedings{{{key},"
        )
    bib.write_text(text, encoding="utf-8")
    _, online = check_json(tmp_path, str(bib))
    found = [(f["rule"], f.get("key")) for f in online["findings"]]
    assert ("CFG001", "he2016deep") in found  # verified, and there was no wrong year to hide
    assert ("CFG001", "kingma2015adam") not in found  # its wrong year was suppressed
    assert ("REF013", "kingma2015adam") not in found
    _, offline = check_json(tmp_path, str(bib), "--offline")
    assert "CFG001" not in [f["rule"] for f in offline["findings"]]
