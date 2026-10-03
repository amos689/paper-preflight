"""The normalised record every source adapter produces."""

from __future__ import annotations

import html
import re
from dataclasses import dataclass, field

_HOMONYM_SUFFIX_RE = re.compile(r"\s+\d{4}$")  # dblp: "Jian Sun 0001"
_SUFFIXES = {"jr", "jr.", "sr", "sr.", "ii", "iii", "iv"}


def collapse(text: str) -> str:
    return " ".join(text.split())


_TAG_RE = re.compile(r"<[^<>]+>")
# Markup tags by name, for text where a bare "<" may be a less-than sign: JATS and MathML from
# registries, ADS's <ASTROBJ> in exported BibTeX.
MARKUP_TAG_RE = re.compile(
    r"</?(?:title|i|b|em|strong|sub|sup|scp|sc|italic|bold|tt|u|inline-formula|named-content|"
    r"astrobj|(?:mml|jats):[\w-]+)(?:\s[^<>]*)?/?>",
    re.IGNORECASE,
)
# A whole LaTeX document around one formula, as some Crossref titles carry it (10.1086/308445:
# "\documentclass{aastex} ... \begin{document} \landscape $z=0.33$ \end{document}").
_EMBEDDED_DOCUMENT_RE = re.compile(
    r"\\documentclass.*?\\begin\{document\}(.*?)\\end\{document\}", re.DOTALL
)


def plain_title(text: str) -> str:
    r"""A title without the markup registries keep in it: HTML and MathML tags, entities, and TeX
    math. A HALLMARK VALID entry was flagged because Crossref's title was
    "$${{\mathrm {Latent}}Out}$$: an unsupervised deep anomaly detection approach ...".
    """
    # tags may also arrive escaped ("&lt;title&gt;HIRES ...&lt;/title&gt;", 10.1117/12.176725)
    text = MARKUP_TAG_RE.sub("", html.unescape(_TAG_RE.sub("", text)))
    text = _EMBEDDED_DOCUMENT_RE.sub(r" \1 ", text)
    if "$" in text or "\\" in text:
        from paper_preflight.bib.parse import latex_to_text

        text = latex_to_text(text)
    return collapse(text)


@dataclass(frozen=True)
class Person:
    family: str
    given: str = ""
    literal: str = ""  # organisation or unsplittable name

    @classmethod
    def from_parts(cls, given: str | None, family: str | None) -> Person:
        return cls(family=collapse(family or ""), given=collapse(given or ""))

    @classmethod
    def from_display(cls, name: str) -> Person:
        """Split "Given Family" or "Family, Given" display names (dblp, arXiv, OpenAlex raw)."""
        name = _HOMONYM_SUFFIX_RE.sub("", collapse(name))
        if not name:
            return cls(family="")
        if "," in name:
            family, given = name.split(",", 1)
            return cls(family=family.strip(), given=given.strip())
        parts = name.split(" ")
        while len(parts) > 1 and parts[-1].lower().strip(",") in _SUFFIXES:
            parts.pop()
        if len(parts) == 1:
            return cls(family=parts[0])
        return cls(family=parts[-1], given=" ".join(parts[:-1]))

    @property
    def display(self) -> str:
        if self.literal:
            return self.literal
        return f"{self.given} {self.family}".strip()


@dataclass(frozen=True)
class SourceRecord:
    """One candidate work as described by one source."""

    source: str
    source_id: str
    title: str
    authors: tuple[Person, ...] = ()
    authors_complete: bool = True  # False when the source truncates author lists
    authors_ordered: bool = True  # False when the source does not keep author order
    year: int | None = None
    years: frozenset[int] = frozenset()  # every registered year (online, print, versions)
    venue: str | None = None
    work_type: str | None = None
    identifiers: dict[str, str] = field(default_factory=dict, hash=False, compare=False)
    alt_titles: tuple[str, ...] = ()  # e.g. earlier arXiv version titles
    # retracted / partial_retraction / expression_of_concern / correction / withdrawn
    status: frozenset[str] = frozenset()
    # provenance of each status flag, e.g. "crossref:retraction-watch:<notice doi>"
    status_sources: tuple[str, ...] = ()
    relations: dict[str, tuple[str, ...]] = field(default_factory=dict, hash=False, compare=False)
    volume: str | None = None
    issue: str | None = None
    pages: str | None = None
    publisher: str | None = None
    url: str | None = None

    @property
    def all_years(self) -> frozenset[int]:
        return self.years | ({self.year} if self.year else set())

    @property
    def doi(self) -> str | None:
        return self.identifiers.get("doi")
