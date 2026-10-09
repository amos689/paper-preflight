"""Parsers against real responses recorded in spikes S1-S4 (tests/fixtures/sources)."""

import json
from pathlib import Path
from typing import Any

import pytest

from paper_preflight.sources import arxiv, crossref, datacite, dblp, doiorg, openalex
from paper_preflight.sources.record import Person, plain_title

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


def test_person_from_parts() -> None:
    assert Person.from_parts("James W.", "Davidson Jr.") == Person("Davidson", "James W.")
    assert Person.from_parts("Martin Luther", "King, Jr.") == Person("King", "Martin Luther")
    # the original script after the romanised name (Crossref) is dropped, a name in it alone kept
    assert Person.from_parts("Lihwai 俐 暉", "Lin 林") == Person("Lin", "Lihwai")
    assert Person.from_parts("志华", "周") == Person("周", "志华")
    assert Person.from_parts(None, "Jr.") == Person("Jr.")
    # an affiliation mark and a look-alike symbol in a deposited name (Crossref, 2006)
    assert Person.from_parts("S⊘ren", "Asmussen c") == Person("Asmussen", "Søren")


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


@pytest.mark.parametrize(
    ("key", "year", "expected"),
    [
        ("conf/birws/AtanassovaB24", 2025, 2024),  # BIR 2024, proceedings published 2025
        ("conf/cvpr/HeZRS16", 2016, None),  # the same year adds nothing
        ("journals/corr/abs-1706-03762", 2017, None),  # no year in the key
        ("conf/nips/Smith99", 2000, 1999),
        ("conf/nips/Smith00a", 1999, 2000),
        ("conf/nips/Smith12", 2016, None),  # four years apart: not this record's year
    ],
)
def test_dblp_key_year(key: str, year: int, expected: int | None) -> None:
    assert dblp.key_year(key, year) == expected
    rows = [{"pub": dblp.REC + key, "title": "T", "year": str(year)}]
    assert dblp.records_from_rows(rows)[key].years == {year} | ({expected} if expected else set())


def test_dblp_prefix_range() -> None:
    assert dblp.prefix_range("Attention Is   All You Need") == (
        "attention is all you need",
        "attention is all you neee",
    )
    query = dblp.title_prefix_query('A "quoted" title')
    assert '\\"quoted\\"' in query


@pytest.mark.parametrize(
    ("title", "low", "high"),
    [
        # cut at a colon: the collation ignores punctuation, so ":" to ";" was an empty range
        (
            "On Pre-Training for Visuo-Motor Control: Revisiting a Learning-from-Scratch Baseline",
            "on pre-training for visuo-motor control",
            "on pre-training for visuo-motor controm",
        ),
        (
            "Llama 2: Open Foundation and Fine-Tuned Chat Models",
            "llama 2: open foundation and fine-tuned",
            "llama 2: open foundation and fine-tunee",
        ),
        (
            "YOLOv3: An Incremental Improvement",
            "yolov3: an incremental improvement",
            "yolov3: an incremental improvemenu",
        ),
        ("ResNet 50", "resnet", "resneu"),  # trailing digits cannot be incremented
        ("Learning to Quiz", "learning to qui", "learning to quj"),  # nor can "z"
        ("Étude des réseaux", "etude des reseaux", "etude des reseauy"),  # accents are folded
        ("2024", "", "￿"),
        # GPQA's "Q&A" as a PDF prints it; spaced on both sides it stays as written
        (
            "GPQA: A Graduate-Level Google-Proof Q &A Benchmark",
            "gpqa: a graduate-level google-proof q&a",
            "gpqa: a graduate-level google-proof q&b",
        ),
        ("Research & Development", "research & development", "research & developmenu"),
    ],
)
def test_dblp_prefix_range_ends_in_a_letter(title: str, low: str, high: str) -> None:
    assert dblp.prefix_range(title) == (low, high)


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


def test_csl_html_entities_are_decoded() -> None:
    # mEDRA's CSL for 10.3254/978-1-61499-018-5-115 (2609.17979v1, Hein2006)
    csl = {
        "title": "Entanglement in graph states and its applications",
        "author": [{"literal": "Hein M."}, {"literal": "D&uuml;r W."}],
        "container-title": "International School of Physics &ldquo;Enrico Fermi&rdquo;",
        "issued": {"date-parts": [[2006]]},
    }
    record = doiorg.parse_csl("10.3254/978-1-61499-018-5-115", csl, "mEDRA")
    assert [p.display for p in record.authors] == ["Hein M.", "Dür W."]
    assert record.venue == "International School of Physics “Enrico Fermi”"


def test_dblp_year_the_key_and_doi_contradict() -> None:
    # dblp files conf/acl/ShaoLF0LQ24 (Findings of ACL 2024) under 2014
    key = "conf/acl/ShaoLF0LQ24"
    row = {"pub": dblp.REC + key, "title": "Balanced Data Sampling", "year": "2014",
           "doi": "https://doi.org/10.18653/V1/2024.FINDINGS-ACL.833"}  # fmt: skip
    assert dblp.records_from_rows([row])[key].year == 2024
    # the key alone, or a DOI without a year, changes nothing
    alone = {**row, "doi": "https://doi.org/10.1145/3219819.3220064"}
    assert dblp.records_from_rows([alone])[key].year == 2014


def test_crossref_cambridge_books_online_date_is_no_year() -> None:
    # 10.1017/cbo9780511976667: Nielsen & Chuang's 2010 edition, deposited with its 2012 date
    item = {
        "DOI": "10.1017/CBO9780511976667", "type": "monograph",
        "title": ["Quantum Computation and Quantum Information"],
        "issued": {"date-parts": [[2012, 6, 5]]},
        "published-online": {"date-parts": [[2012, 6, 5]]},
    }  # fmt: skip
    record = crossref.parse_work(item)
    assert (record.year, record.years) == (None, frozenset())
    printed = crossref.parse_work({**item, "published-print": {"date-parts": [[2010, 12, 9]]}})
    assert 2010 in printed.years
    other = crossref.parse_work({**item, "DOI": "10.1017/9781108627771"})
    assert other.year == 2012


@pytest.mark.parametrize(
    ("raw", "plain"),
    [
        # a Crossref title behind a false REF012 on a HALLMARK VALID entry
        (
            r"$${{\mathrm {Latent}}Out}$$: an unsupervised deep anomaly detection approach",
            "LatentOut : an unsupervised deep anomaly detection approach",
        ),
        ("Learning with <i>Noisy</i> Labels in <sub>2</sub>D", "Learning with Noisy Labels in 2D"),
        ('A <mml:math xmlns:mml="x"><mml:mi>k</mml:mi></mml:math>-means study', "A k-means study"),
        ("Tom &amp; Jerry", "Tom & Jerry"),
        (
            "Deep Residual Learning   for Image Recognition",
            "Deep Residual Learning for Image Recognition",
        ),
        # real papers: escaped tags (10.1117/12.176725), a LaTeX document for one formula
        # (10.1086/308445), arXiv's TeX, and a less-than sign that is no tag
        ("&lt;title&gt;HIRES: the spectrometer&lt;/title&gt;", "HIRES: the spectrometer"),
        (
            r"55 Galaxies in the \documentclass{aastex} \usepackage{amsbsy} \pagestyle{empty}"
            r" \begin{document} \landscape $z=0.33$ \end{document} Cluster",
            "55 Galaxies in the z=0.33 Cluster",
        ),
        (r"Biological $2\mathrm{D}{+}t$ Reaction-Diffusion", "Biological 2D+t Reaction-Diffusion"),
        (
            "from &lt;100 mas Resolution ALMA Observations",
            "from <100 mas Resolution ALMA Observations",
        ),
        # the AAS journals' old markup (10.1086/301140): a phrase in capitals, then as written
        (
            "[ITAL]HUBBLE SPACE TELESCOPE[/ITAL][ITAL]Hubble Space Telescope[/ITAL] Observations"
            " of the C[CLC]f[/CLC]A Seyfert 2 Galaxies",
            "Hubble Space Telescope Observations of the CfA Seyfert 2 Galaxies",
        ),
        ("[ITAL]A[/ITAL][ITAL]B[/ITAL] and M[SUB]sun[/SUB]", "A B and Msun"),
        (
            "H [CSC]i[/CSC] Shells in the Large Magellanic Cloud",
            "H i Shells in the Large Magellanic Cloud",
        ),
        # UTF-8 read as Latin-1 (10.1111/j.1365-2966.2009.15736.x, an em space), and a font
        # switch whose argument is no text (10.1046/j.1365-8711.2001.04912.x)
        ("NLTE analysis of Coâ\u0080\u0083i lines", "NLTE analysis of Co i lines"),
        ("CafÃ© â\u0080\u0094 a study", "Café — a study"),
        (r"Results at \fontshape{it}{z}=0", "Results at z=0"),
        # correctly encoded letters stay as they are
        ("Ångström-scale Café", "Ångström-scale Café"),
    ],
)
def test_plain_title(raw: str, plain: str) -> None:
    assert plain_title(raw) == plain


def test_names_read_with_the_wrong_encoding_are_repaired() -> None:
    # Crossref's record of 10.3389/fgene.2014.00342: UTF-8 read as Windows-1252
    person = Person.from_parts("DuÅ¡ica", "VidoviÄ‡")
    assert (person.given, person.family) == ("Dušica", "Vidović")
    assert Person.from_display("Stephan C SchÃ¼rer").family == "Schürer"
    person = Person.from_parts("Ângela", "Sônia")  # correctly encoded: unchanged
    assert (person.given, person.family) == ("Ângela", "Sônia")


def test_crossref_titles_lose_their_markup() -> None:
    item = {
        "DOI": "10.1/x",
        "title": ["Learning with <i>Noisy</i> Labels"],
        "subtitle": ["A <b>Study</b>"],
    }
    record = crossref.parse_work(item)
    assert record.title == "Learning with Noisy Labels"
    assert record.alt_titles == ("Learning with Noisy Labels: A Study",)


def early_access(**changes: Any) -> dict[str, Any]:
    # DOI 10.1109/tpami.2023.3330794 as Crossref has it: online in November 2023, issue in 2024
    item: dict[str, Any] = {
        "DOI": "10.1109/tpami.2023.3330794", "type": "journal-article",
        "title": ["Temporal Action Localization in the Deep Learning Era: A Survey"],
        "issued": {"date-parts": [[2024, 4]]}, "published-print": {"date-parts": [[2024, 4]]},
        "created": {"date-parts": [[2023, 11, 6]]},
    }  # fmt: skip
    item.update(changes)
    return item


@pytest.mark.parametrize(
    ("changes", "years"),
    [
        ({}, {2023, 2024}),  # early access: the DOI was created when the article went online
        ({"published-online": {"date-parts": [[2023, 11]]}}, {2023, 2024}),  # deposited online
        # an online date deposited as the issue's (APA, ACM's TOSEM): the DOI's creation tells
        (
            {"DOI": "10.1037/xlm0001244", "published-online": {"date-parts": [[2024, 4]]}},
            {2023, 2024},
        ),
        # not two years before an issue whose online date is deposited
        (
            {
                "DOI": "10.1037/xlm0001244",
                "published-online": {"date-parts": [[2024, 4]]},
                "created": {"date-parts": [[2022, 6]]},
            },
            {2024},
        ),
        ({"type": "proceedings-article"}, {2024}),
        # with a DOI that names no year (Proc. IEEE's "10.1109/5.726791"), only the deposit
        # date can tell: too early to be early access, or a later deposit
        ({"DOI": "10.1109/5.726791", "created": {"date-parts": [[2019, 1, 1]]}}, {2024}),
        ({"DOI": "10.1109/5.726791", "created": {"date-parts": [[2025, 1, 1]]}}, {2024}),
    ],
)
def test_crossref_early_access_year(changes: dict[str, Any], years: set[int]) -> None:
    record = crossref.parse_work(early_access(**changes))
    assert record.years == years
    assert record.year == 2024


def test_crossref_ieee_doi_names_the_early_access_year() -> None:
    # TSE's 10.1109/tse.2018.2872971 was online in 2018; Crossref has only its 2020 issue,
    # deposited then. IEEE's journal DOIs name the year they were assigned.
    issue = {"date-parts": [[2020, 9, 1]]}
    record = crossref.parse_work(
        early_access(
            DOI="10.1109/tse.2018.2872971", issued=issue, **{"published-print": issue},
            created={"date-parts": [[2020, 8, 19]]},
        )
    )  # fmt: skip
    assert record.years == {2018, 2020}


def test_crossref_december_print_counts_the_next_year() -> None:
    # MNRAS 500(4): cover date January 2021, printed 10 December 2020 (10.1093/mnras/staa3519)
    item = {
        "DOI": "10.1093/mnras/staa3519", "type": "journal-article", "title": ["LeMMINGs II"],
        "issued": {"date-parts": [[2020, 11, 17]]},
        "published-online": {"date-parts": [[2020, 11, 17]]},
        "published-print": {"date-parts": [[2020, 12, 10]]},
    }  # fmt: skip
    assert crossref.parse_work(item).years == {2020, 2021}
    item["published-print"] = {"date-parts": [[2020, 11]]}
    assert crossref.parse_work(item).years == {2020}


def test_crossref_book_printed_late_in_the_year_counts_the_next() -> None:
    # Cover & Thomas, Elements of Information Theory, 2nd edition: online April 2005, printed
    # September 2005, copyright 2006 (2609.02029v1, cover_thomas); Rasmussen & Williams's GPML
    # (MIT Press) is printed November 2005, copyright 2006
    item = {
        "DOI": "10.1002/047174882x", "type": "monograph",
        "title": ["Elements of Information Theory"],
        "issued": {"date-parts": [[2005, 4, 7]]},
        "published-online": {"date-parts": [[2005, 4, 7]]},
        "published-print": {"date-parts": [[2005, 9, 16]]},
    }  # fmt: skip
    assert crossref.parse_work(item).years == {2005, 2006}
    item["published-print"] = {"date-parts": [[2005, 6]]}
    assert crossref.parse_work(item).years == {2005}
    item["type"] = "journal-article"
    item["published-print"] = {"date-parts": [[2005, 9, 16]]}
    assert crossref.parse_work(item).years == {2005}


def test_crossref_late_online_date_counts_the_next_volume() -> None:
    # Quantum Sci. Technol. 4(1) 014004: online 9 October 2018, no print date; volume 4 is 2019
    item = {
        "DOI": "10.1088/2058-9565/aae0fe", "type": "journal-article", "title": ["Cryogenic"],
        "issued": {"date-parts": [[2018, 10, 9]]}, "volume": "4",
        "published-online": {"date-parts": [[2018, 10, 9]]},
    }  # fmt: skip
    assert crossref.parse_work(item).years == {2018, 2019}
    item["published-online"] = {"date-parts": [[2018, 5, 9]]}  # earlier in the year: no
    assert crossref.parse_work(item).years == {2018}
    item["published-online"] = {"date-parts": [[2018, 10, 9]]}
    item["published-print"] = {"date-parts": [[2018, 11]]}  # a print date says which year
    assert crossref.parse_work(item).years == {2018}


# Crossref's answer to an unknown select: "Valid selects for this route are: ..." (2026-10-03).
# A field outside this list makes every /works request fail with 400.
CROSSREF_WORKS_SELECTS = set(
    "abstract URL resource member posted score created degree update-policy short-title license "
    "ISSN container-title issued update-to issue prefix approved indexed article-number "
    "clinical-trial-number accepted author group-title DOI is-referenced-by-count updated-by "
    "event chair standards-body original-title funder translator published archive "
    "published-print alternative-id subject subtitle published-online publisher-location "
    "content-domain reference title link type publisher volume references-count ISBN issn-type "
    "assertion deposited page contributor content-created short-container-title relation "
    "editor".split()
)


def test_crossref_selects_only_fields_the_route_accepts() -> None:
    assert set(crossref.SELECT.split(",")) <= CROSSREF_WORKS_SELECTS


@pytest.mark.parametrize(
    ("doi", "issued", "years"),
    [
        # MNRAS 319(3), December 2000; Crossref's backfile deposit says 2002
        ("10.1046/j.1365-8711.2000.03658.x", 2002, {2000, 2002}),
        ("10.1111/j.1467-9868.2005.00503.x", 2005, {2005}),  # the same year adds nothing
        ("10.1111/j.1467-9868.1995.tb02031.x", 1995, {1995}),  # no year in this form
        ("10.1046/j.1365-8711.1995.03658.x", 2002, {2002}),  # too far: not this record's year
        ("10.1016/j.acha.2006.03.004", 2007, {2007}),  # Elsevier's pattern is not Wiley's
    ],
)
def test_crossref_wiley_doi_year(doi: str, issued: int, years: set[int]) -> None:
    item = {"DOI": doi, "type": "journal-article", "title": ["t"],
            "issued": {"date-parts": [[issued, 4, 4]]}}  # fmt: skip
    assert crossref.parse_work(item).years == years


def test_datacite_github_release_title_is_the_repository() -> None:
    (record,) = datacite.parse_dois(
        {"data": {"id": "10.5281/zenodo.593816", "attributes": {
            "doi": "10.5281/zenodo.593816", "titles": [{"title": "pyRiemann/pyRiemann: v0.10"}],
            "publicationYear": 2026, "publisher": "Zenodo"}}}
    )  # fmt: skip
    assert record.title == "pyRiemann"
    assert record.alt_titles == ("pyRiemann/pyRiemann: v0.10",)
    (other,) = datacite.parse_dois(
        {"data": {"id": "x", "attributes": {"titles": [{"title": "Data for: A Study: v2"}]}}}
    )
    assert other.title == "Data for: A Study: v2"


def test_crossref_venue_names_and_issns() -> None:
    item = {
        "DOI": "10.1007/978-3-642-04346-8_62", "type": "book-chapter", "title": ["GROBID"],
        "container-title": ["Lecture Notes in Computer Science",
                            "Research and Advanced Technology for Digital Libraries"],
        "short-container-title": [], "ISSN": ["0302-9743", "1611-3349"],
    }  # fmt: skip
    record = crossref.parse_work(item)
    assert record.venue == "Lecture Notes in Computer Science"
    assert record.venue_aliases == ("Research and Advanced Technology for Digital Libraries",)
    assert record.issns == {"0302-9743", "1611-3349"}
    assert {"short-container-title", "ISSN"} <= set(crossref.SELECT.split(","))


def test_dblp_title_prefixes_query() -> None:
    lows = [dblp.prefix_range(t)[0] for t in ("Attention Is All You Need", "Segment Anything")]
    query = dblp.title_prefixes_query(lows)
    assert query.count("{ SELECT ?pub ?t (") == 2
    assert "(0 AS ?i)" in query
    assert "(1 AS ?i)" in query
    assert 'FILTER(?t >= "attention is all you need" && ?t < "attention is all you neee")' in query
    assert "UNION" in query
