"""Parsers against real responses recorded in spikes S1-S4 (tests/fixtures/sources)."""

import json
from pathlib import Path
from typing import Any

from paper_preflight.sources import arxiv, crossref, datacite, dblp, doiorg, openalex
from paper_preflight.sources.record import Person

FIXTURES = Path(__file__).parent / "fixtures" / "sources"


def load(name: str) -> Any:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def text(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def surnames(record: Any) -> list[str]:
    return [p.family for p in record.authors]


def test_person_from_display() -> None:
    assert Person.from_display("Jian Sun 0001") == Person(family="Sun", given="Jian")
    assert Person.from_display("Vaswani, Ashish") == Person(family="Vaswani", given="Ashish")
    assert Person.from_display("Martin Luther King Jr.") == Person(
        family="King", given="Martin Luther"
    )
    assert Person.from_display("Plato") == Person(family="Plato")


def test_doira_routing() -> None:
    answers = {a.doi.lower(): a for a in doiorg.parse_doira(load("doiorg/doira_multi.json"))}
    assert answers["10.1109/cvpr.2016.90"].agency == "Crossref"
    assert answers["10.48550/arxiv.1706.03762"].agency == "DataCite"
    assert answers["10.1109/cvpr.2016.999999"].exists is False
    assert answers["10.1162/tacl\\_a\\_00276"].exists is False  # LaTeX escapes never exist


def test_crossref_work_cvpr() -> None:
    record = crossref.parse_work(load("crossref/work_cvpr.json")["message"])
    assert record.doi == "10.1109/cvpr.2016.90"
    assert record.title == "Deep Residual Learning for Image Recognition"
    assert surnames(record) == ["He", "Zhang", "Ren", "Sun"]
    assert record.year == 2016
    assert record.pages == "770-778"
    assert record.identifiers["doi_prefix"] == "10.1109"
    assert not record.status


def test_crossref_retraction_from_updated_by() -> None:
    record = crossref.parse_work(load("crossref/work_wakefield.json")["message"])
    assert "retracted" in record.status
    assert "correction" in record.status
    assert any("retraction-watch" in s for s in record.status_sources)
    assert record.year == 1998


def test_crossref_whitespace_and_batch() -> None:
    tacl = crossref.parse_work(load("crossref/work_tacl.json")["message"])
    assert tacl.title == "Natural Questions: A Benchmark for Question Answering Research"
    batch = crossref.parse_work_list(load("crossref/batch_filter_doi.json"))
    assert {r.doi for r in batch} >= {"10.1109/cvpr.2016.90", "10.18653/v1/n19-1423"}


def test_crossref_fake_duplicate_is_posted_content_with_suspicious_prefix() -> None:
    record = crossref.parse_work(load("crossref/work_65215_ysbyhc05.json")["message"])
    assert record.title == "Attention Is All You Need"
    assert record.identifiers["doi_prefix"] == "10.65215"
    assert record.work_type == "posted-content"
    assert record.year == 2025


def test_datacite_arxiv_doi() -> None:
    (record,) = datacite.parse_dois(load("datacite/dc_arxiv_attn.json"))
    assert record.doi == "10.48550/arxiv.1706.03762"
    assert record.identifiers["arxiv"] == "1706.03762"
    assert surnames(record)[:3] == ["Vaswani", "Shazeer", "Parmar"]
    assert record.year == 2017
    (gelu,) = datacite.parse_dois(load("datacite/dc_arxiv_gelu.json"))
    assert gelu.title == "Gaussian Error Linear Units (GELUs)"


def test_arxiv_feed_versions_and_missing_ids() -> None:
    records = {r.source_id: r for r in arxiv.parse_feed(text("arxiv/idlist_multi.xml"))}
    assert "1706.03762" in records
    attention = records["1706.03762"]
    assert attention.title == "Attention Is All You Need"
    assert attention.year == 2017
    assert attention.identifiers["arxiv_version"].startswith("v")
    versions = arxiv.parse_feed(text("arxiv/idlist_gelu_versions.xml"))
    titles = list(dict.fromkeys(r.title for r in versions))
    assert titles[0].startswith("Bridging Nonlinearities")
    assert titles[-1] == "Gaussian Error Linear Units (GELUs)"
    assert arxiv.parse_feed(text("arxiv/idlist_nonexistent.xml")) == []
    assert arxiv.total_results(text("arxiv/search_ti_t8.xml")) == 0


def test_arxiv_withdrawn_and_journal_ref() -> None:
    records = arxiv.parse_feed(text("arxiv/idlist_withdrawn_versions_and_jref.xml"))
    assert any("withdrawn" in r.status for r in records)
    with_jref = [r for r in records if r.relations.get("journal_ref")]
    assert with_jref
    assert with_jref[0].doi == "10.1016/j.physletb.2012.08.020"


def test_dblp_prefix_candidates_and_full_records() -> None:
    candidates = dblp.parse_title_candidates(load("dblp/prefix_t1.json"))
    pubs = {pub for pub, _ in candidates}
    assert "https://dblp.org/rec/conf/nips/VaswaniSPUJGKP17" in pubs
    assert all(not title.endswith(".") or title.endswith("..") for _, title in candidates)
    records = dblp.parse_full_records(load("dblp/full_records.json"))
    resnet = records["conf/cvpr/HeZRS16"]
    assert resnet.title == "Deep Residual Learning for Image Recognition"
    assert resnet.doi == "10.1109/cvpr.2016.90"
    assert surnames(resnet) == ["He", "Zhang", "Ren", "Sun"]  # homonym suffix "0001" removed
    assert resnet.venue == "CVPR"
    assert dblp.parse_title_candidates(load("dblp/prefix_t8.json")) == []


def test_dblp_prefix_range() -> None:
    assert dblp.prefix_range("Attention Is   All You Need") == (
        "attention is all you need",
        "attention is all you neee",
    )
    query = dblp.title_prefix_query('A "quoted" title')
    assert '\\"quoted\\"' in query


def test_openalex_retraction_and_pollution() -> None:
    wakefield = openalex.parse_work(load("openalex/work_doi_wakefield.json"))
    assert "retracted" in wakefield.status
    assert wakefield.doi == "10.1016/s0140-6736(97)11096-0"
    polluted = openalex.parse_work(load("openalex/work_W2626778328_attention.json"))
    # OpenAlex merged fake 10.65215 copies into the canonical Attention record (spike S3)
    assert polluted.doi is not None
    assert polluted.doi.startswith("10.65215/")
    assert polluted.year == 2025


def test_csl_parsing() -> None:
    record = doiorg.parse_csl(
        "10.48550/arXiv.1706.03762", load("doiorg/cn_datacite_arxiv.json"), "DataCite"
    )
    assert record.title == "Attention Is All You Need"
    assert record.year == 2017
    assert record.authors[0].family == "Vaswani"
