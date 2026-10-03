"""Mask LaTeX regions that must not be scanned for commands.

The masked text has exactly the same length and line structure as the input: masked characters
are replaced by spaces (line breaks are kept), so offsets, lines and columns computed on the masked
text are valid for the original file.

Masked regions:

* ``%`` comments (a ``%`` is escaped only when preceded by an odd number of backslashes);
* ``\\iffalse ... \\fi`` blocks, honouring nested ``\\if...``/``\\fi`` pairs;
* ``comment`` environments (``\\begin{comment} ... \\end{comment}``);
* verbatim-like environments and ``\\verb`` (their content is not LaTeX).

Comment and conditional handling follows the semantics of google-research/arxiv-latex-cleaner
(Apache-2.0); this is an independent implementation, no code was copied.
"""

from __future__ import annotations

import re

VERBATIM_ENVIRONMENTS = frozenset(
    {"verbatim", "verbatim*", "Verbatim", "lstlisting", "minted", "alltt", "comment"}
)

_BEGIN_RE = re.compile(r"\\begin\s*\{([^}]*)\}")
_IF_RE = re.compile(r"\\(if[a-zA-Z@]*|fi)(?![a-zA-Z@])")
_VERB_RE = re.compile(r"\\verb\*?([^a-zA-Z\s*])")


def _blank(chars: list[str], start: int, end: int) -> None:
    for i in range(start, end):
        if chars[i] not in "\r\n":
            chars[i] = " "


def _is_escaped(text: str, index: int) -> bool:
    """True if text[index] is preceded by an odd number of backslashes."""
    count = 0
    j = index - 1
    while j >= 0 and text[j] == "\\":
        count += 1
        j -= 1
    return count % 2 == 1


def mask_latex(text: str) -> str:
    """Return a copy of ``text`` with comments, ``\\iffalse`` blocks and verbatim blanked."""
    chars = list(text)
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if ch == "%" and not _is_escaped(text, i):
            end = i
            while end < n and text[end] not in "\r\n":
                end += 1
            _blank(chars, i, end)
            i = end
            continue
        if ch == "\\" and not _is_escaped(text, i):
            begin = _BEGIN_RE.match(text, i)
            if begin and begin.group(1).strip() in VERBATIM_ENVIRONMENTS:
                env = begin.group(1).strip()
                end_pattern = re.compile(r"\\end\s*\{" + re.escape(env) + r"\}")
                found = end_pattern.search(text, begin.end())
                stop = found.end() if found else n
                _blank(chars, i, stop)
                i = stop
                continue
            verb = _VERB_RE.match(text, i)
            if verb:
                delimiter = verb.group(1)
                close = text.find(delimiter, verb.end())
                line_end = len(text)
                for sep in ("\n", "\r"):
                    pos = text.find(sep, verb.end())
                    if pos != -1:
                        line_end = min(line_end, pos)
                stop = close + 1 if close != -1 and close < line_end else verb.end()
                _blank(chars, i, stop)
                i = stop
                continue
            if text.startswith("\\iffalse", i) and not _continues_name(text, i + len("\\iffalse")):
                stop = _matching_fi(text, i + len("\\iffalse"))
                _blank(chars, i, stop)
                i = stop
                continue
        i += 1
    return "".join(chars)


def _continues_name(text: str, index: int) -> bool:
    return index < len(text) and (text[index].isalpha() or text[index] == "@")


def _matching_fi(text: str, start: int) -> int:
    """Return the offset just after the ``\\fi`` closing an ``\\iffalse`` opened before start."""
    depth = 1
    for match in _IF_RE.finditer(text, start):
        if _is_escaped(text, match.start()) or _in_comment(text, match.start()):
            continue
        if match.group(1) == "fi":
            depth -= 1
            if depth == 0:
                return match.end()
        else:
            depth += 1
    return len(text)


def _in_comment(text: str, index: int) -> bool:
    line_start = max(text.rfind("\n", 0, index), text.rfind("\r", 0, index)) + 1
    return any(text[j] == "%" and not _is_escaped(text, j) for j in range(line_start, index))
