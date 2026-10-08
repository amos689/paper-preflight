"""PubMed: PMIDs checked against their registry (recorded esummary answers, see fake_web.py)."""

import json
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from paper_preflight.cli import app
from paper_preflight.sources.pubmed import parse_summary

from .fake_web import FakeWeb

FIXTURE = Path(__file__).parent / "fixtures" / "sources" / "pubmed" / "esummary_pubmed.json"
WAKEFIELD = (
    "Ileal-lymphoid-nodular hyperplasia, non-specific colitis, and pervasive developmental "
    "disorder in children"
)
pytestmark = pytest.mark.usefixtures("fast")
runner = CliRunner()


def recorded(uid: str) -> dict[str, Any]:
    return dict(json.loads(FIXTURE.read_text(encoding="utf-8"))["result"][uid])


def test_summary_parsing() -> None:
    record = parse_summary(recorded("9500320"))
    assert record.title == WAKEFIELD  # PubMed's closing period is not part of the title
    assert (record.authors[0].family, record.authors[0].given) == ("Wakefield", "A. J.")
    assert record.authors[-1].family == "Walker-Smith"
    assert (record.year, record.venue) == (1998, "Lancet")  # "Lancet (London, England)"
    assert record.doi == "10.1016/s0140-6736(97)11096-0"
    assert record.status == frozenset({"retracted"})  # "Retracted Publication"
    other = parse_summary(recorded("31452104"))
    assert other.title == "Molegro Virtual Docker for Docking"
    assert other.status == frozenset()


def test_a_translated_title_loses_its_brackets() -> None:
    item = recorded("31452104") | {"title": "[Docking with a virtual docker]."}
    assert parse_summary(item).title == "Docking with a virtual docker"


BIB = f"""@article{{wakefield,
  title = {{{WAKEFIELD}}},
  author = {{Wakefield, A. J. and Murch, S. H. and Anthony, A. and others}},
  journal = {{The Lancet}}, year = {{1998}}, pmid = {{9500320}},
}}

@article{{invented,
  title = {{A Randomised Trial of Something That Was Never Studied at All}},
  author = {{Doe, Jane and Roe, Richard}}, journal = {{BMJ}}, year = {{2019}},
  pmid = {{99999999}},
}}
"""


def test_pmids_are_checked_against_pubmed(tmp_path: Path, recorded_web: FakeWeb) -> None:
    bib = tmp_path / "refs.bib"
    bib.write_text(BIB, encoding="utf-8")
    out = tmp_path / "report.json"
    runner.invoke(app, ["check", str(bib), "--format", "json", "--output", str(out)])
    payload = json.loads(out.read_text(encoding="utf-8"))
    refs = {r["key"]: r for r in payload["references"]}
    found = {(f["rule"], f.get("key")) for f in payload["findings"]}
    assert refs["wakefield"]["matched"]["id"] == "9500320"
    assert ("REF004", "wakefield") in found  # PubMed marks it retracted
    retraction = next(f for f in payload["findings"] if f["rule"] == "REF004")
    assert "reported by PubMed" in retraction["message"]["en"]
    assert ("REF002", "invented") in found  # PubMed has no such PMID
    asked = [r for r in recorded_web.requests if r.url.host == "eutils.ncbi.nlm.nih.gov"]
    assert len(asked) == 1  # both PMIDs in one request


PMC_BIB = """@article{genbank,
  title = {GenBank}, author = {Benson, Dennis A. and Cavanaugh, Mark and Clark, Karen},
  journal = {Nucleic Acids Research}, year = {2013}, pmcid = {PMC3531190},
}

@article{nopmc,
  title = {A Study That Never Appeared in Any Journal at All},
  author = {Doe, Jane and Roe, Richard}, journal = {PLoS One}, year = {2018},
  pmcid = {PMC99999999},
}
"""


def test_pmcids_are_checked_through_pubmed_central(tmp_path: Path) -> None:
    bib = tmp_path / "refs.bib"
    bib.write_text(PMC_BIB, encoding="utf-8")
    out = tmp_path / "report.json"
    runner.invoke(app, ["check", str(bib), "--format", "json", "--output", str(out)])
    payload = json.loads(out.read_text(encoding="utf-8"))
    refs = {r["key"]: r for r in payload["references"]}
    # PMC3531190 is PMID 23193287, whose PubMed record anchors the entry
    assert refs["genbank"]["verdict"] == "verified"
    assert refs["genbank"]["matched"]["id"] == "23193287"
    dead = [f for f in payload["findings"] if f["rule"] == "REF002"]
    assert [f["key"] for f in dead] == ["nopmc"]
    assert "PubMed Central has no record of it" in dead[0]["message"]["en"]


@pytest.mark.anyio
async def test_an_ncbi_key_is_sent_but_never_stored(tmp_path: Path, recorded_web: FakeWeb) -> None:
    from paper_preflight.bib.parse import parse_bib_text
    from paper_preflight.check import VerifyOptions, verify_entries

    entries = parse_bib_text(BIB, Path("refs.bib")).entries
    cache = tmp_path / "c.sqlite3"
    options = VerifyOptions(cache_path=cache, environ={"NCBI_API_KEY": "fictional-ncbi-key"})
    _, verdicts, _ = await verify_entries(entries, options)
    assert any(f.rule_id == "REF004" for f in verdicts["wakefield"].findings)
    asked = [r for r in recorded_web.requests if r.url.host == "eutils.ncbi.nlm.nih.gov"]
    assert [r.url.params.get("api_key") for r in asked] == ["fictional-ncbi-key"]
    assert b"fictional-ncbi-key" not in cache.read_bytes()  # not in a cache key, nor an answer
