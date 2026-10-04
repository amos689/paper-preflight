"""The sentences a LaTeX paper's citations are asked to support.

:func:`citation_sentences` turns the body of every file of a project into plain-text paragraphs,
keeping where each citation command stood, splits the paragraphs into sentences and returns one
:class:`CitationSentence` per cited key:

* ``sentence``: the whole sentence, citations removed;
* ``claim``: what this citation is attached to. When one sentence cites several works at
  different places ("A does X [a], while B does Y [b]"), each gets the clause before its
  citation, if that clause is long enough to say something; otherwise the whole sentence;
* ``kind``: "result" (numbers, scores), "method" (what the authors used or followed) or
  "background", so that numeric claims can be matched exactly later on.

The conversion is deliberately small: inline math keeps its digits and symbols ("$95\\%$" is
"95%"), displayed formulas become "[formula]", references "[ref]", footnotes and captions are
paragraphs of their own, and macros the paper defines without arguments are expanded.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

from paper_preflight.tex.cites import CiteCommand, find_citations
from paper_preflight.tex.mask import mask_latex
from paper_preflight.tex.project import TexProject
from paper_preflight.textio import LineIndex, read_text


@dataclass(frozen=True)
class CitationSentence:
    key: str
    file: Path
    line: int  # of the citation command, 1-based
    column: int
    sentence: str  # the whole sentence, citations removed
    claim: str  # the part of the sentence this citation is attached to
    kind: str  # "result" | "method" | "background"
    previous: str = ""  # the sentence before, in the same paragraph (context)


# ---------------------------------------------------------------- LaTeX to plain text

_MATH_ENVIRONMENTS = frozenset(
    "equation equation* align align* alignat alignat* gather gather* multline multline* "
    "eqnarray eqnarray* displaymath math flalign flalign* dmath dmath*".split()
)
# Environments whose content is not prose
_DROPPED_ENVIRONMENTS = frozenset(
    "thebibliography tabular tabular* tabularx tabulary longtable tikzpicture pgfpicture "
    "axis lstlisting minted verbatim algorithmic filecontents".split()
)
# Commands whose argument is a paragraph of its own (headings, captions)
_HEADINGS = frozenset(
    "part chapter section subsection subsubsection paragraph subparagraph caption "
    "title subcaption".split()
)
_REFERENCES = frozenset("ref eqref autoref Autoref cref Cref pageref nameref vref".split())
# Commands dropped together with their arguments
_DROPPED = frozenset(
    "label vspace hspace includegraphics bibliographystyle bibliography addbibresource input "
    "include newcommand renewcommand providecommand def DeclareMathOperator setlength "
    "setcounter addtocounter index thanks author affiliation email address institute "
    "footnotemark maketitle documentclass usepackage nocite hypersetup graphicspath "
    "definecolor newtheorem pagestyle thispagestyle bibitem keywords acknowledgments "
    "printbibliography tableofcontents appendix centering raggedright noindent "
    "small footnotesize scriptsize large Large normalsize tiny clearpage newpage "
    "linewidth textwidth columnwidth".split()
)
_TWO_ARGUMENTS_KEEP_SECOND = frozenset("href textcolor colorbox".split())
# Macros papers use without defining them
_BUILTIN_MACROS = {
    "ie": "i.e.",
    "eg": "e.g.",
    "etal": "et al.",
    "wrt": "w.r.t.",
    "cf": "cf.",
    "vs": "vs.",
    "etc": "etc.",
    "aka": "a.k.a.",
    "LaTeX": "LaTeX",
    "TeX": "TeX",
    "ldots": "...",
    "dots": "...",
    "textendash": "-",
    "textemdash": "-",
    "S": "§",
    "textasciitilde": "~",
    "textpercent": "%",
    "textdollar": "$",
    "textless": "<",
    "textgreater": ">",
}
# Symbols in math that carry meaning in a claim
_MATH_SYMBOLS = {
    "times": "×",
    "pm": "±",
    "approx": "≈",
    "sim": "~",
    "leq": "≤",
    "le": "≤",
    "geq": "≥",
    "ge": "≥",
    "neq": "≠",
    "cdot": "·",
    "infty": "∞",
    "rightarrow": "→",
    "to": "→",
    "log": "log",
    "exp": "exp",
    "min": "min",
    "max": "max",
    "sum": "sum",
    "alpha": "α",
    "beta": "β",
    "gamma": "γ",
    "delta": "δ",
    "epsilon": "ε",
    "theta": "θ",
    "lambda": "λ",
    "mu": "μ",
    "pi": "π",
    "sigma": "σ",
    "tau": "τ",
    "phi": "φ",
    "omega": "ω",
    "Delta": "Δ",
    "Sigma": "Σ",
    "Omega": "Ω",
}
_ESCAPED = {"%": "%", "&": "&", "_": "_", "#": "#", "$": "$", "{": "{", "}": "}"}
# Citation commands that print the authors, so the sentence uses them as a noun
_TEXTUAL = frozenset(
    "citet Citet citealt Citealt citeauthor Citeauthor citefullauthor textcite Textcite "
    "textcites Textcites citeA citeasnoun citeN citename possessivecite fullcite".split()
)
# A parenthetical citation after a preposition is a noun too ("the benchmark of [12]")
_NOUN_PLACE = re.compile(
    r"(?:\b(?:of|by|in|from|following|to|with|on|than|references?)|\brefs?\.)\s*$", re.IGNORECASE
)
CITED_WORK = "[cited work]"

_NEWCOMMAND_RE = re.compile(
    r"\\(?:newcommand|renewcommand|providecommand)\*?\s*\{?\\([A-Za-z]+)\}?\s*\{"
    r"|\\def\s*\\([A-Za-z]+)\s*\{"
)


def _group_end(text: str, start: int) -> int:
    """The offset just after the brace group opening at ``start`` (or ``start`` if none)."""
    if start >= len(text) or text[start] != "{":
        return start
    depth = 0
    for i in range(start, len(text)):
        ch = text[i]
        if ch == "\\":
            continue
        if ch == "{" and (i == 0 or text[i - 1] != "\\"):
            depth += 1
        elif ch == "}" and (i == 0 or text[i - 1] != "\\"):
            depth -= 1
            if depth == 0:
                return i + 1
    return len(text)


def _skip_spaces(text: str, i: int) -> int:
    while i < len(text) and text[i] in " \t":
        i += 1
    return i


def _skip_optional(text: str, i: int) -> int:
    """Skip ``[...]`` arguments (and the spaces before them)."""
    while True:
        j = _skip_spaces(text, i)
        if j >= len(text) or text[j] != "[":
            return i
        depth = 0
        for k in range(j, len(text)):
            if text[k] == "[":
                depth += 1
            elif text[k] == "]":
                depth -= 1
                if depth == 0:
                    i = k + 1
                    break
        else:
            return len(text)


def defined_macros(texts: Iterable[str]) -> dict[str, str]:
    """Macros a paper defines without arguments (``\\newcommand{\\method}{SimCLR}``), as text."""
    macros: dict[str, str] = {}
    for text in texts:
        for match in _NEWCOMMAND_RE.finditer(text):
            name = match.group(1) or match.group(2)
            body_start = match.end() - 1
            body = text[body_start + 1 : _group_end(text, body_start) - 1]
            if "#" in body or len(body) > 80:
                continue  # takes arguments, or is no short name
            macros[name] = _math_text(body)
    return macros


def _math_text(content: str) -> str:
    """Inline math as text: digits, letters and meaningful symbols ("95\\%" → "95%")."""
    out = re.sub(r"\\([%&_#$])", r"\1", content)
    out = re.sub(
        r"\\(?:mathrm|mathbf|mathit|text|textrm|textbf|operatorname|mathcal|mathbb)", "", out
    )
    out = re.sub(r"\\([A-Za-z]+)", lambda m: _MATH_SYMBOLS.get(m.group(1), ""), out)
    out = re.sub(r"\\.", " ", out)
    out = out.replace("{", "").replace("}", "")  # "10^{9}" stays "10^9", not "109"
    return " ".join(out.split())


@dataclass
class _Paragraph:
    chars: list[str] = field(default_factory=list)
    cites: list[tuple[int, CiteCommand]] = field(default_factory=list)

    def emit(self, text: str) -> None:
        for ch in text:
            if ch.isspace():
                if not self.chars or self.chars[-1] == " ":
                    continue
                ch = " "
            self.chars.append(ch)

    @property
    def text(self) -> str:
        return "".join(self.chars)


class _Converter:
    """Plain-text paragraphs from masked LaTeX, with each citation's place kept."""

    def __init__(self, text: str, cites: list[CiteCommand], macros: dict[str, str]) -> None:
        self.text = text
        self.cites = {c.offset: c for c in cites}
        self.macros = macros
        self.paragraphs: list[_Paragraph] = []
        self.current = _Paragraph()
        self.footnotes: list[tuple[int, int]] = []

    def run(self, start: int, end: int) -> list[_Paragraph]:
        self._convert(start, end)
        self._break()
        while self.footnotes:  # footnotes are paragraphs of their own, after the text
            begin, finish = self.footnotes.pop(0)
            self._convert(begin, finish)
            self._break()
        return self.paragraphs

    def _break(self) -> None:
        if self.current.chars and self.current.text.strip():
            self.paragraphs.append(self.current)
        self.current = _Paragraph()

    def _find_end(self, environment: str, start: int) -> tuple[int, int]:
        """The span of ``\\end{environment}`` after ``start`` (or the end of the text)."""
        match = re.compile(r"\\end\s*\{" + re.escape(environment) + r"\}").search(self.text, start)
        return (match.start(), match.end()) if match else (len(self.text), len(self.text))

    def _convert(self, start: int, end: int) -> None:
        text, i = self.text, start
        while i < end:
            cite = self.cites.get(i)
            if cite is not None:
                if not cite.is_nocite:
                    self.current.cites.append((len(self.current.chars), cite))
                    # a citation the sentence uses as a noun ("We follow \citet{x}", "the
                    # benchmark of \cite{y}") leaves a hole: name it
                    if cite.command in _TEXTUAL or _NOUN_PLACE.search(self.current.text):
                        self.current.emit(f" {CITED_WORK} ")
                i = cite.end
                continue
            ch = text[i]
            if ch == "\\":
                i = self._command(i, end)
            elif ch == "$":
                if text.startswith("$$", i):
                    close = text.find("$$", i + 2, end)
                    close = end if close < 0 else close
                    self.current.emit(" [formula] ")
                    i = close + 2
                else:
                    close = i + 1
                    while close < end and (text[close] != "$" or text[close - 1] == "\\"):
                        close += 1
                    self.current.emit(_math_text(text[i + 1 : close]))
                    i = close + 1
            elif ch in "{}":
                i += 1
            elif ch == "~":
                self.current.emit(" ")
                i += 1
            elif ch == "\n":
                j = i + 1
                while j < end and text[j] in " \t\r":
                    j += 1
                if j < end and text[j] == "\n":
                    self._break()  # a blank line ends the paragraph
                    i = j + 1
                else:
                    self.current.emit(" ")
                    i += 1
            elif text.startswith("``", i) or text.startswith("''", i):
                self.current.emit('"')
                i += 2
            else:
                self.current.emit(ch)
                i += 1

    def _command(self, i: int, end: int) -> int:
        text = self.text
        match = re.compile(r"\\([A-Za-z]+\*?|.)").match(text, i)
        if match is None:
            return i + 1
        name, after = match.group(1), match.end()
        if not name[0].isalpha():
            if name in _ESCAPED:
                self.current.emit(_ESCAPED[name])
            elif name in "([":  # \( inline math \) and \[ displayed math \]
                closing = "\\)" if name == "(" else "\\]"
                close = text.find(closing, after, end)
                close = end if close < 0 else close
                if name == "(":
                    self.current.emit(_math_text(text[after:close]))
                else:
                    self.current.emit(" [formula] ")
                return close + 2
            elif name in "\\ ,;:!":
                self.current.emit(" ")
            return after  # an accent ("\'e") keeps its letter; "\-" and "\@" print nothing
        bare = name.rstrip("*")
        if bare in {"begin", "end"}:
            group_end = _group_end(text, _skip_spaces(text, after))
            environment = text[_skip_spaces(text, after) + 1 : group_end - 1].strip()
            if bare == "end":
                if environment not in _MATH_ENVIRONMENTS:
                    self._break()
                return group_end
            if environment in _MATH_ENVIRONMENTS:
                self.current.emit(" [formula] ")
                return self._find_end(environment, group_end)[1]
            if environment in _DROPPED_ENVIRONMENTS:
                self._break()
                return self._find_end(environment, group_end)[1]
            if environment == "document":
                return group_end
            self._break()
            return _skip_optional(text, group_end)
        if bare in _HEADINGS:
            j = _skip_optional(text, after)
            j = _skip_spaces(text, j)
            group_end = _group_end(text, j)
            self._break()
            if group_end > j:
                self._convert(j + 1, group_end - 1)
            self._break()
            return group_end
        if bare in {"footnote", "footnotetext"}:
            j = _skip_spaces(text, _skip_optional(text, after))
            group_end = _group_end(text, j)
            if group_end > j:
                self.footnotes.append((j + 1, group_end - 1))
            return group_end
        if bare == "item":
            self._break()
            return _skip_optional(text, after)
        if bare == "par":
            self._break()
            return after
        if bare in _REFERENCES:
            self.current.emit("[ref]")
            return _group_end(text, _skip_spaces(text, _skip_optional(text, after)))
        if bare in _DROPPED:
            j = _skip_optional(text, after)
            while True:  # every brace argument
                k = _skip_spaces(text, j)
                if k < end and text[k] == "{":
                    j = _group_end(text, k)
                elif bare in {"newcommand", "renewcommand", "def"} and text.startswith("\\", k):
                    j = re.compile(r"\\(?:[A-Za-z]+|.?)").match(text, k).end()  # type: ignore[union-attr]
                else:
                    return j
        if bare in _TWO_ARGUMENTS_KEEP_SECOND:
            j = _group_end(text, _skip_spaces(text, _skip_optional(text, after)))
            k = _skip_spaces(text, j)
            group_end = _group_end(text, k)
            if group_end > k:
                self._convert(k + 1, group_end - 1)
            return group_end
        if bare in self.macros:
            self.current.emit(self.macros[bare])
            return after
        if bare in _BUILTIN_MACROS:
            self.current.emit(_BUILTIN_MACROS[bare])
            return after
        # any other command: its brace argument's text, if it has one ("\textbf{x}" → "x")
        j = _skip_spaces(text, _skip_optional(text, after))
        if j < end and text[j] == "{":
            group_end = _group_end(text, j)
            self._convert(j + 1, group_end - 1)
            return group_end
        return after


# ---------------------------------------------------------------- sentences

_ABBREVIATIONS = frozenset(
    "e.g i.e et al cf vs fig figs eq eqs sec secs tab ref refs no nos resp approx dr prof "
    "st jr mr ms viz ca ch thm lem def prop cor alg app vol pp eqn eqns sect chap".split()
)
_BOUNDARY = re.compile(r"[.!?]['\")\]]*\s+")
_RESULT = re.compile(
    r"\d+(?:\.\d+)?\s*(?:%|percent|×|x\b|times\b|points?\b|fold\b)"
    r"|\b(?:accuracy|f1|bleu|rouge|auc|error rate|outperform\w*|improv\w* by|achiev\w*"
    r"|state[- ]of[- ]the[- ]art|speed-?up)\b",
    re.IGNORECASE,
)
_METHOD = re.compile(
    r"\b(?:we|our)\b[^.]*\b(?:use[sd]?|using|adopt\w*|follow\w*|employ\w*|build\w* on|based on"
    r"|implement\w*|appl(?:y|ied)|initiali[sz]\w*|fine-?tun\w*|train\w* (?:with|on))\b"
    r"|\b(?:following|as in|similar to)\b",
    re.IGNORECASE,
)
# A number in a claim, other than a year, makes it a result to match exactly
_NUMBER = re.compile(r"(?<![\w.^])\d+(?:[.,]\d+)?(?:\^\d+)?(?![\w])")
_YEAR = re.compile(r"(?:19|20)\d\d")
MIN_CLAUSE_WORDS = 5
# Where one clause of a sentence ends and another begins
_CLAUSE_BREAK = re.compile(
    r";|,?\s+\b(?:while|whereas|although|though)\b|,\s+(?:but|however|and we|which)\b"
)
_CLAUSE_START = re.compile(r"^[,;:\s]*(?:and|or|but|while|whereas|although|though|however)?[,\s]*")


def _sentence_spans(text: str) -> list[tuple[int, int]]:
    """Sentence spans of a paragraph; each span includes the spaces after its end."""
    spans: list[tuple[int, int]] = []
    start = 0
    for match in _BOUNDARY.finditer(text):
        end = match.end()
        following = text[end : end + 1]
        if not following or not (following.isupper() or following.isdigit() or following in '"(['):
            continue
        before = text[start : match.start()].split()
        last = before[-1].lower().rstrip(".") if before else ""
        if last in _ABBREVIATIONS or (len(last) == 1 and last.isalpha()):
            continue  # "et al.", "Fig.", an initial
        spans.append((start, end))
        start = end
    if start < len(text):
        spans.append((start, len(text)))
    return spans


def _clean(text: str) -> str:
    text = re.sub(r"\(\s*(?:e\.g\.,?|see|cf\.|i\.e\.,?)?\s*[,;]?\s*\)", "", text)
    text = re.sub(r"\[\s*\]", "", text)
    text = re.sub(r"\s+([.,;:!?)])", r"\1", text)
    text = re.sub(r"(?<!\.)\.\.(?!\.)", ".", text)  # "Liu et al. [12]." lost its citation
    return " ".join(text.split())


def _kind(claim: str) -> str:
    numbers = (n for n in _NUMBER.findall(claim) if not _YEAR.fullmatch(n))
    if _RESULT.search(claim) or any(True for _ in numbers):
        return "result"
    if _METHOD.search(claim):
        return "method"
    return "background"


def _claims(text: str, start: int, end: int, places: list[int]) -> dict[int, str]:
    """The clause each citation place in a sentence is attached to, when the sentence cites
    works in different clauses ("A does X [a], while B does Y [b]"). A citation belongs to the
    clause it ends; places in one clause, or clauses too short to say anything, get the whole
    sentence (no entry in the result)."""
    bounds = [start, *(start + m.start() for m in _CLAUSE_BREAK.finditer(text[start:end])), end]
    owner = {p: next(k for k in range(len(bounds) - 1) if p <= bounds[k + 1]) for p in places}
    if len(set(owner.values())) < 2:
        return {}
    claims: dict[int, str] = {}
    for place, k in owner.items():
        clause = _CLAUSE_START.sub("", _clean(text[bounds[k] : bounds[k + 1]]))
        if len(clause.split()) >= MIN_CLAUSE_WORDS:
            claims[place] = clause
    return claims


def _paragraph_sentences(
    paragraph: _Paragraph, path: Path, index: LineIndex
) -> list[CitationSentence]:
    text = paragraph.text
    out: list[CitationSentence] = []
    previous = ""
    for start, end in _sentence_spans(text):
        sentence = _clean(text[start:end])
        cites = sorted(
            ((p, c) for p, c in paragraph.cites if start <= p < end or p == end == len(text)),
            key=lambda place: (place[0], place[1].offset),
        )
        claims = _claims(text, start, end, sorted({p for p, _ in cites}))
        for position, command in cites:
            claim = claims.get(position, sentence)
            line, column = index.position(command.offset)
            for key in command.keys:
                out.append(
                    CitationSentence(
                        key.key, path, line, column, sentence, claim, _kind(claim), previous
                    )
                )
        previous = sentence
    return out


def _paragraphs(project: TexProject) -> list[tuple[Path, str, _Paragraph]]:
    """Each file's body as plain-text paragraphs: (file, its source text, paragraph)."""
    sources = {path: read_text(path).text for path in project.files}
    masked = {path: mask_latex(text) for path, text in sources.items()}
    macros = defined_macros(masked.values())
    out: list[tuple[Path, str, _Paragraph]] = []
    for path, text in masked.items():
        start, end = 0, len(text)
        begin = re.search(r"\\begin\s*\{document\}", text)
        if begin:
            start = begin.end()
        finish = re.search(r"\\end\s*\{document\}", text)
        if finish:
            end = finish.start()
        converter = _Converter(text, find_citations(text), macros)
        out.extend((path, sources[path], p) for p in converter.run(start, end))
    return out


def citation_sentences(project: TexProject) -> list[CitationSentence]:
    """Every citation of the project's files, with the sentence and claim it supports."""
    found: list[CitationSentence] = []
    indexes: dict[Path, LineIndex] = {}
    for path, source, paragraph in _paragraphs(project):
        index = indexes.setdefault(path, LineIndex(source))
        found.extend(_paragraph_sentences(paragraph, path, index))
    return found


def document_paragraphs(project: TexProject) -> list[str]:
    """The prose of a LaTeX source as plain-text paragraphs, citations removed: a cited
    paper's own source, read as evidence."""
    return [_clean(paragraph.text) for _, _, paragraph in _paragraphs(project)]


def document_abstract(project: TexProject) -> str:
    """The text of the source's ``abstract`` environment (or ``\\abstract{...}``), if any."""
    for path in project.files:
        masked = mask_latex(read_text(path).text)
        begin = re.search(r"\\begin\s*\{abstract\}", masked)
        if begin:
            end = re.compile(r"\\end\s*\{abstract\}").search(masked, begin.end())
            span = (begin.end(), end.start() if end else len(masked))
        else:
            command = re.search(r"\\abstract\s*\{", masked)
            if command is None:
                continue
            span = (command.end(), _group_end(masked, command.end() - 1) - 1)
        converter = _Converter(masked, find_citations(masked), defined_macros([masked]))
        return " ".join(_clean(p.text) for p in converter.run(*span))
    return ""
