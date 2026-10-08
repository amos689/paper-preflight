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
    first_page,
    given_names_differ,
    is_preprint,
    same_person,
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
    # "et al." run into the one name given (2610.00027v1, ralph2020empirical)
    cut = parse_authors("Paul Ralph et al.")
    assert [(p.given, p.family) for p in cut.people] == [("Paul", "Ralph")]
    assert cut.truncated
    assert not parse_authors("Ralph, Paul").truncated


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
    assert omitted.left_out == ()  # a list cut short: nobody is left out before a listed name
    # ResNet's Shaoqing Ren dropped from between Zhang and Sun
    dropped = check_authors(parse_authors("He, Kaiming and Zhang, Xiangyu and Sun, Jian"), cvpr)
    assert dropped.note == "some authors omitted"
    assert [name.split()[-1] for name in dropped.left_out] == ["Ren"]
    # an affiliation or a placeholder in the record is nobody left out, nor is anyone in a
    # collaboration's list of hundreds
    for odd in ("Westbrook Polytechnic University, Northvale", "Paper Authors",
                "The Fictional Survey Collaboration"):  # fmt: skip
        record = replace(cvpr, authors=(cvpr.authors[0], Person(family=odd), cvpr.authors[1]))
        assert check_authors(two, record).left_out == (), odd
    many = tuple(Person(family=f"Quill{i}", given="Ada") for i in range(40))
    crowd = replace(cvpr, authors=(cvpr.authors[0], *many, cvpr.authors[1]))
    assert check_authors(two, crowd).left_out == ()
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
        # an ampersand for "and" (2609.09561v1, zhang2018taxogen)
        ("Proceedings of the 24th ACM SIGKDD International Conference on Knowledge Discovery "
         "& Data Mining", "kdd"),
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


def test_semantic_scholars_venue_counts_only_for_a_match() -> None:
    # S2 files the ACL 2004 workshop Text Summarization Branches Out (ROUGE) under ACL
    acl = "Annual Meeting of the Association for Computational Linguistics"
    s2 = SourceRecord(source="s2", source_id="x", title="t", venue=acl)
    assert check_venue("Text Summarization Branches Out", s2).status == "unknown"
    assert check_venue("Proceedings of ACL", s2).status == "match"
    assert check_venue("NeurIPS", s2).status == "unknown"
    assert check_venue("NeurIPS", replace(s2, source="dblp", venue="ACL")).status == "mismatch"


def test_software_cited_by_its_name_and_what_it_does() -> None:
    from paper_preflight.match import check_title

    record = SourceRecord(source="datacite", source_id="x", title="spaCy", work_type="software")
    title = "spaCy: Industrial-strength Natural Language Processing in Python"
    assert check_title(title, record).status == "match"
    assert check_title("Gensim: Topic modelling", record).status == "mismatch"
    assert check_title(title, replace(record, work_type="text")).status == "mismatch"


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
        ("Salakhutdinov, Russ R", "Salakhutdinov, Ruslan", False),  # NeurIPS's name for him
        ("Cohen-Or, Daniel", "Cohen-Or, Danny", False),  # Crossref's name for him
        ("Brown, JR", "Brown, John R.", False),  # Google Scholar's initials, without dots
        ("Krathwohl, DR", "Krathwohl, David R.", False),
        ("Karvounarakis, Grigoris", "Karvounarakis, Gregory", False),  # one name, two languages
        ("Papadopoulos, Giorgos", "Papadopoulos, George", False),
        ("Korbak, Tomek", "Korbak, Tomasz", False),  # a Polish diminutive
        ("Spiridonov, Aleksandar", "Spiridonov, Alexander", False),
        ("Levine, Sergey", "Levine, Sergei", False),
        ("{OpenAI}", "{OpenAI}", False),
        ("Ren, Freddy", "Ren, Frederic", False),  # Crossref's Frederic Ren
        ("Chen, Ricky T. Q.", "Chen, Tian Qi", False),  # dblp's Tian Qi Chen
        # a name and one initial are a middle name's, not the other's initials
        ("Horowitz, Seth A.", "Horowitz, Aaron", True),
    ],
)  # fmt: skip
def test_given_names_differ(ours: str, theirs: str, differ: bool) -> None:
    (a,), (b,) = parse_authors(ours).people, parse_authors(theirs).people
    assert given_names_differ(a, b) is differ


@pytest.mark.parametrize(
    ("ours", "theirs", "same"),
    [
        ("Raymond, Alain", "Raymond-Saez, Alain", True),  # a double surname's first part
        ("Karthikeyan, P.", "Palanisamy, K.", True),  # Crossref's order for one name
        ("Kim, P.", "Park, K.", False),  # surnames too short to tell: two people
        ("Garcia, Ana", "Lopez, Ana", False),
    ],
)  # fmt: skip
def test_one_person_in_another_form(ours: str, theirs: str, same: bool) -> None:
    (a,), (b,) = parse_authors(ours).people, parse_authors(theirs).people
    assert same_person(a, b) is same


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


def test_a_title_deposited_as_a_given_name_is_no_name() -> None:
    # Crossref's "Prof." for Wenhong Tian (10.18653/v1/2024.naacl-industry.2, 2609.17943v1)
    assert Person.from_parts("Prof.", "Tian") == Person("Tian", "")
    assert Person.from_parts("Prof. Dr. Anna", "Schmidt") == Person("Schmidt", "Anna")
    assert Person.from_parts("Drew", "Bagnell").given == "Drew"  # a name, not "Dr."
    record = SourceRecord(source="crossref", source_id="x", title="t",
                          authors=(Person.from_parts("Prof.", "Tian"),))  # fmt: skip
    check = check_authors(parse_authors("Tian, Wenhong"), record)
    assert (check.missing, check.renamed) == ((), ())


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


@pytest.mark.parametrize(
    ("written", "recorded"),
    [
        # dblp's "Sabela Ramos Garea" (2609.02006v1, agarwal2024gkd), split as given "Sabela Ramos"
        ("Ramos, Sabela", Person.from_display("Sabela Ramos Garea")),
        ("Dehghani, Zahra", Person.from_display("Zahra Dehghani Tafti")),  # dehghani2026universal
    ],
)
def test_a_double_surname_cited_by_its_first_part(written: str, recorded: Person) -> None:
    record = SourceRecord(source="dblp", source_id="x", title="t", authors=(recorded,))
    check = check_authors(parse_authors(written), record)
    assert (check.missing, check.renamed, check.first_author_match) == ((), (), True)
    # another given name is another person
    family = written.split(",")[0]
    assert check_authors(parse_authors(f"{family}, Ana"), record).disjoint


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


# ------------------------------------------------------------------ journal coordinates


@pytest.mark.parametrize(
    ("pages", "first"),
    [
        ("523--537", "523"),
        ("523–537", "523"),
        ("L25--L28", "l25"),
        ("083509", "083509"),
        ("47, 59", "47"),
        ("", None),
        (None, None),
    ],
)
def test_first_page(pages: str | None, first: str | None) -> None:
    assert first_page(pages) == first


def test_entry_info_keeps_volume_and_first_page() -> None:
    (entry,) = parse_bib_text(
        "@article{k, author={Burkert, A.}, journal={The Astrophysical Journal Letters},"
        " volume={447}, pages={L25--L28}, year={1995}}",
        Path("refs.bib"),
    ).entries
    info = EntryInfo.from_entry(entry)
    assert (info.volume, info.first_page) == ("447", "l25")


def test_a_database_is_cited_by_the_year_it_was_used() -> None:
    # USGS asks for its National Water Information System to be cited with the year of access;
    # DataCite's 1994 (10.5066/F7P55KJN, a "Collection") is when the service started
    record = SourceRecord(
        source="datacite", source_id="10.5066/f7p55kjn", title="USGS Water Data for the Nation",
        year=1994, years=frozenset({1994}), work_type="collection",
    )  # fmt: skip
    assert check_year(2026, record).status == "variant"
    assert check_year(1990, record).status == "mismatch"  # before it existed
    assert check_year(2099, record).status == "mismatch"  # not yet used
    article = replace(record, work_type="journal-article")
    assert check_year(2026, article).status == "mismatch"


def test_a_workshop_in_a_joint_dblp_volume_is_not_another_venue() -> None:
    # STACOM 2024 is in the joint volume dblp names "CMRxRecon/MBAS/STACOM@MICCAI"
    record = SourceRecord(
        source="dblp", source_id="conf/stacom/ChiuRCGPGCMV24", title="Physics-Informed ...",
        venue="CMRxRecon/MBAS/STACOM@MICCAI",
    )  # fmt: skip
    workshop = "International Workshop on Statistical Atlases and Computational Models of the Heart"
    assert check_venue(workshop, record).status == "unknown"
    assert check_venue("Annual Conference on Spatial Intelligence", record).status == "mismatch"
    # a challenge's volume too: "HECKTOR@MICCAI" (2609.05532v1, entry 16)
    hecktor = replace(record, venue="HECKTOR@MICCAI")
    challenge = "3D Head and Neck Tumor Segmentation in PET/CT Challenge"
    assert check_venue(challenge, hecktor).status == "unknown"


def test_preprint_and_report_archives_in_dblp_are_preprints() -> None:
    eprint = SourceRecord(
        source="dblp", source_id="journals/iacr/BabbushZGBKNBDB26", title="t",
        venue="IACR Cryptol. ePrint Arch.",
    )  # fmt: skip
    assert is_preprint(eprint)
    assert is_preprint(replace(eprint, venue="Electron. Colloquium Comput. Complex."))
    assert not is_preprint(replace(eprint, venue="ITCS"))


def test_a_whole_reference_in_a_note_is_read_as_one() -> None:
    # 2609.10121v2 writes each reference as a note, with no title or author fields
    note = (
        r"Boiko, D. A., MacKnight, R., Kline, B. \& Gomes, G. Autonomous chemical research with "
        r"large language models. \emph{Nature} \textbf{624}, 570--578 (2023). "
        r"\url{https://doi.org/10.1038/s41586-023-06792-0}"
    )
    entry = parse_bib_text(f"@misc{{ref02, key = {{02}}, note = {{{note}}}}}", Path("r.bib"))
    info = EntryInfo.from_entry(entry.entries[0])
    assert info.title == "Autonomous chemical research with large language models"
    assert [p.family for p in info.authors.people] == ["Boiko", "MacKnight", "Kline", "Gomes"]
    assert (info.venue, info.venue_field, info.year) == ("Nature", "journal", 2023)
    # a note beside a title is only a note
    titled = parse_bib_text(
        f"@misc{{k, title = {{Own Title}}, note = {{{note}}}}}", Path("r.bib")
    ).entries[0]
    assert EntryInfo.from_entry(titled).authors.people == ()


def test_braces_shown_in_a_title_are_not_searched_for() -> None:
    # PairNorm (2609.09561v1): "{\{}GNN{\}}s" prints as "{GNN}s"
    entry = parse_bib_text(
        r"@inproceedings{k, title = {PairNorm: Tackling Oversmoothing in {\{}GNN{\}}s}}",
        Path("refs.bib"),
    ).entries[0]
    assert EntryInfo.from_entry(entry).title == "PairNorm: Tackling Oversmoothing in GNNs"


def test_a_workshop_paper_is_cited_by_its_workshops_year() -> None:
    # Classifier-Free Diffusion Guidance: NeurIPS 2021 workshop, arXiv 2022 (2609.01997v1)
    record = SourceRecord(
        source="dblp", source_id="journals/corr/abs-2207-12598", title="Classifier-Free ...",
        year=2022, years=frozenset({2022}), venue="CoRR",
    )  # fmt: skip
    workshop = "{NeurIPSW} on Deep Generative Models and Downstream Applications"
    assert check_year(2021, record, venue=workshop).status == "variant"
    assert check_year(2020, record, venue=workshop).status == "mismatch"
    assert check_year(2021, record, venue="NeurIPS").status == "mismatch"
    published = replace(record, source_id="conf/nips/HoS21", venue="NeurIPS")
    assert check_year(2021, replace(published, year=2022), venue=workshop).status == "mismatch"


@pytest.mark.parametrize(
    ("entry", "record", "same"),
    [
        # Vancouver style, which BibTeX reads as given "Rouse D.", family "M."
        ("Rouse D. M.", Person("Rouse", "David M."), True),
        ("Hemami S. S", Person("Hemami", "Sheila S."), True),
        # a given name and family initials, read either way round (HALLMARK's dblp entry)
        ("Mallikarjun B. R.", Person("R.", "Mallikarjun B."), True),
        ("Rouse D. M.", Person("Rouse", "Daniel K."), False),  # another person's initials
        ("Kim P.", Person("Kang", "P. K."), False),
    ],
)
def test_names_in_another_order_with_initials(entry: str, record: Person, same: bool) -> None:
    from paper_preflight.match import same_person

    assert same_person(parse_name(entry), record) is same


def test_a_collaboration_under_a_longer_name_is_on_the_record() -> None:
    # ESO's DataCite records end their author lists with "And The MAGPI Team"
    team = "And The MAGPI Team"
    record = SourceRecord(
        source="datacite", source_id="10.18727/0722-6691/5349", title="Mapping Galaxy ...",
        authors=(Person("Mendel", "J. Trevor"), Person(team, literal=team)),
    )  # fmt: skip
    found = check_authors(parse_authors("Mendel, J. T. and {MAGPI Team}"), record)
    assert found.missing == ()


def test_a_laboratory_credited_among_the_people_is_a_group() -> None:
    # arXiv 2407.14668 lists the people; the entry also credits the collaboration
    # (2609.01971v2, zhang2024universaltranslatorneuraldynamics)
    record = SourceRecord(
        source="arxiv", source_id="2407.14668", title="Towards a Universal Translator ...",
        authors=(Person("Zhang", "Yizi"), Person("Winter", "Olivier"), Person("Dyer", "Eva")),
    )  # fmt: skip
    lab = "{The International Brain Laboratory}"
    written = f"Zhang, Yizi and Winter, Olivier and {lab} and Dyer, Eva"
    assert check_authors(parse_authors(written), record).missing == ()


def test_software_is_matched_by_its_repository_name() -> None:
    # Zenodo titles a release "owner/repo: version"; the entry cites the software by its name
    release = SourceRecord(
        source="datacite", source_id="10.5281/zenodo.591637",
        title="rdkit/rdkit: 2026_09_1 (Q3 2026) Release", work_type="software",
    )  # fmt: skip
    assert check_title("RDKit: Open-source cheminformatics", release).status == "match"
    assert check_title("Pandas: Powerful data structures", release).status == "mismatch"


def test_a_dataset_name_after_the_title_is_not_a_different_title() -> None:
    record = SourceRecord(
        source="arxiv", source_id="2411.04368",
        title="Measuring short-form factuality in large language models",
    )  # fmt: skip
    entry = "Measuring Short-Form Factuality in Large Language Models (SimpleQA)"
    assert check_title(entry, record).status == "variant"
    # the record has the name too, spaced out: it is part of the title
    spaced = SourceRecord(
        source="crossref", source_id="x", title="Basic Reproduction Number (R 0 )"
    )
    assert check_title("Basic Reproduction Number (R0)", spaced).status == "match"


def test_a_short_head_of_five_words_stands_for_a_title_without_its_subtitle() -> None:
    record = SourceRecord(
        source="dblp", source_id="conf/iclr/DosovitskiyB0WZ21",
        title="An Image is Worth 16x16 Words: Transformers for Image Recognition at Scale",
    )  # fmt: skip
    assert check_title("An Image is Worth 16x16 Words", record).status == "variant"


def test_a_joint_meeting_names_both_venues() -> None:
    record = SourceRecord(source="dblp", source_id="conf/acl/Bird06", title="NLTK", venue="ACL")
    venue = "Proceedings of the COLING/ACL 2006 interactive presentation sessions"
    assert check_venue(venue, record).status == "match"
    asplos = SourceRecord(source="dblp", source_id="conf/asplos/X15", title="X", venue="ASPLOS")
    assert check_venue("ACM SIGARCH Computer Architecture News", asplos).status == "unknown"


def test_a_middle_name_may_be_used_by_its_nickname() -> None:
    assert not given_names_differ(Person("Kirby", "Robert M."), Person("Kirby", "Mike"))
    assert given_names_differ(Person("Kirby", "Robert J."), Person("Kirby", "Mike"))


def test_ifmmode_keeps_the_text_branch() -> None:
    from paper_preflight.bib.parse import latex_to_text

    raw = "\\ifmmode \\check{S}\\else \\v{S}\\fi{}upi\\ifmmode \\acute{c}\\else \\'{c}\\fi{}"
    assert latex_to_text(raw) == "Šupić"
