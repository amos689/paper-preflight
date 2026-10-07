"""Turn gathered evidence into one verdict per reference, plus findings (docs/adr/0002).

The resolver collects; this module decides. It follows three rules:

* **Positive evidence only.** An error needs a record that contradicts the entry (REF001, REF010),
  an authority saying an identifier does not exist (REF002), or every required source answering
  "no such work" (REF003). An unavailable source is never counted as an answer.
* **Bind before comparing.** Field findings (REF010-REF014) are only reported against a record the
  entry is bound to: one reached through the entry's own identifier, or a single unambiguous
  search candidate.
* **Abstain loudly.** Everything else is ``cannot_determine`` with reason codes (REF090).
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum

from paper_preflight.bib.ids import Identifier
from paper_preflight.bib.normalize import title_key, word_count
from paper_preflight.bib.parse import BibEntry
from paper_preflight.bibtex import SOURCE_NAMES, escape, format_authors, protect_title
from paper_preflight.findings import Finding, Location, Severity
from paper_preflight.match import (
    NAMED_VENUE_FIELDS,
    TITLE_VARIANT,
    VENUE_FIELDS,
    VENUE_SERIES,
    EntryInfo,
    Match,
    best_candidate,
    canonical_venue,
    evaluate,
    is_preprint,
    related_words,
    subtitle_variant,
    surname_key,
    title_score,
    venue_words,
    wrong_paper,
)
from paper_preflight.resolve import GREY_TYPES, Evidence, looks_cs, unindexed_hosts
from paper_preflight.rules import make_finding
from paper_preflight.sources.record import SourceRecord

MIN_NOT_FOUND_WORDS = 5  # shorter titles are too generic to conclude "not found"
MAX_YEAR_ONLY_GAP = 3  # same title and authors, year off by more than this: do not bind
MIN_TITLE_ONLY_WORDS = 6  # a title this long names one work, even when the authors differ
MIN_TITLE_ANY_YEAR_WORDS = 8  # ... and one this long does even in another year
MIN_VENUE_TITLE_WORDS = 4  # ... and one this long does too, at the same venue in the same year
MAX_REWORDED_WORDS = 2  # a title this many words off is the same work, given the same people
MIN_REWORDED_SCORE = 0.85  # ... and this similar overall
OLD_WORK_YEAR = 1990  # before this, the indexes cover too little to call a work not found


class Verdict(StrEnum):
    VERIFIED = "verified"
    METADATA_MISMATCH = "metadata_mismatch"
    IDENTIFIER_CONFLICT = "identifier_conflict"
    NOT_FOUND = "not_found"
    CANNOT_DETERMINE = "cannot_determine"


class Reason(StrEnum):
    SOURCES_UNAVAILABLE = "SOURCES_UNAVAILABLE"
    OFFLINE_MODE = "OFFLINE_MODE"
    BUDGET_EXHAUSTED = "BUDGET_EXHAUSTED"
    NON_LATIN_UNSUPPORTED = "NON_LATIN_UNSUPPORTED"
    GREY_LITERATURE = "GREY_LITERATURE"
    UNINDEXED_LINK = "UNINDEXED_LINK"
    UNINDEXED_VENUE = "UNINDEXED_VENUE"
    ANONYMOUS = "ANONYMOUS"
    TOO_NEW = "TOO_NEW"
    OLD_WORK = "OLD_WORK"
    IDENTIFIER_EXISTS_NO_METADATA = "IDENTIFIER_EXISTS_NO_METADATA"
    CORRUPTED_SOURCE_RECORD = "CORRUPTED_SOURCE_RECORD"
    AMBIGUOUS_CANDIDATES = "AMBIGUOUS_CANDIDATES"
    INSUFFICIENT_METADATA = "INSUFFICIENT_METADATA"


REASON_TEXT: dict[Reason, tuple[str, str]] = {
    Reason.SOURCES_UNAVAILABLE: ("a source was unavailable", "有来源不可用"),
    Reason.OFFLINE_MODE: ("offline mode and no cached answer", "离线模式且没有缓存结果"),
    Reason.BUDGET_EXHAUSTED: ("the request budget is exhausted", "请求额度已用完"),
    Reason.NON_LATIN_UNSUPPORTED: (
        "non-Latin titles are not supported yet", "暂不支持非拉丁文字的标题",
    ),
    Reason.GREY_LITERATURE: (
        "grey literature without an identifier (book, report, software, web page)",
        "没有标识符的灰色文献（图书、报告、软件、网页等）",
    ),
    Reason.UNINDEXED_LINK: (
        "it links to a site no queried source indexes; check the link",
        "条目链接的网站不在任何已查询来源的收录范围内，请人工核对该链接",
    ),
    Reason.UNINDEXED_VENUE: (
        "a workshop paper, an older book chapter or a web-only publication, which the indexes"
        " often leave out; check it by hand",
        "研讨会论文、较早的图书章节或只在网上发表的文章，索引常未收录，请人工核对",
    ),
    Reason.ANONYMOUS: (
        "an anonymous submission under review, which no index lists",
        "匿名评审中的投稿，任何索引都不收录",
    ),
    Reason.TOO_NEW: ("too recent to be indexed yet", "过新，可能尚未被收录"),
    Reason.OLD_WORK: (
        "published before 1990, when the indexes cover little; check it by hand",
        "1990 年以前的作品，索引收录不全，请人工核对",
    ),
    Reason.IDENTIFIER_EXISTS_NO_METADATA: (
        "the identifier exists but no source returned its metadata",
        "标识符存在，但没有来源返回其元数据",
    ),
    Reason.CORRUPTED_SOURCE_RECORD: (
        "the source record looks corrupted", "来源记录疑似损坏",
    ),
    Reason.AMBIGUOUS_CANDIDATES: (
        "similar works exist but none matches unambiguously", "存在相似作品，但无法确定是哪一篇",
    ),
    Reason.INSUFFICIENT_METADATA: (
        "the title is missing or too short to search reliably", "标题缺失或过短，无法可靠检索",
    ),
}  # fmt: skip

SOURCE_PRIORITY = {
    "crossref": 0, "pubmed": 1, "datacite": 1, "doiorg": 2, "dblp": 3, "openalex": 4, "arxiv": 5,
}  # fmt: skip
# Semantic Scholar's author lists mix initials, orders and duplicates (spike S5; a HALLMARK VALID
# entry with Vietnamese names came back reordered), so they confirm a work but never accuse.
AUTHORS_NOT_CHECKED_AGAINST = frozenset({"s2"})


def source_name(source: str) -> str:
    return SOURCE_NAMES.get(source, source)


@dataclass(frozen=True)
class Assessment:
    key: str
    verdict: Verdict
    reasons: tuple[Reason, ...] = ()
    flags: frozenset[str] = frozenset()
    record: SourceRecord | None = None  # the record the entry is bound to, if any
    findings: tuple[Finding, ...] = ()
    suppressed: frozenset[str] = frozenset()  # rules whose findings a suppression comment dropped


# ---------------------------------------------------------------- helpers


def _location(entry: BibEntry, field: str | None = None) -> Location:
    bib_field = entry.fields.get(field) if field else None
    return Location(entry.file, bib_field.line if bib_field else entry.line, 1)


def _listing(names: list[str], separator: str, last: str) -> str:
    """``A``, ``A and B``, ``A, B and C`` (``A、B 和 C``)."""
    if len(names) <= 1:
        return "".join(names)
    return separator.join(names[:-1]) + last + names[-1]


def _authors_text(record: SourceRecord) -> str:
    people = record.authors
    if not people:
        return "authors unknown"
    first = people[0].family or people[0].display
    if len(people) == 1:
        return first
    if len(people) == 2:
        return f"{first} and {people[1].family or people[1].display}"
    return f"{first} et al."


def non_latin(text: str) -> bool:
    letters = [ch for ch in text if ch.isalpha()]
    if not letters:
        return False
    latin = sum("LATIN" in unicodedata.name(ch, "") for ch in letters)
    return latin / len(letters) < 0.5


def _anchor(record: SourceRecord, identifiers: Iterable[Identifier]) -> Identifier | None:
    """The entry identifier through which a record was reached."""
    doi = (record.doi or "").lower()
    arxiv_id = record.identifiers.get("arxiv")
    for ident in identifiers:
        if ident.scheme == "doi" and doi and ident.value == doi:
            return ident
        if ident.scheme == "arxiv" and arxiv_id and ident.value == arxiv_id:
            return ident
        if ident.scheme in {"pmid", "pmcid"} and ident.value == record.identifiers.get(
            ident.scheme
        ):
            return ident
        if ident.scheme == "doi" and arxiv_id and ident.value == f"10.48550/arxiv.{arxiv_id}":
            return ident
    return None


PLACEHOLDER_TITLE = re.compile(
    r"\b(front matter|back matter|table of contents|title page|editorial board|masthead|"
    r"author index|subject index|session details|untitled)\b|^(contents|index|preface|foreword)$",
    re.IGNORECASE,
)


def versions_known(record: SourceRecord) -> bool:
    """Whether every title a preprint has had is known (titles change between versions).

    arXiv records are complete when the paper has one version or when the resolver fetched the
    versions (``versions``, whose titles are also in ``alt_titles``). Other preprint records
    (DataCite's arXiv DOIs, dblp CoRR entries, posted content) carry one title only.
    """
    if not is_preprint(record):
        return True
    if record.source == "arxiv":
        version = record.identifiers.get("arxiv_version", "v1")
        return version == "v1" or bool(record.versions or record.alt_titles)
    return False


def _relation(m: Match) -> str:
    """How a record reached through an identifier relates to the entry."""
    agree = m.authors.status in {"match", "variant"}
    if m.title.status in {"match", "variant"}:
        return "same"  # author problems become field findings (REF010/REF011)
    if m.title.status == "unknown":
        return "same" if agree else "unclear"
    if agree:  # same identifier and authors, different title
        if PLACEHOLDER_TITLE.search(m.record.title):
            return "corrupted"  # "Front Matter" and the like: the record itself is wrong
        if not versions_known(m.record):
            return "unclear"  # the entry may cite an earlier version with another title
        # Usually the entry's title is wrong (HALLMARK's "chimeric titles": a real DOI and real
        # authors under an invented title). The finding names the recorded title (REF012).
        return "retitled"
    if not versions_known(m.record) and not m.authors.disjoint and m.authors.overlap >= 0.5:
        # an earlier version may have had another title and author order as well (AstroCLIP's
        # v1 had Lanusse first; DataCite and an unanswered version request show only the latest)
        return "unclear"
    if m.authors.status == "unknown" and (m.title.score or 0.0) >= 0.6:
        return "unclear"  # no authors to tell, and the titles are not far apart
    return "conflict"


def _rank(m: Match) -> tuple[int, int, float, float, int]:
    mismatches = sum(c.status == "mismatch" for c in (m.title, m.authors, m.year, m.venue))
    return (
        mismatches,
        int(is_preprint(m.record)),
        -(m.title.score or 0.0),
        -m.authors.overlap,
        SOURCE_PRIORITY.get(m.record.source, 9),
    )


def _work_key(title: str) -> str:
    """One work's titles in its records: a preprint's "Quantity-Quality Tradeoff" and its
    proceedings' "Trade-off" (SoftMatch, dblp) differ only in hyphens and spaces."""
    return title_key(title).replace(" ", "")


def _bind_candidate(
    info: EntryInfo,
    candidates: list[SourceRecord],
    *,
    preprint_pair: bool = False,
    current_year: int | None = None,
) -> Match | None:
    """Bind an unanchored entry to one search candidate, or to none when in doubt."""
    candidates = [r for r in candidates if not book_review(info, r)]
    if not candidates:
        return None
    evaluated = [evaluate(info, r, preprint_pair=preprint_pair) for r in candidates]
    best = best_candidate(info, candidates, preprint_pair=preprint_pair)
    if best is not None:
        same_work = title_key(best.record.title)
        pool = [m for m in evaluated if m.acceptable and title_key(m.record.title) == same_work]
        return min(pool or [best], key=_rank)
    # Same title and the very same authors, only the year differs: that is the cited work with a
    # wrong year (REF013), not a missing one. Bound only if all such records are one work. The
    # gap limit guards against reprints; a year in the future cannot be one, nor can a paper at
    # the same recognised venue (ICLR does not reprint its papers).
    future = info.year is not None and current_year is not None and info.year > current_year + 1
    strong = [
        m
        for m in evaluated
        if m.title.status == "match"
        and m.authors.status == "match"
        and m.suspicious is None
        and not wrong_paper(info.authors, info.year, m.record)
        and (
            future
            or m.venue.status == "match"
            or _year_gap(info.year, m.record) <= MAX_YEAR_ONLY_GAP
        )
        and not (
            m.year.status == "mismatch"
            and (other_publication(info, m) or other_kind(info, m.record))
        )
    ]
    if len({_work_key(m.record.title) for m in strong}) == 1:
        return min(strong, key=lambda m: (_year_gap(info.year, m.record), _rank(m)))
    # The same people at the same recognised venue in the same year, with a title one or two
    # words off ("Inference" for "Reasoning"): the cited work with a reworded title (REF012
    # names the words). The venue guards against a sibling paper the search did not find.
    reworded = [
        m
        for m in evaluated
        if m.authors.status == "match"
        and m.year.status == "match"
        and m.venue.status == "match"
        and m.suspicious is None
        and (m.title.score or 0.0) >= MIN_REWORDED_SCORE
        and 0 < _changed_words(m.title.changed) <= MAX_REWORDED_WORDS
    ]
    if len({_work_key(m.record.title) for m in reworded}) == 1:
        return min(reworded, key=_rank)
    # Same long title, same year, one work, but other authors: that is the cited work with wrong
    # authors (REF010/REF011: HALLMARK's placeholder and swapped authors), not a missing one.
    # A title of eight words or more names one work even a few years off: "To Trust Or Not To
    # Trust A Classifier" (NeurIPS 2018, Jiang, Kim, Guan, Gupta) cited as ICLR 2021 by five
    # other people (Badalova & Mayr) is that paper with wrong authors, venue and year.
    # Needs two named people in the entry, so that "OpenAI" or "et al." never reads as a swap.
    # A shorter title ("Explanations for Monotonic Classifiers") names one work only together
    # with the same recognised venue in the same year.
    named = sum(1 for person in info.authors.people if not person.literal)
    words = word_count(info.title)
    if words < MIN_VENUE_TITLE_WORDS or named < 2:
        return None
    same_title = [
        m
        for m in evaluated
        if m.title.status == "match"
        and m.authors.status == "mismatch"
        and (
            m.year.status in {"match", "variant"}
            or (
                words >= MIN_TITLE_ANY_YEAR_WORDS
                and not m.title.changed  # word for word: not "... Opacities. VI" for "... II"
                and _year_gap(info.year, m.record) <= MAX_YEAR_ONLY_GAP
            )
        )
        and m.suspicious is None
        and (words >= MIN_TITLE_ONLY_WORDS or m.venue.status == "match")
    ]
    if len({_work_key(m.record.title) for m in same_title}) != 1:
        return None
    return min(same_title, key=_rank)


def _published_later(year: int | None, record: SourceRecord) -> bool:
    """The entry's year is a year or two after a preprint's: the published version's year.

    dblp lists an ICLR 2026 paper as a 2025 CoRR preprint until it adds the conference, and the
    entry citing ICLR 2026 is right. Only a preprint record, only a later year, and only while no
    published record of the work is known (the caller checks that).
    """
    years = record.all_years
    return is_preprint(record) and year is not None and bool(years) and 0 < year - max(years) <= 2


def _describe_changes(changes: tuple[tuple[str, str], ...], lang: str) -> str:
    parts = []
    for mine, recorded in changes:
        if lang == "zh":
            parts.append(
                f"“{mine}”应为“{recorded}”"
                if mine and recorded
                else f"多出“{mine}”"
                if mine
                else f"缺少“{recorded}”"
            )
        else:
            parts.append(
                f'"{mine}" where the record has "{recorded}"'
                if mine and recorded
                else f'"{mine}" is not in the record'
                if mine
                else f'"{recorded}" is missing'
            )
    return ("；" if lang == "zh" else "; ").join(parts)


def _changed_words(changes: tuple[tuple[str, str], ...]) -> int:
    return sum(max(len(mine.split()), len(recorded.split())) for mine, recorded in changes)


def other_publication(info: EntryInfo, m: Match) -> bool:
    """The record appeared somewhere else than the entry says: another publication of the title.

    The same authors publish one title twice (Asplund, Grevesse & Sauval, "The Solar Chemical
    Composition": ASP Conf. Ser. 336, 2005, and Nuclear Physics A, 2006). With the year off as
    well and two venue names that share no word, the record is that other publication, not the
    cited one with a wrong year. Recognised venues are left to the venue check (an invented
    "IJCAI 2023" for a NeurIPS 2021 paper is a wrong venue, not another paper), and so are
    preprints, which precede every publication.
    """
    if info.venue is None or info.venue_field not in NAMED_VENUE_FIELDS or not m.record.venue:
        return False
    if is_preprint(m.record) or canonical_venue(info.venue) or canonical_venue(m.record.venue):
        return False
    ours = venue_words(VENUE_SERIES.sub(" ", info.venue))
    theirs = venue_words(VENUE_SERIES.sub(" ", m.record.venue))
    return bool(ours) and bool(theirs) and not related_words(ours, theirs)


# What kind of publication a record or an entry is, across the sources' vocabularies (Crossref
# and OpenAlex types, CSL, dblp, DataCite's resourceTypeGeneral) and BibTeX's entry types.
_RECORD_KINDS = {
    "journal-article": "article", "article": "article", "article-journal": "article",
    "proceedings-article": "paper", "inproceedings": "paper", "paper-conference": "paper",
    "book-chapter": "chapter", "incollection": "chapter", "chapter": "chapter",
    "dissertation": "thesis", "thesis": "thesis", "phdthesis": "thesis",
    "posted-content": "preprint", "preprint": "preprint", "informal": "preprint",
    "report": "report", "software": "software", "dataset": "software", "component": "software",
}  # fmt: skip
_ENTRY_KINDS = {
    "phdthesis": "thesis", "mastersthesis": "thesis", "thesis": "thesis",
    "incollection": "chapter", "inbook": "chapter",
    "online": "software", "software": "software", "electronic": "software", "www": "software",
    "article": "article", "inproceedings": "paper", "conference": "paper",
    "book": "book", "mvbook": "book",
}  # fmt: skip
# Record kinds an entry of each kind cannot be, whatever the title
_NOT_THE_SAME = {
    "thesis": {"article", "paper", "chapter", "preprint", "report", "software"},
    "chapter": {"article", "paper", "preprint"},
    "software": {"article", "paper", "chapter", "thesis"},
    "article": {"report", "thesis"},
    "paper": {"report", "thesis"},
    # a book is not one chapter of a later collection that reprints it (Baxter's "Exactly
    # Solved Models in Statistical Mechanics", 1982, and a 1985 World Scientific chapter)
    "book": {"chapter"},
}


def other_kind(info: EntryInfo, record: SourceRecord) -> bool:
    """The record is another kind of publication than the entry: a thesis abstract in a journal
    for a thesis (Martel 1996, PASP 1997), a conference paper for a book chapter of the same title
    (Hecht-Nielsen, IJCNN 1989 and Neural Networks for Perception 1992), a paper for the
    repository that implements it, a technical report for a NIPS paper.
    """
    entry_kind = _ENTRY_KINDS.get(info.entry_type)
    record_kind = _RECORD_KINDS.get((record.work_type or "").lower())
    return record_kind in _NOT_THE_SAME.get(entry_kind or "", set())


_PAGE_SPAN = re.compile(r"^\D*(\d+)\D*(?:[-‐-―]+\D*(\d+))?\D*$")
MAX_REVIEW_PAGES = 4


def book_review(info: EntryInfo, record: SourceRecord) -> bool:
    """A journal article of a few pages for a cited book: a review of the book, which journals
    title with the book's title (Deng on Rubinstein & Kroese's "The Cross-Entropy Method",
    Technometrics 2006, pp. 147-148; Law on Hampel et al.'s "Robust Statistics", 1986, p. 565).
    """
    if info.entry_type not in {"book", "mvbook"} or record.work_type != "journal-article":
        return False
    span = _PAGE_SPAN.match(record.pages or "")
    if span is None:
        return False
    first, last = int(span[1]), int(span[2] or span[1])
    return 0 <= last - first < MAX_REVIEW_PAGES


def _year_gap(year: int | None, record: SourceRecord) -> int:
    years = record.all_years
    if year is None or not years:
        return 0
    return min(abs(year - y) for y in years)


# ---------------------------------------------------------------- findings


def _field_findings(
    entry: BibEntry,
    info: EntryInfo,
    m: Match,
    *,
    published_known: bool = True,
    coordinates: bool = False,
) -> list[Finding]:
    """Findings on the fields of a bound entry.

    ``published_known``: a published (non-preprint) record of the bound work is known; without
    one, a preprint record cannot correct the year of a published version.
    """
    key, record = entry.key, m.record
    source = source_name(record.source)
    out: list[Finding] = []
    score = f"{m.title.score or 0.0:.2f}"
    if m.title.status == "mismatch":
        few = 0 < _changed_words(m.title.changed) <= MAX_REWORDED_WORDS
        out.append(
            make_finding(
                "REF012", _location(entry, "title"), key=key, field="title", source=source,
                found_title=record.title, score=score,
                difference=(
                    _describe_changes(m.title.changed, "en") if few else f"similarity {score}"
                ),
                difference_zh=(
                    _describe_changes(m.title.changed, "zh") if few else f"相似度 {score}"
                ),
                suggestion=protect_title(record.title),
            )
        )  # fmt: skip
    elif m.title.changed and versions_known(record):
        # Close but reworded ("towards" for "for", "Hidden" for "Latent"): HALLMARK's near-miss
        # titles. Only when every title the work has had is known: a preprint's earlier version
        # may carry the entry's wording.
        out.append(
            make_finding(
                "REF012", _location(entry, "title"), key=key, field="title", source=source,
                found_title=record.title, score=score,
                difference=_describe_changes(m.title.changed, "en"),
                difference_zh=_describe_changes(m.title.changed, "zh"),
                suggestion=protect_title(record.title),
            )
        )  # fmt: skip
    authors = m.authors
    author_field = "author" if "author" in entry.fields else "editor"
    if record.source in AUTHORS_NOT_CHECKED_AGAINST:
        pass  # see AUTHORS_NOT_CHECKED_AGAINST
    elif authors.status == "mismatch" and authors.disjoint:
        out.append(
            make_finding(
                "REF010", _location(entry, author_field), key=key, field=author_field,
                source=source, found_authors=_authors_text(record),
                suggestion=format_authors(record),
            )
        )  # fmt: skip
    elif (
        authors.status in {"mismatch", "variant"}
        and (authors.missing or not authors.first_author_match)
    ) or authors.renamed:
        names = list(authors.missing)
        details: list[tuple[str, str]] = []
        if names:
            en, zh = ", ".join(names), "、".join(names)
            details.append((f"not on the record: {en}", f"记录中没有：{zh}"))
        if not authors.first_author_match and record.authors:
            first = record.authors[0].display
            details.append((f"the first author is {first}", f"第一作者应为 {first}"))
        if authors.renamed:
            # the surname is right, the person is not (HALLMARK's "Aviral" for Archit Sharma)
            en = ", ".join(f"{ours} (recorded: {theirs})" for ours, theirs in authors.renamed)
            zh = "、".join(f"{ours}（记录为 {theirs}）" for ours, theirs in authors.renamed)
            details.append((f"other given names: {en}", f"名字不同：{zh}"))
        # Found by journal, volume and page, with the right first author, on a record that lists
        # fewer people than the entry: Crossref's records of older articles often stop short
        # (Biometrika 85(2) 379 without Vohra, MNRAS 441, 2986 without Wadsley), and no other
        # source was asked. Worth a look, not a warning.
        short_record = (
            coordinates
            and authors.first_author_match
            and not authors.renamed
            and len(record.authors) < len(info.authors.people)
        )
        out.append(
            make_finding(
                "REF011", _location(entry, author_field), key=key, field=author_field,
                severity=Severity.INFO if short_record else None,
                source=source, missing=names, suggestion=format_authors(record),
                detail="; ".join(d[0] for d in details), detail_zh="；".join(d[1] for d in details),
            )
        )  # fmt: skip
    elif authors.status == "variant" and authors.note == "some authors omitted":
        listed, total = len(info.authors.people), len(record.authors)
        out.append(
            make_finding(
                "REF011", _location(entry, author_field), key=key, field=author_field,
                severity=Severity.INFO, source=source, suggestion=format_authors(record),
                detail=f"the entry lists {listed} of {total} authors without 'and others'",
                detail_zh=f"条目只列出了 {total} 位作者中的 {listed} 位，且没有写 'and others'",
            )
        )  # fmt: skip
    if m.year.status == "mismatch" and (published_known or not _published_later(info.year, record)):
        years = ", ".join(str(y) for y in sorted(record.all_years))
        out.append(
            make_finding(
                "REF013", _location(entry, "year"), key=key, field="year", source=source,
                year=info.year, found_years=years, suggestion=str(record.year or ""),
            )
        )  # fmt: skip
    if m.venue.status == "mismatch" and not is_preprint(record):
        venue_field = next((f for f in VENUE_FIELDS if f in entry.fields), None)
        out.append(
            make_finding(
                "REF014", _location(entry, venue_field), key=key, field=venue_field,
                source=source, venue=info.venue, found_venue=record.venue,
                suggestion=escape(record.venue or ""),
            )
        )  # fmt: skip
    return out


_STATUS_FINDINGS: dict[str, tuple[str, str, str, Severity | None]] = {
    # status -> (rule, notice, notice_zh, severity override)
    "retracted": ("REF004", "retracted", "撤稿", None),
    "partial_retraction": ("REF004", "partially retracted", "部分撤稿", Severity.WARNING),
    "withdrawn": ("REF004", "withdrawn by the publisher", "被出版方撤回", None),
    "expression_of_concern": ("REF005", "an expression of concern", "关注声明", None),
    "correction": ("REF005", "a published correction", "已发布的更正", Severity.INFO),
}
_FLAG_NAMES = {"partial_retraction": "retracted", "correction": "corrected"}


def _status_findings(
    entry: BibEntry, same: list[SourceRecord], status_records: list[SourceRecord]
) -> tuple[list[Finding], set[str]]:
    dois = {r.doi.lower() for r in same if r.doi}
    records = same + [r for r in status_records if r.doi and r.doi.lower() in dois]
    reporters: dict[str, set[str]] = {}
    arxiv_withdrawn: list[str] = []
    for record in records:
        for status in record.status:
            if status == "withdrawn" and record.source == "arxiv":
                arxiv_withdrawn.append(record.identifiers.get("arxiv", record.source_id))
                continue
            reporters.setdefault(status, set()).add(source_name(record.source))
    findings: list[Finding] = []
    flags: set[str] = set()
    for status, sources in sorted(reporters.items()):
        if status not in _STATUS_FINDINGS:
            continue
        rule, notice, notice_zh, severity = _STATUS_FINDINGS[status]
        flags.add(_FLAG_NAMES.get(status, status))
        findings.append(
            make_finding(
                rule, _location(entry), key=entry.key, severity=severity,
                notice=notice, notice_zh=notice_zh, sources=", ".join(sorted(sources)),
                sources_zh="、".join(sorted(sources)),
            )
        )  # fmt: skip
    for arxiv_id in dict.fromkeys(arxiv_withdrawn):
        flags.add("withdrawn")
        findings.append(
            make_finding(
                "REF018",
                _location(entry, "eprint"),
                key=entry.key,
                identifier=arxiv_id,
            )
        )
    return findings, flags


# Venue names that still mean "a preprint": servers, and drafts not yet published.
_PREPRINT_VENUE = re.compile(
    r"arxiv|\bcorr\b|preprint|biorxiv|medrxiv|chemrxiv|ssrn|techrxiv|research square|"
    r"submitted|under review|in press|to appear",
    re.I,
)


def cites_preprint(evidence: Evidence) -> bool:
    """The entry cites an arXiv preprint, not a published version that keeps its eprint.

    An entry that names where the work appeared (booktitle or journal: "2017 IEEE Symposium on
    Security and Privacy (SP)") cites that version, recognised venue or not.
    """
    ids = evidence.identifiers
    info = evidence.info
    names_venue = (
        info.venue is not None
        and info.venue_field in NAMED_VENUE_FIELDS
        and not _PREPRINT_VENUE.search(info.venue)
        and canonical_venue(info.venue) != "arxiv"
    )
    return (
        any(i.scheme == "arxiv" for i in ids)
        and not any(i.scheme == "doi" and not i.value.startswith("10.48550/") for i in ids)
        and not names_venue
    )


def _version_distance(preprint: SourceRecord, version: SourceRecord) -> tuple[int, int, int]:
    """How unlike a published version of a preprint ``version`` is: other people first, then an
    earlier year. dblp finds every paper of the first author with the title: arXiv 1408.6027, Xin
    Geng's "Label Distribution Learning" (2014), is his TKDE 2016 article, not the ICDM Workshops
    2013 paper of that title by Geng and Ji.
    """
    people = {surname_key(p) for p in preprint.authors}
    others = {surname_key(p) for p in version.authors} != people
    year, published = preprint.year or 0, version.year or 0
    return int(others), int(published < year), abs(published - year)


def _published_version(
    entry: BibEntry, evidence: Evidence, bound: SourceRecord | None
) -> Finding | None:
    """REF015 when the entry cites a preprint whose published version is known."""
    if not cites_preprint(evidence):
        return None
    versions = list(evidence.published_versions)
    if bound is not None and not is_preprint(bound):
        versions.append(bound)  # the title search found the published version itself
    elif bound is not None:
        versions.sort(key=lambda version: _version_distance(bound, version))
    for version in versions:
        m = evaluate(evidence.info, version, preprint_pair=True)
        if m.title.status == "mismatch" or m.authors.status in {"mismatch", "unknown"}:
            continue
        doi = version.doi
        return make_finding(
            "REF015", _location(entry, "eprint"), key=entry.key, field="eprint",
            found_venue=version.venue or "a venue", found_year=version.year or "n.d.",
            published_id=version.source_id, doi=doi or "",
            doi_note=f", DOI {doi}" if doi else "", doi_note_zh=f"，DOI {doi}" if doi else "",
        )  # fmt: skip
    return None


def _cited_version(info: EntryInfo, evidence: Evidence, preprint: Match) -> Match:
    """The version to compare an entry with that names its venue but reached the preprint.

    Both are the work, and authors write either: an ICML 2018 entry whose URL is arXiv 1804.03329
    lists Frederic Sala first, as ICML does, while arXiv lists Christopher De Sa first; an ICLR
    2025 entry names "Jade Yu" as arXiv does, while ICLR has "Lei Yu". The published version at
    the venue and in the year the entry names counts as well, and the one that fits the entry
    best is compared.
    """
    versions = [
        m
        for m in (evaluate(info, r) for r in evidence.published_versions)
        if m.title.status in {"match", "variant"}
        and m.authors.status != "mismatch"
        and m.venue.status == "match"  # the version at the venue and in the year the entry names
        and m.year.status == "match"
    ]

    def fit(m: Match) -> tuple[int, int, int]:
        # the preprint's venue is arXiv by nature: only title, authors and year count
        mismatches = sum(c.status == "mismatch" for c in (m.title, m.authors, m.year))
        return mismatches, len(m.authors.renamed), int(is_preprint(m.record))

    return min([preprint, *versions], key=fit)


def _addable_doi(entry: BibEntry, evidence: Evidence, record: SourceRecord) -> Finding | None:
    """REF016 when the entry has no DOI and the record it is bound to has one.

    Not for preprint citations (REF015 covers the published version) and never for arXiv's
    DataCite DOIs, which add nothing to an eprint field.
    """
    doi = record.doi
    if not doi or doi.startswith("10.48550/") or cites_preprint(evidence):
        return None
    if any(i.scheme == "doi" for i in evidence.identifiers):
        return None
    return make_finding(
        "REF016", _location(entry), key=entry.key, field="doi",
        source=source_name(record.source), doi=doi, suggestion=doi,
    )  # fmt: skip


def _dead_identifiers(entry: BibEntry, evidence: Evidence) -> tuple[list[Finding], set[str]]:
    findings: list[Finding] = []
    dead: set[str] = set()
    for ident in evidence.identifiers:
        if ident.scheme == "doi":
            answer = evidence.doi_agency.get(ident.value)
            if answer is None or answer.exists:
                continue
            authority = "doi.org"
        elif ident.scheme == "arxiv" and ident.value in evidence.arxiv_missing:
            authority = "arXiv"
        elif ident.scheme == "pmid" and ident.value in evidence.pmid_missing:
            authority = "PubMed"
        elif ident.scheme == "pmcid" and ident.value in evidence.pmcid_missing:
            authority = "PubMed Central"
        else:
            continue
        dead.add(ident.value)
        findings.append(
            make_finding(
                "REF002", _location(entry, ident.field), key=entry.key, field=ident.field,
                identifier=ident.value, authority=authority,
            )
        )  # fmt: skip
    return findings, dead


# ---------------------------------------------------------------- the verdict


_BOOK_TYPES = frozenset({"book", "edited-book", "monograph", "reference-book", "book-set"})


def _container(info: EntryInfo, record: SourceRecord) -> bool:
    """The record is the book the cited chapter is in, not another work: Thompson, Zanna &
    Griffin (1995) is cited with 10.4324/9781315807041, Routledge's edition of the volume
    "Attitude Strength" that the entry's booktitle names."""
    if record.work_type not in _BOOK_TYPES or info.venue_field != "booktitle" or not info.venue:
        return False
    return title_score(info.venue, record.title) >= TITLE_VARIANT or subtitle_variant(
        info.venue, record.title
    )


def assess(entry: BibEntry, evidence: Evidence, *, current_year: int) -> Assessment:
    info = evidence.info
    findings, dead = _dead_identifiers(entry, evidence)
    preprint = cites_preprint(evidence)  # a published version may then be a year or two later

    # 1. Records reached through the entry's own identifiers.
    same: list[Match] = []
    conflicts: list[tuple[Match, Identifier | None]] = []
    corrupted = False
    anchored = [r for r in evidence.anchored if not _container(info, r)]
    for record in anchored:
        m = evaluate(info, record, preprint_pair=preprint)
        relation = _relation(m)
        if relation in {"same", "retitled"}:
            same.append(m)
        elif relation == "conflict":
            conflicts.append((m, _anchor(record, evidence.identifiers)))
        elif relation == "corrupted":
            corrupted = True
    confirmed_ids = {a.value for m in same if (a := _anchor(m.record, evidence.identifiers))}
    for m, ident in conflicts:
        if ident is not None and ident.value in confirmed_ids:
            continue  # another source confirms this identifier: one bad record is not a conflict
        record = m.record
        findings.append(
            make_finding(
                "REF001", _location(entry, ident.field if ident else None), key=entry.key,
                field=ident.field if ident else None,
                identifier=ident.value if ident else "identifier",
                source=source_name(record.source), found_title=record.title,
                found_authors=_authors_text(record), found_year=record.year or "n.d.",
                remove=True,
            )
        )  # fmt: skip
    has_conflict = any(f.rule_id == "REF001" for f in findings)

    # 2. Bind: the best record reached by identifier, else one unambiguous search candidate.
    bound = min(same, key=_rank) if same else None
    if bound is None and not anchored:
        bound = _bind_candidate(
            info, evidence.candidates, preprint_pair=preprint, current_year=current_year
        )

    if bound is not None and not preprint and is_preprint(bound.record):
        bound = _cited_version(info, evidence, bound)

    flags: set[str] = set()
    reasons: list[Reason] = []
    if bound is not None:
        same_work = title_key(bound.record.title)
        published_known = any(
            not is_preprint(r) and title_key(r.title) == same_work
            for r in (*evidence.anchored, *evidence.candidates, *evidence.published_versions)
        )
        findings.extend(
            _field_findings(
                entry, info, bound, published_known=published_known,
                coordinates=evidence.by_coordinates,
            )
        )  # fmt: skip
        same_records = [m.record for m in same] or [bound.record]
        status_findings, flags = _status_findings(entry, same_records, evidence.status_records)
        findings.extend(status_findings)
        if evidence.by_coordinates:
            flags.add("coordinates")  # found by journal, volume and page: there is no title
        published = _published_version(entry, evidence, bound.record)
        if published is not None:
            findings.append(published)
            flags.add("preprint_published")
        addable = _addable_doi(entry, evidence, bound.record)
        if addable is not None:
            findings.append(addable)
        field_problem = any(
            f.rule_id in {"REF010", "REF011", "REF012", "REF013", "REF014"}
            and f.severity is not Severity.INFO
            for f in findings
        )
        confirmed = sum(
            c.status in {"match", "variant"} for c in (bound.title, bound.authors, bound.year)
        )
        if has_conflict:
            verdict = Verdict.IDENTIFIER_CONFLICT
        elif field_problem or dead:
            verdict = Verdict.METADATA_MISMATCH
        elif confirmed >= 2:
            verdict = Verdict.VERIFIED
        else:
            verdict = Verdict.CANNOT_DETERMINE
            reasons.append(Reason.INSUFFICIENT_METADATA)
    elif has_conflict:
        verdict = Verdict.IDENTIFIER_CONFLICT
    else:
        reasons = _abstention_reasons(evidence, dead, corrupted, current_year)
        if not reasons:
            verdict = Verdict.NOT_FOUND
            sources = [source_name(s) for s in sorted(_answered_no(evidence))]
            findings.append(
                make_finding(
                    "REF003", _location(entry, "title"), key=entry.key,
                    sources=_listing(sources, ", ", " and "),
                    sources_zh=_listing(sources, "、", " 和 "),
                    searched=sorted(evidence.negative),
                )
            )  # fmt: skip
        else:
            verdict = Verdict.CANNOT_DETERMINE

    if verdict is Verdict.CANNOT_DETERMINE:
        findings.append(
            make_finding(
                "REF090", _location(entry), key=entry.key, reasons=[r.value for r in reasons],
                reasons_text="; ".join(REASON_TEXT[r][0] for r in reasons),
                reasons_text_zh="；".join(REASON_TEXT[r][1] for r in reasons),
            )
        )  # fmt: skip

    kept = tuple(f for f in findings if entry.suppressed(f.rule_id) is None)
    return Assessment(
        key=entry.key,
        verdict=verdict,
        reasons=tuple(reasons),
        flags=frozenset(flags),
        record=bound.record if bound else None,
        findings=kept,
        suppressed=frozenset(f.rule_id for f in findings if entry.suppressed(f.rule_id)),
    )


def _other_works(evidence: Evidence) -> list[SourceRecord]:
    """Search results that cannot be the cited work: no author in common and another title.

    Similar titles by other people ("Multiview Diffusion Models for High-Resolution Image
    Synthesis" for an invented "Diffusion Models for ...") do not make an entry ambiguous. The
    same title by other people does (wrong authors?), and so does any Semantic Scholar result,
    whose author lists are not trusted (AUTHORS_NOT_CHECKED_AGAINST).
    """
    info = evidence.info
    if not any(not person.literal for person in info.authors.people):
        return []
    others = []
    for record in evidence.candidates:
        if record.source in AUTHORS_NOT_CHECKED_AGAINST:
            continue
        m = evaluate(info, record)
        if m.authors.disjoint and m.title.status != "match":
            others.append(record)
    return others


def _answered_no(evidence: Evidence) -> set[str]:
    """Sources that answered "no such work": nothing similar, or only other works."""
    others = _other_works(evidence)
    if len(others) < len(evidence.candidates):
        return set(evidence.negative)
    return evidence.negative | {record.source for record in others}


ANONYMOUS = re.compile(r"anon(?:ymous|\.)?(?:\s+authors?)?", re.IGNORECASE)
_UNDER_REVIEW = re.compile(r"openreview|under review|submitted|submission", re.IGNORECASE)
UNINDEXED_CHAPTER_YEAR = 2000  # book chapters before this are seldom in the indexes


def _under_review(info: EntryInfo) -> bool:
    """An anonymous submission under review: "Anonymous Authors", booktitle "OpenReview". An
    anonymous paper at a venue that has published (NeurIPS 2021, arXiv) is no such thing."""
    people = info.authors.people
    if not people or not all(ANONYMOUS.fullmatch(person.display) for person in people):
        return False
    return bool(_UNDER_REVIEW.search(info.venue or "")) or "openreview.net" in info.link_hosts


# Publications that appear only on their own sites, cited like journals ("journal =
# {Transformer Circuits Thread}"); no queried source indexes them
_WEB_VENUES = re.compile(
    r"\btransformer circuits\b|\blesswrong\b|\balignment forum\b|^the gradient$|\bsubstack\b",
    re.IGNORECASE,
)


_REPORT_VENUE = re.compile(
    r"\btech(?:nical|\.)?\s*rep(?:ort|\.)?(?!\w)|\b(?:phd|master'?s)\s+thesis\b|\bdissertation\b",
    re.IGNORECASE,
)


def _unindexed_venue(info: EntryInfo) -> bool:
    if info.venue and re.search(r"\bworkshop\b", info.venue, re.IGNORECASE):
        return True
    if info.venue and _WEB_VENUES.search(info.venue.strip()):
        return True
    chapter = info.entry_type in {"incollection", "inbook"}
    return chapter and info.year is not None and info.year < UNINDEXED_CHAPTER_YEAR


def _abstention_reasons(
    evidence: Evidence, dead: set[str], corrupted: bool, current_year: int
) -> list[Reason]:
    """Why an entry nobody found cannot be called "not found" (docs/plan 5.7). Empty = it can."""
    info = evidence.info
    reasons: list[Reason] = []
    unavailable = set(evidence.unavailable.values())
    if unavailable:
        if unavailable == {"offline"}:
            reasons.append(Reason.OFFLINE_MODE)
        elif unavailable == {"budget_exhausted"}:
            reasons.append(Reason.BUDGET_EXHAUSTED)
        else:
            reasons.append(Reason.SOURCES_UNAVAILABLE)
    if corrupted:
        reasons.append(Reason.CORRUPTED_SOURCE_RECORD)
    if non_latin(info.title):
        reasons.append(Reason.NON_LATIN_UNSUPPORTED)
    live_ids = [
        i
        for i in evidence.identifiers
        if i.scheme in {"doi", "arxiv", "pmid", "pmcid"} and i.value not in dead
    ]
    # a report or thesis under another entry type: Zhu's "Semi-supervised learning literature
    # survey" as @inproceedings with booktitle "Technical Report, University of Wisconsin-Madison".
    # It must name who issued it: a bare "Technical Report" (Parr 1998, which does not exist)
    # says nothing a reader could look up.
    venue = info.venue or ""
    report = bool(_REPORT_VENUE.search(venue)) and bool(
        re.search(r"[^\W\d_]{3,}", _REPORT_VENUE.sub(" ", venue))
    )
    if (info.entry_type in GREY_TYPES or report) and not live_ids:
        reasons.append(Reason.GREY_LITERATURE)
    # a paper in a society's own proceedings, linked there (Proceedings of the Samahang Pisika ng
    # Pilipinas, proceedings.spp-online.org): no source knowing it says nothing about it
    elif not live_ids and unindexed_hosts(info.link_hosts):
        reasons.append(Reason.UNINDEXED_LINK)
    # works from before the indexes' digital coverage: real papers of the 1950s and 60s in
    # mechanics and physics (Barenblatt 1952, Bluman & Cole 1969) are known to none of them
    if not live_ids and info.year is not None and info.year < OLD_WORK_YEAR:
        reasons.append(Reason.OLD_WORK)
    # venues the indexes often leave out: an ICLR 2025 workshop paper on OpenReview, a chapter
    # in a 1996 Dekker volume of Lecture Notes in Pure and Applied Mathematics
    elif not live_ids and _unindexed_venue(info):
        reasons.append(Reason.UNINDEXED_VENUE)
    if not live_ids and _under_review(info):
        reasons.append(Reason.ANONYMOUS)
    # this year's and next year's papers may not be indexed yet; a later year is just wrong
    if not live_ids and info.year is not None and current_year <= info.year <= current_year + 1:
        reasons.append(Reason.TOO_NEW)
    if any(i.scheme == "doi" and i.value in evidence.doi_agency for i in live_ids):
        reasons.append(Reason.IDENTIFIER_EXISTS_NO_METADATA)
    if len(_other_works(evidence)) < len(evidence.candidates):
        reasons.append(Reason.AMBIGUOUS_CANDIDATES)
    if reasons:
        return reasons
    required = {"crossref"} | ({"dblp"} if looks_cs(info) else set())
    answered_no = bool(evidence.searched) and evidence.searched | required <= _answered_no(evidence)
    if not answered_no or (
        word_count(info.title) < MIN_NOT_FOUND_WORDS and not _venue_vouches(evidence, current_year)
    ):
        return [Reason.INSUFFICIENT_METADATA]
    return []


def _venue_vouches(evidence: Evidence, current_year: int) -> bool:
    """A short title can be called "not found" at a venue dblp indexes in full, in a past year:
    "Spectral Contrastive Graph Clustering" at ICLR 2022 is a title, not a topic, there. Not
    when a found title is the entry's and more (a real paper cited by its first words), and
    never below three words, which Crossref is not even asked about."""
    info = evidence.info
    venue = canonical_venue(info.venue)
    return (
        venue is not None
        and venue != "arxiv"
        and info.year is not None
        and info.year < current_year
        and word_count(info.title) >= 3
        and not evidence.extended
    )


def assess_all(
    entries: Iterable[BibEntry], evidence: dict[str, Evidence], *, current_year: int
) -> dict[str, Assessment]:
    """Assess the first definition of every key that has evidence."""
    result: dict[str, Assessment] = {}
    for entry in entries:
        if entry.key in result or entry.key not in evidence:
            continue
        result[entry.key] = assess(entry, evidence[entry.key], current_year=current_year)
    return result


def run_findings(evidence: dict[str, Evidence]) -> list[Finding]:
    """RUN001 when a source was unavailable for a reference and nothing answered in its place:
    the run cannot claim a pass. RUN002 (info) when another source answered instead (arXiv's
    questions through DataCite): the reference is checked, but not what only that source knows.

    Offline mode is the user's choice, not a failing source, so it does not count here.
    """
    by_source: dict[str, set[str]] = {}
    affected = 0
    substituted: dict[str, set[str]] = {}  # unavailable source -> sources used instead
    replaced = 0
    for item in evidence.values():
        failures = {s: r for s, r in item.unavailable.items() if r != "offline"}
        stood_in = {s: item.substituted[s] for s in failures if s in item.substituted}
        failures = {s: r for s, r in failures.items() if s not in stood_in}
        affected += bool(failures)
        replaced += bool(stood_in)
        for source, reason in failures.items():
            by_source.setdefault(source, set()).add(reason)
        for source, substitute in stood_in.items():
            substituted.setdefault(source, set()).add(substitute)
    findings = []
    if affected:
        described = [
            f"{source_name(s)} ({', '.join(sorted(r))})" for s, r in sorted(by_source.items())
        ]
        findings.append(
            make_finding(
                "RUN001", None, count=affected, sources="; ".join(described),
                unavailable=sorted(by_source),
            )
        )  # fmt: skip
    if replaced:
        findings.append(
            make_finding(
                "RUN002", None, count=replaced,
                sources=", ".join(source_name(s) for s in sorted(substituted)),
                substitutes=", ".join(
                    sorted({source_name(x) for xs in substituted.values() for x in xs})
                ),
                substituted=sorted(substituted),
            )
        )  # fmt: skip
    return findings
