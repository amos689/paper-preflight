"""Tokenize citation commands in (masked) LaTeX source.

The command table covers natbib, biblatex (including multicite and volcite families), apacite,
harvard/chicago styles and bibentry. The list of command names was seeded from the MIT-licensed
tree-sitter-latex grammar (https://github.com/latex-lsp/tree-sitter-latex); the parsing logic
is our own.

Always run :func:`find_citations` on text produced by :func:`paper_preflight.tex.mask.mask_latex`
so that commented-out citations are ignored; offsets still refer to the original file.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import Enum


class CiteKind(Enum):
    SINGLE = "single"  # \cmd<pre>[pre][post]{keys}
    MULTI = "multi"  # \cmds(pre)(post)[pre][post]{keys}[pre][post]{keys}...
    VOLUME = "volume"  # \volcite[pre]{volume}[pages]{key}
    NOCITE = "nocite"  # \nocite{keys} — keys are "used" but not cited in text


_SINGLE = """
cite citet citep citealt citealp citeauthor citefullauthor citeyear citeyearpar citenum
Citet Citep Citealt Citealp Citeauthor Cite
parencite Parencite footcite footcitetext textcite Textcite smartcite Smartcite
autocite Autocite supercite citetitle Citetitle citedate citeurl citeurldate fullcite
footfullcite citelist citefield notecite Notecite pnotecite Pnotecite fnotecite
citeA citeNP citeANP citeyearNP citeauthorNP shortcite shortciteA shortciteNP
citeasnoun possessivecite citename citeN bibentry
""".split()

_MULTI = """
cites Cites parencites Parencites footcites footcitetexts smartcites Smartcites
textcites Textcites supercites autocites Autocites
""".split()

_VOLUME = """
volcite Volcite pvolcite Pvolcite fvolcite ftvolcite svolcite Svolcite tvolcite Tvolcite
avolcite Avolcite
""".split()

DEFAULT_COMMANDS: Mapping[str, CiteKind] = {
    **dict.fromkeys(_SINGLE, CiteKind.SINGLE),
    **dict.fromkeys(_MULTI, CiteKind.MULTI),
    **dict.fromkeys(_VOLUME, CiteKind.VOLUME),
    "nocite": CiteKind.NOCITE,
}

_COMMAND_RE = re.compile(r"\\([A-Za-z]+)(\*?)")


@dataclass(frozen=True)
class CiteKey:
    key: str
    offset: int  # offset of the first character of the key in the file


@dataclass(frozen=True)
class CiteCommand:
    command: str
    star: bool
    kind: CiteKind
    offset: int  # offset of the backslash
    end: int  # offset just after the last consumed argument
    keys: tuple[CiteKey, ...]
    notes: tuple[str, ...]  # raw pre/post notes, in order of appearance

    @property
    def is_nocite(self) -> bool:
        return self.kind is CiteKind.NOCITE


@dataclass(frozen=True)
class _Group:
    content: str
    start: int  # offset of the first character inside the delimiters
    end: int  # offset just after the closing delimiter


def _skip_spaces(text: str, i: int) -> int:
    """Skip spaces and at most one line break (a blank line ends the argument scan in TeX)."""
    newlines = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if ch in " \t":
            i += 1
        elif ch in "\r\n":
            if newlines == 1:
                break
            newlines += 1
            i += 2 if ch == "\r" and i + 1 < n and text[i + 1] == "\n" else 1
        else:
            break
    return i


def _read_group(text: str, i: int, open_ch: str, close_ch: str) -> _Group | None:
    """Read a delimited group starting at text[i]; nested braces are respected."""
    if i >= len(text) or text[i] != open_ch:
        return None
    depth_brace = 0
    depth_same = 0
    j = i + 1
    n = len(text)
    while j < n:
        ch = text[j]
        if ch == "\\":
            j += 2
            continue
        if ch == "{":
            depth_brace += 1
        elif ch == "}":
            if open_ch == "{" and depth_brace == 0:
                return _Group(text[i + 1 : j], i + 1, j + 1)
            depth_brace -= 1
            if depth_brace < 0:
                return None
        elif open_ch != "{" and depth_brace == 0:
            if ch == open_ch and open_ch != close_ch:
                depth_same += 1
            elif ch == close_ch:
                if depth_same == 0:
                    return _Group(text[i + 1 : j], i + 1, j + 1)
                depth_same -= 1
        j += 1
    return None


def _split_keys(group: _Group) -> tuple[CiteKey, ...]:
    keys: list[CiteKey] = []
    pos = group.start
    for part in group.content.split(","):
        stripped = part.strip()
        if stripped:
            keys.append(CiteKey(stripped, pos + (len(part) - len(part.lstrip()))))
        pos += len(part) + 1
    return tuple(keys)


def _read_optionals(
    text: str, i: int, open_ch: str, close_ch: str, limit: int, notes: list[str]
) -> int:
    for _ in range(limit):
        j = _skip_spaces(text, i)
        group = _read_group(text, j, open_ch, close_ch)
        if group is None:
            break
        notes.append(group.content)
        i = group.end
    return i


def _parse_single(text: str, i: int, notes: list[str]) -> tuple[_Group | None, int]:
    i = _read_optionals(text, i, "<", ">", 1, notes)  # apacite prenote
    i = _read_optionals(text, i, "[", "]", 2, notes)
    j = _skip_spaces(text, i)
    group = _read_group(text, j, "{", "}")
    return group, (group.end if group else i)


def find_citations(
    masked_text: str, commands: Mapping[str, CiteKind] = DEFAULT_COMMANDS
) -> list[CiteCommand]:
    """Find all citation commands in masked LaTeX text."""
    results: list[CiteCommand] = []
    for match in _COMMAND_RE.finditer(masked_text):
        name = match.group(1)
        kind = commands.get(name)
        if kind is None:
            continue
        start = match.start()
        if start > 0 and masked_text[start - 1] == "\\":
            # "\\cite" is a line break followed by text "cite", not a command.
            backslashes = len(masked_text[:start]) - len(masked_text[:start].rstrip("\\"))
            if backslashes % 2 == 1:
                continue
        i = match.end()
        notes: list[str] = []
        keys: list[CiteKey] = []
        if kind is CiteKind.MULTI:
            i = _read_optionals(masked_text, i, "(", ")", 2, notes)
            while True:
                group, new_i = _parse_single(masked_text, i, notes)
                if group is None:
                    break
                keys.extend(_split_keys(group))
                i = new_i
        elif kind is CiteKind.VOLUME:
            i = _read_optionals(masked_text, i, "[", "]", 1, notes)
            volume = _read_group(masked_text, _skip_spaces(masked_text, i), "{", "}")
            if volume is not None:
                notes.append(volume.content)
                i = _read_optionals(masked_text, volume.end, "[", "]", 1, notes)
                group = _read_group(masked_text, _skip_spaces(masked_text, i), "{", "}")
                if group is not None:
                    keys.extend(_split_keys(group))
                    i = group.end
        else:
            group, i = _parse_single(masked_text, i, notes)
            if group is not None:
                keys.extend(_split_keys(group))
        if not keys:
            continue  # e.g. "\cite" used as a word in prose, or a malformed command
        results.append(
            CiteCommand(
                command=name,
                star=bool(match.group(2)),
                kind=kind,
                offset=start,
                end=i,
                keys=tuple(keys),
                notes=tuple(notes),
            )
        )
    return results


def command_table(extra_single: Iterable[str] = ()) -> dict[str, CiteKind]:
    """Return the default command table extended with user-declared wrapper commands."""
    table = dict(DEFAULT_COMMANDS)
    for name in extra_single:
        table[name.lstrip("\\")] = CiteKind.SINGLE
    return table
