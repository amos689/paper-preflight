"""Offline citation-key and bibliography hygiene checks (rule families CIT and TEX)."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from paper_preflight.bib.ids import extract_identifiers
from paper_preflight.bib.normalize import title_key, word_count
from paper_preflight.bib.parse import BibEntry, BibFile
from paper_preflight.findings import Finding, Location
from paper_preflight.identifier_lint import check_identifier_syntax
from paper_preflight.rules import make_finding
from paper_preflight.tex.auxdata import AuxData
from paper_preflight.tex.project import TexProject

# Required fields per entry type (classic BibTeX, with BibLaTeX alternatives after "|").
REQUIRED_FIELDS: dict[str, list[str]] = {
    "article": ["author", "title", "journal|journaltitle", "year|date"],
    "inproceedings": ["author", "title", "booktitle", "year|date"],
    "conference": ["author", "title", "booktitle", "year|date"],
    "book": ["author|editor", "title", "publisher", "year|date"],
    "incollection": ["author", "title", "booktitle", "publisher", "year|date"],
    "inbook": ["author|editor", "title", "chapter|pages", "publisher", "year|date"],
    "phdthesis": ["author", "title", "school|institution", "year|date"],
    "mastersthesis": ["author", "title", "school|institution", "year|date"],
    "thesis": ["author", "title", "type", "institution|school", "year|date"],
    "techreport": ["author", "title", "institution", "year|date"],
    "report": ["author", "title", "type", "institution", "year|date"],
    "online": ["title", "url", "year|date|urldate"],
}


@dataclass
class HygieneInput:
    bib_files: list[BibFile]
    project: TexProject | None = None
    build_data: AuxData | None = None
    cited_keys: set[str] = field(default_factory=set)
    nocite_all: bool = False


def _entry_location(entry: BibEntry) -> Location:
    return Location(entry.file, entry.line, 1)


def check_hygiene(data: HygieneInput) -> list[Finding]:
    findings: list[Finding] = []
    entries: dict[str, BibEntry] = {}
    for bib in data.bib_files:
        for issue in bib.issues:
            location = Location(issue.file, issue.line, 1)
            if issue.kind == "unreadable":
                findings.append(make_finding("CIT005", location, path=issue.file.name))
            elif issue.kind == "syntax_error":
                findings.append(make_finding("CIT007", location, detail=issue.detail))
            elif issue.kind == "duplicate_field":
                findings.append(make_finding("CIT008", location, key=issue.key, field=issue.detail))
            elif issue.kind == "duplicate_key":
                findings.append(
                    make_finding("CIT002", location, key=issue.key, first_line=issue.detail)
                )
        for entry in bib.entries:
            if entry.key in entries:  # same key in two different .bib files
                first = entries[entry.key]
                findings.append(
                    make_finding(
                        "CIT002",
                        _entry_location(entry),
                        key=entry.key,
                        first_line=f"{first.line} ({first.file.name})",
                    )
                )
                continue
            entries[entry.key] = entry

    project = data.project
    if project is not None:
        findings.extend(_project_findings(project))
        sites_by_key: dict[str, list[Location]] = defaultdict(list)
        for site in project.cite_sites:
            if site.key != "*":
                loc = site.location
                sites_by_key[site.key].append(Location(loc.file, loc.line, loc.column))
        cited = data.cited_keys or set(sites_by_key)
        for key in sorted(cited):
            if key in entries:
                continue
            sites = sites_by_key.get(key, [])
            location = sites[0] if sites else Location(project.main, 1, 1)
            findings.append(
                make_finding(
                    "CIT001", location, key=key, related=tuple(sites[1:]), count=len(sites) or 1
                )
            )
        if not data.nocite_all:
            for key, entry in entries.items():
                if key not in cited:
                    findings.append(make_finding("CIT003", _entry_location(entry), key=key))

    for entry in entries.values():
        missing = _missing_required(entry)
        if missing:
            findings.append(
                make_finding(
                    "CIT006",
                    _entry_location(entry),
                    key=entry.key,
                    entry_type=entry.entry_type,
                    fields=", ".join(missing),
                )
            )
    findings.extend(_near_duplicates(list(entries.values())))
    findings.extend(check_identifier_syntax(list(entries.values())))
    return _apply_suppressions(findings, entries)


def _project_findings(project: TexProject) -> list[Finding]:
    findings: list[Finding] = []
    for issue in project.issues:
        loc = issue.location
        location = Location(loc.file, loc.line, loc.column)
        rule = {
            "missing_include": "TEX001",
            "include_cycle": "TEX002",
            "remote_bib_resource": "TEX003",
            "unreadable_file": "TEX004",
        }[issue.kind]
        findings.append(make_finding(rule, location, name=issue.detail, detail=issue.detail))
    for resource in project.bib_resources:
        if not resource.exists:
            loc = resource.declared_at
            findings.append(
                make_finding(
                    "CIT005", Location(loc.file, loc.line, loc.column), path=resource.path.name
                )
            )
    return findings


def _missing_required(entry: BibEntry) -> list[str]:
    missing: list[str] = []
    for requirement in REQUIRED_FIELDS.get(entry.entry_type, []):
        alternatives = requirement.split("|")
        if not any(entry.text(name) for name in alternatives):
            missing.append(alternatives[0])
    return missing


def _near_duplicates(entries: list[BibEntry]) -> list[Finding]:
    findings: list[Finding] = []
    seen: dict[tuple[str, str], BibEntry] = {}
    reasons_zh = {"DOI": "DOI", "arXiv ID": "arXiv 编号", "title and year": "标题与年份"}
    for entry in sorted(entries, key=lambda e: (e.file.as_posix(), e.line)):
        signatures: list[tuple[str, str]] = []
        for identifier in extract_identifiers(entry):
            if identifier.scheme == "doi":
                signatures.append(("DOI", identifier.value))
            elif identifier.scheme == "arxiv":
                signatures.append(("arXiv ID", identifier.value))
        title = entry.text("title") or ""
        year = entry.text("year") or (entry.text("date") or "")[:4]
        if title and year and word_count(title) >= 4:
            signatures.append(("title and year", f"{title_key(title)}|{year}"))
        for signature in signatures:
            other = seen.get(signature)
            if other is not None and other.key != entry.key:
                findings.append(
                    make_finding(
                        "CIT004",
                        _entry_location(entry),
                        key=entry.key,
                        related=(_entry_location(other),),
                        other=other.key,
                        reason=signature[0],
                        reason_zh=reasons_zh[signature[0]],
                    )
                )
                break
            seen.setdefault(signature, entry)
    return findings


def _apply_suppressions(findings: list[Finding], entries: dict[str, BibEntry]) -> list[Finding]:
    """Drop findings suppressed by ``% preflight: ignore[RULE]`` comments above their entry.

    Reporting unused suppressions (CFG001) needs every rule to have run, so it lives in the
    full pipeline rather than here.
    """
    kept: list[Finding] = []
    for finding in findings:
        entry = entries.get(finding.key) if finding.key else None
        if entry is not None and entry.suppressed(finding.rule_id):
            continue
        kept.append(finding)
    return kept


def bib_paths_for(project: TexProject, extra: list[Path]) -> list[Path]:
    paths = [r.path for r in project.bib_resources if r.exists]
    for path in extra:
        resolved = path.resolve()
        if resolved not in paths:
            paths.append(resolved)
    return paths
