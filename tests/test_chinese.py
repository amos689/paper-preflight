"""Chinese-language works cited in English (paper_preflight.chinese and where it is used)."""

from pathlib import Path

import pytest

from paper_preflight import chinese
from paper_preflight.bib.ids import extract_identifiers
from paper_preflight.bib.parse import parse_bib_text
from paper_preflight.findings import Severity
from paper_preflight.match import EntryInfo, check_title
from paper_preflight.resolve import Evidence
from paper_preflight.sources import crossref
from paper_preflight.sources.record import Person, SourceRecord
from paper_preflight.verdict import Reason, Verdict, assess, non_latin

YEAR = 2026


def info(bib: str) -> EntryInfo:
    (entry,) = parse_bib_text(bib, Path("refs.bib")).entries
    return EntryInfo.from_entry(entry)


@pytest.mark.parametrize(
    ("fields", "translated"),
    [
        ("title = {Research on Graph Clustering (in Chinese)}, journal = {Some Journal}", True),
        ("title = {Research on Graph Clustering}, note = {in Chinese}", True),
        ("title = {Research on Graph Clustering}, journal = {Chinese Journal of Computers}", True),
        ("title = {Research on Graph Clustering}, journal = {Jisuanji Xuebao}", True),
        ("title = {Research on Graph Clustering}, language = {chinese}", True),
        # a title's own words, not a mark
        ("title = {Nominal Expressions in Chinese}, journal = {J. East Asian Linguistics}", False),
        (
            "title = {Research on Graph Clustering}, journal = {Journal of Software Engineering}",
            False,
        ),
    ],
)
def test_a_chinese_work_cited_in_english_is_recognised(fields: str, translated: bool) -> None:
    found = info(f"@article{{k, author = {{Wang, Lei}}, {fields}, year = {{2021}}}}")
    assert found.translated is translated


def test_the_language_mark_is_not_part_of_the_title() -> None:
    found = info("@article{k, title = {Research on Graph Clustering (in Chinese)}, year = {2021}}")
    assert found.title == "Research on Graph Clustering"
    assert chinese.strip_mark("Nominal Expressions in Chinese") == "Nominal Expressions in Chinese"


def test_a_translated_work_nobody_indexes_is_not_called_not_found() -> None:
    (entry,) = parse_bib_text(
        "@article{k, author = {Wang, Lei and Li, Ming}, title = {A Survey of Deep Graph"
        " Clustering Methods for Social Networks}, journal = {Journal of Software},"
        " year = {2021}}",
        Path("refs.bib"),
    ).entries
    evidence = Evidence(entry.key, EntryInfo.from_entry(entry), extract_identifiers(entry))
    evidence.searched = {"dblp", "crossref"}
    evidence.negative = {"dblp", "crossref"}
    result = assess(entry, evidence, current_year=YEAR)
    assert result.verdict is Verdict.CANNOT_DETERMINE
    assert Reason.TRANSLATED_CHINESE_WORK in result.reasons


def test_chinese_script_against_latin_script_is_no_title_difference() -> None:
    record = SourceRecord(
        source="doiorg:istic", source_id="x", title="基于深度学习的图聚类方法研究"
    )
    assert check_title("Research on Graph Clustering Based on Deep Learning", record).status == (
        "unknown"
    )
    # and a Chinese title with English acronyms is Chinese, not Latin
    assert non_latin("基于BERT和BiLSTM-CRF的中文命名实体识别")


def test_a_translated_title_worded_otherwise_is_only_worth_a_look() -> None:
    (entry,) = parse_bib_text(
        "@article{k, author = {Wang, Lei}, title = {Text Big Data Content Understanding and"
        " Development Based on Feature Learning}, journal = {Big Data Research},"
        " note = {in Chinese}, year = {2015}}",
        Path("refs.bib"),
    ).entries
    record = SourceRecord(
        source="crossref", source_id="10.1/x", authors=(Person("Wang", "Lei"),), year=2015,
        title="Text Big Data Content Understanding and Development Trend Based on Feature Learning",
        years=frozenset({2015}),
    )  # fmt: skip
    evidence = Evidence(entry.key, EntryInfo.from_entry(entry), extract_identifiers(entry))
    evidence.candidates = [record]
    result = assess(entry, evidence, current_year=YEAR)
    titles = [f for f in result.findings if f.rule_id == "REF012"]
    assert titles
    assert all(f.severity is Severity.INFO for f in titles)


def test_a_chinese_journals_record_is_read_as_such_for_a_translated_entry() -> None:
    # Crossref's backfile records of Chinese-language journals: a whole name in the family name,
    # the first author only, another author order
    (entry,) = parse_bib_text(
        "@article{k, author = {Jia, Zhengmao and Wang, Yuncai and Li, Ming}, title = {Chaotic"
        " Synchronization of Semiconductor Lasers with Optical Feedback}, journal = {Acta Physica"
        " Sinica}, year = {2010}, doi = {10.7498/aps.59.1}}",
        Path("refs.bib"),
    ).entries
    record = SourceRecord(
        source="crossref", source_id="10.7498/aps.59.1",
        title="Chaotic Synchronization of Semiconductor Lasers with Optical Feedback",
        authors=(Person("Jia Zheng-Mao"),), year=2010, years=frozenset({2010}),
        identifiers={"doi": "10.7498/aps.59.1"},
    )  # fmt: skip
    evidence = Evidence(entry.key, EntryInfo.from_entry(entry), extract_identifiers(entry))
    evidence.anchored = [record]
    result = assess(entry, evidence, current_year=YEAR)
    assert result.verdict is Verdict.VERIFIED
    assert not [f for f in result.findings if f.rule_id in {"REF010", "REF011"}]


def test_a_chinese_journals_doi_names_its_year() -> None:
    # J. Computer Applications 32(2), 2012: Science Press's DOI names 2012, Crossref has 2013
    item = {
        "DOI": "10.3724/SP.J.1087.2012.00322", "type": "journal-article",
        "title": ["User behavior similarity analysis of location based social network"],
        "issued": {"date-parts": [[2013, 1]]},
    }  # fmt: skip
    assert crossref.parse_work(item).years == {2012, 2013}
