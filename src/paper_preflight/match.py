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
from dataclasses import dataclass, field, replace
from datetime import date
from difflib import SequenceMatcher
from functools import cache
from importlib import resources
from typing import Literal
from urllib.parse import urlsplit

from rapidfuzz import fuzz
from rapidfuzz.distance import Levenshtein

from paper_preflight import chinese
from paper_preflight.bib.names import AuthorList, parse_authors
from paper_preflight.bib.normalize import fold, title_key, word_count
from paper_preflight.bib.parse import BibEntry
from paper_preflight.bib.plaintext import parse_reference
from paper_preflight.sources.dblp import PREPRINT_ARCHIVES
from paper_preflight.sources.record import COLLECTIVE_WORDS, Person, SourceRecord

Status = Literal["match", "variant", "mismatch", "unknown"]

TITLE_SAME = 0.95
TITLE_VARIANT = 0.90
TITLE_ACCEPT = 0.92  # minimum title similarity to accept an unanchored search candidate
MIN_PREFIX_CHARS = 30  # a title may omit its subtitle only if the remaining prefix is this long
MIN_PREFIX_WORDS = 5  # ... or has this many words ("An Image is Worth 16x16 Words", 29 chars)


def long_prefix(key: str) -> bool:
    """A title key long enough to stand for a title without its subtitle."""
    return len(key) >= MIN_PREFIX_CHARS or len(key.split()) >= MIN_PREFIX_WORDS


@dataclass(frozen=True)
class FieldCheck:
    status: Status
    score: float | None = None
    note: str = ""
    # titles: the words that differ from the closest recorded title, (entry's, record's) per place
    changed: tuple[tuple[str, str], ...] = ()


# Where an entry names its venue, in order of preference. Only the first three name it; the
# others may hold a URL or a publisher.
VENUE_FIELDS = ("booktitle", "journal", "journaltitle", "howpublished", "publisher")
NAMED_VENUE_FIELDS = frozenset(VENUE_FIELDS[:3])


_ISSN_RE = re.compile(r"\b\d{4}-\d{3}[\dX]\b")
_LINK_RE = re.compile(r"https?://[^\s{}<>\"]+", re.IGNORECASE)
_PAGE_SEPARATOR = re.compile(r"\s*(?:-+|–|—|,)\s*")


_CJK = re.compile("[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")


def has_cjk(text: str) -> bool:
    """The text has Han characters: Chinese (or Japanese) script."""
    return bool(_CJK.search(text))


def first_page(pages: str | None) -> str | None:
    """The first page or article number of a page field, lower-cased ("L25--L28" -> "l25")."""
    head = _PAGE_SEPARATOR.split((pages or "").strip(), maxsplit=1)[0].strip().lower()
    return head or None


# a number in an issuer's series of reports: "JWST-STScI-008296", "CUCS-006-96", "MSR-TR-2005-02";
# not an arXiv identifier ("2401.01234", "hep-th/9901001")
_REPORT_NUMBER = re.compile(r"[A-Za-z]{2,}[A-Za-z0-9]*(?:-[A-Za-z0-9]+)*-\d{2,}[A-Za-z0-9-]*")


def _issuer(entry: BibEntry) -> str | None:
    """Who issued a report: its institution, or a number in the issuer's own series."""
    institution = (entry.text("institution") or "").strip()
    if institution:
        return institution
    for name in ("number", "reportnumber", "eprint"):
        value = (entry.text(name) or "").strip()
        if _REPORT_NUMBER.fullmatch(value):
            return value
    return None


@dataclass(frozen=True)
class EntryInfo:
    """The parts of a BibTeX entry that matching needs, extracted once."""

    key: str
    title: str
    authors: AuthorList
    year: int | None
    venue: str | None
    entry_type: str
    venue_field: str | None = None  # where ``venue`` came from (booktitle, journal, publisher ...)
    link_hosts: tuple[str, ...] = ()  # hosts of the web pages the entry links to
    issns: frozenset[str] = frozenset()
    volume: str | None = None
    first_page: str | None = None  # see :func:`first_page`
    # a Chinese-language work cited in English ("... (in Chinese)"; see paper_preflight.chinese)
    translated: bool = False
    # who issued a report, by its institution or a number in its issuer's series
    # ("JWST-STScI-008296", "CUCS-006-96")
    issuer: str | None = None

    @classmethod
    def from_entry(cls, entry: BibEntry) -> EntryInfo:
        author_field = entry.fields.get("author") or entry.fields.get("editor")
        author_value = author_field.value if author_field else None
        # braces left in the text were escaped to show, as protection meant: "Oversmoothing in
        # {\{}GNN{\}}s" (PairNorm, ICLR 2020) is "GNNs" to every source searched
        title = (entry.text("title") or "").replace("{", "").replace("}", "")
        written = {} if title or author_value else reference_in_note(entry)
        year_text = entry.text("year") or (entry.text("date") or "")[:4] or written.get("year")
        match = re.search(r"\d{4}", year_text or "")
        venue_field = next((f for f in VENUE_FIELDS if entry.text(f)), None)
        venue = entry.text(venue_field) if venue_field else None
        if written:
            title, author_value = written["title"], written["author"]
            named = next((f for f in ("journal", "booktitle") if written.get(f)), None)
            if named:
                venue_field, venue = named, written[named]
        chapter = entry.text("chapter") or ""
        if entry.entry_type == "inbook" and len(re.findall(r"[^\W\d_]{2,}", chapter)) >= 3:
            # Springer's export: the paper in "chapter", the volume it is in as the title
            title, venue, venue_field = chapter, title, "booktitle"
        links = " ".join(entry.text(f) or "" for f in ("url", "howpublished", "note", "journal"))
        hosts = (urlsplit(url).hostname or "" for url in _LINK_RE.findall(links))
        other = " ".join(entry.text(f) or "" for f in ("note", "pages", "howpublished"))
        language = entry.text("language") or entry.text("langid") or ""
        is_translated = chinese.translated(title=title, venue=venue, other=other, language=language)
        return cls(
            key=entry.key,
            title=chinese.strip_mark(title),
            authors=parse_authors(author_value),
            year=int(match.group(0)) if match else None,
            venue=venue,
            entry_type=entry.entry_type,
            venue_field=venue_field,
            link_hosts=tuple(dict.fromkeys(h.removeprefix("www.") for h in hosts if h)),
            issns=frozenset(_ISSN_RE.findall((entry.text("issn") or "").upper())),
            volume=(entry.text("volume") or written.get("volume") or "").strip() or None,
            first_page=first_page(entry.text("pages") or entry.text("eid") or written.get("pages")),
            translated=is_translated,
            issuer=_issuer(entry),
        )


def reference_in_note(entry: BibEntry) -> dict[str, str]:
    """A whole formatted reference written in an entry's note, with no title or author fields,
    read as plain text: 2609.10121v2 gives each of its 46 references as "@misc{ref02, note =
    {Boiko, D. A., ... Autonomous chemical research with large language models. Nature 624,
    570-578 (2023). url}}". Empty unless a title and authors come out."""
    text = entry.text("note") or entry.text("howpublished") or ""
    if len(text) < 30 or not _NOTE_YEAR.search(text):
        return {}
    _, fields = parse_reference(text)
    if not fields.get("title") or not fields.get("author"):
        return {}
    return fields


_NOTE_YEAR = re.compile(r"(?<!\d)(?:1[89]|20)\d{2}(?!\d)")


# ---------------------------------------------------------------- titles


def title_score(a: str, b: str) -> float:
    ka, kb = title_key(a), title_key(b)
    if not ka or not kb:
        return 0.0
    if ka == kb:
        return 1.0
    return float(fuzz.ratio(ka, kb)) / 100.0


def subtitle_variant(a: str, b: str) -> bool:
    """One title is the other without its subtitle (``Title: Subtitle``).

    ``a`` is the entry's title, ``b`` the record's. A record title shorter than usual counts when
    it is all of the entry's part before the colon: Crossref has "Optical Nanofibers" for the
    chapter "Optical Nanofibers: A New Platform for Quantum Optics". A short entry title does not
    ("Natural Questions" may be another work).
    """
    ka, kb = title_key(a), title_key(b)
    short, long_ = sorted((ka, kb), key=len)
    if not (":" in a or ":" in b or " - " in a or " - " in b):
        return False
    if long_prefix(short) and long_.startswith(short):
        return True
    # or without the name before the colon: arXiv's "mHC: Manifold-Constrained Hyper-Connections"
    for full, rest in ((b, ka), (a, kb)):
        name, colon, tail = full.partition(":")
        short_name = colon and len(name.split()) <= 2
        if short_name and long_prefix(rest) and title_key(tail) == rest:
            return True
    if len(kb) >= len(ka):
        return False
    head = re.split(r":| - ", a, maxsplit=1)[0]
    return len(kb.split()) >= 2 and title_key(head) == kb


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


# Symbols one side writes as a word: ADS exports "M$_{sun}$" where Crossref has "M_⊙".
_SYMBOL_WORDS = {"\u2299": "sun", "\u2609": "sun", "\u2295": "earth", "\u2641": "earth"}
_SYMBOL_WORDS_RE = re.compile("|".join(_SYMBOL_WORDS))


# A registry's section label after the title ("... Future Directions [Review Article]", IEEE),
# the plates section ADS lists apart, in Semantic Scholar's title (". Plates."), or a journal's
# note that discussions follow ("... of MCMC (with Discussion)", Bayesian Analysis on Crossref)
# A chapter's or article's number before its title: "Chapter 4 - ...", Graphics Gems' "VIII.5. -
# Contrast Limited ..." (ScienceDirect), Phil. Trans.'s "XVI. Functions of Positive ..." (Crossref)
_CHAPTER_NUMBER = re.compile(r"^\s*(?:(?i:chapter)\s+\d+|[IVXLC]+\.(?:\d+\.?)?)\s*[-–—:.]?\s+")
_EDITION = re.compile(
    r",?\s*\(?(?:\d+(?:st|nd|rd|th)|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth)"
    r"\s+edition\)?\s*$",
    re.I,
)
_SECTION_LABEL = re.compile(
    r"\s*\[[^\[\]]{3,40}\]\s*$|\.\s*Plates\.?\s*$|\s*\(with (discussions?|comments)[^()]*\)\s*$",
    re.I,
)
_ARTICLES = frozenset({"a", "an", "the"})
_ACRONYM_AFTER = re.compile(r"^(?P<head>.{8,}?)\s*\((?P<acronym>[A-Z][A-Za-z]{1,11})\)\s*$")


def _without_acronym(title: str) -> str:
    """The title without the acronym after it that its words spell: DataCite's "Spitzer
    Enhanced Imaging Products (SEIP)" is the entry's "Spitzer Enhanced Imaging Products"."""
    found = _ACRONYM_AFTER.match(title)
    if not found:
        return title
    initials = iter(word[0] for word in re.findall(r"[^\W\d_]+", fold(found["head"])))
    # each letter an initial, in order (an iterator consumed as it goes)
    spelled = all(letter in initials for letter in found["acronym"].lower())
    return found["head"] if spelled else title


# A letter a registry lost: U+FFFD in "Berechnung der nat\ufffdrlichen Linienbreite" (Crossref)
_LOST = "\ufffd"
_LOST_MARK = "zzlostzz"
# A part's number in roman numerals or digits: "Seyfert Nuclei. II." is Crossref's "... 2:"
_ROMAN = {
    numeral: str(number)
    for number, numeral in enumerate(
        "i ii iii iv v vi vii viii ix x xi xii xiii xiv xv xvi xvii xviii xix xx".split(), start=1
    )
}
# Words an entry gives for a symbol a registry dropped: ADS's "Z$_{solar}$", Crossref's "Z"
_SYMBOL_NAMES = frozenset({"sun", "solar", "odot", "earth", "oplus", "jup", "jupiter"})
# A footnote mark a registry kept on the title's last word: Crossref's "... Absorption1"
_FOOTNOTE_MARK = re.compile(r"([a-z]{3,})\d")


def _same_word(a: str, b: str) -> bool:
    return _american(_ROMAN.get(a, a)) == _american(_ROMAN.get(b, b))


def _isotope(mine: str, recorded: str) -> bool:
    """A mass number written before or after its element: the same characters, a digit among
    them, in a word or two on each side."""
    a, b = mine.replace(" ", ""), recorded.replace(" ", "")
    return (
        a != b
        and any(c.isdigit() for c in a)
        and sorted(a) == sorted(b)
        and len(mine.split()) <= 2
        and len(recorded.split()) <= 2
    )


def changed_words(entry_title: str, record_title: str) -> tuple[tuple[str, str], ...]:
    """Where two titles differ word for word: (entry's words, record's words) per place.

    Case, punctuation, spacing and hyphenation ("Chain of-Thought", "Pre-training"), "&" for
    "and", British spellings, roman numerals for digits, and a registry's "RETRACTED:", lost
    symbol or footnote mark are not differences.
    """
    record_title = _SYMBOL_WORDS_RE.sub(
        lambda m: f" {_SYMBOL_WORDS[m.group(0)]} ", _EDITORIAL_PREFIX.sub("", record_title)
    ).replace(_LOST, _LOST_MARK)
    entry_title = _SYMBOL_WORDS_RE.sub(lambda m: f" {_SYMBOL_WORDS[m.group(0)]} ", entry_title)
    ours = title_key(entry_title.replace("&", " and ")).split()
    theirs = title_key(record_title.replace("&", " and ")).split()
    changes: list[tuple[str, str]] = []
    for op, i1, i2, j1, j2 in SequenceMatcher(a=ours, b=theirs, autojunk=False).get_opcodes():
        if op == "equal":
            continue
        mine, recorded = " ".join(ours[i1:i2]), " ".join(theirs[j1:j2])
        if _isotope(mine, recorded):
            continue  # "$^{13}$CO" and the registry's "CO-13", "$^{171}$Yb" and "Yb171"
        if mine.replace(" ", "") == recorded.replace(" ", "") or (
            i2 - i1 == j2 - j1
            and all(_same_word(a, b) for a, b in zip(ours[i1:i2], theirs[j1:j2], strict=True))
        ):
            continue
        quantity = i1 > 0 and len(ours[i1 - 1]) == 1 and ours[i1 - 1] not in {"a", "i"}
        if not recorded and mine in _SYMBOL_NAMES and quantity:
            continue  # "Z solar" where the registry dropped the symbol after "Z"
        footnote = _FOOTNOTE_MARK.fullmatch(recorded)
        if j2 == len(theirs) and footnote and footnote[1] == mine:
            continue  # the registry kept a footnote mark on the last word
        if not (mine + recorded).isascii() or (len(mine) <= 1 and len(recorded) <= 1):
            continue  # math: registries render "ε" as "ε", "epsilon" or "e", and variables vary
        last = i2 == len(ours) or j2 == len(theirs)
        if not (mine and recorded) and (mine or recorded) in _ARTICLES and not last:
            # an article one side has: Semantic Scholar's "Improved Method ..." for "An Improved
            # Method ...", ADS's "... of dense interstellar clouds" for Crossref's "of the dense
            # ..." (ApJ 354, 504); not a last word ("Model A"). Other small words count: an
            # entry that drops "of" misquotes the title (Krathwohl 2002, in the museum)
            continue
        if _LOST_MARK in recorded and re.fullmatch(
            ".{1,2}".join(map(re.escape, recorded.split(_LOST_MARK))), mine
        ):
            continue  # the letter the registry lost is the entry's
        changes.append((mine, recorded))
    return tuple(changes)


EARLIER_VERSION = "matches an earlier version's title"


CONTAINER_IN_TITLE = "the title field also names the book or proceedings"
NAME_AFTER_TITLE = "the title field adds a name in parentheses"
# a dataset's or system's name after the title: "... in Large Language Models (SimpleQA)"; one
# word with a second capital or a digit, so that "(Extended Abstract)" stays part of a title
_NAME_AFTER = re.compile(r"^(?P<head>.{12,}?)\s*\((?P<name>[A-Z][a-z]*[A-Z0-9][\w-]{0,22})\)\s*$")
# "Quarks and Strings on a Lattice, in New Phenomena in Subnuclear Physics": a chapter's title
# field that also names its book, a style trick (set with \textup in a real paper's .bib)
_IN_CONTAINER = re.compile(r"^(?P<head>.{12,}?),\s+in\s+(?P<tail>[A-Z]\S*(?:\s+\S+){2,})$")
# a name before what it is: "spaCy: Industrial-strength ...", "simplexity - Functions to ..."
_REPOSITORY_RELEASE = re.compile(r"^[\w.-]+/(?P<repo>[\w.-]+):\s")
_SOFTWARE_NAME = re.compile(r"^(?P<name>[^\s:]{2,40})\s*(?::|\s[-–—])\s+\S")

VOLUME_NOT_IN_RECORD = "the record's title leaves out the volume"
# "The Quantum Theory of Fields. Vol. 2: Modern Applications": a volume of a multi-volume book,
# which Crossref titles without the volume
_VOLUME = re.compile(
    r"^(?P<head>.{12,}?)[.,:]?\s+(?:vol(?:ume)?\.?|part|band|tome)\s*(?:\d+|[IVX]+)\b.*$",
    re.IGNORECASE,
)


def check_title(entry_title: str, record: SourceRecord) -> FieldCheck:
    if not entry_title or not record.title:
        return FieldCheck("unknown")
    if has_cjk(entry_title) != has_cjk(record.title):
        # one side in Chinese script, the other in Latin script: a translation cannot be compared
        # (ISTIC's record of a paper an English entry cites by its translated title)
        return FieldCheck("unknown")
    named = _SOFTWARE_NAME.match(entry_title)
    # Zenodo titles a release by its GitHub repository: "rdkit/rdkit: 2026_09_1 (Q3 2026) Release"
    repository = _REPOSITORY_RELEASE.match(record.title)
    if (
        record.work_type == "software"
        and named
        and title_key(named["name"])
        in {title_key(record.title), title_key(repository["repo"]) if repository else None}
    ):
        # software is cited by its name and what it does ("spaCy: Industrial-strength Natural
        # Language Processing in Python"); its record may carry the name alone ("spaCy")
        return FieldCheck("match", 1.0)
    named = _NAME_AFTER.match(entry_title)
    # not when the record has the name too, perhaps spaced out ("(S 4 G)" for "(S4G)")
    if named and title_key(named["name"]) not in title_key(record.title).replace(" ", ""):
        found = check_title(named["head"], record)
        if found.status == "match" and not found.changed:  # word for word without the name
            return replace(found, status="variant", note=NAME_AFTER_TITLE)
    within = _IN_CONTAINER.match(entry_title)
    if within and title_score(within["head"], record.title) >= TITLE_SAME:
        found = check_title(within["head"], record)
        return replace(found, status="variant", note=found.note or CONTAINER_IN_TITLE)

    volume = _VOLUME.match(entry_title)
    head = volume["head"] if volume and not _VOLUME.match(record.title) else ""
    if head and title_score(head, record.title) >= TITLE_SAME:
        found = check_title(head, record)
        return replace(found, status="variant", note=found.note or VOLUME_NOT_IN_RECORD)
    best = 0.0
    best_note = ""
    changed: tuple[tuple[str, str], ...] | None = None  # against the closest recorded title
    # a chapter's number before its title, as ScienceDirect exports it ("Chapter 4 - ...") and
    # Crossref sometimes records it ("Chapter 1 Förster resonance ..."); an edition after a
    # book's ("Statistical Analysis with Missing Data, Third Edition")
    entry_title = _CHAPTER_NUMBER.sub("", entry_title) or entry_title
    labelled = _SECTION_LABEL.sub("", record.title)
    titles = [(record.title, "")] + ([(labelled, "")] if labelled != record.title else [])
    for bare in (
        _CHAPTER_NUMBER.sub("", record.title),
        _EDITION.sub("", record.title),
        _without_acronym(record.title),
    ):
        if bare and bare != record.title:
            titles.append((bare, ""))
    for candidate, note in titles + [(t, EARLIER_VERSION) for t in record.alt_titles]:
        score = title_score(entry_title, candidate)
        if score > best:
            best, best_note = score, note
        subtitle = subtitle_variant(entry_title, candidate)
        if subtitle and best < TITLE_SAME:
            best, best_note = TITLE_SAME, "subtitle omitted"
        diff = () if subtitle else changed_words(entry_title, candidate)
        if changed is None or len(diff) < len(changed):
            changed = diff
    if best >= TITLE_SAME:
        return FieldCheck("variant" if best_note else "match", best, best_note, changed or ())
    if best >= TITLE_VARIANT:
        return FieldCheck("variant", best, best_note or "minor title difference", changed or ())
    return FieldCheck("mismatch", best, "", changed or ())


# ---------------------------------------------------------------- authors


# Apostrophes in names: straight, curly (Crossref's O’Connell), modifier letter, accents.
_APOSTROPHES = re.compile("['\u2018\u2019\u02bc\u0060\u00b4]")


def _group_key(name: str) -> str:
    """A group's key: "Gemma Team" (arXiv) is the entry's "{Gemma}", "The LIGO Scientific
    Collaboration" its "LIGO Scientific". Hyphens, footnote marks and word order do not count:
    arXiv's "Xiaomi LLM-Core Team" is the entry's "{LLM-Core Xiaomi}", Crossref's "The Tabula
    Sapiens Consortium*" the entry's "{The Tabula Sapiens Consortium}"."""
    words = re.findall(r"\w+", fold(_APOSTROPHES.sub("", name)))
    core = words[1:] if len(words) > 1 and words[0] == "the" else words
    while len(core) > 1 and core[-1] in COLLECTIVE_WORDS:
        core.pop()
    return " ".join(sorted(core))


def surname_key(person: Person) -> str:
    """Comparison key: last word of the folded family name (``van der Berg`` → ``berg``).

    Apostrophes are dropped, so O'Connell and O’Connell (as Crossref writes it) are one key.
    """
    if person.literal:
        return _group_key(person.literal)
    family = re.findall(r"\w+", fold(person.family))
    if not person.given and len(family) > 1:
        # a name of several words and no given name is a group's: "DeepSeek-AI", "Kimi-Team"
        return _group_key(person.family)
    if person.given and family and all(word in COLLECTIVE_WORDS for word in family):
        # BibTeX reads "Team, Chameleon" and "Gemma Team" as a given name and the family name
        # "Team": the group the record calls "Chameleon Team"
        return _group_key(f"{person.given} {person.family}")
    words = re.findall(r"[\w-]+", fold(_APOSTROPHES.sub("", person.family)))
    # a generational suffix is no surname: BibTeX's "Smith IV, David H" is Crossref's Smith
    while len(words) > 1 and words[-1] in {"jr", "sr", "ii", "iii", "iv"}:
        words.pop()
    return words[-1].strip("-") if words else ""


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
    family = re.findall(r"\w+", fold(_APOSTROPHES.sub("", person.family)))
    given = re.findall(r"\w+", fold(person.given))
    forms: set[str] = set()
    if family:
        forms |= {family[-1], "".join(family)}
        if given:
            forms.add(given[-1] + "".join(family))
    # a double surname cited by its first part: dblp's Alain Raymond-Saez is "Raymond, Alain"
    double = fold(person.family).split("-")
    if len(double) == 2 and min(len(part) for part in double) >= 3:
        forms.add(double[0])
    return {loose_surname(form) for form in forms if form}


def _first_given(person: Person) -> str:
    words = re.findall(r"\w+", fold(person.given))
    return words[0] if words else ""


def _name_words(text: str) -> set[str]:
    return {w for w in re.findall(r"\w+", fold(_APOSTROPHES.sub("", text))) if len(w) > 1}


def _same_words(a: Person, b: Person) -> bool:
    """One name split into given and family name another way, or with a name left out:
    Crossref's given "Vijendra Shenoy", family "S" is Shenoy, Vijendra S.; its given "Do",
    family "Long" is Do Xuan Long; arXiv's "De Luo" is the entry's "De Luo, Henry". Each
    side's family name must be among the other's words."""
    words_a, words_b = _name_words(a.display), _name_words(b.display)
    if min(len(words_a), len(words_b)) < 2 or not (words_a <= words_b or words_b <= words_a):
        return False
    return _name_words(a.family) <= words_b and _name_words(b.family) <= words_a


def _in_other_order(a: Person, b: Person) -> bool:
    """One name written in the other order, with an initial for the given name: Crossref's
    "K. Palanisamy" is the entry's "Karthikeyan, P." (Karthikeyan Palanisamy). Both surnames
    must be long enough not to be two people's (Kim, P. and K. Park)."""
    given_a, given_b = _given_words(a), _given_words(b)
    family_a, family_b = surname_key(a), surname_key(b)
    if len(given_a) != 1 or len(given_b) != 1 or min(len(family_a), len(family_b)) < 5:
        return False
    return given_a[0] in {family_b[0], family_b} and given_b[0] in {family_a[0], family_a}


def _double_surname(a: Person, b: Person) -> bool:
    """``a`` cites a double surname by its first part, and ``b`` was split as if the first were
    a given name: the entry's "Ramos, Sabela" is dblp's "Sabela Ramos Garea" (given "Sabela
    Ramos"), "Dehghani, Zahra" is "Zahra Dehghani Tafti". Short surnames are left out: "Li, Wei"
    is not "Zhang, Wei Li"."""
    given_b = re.findall(r"\w+", fold(b.given))
    first_a = re.findall(r"\w+", fold(a.given))
    family_a = fold(a.family).replace(" ", "")
    return (
        len(given_b) >= 2
        and bool(first_a)
        and len(first_a[0]) > 1
        and len(family_a) >= 4
        and len(fold(b.family)) >= 4
        and given_b[0] == first_a[0]
        and given_b[-1] == family_a
    )


def _first_surname(a: Person, b: Person) -> bool:
    """``a`` gives both surnames of a Spanish or Portuguese name, ``b`` only the first, with the
    same initial: the entry's "Schatan Pérez, C." is Crossref's "Claudia Schatan"."""
    family_a = re.findall(r"\w+", fold(a.family))
    family_b = fold(b.family).replace(" ", "")
    initial_a, initial_b = fold(a.given)[:1], fold(b.given)[:1]
    return (
        len(family_a) == 2
        and len(family_b) >= 4
        and family_a[0] == family_b
        and bool(initial_a)
        and initial_a == initial_b
    )


def _same_letters(a: Person, b: Person) -> bool:
    """The same names and initials in any order: "Rouse D. M." (Vancouver style, which BibTeX
    reads as given "Rouse D.", family "M.") is David M. Rouse; "Mallikarjun B. R." is the same
    either way round. Words pair with equal words, initials with words they begin; a full name
    of three letters or more must pair, so that initials alone never make a person."""
    rest_a = re.findall(r"\w+", fold(_APOSTROPHES.sub("", a.display)))
    rest_b = re.findall(r"\w+", fold(_APOSTROPHES.sub("", b.display)))
    if len(rest_a) != len(rest_b) or len(rest_a) < 2:
        return False
    full = False
    for word in [w for w in rest_a if len(w) >= 2]:
        if word in rest_b:
            rest_a.remove(word)
            rest_b.remove(word)
            full = full or len(word) >= 3
    if not full:
        return False
    pairs = zip(sorted(rest_a), sorted(rest_b), strict=True)
    return all(x[0] == y[0] and min(len(x), len(y)) == 1 for x, y in pairs)


def same_person(a: Person, b: Person) -> bool:
    """One person written differently by two sources (checked after exact surnames pair up)."""
    if surname_key(a) == surname_key(b) or _name_forms(a) & _name_forms(b) or _same_words(a, b):
        return True
    if _same_letters(a, b):
        return True
    if _in_other_order(a, b) or _double_surname(a, b) or _double_surname(b, a):
        return True
    if _first_surname(a, b) or _first_surname(b, a):
        return True
    # A one-letter slip in one source ("Hut" for Jiahui Hu, "Rent" for Kui Ren in a Crossref
    # record), accepted only when the full given names agree; or, in a surname of eight letters
    # or more, their initials ("Trakhenbrot" for B. Trakhtenbrot in Crossref and arXiv).
    key_a, key_b = surname_key(a), surname_key(b)
    if min(len(key_a), len(key_b)) < 2 or Levenshtein.distance(key_a, key_b) > 1:
        return False
    given, other = _first_given(a), _first_given(b)
    if len(given) >= 2 and given == other:
        return True
    initials_only = min(len(given), len(other)) == 1 and given[:1] == other[:1]
    return min(len(key_a), len(key_b)) >= _LONG_SURNAME and initials_only


_LONG_SURNAME = 8


def _transliterated(word: str) -> str:
    """One spelling of the ways a Cyrillic name is romanised: Iurii, Yurii and Yury are Yuri;
    Andrey Andrei, Dmitriy Dmitri (heldout16: arXiv's Iurii Makarov, dblp's Yuri). Names of
    four letters or more only; pinyin is left alone ("Yi" stays "Yi")."""
    if len(word) < 4:
        return word
    word = re.sub(r"^i(?=[aeou])", "y", word)
    return re.sub(r"(?:ii|iy|y)$", "i", word)


# Short forms that are not prefixes of the name they stand for.
_NICKNAMES = {
    frozenset(_transliterated(name) for name in pair.split("/"))
    for pair in (
        "bill/william bob/robert rob/robert bobby/robert dick/richard rick/richard jim/james "
        "jimmy/james mike/michael mick/michael tony/anthony andy/andrew drew/andrew dave/david "
        "steve/stephen steve/steven joe/joseph jack/john johnny/john ted/edward ned/edward "
        "ed/edward ted/theodore harry/henry hank/henry larry/lawrence chuck/charles "
        "charlie/charles peggy/margaret maggie/margaret meg/margaret kate/katherine "
        "kathy/katherine katie/katherine liz/elizabeth beth/elizabeth betty/elizabeth "
        "jenny/jennifer jen/jennifer sandy/alexandra sasha/alexander sasha/alexandra "
        "bert/albert bert/herbert nate/nathan nate/nathaniel jake/jacob tom/thomas "
        "pete/peter greg/gregory sue/susan susie/susan kim/kimberly ray/raymond liam/william "
        "misha/mikhail misha/michael sasha/aleksandr dima/dmitry dima/dmitri kolya/nikolai "
        "volodya/vladimir pasha/pavel zhenya/evgeny zhenya/evgeniy lena/elena katya/ekaterina "
        "yura/yuri gary/garrison danny/daniel freddy/frederic freddy/frederick russ/ruslan "
        "freddie/frederick fred/frederic fred/frederick nati/nathan nat/nathan "
        # Polish diminutives
        "tomek/tomasz kuba/jakub bartek/bartlomiej wojtek/wojciech jurek/jerzy "
        "staszek/stanislaw kasia/katarzyna gosia/malgorzata"
    ).split()
}


# One given name in the forms different languages give it (a Greek author's "Grigoris" is
# "Gregory" in dblp). Each line is one name; forms are folded like _given_words folds them.
_COGNATE_GROUPS = """
gregory gregor grigoris grigorios grigory grigorii grzegorz gregorio gregoire
george georg georgios giorgos giorgio jorge jerzy jiri yuri yury jurgen
john johann johannes johan jan jean juan giovanni ioannis yannis ivan joao jon jens hans
james jacob jakob jacques giacomo jaime jakub iakovos
peter pierre pedro pietro piotr petr petros pieter
paul pablo paolo pavel pawel paulo pavlos
michael michel miguel michele mikhail michal michalis mikael
nicholas nicolas nicola nikolai nikolay nikolaos nikos niklas mikolaj
alexander alexandre alessandro alejandro alexandr alexandros
andrew andre andreas andrea andres andrei andrey andrzej andrej
stephen steven stefan stephane stefano esteban stepan stefanos
thomas tomas tommaso tomasz
joseph josef jose giuseppe jozef iosif
william wilhelm guillaume guillermo guglielmo willem
charles carl karl carlos carlo karol
henry heinrich henri enrique enrico henrik
matthew matthias mathieu mateo matteo mateusz matvei
mark marc marco marcos markus marek
luke lucas luca lukas lukasz luc
anthony antonio antoine anton antonios
dimitri dimitrios dmitry dmitri demetrios
constantine konstantinos konstantin costantino kostas
emmanuel manuel emanuele manolis
christopher christoph christophe cristobal krzysztof
francis francois francesco francisco franz frantisek
vincent vincenzo vicente
elizabeth elisabeth isabel elisabetta
catherine katherine katharina caterina ekaterina katerina
helen helena elena eleni
"""
_COGNATES = {
    _transliterated(name.replace("ks", "x")): index
    for index, line in enumerate(_COGNATE_GROUPS.strip().splitlines())
    for name in line.split()
}


def _given_words(person: Person) -> list[str]:
    # initials written without dots, as Google Scholar exports them: "Brown, JR" is J. R. Brown
    if re.fullmatch(r"[A-Z]{2,3}", person.given.strip()):
        return list(person.given.strip().lower())
    # "ks" and "x" are one sound in transcriptions (Aleksandar, Alexander)
    words = re.findall(r"[a-z]+", fold(person.given).replace("ks", "x"))
    return [_transliterated(w) for w in words]


def given_names_differ(a: Person, b: Person) -> bool:
    """Two people with one surname whose written given names cannot be the same person's.

    Only full names count: an initial ("J."), a prefix ("Alex", "Chris"), a middle name used
    as the first ("Alp" for Durmus Alp Emre), hyphenation ("Jun-Yan", "Junyan"), a typo or a
    transcription ("Aleksandr"), common nicknames ("Bill") and one name's forms in other
    languages ("Grigoris" for Gregory) all agree.
    """
    if a.literal or b.literal:
        return False
    words_a, words_b = _given_words(a), _given_words(b)
    if not words_a or not words_b or len(words_a[0]) == 1 or len(words_b[0]) == 1:
        return False  # no given name, or an initial first: nothing to compare
    if "".join(words_a) == "".join(words_b):
        return False
    if {w for w in words_a if len(w) >= 2} & {w for w in words_b if len(w) >= 2}:
        return False
    first_a, first_b = words_a[0], words_b[0]
    if first_a.startswith(first_b) or first_b.startswith(first_a):
        return False
    if "and" + first_a == first_b or "and" + first_b == first_a:
        return False  # a registry that took "And" for a conjunction: Crossref's "res" for Andres

    if frozenset((first_a, first_b)) in _NICKNAMES:
        return False
    if _middle_nickname(words_a, first_b) or _middle_nickname(words_b, first_a):
        return False
    if first_a in _COGNATES and _COGNATES[first_a] == _COGNATES.get(first_b):
        return False
    if _name_and_initials(words_a, words_b) or _name_and_initials(words_b, words_a):
        return False
    return fuzz.ratio(first_a, first_b) < 75 and Levenshtein.distance(first_a, first_b) > 1


def _middle_nickname(words: list[str], other: str) -> bool:
    """``other`` is a nickname of a name whose initial is one of ``words``' middle initials:
    "Robert M." publishes as "Mike" (Robert Michael Kirby)."""
    formal = {name for pair in _NICKNAMES if other in pair for name in pair if name != other}
    middles = [w for w in words[1:] if len(w) == 1]
    return any(name.startswith(m) for m in middles for name in formal)


def _name_and_initials(words: list[str], others: list[str]) -> bool:
    """An English name before the initials of the other's two or more given names: "Ricky T. Q."
    is dblp's Tian Qi Chen. One initial is a middle name's: "Seth A." is not Aaron."""
    initials = words[1:]
    return (
        len(initials) >= 2
        and all(len(w) == 1 for w in initials)
        and [o[0] for o in others] == initials
    )


@dataclass(frozen=True)
class AuthorCheck(FieldCheck):
    overlap: float = 0.0
    first_author_match: bool = False
    disjoint: bool = False
    missing: tuple[str, ...] = field(default=())  # entry authors not found in the record
    # surnames that pair up with another person's given name: (entry's name, record's name)
    renamed: tuple[tuple[str, str], ...] = field(default=())
    # the record's people the entry leaves out before another it lists: not a list cut short
    # but a name dropped from the middle (HALLMARK's partial author lists)
    left_out: tuple[str, ...] = field(default=())


_INITIALS_ONLY = re.compile(r"^(?:[A-Z]\.?){1,3}$")


def _as_meant(person: Person, other_keys: set[str]) -> Person:
    """ "Zhang C." written without a comma reads as given name "Zhang", family name "C.".

    When the other side has no such family name but has a Zhang, the name is taken as meant:
    family name first, then initials (PubMed's form, seen in a real paper's .bib). Registries do
    it too: Crossref files the single name and initial "Shwetha S" as given name Shwetha.
    """
    if person.literal or not _INITIALS_ONLY.match(person.family):
        return person
    if not re.fullmatch(r"[^\W\d_][\w'-]+", person.given):
        return person
    swapped = Person(family=person.given, given=person.family)
    if surname_key(person) not in other_keys and surname_key(swapped) in other_keys:
        return swapped
    return person


def _organisation(person: Person) -> bool:
    """A collective author: a literal name, or a single word without a given name ("OpenAI")."""
    return bool(person.literal) or (not person.given and len(person.family.split()) == 1)


def _group(person: Person) -> bool:
    """A group credited as an author: "{The Tabula Sapiens Consortium}", "Thinking Machines
    Lab" (which BibTeX splits into given and family name)."""
    return any(word in COLLECTIVE_WORDS for word in _name_words(person.display))


# words of a name that is no person's: an affiliation a registry took for an author ("Ural
# Federal University"), a placeholder ("Paper Authors")
_NOT_A_PERSON = frozenset(
    "university universities college school department centre center academy hospital "
    "authors network".split()
)
# a list this long is a collaboration's, which citing authors shorten as they see fit
_LONG_LIST = 30


def _left_out_person(person: Person) -> bool:
    """Someone whose absence from the middle of a list is worth naming: not a group, an
    organisation, a single name, or an affiliation ("Qassim University, Buraidah, Kingdom of
    Saudi Arabia" in Crossref's record of a two-author article)."""
    if _group(person) or _organisation(person) or "," in person.display:
        return False
    return not (_name_words(person.display) & _NOT_A_PERSON)


def _same_group(a: Person, b: Person) -> bool:
    """One group under a longer name: ESO's DataCite records end with "And The MAGPI Team";
    an entry credits "on behalf of the CMS Collaboration" (J. Phys. Conf. Ser. 1162, 012002)."""
    ours = _name_words(a.display) - {"and", "the", "on", "behalf", "of", "for"}
    return bool(ours) and _group(b) and ours <= _name_words(b.display)


def _same_one(a: Person, b: Person) -> bool:
    """One person, or one group by its acronym."""
    return same_person(a, b) or _acronym_of(a, b)


def _acronym_of(a: Person, b: Person) -> bool:
    """A group by its acronym: the entry's "{ROTAC}" is the Roman Observations Time Allocation
    Committee of arXiv 2505.10574 (heldout16)."""
    name = (a.literal or a.family).strip()
    if (a.given and not a.literal) or not re.fullmatch(r"[A-Z]{3,8}", name):
        return False
    words = re.findall(r"[^\W\d_]+", b.display)
    initials = "".join(w[0] for w in words if w.lower() not in {"and", "the", "of", "for", "on"})
    return initials.upper() == name


def _pair_by_given_name(
    entry: list[tuple[Person, str]], pool: list[tuple[Person, str]]
) -> dict[int, int]:
    """Pair entry and record people of one surname whose given names agree, as many as possible.

    Co-authors sharing a surname (Yang Song and Jiaming Song; Lihwai, Yen-Ting and Sicheng Lin in
    SDSS DR17) must not be paired in order: "L. Lin" agrees with each of them, and taking the
    first would leave a later Lin with none. Augmenting paths find the largest pairing.
    """
    options = [
        [
            i
            for i, (other, k) in enumerate(pool)
            if k == key and (not given_names_differ(person, other) or _same_words(person, other))
        ]
        for person, key in entry
    ]
    owner: dict[int, int] = {}  # record index -> entry index

    def place(j: int, seen: set[int]) -> bool:
        for i in options[j]:
            if i not in seen:
                seen.add(i)
                if i not in owner or place(owner[i], seen):
                    owner[i] = j
                    return True
        return False

    for j in range(len(entry)):
        place(j, set())
    return {j: i for i, j in owner.items()}


def _latin_part(person: Person) -> Person:
    """A name a registry wrote in Latin and another script, as the Latin part: Crossref's
    "Tonima Tasnim অনন্যা" "Ananna তনিমা তাসনিম" (ApJL 969, L18; dev3) is Tonima Tasnim Ananna."""
    if person.literal or person.display.isascii():
        return person

    def latin(text: str) -> str:
        words = text.split()
        kept = [w for w in words if not re.search(r"[^\W\d_]", fold(w)) or fold(w).isascii()]
        return " ".join(kept) if kept and len(kept) < len(words) else text

    family = latin(person.family)
    if not family or not fold(family).isascii():
        return person
    return Person(family=family, given=latin(person.given))


def _lost_letters(person: Person, written: tuple[Person, ...]) -> Person:
    """A recorded name with a character the registry lost (Schönle as "P. Sch" + _LOST +
    "nle", Crossref) as the entry writes it, when exactly one of the entry's names fits it
    letter for letter."""
    if _LOST not in person.family:
        # or dropped without a trace: Crossref's "Ivezi" for Ivezić (ApJ 596, L191), the
        # entry's name the recorded one and a letter or two outside ASCII
        fits = [
            p for p in written
            if p.family.lower().startswith(person.family.lower())
            and 0 < len(p.family) - len(person.family) <= 2
            and not p.family[len(person.family):].isascii()
            and len(person.family) >= 4
        ]  # fmt: skip
        return replace(person, family=fits[0].family) if len(fits) == 1 else person
    # one letter may have become two marks, one per byte ("G" + 2 marks + "nther", Günther)
    pattern = ".{1,2}".join(map(re.escape, re.split(f"{_LOST}+", person.family)))
    fits = [p for p in written if re.fullmatch(pattern, p.family, re.IGNORECASE)]
    return replace(person, family=fits[0].family) if len(fits) == 1 else person


def check_authors(authors: AuthorList, record: SourceRecord) -> AuthorCheck:
    check = _check_authors(authors, record)
    if check.disjoint and len(record.authors) >= 2:
        # a registry that put Chinese names the other way round: given "LI", family
        # "Zhen-qiang" (Chinese Astronomy and Astrophysics 45, 559, in Crossref)
        swapped = tuple(
            Person(family=p.given, given=p.family) if p.given and not p.literal else p
            for p in record.authors
        )
        other = _check_authors(authors, replace(record, authors=swapped))
        if other.status in {"match", "variant"}:
            return other
    return check


def _check_authors(authors: AuthorList, record: SourceRecord) -> AuthorCheck:
    written = {surname_key(person) for person in authors.people}
    recorded = [_lost_letters(_latin_part(p), authors.people) for p in record.authors]
    people = [_as_meant(p, written) for p in recorded if surname_key(p)]
    record_keys = [surname_key(person) for person in people]
    meant = [_as_meant(person, set(record_keys)) for person in authors.people]
    entry = [(person, key) for person in meant if (key := surname_key(person))]
    if not entry or not people:
        return AuthorCheck("unknown")
    if all(_group(p) or p.literal for p in people) and not all(
        _group(p) or _organisation(p) for p, _ in entry
    ):
        # a record crediting only a group says nothing of the people the entry lists with it
        # (dblp's "Gemini Robotics Team" for arXiv 2503.20020, which names them all; heldout16)
        return AuthorCheck("unknown")
    # exact surnames first, then spelling variants, so a variant never takes an exact match
    paired = _pair_by_given_name(entry, list(zip(people, record_keys, strict=True)))
    taken = set(paired.values())
    renamed: list[tuple[str, str]] = []
    for j, (person, key) in enumerate(entry):
        if j in paired:
            continue
        index = next((i for i, k in enumerate(record_keys) if k == key and i not in taken), None)
        if index is not None:
            paired[j] = index
            taken.add(index)
            renamed.append((person.display, people[index].display))
    missing: list[str] = []
    groups: set[int] = set()  # groups credited where the record lists no group
    # (a one-word handle such as GitHub's "sriniker" on a Zenodo release is no group)
    people_only = not any(_group(p) for p in people)
    for j, (person, _) in enumerate(entry):
        if j in paired:
            continue
        index = next(
            (i for i, other in enumerate(people) if i not in taken and same_person(person, other)),
            None,
        )
        if index is None and _group(person):
            index = next(
                (i for i, o in enumerate(people) if i not in taken and _same_group(person, o)),
                None,
            )
        if index is None:
            index = next(
                (i for i, o in enumerate(people) if i not in taken and _acronym_of(person, o)),
                None,
            )
        if index is None and people_only and _group(person):
            groups.add(j)  # "Kevin Lu and Thinking Machines Lab": the lab is no missing person
        elif index is None:
            missing.append(person.display)
        else:
            taken.add(index)
    counted = len(entry) - len(groups)
    matched = counted - len(missing)
    if matched == 0 and (counted == 0 or all(_organisation(p) for p in people)):
        # a consortium credited for the people the record lists (Cell's COMBAT Consortium), or a
        # record naming only an organisation (dblp's "DeepSeek-AI" for the DeepSeek-R1 report)
        return AuthorCheck("unknown")
    overlap = matched / counted
    first_person = next(p for j, (p, _) in enumerate(entry) if j not in groups)
    if record.authors_ordered:
        leads = [people[0]]
        # an organisation leading the record ("OpenAI" before Josh Achiam, arXiv 2303.08774) is
        # no first author to compare with when the entry leaves it out or names it later
        # ("Kevin Lu and Thinking Machines Lab", as the lab asks; Crossref has the lab first),
        # nor is a collaboration Crossref files as a person ("The ALICE" "Collaboration" before
        # K. Aamodt, JINST 3 S08002)
        if _organisation(people[0]) or _group(people[0]):
            leads += people[1:2]
        first = any(_same_one(first_person, lead) for lead in leads)
    else:
        first = any(_same_one(first_person, other) for other in people)
    missing_names = tuple(missing)
    last = max(taken, default=-1)
    left_out = (
        tuple(
            people[i].display for i in range(last) if i not in taken and _left_out_person(people[i])
        )
        if len(people) <= _LONG_LIST
        else ()
    )

    def result(status: Status, note: str = "", *, disjoint: bool = False) -> AuthorCheck:
        return AuthorCheck(
            status, overlap, note, overlap=overlap, first_author_match=first,
            disjoint=disjoint, missing=missing_names, renamed=tuple(renamed), left_out=left_out,
        )  # fmt: skip

    if matched == 0:
        return result("mismatch", "no author in common", disjoint=True)
    if missing and not record.authors_complete and len(taken) == len(people) and first:
        # the record lists only some of the authors (a dataset's deposit, a truncated list) and
        # all of them are in the entry: the entry's other authors are no error
        return result("match")
    if overlap == 1.0 and first:
        omitted = (
            len(entry) < len(record_keys) and not authors.truncated and record.authors_complete
        )
        return result("variant", "some authors omitted") if omitted else result("match")
    if overlap >= 0.5 and first:
        return result("variant", "some authors differ")
    return result("mismatch", "author list differs")


# ---------------------------------------------------------------- year and venue


def is_preprint(record: SourceRecord) -> bool:
    return (
        record.source == "arxiv"
        or record.work_type in {"preprint", "posted-content"}
        or canonical_venue(record.venue) == "arxiv"
        or (record.source == "dblp" and record.venue in PREPRINT_ARCHIVES)
    )


# Records of proceedings, whose volume may appear the year after the meeting
_PROCEEDINGS_TYPES = frozenset({"proceedings-article", "book-chapter", "inproceedings"})
# a record's venue that is a meeting's proceedings
_HELD = re.compile(r"\b(?:conference|symposium|workshop|congress)\b", re.I)
# Resources that keep changing after they are registered (DataCite resource types)
_LIVING_TYPES = frozenset({"dataset", "service", "database", "collection"})
# a year check's note when the record may be a later edition of the book the entry cites
LATER_EDITION = "a later edition"
# a book record this many years after the year an entry gives is a reissue's, not the book's
REISSUE_GAP = 10
# a whole book, in Crossref's, OpenAlex's and DataCite's words
_BOOK_RECORD_TYPES = frozenset({"book", "monograph", "edited-book", "reference-book", "book-set"})


# a workshop, also as a conference's acronym with a W ("NeurIPSW on Deep Generative Models")
_WORKSHOP = re.compile(r"\bworkshops?\b|\b(?:neurips|nips|icml|iclr|cvpr|iccv|eccv)w\b", re.I)


def names_workshop(venue: str | None) -> bool:
    """The venue is a workshop ("Proceedings of the First Workshop on ...", "EurIPS 2025
    Workshop: AI for Tabular Data")."""
    return bool(_WORKSHOP.search(venue or ""))


# a year a publisher wrote into a DOI's suffix with the month or issue run on: ".202007_",
# ".2022096". Not a year standing alone (".2024.0241", ".2016.1158716"), often the year the DOI
# was registered rather than the issue's.
_DOI_YEAR = re.compile(r"\.((?:19|20)\d\d)\d{2,3}(?=[._(]|$)")


def _doi_year(doi: str | None) -> int | None:
    match = _DOI_YEAR.search(doi.split("/", 1)[-1]) if doi else None
    return int(match.group(1)) if match else None


def names_year(venue: str | None, year: int) -> bool:
    """The venue names the year: "Proceedings of SAT-2003", "ICML 2019", "NeurIPS'19"."""
    if not venue:
        return False
    short = f"{year % 100:02d}"
    return bool(re.search(rf"(?<!\d){year}(?!\d)|['’]{short}\b", venue))


def check_year(
    year: int | None,
    record: SourceRecord,
    *,
    preprint_pair: bool = False,
    venue: str | None = None,
) -> FieldCheck:
    years = record.all_years
    if year is None or not years:
        return FieldCheck("unknown")
    if year in years:  # any registered year counts (online-first, print, preprint versions)
        return FieldCheck("match")
    if (
        year + 1 in years
        and (
            record.work_type in _PROCEEDINGS_TYPES
            or "/conf/" in f"/{record.source_id}"
            or _HELD.search(record.venue or "")
        )
        and (names_year(venue, year) or names_year(record.venue, year))
    ):
        # the meeting's year, which the entry's venue names (SAT 2003, its LNCS volume 2004) or
        # the record's (SPIE's "Sixteenth International Conference on Machine Vision (ICMV
        # 2023)", volume 2024; IET's Conference Proceedings, deposited as journal articles; dev3)
        return FieldCheck("match")
    if min(years) < year < max(years) <= min(years) + 2:
        # between two of the article's own dates: an issue dated between its appearance online
        # and in print (Int. J. Epidemiol. 49(6), December 2020: online 2019, print 2021). Not
        # between a print date and a backfile's years later (SIAM J. Control Optim. 42(4),
        # 2003, online in 2006: 2004 is wrong)
        return FieldCheck("match")
    if abs(year - min(years)) == 1 and year == _doi_year(record.doi):
        # the year the publisher wrote into the DOI, where Crossref has only another date
        # (J. Data Sci. 10.6339/jds.202007_18(3).0003, the July 2020 issue, dated 2021;
        # 10.3934/mbe.2022096, volume 19, 2022, dated 2021)
        return FieldCheck("match")
    if year - 1 in years and record.source_id.startswith("journals/jmlr/"):
        # a JMLR volume runs into the next year: dblp files volume 18 under 2017, and JMLR
        # cites its paper 18(167) as 2018
        return FieldCheck("match")
    if (
        record.work_type in _BOOK_RECORD_TYPES
        and year < min(years)
        and (record.reissue or min(years) - year >= REISSUE_GAP)
    ):
        # a publisher's backfile record of a book may carry a later printing's date, the book
        # itself older (Bhatia's Positive Definite Matrices, Princeton 2007: De Gruyter's record,
        # 2009, its DOI registered in 2014); so does a reissue decades on (Crowder's Principles
        # of Learning and Memory, 1976: Psychology Press's Classic Edition, 2014; dev2). A record
        # made with the book is believed: Poisson and Will's Gravity is 2014, not 2012.
        return FieldCheck("variant", None, f"{LATER_EDITION}, recorded year(s) {sorted(years)}")
    if record.work_type in _LIVING_TYPES and max(years) < year <= date.today().year:
        # a database or service is cited by the year it was used, as its maintainers ask (USGS
        # NWIS: DataCite's 1994 is when the service started)
        return FieldCheck("variant", None, f"recorded year(s) {sorted(years)}")
    if record.work_type == "software" and year < min(years):
        # software is cited by the year its makers name, often the project's first; a DOI that
        # stands for every version resolves to the latest release (RDKit, 2006: Zenodo's record
        # is the 2026_09_1 release; heldout16)
        return FieldCheck("variant", None, f"a later release, recorded year(s) {sorted(years)}")
    if (record.doi or "").startswith("10.2139/ssrn.") and max(years) < year <= date.today().year:
        # SSRN keeps one DOI for every revision and dates it by the first posting: "Available at
        # SSRN 3062830", 2020, is a revision of the 2017 paper (dev3)
        return FieldCheck("variant", None, f"a later revision, recorded year(s) {sorted(years)}")
    if year < min(years) and min(years) > date.today().year:
        # only a date still to come: the issue a paper accepted "to appear" is scheduled for
        # (Statistica Sinica, accepted 2025: Crossref has 2028; heldout16)
        return FieldCheck("variant", None, f"a scheduled issue, recorded year(s) {sorted(years)}")
    # No general ±1 tolerance: refchecker dropped it because it silently hid real year errors.
    # Only preprint/published pairs legitimately differ by a year or two.
    distance = min(abs(year - y) for y in years)
    preprint = preprint_pair or record.work_type in {"preprint", "posted-content"}
    if preprint and distance <= 2:
        return FieldCheck("variant", None, f"recorded year(s) {sorted(years)}")
    if distance == 1 and is_preprint(record) and _WORKSHOP.search(venue or ""):
        # a workshop paper is cited by its workshop's year, and many reach arXiv only later
        # (Classifier-Free Diffusion Guidance: NeurIPS 2021 workshop, arXiv 2022)
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
    ("aaai", ("aaai", "national conference on artificial intelligence")),
    ("ijcai", ("ijcai", "international joint conference on artificial intelligence")),
    # "ACM SIGKDD international conference on Knowledge discovery in data mining" (KDD 2005)
    (
        "kdd",
        (
            "kdd",
            "sigkdd",
            "knowledge discovery and data mining",
            "knowledge discovery in data mining",
        ),
    ),
    ("sigir", ("sigir",)),
    ("jmlr", ("jmlr", "journal of machine learning research")),
    ("tpami", ("tpami", "pattern analysis and machine intelligence")),
    ("ijcv", ("ijcv", "international journal of computer vision")),
    ("tmlr", ("tmlr", "transactions on machine learning research")),
    ("aistats", ("aistats", "artificial intelligence and statistics")),
    ("uai", ("uai", "uncertainty in artificial intelligence")),
    ("colt", ("colt", "conference on learning theory", "computational learning theory")),
    ("corl", ("corl", "conference on robot learning")),
    # on OpenReview only, in no catalogue of journals and conferences
    ("colm", ("colm", "conference on language modeling")),
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


def _venue_words(text: str) -> str:
    """A venue name as lower-case words, links dropped and "&" read as "and" ("Knowledge
    Discovery & Data Mining" is KDD)."""
    return " ".join(re.findall(r"[\w-]+", fold(_URL.sub(" ", text).replace("&", " and "))))


def canonical_venue(text: str | None) -> str | None:
    if not text:
        return None
    folded = _venue_words(text)
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
    # ordinals: "Proceedings of the Thirty-Fifth AAAI Conference"
    + "first second third fourth fifth sixth seventh eighth ninth tenth eleventh twelfth "
    "thirteenth fourteenth fifteenth sixteenth seventeenth eighteenth nineteenth twentieth "
    "twenty thirtieth thirty fortieth forty fiftieth fifty sixtieth sixty".split()
)
# Words of the full names of venues whose patterns are only their abbreviation.
_VENUE_FULL_NAMES = {
    "aaai": "association for the advancement of artificial intelligence conference on artificial "
    "intelligence",
    "neurips": "advances in neural information processing systems",
    "sigir": "research and development in information retrieval",
    "interspeech": "conference of the international speech communication association",
}


def canonical_venues(text: str | None) -> set[str]:
    """Every recognised venue a name names: "COLING/ACL 2006" names COLING and ACL."""
    if not text:
        return set()
    folded = _venue_words(text)
    return {
        key
        for key, patterns in _VENUES
        if any(re.search(rf"(?<!\w){re.escape(p)}(?!\w)", folded) for p in patterns)
    }


_SIG_NEWSLETTER = re.compile(
    r"\bSIG[A-Z]+ (?:Notices|Record|News|Newsletter)\b|Computer Architecture News|"
    r"Operating Systems Review|Performance Evaluation Review|Software Engineering Notes",
    re.IGNORECASE,
)


def venue_words(text: str | None) -> set[str]:
    words = re.findall(r"[a-z]+", fold(text or ""))
    return {w for w in words if len(w) >= 3 and w not in _VENUE_FILLER}


def related_words(ours: set[str], theirs: set[str]) -> bool:
    """Some word of one name abbreviates or equals a word of the other ("recog"/"recognition")."""
    return any(a.startswith(b) or b.startswith(a) for a in ours for b in theirs)


def _abbreviates(word: str, known: set[str]) -> bool:
    """``word`` is a known word, an abbreviation of one ("mach") or a longer form ("networks")."""
    return any(k.startswith(word) or (len(k) >= 5 and word.startswith(k)) for k in known)


# Series and publishers that stand in for a venue name ("Proceedings of Machine Learning
# Research" for ICML); they say nothing about which venue it was.
VENUE_SERIES = re.compile(
    r"proceedings of machine learning research|\bpmlr\b|"
    r"lecture notes in (computer science|artificial intelligence|bioinformatics)|\blncs\b|"
    r"\blnai\b|openreview(\.net)?|curran associates|\bceur\b|springer|elsevier|mit press|"
    r"acm press|aaai press|ieee computer society|association for computing machinery",
    re.I,
)


_MEETING = re.compile(r"proceedings|conference|symposium|workshop|congress|meeting|assembly", re.I)


def check_venue(
    venue: str | None,
    record: SourceRecord,
    *,
    named: bool = True,
    journal: bool = False,
    issns: frozenset[str] = frozenset(),
) -> FieldCheck:
    """The entry's venue against the record's; see :func:`_check_venue`. Semantic Scholar's
    venue only ever counts for a match: it files workshops under their conference (ROUGE, of
    the ACL 2004 workshop Text Summarization Branches Out, under ACL), and on the real-paper
    batches its venues gave two false REF014s and no real one."""
    found = _check_venue(venue, record, named=named, journal=journal, issns=issns)
    if found.status == "mismatch" and record.source == "s2":
        return FieldCheck("unknown")
    return found


def _check_venue(
    venue: str | None,
    record: SourceRecord,
    *,
    named: bool = True,
    journal: bool = False,
    issns: frozenset[str] = frozenset(),
) -> FieldCheck:
    """A mismatch needs positive evidence: two recognised, different venues, or a venue nobody
    recognises next to a recognised recorded one, naming something the recorded one does not.

    The second case catches invented venues ("Annual Conference on Spatial Intelligence" or
    "International Conference on Quantum Machine Learning" for an ICML paper; HALLMARK's
    nonexistent_venue type) without flagging abbreviations such as "Proc. IEEE Conf. Comp. Vis.
    Patt. Recog." for CVPR. It needs two words to compare, ignores series and publishers (PMLR,
    LNCS, OpenReview), and only judges venue names (``named``: booktitle or journal, not a
    publisher). A workshop must share no word at all: its name rarely contains its venue's.
    """
    if venue and _SIG_NEWSLETTER.search(venue):
        # ACM's SIG newsletters carry the proceedings of their conferences (ASPLOS in SIGARCH
        # Computer Architecture News): the newsletter is no other venue
        return FieldCheck("unknown")
    mine, theirs = canonical_venue(venue), canonical_venue(record.venue)
    if mine is not None and theirs is not None:
        if mine == theirs or theirs in canonical_venues(venue):
            return FieldCheck("match")  # or a joint meeting: COLING/ACL 2006 is ACL's too
        if "workshop" in fold(venue or "") and "workshop" not in fold(record.venue or ""):
            # a workshop at another meeting: the work's workshop version (Pavlova et al., the
            # ICLR 2025 BuildingTrust workshop, then ICML 2025)
            return FieldCheck("unknown")
        return FieldCheck("mismatch", None, f"{mine} vs {theirs}")
    if "@" in (record.venue or "") and re.search(
        r"\b(?:workshops?|challenges?)\b", venue or "", re.I
    ):
        # dblp names a workshop or challenge by its acronyms at its conference: "CMRxRecon/MBAS/
        # STACOM@MICCAI" for the Workshop on Statistical Atlases and Computational Models of the
        # Heart, "HECKTOR@MICCAI" for the 3D Head and Neck Tumor Segmentation in PET/CT Challenge
        return FieldCheck("unknown")
    if mine is None and theirs is not None and named and venue:
        ours = venue_words(VENUE_SERIES.sub(" ", venue))
        # every word of the recorded name and its known forms, filler included ("adv", "proc")
        names = [record.venue or "", _VENUE_FULL_NAMES.get(theirs, "")]
        names += next(p for k, p in _VENUES if k == theirs)
        known = {w for name in names for w in re.findall(r"[a-z]+", fold(name)) if len(w) >= 3}
        foreign = {w for w in ours if not _abbreviates(w, known)}
        workshop = "workshop" in fold(venue)
        if len(ours) >= 2 and foreign and (foreign == ours or not workshop):
            return FieldCheck("mismatch", None, f"unrecognised venue vs {theirs}")
    if issns & record.issns:
        return FieldCheck("match")
    if (
        journal and mine is None and theirs is None and venue
        and record.source in {"crossref", "dblp"}
        and not _MEETING.search(venue)
        and venue.isascii() and (record.venue or "").isascii()
    ):  # fmt: skip
        # A journal nobody recognises, and the name of where the work appeared: another venue
        # only if the names share no word or abbreviation. LIONESS (Kuijjer et al., iScience
        # 2019) cited in Nature Communications; GROBID (Lopez, ECDL 2009) cited in the
        # "International Journal on Document Analysis and Recognition" (Badalova & Mayr). Not a
        # meeting's name, even in the journal field: dblp names it by acronym ("PODS"), and the
        # entry may cite a talk or abstract of the same title. Not a name in another language.
        ours = venue_words(VENUE_SERIES.sub(" ", venue))
        names = [record.venue or "", *record.venue_aliases]
        recorded = {w for name in names for w in venue_words(VENUE_SERIES.sub(" ", name))}
        if len(ours) >= 2 and recorded and not related_words(ours, recorded):
            return FieldCheck("mismatch", None, "venues share no word")
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


_AUTHOR_FIT = {"match": 3, "variant": 2, "unknown": 1, "mismatch": 0}


def _fit(title: FieldCheck, authors: AuthorCheck) -> tuple[bool, int, float, float]:
    return (
        title.status != "mismatch", _AUTHOR_FIT[authors.status], title.score or 0.0,
        authors.overlap,
    )  # fmt: skip


def _as_chinese_journal_record(record: SourceRecord) -> SourceRecord:
    """A Chinese-language journal's record as an English entry is compared with it. Crossref's
    backfile records of these journals put a whole name in the family name ("Jia Zheng-Mao",
    Acta Physica Sinica), list the first author only, or list the authors in another order than
    the printed paper; the experiments' development data had seven false author findings so."""
    people = []
    for person in record.authors:
        words = person.family.split()
        if not person.given and not person.literal and 2 <= len(words) <= 3:
            person = Person(family=words[0], given=" ".join(words[1:]))
        people.append(person)
    return replace(
        record,
        authors=tuple(people),
        authors_ordered=False,
        authors_complete=record.authors_complete and len(people) > 1,
    )


DISCUSSION_OF_RECORD = "a comment on the recorded work, under its DOI"
# "Comment on ``That BLUP is a Good Thing ...'' by G. K. Robinson", "Discussion of ...",
# "Rejoinder to ..."
_DISCUSSION_OF = re.compile(
    r"^\s*(?:comments?|discussion|rejoinder)\s+(?:on|of|to)\s+[\"'`‘“]*(?P<title>.+?)[\"'’”]*"
    r"(?:,?\s+by\s+[^,]{2,60})?\s*$",
    re.IGNORECASE,
)


def _maker_in_title(info: EntryInfo, record: SourceRecord) -> SourceRecord | None:
    """The record retitled without the organisation the entry credits alone, when its title
    starts with that name and is otherwise the entry's: None if it does not."""
    people = info.authors.people
    if len(people) != 1 or not _organisation(people[0]):
        return None
    name = people[0].display
    found = re.match(rf"{re.escape(name)}(?:'s|’s)?:?\s+(?P<rest>.+)$", record.title, re.I)
    if not found or title_key(found["rest"]) != title_key(info.title):
        return None
    return replace(record, title=found["rest"])


def _title_and_authors(info: EntryInfo, record: SourceRecord) -> tuple[FieldCheck, AuthorCheck]:
    """The title and authors, checked against the version of the work the entry fits best.

    An entry citing an earlier arXiv version lists that version's title and authors: AstroCLIP's
    v2 (arXiv 2310.03024) changed the title and put Parker before Lanusse, and arXiv 2212.12913's
    v2 kept three of v1's five authors. With the versions fetched, each is compared in turn;
    without them, an earlier title's authors are compared in any order (arXiv 2508.03341 put its
    second author first in v4).
    """
    if info.translated:
        record = _as_chinese_journal_record(record)
    title = check_title(info.title, record)
    discussed = _DISCUSSION_OF.match(info.title)
    if discussed and title_key(discussed["title"]) == title_key(record.title):
        # a comment on the work, printed with it under one DOI: Speed's comment on Robinson's
        # "That BLUP is a Good Thing" (Statistical Science 6(1), 10.1214/ss/1177011926; dev3)
        return FieldCheck("variant", 1.0, DISCUSSION_OF_RECORD), AuthorCheck("unknown")
    maker = _maker_in_title(info, record)
    if maker is not None:
        # the organisation the entry credits, named before the title: "OpenAI GPT-5 System
        # Card" (arXiv 2601.03267, with 486 people) is OpenAI's "GPT-5 System Card" (heldout16).
        # Who to credit for an organisation's own document is for the citing author to choose.
        return replace(check_title(info.title, maker), note=""), AuthorCheck("unknown")
    if title.note == EARLIER_VERSION and not record.versions:
        authors = check_authors(info.authors, replace(record, authors_ordered=False))
    else:
        authors = check_authors(info.authors, record)
    for version in record.versions:
        version_title = check_title(info.title, version)
        version_authors = check_authors(info.authors, version)
        if _fit(version_title, version_authors) <= _fit(title, authors):
            continue
        if version.title != record.title and version_title.status != "mismatch":
            version_title = replace(version_title, status="variant", note=EARLIER_VERSION)
        title, authors = version_title, version_authors
    return title, authors


def evaluate(info: EntryInfo, record: SourceRecord, *, preprint_pair: bool = False) -> Match:
    title, authors = _title_and_authors(info, record)
    year = check_year(info.year, record, preprint_pair=preprint_pair, venue=info.venue)
    venue = check_venue(
        info.venue, record, named=info.venue_field in NAMED_VENUE_FIELDS,
        journal=info.venue_field in {"journal", "journaltitle"}, issns=info.issns,
    )  # fmt: skip
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
    # a later edition of a book only when no record of the book the entry dates fits as well
    matches.sort(
        key=lambda m: (
            m.title.score or 0.0,
            not m.year.note.startswith(LATER_EDITION),
            m.authors.overlap,
        ),
        reverse=True,
    )
    best = matches[0]
    distinct = {m.record.title.lower() for m in matches if (m.title.score or 0) >= TITLE_SAME}
    if len(distinct) > 1 and (best.title.score or 0) < 1.0:
        return None  # ambiguous: several different works fit equally well — refuse to guess
    return best


def at_coordinates(info: EntryInfo, record: SourceRecord) -> bool:
    """The record is the article an untitled entry cites by journal, volume and page ("MNRAS
    249, 523", as astronomy and physics cite): the same volume and first page, and the same
    first author, the authors agreeing as a whole. There is no title to compare, so neither
    alone is enough: a volume and page may be misprinted, a first author has many papers."""
    if not (info.volume and info.first_page and record.volume):
        return False
    if record.volume.strip().lower() != info.volume.lower():
        return False
    if first_page(record.pages) != info.first_page:
        return False
    authors = check_authors(info.authors, record)
    return authors.first_author_match and authors.status in {"match", "variant"}
