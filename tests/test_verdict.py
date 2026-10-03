from dataclasses import replace
from pathlib import Path

import httpx
import pytest

from paper_preflight.bib.ids import extract_identifiers
from paper_preflight.bib.parse import BibEntry, parse_bib_file, parse_bib_text
from paper_preflight.cache import Cache
from paper_preflight.findings import Severity
from paper_preflight.match import EntryInfo
from paper_preflight.resolve import Evidence, Sources, resolve
from paper_preflight.sources.doiorg import AgencyAnswer
from paper_preflight.sources.record import Person, SourceRecord
from paper_preflight.verdict import Assessment, Reason, Verdict, assess, assess_all, run_findings

from .fake_web import FakeWeb

pytestmark = pytest.mark.usefixtures("fast")

DEMO = Path(__file__).parent.parent / "examples" / "demo-paper" / "refs.bib"
YEAR = 2026

# examples/demo-paper/EXPECTED.md, online rows. lecun1998gradient is left out: it only exists to
# test CIT003, and its DOI is not in the recorded Crossref batch.
EXPECTED: dict[str, tuple[Verdict, set[str]]] = {
    "vaswani2017attention": (Verdict.VERIFIED, set()),
    "he2016deep": (Verdict.VERIFIED, set()),
    "he2015residual": (Verdict.VERIFIED, {"REF015"}),
    "devlin2019bert": (Verdict.IDENTIFIER_CONFLICT, {"REF001"}),
    "kingma2015adam": (Verdict.METADATA_MISMATCH, {"REF013"}),
    "hendrycks2016gelu": (Verdict.VERIFIED, set()),
    "lindqvist2024quantum": (Verdict.NOT_FOUND, {"REF003"}),
    "wakefield1998ileal": (Verdict.VERIFIED, {"REF004", "REF005"}),
    "goodfellow2016deep": (Verdict.CANNOT_DETERMINE, {"REF090"}),
    "zhou2016ml": (Verdict.CANNOT_DETERMINE, {"REF090"}),
    "tacl2019example": (Verdict.VERIFIED, set()),
}


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


async def run_demo(web: FakeWeb) -> tuple[dict[str, Assessment], dict[str, Evidence]]:
    entries = [e for e in parse_bib_file(DEMO).entries if e.key in EXPECTED]
    async with httpx.AsyncClient(transport=httpx.MockTransport(web)) as http:
        evidence = await resolve(entries, Sources.create(http, Cache(None), environ={}))
    return assess_all(entries, evidence, current_year=YEAR), evidence


@pytest.fixture
async def demo() -> dict[str, Assessment]:
    assessments, _ = await run_demo(FakeWeb())
    return assessments


# ---------------------------------------------------------------- the demo paper, end to end


@pytest.mark.anyio
async def test_demo_paper_verdicts(demo: dict[str, Assessment]) -> None:
    actual = {key: (a.verdict, {f.rule_id for f in a.findings}) for key, a in demo.items()}
    assert actual == EXPECTED


@pytest.mark.anyio
async def test_messages_are_complete_in_both_languages(demo: dict[str, Assessment]) -> None:
    for assessment in demo.values():
        for finding in assessment.findings:
            for text in (finding.message.en, finding.message.zh):
                assert "{" not in text, text
                assert "None" not in text, text
            assert "fabricat" not in finding.message.en.lower()  # ADR-0002: neutral wording


@pytest.mark.anyio
async def test_correct_entry_is_bound_to_dblp_not_to_fake_crossref_copies(
    demo: dict[str, Assessment],
) -> None:
    vaswani = demo["vaswani2017attention"]
    assert vaswani.record is not None
    assert (vaswani.record.source, vaswani.record.source_id) == (
        "dblp", "conf/nips/VaswaniSPUJGKP17",
    )  # fmt: skip


@pytest.mark.anyio
async def test_wrong_doi_points_at_the_doi_field(demo: dict[str, Assessment]) -> None:
    (finding,) = demo["devlin2019bert"].findings
    assert finding.field == "doi"
    assert finding.location is not None
    bert = next(e for e in parse_bib_file(DEMO).entries if e.key == "devlin2019bert")
    doi_line = bert.fields["doi"].line
    assert finding.location.line == doi_line
    assert "Deep Residual Learning for Image Recognition" in finding.message.en


@pytest.mark.anyio
async def test_wrong_year_found_by_title_search(demo: dict[str, Assessment]) -> None:
    adam = demo["kingma2015adam"]
    (finding,) = adam.findings
    assert finding.severity is Severity.WARNING
    assert finding.data["year"] == 2016
    assert finding.data["found_years"] == "2014, 2015"  # dblp key conf/iclr/KingmaB14


@pytest.mark.anyio
async def test_flags_and_reasons(demo: dict[str, Assessment]) -> None:
    assert demo["he2015residual"].flags == {"preprint_published"}
    (published,) = demo["he2015residual"].findings
    assert published.data["doi"] == "10.1109/cvpr.2016.90"
    assert "retracted" in demo["wakefield1998ileal"].flags
    retraction = next(f for f in demo["wakefield1998ileal"].findings if f.rule_id == "REF004")
    assert retraction.severity is Severity.ERROR
    assert demo["goodfellow2016deep"].reasons == (Reason.GREY_LITERATURE,)
    assert Reason.NON_LATIN_UNSUPPORTED in demo["zhou2016ml"].reasons


@pytest.mark.anyio
async def test_unavailable_source_is_not_a_negative_answer() -> None:
    web = FakeWeb()
    web.fail("sparql.dblp.org", "html")
    assessments, evidence = await run_demo(web)
    fabricated = assessments["lindqvist2024quantum"]
    assert fabricated.verdict is Verdict.CANNOT_DETERMINE
    assert fabricated.reasons == (Reason.SOURCES_UNAVAILABLE,)
    assert "REF003" not in {f.rule_id for f in fabricated.findings}
    (incomplete,) = run_findings(evidence)
    assert incomplete.rule_id == "RUN001"
    assert "dblp (challenge)" in incomplete.message.en


@pytest.mark.anyio
async def test_arxiv_outage_falls_back_to_datacite() -> None:
    # Seen live on 2026-10-03: the arXiv API answered 429. DataCite holds every arXiv paper as
    # 10.48550/arXiv.<id>, so both preprints are still verified.
    web = FakeWeb()
    web.fail("export.arxiv.org", "429")
    assessments, evidence = await run_demo(web)
    preprint = assessments["he2015residual"]
    assert preprint.record is not None
    assert preprint.record.source == "datacite"
    assert (preprint.verdict, rules(preprint)) == (Verdict.VERIFIED, {"REF015"})
    gelu = assessments["hendrycks2016gelu"]
    assert (gelu.verdict, rules(gelu)) == (Verdict.VERIFIED, set())
    # withdrawals are only known to arXiv: the run still says arXiv was unavailable
    (incomplete,) = run_findings(evidence)
    assert "arXiv (rate_limited)" in incomplete.message.en


@pytest.mark.anyio
async def test_arxiv_outage_does_not_turn_a_preprint_year_into_an_error() -> None:
    # With arXiv and DataCite both down, the preprint entry is found by title search and bound
    # to the published CVPR 2016 record. Its year (2015) is the preprint's, which is expected;
    # the right finding is REF015, not a year mismatch (a false REF013 seen live on 2026-10-03).
    web = FakeWeb()
    web.fail("export.arxiv.org", "429")
    web.fail("api.datacite.org", "429")
    assessments, _ = await run_demo(web)
    preprint = assessments["he2015residual"]
    assert preprint.record is not None
    assert preprint.record.source == "crossref"  # the published version, found by title
    assert (preprint.verdict, rules(preprint)) == (Verdict.VERIFIED, {"REF015"})
    gelu = assessments["hendrycks2016gelu"]
    assert (gelu.verdict, gelu.reasons) == (Verdict.CANNOT_DETERMINE, (Reason.SOURCES_UNAVAILABLE,))


@pytest.mark.anyio
async def test_complete_run_has_no_run_finding() -> None:
    _, evidence = await run_demo(FakeWeb())
    assert run_findings(evidence) == []


# ---------------------------------------------------------------- focused cases


ANN, BOB, CAROL = (Person("Smith", "Ann"), Person("Jones", "Bob"), Person("Lee", "Carol"))
TITLE = "Robust Sparse Attention for Long Document Summarization"
CS_ENTRY = f"""
@inproceedings{{smith2023robust,
  title = {{{TITLE}}},
  author = {{Smith, Ann and Jones, Bob and Lee, Carol}},
  booktitle = {{Proceedings of ACL}},
  year = {{2023}},
  doi = {{10.1234/acl.2023.1}},
}}
"""


def bib(text: str) -> BibEntry:
    return parse_bib_text(text, Path("refs.bib")).entries[0]


def evidence_for(entry: BibEntry, **values: object) -> Evidence:
    item = Evidence(entry.key, EntryInfo.from_entry(entry), extract_identifiers(entry))
    for name, value in values.items():
        setattr(item, name, value)
    return item


def record(
    title: str = TITLE,
    authors: tuple[Person, ...] = (ANN, BOB, CAROL),
    year: int = 2023,
    source: str = "crossref",
    **extra: object,
) -> SourceRecord:
    identifiers = {"doi": "10.1234/acl.2023.1"} if source == "crossref" else {}
    return SourceRecord(
        source=source, source_id=f"{source}:{title[:10]}", title=title, authors=authors,
        year=year, years=frozenset({year}), identifiers=identifiers, **extra,  # type: ignore[arg-type]
    )  # fmt: skip


def rules(assessment: Assessment) -> set[str]:
    return {f.rule_id for f in assessment.findings}


def test_identifier_record_that_agrees_is_verified() -> None:
    entry = bib(CS_ENTRY)
    result = assess(entry, evidence_for(entry, anchored=[record()]), current_year=YEAR)
    assert (result.verdict, rules(result)) == (Verdict.VERIFIED, set())


def test_dead_doi_and_nothing_found_gives_both_findings() -> None:
    entry = bib(CS_ENTRY)
    item = evidence_for(
        entry,
        doi_agency={"10.1234/acl.2023.1": AgencyAnswer("10.1234/acl.2023.1", None, False)},
        searched={"dblp", "crossref"},
        negative={"dblp", "crossref"},
    )
    result = assess(entry, item, current_year=YEAR)
    assert result.verdict is Verdict.NOT_FOUND
    assert rules(result) == {"REF002", "REF003"}


def test_dead_doi_but_work_found_by_title_is_a_metadata_problem() -> None:
    entry = bib(CS_ENTRY)
    item = evidence_for(
        entry,
        doi_agency={"10.1234/acl.2023.1": AgencyAnswer("10.1234/acl.2023.1", None, False)},
        candidates=[record(source="dblp")],
        searched={"dblp", "crossref"},
        negative={"crossref"},
    )
    result = assess(entry, item, current_year=YEAR)
    assert result.verdict is Verdict.METADATA_MISMATCH
    assert rules(result) == {"REF002"}


@pytest.mark.parametrize(
    ("unavailable", "reason"),
    [
        ({"dblp": "offline", "crossref": "offline"}, Reason.OFFLINE_MODE),
        ({"dblp": "rate_limited"}, Reason.SOURCES_UNAVAILABLE),
    ],
)
def test_unavailability_reasons(unavailable: dict[str, str], reason: Reason) -> None:
    entry = bib(CS_ENTRY.replace("  doi = {10.1234/acl.2023.1},\n", ""))
    item = evidence_for(
        entry, searched={"dblp", "crossref"}, negative={"crossref"}, unavailable=unavailable
    )
    result = assess(entry, item, current_year=YEAR)
    assert (result.verdict, result.reasons) == (Verdict.CANNOT_DETERMINE, (reason,))
    assert rules(result) == {"REF090"}


def test_too_new_to_be_indexed() -> None:
    entry = bib(CS_ENTRY.replace("  doi = {10.1234/acl.2023.1},\n", "").replace("2023", "2026"))
    item = evidence_for(entry, searched={"dblp", "crossref"}, negative={"dblp", "crossref"})
    result = assess(entry, item, current_year=YEAR)
    assert result.reasons == (Reason.TOO_NEW,)


@pytest.mark.parametrize(
    ("url", "verdict"),
    [
        # a real paper in a society's own proceedings (2607.00307v1, Sese & Galapon 2022)
        ("https://proceedings.spp-online.org/article/view/SPP-2022", Verdict.CANNOT_DETERMINE),
        # a site the sources index: a paper linked there that none of them knows is missing
        ("https://proceedings.mlr.press/v202/smith23a.html", Verdict.NOT_FOUND),
        ("https://www.aclweb.org/anthology/2023.acl-long.1", Verdict.NOT_FOUND),
    ],
)  # fmt: skip
def test_a_link_to_a_site_no_source_indexes_is_no_proof_of_absence(
    url: str, verdict: Verdict
) -> None:
    entry = bib(NO_DOI.replace("  year = {2023},", f"  year = {{2023}}, url = {{{url}}},"))
    item = evidence_for(entry, searched={"dblp", "crossref"}, negative={"dblp", "crossref"})
    result = assess(entry, item, current_year=YEAR)
    assert result.verdict is verdict
    if verdict is Verdict.CANNOT_DETERMINE:
        assert result.reasons == (Reason.UNINDEXED_LINK,)


@pytest.mark.parametrize(("year", "reasons"), [(1969, (Reason.OLD_WORK,)), (1990, ())])
def test_an_old_work_nobody_knows_is_not_called_not_found(
    year: int, reasons: tuple[Reason, ...]
) -> None:
    # real papers of the 1950s and 60s (Barenblatt 1952, Bluman & Cole 1969) are in no index
    entry = bib(NO_DOI.replace("2023", str(year)))
    item = evidence_for(entry, searched={"dblp", "crossref"}, negative={"dblp", "crossref"})
    result = assess(entry, item, current_year=YEAR)
    assert result.reasons == reasons
    assert result.verdict is (Verdict.CANNOT_DETERMINE if reasons else Verdict.NOT_FOUND)


def test_short_title_is_never_not_found() -> None:
    entry = bib(CS_ENTRY.replace(TITLE, "Sparse Attention Revisited").replace(
        "  doi = {10.1234/acl.2023.1},\n", ""
    ))  # fmt: skip
    item = evidence_for(entry, searched={"dblp", "crossref"}, negative={"dblp", "crossref"})
    result = assess(entry, item, current_year=YEAR)
    assert result.reasons == (Reason.INSUFFICIENT_METADATA,)


def test_suppression_drops_the_finding_but_keeps_the_verdict() -> None:
    # the suppression comment must sit directly above the entry
    text = '% preflight: ignore[REF003] reason="internal report"\n' + CS_ENTRY.lstrip().replace(
        "  doi = {10.1234/acl.2023.1},\n", ""
    )
    entry = bib(text)
    item = evidence_for(entry, searched={"dblp", "crossref"}, negative={"dblp", "crossref"})
    result = assess(entry, item, current_year=YEAR)
    assert result.verdict is Verdict.NOT_FOUND
    assert result.findings == ()


def test_retitled_record_reports_the_title() -> None:
    entry = bib(CS_ENTRY)
    other_title = "Robust Sparse Attention Mechanisms for Long Documents"
    result = assess(entry, evidence_for(entry, anchored=[record(other_title)]), current_year=YEAR)
    assert result.verdict is Verdict.METADATA_MISMATCH
    assert rules(result) == {"REF012"}


def test_record_with_unrelated_title_but_same_authors_is_not_trusted() -> None:
    entry = bib(CS_ENTRY)
    corrupted = record("Proceedings Front Matter")
    result = assess(entry, evidence_for(entry, anchored=[corrupted]), current_year=YEAR)
    assert result.verdict is Verdict.CANNOT_DETERMINE
    assert Reason.CORRUPTED_SOURCE_RECORD in result.reasons


def test_swapped_first_author() -> None:
    entry = bib(CS_ENTRY)
    swapped = record(authors=(BOB, ANN, CAROL))
    result = assess(entry, evidence_for(entry, anchored=[swapped]), current_year=YEAR)
    (finding,) = result.findings
    assert finding.rule_id == "REF011"
    assert "first author is Bob Jones" in finding.message.en


def test_conflicting_record_is_outvoted_by_a_confirming_one() -> None:
    entry = bib(CS_ENTRY)
    # same DOI, but this source holds a polluted record for it (seen in OpenAlex, spike S4)
    stale = replace(
        record("A Completely Different Paper About Databases", (Person("Wu", "Dan"),)),
        source="openalex",
    )
    result = assess(entry, evidence_for(entry, anchored=[stale, record()]), current_year=YEAR)
    assert (result.verdict, rules(result)) == (Verdict.VERIFIED, set())


def test_year_only_binding_has_a_limit() -> None:
    entry = bib(CS_ENTRY.replace("  doi = {10.1234/acl.2023.1},\n", ""))
    far = record(source="dblp", year=2016)
    item = evidence_for(
        entry, candidates=[far], searched={"dblp", "crossref"}, negative={"crossref"}
    )
    result = assess(entry, item, current_year=YEAR)
    assert result.record is None
    assert result.reasons == (Reason.AMBIGUOUS_CANDIDATES,)


ARXIV_ENTRY = """
@misc{smith2021sparse,
  title = {Robust Sparse Attention for Long Document Summarization},
  author = {Smith, Ann and Jones, Bob and Lee, Carol},
  year = {2021},
  eprint = {2101.00001},
  archivePrefix = {arXiv},
}
"""


def arxiv_record(**extra: object) -> SourceRecord:
    return SourceRecord(
        source="arxiv", source_id="2101.00001", title=TITLE, authors=(ANN, BOB, CAROL),
        year=2021, years=frozenset({2021}), work_type="preprint",
        identifiers={"arxiv": "2101.00001"}, **extra,  # type: ignore[arg-type]
    )  # fmt: skip


def test_withdrawn_arxiv_preprint() -> None:
    entry = bib(ARXIV_ENTRY)
    withdrawn = arxiv_record(status=frozenset({"withdrawn"}))
    result = assess(entry, evidence_for(entry, anchored=[withdrawn]), current_year=YEAR)
    assert rules(result) == {"REF018"}
    assert result.flags == {"withdrawn"}


def test_citing_the_published_version_with_an_eprint_is_fine() -> None:
    # The entry already cites the ACL version and keeps the eprint, as REF015 recommends; the
    # arXiv record must not trigger a venue mismatch (arXiv vs ACL) or REF015.
    entry = bib(ARXIV_ENTRY.replace("@misc", "@inproceedings").replace(
        "  year = {2021},", "  booktitle = {Proceedings of ACL},\n  year = {2022},"
    ))  # fmt: skip
    published = record(source="dblp", year=2022, venue="ACL")
    item = evidence_for(entry, anchored=[arxiv_record()], published_versions=[published])
    result = assess(entry, item, current_year=YEAR)
    assert (result.verdict, rules(result)) == (Verdict.VERIFIED, set())


@pytest.mark.parametrize(
    ("field", "venue", "rules_expected"),
    [
        # a venue nobody recognises is still where the work appeared (seen on a real paper)
        ("booktitle", "2017 IEEE Symposium on Security and Privacy (SP)", set()),
        ("booktitle", "IEEE Conference on Secure and Trustworthy Machine Learning", set()),
        # these still name a preprint
        ("journal", "arXiv preprint arXiv:2101.00001", {"REF015"}),
        ("journal", "CoRR", {"REF015"}),
        ("journal", "Submitted to Nature", {"REF015"}),
    ],
)
def test_a_named_venue_cites_the_published_version(
    field: str, venue: str, rules_expected: set[str]
) -> None:
    entry = bib(
        ARXIV_ENTRY.replace("  year = {2021},", f"  {field} = {{{venue}}},\n  year = {{2021}},")
    )
    published = record(source="dblp", year=2022, venue="ACL")
    item = evidence_for(entry, anchored=[arxiv_record()], published_versions=[published])
    assert rules(assess(entry, item, current_year=YEAR)) == rules_expected


def test_invented_title_on_a_real_doi_is_reported() -> None:
    # HALLMARK "chimeric title": the DOI and the authors are real, the title is invented
    entry = bib(CS_ENTRY)
    real = record("Graph Neural Networks for Combinatorial Optimization Benchmarks")
    result = assess(entry, evidence_for(entry, anchored=[real]), current_year=YEAR)
    assert (result.verdict, rules(result)) == (Verdict.METADATA_MISMATCH, {"REF012"})
    (finding,) = result.findings
    assert finding.data["found_title"] == real.title


def test_a_reworded_title_is_reported_with_the_words_that_differ() -> None:
    # HALLMARK "near-miss title": one word swapped, still 0.9+ similar character by character
    entry = bib(CS_ENTRY)
    real = record("Robust Dense Attention for Long Document Summarization")
    result = assess(entry, evidence_for(entry, anchored=[real]), current_year=YEAR)
    assert (result.verdict, rules(result)) == (Verdict.METADATA_MISMATCH, {"REF012"})
    (finding,) = result.findings
    assert finding.data["suggestion"] == real.title
    assert '"sparse" where the record has "dense"' in finding.message.en
    assert "“sparse”应为“dense”" in finding.message.zh


def test_a_reworded_title_is_reported_on_a_search_result_too() -> None:
    entry = bib(NO_DOI)
    real = record("Robust Sparse Attention towards Long Document Summarization")
    result = assess(entry, search_result(entry, real), current_year=YEAR)
    assert result.record == real
    assert (result.verdict, rules(result)) == (Verdict.METADATA_MISMATCH, {"REF012", "REF016"})


@pytest.mark.parametrize(
    "recorded",
    [
        "Robust Sparse Attention for Long Document Summarisation",  # British spelling
        "Robust Sparse-Attention for Long-Document Summarization",  # hyphenation
        "RETRACTED: Robust Sparse Attention for Long Document Summarization",  # registry notice
    ],
)
def test_spelling_hyphens_and_notices_are_not_rewording(recorded: str) -> None:
    entry = bib(CS_ENTRY)
    result = assess(entry, evidence_for(entry, anchored=[record(recorded)]), current_year=YEAR)
    assert (result.verdict, rules(result)) == (Verdict.VERIFIED, set())


def test_a_reworded_preprint_title_is_not_judged_without_its_version_titles() -> None:
    # DataCite holds only the latest arXiv title: an earlier version may have had this wording
    entry = bib(ARXIV_ENTRY)
    latest_only = SourceRecord(
        source="datacite", source_id="10.48550/arxiv.2101.00001",
        title=TITLE.replace("Sparse", "Dense"), authors=(ANN, BOB, CAROL), year=2021,
        years=frozenset({2021}), venue="arXiv", work_type="preprint",
        identifiers={"doi": "10.48550/arxiv.2101.00001", "arxiv": "2101.00001"},
    )  # fmt: skip
    result = assess(entry, evidence_for(entry, anchored=[latest_only]), current_year=YEAR)
    assert "REF012" not in rules(result)


def test_preprint_with_unknown_version_titles_is_not_judged_on_its_title() -> None:
    # DataCite holds only the latest arXiv title; the entry may cite an earlier version
    entry = bib(ARXIV_ENTRY)
    latest_only = SourceRecord(
        source="datacite", source_id="10.48550/arxiv.2101.00001",
        title="An Entirely Different Later Title", authors=(ANN, BOB, CAROL), year=2021,
        years=frozenset({2021}), venue="arXiv", work_type="preprint",
        identifiers={"doi": "10.48550/arxiv.2101.00001", "arxiv": "2101.00001"},
    )  # fmt: skip
    result = assess(entry, evidence_for(entry, anchored=[latest_only]), current_year=YEAR)
    assert result.verdict is Verdict.CANNOT_DETERMINE
    assert "REF012" not in rules(result)


def test_an_earlier_arxiv_version_title_is_fine() -> None:
    entry = bib(ARXIV_ENTRY)
    renamed = arxiv_record(alt_titles=(TITLE, "A Later Title"))
    renamed = replace(
        renamed, title="A Later Title",
        identifiers={**renamed.identifiers, "arxiv_version": "v3"},
    )  # fmt: skip
    result = assess(entry, evidence_for(entry, anchored=[renamed]), current_year=YEAR)
    assert (result.verdict, rules(result)) == (Verdict.VERIFIED, set())


def test_an_earlier_version_keeps_its_own_author_order() -> None:
    # arXiv 2508.03341: v1 "Nemori: ..." by Nan, Ma, Wu, Chen; v4 renamed and Ma listed first
    entry = bib(ARXIV_ENTRY)
    renamed = replace(
        arxiv_record(alt_titles=(TITLE, "A Later Title")), title="A Later Title",
        authors=(BOB, ANN, CAROL),
        identifiers={"arxiv": "2101.00001", "arxiv_version": "v4"},
    )  # fmt: skip
    result = assess(entry, evidence_for(entry, anchored=[renamed]), current_year=YEAR)
    assert (result.verdict, rules(result)) == (Verdict.VERIFIED, set())
    # with the latest title, the latest order counts
    reordered = replace(arxiv_record(), authors=(BOB, ANN, CAROL))
    result = assess(entry, evidence_for(entry, anchored=[reordered]), current_year=YEAR)
    assert "REF011" in rules(result)


NO_DOI = CS_ENTRY.replace("  doi = {10.1234/acl.2023.1},\n", "")


def search_result(entry: BibEntry, *found: SourceRecord) -> Evidence:
    return evidence_for(
        entry, candidates=list(found), searched={"dblp", "crossref"}, negative={"crossref"}
    )


def test_a_year_in_the_future_is_reported_against_the_real_one() -> None:
    # HALLMARK "future date": a real paper cited as 2034 (the gap limit guards reprints only)
    entry = bib(NO_DOI.replace("2023", "2034"))
    result = assess(entry, search_result(entry, record(source="dblp")), current_year=YEAR)
    assert (result.verdict, rules(result)) == (Verdict.METADATA_MISMATCH, {"REF013"})


def test_too_new_means_this_year_or_next() -> None:
    def reasons_for(year: int) -> tuple[Reason, ...]:
        entry = bib(NO_DOI.replace("2023", str(year)))
        item = evidence_for(entry, searched={"dblp", "crossref"}, negative={"dblp", "crossref"})
        return assess(entry, item, current_year=YEAR).reasons

    assert reasons_for(YEAR + 1) == (Reason.TOO_NEW,)
    assert reasons_for(YEAR + 8) == ()  # not "too new": no such paper was found (REF003)


def test_placeholder_authors_on_a_real_title_are_reported() -> None:
    # HALLMARK "placeholder authors": the title and year are real, the authors invented
    entry = bib(
        NO_DOI.replace(
            "Smith, Ann and Jones, Bob and Lee, Carol", "Nina Rodriguez and Ibrahim Diallo"
        )
    )
    result = assess(entry, search_result(entry, record(source="dblp")), current_year=YEAR)
    assert (result.verdict, rules(result)) == (Verdict.METADATA_MISMATCH, {"REF010"})


def test_swapped_coauthors_on_a_real_title_are_reported() -> None:
    entry = bib(NO_DOI.replace("Jones, Bob and Lee, Carol", "Petrov, Slav and Kumar, Ravi"))
    result = assess(entry, search_result(entry, record(source="dblp")), current_year=YEAR)
    assert rules(result) == {"REF011"}


@pytest.mark.parametrize(
    ("change", "why"),
    [
        (("Smith, Ann and Jones, Bob and Lee, Carol", "{OpenAI}"), "an organisation, not a swap"),
        (("Smith, Ann and Jones, Bob and Lee, Carol", "Kumar, Ravi"), "one name is too little"),
        ((TITLE, "Robust Sparse Attention Revisited Today"), "a short title names many works"),
        (("2023", "2019"), "another year may be another work"),
    ],
)
def test_title_only_binding_stays_narrow(change: tuple[str, str], why: str) -> None:
    entry = bib(NO_DOI.replace(*change))
    other_authors = record(
        title=entry.text("title") or "", authors=(Person("Wu", "Dan"), Person("Ito", "Ken"))
    )
    result = assess(
        entry, search_result(entry, replace(other_authors, source="dblp")), current_year=YEAR
    )
    assert result.record is None, why
    assert "REF010" not in rules(result), why


OTHERS = (Person("Wu", "Dan"), Person("Ito", "Ken"))


def test_similar_titles_by_other_people_do_not_make_an_entry_ambiguous() -> None:
    # HALLMARK hybrid and plausible fabrications: an invented entry that resembles real papers
    entry = bib(NO_DOI)
    other_work = record(
        "Robust Sparse Attention for Long Video Summarization", authors=OTHERS, source="dblp"
    )
    result = assess(entry, search_result(entry, other_work), current_year=YEAR)
    assert (result.verdict, rules(result)) == (Verdict.NOT_FOUND, {"REF003"})
    (finding,) = result.findings
    assert "dblp" in finding.message.en


@pytest.mark.parametrize(
    "candidate",
    [
        # the same title by other people: perhaps the cited work with wrong authors
        record(authors=OTHERS, source="dblp", year=2016),
        # another title by the same people: perhaps the cited work with a wrong title
        record("Robust Sparse Attention for Long Video Summarization", source="dblp", year=2016),
        # Semantic Scholar's author lists are not trusted to tell people apart
        record("Robust Sparse Attention for Long Video Summarization", authors=OTHERS, source="s2"),
    ],
)
def test_results_that_may_be_the_cited_work_stay_ambiguous(candidate: SourceRecord) -> None:
    entry = bib(NO_DOI)
    item = evidence_for(entry, candidates=[candidate], searched={"dblp", "crossref"},
                        negative={"crossref"})  # fmt: skip
    result = assess(entry, item, current_year=YEAR)
    assert result.verdict is Verdict.CANNOT_DETERMINE
    assert result.reasons == (Reason.AMBIGUOUS_CANDIDATES,)


SHORT_TITLE = "Sparse Attention Revisited Today"


@pytest.mark.parametrize(("venue", "bound"), [("ACL", True), ("EMNLP", False), (None, False)])
def test_a_short_title_names_one_work_at_the_same_venue_and_year(
    venue: str | None, bound: bool
) -> None:
    # HALLMARK swapped authors on "Explanations for Monotonic Classifiers" (ICML 2021)
    entry = bib(NO_DOI.replace(TITLE, SHORT_TITLE))
    other_authors = record(
        title=SHORT_TITLE, authors=(Person("Wu", "Dan"), Person("Ito", "Ken")), source="dblp",
        venue=venue,
    )  # fmt: skip
    result = assess(entry, search_result(entry, other_authors), current_year=YEAR)
    assert (result.record is not None) is bound
    assert ("REF010" in rules(result)) is bound


@pytest.mark.parametrize(
    ("recorded", "venue", "bound"),
    [
        ("Robust Sparse Attention for Long Video Summarization", "ACL", True),
        # a sibling paper elsewhere, or more than two words off: perhaps another work
        ("Robust Sparse Attention for Long Video Summarization", "EMNLP", False),
        ("Robust Sparse Attention for Short Video Captioning", "ACL", False),
    ],
)
def test_a_title_two_words_off_binds_with_the_same_people_and_venue(
    recorded: str, venue: str, bound: bool
) -> None:
    # HALLMARK near-miss titles below the search threshold ("Inference" for "Reasoning")
    entry = bib(NO_DOI)
    real = record(recorded, source="dblp", venue=venue)
    result = assess(entry, search_result(entry, real), current_year=YEAR)
    assert (result.record is not None) is bound
    if bound:
        (finding,) = result.findings
        assert finding.rule_id == "REF012"
        assert '"document" where the record has "video"' in finding.message.en


@pytest.mark.parametrize(("venue", "bound"), [("ACL", True), ("EMNLP", False)])
def test_a_far_year_is_no_reprint_at_the_same_venue(venue: str, bound: bool) -> None:
    # an ICLR 2017 paper cited as ICLR 2023: venues do not reprint their papers
    entry = bib(NO_DOI)
    far = record(source="dblp", year=2016, venue=venue)
    result = assess(entry, search_result(entry, far), current_year=YEAR)
    assert (result.record is not None) is bound
    if bound:
        assert rules(result) == {"REF013"}


def test_a_coauthor_with_another_given_name_is_reported() -> None:
    entry = bib(CS_ENTRY)
    real = record(authors=(ANN, Person("Jones", "Ben"), CAROL))
    result = assess(entry, evidence_for(entry, anchored=[real]), current_year=YEAR)
    assert (result.verdict, rules(result)) == (Verdict.METADATA_MISMATCH, {"REF011"})
    (finding,) = result.findings
    assert "other given names: Bob Jones (recorded: Ben Jones)" in finding.message.en


def test_semantic_scholar_authors_never_raise_a_finding() -> None:
    # S2 author lists mix initials, orders and duplicates: they confirm a work, never accuse
    entry = bib(NO_DOI)
    s2 = replace(record(source="s2", authors=(ANN, Person("Tran", "Tho"), CAROL)), year=None)
    s2 = replace(s2, years=frozenset())
    result = assess(entry, search_result(entry, s2), current_year=YEAR)
    assert result.record is not None
    assert result.record.source == "s2"
    assert not {"REF010", "REF011"} & rules(result)


def test_a_doi_the_entry_lacks_is_offered_as_a_safe_fix() -> None:
    entry = bib(NO_DOI)
    result = assess(entry, search_result(entry, record()), current_year=YEAR)  # Crossref, has DOI
    (finding,) = [f for f in result.findings if f.rule_id == "REF016"]
    assert finding.severity is Severity.INFO
    assert finding.data["suggestion"] == "10.1234/acl.2023.1"
    assert result.verdict is Verdict.VERIFIED  # info findings never change the verdict


def test_no_doi_offer_when_there_is_nothing_to_add() -> None:
    with_doi = bib(CS_ENTRY)
    assert "REF016" not in rules(
        assess(with_doi, evidence_for(with_doi, anchored=[record()]), current_year=YEAR)
    )
    preprint = bib(ARXIV_ENTRY)
    published = record(source="dblp", year=2022, venue="ACL")
    item = evidence_for(preprint, anchored=[arxiv_record()], published_versions=[published])
    assert "REF016" not in rules(assess(preprint, item, current_year=YEAR))  # REF015's job
    arxiv_doi = replace(record(), identifiers={"doi": "10.48550/arxiv.2101.00001"})
    entry = bib(NO_DOI)
    assert "REF016" not in rules(assess(entry, search_result(entry, arxiv_doi), current_year=YEAR))


@pytest.mark.parametrize(
    ("venue", "year", "reported"),
    [
        ("CoRR", 2022, False),  # dblp only has the preprint yet: the entry's later year is right
        ("CoRR", 2020, True),  # three years before the entry is not the same publication
        ("ACL", 2022, True),  # the published record itself says another year
    ],
)
def test_a_preprint_record_does_not_correct_the_published_year(
    venue: str, year: int, reported: bool
) -> None:
    entry = bib(NO_DOI)  # ACL 2023
    found = record(source="dblp", year=year, venue=venue)
    result = assess(entry, search_result(entry, found), current_year=YEAR)
    assert result.record is not None
    assert ("REF013" in rules(result)) is reported


def test_a_known_published_version_keeps_the_year_check() -> None:
    # HALLMARK: "IJCAI 2023" for a NeurIPS 2021 paper whose arXiv copy is from 2022. With the
    # published record known, the later year is no "not indexed yet".
    entry = bib(NO_DOI)  # ACL 2023
    preprint = record(source="dblp", year=2022, venue="CoRR")
    published = replace(record(source="dblp", year=2021, venue="NeurIPS"), source_id="conf/x")
    result = assess(entry, search_result(entry, preprint, published), current_year=YEAR)
    assert "REF013" in rules(result)


SOLAR = """
@inproceedings{asplund2005,
  title = {The Solar Chemical Composition},
  author = {Asplund, Martin and Grevesse, Nicolas and Sauval, A. Jacques},
  booktitle = {Cosmic Abundances as Records of Stellar Evolution and Nucleosynthesis},
  series = {Astronomical Society of the Pacific Conference Series},
  volume = {336},
  year = {2005},
}
"""


@pytest.mark.parametrize(
    ("venue", "year", "reported"),
    [
        ("Nuclear Physics A", 2006, False),  # the same authors' journal paper of the same title
        ("Nuclear Physics A", 2005, False),  # same year: nothing to report either way
        ("Cosmic Abundances as Records of Stellar Evolution", 2006, True),  # the cited one
    ],
)
def test_another_publication_of_the_title_does_not_correct_the_year(
    venue: str, year: int, reported: bool
) -> None:
    entry = bib(SOLAR)
    authors = (Person("Asplund", "M."), Person("Grevesse", "N."), Person("Sauval", "A. J."))
    found = record("The Solar Chemical Composition", authors, year, source="dblp", venue=venue)
    result = assess(entry, search_result(entry, found), current_year=YEAR)
    assert ("REF013" in rules(result)) is reported


THESIS = r"""
@phdthesis{martel1996,
  title = {Spectropolarimetry of High-Polarization Seyfert 1 Galaxies},
  author = {Martel, Andr{\'e} R. and Miller, Joseph S.},
  school = {University of California, Santa Cruz},
  year = {1996},
}
"""


@pytest.mark.parametrize(
    ("work_type", "reported"),
    [
        ("journal-article", False),  # the thesis abstract in PASP (1997), not the thesis
        ("dissertation", True),  # the thesis itself, with a wrong year
    ],
)
def test_another_kind_of_publication_does_not_correct_the_year(
    work_type: str, reported: bool
) -> None:
    entry = bib(THESIS)
    authors = (Person("Martel", "André R."), Person("Miller", "Joseph S."))
    found = record(
        "Spectropolarimetry of High-Polarization Seyfert 1 Galaxies", authors, 1997,
        work_type=work_type,
    )  # fmt: skip
    result = assess(entry, search_result(entry, found), current_year=YEAR)
    assert ("REF013" in rules(result)) is reported


ICML_ENTRY = ARXIV_ENTRY.replace("@misc", "@inproceedings").replace(
    "  year = {2021},", "  booktitle = {Proceedings of ICML},\n  year = {2021},"
)


@pytest.mark.parametrize(
    ("written", "on_arxiv", "at_icml"),
    [
        # ICML lists Jones first, arXiv lists Smith first: the entry follows ICML
        ("Jones, Bob and Smith, Ann and Lee, Carol", (ANN, BOB, CAROL), (BOB, ANN, CAROL)),
        # arXiv has "Bob Jones", ICML "Robert Jones": the entry follows arXiv
        ("Smith, Ann and Jones, Bob and Lee, Carol", (ANN, BOB, CAROL),
         (ANN, Person("Jones", "Robert"), CAROL)),
    ],
)  # fmt: skip
def test_an_entry_naming_its_venue_fits_either_version(
    written: str, on_arxiv: tuple[Person, ...], at_icml: tuple[Person, ...]
) -> None:
    entry = bib(ICML_ENTRY.replace("Smith, Ann and Jones, Bob and Lee, Carol", written))
    published = replace(record(authors=at_icml, year=2021, source="dblp", venue="ICML"),
                        source_id="conf/icml/x")  # fmt: skip
    item = evidence_for(
        entry, anchored=[replace(arxiv_record(), authors=on_arxiv)], published_versions=[published]
    )
    assert rules(assess(entry, item, current_year=YEAR)) == set()


def test_the_published_version_is_the_one_by_the_preprints_authors() -> None:
    # arXiv 1408.6027 (Xin Geng, 2014) is his TKDE 2016 article; dblp also has an ICDM Workshops
    # 2013 paper of the same title by Geng and Ji, found first
    entry = bib(ARXIV_ENTRY.replace("2021", "2014"))
    workshop = replace(
        record(authors=(ANN, BOB, CAROL, Person("Ji", "Rongzi")), year=2013, source="dblp",
               venue="ICDM Workshops"),
        source_id="conf/icdm/workshop13",
    )  # fmt: skip
    journal = replace(
        record(year=2016, source="dblp", venue="IEEE Trans. Knowl. Data Eng."),
        source_id="journals/tkde/x16",
    )
    preprint = replace(arxiv_record(), year=2014, years=frozenset({2014}))
    item = evidence_for(entry, anchored=[preprint], published_versions=[workshop, journal])
    (finding,) = [
        f for f in assess(entry, item, current_year=YEAR).findings if f.rule_id == "REF015"
    ]
    assert finding.data["published_id"] == "journals/tkde/x16"


TRUST = """
@inproceedings{jiang2021trust,
  title = {To trust or not to trust a classifier},
  author = {Jiang, Hao and Pang, Bo and Ding, Wei and Xu, Jian and Carin, Lawrence},
  booktitle = {International Conference on Learning Representations (ICLR)},
  year = {2021},
}
"""


@pytest.mark.parametrize(
    ("found_title", "bound"),
    [
        # NeurIPS 2018 by Jiang, Kim, Guan and Gupta: the cited work with invented authors
        ("To Trust Or Not To Trust A Classifier", True),
        # one word off is another paper of a series, not a reason to accuse across years
        ("To Trust Or Not To Trust A Regressor", False),
    ],
)
def test_a_long_title_names_one_work_a_few_years_off(found_title: str, bound: bool) -> None:
    entry = bib(TRUST)
    authors = (Person("Jiang", "Heinrich"), Person("Kim", "Been"), Person("Guan", "Melody Y."),
               Person("Gupta", "Maya R."))  # fmt: skip
    found = record(found_title, authors, 2018, source="dblp", venue="NeurIPS")
    result = assess(entry, search_result(entry, found), current_year=YEAR)
    if bound:
        assert {"REF011", "REF013"} <= rules(result)
    else:
        assert result.verdict is Verdict.CANNOT_DETERMINE


def test_no_control_characters_in_the_source() -> None:
    # a "\b" written through a tool once became a backspace in a raw-string pattern (#60)
    package = Path(__file__).parent.parent / "src" / "paper_preflight"
    for path in package.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert not [c for c in text if ord(c) < 32 and c not in "\n\t"], path


@pytest.mark.parametrize("venue", ["CoRR abs/2101.00001", "corr"])
def test_corr_names_a_preprint(venue: str) -> None:
    entry = bib(
        ARXIV_ENTRY.replace("  year = {2021},", f"  journal = {{{venue}}},\n  year = {{2021}},")
    )
    published = record(source="dblp", year=2022, venue="ACL")
    item = evidence_for(entry, anchored=[arxiv_record()], published_versions=[published])
    assert "REF015" in rules(assess(entry, item, current_year=YEAR))
