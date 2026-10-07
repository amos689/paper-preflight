"""`bib fix`: turn findings into edits of the .bib files, shown as a unified diff.

Two levels:

* ``safe`` — edits that cannot change which work is cited: identifiers written so that links
  break (REF017) and a DOI the registry has but the entry lacks (REF016).
* ``unsafe`` — also edits that rewrite what the entry says, taken from the record it is bound
  to: authors (REF010/REF011), title (REF012), year (REF013), venue (REF014), and removing an
  identifier that points to another work (REF001). Review them before applying.

Edits touch only the fields concerned; every other byte of the file, including line endings
and encoding, is kept. Nothing is written unless asked (the CLI's ``--apply``).
"""

from __future__ import annotations

import contextlib
import difflib
import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from paper_preflight.bib.parse import BibEntry, BibFile
from paper_preflight.findings import Finding
from paper_preflight.textio import TextFile, read_text

Level = Literal["safe", "unsafe"]
Action = Literal["replace", "add", "remove"]

SAFE_RULES = frozenset({"REF016", "REF017"})
UNSAFE_RULES = frozenset({"REF001", "REF010", "REF011", "REF012", "REF013", "REF014"})


@dataclass(frozen=True)
class Fix:
    file: Path
    key: str
    rule: str
    field: str
    action: Action
    old: str | None
    new: str | None
    level: Level


def plan(
    findings: Iterable[Finding],
    bib_files: Iterable[BibFile],
    *,
    level: Level = "safe",
    keys: set[str] | None = None,
) -> list[Fix]:
    """The edits the findings call for: at most one per field, safe ones first."""
    rules = SAFE_RULES | (UNSAFE_RULES if level == "unsafe" else frozenset())
    entries: dict[str, BibEntry] = {}
    for bib in bib_files:
        if bib.derived:
            continue  # a compiled .bbl is not the source to fix
        for entry in bib.entries:
            entries.setdefault(entry.key, entry)
    fixes: dict[tuple[str, str], Fix] = {}
    ordered = sorted(findings, key=lambda f: f.rule_id not in SAFE_RULES)
    for finding in ordered:
        if finding.rule_id not in rules or finding.key is None or finding.field is None:
            continue
        if keys is not None and finding.key not in keys:
            continue
        target = entries.get(finding.key)
        if target is None or (finding.key, finding.field) in fixes:
            continue
        fix = _fix_for(finding, target)
        if fix is not None:
            fixes[(finding.key, finding.field)] = fix
    return list(fixes.values())


def _fix_for(finding: Finding, entry: BibEntry) -> Fix | None:
    field = finding.field or ""
    current = entry.fields.get(field)
    suggestion = finding.data.get("suggestion")
    level: Level = "safe" if finding.rule_id in SAFE_RULES else "unsafe"
    if finding.data.get("remove"):
        if current is None:
            return None
        return Fix(
            entry.file, entry.key, finding.rule_id, field, "remove", current.raw, None, level
        )
    # a suggestion that is advice for a person ("(correct the arXiv ID)"), not a value
    if not isinstance(suggestion, str) or not suggestion or finding.data.get("manual"):
        return None
    if current is None:
        return Fix(entry.file, entry.key, finding.rule_id, field, "add", None, suggestion, level)
    if current.value.strip() == suggestion.strip():
        return None
    return Fix(
        entry.file, entry.key, finding.rule_id, field, "replace", current.raw, suggestion, level
    )


def _entry_span(text: str, entry: BibEntry) -> tuple[int, int]:
    line_start = 0
    for _ in range(entry.line - 1):
        line_start = text.index("\n", line_start) + 1
    start = text.find(entry.raw, line_start) if entry.raw else -1
    if start < 0:
        raise ValueError(f"entry '{entry.key}' was not found where the parser saw it")
    return start, start + len(entry.raw)


def _after_name(value: str) -> Callable[[re.Match[str]], str]:
    """Keep the matched ``name =`` prefix and put ``value`` after it."""
    return lambda match: match.group(1) + value


def _edit_entry(raw: str, fixes: list[Fix], newline: str) -> str:
    for fix in fixes:
        name = re.escape(fix.field)
        if fix.action == "replace" and fix.old is not None:
            pattern = re.compile(rf"(?i)(\b{name}\s*=\s*){re.escape(fix.old)}")
            replacement = "{" + str(fix.new) + "}"
            raw, count = pattern.subn(_after_name(replacement), raw, 1)
            if count != 1:
                raise ValueError(f"field '{fix.field}' of '{fix.key}' could not be located")
        elif fix.action == "remove" and fix.old is not None:
            value = re.escape(fix.old)
            pattern = re.compile(rf"(?im)^[ \t]*{name}\s*=\s*{value}[ \t]*,?[ \t]*\r?\n")
            raw, count = pattern.subn("", raw, 1)
            if count != 1:
                raise ValueError(f"field '{fix.field}' of '{fix.key}' could not be located")
        elif fix.action == "add":
            indent_match = re.search(r"\n([ \t]+)[A-Za-z]+\s*=", raw)
            indent = indent_match.group(1) if indent_match else "  "
            body = raw.rstrip()
            if not body.endswith("}"):
                raise ValueError(f"entry '{fix.key}' does not end with a closing brace")
            inner = body[:-1].rstrip()
            separator = "" if inner.endswith(",") else ","
            line = f"{indent}{fix.field} = {{{fix.new}}},"
            raw = f"{inner}{separator}{newline}{line}{newline}}}" + raw[len(body) :]
    return raw


def apply(text: str, entries: Iterable[BibEntry], fixes: list[Fix], newline: str = "\n") -> str:
    """The file text with the fixes applied; untouched parts stay byte for byte."""
    by_key: dict[str, list[Fix]] = {}
    for fix in fixes:
        by_key.setdefault(fix.key, []).append(fix)
    spans: list[tuple[int, int, BibEntry]] = []
    for entry in entries:
        if entry.key in by_key and all(entry.key != s[2].key for s in spans):
            start, end = _entry_span(text, entry)
            spans.append((start, end, entry))
    for start, end, entry in sorted(spans, key=lambda s: s[0], reverse=True):
        text = text[:start] + _edit_entry(text[start:end], by_key[entry.key], newline) + text[end:]
    return text


@dataclass(frozen=True)
class FileEdit:
    path: Path
    source: TextFile
    new_text: str
    fixes: list[Fix]

    def diff(self, base: Path | None = None) -> str:
        name = self.path.as_posix()
        if base is not None:
            with contextlib.suppress(ValueError):
                name = self.path.relative_to(base).as_posix()
        return "".join(
            difflib.unified_diff(
                self.source.text.splitlines(keepends=True),
                self.new_text.splitlines(keepends=True),
                fromfile=f"a/{name}",
                tofile=f"b/{name}",
            )
        )

    def write(self) -> None:
        data = self.new_text.encode(self.source.encoding)
        if self.source.had_bom and self.source.encoding.replace("-", "").lower() == "utf8":
            data = b"\xef\xbb\xbf" + data
        self.path.write_bytes(data)


def edits(bib_files: Iterable[BibFile], fixes: list[Fix]) -> list[FileEdit]:
    out: list[FileEdit] = []
    for bib in bib_files:
        mine = [f for f in fixes if f.file == bib.path]
        if not mine:
            continue
        source = read_text(bib.path)
        new_text = apply(source.text, bib.entries, mine, source.newline)
        if new_text != source.text:
            out.append(FileEdit(bib.path, source, new_text, mine))
    return out
