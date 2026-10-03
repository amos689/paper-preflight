import json
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from paper_preflight.bib.ids import extract_identifiers
from paper_preflight.bib.parse import parse_bib_text
from paper_preflight.bibtex import citation_key, protect_title, render
from paper_preflight.match import EntryInfo
from paper_preflight.resolve import Evidence
from paper_preflight.sources import arxiv, crossref, dblp
from paper_preflight.sources.record import Person, SourceRecord
from paper_preflight.verdict import Verdict, assess

FIXTURES = Path(__file__).parent / "fixtures" / "sources"
TODAY = date(2026, 10, 3)


def load(name: str) -> Any:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def crossref_record(doi: str) -> SourceRecord:
    items = load("crossref/batch_filter_doi.json")["message"]["items"]
    (item,) = [i for i in items if i["DOI"].lower() == doi]
    return crossref.parse_work(item)


def arxiv_record(arxiv_id: str) -> SourceRecord:
    feed = (FIXTURES / "arxiv/idlist_multi.xml").read_text(encoding="utf-8")
    (record,) = [r for r in arxiv.parse_feed(feed) if r.identifiers["arxiv"] == arxiv_id]
    return record


def dblp_record(key: str) -> SourceRecord:
    return dblp.parse_full_records(load("dblp/full_records.json"))[key]


RECORDS = {
    "crossref ResNet (CVPR)": lambda: crossref_record("10.1109/cvpr.2016.90"),
    "crossref NQ (TACL)": lambda: crossref_record("10.1162/tacl_a_00276"),
    "crossref Wakefield (Lancet)": lambda: crossref_record("10.1016/s0140-6736(97)11096-0"),
    "arxiv GELU": lambda: arxiv_record("1606.08415"),
    "dblp Attention (NeurIPS)": lambda: dblp_record("conf/nips/VaswaniSPUJGKP17"),
    "dblp BERT (NAACL)": lambda: dblp_record("conf/naacl/DevlinCLT19"),
}


@pytest.mark.parametrize("name", sorted(RECORDS))
def test_a_rendered_entry_verifies_clean_against_its_own_record(name: str) -> None:
    # What `bib fetch` writes must pass `check` against the record it came from.
    record = RECORDS[name]()
    (entry,) = parse_bib_text(render(record, today=TODAY), Path("refs.bib")).entries
    evidence = Evidence(entry.key, EntryInfo.from_entry(entry), extract_identifiers(entry))
    evidence.anchored = [record]
    result = assess(entry, evidence, current_year=2026)
    assert result.verdict is Verdict.VERIFIED, (name, [f.message.en for f in result.findings])
    assert not [f for f in result.findings if f.rule_id.startswith("REF01")], name


def test_conference_paper_fields() -> None:
    text = render(crossref_record("10.1109/cvpr.2016.90"), today=TODAY)
    assert text.startswith(
        "% Verified with paper-preflight against Crossref (10.1109/cvpr.2016.90), 2026-10-03\n"
        "@inproceedings{he2016deep,\n"
    )
    assert "author    = {He, Kaiming and Zhang, Xiangyu and Ren, Shaoqing and Sun, Jian}," in text
    assert "doi       = {10.1109/cvpr.2016.90}," in text
    assert "booktitle" in text
    assert "pages" not in text  # the recorded item has no pages: nothing is filled in


@pytest.mark.parametrize("pages", ["770-778", "770–778", "770 - 778"])
def test_page_ranges_use_double_hyphens(pages: str) -> None:
    record = SourceRecord(
        source="crossref", source_id="x", title="T", year=2016, pages=pages,
        work_type="journal-article",
    )  # fmt: skip
    assert "pages = {770--778}," in render(record, today=TODAY)


def test_arxiv_preprint_is_misc_with_eprint_and_no_arxiv_doi() -> None:
    text = render(arxiv_record("1606.08415"), today=TODAY)
    assert "@misc{hendrycks2016gaussian," in text
    assert "eprint        = {1606.08415}," in text
    assert "archivePrefix = {arXiv}," in text
    assert "10.48550" not in text


def test_truncated_author_lists_end_in_others_and_specials_are_escaped() -> None:
    record = SourceRecord(
        source="crossref", source_id="10.1/x", title="Q&A over 50% of BERT's ImageNet",
        authors=(Person("Smith", "Ann"), Person("World Health Organization",
                                                literal="World Health Organization")),
        authors_complete=False, year=2020, work_type="journal-article", venue="J. of R&D",
        identifiers={"doi": "10.1/x"},
    )  # fmt: skip
    text = render(record, today=TODAY)
    assert "author  = {Smith, Ann and {World Health Organization} and others}," in text
    assert r"title   = {{Q\&A} over 50\% of {BERT's} {ImageNet}}," in text
    assert r"journal = {J. of R\&D}," in text
    (entry,) = parse_bib_text(text, Path("refs.bib")).entries
    assert entry.text("title") == "Q&A over 50% of BERT's ImageNet"


@pytest.mark.parametrize(
    ("title", "key"),
    [
        ("Deep Residual Learning for Image Recognition", "he2016deep"),
        ("On Pre-Training for Visuo-Motor Control", "he2016pretraining"),
        ("The Élan of Tiny Models", "he2016elan"),
    ],
)
def test_citation_keys(title: str, key: str) -> None:
    record = SourceRecord(
        source="crossref",
        source_id="x",
        title=title,
        authors=(Person("He", "Kaiming"),),
        year=2016,
    )
    assert citation_key(record) == key


def test_protect_title_keeps_inner_capitals_only() -> None:
    assert protect_title("BERT: Pre-training of Deep Bidirectional Transformers") == (
        "{BERT:} Pre-training of Deep Bidirectional Transformers"
    )
