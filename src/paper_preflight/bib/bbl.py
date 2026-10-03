"""Read a compiled bibliography (.bbl) when a project ships no .bib file.

A fifth of the arXiv sources sampled for the real-paper evaluation had no .bib, most of them a
.bbl. Three forms are read:

* biblatex's ``\\entry{key}{type}{}`` records, field by field (``\\field``, ``\\name``,
  ``\\verb`` for DOIs, eprints and URLs);
* ``\\bibinfo{field}{value}`` tags (elsarticle, revtex, apsrev), one per author;
* BibTeX's ``thebibliography`` with ``\\bibitem`` and ``\\newblock`` (plainnat, abbrvnat,
  unsrtnat and most styles): authors, then the title, then where and when, with the year, DOI,
  arXiv ID and URL picked from the rest. Styles without ``\\newblock`` (IEEEtran) give the title
  in quotes; physics styles often give none, and the item is then known by its identifiers.

Each item becomes a BibTeX entry, parsed like any other, whose locations point at the item's
line in the .bbl. The file is marked derived: fixes are never proposed against it.
"""

from __future__ import annotations

import re
from dataclasses import replace
from pathlib import Path

from paper_preflight.bib.parse import BibEntry, BibFile, BibIssue, parse_bib_text
from paper_preflight.textio import read_text

_BIBITEM = re.compile(
    r"\\bibitem\s*(?:\[(?P<label>(?:[^\[\]]|\[[^\]]*\])*)\])?\s*\{(?P<key>[^}]+)\}"
)
_ENTRY = re.compile(r"\\entry\{(?P<key>[^}]+)\}\{(?P<type>[^}]+)\}")
_FIELD = re.compile(
    r"\\field\{(?P<name>[^}]+)\}\{(?P<value>(?:[^{}]|\{(?:[^{}]|\{[^{}]*\})*\})*)\}"
)
_VERB = re.compile(r"\\verb\{(?P<name>[^}]+)\}\s*\n\s*\\verb (?P<value>.*?)\n\s*\\endverb", re.S)
_NAME_PART = re.compile(r"(?P<part>family|given)=\{(?P<value>(?:[^{}]|\{[^{}]*\})*)\}")
_BIBINFO = re.compile(r"\\bibinfo\s*\{(?P<name>[a-z]+)\}\s*")
_YEAR = re.compile(r"\b(1[89]\d\d|20\d\d)[a-z]?\b")
# \doi{...}, AAS's \dodoi{...}, "doi:", a doi.org link
_DOI = re.compile(r"(?:\\(?:do)?doi\{|doi:\s*|doi\.org/)(?P<doi>10\.\d{4,9}/[^\s},]+)", re.I)
_ARXIV = re.compile(r"arXiv[:\s]*(?P<id>\d{4}\.\d{4,5}|[a-z\-]+/\d{7})", re.I)
_URL = re.compile(r"\\url\{(?P<url>[^}]+)\}")
_HREF = re.compile(r"\\href\s*\{(?P<url>[^}]*)\}\s*")
_EMPH = re.compile(r"\\(?:emph|textit|textsl)\s*\{(?P<text>(?:[^{}]|\{[^{}]*\})*)\}")
_QUOTED = re.compile(r"``(?P<title>.+?)(?:,|\.)?''", re.S)
_IDENTIFIER_ONLY = re.compile(r"^\s*(\\doi\{|doi:|\\url\{|URL\b|https?://)", re.I)
_URL_TEXT = re.compile(r"https?://\S+\s*")
_NEWBLOCK = re.compile(r"\\newblock\b")
_TITLE_YEAR = re.compile(r",\s*(1[89]\d\d|20\d\d)[a-z]?\.?$")
_BIBINFO_FIELDS = {
    "title": "title", "journal": "journal", "booktitle": "booktitle", "year": "year",
    "doi": "doi", "eprint": "eprint", "url": "url",
}  # fmt: skip


def parse_bbl_file(path: Path) -> BibFile:
    try:
        source = read_text(path)
    except OSError as exc:
        result = BibFile(path=path, encoding="unknown", derived=True)
        result.issues.append(BibIssue("unreadable", path, 1, None, str(exc)))
        return result
    return parse_bbl_text(source.text, path, source.encoding)


def parse_bbl_text(text: str, path: Path, encoding: str = "utf-8") -> BibFile:
    items = _biblatex_items(text) if _ENTRY.search(text) else _bibitems(text)
    result = BibFile(path=path, encoding=encoding, derived=True)
    for line, entry_type, key, fields in items:
        body = ",\n".join(f"  {name} = {{{value}}}" for name, value in fields.items() if value)
        parsed = parse_bib_text(f"@{entry_type}{{{key},\n{body}\n}}\n", path, encoding)
        for entry in parsed.entries:
            result.entries.append(_at_line(entry, line))
    return result


def _at_line(entry: BibEntry, line: int) -> BibEntry:
    """The entry with every location at ``line`` of the .bbl."""
    fields = {name: replace(f, line=line) for name, f in entry.fields.items()}
    return replace(entry, fields=fields, line=line)


def _line_of(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def _braced(text: str, start: int) -> str:
    """The content of the brace group opening at or after ``start``."""
    open_at = text.find("{", start)
    if open_at < 0:
        return ""
    depth = 0
    for i in range(open_at, len(text)):
        escaped = text[i - 1] == "\\"
        if text[i] == "{" and not escaped:
            depth += 1
        elif text[i] == "}" and not escaped:
            depth -= 1
            if depth == 0:
                return text[open_at + 1 : i]
    return text[open_at + 1 :]


# ---------------------------------------------------------------- biblatex


def _biblatex_items(text: str) -> list[tuple[int, str, str, dict[str, str]]]:
    items = []
    for match in _ENTRY.finditer(text):
        end = text.find("\\endentry", match.end())
        block = text[match.end() : end if end >= 0 else len(text)]
        fields: dict[str, str] = {}
        for field in _FIELD.finditer(block):
            name = field["name"].lower()
            fields["journal" if name == "journaltitle" else name] = field["value"]
        for verb in _VERB.finditer(block):
            fields[verb["name"].lower()] = verb["value"].strip()
        authors = _biblatex_names(block, "author") or _biblatex_names(block, "editor")
        if authors:
            fields["author"] = authors
        if "year" not in fields and fields.get("date"):
            fields["year"] = fields["date"][:4]
        fields.pop("date", None)
        items.append((_line_of(text, match.start()), match["type"], match["key"], fields))
    return items


def _biblatex_names(block: str, role: str) -> str:
    start = block.find(f"\\name{{{role}}}")
    if start < 0:
        return ""
    end = block.find("\\list{", start)
    names = block[start : end if end > 0 else len(block)]
    people = []
    for chunk in re.split(r"\{\{(?:un=\d+,)?(?:uniquepart=\w+,)?hash=", names)[1:]:
        parts = {m["part"]: m["value"] for m in _NAME_PART.finditer(chunk)}
        if parts.get("family"):
            people.append(f"{parts['family']}, {parts.get('given', '')}".rstrip(", "))
    return " and ".join(people)


# ---------------------------------------------------------------- thebibliography


def _bibitems(text: str) -> list[tuple[int, str, str, dict[str, str]]]:
    end_list = text.find("\\end{thebibliography}")
    if end_list >= 0:
        text = text[:end_list]
    matches = list(_BIBITEM.finditer(text))
    items = []
    for i, match in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        fields, entry_type = _item_fields(text[match.end() : end], _first_family(match["label"]))
        items.append((_line_of(text, match.start()), entry_type, match["key"].strip(), fields))
    return items


def _first_family(label: str | None) -> str | None:
    """The first author's family name in a natbib label: "{Saad et~al.(2023)Saad, ...}"."""
    if not label:
        return None
    head = re.split(r"\s+et\s*~?\s*al|\(", label.strip("{} "), maxsplit=1)[0]
    head = re.sub(r"[{}]", "", head).replace("~", " ").strip()
    return head or None


def _item_fields(block: str, first_family: str | None = None) -> tuple[dict[str, str], str]:
    block = re.sub(r"\\penalty0\s*", "", block)
    block = re.sub(r"%\n\s*", "", block)
    tags: dict[str, list[str]] = {}
    for match in _BIBINFO.finditer(block):
        tags.setdefault(match["name"], []).append(_braced(block, match.end()))
    if tags.get("title") or tags.get("author"):
        fields = {name: tags[tag][0] for tag, name in _BIBINFO_FIELDS.items() if tags.get(tag)}
        fields["author"] = " and ".join(_authors(a) for a in tags.get("author", []))
        if "journal" in fields:
            entry_type = "article"
        else:
            entry_type = "inproceedings" if "booktitle" in fields else "misc"
        _identifiers(block, fields)
        return fields, entry_type

    fields = {}
    _identifiers(block, fields)  # before links are dropped: a DOI may be one
    block = _HREF.sub("", block)  # a link around the title: its text stays
    block = _NATEXLAB.sub(r"\g<letter>", block)  # "2023{\natexlab{b}}" is 2023b
    parts = [p for p in (" ".join(part.split()) for part in _NEWBLOCK.split(block)) if p]
    names_then_more = _split_names(parts[0]) if parts else ([], [])
    if names_then_more[0] and len(" ".join(names_then_more[1]).split()) >= 3:
        # Elsevier's numbered style with a \newblock for the link: "K. Simonyan, A. Zisserman,
        # Very deep convolutional networks ... (2015). \newblock \href{...}{arXiv:1409.1556}"
        numbered = _numbered(" ".join(parts), fields)
        if numbered is not None:
            years = _YEAR.findall(parts[0])
            if years:
                fields["year"] = years[-1]
            return fields, numbered
    if len(parts) >= 2 and not _IDENTIFIER_ONLY.match(parts[1]):
        authors, title, rest = parts[0], parts[1], " ".join(parts[2:])
    else:  # IEEEtran: authors, ``title,'' venue; physics styles: authors, journal, no title
        whole = " ".join(parts)
        quoted = _QUOTED.search(whole)
        lncs = _LNCS.match(whole)
        aas = _AAS.match(whole)
        if quoted is not None:
            authors, title = whole[: quoted.start()], quoted["title"]
            rest = whole[quoted.end() :]
        elif lncs is not None and _family_first(lncs["authors"]):
            # Springer LNCS: "Cao, J., Zhang, X.: Title. In: Venue. pp. 1--9 (2025)"
            authors, title, rest = lncs["authors"], lncs["title"], lncs["rest"]
        else:
            _identifiers(whole, fields)
            years = _YEAR.findall(whole)
            if years:
                fields["year"] = years[-1]
            if aas is not None and _family_first(aas["authors"]):
                # AAS: "{Belfiore}, F., {Vincenzo}, F., \& {Maiolino}, R. 2019, \mnras, 487"
                fields["author"], fields["year"] = _authors(aas["authors"]), aas["year"]
            else:
                numbered = _numbered(whole, fields)  # "B. Zoph, Q. V. Le, Title, in: ..., 2017"
                if numbered is not None:
                    return fields, numbered
                # "J.N. Ginocchio, A.S. de Castro, Phys. Rev. Lett. 78, 436 (1997)": no title
                fields["author"] = " and ".join(_leading_names(whole))
            return fields, "misc"
    fields["author"] = _authors(authors, first_family)
    year_in_title = _TITLE_YEAR.search(title)
    if year_in_title and not rest:  # "Smollm2: When smol goes big ..., 2025."
        title, rest = title[: year_in_title.start()], year_in_title.group(1)
    book = _EMPH.match(title)  # a title in italics is a book's: "\emph{The cross-entropy method}"
    if book:
        title = book["text"]
    fields["title"] = _URL_TEXT.sub("", title).strip().rstrip(".,").strip()
    _identifiers(block, fields)
    venue_text = re.split(r"\\newblock|\\doi\{|URL\s*\\url|ISBN", rest)[0]
    # a year right after the authors (APA, ACL, Chicago) is the year; pages may look like one
    after_authors = _PAREN_YEAR.search(authors.strip())
    years = (
        (_YEAR.findall(after_authors.group(0)) if after_authors else [])
        or _YEAR.findall(venue_text)
        or _YEAR.findall(rest)
    )
    if years:
        fields["year"] = years[-1]
    if book:
        return fields, "book"
    emph = _EMPH.search(venue_text)
    entry_type = "misc"
    if emph:
        venue = emph["text"].strip().rstrip(".,")
        if re.match(r"\s*In\b", venue_text):
            fields["booktitle"], entry_type = venue, "inproceedings"
        else:
            fields["journal"], entry_type = venue, "article"
    return fields, entry_type


_NATEXLAB = re.compile(r"\{\\natexlab\{(?P<letter>[a-z])\}\}")
_LNCS = re.compile(r"(?P<authors>[^:]+?):\s+(?P<title>.+?)\.\s+(?P<rest>(?:In:|[A-Z\d]|arXiv).*)$")
_AAS = re.compile(r"(?P<authors>.+?),?\s+(?P<year>(?:1[89]|20)\d\d)[a-z]?,\s")


def _family_first(text: str) -> bool:
    """Names written "Family, I." in pairs: "Cao, J., Zhang, X." or "{Belfiore}, F., \\& ..."."""
    parts = [p.strip() for p in re.split(r",\s*(?:\\?&\s*)?", text.replace("~", " ")) if p.strip()]
    parts = [p for p in parts if not re.fullmatch(r"\{?et al\.?\}?", p)]
    return len(parts) >= 2 and all(_INITIALS.fullmatch(p.strip("{} ")) for p in parts[1::2])


# "J.N. Ginocchio", "A.S. de Castro", "P. Alberto": initials, then a family name
_INITIALS_NAME = re.compile(
    r"(?:[A-Z][a-z]?\.\s*-?\s*)+(?:[a-z]+\s+)*[A-Z][\w'\-]+(?:\s+[A-Z][\w'\-]+)*"  # "C. De Sa"
)


def _leading_names(text: str) -> list[str]:
    """The names an item starts with, up to the first part that is no name."""
    return _split_names(text)[0]


def _split_names(text: str) -> tuple[list[str], list[str]]:
    """Leading "I. Family" names ("et al." as others), and the comma-separated parts after."""
    parts = [p.strip() for p in text.replace("~", " ").split(",")]
    names: list[str] = []
    for i, part in enumerate(parts):
        if re.fullmatch(r"et al\.?", part):
            names.append("others")
            return names, parts[i + 1 :]
        if not _INITIALS_NAME.fullmatch(part):
            return names, parts[i:]
        names.append(part)
    return names, []


_JOURNAL_LIKE = re.compile(r"\\textbf|^(?:[A-Z][a-z]{0,5}\.\s*){2,}")


_DATED_TITLE = re.compile(r"(?P<title>[^(]+?)\s*\((?:1[89]|20)\d\d[a-z]?\)")


def _numbered(whole: str, fields: dict[str, str]) -> str | None:
    """Elsevier's numbered style: "B. Zoph, Q. V. Le, Title, in: Venue, 2017." The title runs to
    "in:" or to the first part with a number in it (a volume, a year, an arXiv ID)."""
    names, parts = _split_names(whole)
    if not names or not parts:
        return None
    end = next(
        (
            i
            for i, p in enumerate(parts)
            if i and (p.lower().startswith("in:") or re.search(r"\d", p))
        ),
        None,
    )
    if end is None:
        # no comma before the year: "Very deep convolutional networks ... recognition (2015)."
        dated = _DATED_TITLE.match(", ".join(parts))
        if dated is None or len(dated["title"].split()) < 3:
            return None
        fields["author"], fields["title"] = " and ".join(names), dated["title"]
        return "misc"
    title = ", ".join(parts[:end]).strip()
    if len(title.split()) < 3 or _JOURNAL_LIKE.search(title):
        return None  # "Phys. Rev. Lett. \textbf{78}" is where, not what
    fields["author"], fields["title"] = " and ".join(names), title
    venue = parts[end]
    if venue.lower().startswith("in:"):
        fields["booktitle"] = venue[3:].strip()
        return "inproceedings"
    journal = re.split(r"\s+\d|\s*\(", venue)[0].strip()
    if journal and not journal.lower().startswith("arxiv"):
        fields["journal"] = journal
        return "article"
    return "misc"


def _identifiers(text: str, fields: dict[str, str]) -> None:
    """The DOI, arXiv ID and URL an item carries, unless already known."""
    doi = _DOI.search(text)
    if doi and "doi" not in fields:
        fields["doi"] = doi["doi"].rstrip(".")
    arxiv = _ARXIV.search(text)
    if arxiv and "eprint" not in fields:
        fields["eprint"], fields["archiveprefix"] = arxiv["id"], "arXiv"
    url = _URL.search(text)
    if url and "url" not in fields and "doi.org" not in url["url"]:
        fields["url"] = url["url"]


_INITIALS = re.compile(r"(?:[A-Z]\.\s*-?\s*)+")


def _authors(text: str, first_family: str | None = None) -> str:
    """ "A. Smith, B. Jones, and C. Lee." as BibTeX: "A. Smith and B. Jones and C. Lee".

    APA-like lists put the family name first ("Aycock, S., Stap, D., & Wu, D."): the pairs are
    kept together. ``first_family``, the first author's family name from the item's label, tells
    an inverted first author ("Saad, El Mehdi, Gilles Blanchard") from two people.
    """
    text = text.replace("~", " ").replace("\\&", "&").strip()
    # protective braces ("{Belfiore}", "{et al.}"), not a macro's argument ("\c{S}imek")
    text = re.sub(r"(?<![\\A-Za-z])\{([^{}\\]*)\}", r"\1", text)
    text = _PAREN_YEAR.sub("", text).strip().rstrip(",")  # APA: "... Wu, D. (2025)."
    text = re.sub(r"\bet al\b\.?", "and others", text)
    names = [n.strip() for n in re.split(r",\s*(?:and\s+|&\s*)?|\s+(?:and|&)\s+", text)]
    names = [n for n in names if n]
    truncated = names[-1:] == ["others"]
    people = names[:-1] if truncated else names
    if len(people) >= 2 and all(_INITIALS.fullmatch(n) for n in people[1::2]):
        names = [f"{people[i]}, {people[i + 1]}" for i in range(0, len(people) - 1, 2)]
        names += ["others"] if truncated else []
    elif _inverted_first(names) or (
        first_family is not None and len(names) >= 2 and names[0] == first_family
    ):
        # only the first author inverted: "Angelopoulos, Anastasios N., John C. Duchi, ...",
        # "Ochoa Rivera, Eduardo, Ambuj Tewari", "Bastani, Hamsa"
        names = [f"{names[0]}, {names[1]}", *names[2:]]
    # the period after the last name goes; an initial's stays
    return " and ".join(n[:-1] if _SENTENCE_END.search(n) else n for n in names)


def _inverted_first(names: list[str]) -> bool:
    """The first two parts are one person written "Family, Given": the given part is one word or
    ends in an initial ("Eduardo", "Robert E", "Anastasios N."), and everyone after is written
    "Given Family". "Peng Ye, Julian Qian" are two people."""
    if len(names) < 2 or _INITIALS.search(names[0]) or not all(" " in n for n in names[2:]):
        return False
    given = names[1].split()
    return len(given) == 1 or (len(given) <= 3 and bool(re.fullmatch(r"[A-Z]\.?", given[-1])))


# a year after the authors: APA "Wu, D. (2025).", ACL "John Schulman. 2021."
_PAREN_YEAR = re.compile(r"(?:\(\s*|[.,]\s+)(?:1[89]\d\d|20\d\d)[a-z]?\s*\)?\.?\s*$")
_SENTENCE_END = re.compile(r"[a-zà-ɏ']\.$")
