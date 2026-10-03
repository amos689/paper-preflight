"""`bib fetch` against the recorded web (conftest.py)."""

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner, Result

from paper_preflight.bib.parse import parse_bib_text
from paper_preflight.cli import EXIT_FINDINGS, EXIT_INCOMPLETE, EXIT_OK, EXIT_USAGE, app
from paper_preflight.fetch import identifier_query

runner = CliRunner()
pytestmark = pytest.mark.usefixtures("fast")


def fetch(*args: str) -> Result:
    return runner.invoke(app, ["bib", "fetch", *args])


def entry_of(result: Result) -> dict[str, str]:
    (entry,) = parse_bib_text(result.stdout, Path("out.bib")).entries
    return {"type": entry.entry_type, "key": entry.key} | {
        name: entry.text(name) or "" for name in entry.fields
    }


@pytest.mark.parametrize(
    ("text", "field"),
    [
        ("10.1109/CVPR.2016.90", "doi"),
        ("https://doi.org/10.1109/CVPR.2016.90", "doi"),
        ("doi:10.1109/CVPR.2016.90", "doi"),
        ("1512.03385", "eprint"),
        ("arXiv:1512.03385v2", "eprint"),
        ("https://arxiv.org/abs/1512.03385", "eprint"),
        ("hep-th/9901001", "eprint"),
    ],
)
def test_identifier_forms(text: str, field: str) -> None:
    query = identifier_query(text)
    assert query is not None
    assert f"{field} = " in query
    assert identifier_query("not an identifier") is None


def test_doi() -> None:
    result = fetch("10.1109/CVPR.2016.90")
    assert result.exit_code == EXIT_OK
    entry = entry_of(result)
    assert (entry["type"], entry["key"]) == ("inproceedings", "he2016deep")
    assert entry["title"] == "Deep Residual Learning for Image Recognition"
    assert entry["doi"] == "10.1109/cvpr.2016.90"
    assert result.stdout.startswith("% Verified with paper-preflight against Crossref")


def test_arxiv_preprint_comes_back_as_its_published_version() -> None:
    result = fetch("1512.03385")
    assert result.exit_code == EXIT_OK
    entry = entry_of(result)
    assert entry["type"] == "inproceedings"
    assert entry["booktitle"] == "CVPR"
    assert entry["year"] == "2016"
    assert entry["eprint"] == "1512.03385"  # kept, as REF015 recommends
    assert "was published" in result.stderr


def test_prefer_preprint() -> None:
    entry = entry_of(fetch("1512.03385", "--prefer", "preprint"))
    assert entry["type"] == "misc"
    assert entry["eprint"] == "1512.03385"
    assert entry["year"] == "2015"


def test_a_doi_that_does_not_exist() -> None:
    result = fetch("10.1109/CVPR.2016.999999")
    assert result.exit_code == EXIT_FINDINGS
    assert result.stdout == ""
    assert "does not exist" in result.stderr


def test_title_search() -> None:
    result = fetch("--title", "Attention Is All You Need", "--author", "Vaswani, Ashish")
    assert result.exit_code == EXIT_OK
    entry = entry_of(result)
    assert entry["key"] == "vaswani2017attention"
    assert entry["booktitle"] == "NIPS"  # dblp keeps the venue name of the time


def test_a_title_nobody_has() -> None:
    result = fetch("--title", "Quantum Gradient Folding for Sparse Mixture-of-Experts Transformers")
    assert result.exit_code == EXIT_FINDINGS
    assert "not found" in result.stderr


def test_json_output_for_agents() -> None:
    result = fetch("10.1109/CVPR.2016.90", "--format", "json", "--key", "resnet")
    payload = json.loads(result.stdout)
    assert payload["status"] == "found"
    assert payload["source"] == "crossref"
    assert "@inproceedings{resnet," in payload["bibtex"]


def test_usage_errors() -> None:
    assert fetch().exit_code == EXIT_USAGE
    assert fetch("not an identifier").exit_code == EXIT_USAGE
    assert fetch("10.1/x", "--title", "both").exit_code == EXIT_USAGE


def test_offline_without_cache_cannot_answer() -> None:
    result = fetch("10.1109/CVPR.2016.90", "--offline")
    assert result.exit_code == EXIT_INCOMPLETE
    assert "unavailable" in result.stderr


def test_a_retracted_work_comes_with_a_warning() -> None:
    result = fetch("10.1016/S0140-6736(97)11096-0")
    assert result.exit_code == EXIT_OK
    assert "warning: this work is marked" in result.stderr
    assert "retracted" in result.stderr
    entry = entry_of(result)
    assert entry["key"].startswith("wakefield1998ileal")  # not "...retracted"
    payload = json.loads(fetch("10.1016/S0140-6736(97)11096-0", "--format", "json").stdout)
    assert "retracted" in payload["status_flags"]


def test_json_found_prints_nothing_on_stderr() -> None:
    result = fetch("10.1109/CVPR.2016.90", "--format", "json")
    assert result.exit_code == EXIT_OK
    assert result.stderr == ""
