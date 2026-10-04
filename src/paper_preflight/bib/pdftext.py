"""Read the reference list of a PDF: its text, from the "References" heading (or the first "[1]"
when there is none, as in APS journals) to the end or to an appendix, read as a plain-text list
(paper_preflight.bib.plaintext).

Needs the ``pdf`` extra (pypdf). Text comes out of a PDF in reading order for most papers
typeset with LaTeX or Word, two columns included. What the extraction loses is put back where
its place is clear: ligatures ("ﬁ"), the space after a comma or a period at a change of font
("Moraga,Optimal", "Woo.ApJ", "InThe"), an initial's period set apart ("Y ."). Running headers
and page numbers are dropped. A scanned PDF has no text to read.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from collections import Counter
from dataclasses import replace
from pathlib import Path

from paper_preflight.bib.parse import BibFile, BibIssue
from paper_preflight.bib.plaintext import parse_plaintext

# "References", "REFERENCES", "7 References", "R EFERENCES" (small capitals), "Bibliography"
_HEADING_WORDS = frozenset(
    {"references", "reference", "referencesandnotes", "bibliography", "literaturecited",
     "workscited", "citedliterature", "参考文献"}
)  # fmt: skip
# where the list ends: an appendix, supplementary material, a checklist
_AFTER = re.compile(
    r"^\s*(?:[A-Z](?:\.\d+)*\.?\s+)?(?:appendix|appendices|supplementary\s+(?:material|information)|"
    r"technical\s+appendices|neurips\s+paper\s+checklist|checklist)\b",
    re.IGNORECASE,
)
# ... or a lettered section heading: "A Proofs", "B.2 Additional Results" (not "A. Smith, ...")
_LETTERED = re.compile(r"^\s*[A-H](?:\.\d+)*\.?\s+[A-Z][a-z][\w-]*(?:\s+[\w-]+){0,8}\s*$")
_PAGE_NUMBER = re.compile(r"^\s*(?:\d{1,4}|page \d+(?: of \d+)?)\s*$", re.IGNORECASE)
_FIRST = re.compile(r"^\s*\[1\]\s")
_SECOND = re.compile(r"^\s*\[2\]\s")
# spaces a change of font swallowed
_SPACES = (
    (re.compile(r",(?=[A-Za-z“\"(])"), ", "),  # "S. Moraga,Optimal approximation"
    (re.compile(r"(?<=[a-z]{2})\.(?=[A-Z]|arXiv)"), ". "),  # "Laor.MNRAS", "probes.arXiv"
    (re.compile(r"\bIn(?=[A-Z]{2}|[A-Z0-9][a-z0-9])"), "In "),  # "InThe Thirty", "InAAAI"
    (re.compile(r"\bin(?=[A-Z])"), "in "),  # IEEE's "inProceedings of", "inVLDB"
    (re.compile(r"(?<=[a-z]{2})(?=et al\.)"), " "),  # "E. Xinget al."
    (re.compile(r"(?<=[a-z])\((?=[A-Z])"), " ("),  # "Open Quantum Systems(Oxford University"
    (re.compile(r"\b([A-Z]) \.(?=[\s,]|$)"), r"\1."),  # "Bengio, Y ."
)


class PdfUnavailable(RuntimeError):
    """pypdf is not installed."""


def pdf_text(path: Path) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover - depends on the environment
        raise PdfUnavailable(
            "reading a PDF needs the pdf extra: pip install 'paper-preflight[pdf]'"
        ) from exc
    # pypdf logs every font it cannot fully decode ("fontTools is required ..."): noise here
    logging.getLogger("pypdf").setLevel(logging.ERROR)
    reader = PdfReader(path)
    pages = [page.extract_text() or "" for page in reader.pages]
    return unicodedata.normalize("NFKC", "\n".join(pages))


def _heading(line: str) -> bool:
    if len(line) >= 40:
        return False
    words = re.sub(r"^\s*(?:\d+(?:\.\d+)*|[IVX]+)\.?\s+", "", line)  # "7 References", "VI. ..."
    return re.sub(r"[\s:]+", "", words).lower() in _HEADING_WORDS


def _ends_list(lines: list[str], i: int, seen: Counter[str]) -> bool:
    """An appendix starts at lines[i]. A lettered heading counts unless it is a running header
    (the paper's title, "A Mechanistic View of ...", seen on every page) or the line before runs
    on into it ("..., and Mourachko," then "A. How good is post-hoc watermarking ...")."""
    line = lines[i]
    if _AFTER.match(line):
        return True
    if not _LETTERED.match(line) or re.search(r"[,;]|\band\b|\s[A-Z]\.", line):
        return False
    before = lines[i - 1].rstrip() if i else ""
    return seen[line.strip()] == 1 and not re.search(r"(?:[,;\-]|\band)$", before)


def reference_section(text: str) -> tuple[int, str]:
    """(the line the list starts on, the list) after the last "References" heading."""
    lines = text.splitlines()
    starts = [i + 1 for i, line in enumerate(lines) if _heading(line)]
    if not starts:  # no heading: the last "[1]" followed by a "[2]"
        firsts = [i for i, line in enumerate(lines) if _FIRST.match(line)]
        starts = [i for i in firsts if any(_SECOND.match(x) for x in lines[i + 1 : i + 60])]
    if not starts:
        return 1, ""
    start = starts[-1]
    seen = Counter(line.strip() for line in lines)
    end = next((i for i in range(start, len(lines)) if _ends_list(lines, i, seen)), len(lines))
    kept = [line for line in lines[start:end] if not _PAGE_NUMBER.match(line)]
    section = "\n".join(_drop_running_lines(kept))
    for pattern, spaced in _SPACES:
        section = pattern.sub(spaced, section)
    return start + 1, section


def body_lines(text: str) -> list[str]:
    """A paper's lines before its (last) reference list heading, without page numbers and
    running headers: its prose, for citation-support evidence."""
    lines = text.splitlines()
    starts = [i for i, line in enumerate(lines) if _heading(line)]
    end = starts[-1] if starts else len(lines)
    return _drop_running_lines([line for line in lines[:end] if not _PAGE_NUMBER.match(line)])


def _drop_running_lines(lines: list[str]) -> list[str]:
    """Running headers and footers: a short line repeated on several pages ("Preprint", the
    paper's short title, with or without its page number)."""

    def key(line: str) -> str:
        return re.sub(r"\d+$", "", line.strip())

    counts: dict[str, int] = {}
    for line in lines:
        if key(line) and len(line.strip()) < 90:
            counts[key(line)] = counts.get(key(line), 0) + 1
    repeated = {k for k, n in counts.items() if n >= 3 and not re.match(r"^\[?\d", k)}
    return [line for line in lines if key(line) not in repeated]


def parse_pdf_file(path: Path) -> BibFile:
    try:
        text = pdf_text(path)
    except PdfUnavailable as exc:
        result = BibFile(path=path, encoding="pdf", derived=True)
        result.issues.append(BibIssue("unreadable", path, 1, None, str(exc)))
        return result
    except Exception as exc:  # a damaged or encrypted PDF
        result = BibFile(path=path, encoding="pdf", derived=True)
        result.issues.append(BibIssue("unreadable", path, 1, None, f"cannot read the PDF: {exc}"))
        return result
    first, section = reference_section(text)
    result = parse_plaintext(section, path, "pdf", wrapped=True)
    if not section:
        result.issues.append(
            BibIssue("unreadable", path, 1, None, "no reference list found (no 'References')")
        )
    # lines count from the reference list's heading in the extracted text
    for entry in result.entries:
        entry.line += first - 1
        entry.fields = {n: replace(f, line=f.line + first - 1) for n, f in entry.fields.items()}
    return result
