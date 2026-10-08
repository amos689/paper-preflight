"""Read a plain-text reference list: pasted from Word, a web page or a PDF.

The list is split into references (numbered "[1]" or "1.", or one per paragraph, or one per
line), and each reference is read in the common styles:

* a quoted title (IEEE, MLA, biblatex): authors, “Title,” venue, year;
* APA: authors (year). Title. Venue;
* the year after the authors (ACM, ACL, Chicago): authors. year. Title. Venue;
* authors. Title. Venue, year (natbib, many journals);
* Springer LNCS ("Family, I.: Title. In: ...") and Elsevier's numbered style ("I. Family,
  Title, in: ..."), as in compiled bibliographies.

Each reference becomes a BibTeX entry keyed ``ref1``, ``ref2``, ... at the reference's first
line. Reading a formatted reference is guesswork where BibTeX is not, so the file is marked
derived (never edited), and a reference whose title or authors cannot be told apart is checked
by its identifiers alone, or left undecided.
"""

from __future__ import annotations

import re
from dataclasses import replace
from itertools import pairwise
from pathlib import Path

from paper_preflight.bib import bbl
from paper_preflight.bib.normalize import deaccent
from paper_preflight.bib.parse import BibFile, BibIssue, parse_bib_text
from paper_preflight.textio import read_text

_NUMBERED = re.compile(r"^\s*(?:\[(\d{1,4})\]|(\d{1,4})[.)](?=\s)|\((\d{1,4})\))\s*")
_DOI = re.compile(
    r"\bdoi:\s*(?P<labelled>\S+?)[.,;]?(?=\s|$)|\b(?P<bare>10\.\d{4,9}/[^\s\"<>]+?)(?=[.,;)]?(?:\s|$))",
    re.I,
)
# "arXiv:2402.03563", "arXiv preprint arXiv:2305.XXXX" (an ID never filled in), "arXiv, 1610.02424"
_ARXIV = re.compile(
    r"(?:\barXiv\b[\s:,]*(?:preprint\s+)?(?:arXiv:\s*)?|arxiv\.org/(?:abs|pdf)/)"
    r"(?P<id>\d{4}\.[\dX]{4,5}(?:v\d+)?|[a-z\-]+(?:\.[A-Z]{2})?/\d{7})",
    re.I,
)
_URL = re.compile(r"https?://\S+")
# "URL https://...", "doi: 10...", "Available from: https://..." and what they introduce
_LINK = re.compile(
    r"(?:\b(?:url|doi|available(?:\s+(?:at|from))?|retrieved\s+from)\s*:?\s*)?"
    r"<?(?:https?://\S+|\b10\.\d{4,9}/\S+)",  # "<https://doi.org/...>", as \url prints
    re.I,
)
# when the reader looked a page up, not when the work appeared
_VISITED = re.compile(
    r"\((?:visited|accessed|retrieved)\b[^)]*\)?|\b(?:accessed|retrieved|visited)(?:\s+on)?:?\s+"
    r"[\w ,./-]*\d{4}",
    re.I,
)
_NUMBERS = re.compile(r"\b(?:issn|isbn|e?issn)\s*:?\s*[\dXx-]{8,}", re.I)  # no year in them
_QUOTES = re.compile(r"[“\"](?P<title>[^”\"]{8,}?)[,.]?[”\"]")
_YEAR = re.compile(r"\b(1[89]\d\d|20\d\d)[a-z]?\b")
_APA = re.compile(
    r"^(?P<authors>.+?)\s*\((?P<year>(?:1[89]|20)\d\d)[a-z]?(?:,[^)]*)?\)\.?\s*(?P<rest>.*)$"
)
_DATED = re.compile(r"[.,]?\s*\(?(?P<year>(?:1[89]|20)\d\d)[a-z]?\)?$")
_YEAR_AFTER = re.compile(
    r"^(?P<authors>.+?)\.\s+(?P<year>(?:1[89]|20)\d\d)[a-z]?\.\s+(?P<rest>.+)$"
)
# A sentence ends at ". " unless the word before is an initial ("Daniel S. Weld"); it always ends
# after "et al.", and at a missing space between two words ("Andrew Y. Ng.Dynamic pooling").
_SENTENCE = re.compile(
    r"(?<!\b[A-Z])(?<!\bSt)(?<!\bJr)\.\s+(?=[A-Z0-9“\"(]|arXiv|pp?\.\s*\d)|(?<=\bal)\.\s+"
    r"|(?<=[a-z])\.(?=[A-Z][a-z])"
)
# a title that asks runs into its venue: "Can machine learning improve delta hedging? Journal of
# Derivatives, 9(1)"; a "?" inside names is a lost letter ("Kamile? Luko?iut?e")
_ASKING_TITLE = re.compile(r"^(?P<title>.{8,}?[a-z][?!])\s+(?P<venue>[A-Z].*)$")
_VOLUME = re.compile(r"\d+\s*\(\d+\)|,\s*\d")  # "9(1)", ", 12"
_BROKEN_HOST = re.compile(r"\b((?:arxiv|doi)\.org/)\s+(?=\S)", re.I)
_SECOND_NUMBER = re.compile(r"^\[\d{1,4}\]\s*")
_TITLE_YEAR = re.compile(r"^(?P<title>.{8,}?)(?:,\s*|\s+\()(?P<year>(?:1[89]|20)\d\d)[a-z]?\)?$")
# a venue may start with its edition or year: "37th International Conference ...", "2009 IEEE ..."
_EDITION = re.compile(r"^(?:\d+(?:st|nd|rd|th)|(?:1[89]|20)\d\d)\s+(?=[A-Z])")
_IN = re.compile(r"^In(?::|\s)\s*", re.I)
_EDITORS = re.compile(r"^.*?\((?:eds?|editors?)\.?\),?\s*", re.I)
_LANGUAGE = re.compile(r"^[a-z]{2}\.\s+")  # biblatex's "langid": ". en. In: ..."
_MEETING = re.compile(
    r"\b(?:Proc\.|Proceedings|Conference|Workshop|Symposium|Meeting|Congress|Colloquium)\b", re.I
)
_REPORT = re.compile(r"\btech(?:nical)?\.?\s*rep(?:ort)?\b|\bworking\s+paper\b", re.I)
_JOURNAL = re.compile(r"\b(?:Journal|Transactions|Letters|Review|Magazine|Annals)\b", re.I)
_PREPRINT = re.compile(r"^(?:arXiv|CoRR|bioRxiv|medRxiv|SSRN|Preprint|preprint)\b")
# a name: capitalised words, a few lower-case particles, initials
_NAME_WORD = r"(?:[A-Z][\w'’\-.?@]*|(?:van|von|de|der|den|del|della|di|da|du|la|le|dos|bin|al)\b)"
_PERSON = re.compile(rf"{_NAME_WORD}(?:\s*{_NAME_WORD}){{0,5}}\.?")
# a name with one or two short lower-case words after its first (see _looks_like_names)
_LOOSE_PERSON = re.compile(rf"{_NAME_WORD}(?:\s+(?:{_NAME_WORD}|[a-z]{{2,8}})){{1,4}}\.?")
_FUNCTION_WORDS = frozenset(
    "a an the of on in for to at by and or with from via into is are as its".split()
)
_ET_AL = re.compile(r",?\s*(?:and\s+)?et\.?\s+al\.?$")
# Nature, LNCS: "Smith, J. A., Lee, K. & Wu, X." and what follows
_FAMILY_INITIALS = re.compile(
    r"\s*(?:,\s*)?(?:&|and)?\s*"
    r"(?P<family>(?:(?:van|von|de|der|den|del|della|di|da|du|la|le|dos)\s+)*[A-Z][^,.&():]*?),"
    r"\s+(?P<initials>(?:[A-Z][a-z]?\.\s?-?\s?)+)"
)
# Vancouver: "Smith JA, Lee K, et al." and what follows
_VANCOUVER_NAME = r"[A-Z][\w'’\-]*(?:\s+(?:[a-z]+\s+)*[A-Z][\w'’\-]+)*\s+[A-Z]{1,3}"
_VANCOUVER = re.compile(
    rf"(?P<authors>(?:{_VANCOUVER_NAME},\s+)*(?:{_VANCOUVER_NAME}|et\s+al)\.)\s+(?P<rest>.+)$"
)


def parse_plaintext_file(path: Path) -> BibFile:
    try:
        source = read_text(path)
    except OSError as exc:
        result = BibFile(path=path, encoding="unknown", derived=True)
        result.issues.append(BibIssue("unreadable", path, 1, None, str(exc)))
        return result
    return parse_plaintext(source.text, path, source.encoding)


def parse_plaintext(
    text: str, path: Path, encoding: str = "utf-8", *, wrapped: bool = False
) -> BibFile:
    """``wrapped``: the lines are wrapped as on a page (a PDF), not one reference per line."""
    result = BibFile(path=path, encoding=encoding, derived=True)
    authors = ""
    for number, (line, reference) in enumerate(split_references(text, wrapped), start=1):
        ditto = _DITTO.match(reference)
        if ditto and authors:  # "———, Title" or ", Title": the authors of the reference before
            entry_type, fields = parse_reference("A. Ditto, " + reference[ditto.end() :])
            fields["author"] = authors
        else:
            entry_type, fields = parse_reference(reference)
        authors = fields.get("author", "")
        body = ",\n".join(f"  {k} = {{{_escape(k, v)}}}" for k, v in fields.items() if v)
        parsed = parse_bib_text(f"@{entry_type}{{ref{number},\n{body}\n}}\n", path, encoding)
        for entry in parsed.entries:
            fields_at = {name: replace(f, line=line) for name, f in entry.fields.items()}
            result.entries.append(replace(entry, fields=fields_at, line=line))
    return result


_DITTO = re.compile(r"\s*(?:[—–_-]{2,}\.?,?|,)\s*")  # the same authors as the reference before
_IDENTIFIER_FIELDS = frozenset({"doi", "eprint", "url"})


def _escape(name: str, value: str) -> str:
    """Plain text as a BibTeX value: braces balanced, LaTeX's special characters escaped, except
    in identifiers, which are read as written (``10.26615/978-954-452-056-4_083``)."""
    value = value.replace("\\", " ").replace("{", "(").replace("}", ")")
    return value if name in _IDENTIFIER_FIELDS else re.sub(r"([&%#_$])", r"\\\1", value)


def split_references(text: str, wrapped: bool = False) -> list[tuple[int, str]]:
    """(first line, reference) for each reference in the list."""
    lines = text.splitlines()
    numbered = _numbered_starts(lines)
    if len(numbered) >= 2:
        starts = numbered
    elif any(not line.strip() for line in lines) and not wrapped:
        starts = [
            i
            for i, line in enumerate(lines)
            if line.strip() and (i == 0 or not lines[i - 1].strip())
        ]
    else:
        starts = _unmarked_starts(lines, wrapped)
    references = []
    for n, start in enumerate(starts):
        end = starts[n + 1] if n + 1 < len(starts) else len(lines)
        joined = _join(lines[start:end])
        joined = _NUMBERED.sub("", joined, count=1).strip()
        if joined:
            # a word broken at the end of a line: "lan- guage"
            references.append((start + 1, re.sub(r"(?<=[a-z])-\s+(?=[a-z])", "", joined)))
    return references


# a DOI or URL broken at the end of a line ("10.18653/v1/2025.emnlp-main." then "661.")
_BROKEN_LINK = re.compile(r"(?:\b10\.\d{4,9}/|https?://)\S*[./_\-]$")


def _join(lines: list[str]) -> str:
    """A reference's lines as one line; a DOI or URL broken across lines is put back whole."""
    text = ""
    for line in (line.strip() for line in lines):
        if not line:
            continue
        if text and _BROKEN_LINK.search(text) and re.match(r"[a-z0-9]", line):
            text += line
        else:
            text = f"{text} {line}" if text else line
    return text


# three lower-case words in a row: a title's, never a list of names ("van der Berg" is two)
_LOWER_RUN = re.compile(r"(?:\b[a-z][\w-]*[\s,]+){3}")


# a journal and its volume where a style prints no title: "ApJ, 795(1):30", "MNRAS, 500, 4749"
_VENUE_NOT_TITLE = re.compile(r"^[A-Z][\w.&\s]{0,60}?,\s*[A-Z]?\d+(?:\(\d+\))?(?:[:,]|$)")
# AAS (ApJ, AJ, MNRAS, A&A): "Abbott, B. P., Abbott, R., et al. 2017, ApJL, 848, L12"
_AAS = re.compile(
    r"^(?P<authors>.+?),?\s+(?P<year>(?:1[89]|20)\d\d)[a-z]?,\s+"
    r"(?P<journal>[A-Za-z&][\w&.\s]{0,40}?),\s+(?P<volume>[A-Z]?\d+)(?:,\s+(?P<pages>[A-Z]?\d+))?"
)


def _aas(text: str) -> tuple[str, dict[str, str]] | None:
    """AAS: authors, year, journal, volume, page; no title, so the DOI or the authors and year
    tell the work."""
    match = _AAS.match(text)
    if match is None or _LOWER_RUN.search(match["authors"]):
        return None
    if not _APA_INITIALS.search(match["authors"]):
        return None
    fields = {
        "author": _apa_authors(match["authors"]),
        "year": match["year"],
        "journal": match["journal"],
        "volume": match["volume"],
        "pages": match["pages"] or "",
    }
    return "article", fields


def _numbered_starts(lines: list[str]) -> list[int]:
    """Lines numbered 1, 2, 3 ... in order; a wrapped line that starts "2025. emnlp-main" is no
    reference's number."""
    starts: list[int] = []
    for i, line in enumerate(lines):
        match = _NUMBERED.match(line)
        number = int(next(g for g in match.groups() if g)) if match else None
        if number is not None and number == len(starts) + 1:
            starts.append(i)
    return starts


_ENDS_REFERENCE = re.compile(r"[.)\]]$|\d$|://\S+$")
_ENDS_ABBREVIATION = re.compile(r"(?:\b[A-Z]|\bal|\bpp|\bvol|\bno|\bProc|\beds?|\bIn)\.$")


# A line that starts a reference: its authors ("Carlini, N.,", "H.-J. Bae and", "Ashish Vaswani,")
_AUTHOR_START = re.compile(
    r"(?!(?:In|Proc|Proceedings|Journal|Advances|Conference|International|Transactions|Annual|"
    r"Workshop|IEEE|ACM|Springer|URL|Available|Preprint|Technical)\b)"
    r"(?:[A-Z][\w'’\-]+(?:\s(?:van|von|de|der|den|da|di|du|le|la|del)\s[\w'’\-]+)?,\s+[A-Z]"
    r"|(?:[A-Z]\.[\s-]?)+\s?(?:(?:van|von|de|del|der|den|da|di|du|le|la)\s)?[A-Z][\w'’\-]+"
    r"|[A-Z][a-z]+(?:\s[A-Z][a-z]*\.?)*\s(?:(?:van|von|de|der|da|di|du|le|la)\s)?[A-Z][\w'’\-]+"
    r"(?:,|\sand\s|\set\sal))"
)


def _unmarked_starts(lines: list[str], wrapped: bool = False) -> list[int]:
    """Where references start in a list with no numbers and no blank lines: on every line when
    most lines end one (one reference per line), else after a line ending one, at a line that
    starts with names (lines wrapped as on a page)."""
    filled = [i for i, line in enumerate(lines) if line.strip()]
    ended = [i for i in filled if _ENDS_REFERENCE.search(lines[i].rstrip())]
    if not wrapped and len(ended) >= 0.6 * len(filled):
        return filled
    starts = filled[:1]
    for before, here in pairwise(filled):
        last = lines[before].rstrip()
        if (
            _ENDS_REFERENCE.search(last)
            and not _ENDS_ABBREVIATION.search(last)
            and _AUTHOR_START.match(lines[here].lstrip())
        ):
            starts.append(here)
    return starts


def parse_reference(text: str) -> tuple[str, dict[str, str]]:
    """The entry type and fields of one formatted reference."""
    fields: dict[str, str] = {}
    text = _BROKEN_HOST.sub(r"\1", text)  # "https://arxiv.org/ abs/2501.17727", from a PDF
    _identifiers(text, fields)
    plain = _VISITED.sub("", _NUMBERS.sub("", _LINK.sub("", text)))
    plain = re.sub(r"\s+", " ", plain.replace("$", "")).strip(" .,;")  # "$9(1): 39-56,2001$"
    plain = _SECOND_NUMBER.sub("", plain)  # "[3] K. Arnold, ...", numbered twice
    entry_type = "misc"
    readers = (_quoted, _apa, _aas, _family_initials, _vancouver, _year_after, _sentences)
    for read in (*readers, _numbered):
        found = read(plain)
        if found is not None and (found[1].get("title") or read is _aas):
            entry_type, read_fields = found
            title = read_fields.get("title", "")
            if _VENUE_NOT_TITLE.match(title):  # "ApJ, 795(1):30": a style without titles
                read_fields["journal"] = read_fields.pop("title").split(",")[0]
            for key, value in read_fields.items():
                value = value.strip(" ,;")
                if value and key not in fields:
                    fields[key] = value
            break
    asking = _ASKING_TITLE.match(fields.get("title", ""))
    if asking and not {"journal", "booktitle"} & set(fields):
        venue_type, venue = _venue(asking["venue"])
        name = venue.get("journal") or venue.get("booktitle") or ""
        if (
            venue_type in {"article", "inproceedings"}  # and no subtitle: "Matter? Identifiability"
            and (_JOURNAL.search(name) or _MEETING.search(name) or _VOLUME.search(asking["venue"]))
        ):
            entry_type, fields["title"] = venue_type, asking["title"]
            fields.update(venue)
    dated = _TITLE_YEAR.match(fields.get("title", ""))  # "Title, 2025. URL ...": no venue
    if dated:
        fields["title"] = dated["title"]
        fields.setdefault("year", dated["year"])
    if "year" not in fields:
        years = _YEAR.findall(plain)
        if years:
            fields["year"] = years[-1]
    return entry_type, fields


def _identifiers(text: str, fields: dict[str, str]) -> None:
    doi = _DOI.search(text)
    if doi:
        fields["doi"] = (doi["labelled"] or doi["bare"]).rstrip(".")
    arxiv = _ARXIV.search(text)
    if arxiv:
        fields["eprint"], fields["archiveprefix"] = arxiv["id"], "arXiv"
    url = _URL.search(text)
    if url and not re.search(r"doi\.org|arxiv\.org", url.group(0)):
        fields["url"] = url.group(0).rstrip(".,;")


def _venue(rest: str) -> tuple[str, dict[str, str]]:
    """What follows the title: "In Proceedings of X, pages 1-9, 2020" or "Journal 12(3), 4-5"."""
    rest = _LANGUAGE.sub("", rest.strip().lstrip(".,").strip())
    if not rest:
        return "misc", {}
    if _PREPRINT.match(rest):
        return "misc", {"journal": re.split(r"[,(]|\s+(?:arXiv|abs)?:?\d", rest)[0].strip(" .")}
    booktitle = _IN.match(rest)
    if booktitle:
        rest = _EDITORS.sub("", rest[booktitle.end() :])
        if _PREPRINT.match(rest):  # "In arXiv preprint arXiv:2205.05407"
            return _venue(rest)
    venue = _venue_name(rest)
    if venue is None:
        return "misc", {}
    if _REPORT.search(venue):  # "University of Chicago, Dept. of Statistics, Tech. Rep"
        return "techreport", {"institution": venue}
    volume = re.match(r"\s*\d+(?:\.\d+)?\s*[(,:]", rest[rest.find(venue) + len(venue) :])
    if _MEETING.search(venue) or (booktitle and volume is None and not _JOURNAL.search(venue)):
        return "inproceedings", {"booktitle": venue}
    return "article", {"journal": venue}


def _venue_name(text: str) -> str | None:
    """A venue's name: up to its volume, pages, year or publisher. Abbreviated words
    ("Mech. Transl. Comput. Linguistics") keep their periods."""
    end = len(text)
    for stop in re.finditer(
        r",\s*(?:\d|pp?\.|pages|vol\b|volume|no\.|[A-Z][a-z]+\.?\s+\d)|\s+\d+(?:\.\d+)?\s*(?:[(,:]|$)"
        r"|\s*\((?![A-Z][\w&@-]{1,15}\))|\.\s+(?:Publisher|ISSN|ISBN|Ed\.|Eds\.|Edited)\b"
        r"|[.,]?\s+(?:1[89]|20)\d\d(?=[;.,)]|\s*$)",  # Vancouver: "J Mach Learn Res. 2020;21:1-9"
        text,
        re.I,
    ):
        end = stop.start()
        break
    for period in re.finditer(r"\.\s+", text[:end]):
        word = re.search(r"(\S+)$", text[: period.start()])
        if word and not re.fullmatch(r"[A-Z][a-z]{0,5}", word.group(1)):
            end = period.start()  # a sentence ends, not an abbreviation
            break
    name = text[:end].strip(" .,;:")
    if len(re.findall(r"[A-Za-z]{3,}", name)) == 0 or not _EDITION.sub("", name)[:1].isupper():
        return None
    if _YEAR.fullmatch(name) or len(name.split()) > 20:
        return None
    return name


def _people(authors: str) -> str:
    return bbl._authors(re.sub(r"\band\s+(?=et\.?\s+al\b)", "", authors))  # "Nuo Lou and et al."


def _quoted(text: str) -> tuple[str, dict[str, str]] | None:
    """IEEE, MLA, biblatex: A. Smith and B. Lee, “Title,” in Proc. X, 2020."""
    match = _QUOTES.search(text)
    if match is None or match.start() == 0:
        return None
    authors = text[: match.start()].strip(" ,.")
    year = _DATED.search(authors)  # Chicago: Smith, Ann, and Bob Lee. 2020. “Title.”
    authors = authors[: year.start()] if year else authors
    if not _looks_like_names(authors):
        return None
    entry_type, fields = _venue(text[match.end() :])
    fields.update(author=_people(authors), title=match["title"].strip(" ,."))
    if year:
        fields["year"] = year["year"]
    return entry_type, fields


def _apa(text: str) -> tuple[str, dict[str, str]] | None:
    """APA: Smith, J., & Lee, K. (2020). Title. Journal, 1(2), 3-4."""
    match = _APA.match(text)
    if match is None or _LOWER_RUN.search(match["authors"]):
        return None  # a title's words before a year in parentheses: another style
    if not match["rest"]:  # no authors: "Title (2024)."; not Nature's "... 436 (2015)."
        if len(_SENTENCE.split(match["authors"])) > 1 or _AUTHOR_START.match(match["authors"]):
            return None
        return "misc", {"title": match["authors"], "year": match["year"]}
    sentences = _SENTENCE.split(match["rest"], maxsplit=1)
    entry_type, fields = _venue(sentences[1] if len(sentences) > 1 else "")
    authors = re.sub(r"(?<=\w\w)\.$", "", match["authors"])  # "CiteX. (2026)", not "Wu, D."
    fields.update(author=_apa_authors(authors), title=sentences[0], year=match["year"])
    return entry_type, fields


_APA_INITIALS = re.compile(r"(?:[A-Z][a-z]?\.\s?-?\s?)+")
_APA_OTHERS = re.compile(r"…|\.\.\.|et\.?\s*al\.?|al\.?|et\.?")


def _apa_authors(text: str) -> str:
    """APA's "Family, I." pairs, with a group first ("Gemma, Kamath, A., ...") and APA 7's
    ellipsis before the last of more than twenty authors ("..., Chang, C., … Zhao, S.")."""
    people: list[str] = []
    others = False
    for part in re.split(r",\s*(?:&\s*)?|\s+&\s+", text):
        part = part.strip().removeprefix("&").strip()
        ellipsis = re.match(r"(?:…|\.\.\.)\s*", part)
        if ellipsis:
            others, part = True, part[ellipsis.end() :]
        if not part:
            continue
        if _APA_OTHERS.fullmatch(part):
            others = True
        elif _APA_INITIALS.fullmatch(part) and people and "," not in people[-1]:
            people[-1] = f"{people[-1]}, {part.strip()}"
        else:
            people.append(part)
    return " and ".join(people + (["others"] if others else []))


def _year_after(text: str) -> tuple[str, dict[str, str]] | None:
    """ACM, ACL: Ann Smith and Bob Lee. 2020. Title. In Proceedings of X."""
    match = _YEAR_AFTER.match(text)
    if match is None or not _looks_like_names(match["authors"]):
        return None
    sentences = _SENTENCE.split(match["rest"], maxsplit=1)
    entry_type, fields = _venue(sentences[1] if len(sentences) > 1 else "")
    fields.update(author=_people(match["authors"]), title=sentences[0], year=match["year"])
    return entry_type, fields


def _sentences(text: str) -> tuple[str, dict[str, str]] | None:
    """natbib and many journals: Authors. Title. Venue, year."""
    sentences = _SENTENCE.split(text, maxsplit=2)
    if len(sentences) < 2 or not _looks_like_names(sentences[0]):
        return None
    entry_type, fields = _venue(sentences[2] if len(sentences) > 2 else "")
    fields.update(author=_people(sentences[0]), title=sentences[1])
    return entry_type, fields


def _family_initials(text: str) -> tuple[str, dict[str, str]] | None:
    """Nature, LNCS: Smith, J. A. & Lee, K. Title. Nature 1, 2-3 (2020)."""
    names, position = [], 0
    while (name := _FAMILY_INITIALS.match(text, position)) is not None:
        names.append(f"{name['family'].strip()}, {name['initials'].strip()}")
        position = name.end()
    rest = text[position:].lstrip(" ,:")
    et_al = re.match(r"(?:&\s*)?et\.?\s+al\.?\s*", rest)
    if et_al:
        names.append("others")
        rest = rest[et_al.end() :]
    if not names or not re.match(r"[^\d(]", rest):
        return None
    return _title_then_venue(rest, " and ".join(names))


def _vancouver(text: str) -> tuple[str, dict[str, str]] | None:
    """Vancouver: Smith JA, Lee K, et al. Title. J Mach Learn Res. 2020;21(3):1-9."""
    match = _VANCOUVER.match(text)
    if match is None or _looks_like_names(_SENTENCE.split(match["rest"], maxsplit=1)[0]):
        return None  # "Alexandros N. Angelopoulos, Stephen Bates, ...": given names first
    names = []
    for part in re.split(r",\s+", match["authors"].strip(" .")):
        if re.fullmatch(r"et\s+al", part.removesuffix(".")):
            names.append("others")
            continue
        family, initials = part.rsplit(" ", 1)
        names.append(f"{family}, {' '.join(f'{c}.' for c in initials)}")
    return _title_then_venue(match["rest"], " and ".join(names))


def _title_then_venue(rest: str, authors: str) -> tuple[str, dict[str, str]]:
    sentences = _SENTENCE.split(rest, maxsplit=2)
    title = sentences[0]
    if (
        len(sentences) == 3
        and _SECOND_TITLE_SENTENCE.fullmatch(sentences[1].strip())
        and _VENUE_WITH_VOLUME.match(sentences[2])
    ):
        # "Topological torsion: a new molecular descriptor for SAR applications. Comparison
        # with other descriptors. Journal of Chemical Information ... 27, 82-85 (1987)"
        title = f"{title}. {sentences[1].strip()}"
        sentences = [title, sentences[2]]
    venue = sentences[1] if len(sentences) == 2 else ". ".join(sentences[1:])
    entry_type, fields = _venue(venue if len(sentences) > 1 else "")
    fields.update(author=authors, title=title)
    return entry_type, fields


# A sentence that may still be the title's: words, no digits, nothing a venue starts with
_SECOND_TITLE_SENTENCE = re.compile(
    r"(?!In\b|Proc|arXiv|CoRR|Preprint|Technical|Tech\.)[A-Z][^\d.:;]{2,80}"
)
# what a journal reference looks like: a capitalised name, then its volume ("Nature 624, 570")
_VENUE_WITH_VOLUME = re.compile(r"[A-Z][^.\d]{2,120}?\s\d+(?:\s*\(\d+\))?\s*[,:]")


def _numbered(text: str) -> tuple[str, dict[str, str]] | None:
    """Elsevier's numbered style: B. Zoph, Q. V. Le, Title, in: Venue, 2017."""
    fields: dict[str, str] = {}
    entry_type = bbl._numbered(text, fields)
    return (entry_type, fields) if entry_type is not None else None


def _loose_person(part: str) -> bool:
    """A capitalised name with one or two short lower-case words: "Yun chen Chen". Never a
    word of a phrase ("Proceedings on", Badalova & Mayr's P3R30)."""
    lower = [w for w in part.split() if re.fullmatch(r"[a-z]+", w)]
    return (
        bool(_LOOSE_PERSON.fullmatch(part))
        and len(lower) <= 2
        and not any(w in _FUNCTION_WORDS for w in lower)
    )


def _looks_like_names(text: str) -> bool:
    """A list of people or one organisation: capitalised names joined by commas, "and", "&"."""
    text = deaccent(_ET_AL.sub("", text.strip()))  # "Étienne Pardoux"
    parts = [p.strip() for p in re.split(r",|\band\b|&", text) if p.strip()]
    if not parts or len(text) > 3000:
        return False
    names = [bool(_PERSON.fullmatch(p)) or p == "others" for p in parts]
    # a name with a lower-case part, as PDFs and generated lists write them ("Yun chen Chen",
    # "Oded teht sun"): among many proper names only, for a title may read like one
    loose = sum(not n and _loose_person(p) for n, p in zip(names, parts, strict=True))
    # a long list may hold a name a PDF mangled ("Anton V orontsov", "Christopher R ́e")
    odd = len(parts) - sum(names) - loose
    return odd <= len(parts) // 8 and (loose == 0 or sum(names) >= max(3, 3 * loose))
