"""Compare a BibTeX entry with a source record, field by field (docs/adr/0003, section 5).

Every comparison returns a :class:`FieldCheck` with one of four statuses — ``match``, ``variant``
(a benign difference such as an omitted subtitle or a preprint/print year), ``mismatch`` and
``unknown``. Thresholds follow the consensus of existing tools (hallucinator, bibtexupdater,
refchecker) recorded in reports/paper preflight 实现参考与灵感.md; no candidate is accepted on a
title alone, and a source's relevance score is never used.
"""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from functools import cache
from importlib import resources
from typing import Literal

from rapidfuzz import fuzz
from rapidfuzz.distance import Levenshtein

from paper_preflight.bib.names import AuthorList, parse_authors
from paper_preflight.bib.normalize import fold, title_key, word_count
from paper_preflight.bib.parse import BibEntry
from paper_preflight.sources.record import Person, SourceRecord

Status = Literal["match", "variant", "mismatch", "unknown"]

TITLE_SAME = 0.95
TITLE_VARIANT = 0.90
TITLE_ACCEPT = 0.92  # minimum title similarity to accept an unanchored search candidate
MIN_PREFIX_CHARS = 30  # a title may omit its subtitle only if the remaining prefix is this long


@dataclass(frozen=True)
class FieldCheck:
    status: Status
    score: float | None = None
    note: str = ""
    # titles: the words that differ from the closest recorded title, (entry's, record's) per place
    changed: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class EntryInfo:
    """The parts of a BibTeX entry that matching needs, extracted once."""

    key: str
    title: str
    authors: AuthorList
    year: int | None
    venue: str | None
    entry_type: str

    @classmethod
    def from_entry(cls, entry: BibEntry) -> EntryInfo:
        author_field = entry.fields.get("author") or entry.fields.get("editor")
        year_text = entry.text("year") or (entry.text("date") or "")[:4]
        match = re.search(r"\d{4}", year_text or "")
        venue = (
            entry.text("booktitle")
            or entry.text("journal")
            or entry.text("journaltitle")
            or entry.text("howpublished")
            or entry.text("publisher")
        )
        return cls(
            key=entry.key,
            title=entry.text("title") or "",
            authors=parse_authors(author_field.value if author_field else None),
            year=int(match.group(0)) if match else None,
            venue=venue,
            entry_type=entry.entry_type,
        )


# ---------------------------------------------------------------- titles


def title_score(a: str, b: str) -> float:
    ka, kb = title_key(a), title_key(b)
    if not ka or not kb:
        return 0.0
    if ka == kb:
        return 1.0
    return float(fuzz.ratio(ka, kb)) / 100.0


def _subtitle_variant(a: str, b: str) -> bool:
    """One title is the other without its subtitle (``Title: Subtitle``)."""
    ka, kb = title_key(a), title_key(b)
    short, long_ = sorted((ka, kb), key=len)
    return (
        len(short) >= MIN_PREFIX_CHARS
        and long_.startswith(short)
        and (":" in a or ":" in b or " - " in a or " - " in b)
    )


# British spellings and their American forms ("optimisation", "modelling", "behaviour").
_SPELLING = (
    (re.compile(r"is(e|es|ed|ing|er|ers|ation|ations)$"), r"iz\1"),
    (re.compile(r"ys(e|es|ed|ing)$"), r"yz\1"),
    (re.compile(r"(?<=\w{3})our(s|ed|ing|al|ite|able)?$"), r"or\1"),
    (re.compile(r"ll(ed|ing|er|ers)$"), r"l\1"),
    (re.compile(r"tre(s?)$"), r"ter\1"),
    (re.compile(r"ogue(s?)$"), r"og\1"),
)


def _american(word: str) -> str:
    for pattern, replacement in _SPELLING:
        word = pattern.sub(replacement, word)
    return word


# Notices registries put before a title ("RETRACTED: ..."); REF004 reports the retraction itself.
_EDITORIAL_PREFIX = re.compile(
    r"^\W*(retracted|withdrawn|retraction|expression of concern)( article)?\W*[:.]\s*", re.I
)


def changed_words(entry_title: str, record_title: str) -> tuple[tuple[str, str], ...]:
    """Where two titles differ word for word: (entry's words, record's words) per place.

    Case, punctuation, spacing and hyphenation ("Chain of-Thought", "Pre-training"), "&" for
    "and", British spellings and a registry's "RETRACTED:" are not differences.
    """
    record_title = _EDITORIAL_PREFIX.sub("", record_title)
    ours = title_key(entry_title.replace("&", " and ")).split()
    theirs = title_key(record_title.replace("&", " and ")).split()
    changes: list[tuple[str, str]] = []
    for op, i1, i2, j1, j2 in SequenceMatcher(a=ours, b=theirs, autojunk=False).get_opcodes():
        if op == "equal":
            continue
        mine, recorded = " ".join(ours[i1:i2]), " ".join(theirs[j1:j2])
        if mine.replace(" ", "") == recorded.replace(" ", "") or (
            i2 - i1 == j2 - j1
            and all(
                _american(a) == _american(b)
                for a, b in zip(ours[i1:i2], theirs[j1:j2], strict=True)
            )
        ):
            continue
        if not (mine + recorded).isascii() or (len(mine) <= 1 and len(recorded) <= 1):
            continue  # math: registries render "ε" as "ε", "epsilon" or "e", and variables vary
        changes.append((mine, recorded))
    return tuple(changes)


def check_title(entry_title: str, record: SourceRecord) -> FieldCheck:
    if not entry_title or not record.title:
        return FieldCheck("unknown")
    best = 0.0
    best_note = ""
    changed: tuple[tuple[str, str], ...] | None = None  # against the closest recorded title
    for candidate, note in [(record.title, "")] + [
        (t, "matches an earlier version's title") for t in record.alt_titles
    ]:
        score = title_score(entry_title, candidate)
        if score > best:
            best, best_note = score, note
        subtitle = _subtitle_variant(entry_title, candidate)
        if subtitle and best < TITLE_SAME:
            best, best_note = TITLE_SAME, "subtitle omitted"
        diff = () if subtitle else changed_words(entry_title, candidate)
        if changed is None or len(diff) < len(changed):
            changed = diff
    if best >= TITLE_SAME:
        return FieldCheck("variant" if best_note else "match", best, best_note, changed or ())
    if best >= TITLE_VARIANT:
        return FieldCheck("variant", best, best_note or "minor title difference", changed or ())
    return FieldCheck("mismatch", best)


# ---------------------------------------------------------------- authors


def surname_key(person: Person) -> str:
    """Comparison key: last word of the folded family name (``van der Berg`` → ``berg``)."""
    if person.literal:
        return " ".join(re.findall(r"\w+", fold(person.literal)))
    words = re.findall(r"[\w'-]+", fold(person.family))
    return words[-1].strip("'-") if words else ""


_TRANSCRIPTIONS = (("ae", "a"), ("oe", "o"), ("ue", "u"), ("ss", "s"))


def loose_surname(key: str) -> str:
    """A looser key for one surname spelled differently by different sources.

    Covers umlaut transcriptions (Müller/Mueller) and ß (Reiß/Reiss/Reis: Crossref has "Reis"
    for a HALLMARK VALID entry). General doubled letters are not collapsed, so distinct surnames
    such as Lee and Le, or Chen and Cheng, stay distinct.
    """
    for written, plain in _TRANSCRIPTIONS:
        key = key.replace(written, plain)
    return key


def _name_forms(person: Person) -> set[str]:
    """Ways sources write one surname: its last part, all parts joined, and the last given name
    joined to it (Crossref has "RichardWebster" for Brandon Richard Webster; "Sánchez-Fernández"
    and "Sánchez Fernández" are one name), all with transcriptions folded."""
    if person.literal:
        return {loose_surname(surname_key(person))}
    family = [w.strip("'") for w in re.findall(r"[\w']+", fold(person.family))]
    given = re.findall(r"\w+", fold(person.given))
    forms: set[str] = set()
    if family:
        forms |= {family[-1], "".join(family)}
        if given:
            forms.add(given[-1] + "".join(family))
    return {loose_surname(form) for form in forms if form}


def _first_given(person: Person) -> str:
    words = re.findall(r"\w+", fold(person.given))
    return words[0] if words else ""


def same_person(a: Person, b: Person) -> bool:
    """One person written differently by two sources (checked after exact surnames pair up)."""
    if surname_key(a) == surname_key(b) or _name_forms(a) & _name_forms(b):
        return True
    # A one-letter slip in one source ("Hut" for Jiahui Hu, "Rent" for Kui Ren in a Crossref
    # record), accepted only when the full given names agree.
    given = _first_given(a)
    if len(given) < 2 or given != _first_given(b):
        return False
    key_a, key_b = surname_key(a), surname_key(b)
    return min(len(key_a), len(key_b)) >= 2 and Levenshtein.distance(key_a, key_b) <= 1


@dataclass(frozen=True)
class AuthorCheck(FieldCheck):
    overlap: float = 0.0
    first_author_match: bool = False
    disjoint: bool = False
    missing: tuple[str, ...] = field(default=())  # entry authors not found in the record


def check_authors(authors: AuthorList, record: SourceRecord) -> AuthorCheck:
    entry = [(person, key) for person in authors.people if (key := surname_key(person))]
    people = [person for person in record.authors if surname_key(person)]
    record_keys = [surname_key(person) for person in people]
    if not entry or not people:
        return AuthorCheck("unknown")
    # exact surnames first, then spelling variants, so a variant never takes an exact match
    pool = list(zip(people, record_keys, strict=True))
    unmatched: list[Person] = []
    for person, key in entry:
        index = next((i for i, (_, k) in enumerate(pool) if k == key), None)
        if index is None:
            unmatched.append(person)
        else:
            pool.pop(index)
    missing: list[str] = []
    for person in unmatched:
        index = next((i for i, (other, _) in enumerate(pool) if same_person(person, other)), None)
        if index is None:
            missing.append(person.display)
        else:
            pool.pop(index)
    matched = len(entry) - len(missing)
    overlap = matched / len(entry)
    first_person = entry[0][0]
    if record.authors_ordered:
        first = same_person(first_person, people[0])
    else:
        first = any(same_person(first_person, other) for other in people)
    missing_names = tuple(missing)

    def result(status: Status, note: str = "", *, disjoint: bool = False) -> AuthorCheck:
        return AuthorCheck(
            status, overlap, note, overlap=overlap, first_author_match=first,
            disjoint=disjoint, missing=missing_names,
        )  # fmt: skip

    if matched == 0:
        return result("mismatch", "no author in common", disjoint=True)
    if overlap == 1.0 and first:
        omitted = (
            len(entry) < len(record_keys) and not authors.truncated and record.authors_complete
        )
        return result("variant", "some authors omitted") if omitted else result("match")
    if overlap >= 0.5 and first:
        return result("variant", "some authors differ")
    return result("mismatch", "author list differs")


# ---------------------------------------------------------------- year and venue


def check_year(
    year: int | None, record: SourceRecord, *, preprint_pair: bool = False
) -> FieldCheck:
    years = record.all_years
    if year is None or not years:
        return FieldCheck("unknown")
    if year in years:  # any registered year counts (online-first, print, preprint versions)
        return FieldCheck("match")
    # No general ±1 tolerance: refchecker dropped it because it silently hid real year errors.
    # Only preprint/published pairs legitimately differ by a year or two.
    distance = min(abs(year - y) for y in years)
    preprint = preprint_pair or record.work_type in {"preprint", "posted-content"}
    if preprint and distance <= 2:
        return FieldCheck("variant", None, f"recorded year(s) {sorted(years)}")
    return FieldCheck("mismatch", None, f"recorded year(s) {sorted(years)}")


_VENUES: list[tuple[str, tuple[str, ...]]] = [
    # order matters: more specific names first
    ("naacl", ("naacl", "north american chapter of the association for computational linguistics")),
    ("eacl", ("eacl", "european chapter of the association for computational linguistics")),
    ("aacl", ("aacl", "asia-pacific chapter of the association for computational linguistics")),
    ("tacl", ("tacl", "transactions of the association for computational linguistics")),
    ("emnlp", ("emnlp", "empirical methods in natural language processing")),
    ("coling", ("coling", "international conference on computational linguistics")),
    ("acl", ("acl", "association for computational linguistics")),
    ("neurips", ("neurips", "nips", "neural information processing systems")),
    ("iclr", ("iclr", "international conference on learning representations")),
    ("icml", ("icml", "international conference on machine learning")),
    ("cvpr", ("cvpr", "computer vision and pattern recognition")),
    ("iccv", ("iccv", "international conference on computer vision")),
    ("eccv", ("eccv", "european conference on computer vision")),
    ("aaai", ("aaai",)),
    ("ijcai", ("ijcai", "international joint conference on artificial intelligence")),
    ("kdd", ("kdd", "knowledge discovery and data mining")),
    ("sigir", ("sigir",)),
    ("jmlr", ("jmlr", "journal of machine learning research")),
    ("tpami", ("tpami", "pattern analysis and machine intelligence")),
    ("ijcv", ("ijcv", "international journal of computer vision")),
    ("tmlr", ("tmlr", "transactions on machine learning research")),
    ("aistats", ("aistats", "artificial intelligence and statistics")),
    ("uai", ("uai", "uncertainty in artificial intelligence")),
    ("colt", ("colt", "conference on learning theory", "computational learning theory")),
    ("corl", ("corl", "conference on robot learning")),
    ("www", ("www", "web conference", "world wide web")),
    ("wsdm", ("wsdm", "web search and data mining")),
    ("cikm", ("cikm", "information and knowledge management")),
    ("icassp", ("icassp", "acoustics speech and signal processing")),
    ("interspeech", ("interspeech",)),
    ("miccai", ("miccai", "medical image computing")),
    ("icra", ("icra", "international conference on robotics and automation")),
    ("iros", ("iros", "intelligent robots and systems")),
    ("wacv", ("wacv", "winter conference on applications of computer vision")),
    ("bmvc", ("bmvc", "british machine vision conference")),
    ("arxiv", ("arxiv", "corr")),
]
_URL = re.compile(r"(?:https?://|www\.)\S+", re.I)


def canonical_venue(text: str | None) -> str | None:
    if not text:
        return None
    folded = " ".join(re.findall(r"[\w-]+", fold(_URL.sub(" ", text))))
    for key, patterns in _VENUES:
        for pattern in patterns:
            if re.search(rf"(?<!\w){re.escape(pattern)}(?!\w)", folded):
                return key
    return None


# Words every venue name may carry; they say nothing about which venue it is.
_VENUE_FILLER = frozenset(
    "proceedings proc conference conf international intl annual journal transactions trans "
    "symposium symp workshop workshops meeting the and for ieee acm cvf advances volume vol "
    "part series lecture notes".split()
)


def venue_words(text: str | None) -> set[str]:
    words = re.findall(r"[a-z]+", fold(text or ""))
    return {w for w in words if len(w) >= 3 and w not in _VENUE_FILLER}


def _related(ours: set[str], theirs: set[str]) -> bool:
    """Some word of one name abbreviates or equals a word of the other ("recog"/"recognition")."""
    return any(a.startswith(b) or b.startswith(a) for a in ours for b in theirs)


def check_venue(venue: str | None, record: SourceRecord) -> FieldCheck:
    """A mismatch needs positive evidence: two recognised, different venues, or a venue nobody
    recognises that shares no word (or abbreviation) with the recognised recorded one.

    The second case catches invented venues ("Annual Conference on Spatial Intelligence" for a
    CVPR paper; HALLMARK's nonexistent_venue type) without flagging abbreviations such as
    "Proc. IEEE Conf. Comp. Vis. Patt. Recog." for CVPR.
    """
    mine, theirs = canonical_venue(venue), canonical_venue(record.venue)
    if mine is not None and theirs is not None:
        if mine == theirs:
            return FieldCheck("match")
        return FieldCheck("mismatch", None, f"{mine} vs {theirs}")
    if mine is None and theirs is not None:
        ours = venue_words(venue)
        known = venue_words(record.venue)
        for key, patterns in _VENUES:
            if key == theirs:
                known |= {w for pattern in patterns for w in venue_words(pattern)}
        if len(ours) >= 2 and not _related(ours, known):
            return FieldCheck("mismatch", None, f"unrecognised venue vs {theirs}")
    return FieldCheck("unknown")


# ---------------------------------------------------------------- guards


@cache
def _suspicious_sources() -> tuple[dict[str, str], ...]:
    data = (
        resources.files("paper_preflight.data")
        .joinpath("suspicious_sources.toml")
        .read_text(encoding="utf-8")
    )
    return tuple(tomllib.loads(data).get("source", []))


def suspicious_reason(record: SourceRecord, cited_year: int | None) -> str | None:
    prefix = record.identifiers.get("doi_prefix") or (record.doi or "").split("/", 1)[0]
    member = record.identifiers.get("crossref_member")
    for entry in _suspicious_sources():
        if (prefix and prefix == entry.get("doi_prefix")) or (
            member and member == entry.get("crossref_member")
        ):
            return str(entry.get("reason", "denylisted source"))
    if (
        record.work_type == "posted-content"
        and record.year is not None
        and cited_year is not None
        and record.year - cited_year >= 3
    ):
        return "posted-content record dated years after the cited work"
    return None


def wrong_paper(authors: AuthorList, year: int | None, record: SourceRecord) -> bool:
    """refchecker's guard: no surname in common and years at least 5 apart → different paper."""
    check = check_authors(authors, record)
    if not check.disjoint:
        return False
    years = record.all_years
    return year is not None and bool(years) and min(abs(year - y) for y in years) >= 5


# ---------------------------------------------------------------- whole-record evaluation


@dataclass(frozen=True)
class Match:
    record: SourceRecord
    title: FieldCheck
    authors: AuthorCheck
    year: FieldCheck
    venue: FieldCheck
    suspicious: str | None
    acceptable: bool  # good enough to bind an unanchored (title-search) candidate


def evaluate(info: EntryInfo, record: SourceRecord, *, preprint_pair: bool = False) -> Match:
    title = check_title(info.title, record)
    authors = check_authors(info.authors, record)
    year = check_year(info.year, record, preprint_pair=preprint_pair)
    venue = check_venue(info.venue, record)
    suspicious = suspicious_reason(record, info.year)
    short_title = word_count(info.title) < 5
    acceptable = (
        suspicious is None
        and (title.score or 0.0) >= TITLE_ACCEPT
        and authors.status in {"match", "variant", "unknown"}
        and (authors.status != "unknown" or not short_title)
        and (not short_title or authors.status == "match")
        and year.status != "mismatch"
        and not wrong_paper(info.authors, info.year, record)
    )
    return Match(record, title, authors, year, venue, suspicious, acceptable)


def best_candidate(
    info: EntryInfo, records: list[SourceRecord], *, preprint_pair: bool = False
) -> Match | None:
    """The best acceptable candidate, or None when no candidate (or more than one) qualifies.

    ``preprint_pair``: the entry cites a preprint, so a published version may be a year or two
    later.
    """
    matches = [
        m for m in (evaluate(info, r, preprint_pair=preprint_pair) for r in records) if m.acceptable
    ]
    if not matches:
        return None
    matches.sort(key=lambda m: (m.title.score or 0.0, m.authors.overlap), reverse=True)
    best = matches[0]
    distinct = {m.record.title.lower() for m in matches if (m.title.score or 0) >= TITLE_SAME}
    if len(distinct) > 1 and (best.title.score or 0) < 1.0:
        return None  # ambiguous: several different works fit equally well — refuse to guess
    return best
