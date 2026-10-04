import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from paper_preflight.bib.names import parse_authors, parse_name
from paper_preflight.bib.parse import parse_bib_file, parse_bib_text
from paper_preflight.match import (
    EntryInfo,
    best_candidate,
    canonical_venue,
    changed_words,
    check_authors,
    check_title,
    check_venue,
    check_year,
    evaluate,
    given_names_differ,
    surname_key,
    suspicious_reason,
    title_score,
)
from paper_preflight.sources import crossref
from paper_preflight.sources.record import Person, SourceRecord

FIXTURES = Path(__file__).parent / "fixtures" / "sources"
DEMO = Path(__file__).parent.parent / "examples" / "demo-paper" / "refs.bib"


def load(name: str) -> Any:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def demo() -> dict[str, EntryInfo]:
    return {e.key: EntryInfo.from_entry(e) for e in parse_bib_file(DEMO).entries}


@pytest.fixture(scope="module")
def cvpr() -> SourceRecord:
    return crossref.parse_work(load("crossref/work_cvpr.json")["message"])


# ------------------------------------------------------------------ names


@pytest.mark.parametrize(
    ("raw", "family", "given"),
    [
        ("He, Kaiming", "He", "Kaiming"),
        ("Kaiming He", "He", "Kaiming"),
        ("van der Berg, Jan", "van der Berg", "Jan"),
        ("Jan van der Berg", "van der Berg", "Jan"),
        ('M{\\"u}ller, J{\\"o}rg', "Müller", "Jörg"),
        ("Gomez, Aidan N.", "Gomez", "Aidan N."),
        ("{World Health Organization}", "World Health Organization", ""),
        # a generational suffix stays with the family name, which BibTeX alone takes it for
        ("David H. Smith IV", "Smith IV", "David H."),
        ("Martin Luther King Jr.", "King Jr.", "Martin Luther"),
    ],
)
def test_parse_name(raw: str, family: str, given: str) -> None:
    person = parse_name(raw)
    assert (person.family, person.given) == (family, given)


def test_parse_authors_and_others() -> None:
    authors = parse_authors("Doe, Jane and {Research and Development Team} and others")
    assert [p.family for p in authors.people] == ["Doe", "Research and Development Team"]
    assert authors.truncated
    assert parse_authors("").people == ()


# ------------------------------------------------------------------ titles


def test_title_scores() -> None:
    assert title_score("Attention Is All You Need", "Attention is All you Need.") == 1.0
    assert title_score("{BERT}: Pre-training", "BERT: Pre-training") == 1.0
    assert (
        title_score("Deep Residual Learning", "Deep Residual Learning for Image Recognition") < 0.9
    )


def test_subtitle_omitted_is_a_variant(cvpr: SourceRecord) -> None:
    record = SourceRecord(
        source="x", source_id="1",
        title="Natural Questions: A Benchmark for Question Answering Research",
    )  # fmt: skip
    check = check_title("Natural Questions", record)
    assert check.status == "mismatch"  # too short to be an acceptable prefix
    long_record = SourceRecord(
        source="x", source_id="2",
        title="Gaussian Error Linear Units for Deep Networks: A Practical Study",
    )  # fmt: skip
    assert (
        check_title("Gaussian Error Linear Units for Deep Networks", long_record).status
        == "variant"
    )


def test_a_title_without_its_leading_name_is_a_variant() -> None:
    # arXiv 2512.24880 is "mHC: Manifold-Constrained Hyper-Connections"
    named = SourceRecord(
        source="arxiv", source_id="2512.24880", title="mHC: Manifold-Constrained Hyper-Connections"
    )
    check = check_title("Manifold-Constrained Hyper-Connections", named)
    assert check.status != "mismatch"
    assert check.changed == ()  # no word reported missing
    # what follows the colon must be long enough to name the work on its own
    short = SourceRecord(source="x", source_id="1", title="GELU: Activation Functions")
    assert check_title("Activation Functions", short).status == "mismatch"
    # and the part before it must be a name, not the start of a sentence
    sentence = SourceRecord(
        source="x", source_id="2",
        title="Why Attention Fails: Manifold-Constrained Hyper-Connections Revisited",
    )  # fmt: skip
    assert (
        check_title("Manifold-Constrained Hyper-Connections Revisited", sentence).status != "match"
    )


def test_earlier_version_title_is_a_variant() -> None:
    record = SourceRecord(
        source="arxiv", source_id="1606.08415",
        title="Gaussian Error Linear Units (GELUs)",
        alt_titles=(
            "Bridging Nonlinearities and Stochastic Regularizers with Gaussian Error Linear"
            " Units",
        ),
    )  # fmt: skip
    check = check_title(
        "Bridging Nonlinearities and Stochastic Regularizers with Gaussian Error Linear Units",
        record,
    )
    assert check.status == "variant"
    assert "earlier version" in check.note
    assert check.changed == ()  # it is exactly the earlier title


@pytest.mark.parametrize(
    ("ours", "theirs", "changes"),
    [
        ("FSDR: Domain Randomization towards Domain Generalization",
         "FSDR: Domain Randomization for Domain Generalization", (("towards", "for"),)),
        ("Subspace Differential Privacys", "Subspace Differential Privacy",
         (("privacys", "privacy"),)),
        ("SCAFFOLD: Controlled Averaging for On-Device Federated Learning",
         "SCAFFOLD: Controlled Averaging for Federated Learning", (("on device", ""),)),
        ("UniT: Unified Multimodal Chain of-Thought Scaling",
         "UniT: Unified Multimodal Chain-of-Thought Scaling", ()),
        ("Self-Supervised Pretraining at Scale", "Self Supervised Pre-training at Scale", ()),
        ("Behaviour Modelling and Optimisation", "Behavior Modeling and Optimization", ()),
        ("Graphs & Networks", "Graphs and Networks", ()),
        ("RETRACTED: Ileal-lymphoid-nodular hyperplasia", "Ileal-lymphoid-nodular hyperplasia", ()),
        ("Augmenting Online Algorithms with ε-Accurate Predictions",
         "Augmenting Online Algorithms with e-Accurate Predictions", ()),
        # an article one side starts with (Semantic Scholar for A&A 14, 226), not one elsewhere
        ("An improved method for computing membership probabilities",
         "IMPROVED METHOD FOR COMPUTING MEMBERSHIP PROBABILITIES", ()),
        ("A method for the cluster", "A method for an cluster", (("the", "an"),)),
        # a part's number in roman numerals (ApJS 98, 477), but no other word for a digit
        ("Seyfert Nuclei. II. An Optical Atlas", "Seyfert nuclei. 2: an optical atlas", ()),
        ("Seyfert Nuclei. III. An Atlas", "Seyfert nuclei. 2: an atlas", (("iii", "2"),)),
        # a footnote mark on the record's last word (PASP 115, 389), only there
        ("Correcting Spectra for Absorption", "Correcting Spectra for Absorption1", ()),
        ("Absorption Spectra of Stars", "Absorption1 Spectra of Stars",
         (("absorption", "absorption1"),)),
        # a symbol the registry dropped after a one-letter quantity (ApJ 573, 81)
        ("Ionizing fluxes from 0.05 to 2 Z$_{solar}$", "Ionizing fluxes from 0.05 to 2 Z", ()),
        ("A solar model of fluxes", "A model of fluxes", (("solar", ""),)),
    ],
)  # fmt: skip
def test_changed_words(ours: str, theirs: str, changes: tuple[tuple[str, str], ...]) -> None:
    if ours.startswith("RETRACTED"):  # the notice sits on the record's side
        ours, theirs = theirs, ours
    assert changed_words(ours, theirs) == changes


def test_a_reworded_title_keeps_its_status_but_names_the_words() -> None:
    record = SourceRecord(
        source="crossref", source_id="10.1109/cvpr46437.2021.00682",
        title="FSDR: Frequency Space Domain Randomization for Domain Generalization",
    )  # fmt: skip
    check = check_title(
        "FSDR: Frequency Space Domain Randomization towards Domain Generalization", record
    )
    assert check.status == "match"  # still the same work: binding is unchanged
    assert check.changed == (("towards", "for"),)


# ------------------------------------------------------------------ authors


def test_authors_match_and_truncation(demo: dict[str, EntryInfo], cvpr: SourceRecord) -> None:
    assert check_authors(demo["he2016deep"].authors, cvpr).status == "match"
    two = parse_authors("He, Kaiming and Zhang, Xiangyu")
    omitted = check_authors(two, cvpr)
    assert omitted.status == "variant"
    assert omitted.note == "some authors omitted"
    assert (
        check_authors(parse_authors("He, Kaiming and Zhang, Xiangyu and others"), cvpr).status
        == "match"
    )


def test_disjoint_authors(demo: dict[str, EntryInfo], cvpr: SourceRecord) -> None:
    check = check_authors(demo["devlin2019bert"].authors, cvpr)
    assert check.status == "mismatch"
    assert check.disjoint


def record_with(*families: str) -> SourceRecord:
    return SourceRecord(
        source="crossref", source_id="x", title="t", authors=tuple(Person(f) for f in families)
    )


def test_transcribed_surnames_match() -> None:
    # HALLMARK VALID entry: the .bib has "Simon Reiß", Crossref has "Reis"
    entry = parse_authors("Kailun Yang and Simon Reiß and Rainer Stiefelhagen")
    assert check_authors(entry, record_with("Yang", "Reis", "Stiefelhagen")).status == "match"
    umlaut = parse_authors("Jürgen Müller and Anna Schäfer")
    assert check_authors(umlaut, record_with("Mueller", "Schaefer")).status == "match"


def test_different_surnames_stay_different() -> None:
    for written, recorded in (("Chen", "Cheng"), ("Lee", "Le"), ("Wang", "Wan")):
        authors = parse_authors(f"Ann {written} and Bo Li")
        check = check_authors(authors, record_with(recorded, "Li"))
        assert not check.first_author_match, (written, recorded)
        assert check.missing == (f"Ann {written}",)


def test_an_exact_surname_is_not_taken_by_a_variant() -> None:
    # "Reis" on the record must pair with the entry's "Reis", leaving "Reiss" to match "Reiss"
    entry = parse_authors("Ana Reiss and Bo Reis")
    assert check_authors(entry, record_with("Reiss", "Reis")).status == "match"


def test_fabricated_coauthor_is_detected(cvpr: SourceRecord) -> None:
    authors = parse_authors("He, Kaiming and Lindqvist, Aurelio and Ren, Shaoqing and Sun, Jian")
    check = check_authors(authors, cvpr)
    assert check.status == "variant"
    assert check.missing == ("Aurelio Lindqvist",)


# ------------------------------------------------------------------ year and venue


def test_year_has_no_blanket_tolerance(demo: dict[str, EntryInfo]) -> None:
    # dblp files Adam under a CoRR key but lists it as ICLR (Poster) 2015 (spike S1)
    record = SourceRecord(
        source="dblp", source_id="journals/corr/KingmaB14",
        title="Adam: A Method for Stochastic Optimization", year=2015,
        years=frozenset({2015}), venue="ICLR (Poster)",
    )  # fmt: skip
    assert check_year(demo["kingma2015adam"].year, record).status == "mismatch"  # 2016 vs 2015
    preprint = SourceRecord(
        source="arxiv", source_id="x", title="t", year=2015, work_type="preprint"
    )
    assert check_year(2016, preprint).status == "variant"


def test_a_meetings_year_named_by_its_venue() -> None:
    # Een & Sorensson, SAT 2003: the LNCS volume appeared in 2004 (Crossref, a book chapter)
    record = SourceRecord(
        source="crossref", source_id="10.1007/978-3-540-24605-3_37", title="An Extensible",
        year=2004, years=frozenset({2004}), work_type="book-chapter",
    )  # fmt: skip
    assert check_year(2003, record, venue="Proceedings of SAT-2003").status == "match"
    assert check_year(2003, record, venue="Proc. SAT'03").status == "match"
    assert check_year(2003, record, venue="Proceedings of SAT").status == "mismatch"
    assert check_year(2002, record, venue="Proceedings of SAT-2002").status == "mismatch"
    article = replace(record, work_type="journal-article")
    assert check_year(2003, article, venue="Journal of SAT 2003").status == "mismatch"


def test_a_jmlr_volume_runs_into_the_next_year() -> None:
    # JMLR cites 18(167) as 2018; dblp files volume 18 under 2017 (journals/jmlr/ChowGJP17)
    record = SourceRecord(
        source="dblp", source_id="journals/jmlr/ChowGJP17", title="Risk-Constrained RL",
        year=2017, years=frozenset({2017}),
    )  # fmt: skip
    assert check_year(2018, record).status == "match"
    assert check_year(2016, record).status == "mismatch"
    other = replace(record, source_id="journals/tit/GavishD14")
    assert check_year(2018, other).status == "mismatch"


def test_a_volume_the_record_leaves_out() -> None:
    record = SourceRecord(source="crossref", source_id="x", title="The Quantum Theory of Fields")
    check = check_title("The Quantum Theory of Fields. Vol. 2: Modern Applications", record)
    assert (check.status, check.changed) == ("variant", ())
    # two parts of one series are two works
    part = SourceRecord(source="x", source_id="y", title="Deep Nets, Part 2: Advanced Systems")
    assert check_title("Deep Nets, Part 1: Basics of Learning", part).status == "mismatch"


@pytest.mark.parametrize(
    ("text", "key"),
    [
        ("Advances in Neural Information Processing Systems 30", "neurips"),
        ("NIPS", "neurips"),
        ("2016 IEEE Conference on Computer Vision and Pattern Recognition (CVPR)", "cvpr"),
        ("IEEE/CVF International Conference on Computer Vision", "iccv"),
        ("Proceedings of NAACL-HLT 2019", "naacl"),
        (
            "Proceedings of the 2019 Conference of the North American Chapter of the Association "
            "for Computational Linguistics",
            "naacl",
        ),
        ("Transactions of the Association for Computational Linguistics", "tacl"),
        ("CoRR", "arxiv"),
        ("The Lancet", None),
        ("UAI", "uai"),
        ("Proceedings of the Thirty-Seventh Conference on Uncertainty in Artificial Intelligence",
         "uai"),
        ("International Conference on Artificial Intelligence and Statistics", "aistats"),
        ("Proceedings of Thirty Fifth Conference on Learning Theory", "colt"),
        ("WWW '22: Proceedings of the ACM Web Conference 2022", "www"),
        ("ICASSP 2023 - IEEE International Conference on Acoustics, Speech and Signal Processing",
         "icassp"),
        ("Medical Image Computing and Computer-Assisted Intervention", "miccai"),
        ("Transactions on Machine Learning Research", "tmlr"),
        ("\\url{https://www.tensorflow.org/}", None),  # a URL is not the Web Conference
    ],
)  # fmt: skip
def test_canonical_venue(text: str, key: str | None) -> None:
    assert canonical_venue(text) == key


# ------------------------------------------------------------------ whole records


def test_evaluate_correct_entry(demo: dict[str, EntryInfo], cvpr: SourceRecord) -> None:
    match = evaluate(demo["he2016deep"], cvpr)
    assert match.acceptable
    assert (match.title.status, match.authors.status, match.year.status, match.venue.status) == (
        "match", "match", "match", "match",
    )  # fmt: skip


def test_fake_duplicate_is_never_acceptable(demo: dict[str, EntryInfo]) -> None:
    fake = crossref.parse_work(load("crossref/work_65215_ysbyhc05.json")["message"])
    assert suspicious_reason(fake, 2017) is not None
    match = evaluate(demo["vaswani2017attention"], fake)
    assert match.title.status == "match"
    assert not match.acceptable


def test_best_candidate_from_crossref_search(demo: dict[str, EntryInfo]) -> None:
    candidates = crossref.parse_work_list(load("crossref/biblio_t2.json"))
    best = best_candidate(demo["he2016deep"], candidates)
    assert best is not None
    assert best.record.doi == "10.1109/cvpr.2016.90"  # ranked 3rd by Crossref, still found


def test_no_candidate_for_fabricated_reference(demo: dict[str, EntryInfo]) -> None:
    candidates = crossref.parse_work_list(load("crossref/biblio_t8.json"))
    assert best_candidate(demo["lindqvist2024quantum"], candidates) is None


def test_wrong_paper_guard() -> None:
    info = EntryInfo(
        "k", "Some Title Of A Paper", parse_authors("Smith, A."), 2020, None, "article"
    )
    record = SourceRecord(
        source="x", source_id="1", title="Some Title Of A Paper",
        authors=(Person(family="Jones"),), year=2005,
    )  # fmt: skip
    assert not evaluate(info, record).acceptable


def test_compound_surnames_written_differently_match() -> None:
    # Crossref: "RichardWebster, Brandon"; the entry: "Brandon Richard Webster"
    record = SourceRecord(
        source="crossref", source_id="x", title="t",
        authors=(Person("RichardWebster", "Brandon"), Person("Sánchez-Fernández", "Luis")),
    )  # fmt: skip
    entry = parse_authors("Brandon Richard Webster and Luis Sánchez Fernández")
    assert check_authors(entry, record).status == "match"


def test_a_one_letter_slip_in_a_source_needs_the_same_given_name() -> None:
    # a Crossref record with "Hut" for Jiahui Hu and "Rent" for Kui Ren
    record = SourceRecord(
        source="crossref", source_id="x", title="t",
        authors=(Person("Hut", "Jiahui"), Person("Rent", "Kui")),
    )  # fmt: skip
    assert check_authors(parse_authors("Jiahui Hu and Kui Ren"), record).status == "match"
    other = check_authors(parse_authors("Wei Hu and Kui Ren"), record)
    assert other.missing == ("Wei Hu",)  # another given name: another person


@pytest.mark.parametrize(
    ("venue", "status"),
    [
        # invented venue names on CVPR papers (HALLMARK nonexistent_venue)
        ("Annual Conference on Spatial Intelligence", "mismatch"),
        ("Transactions on Autonomous Learning Systems", "mismatch"),
        # the same venue written another way is never a mismatch
        ("CVPR", "match"),
        ("IEEE/CVF Conference on Computer Vision and Pattern Recognition", "match"),
        ("Proc. IEEE Conf. Comp. Vis. Patt. Recog.", "unknown"),
        # a real venue sharing words with the record: not enough evidence either way
        ("Pattern Recognition", "unknown"),
        # too little to judge
        ("Spatial", "unknown"),
        (None, "unknown"),
    ],
)
def test_venues_nobody_recognises(venue: str | None, status: str) -> None:
    cvpr = SourceRecord(source="dblp", source_id="x", title="t", venue="CVPR")
    assert check_venue(venue, cvpr).status == status


@pytest.mark.parametrize(
    ("venue", "recorded", "status"),
    [
        # one word the recorded venue does not have is enough...
        ("International Conference on Quantum Machine Learning", "ICML", "mismatch"),
        ("Journal of Statistical Machine Learning Theory", "ICML", "mismatch"),
        ("Conference on Disentangled Representations", "ICLR", "mismatch"),
        # ...but abbreviations, ordinals, series and publishers are not such words
        ("Adv. Neural Inf. Process. Syst.", "NeurIPS", "unknown"),
        ("Int. Conf. Mach. Learn.", "ICML", "unknown"),
        ("Proceedings of Machine Learning Research", "ICML", "unknown"),
        ("OpenReview.net", "ICLR", "unknown"),
        ("Proc. of the Thirty-Fifth Conference on Artificial Intelligence", "AAAI", "unknown"),
        # a workshop's name rarely contains its venue's: it must share no word at all
        ("Workshop on Machine Learning for Creativity", "ICML", "unknown"),
        ("ACM Workshop on Spatial Intelligence", "ICML", "mismatch"),
        # a workshop at another meeting is the work's workshop version (2607.13394v1, Pavlova)
        ("ICLR 2025 Workshop on Building Trust in Language Models and Applications", "ICML",
         "unknown"),
        ("ICLR", "ICML", "mismatch"),
    ],
)  # fmt: skip
def test_unrecognised_venues_naming_something_else(venue: str, recorded: str, status: str) -> None:
    record = SourceRecord(source="dblp", source_id="x", title="t", venue=recorded)
    assert check_venue(venue, record).status == status


def test_only_venue_names_are_judged() -> None:
    # a publisher or a howpublished note is not where the entry names its venue
    record = SourceRecord(source="dblp", source_id="x", title="t", venue="CVPR")
    assert check_venue("Curran Associates", record, named=False).status == "unknown"
    entry = parse_bib_text(
        "@inproceedings{k, title = {T}, publisher = {Curran Associates}, year = {2020}}",
        Path("refs.bib"),
    ).entries[0]
    assert EntryInfo.from_entry(entry).venue_field == "publisher"


@pytest.mark.parametrize(
    ("ours", "theirs", "differ"),
    [
        # HALLMARK swapped authors: the surname stays, the person changes
        ("Sharma, Aviral", "Sharma, Archit", True),
        ("Feng, Sheng", "Feng, Shi", True),
        ("Suriana, Pratham", "Suriana, Patricia", True),
        # one person written differently
        ("Smith, J.", "Smith, John", False),
        ("Smith, Alex", "Smith, Alexander", False),
        ("Acar, Durmus", "Acar, Durmus Alp Emre", False),
        ("Zhu, Jun-Yan", "Zhu, Junyan", False),
        ("Gates, Bill", "Gates, William", False),
        ("Belkin, Mikhail", "Belkin, Misha", False),
        ("Cottrell, Garrison W.", "Cottrell, Gary", False),  # dblp's name for him
        ("Cohen-Or, Daniel", "Cohen-Or, Danny", False),  # Crossref's name for him
        ("Brown, JR", "Brown, John R.", False),  # Google Scholar's initials, without dots
        ("Krathwohl, DR", "Krathwohl, David R.", False),
        ("Karvounarakis, Grigoris", "Karvounarakis, Gregory", False),  # one name, two languages
        ("Papadopoulos, Giorgos", "Papadopoulos, George", False),
        ("Korbak, Tomek", "Korbak, Tomasz", False),  # a Polish diminutive
        ("Spiridonov, Aleksandar", "Spiridonov, Alexander", False),
        ("Levine, Sergey", "Levine, Sergei", False),
        ("{OpenAI}", "{OpenAI}", False),
    ],
)  # fmt: skip
def test_given_names_differ(ours: str, theirs: str, differ: bool) -> None:
    (a,), (b,) = parse_authors(ours).people, parse_authors(theirs).people
    assert given_names_differ(a, b) is differ


def test_co_authors_sharing_a_surname_pair_up_by_given_name() -> None:
    record = SourceRecord(
        source="dblp", source_id="x", title="t",
        authors=(Person("Song", "Yang"), Person("Song", "Jiaming")),
    )  # fmt: skip
    check = check_authors(parse_authors("Jiaming Song and Yang Song"), record)
    assert check.renamed == ()
    other = check_authors(parse_authors("Yang Song and Aviral Song"), record)
    assert other.renamed == (("Aviral Song", "Jiaming Song"),)
    # an initial agrees with both: it must not take the one only the full name can have
    lins = SourceRecord(
        source="dblp", source_id="y", title="t",
        authors=(Person("Lin", "Yen-Ting"), Person("Lin", "Yuan")),
    )  # fmt: skip
    check = check_authors(parse_authors("Lin, Y. and Lin, Yen-Ting"), lins)
    assert (check.status, check.renamed, check.missing) == ("match", (), ())


def test_a_name_in_two_scripts_and_a_suffix_are_one_person() -> None:
    # SDSS DR17 on Crossref (10.3847/1538-4365/ac4414): "Lin 林, Lihwai 俐 暉", "Davidson Jr."
    record = crossref.parse_work(
        {
            "DOI": "10.3847/1538-4365/ac4414",
            "title": ["The Seventeenth Data Release of the Sloan Digital Sky Surveys"],
            "author": [
                {"given": "Y. Sophia 昱", "family": "Dai 戴"},
                {"given": "James W.", "family": "Davidson Jr."},
                {"given": "Lihwai 俐 暉", "family": "Lin 林"},
                {"given": "Yen-Ting", "family": "Lin"},
                {"given": "Sicheng", "family": "Lin"},
            ],
        }
    )
    written = (
        "Dai, Y. Sophia and Davidson, Jr., James W. and Lin, Lihwai and Lin, Yen-Ting and "
        "Lin, Sicheng"
    )
    check = check_authors(parse_authors(written), record)
    assert (check.status, check.renamed, check.missing) == ("match", (), ())


def test_an_unrecognised_record_venue_is_never_a_mismatch() -> None:
    record = SourceRecord(source="crossref", source_id="x", title="t", venue="J. Obscure Stud.")
    assert check_venue("Annual Conference on Spatial Intelligence", record).status == "unknown"


def test_family_name_then_initials_without_a_comma() -> None:
    # "Zhang C. and Zhang T. and Wang L." (a real paper's .bib) reads as given name "Zhang",
    # family "C."; the record's Zhang, Zhang and Wang are the people meant
    record = SourceRecord(
        source="crossref", source_id="x", title="t",
        authors=(Person("Zhang", "Chenyu"), Person("Zhang", "Tianyu"), Person("Wang", "Lei")),
    )  # fmt: skip
    check = check_authors(parse_authors("Zhang C. and Zhang T. and Wang L."), record)
    assert (check.status, check.missing) == ("match", ())
    # a family name that is an initial stays one when the record has it
    malcolm = SourceRecord(source="x", source_id="y", title="t", authors=(Person("X", "Malcolm"),))
    assert check_authors(parse_authors("Malcolm X"), malcolm).status == "match"
    # and other people are still other people
    others = check_authors(parse_authors("Doe J. and Roe R."), record)
    assert others.disjoint
    # the registry may be the side that swapped them (Crossref: given "Shwetha", family "S")
    crossref = SourceRecord(
        source="crossref", source_id="z", title="t",
        authors=(Person("Mondal", "Ishani"), Person("S", "Shwetha")),
    )  # fmt: skip
    swapped = check_authors(parse_authors("Mondal, Ishani and Shwetha, S"), crossref)
    assert (swapped.status, swapped.missing) == ("match", ())


def test_a_team_is_one_author_named_by_its_project() -> None:
    # arXiv 2503.19786 lists "Gemma Team" first; papers cite it as "Gemma" or "Gemma Team"
    record = SourceRecord(
        source="arxiv", source_id="2503.19786", title="Gemma 3 Technical Report",
        authors=(Person.from_display("Gemma Team"), Person("Kamath", "Aishwarya")),
    )  # fmt: skip
    assert record.authors[0].literal == "Gemma Team"
    for written in ("{Gemma} and Kamath, A.", "{Gemma Team} and Kamath, A."):
        check = check_authors(parse_authors(written), record)
        assert (check.status, check.missing, check.first_author_match) == ("match", (), True)
    ligo = Person("The LIGO Scientific Collaboration", literal="The LIGO Scientific Collaboration")
    assert surname_key(ligo) == surname_key(Person("LIGO Scientific", literal="LIGO Scientific"))
    # a person is still a person, and another team another author
    assert Person.from_display("Ann Teamson") == Person("Teamson", "Ann")
    other = check_authors(parse_authors("{Llama Team} and Kamath, A."), record)
    assert not other.first_author_match


@pytest.mark.parametrize(
    ("written", "recorded"),
    [
        # entries of real papers, as BibTeX reads them: given name "Chameleon", family "Team"
        ("Team, Chameleon", "Chameleon Team"),
        ("Team, Gemini and Anil, Rohan", "Gemini Team"),
        ("Gemma Team and Aishwarya Kamath and others", "Gemma Team"),
        ("Collaboration, Euclid and others", "Euclid Collaboration"),
        (r"Collaboration, {\relax DESI} and others", "DESI Collaboration"),
        ("Gopakumar, Vignesh and Team, MAST", "MAST Team"),
    ],
)
def test_a_team_written_as_a_name_is_the_team(written: str, recorded: str) -> None:
    record = SourceRecord(
        source="arxiv", source_id="x", title="t",
        authors=(Person.from_display(recorded), Person("Anil", "Rohan"),
                 Person("Gopakumar", "Vignesh"), Person("Kamath", "Aishwarya")),
        authors_ordered=False,
    )  # fmt: skip
    check = check_authors(parse_authors(written), record)
    assert (check.missing, check.disjoint) == ((), False)


def test_a_generational_suffix_in_the_family_name_is_no_surname() -> None:
    # Crossref has family "Smith IV" in one record and family "Smith", suffix "IV" in another;
    # the entry writes "Smith IV, David H" (real papers, ITiCSE 2024)
    record = SourceRecord(
        source="crossref", source_id="10.1145/3649217.3653587", title="T",
        authors=(Person("Denny", "Paul"), Person("Smith", "David H.")),
    )  # fmt: skip
    check = check_authors(parse_authors("Denny, Paul and Smith IV, David H"), record)
    assert (check.status, check.missing) == ("match", ())


def test_an_organisation_leading_the_record_is_not_the_first_author() -> None:
    # arXiv 2303.08774 (GPT-4 Technical Report) lists "OpenAI", then Josh Achiam, ...
    record = SourceRecord(
        source="arxiv", source_id="2303.08774", title="GPT-4 Technical Report",
        authors=(Person("OpenAI"), Person("Achiam", "Josh"), Person("Adler", "Steven")),
    )  # fmt: skip
    check = check_authors(parse_authors("Achiam, Josh and Adler, Steven"), record)
    assert check.first_author_match
    assert check_authors(parse_authors("{OpenAI}"), record).first_author_match
    # anyone else first is still not the first author
    assert not check_authors(
        parse_authors("Adler, Steven and Achiam, Josh"), record
    ).first_author_match
    # "Cursor Research" on arXiv 2603.24477 is an organisation too
    cursor = SourceRecord(
        source="arxiv", source_id="2603.24477", title="Composer 2 Technical Report",
        authors=(Person.from_display("Cursor Research"), Person.from_display("Aaron Chan")),
    )  # fmt: skip
    assert check_authors(parse_authors("Aaron Chan"), cursor).first_author_match


def test_a_solar_symbol_is_the_word_sun() -> None:
    # ADS writes "M$_{sun}$" where Crossref has "M_⊙" (Girardi et al. 2000, real paper)
    entry = "Isochrones for low- and intermediate-mass stars: From 0.15 to 7 M_sun"
    record = "Isochrones for low- and intermediate-mass stars: From 0.15 to 7 M_\u2299"
    assert changed_words(entry, record) == ()


@pytest.mark.parametrize(
    ("written", "recorded"),
    [
        ("O'Connell, Julia", "O\u2019Connell"),  # Crossref's curly apostrophe (real papers)
        ("D'Orazi, V.", "D\u2019Orazi"),
        ("Dell'Oro, A.", "Dell\u2019Oro"),
        ("{Abdurro'uf}", "Abdurro\u2019uf"),
    ],
)
def test_apostrophes_do_not_make_another_person(written: str, recorded: str) -> None:
    record = SourceRecord(
        source="crossref", source_id="x", title="t", authors=(Person(recorded, "J."),)
    )
    check = check_authors(parse_authors(written), record)
    assert (check.status, check.missing) == ("match", ())


@pytest.mark.parametrize(
    ("entry", "recorded"),
    [
        # IEEE's section label (10.1109/mci.2015.2471235)
        ("Ensemble Classification and Regression-Recent Developments, Applications and Future "
         "Directions", "Ensemble Classification and Regression-Recent Developments, "
         "Applications and Future Directions [Review Article]"),
        # a letter Crossref lost (10.1007/bf01336768)
        ("Berechnung der nat{\\\"u}rlichen Linienbreite auf Grund der Diracschen Lichttheorie",
         "Berechnung der nat\ufffdrlichen Linienbreite auf Grund der Diracschen Lichttheorie"),
        # Crossref keeps only the main title (10.1016/bs.aamop.2017.02.003)
        ("Optical Nanofibers: A New Platform for Quantum Optics", "Optical Nanofibers"),
        # the journal's note that discussions follow (Bayesian Analysis 16, 667)
        ("Rank-normalization, folding, and localization: An improved R for assessing "
         "convergence of MCMC", "Rank-Normalization, Folding, and Localization: An Improved R "
         "for Assessing Convergence of MCMC (with Discussion)"),
        # a chapter's title field that also names its book, set with \textup (real paper)
        ("\\textup{Quarks and Strings on a Lattice, in} New Phenomena in Subnuclear Physics",
         "Quarks and Strings on a Lattice"),
        # a word in typewriter type is a word
        ("\\texttt{torch.compile}: Faster Training with Graph Capture",
         "torch.compile: Faster Training with Graph Capture"),
    ],
)  # fmt: skip
def test_registry_title_artefacts_are_not_differences(entry: str, recorded: str) -> None:
    (parsed,) = parse_bib_text(f"@article{{k, title = {{{entry}}}}}", Path("x.bib")).entries
    record = SourceRecord(source="crossref", source_id="x", title=recorded)
    check = check_title(parsed.text("title"), record)
    assert check.status in {"match", "variant"}
    assert not check.changed


def test_only_a_named_book_after_in_is_the_container() -> None:
    record = SourceRecord(source="crossref", source_id="x", title="Learning in High Dimension")
    assert check_title("Learning in High Dimension, in particular for deep nets", record).changed


def test_dblp_titles_lose_their_tex() -> None:
    from paper_preflight.sources.dblp import clean_title

    title = clean_title("The Optimal Hard Threshold for Singular Values is \\(4/\\sqrt {3}\\).")
    assert "\\" not in title
    assert not title.endswith(".")


def test_a_lost_letter_matches_only_its_place() -> None:
    record = SourceRecord(source="crossref", source_id="x", title="Ein nat\ufffdrlicher Fall")
    assert check_title("Ein natürlicher Fall", record).changed == ()
    assert check_title("Ein künstlicher Fall", record).changed


@pytest.mark.parametrize(
    ("journal", "recorded", "aliases", "status"),
    [
        # LIONESS is iScience 14 (2019); the entry says Nature Communications
        ("Nature Communications", "iScience", (), "mismatch"),
        # abbreviations are the same journal
        ("IEEE Transactions on Pattern Analysis and Machine Intelligence",
         "IEEE Trans. Pattern Anal. Mach. Intell.", (), "unknown"),
        ("J. Mach. Learn. Res.", "Journal of Machine Learning Research", (), "unknown"),
        # Crossref's short title counts as a name of the journal
        ("Phys. Rev. Lett.", "Physical Review Letters", ("Phys. Rev. Lett.",), "unknown"),
        # a meeting's name in the journal field is not compared (dblp names meetings by acronym)
        ("Proceedings of the 26th Symposium on Principles of Database Systems", "PODS", (),
         "unknown"),
        # nor a name in another language
        ("Fracture and Structural Integrity", "Frattura ed Integrità Strutturale", (), "unknown"),
    ],
)  # fmt: skip
def test_journal_names_are_compared_word_by_word(
    journal: str, recorded: str, aliases: tuple[str, ...], status: str
) -> None:
    record = SourceRecord(source="crossref", source_id="x", title="t", venue=recorded,
                          venue_aliases=aliases)  # fmt: skip
    assert check_venue(journal, record, journal=True).status == status
    assert check_venue(journal, record, journal=False).status == "unknown"  # a booktitle


def test_a_shared_issn_is_the_same_journal() -> None:
    record = SourceRecord(source="crossref", source_id="x", title="t", venue="Frattura ed "
                          "Integrità Strutturale", issns=frozenset({"1971-8993"}))  # fmt: skip
    assert check_venue("Fracture", record, issns=frozenset({"1971-8993"})).status == "match"


@pytest.mark.parametrize(
    ("written", "recorded"),
    [
        # the group's words in another order, with a hyphen, or with a footnote mark (heldout2)
        ("{LLM-Core Xiaomi} and Xiao, Bangjun", "Xiaomi LLM-Core Team"),
        ("Kimi-Team and Du, Angang", "Kimi Team"),
        ("{DeepSeek-AI} and Xiao, Bangjun", " DeepSeek-AI"),
        ("{The Tabula Sapiens Consortium}", "The Tabula Sapiens Consortium*"),
    ],
)
def test_a_group_written_another_way_is_the_group(written: str, recorded: str) -> None:
    people = [Person.from_display(recorded), Person("Xiao", "Bangjun"), Person("Du", "Angang")]
    if recorded.endswith("*"):  # Crossref: the whole name as a family name, no given name
        people[0] = Person(recorded)
    record = SourceRecord(source="x", source_id="x", title="t", authors=tuple(people))
    check = check_authors(parse_authors(written), record)
    assert (check.missing, check.first_author_match) == ((), True)


def test_groups_and_people_are_not_compared() -> None:
    members = SourceRecord(
        source="crossref", source_id="10.1016/j.cell.2022.01.012", title="t",
        authors=(Person("Ahern", "David J."), Person("Ai", "Zhichao")),
    )  # fmt: skip
    # Cell credits the COMBAT Consortium; Crossref lists its members
    combat = r"{COvid-19 Multi-omics Blood ATlas (COMBAT) Consortium}"
    assert check_authors(parse_authors(combat), members).status == "unknown"
    # dblp names only "DeepSeek-AI" for the DeepSeek-R1 report, the Nature paper its people
    organisation = SourceRecord(
        source="dblp", source_id="x", title="t", authors=(Person("DeepSeek-AI"),)
    )
    assert check_authors(parse_authors("Guo, Daya and Yang, Dejian"), organisation).status == (
        "unknown"
    )
    # an organisation that is no group is still another author: "Meta AI" for SAM 3's authors
    assert check_authors(parse_authors("{Meta AI}"), members).disjoint


def test_a_lab_credited_with_its_author() -> None:
    # Crossref 10.64434/tml.20251026 lists the lab first; the lab asks for "Kevin Lu and
    # Thinking Machines Lab"
    record = SourceRecord(
        source="crossref", source_id="x", title="On-Policy Distillation",
        authors=(Person("Thinking Machines Lab", literal="Thinking Machines Lab"),
                 Person("Lu", "Kevin")),
    )  # fmt: skip
    check = check_authors(parse_authors("Kevin Lu and Thinking Machines Lab"), record)
    assert (check.status, check.missing, check.first_author_match) == ("match", (), True)
    # where the record lists only people, a lab the entry adds is no missing person
    alone = SourceRecord(source="x", source_id="x", title="t", authors=(Person("Lu", "Kevin"),))
    check = check_authors(parse_authors("Kevin Lu and Thinking Machines Lab"), alone)
    assert (check.status, check.missing) == ("match", ())


@pytest.mark.parametrize(
    ("written", "recorded"),
    [
        ("Shenoy, Vijendra S.", Person("S", "Vijendra Shenoy")),  # Crossref, heldout2
        ("Do, Xuan Long", Person("Long", "Do")),  # Crossref: Do Xuan Long, family name Do
        ("De Luo, Henry", Person.from_display("De Luo")),  # arXiv lists him as "De Luo"
        ("De La Torre", Person("De La Torre", "Steven A.")),  # BibTeX: given name "De La"
        ("Stimper Vincent", Person("Stimper", "Vincent")),  # family name first, no comma
    ],
)
def test_one_name_split_another_way(written: str, recorded: Person) -> None:
    record = SourceRecord(
        source="x", source_id="x", title="t", authors=(recorded, Person("Rai", "Thripthi"))
    )
    check = check_authors(parse_authors(f"{written} and Rai, Thripthi"), record)
    assert (check.missing, check.renamed, check.first_author_match) == ((), (), True)


def test_other_names_stay_other_people() -> None:
    record = SourceRecord(
        source="arxiv", source_id="2410.00425", title="ManiSkill3",
        authors=(Person("Tao", "Stone"), Person("Hinrichsen", "Xander"), Person("Yuan", "Xiaodi")),
    )  # fmt: skip
    check = check_authors(parse_authors("Tao, Stone and Hu, Xander and Yuan, Michael"), record)
    assert check.missing == ("Xander Hu",)
    assert check.renamed == (("Michael Yuan", "Xiaodi Yuan"),)
    # a family name must be among the other's words: Wei Li is not Wei Li Zhang
    other = SourceRecord(source="x", source_id="x", title="t", authors=(Person("Zhang", "Wei Li"),))
    assert check_authors(parse_authors("Li, Wei"), other).disjoint


def test_a_registry_label_after_the_title() -> None:
    # Semantic Scholar's title of Holmberg (1937) ends in the plates section ADS lists apart
    record = SourceRecord(
        source="s2", source_id="x",
        title="A Study of Double and Multiple Galaxies Together with Inquiries into some General"
        " Metagalactic Problems. Plates.",
    )  # fmt: skip
    title = (
        "A Study of Double and Multiple Galaxies Together with Inquiries into some General"
        " Metagalactic Problems"
    )
    assert check_title(title, record).changed == ()


def test_a_chapter_in_springers_inbook_export() -> None:
    entry = parse_bib_text(
        "@Inbook{b, author={Bartholomew, Michael and Lee, Joohyung},"
        " chapter={System aspmt2smt: Computing ASPMT Theories by SMT Solvers},"
        " title={Logics in Artificial Intelligence: 14th European Conference, JELIA 2014},"
        " publisher={Springer}, year={2014}}",
        Path("x.bib"),
    ).entries[0]
    info = EntryInfo.from_entry(entry)
    assert info.title == "System aspmt2smt: Computing ASPMT Theories by SMT Solvers"
    assert (info.venue_field, info.venue) == (
        "booktitle",
        "Logics in Artificial Intelligence: 14th European Conference, JELIA 2014",
    )
    numbered = parse_bib_text("@inbook{c, chapter={7}, title={A Book}}", Path("x.bib")).entries[0]
    assert EntryInfo.from_entry(numbered).title == "A Book"
