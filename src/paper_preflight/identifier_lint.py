"""Offline checks of how identifiers are written in .bib entries (REF017).

Google Scholar and many exporters write DOIs with LaTeX escapes (``10.1162/tacl\\_a\\_00276``);
styles that print the field through ``\\url`` or ``\\href`` then produce a broken link, and no
registration agency knows the escaped string (docs/spikes/S4). We also flag DOI fields that hold a
URL prefix or are not syntactically DOIs, and arXiv ``eprint`` fields that are not arXiv IDs.
"""

from __future__ import annotations

import re

from paper_preflight.bib.ids import is_valid_doi_syntax, normalize_doi
from paper_preflight.bib.parse import BibEntry, unescape_identifier
from paper_preflight.findings import Finding, Location
from paper_preflight.rules import make_finding

_ESCAPE_RE = re.compile(r"\\[_%&#$]|[{}]")
_ARXIV_ID_RE = re.compile(
    r"^(?:arxiv:)?(\d{4}\.\d{4,5}|[a-z][a-z-]+(?:\.[A-Z]{2})?/\d{7})(v\d+)?$", re.I
)


def _raw_value(entry: BibEntry, name: str) -> str | None:
    field = entry.fields.get(name)
    if field is None:
        return None
    raw = field.raw.strip()
    if len(raw) >= 2 and (raw[0], raw[-1]) in (("{", "}"), ('"', '"')):
        raw = raw[1:-1]
    return raw


def check_identifier_syntax(entries: list[BibEntry]) -> list[Finding]:
    findings: list[Finding] = []
    for entry in entries:
        doi_field = entry.fields.get("doi")
        raw = _raw_value(entry, "doi")
        if doi_field is not None and raw is not None and raw.strip():
            location = Location(entry.file, doi_field.line, 1)
            normalized = normalize_doi(unescape_identifier(raw))
            if normalized is None or not is_valid_doi_syntax(normalized):
                findings.append(
                    make_finding(
                        "REF017", location, key=entry.key, field="doi",
                        problem="not a DOI", problem_zh="不是有效的 DOI",
                        value=raw, suggestion="(remove or correct the field)",
                        detail="invalid",
                    )
                )  # fmt: skip
            elif _ESCAPE_RE.search(raw) or raw != raw.strip() or normalized != raw.lower():
                problem, problem_zh = _describe(raw)
                findings.append(
                    make_finding(
                        "REF017", location, key=entry.key, field="doi",
                        problem=problem, problem_zh=problem_zh, value=raw,
                        suggestion=normalized, detail="escaped",
                    )
                )  # fmt: skip

        archive = (entry.text("archiveprefix") or entry.text("eprinttype") or "").lower()
        eprint_field = entry.fields.get("eprint")
        eprint = entry.text("eprint")
        if (
            eprint_field is not None
            and eprint
            and archive == "arxiv"
            and not _ARXIV_ID_RE.match(eprint.strip())
        ):
            findings.append(
                    make_finding(
                        "REF017", Location(entry.file, eprint_field.line, 1), key=entry.key,
                        field="eprint", problem="not an arXiv identifier",
                        problem_zh="不是有效的 arXiv 编号", value=eprint,
                        suggestion="(correct the arXiv ID)", detail="invalid-eprint",
                    )
                )  # fmt: skip
    return findings


def _describe(raw: str) -> tuple[str, str]:
    if "\\" in raw:
        return "contains LaTeX escapes", "包含 LaTeX 转义符"
    if "{" in raw or "}" in raw:
        return "contains braces", "包含花括号"
    if raw.lower().startswith(("http", "doi:")):
        return "contains a URL or 'doi:' prefix", "带有网址或 'doi:' 前缀"
    return "is not in canonical form", "不是规范写法"
