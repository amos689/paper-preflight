"""Discover a LaTeX project: main file, include graph, citation sites and bibliography files."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from paper_preflight.tex.cites import DEFAULT_COMMANDS, CiteKind, find_citations
from paper_preflight.tex.mask import mask_latex
from paper_preflight.textio import LineIndex, read_text


class ProjectError(Exception):
    """The project cannot be analysed (no main file, ambiguous main file, unreadable input)."""


@dataclass(frozen=True)
class Location:
    file: Path
    line: int  # 1-based
    column: int  # 1-based, in Unicode code points


@dataclass(frozen=True)
class CiteSite:
    key: str
    command: str
    location: Location
    nocite: bool


@dataclass(frozen=True)
class BibResource:
    path: Path
    declared_at: Location
    exists: bool


@dataclass(frozen=True)
class ProjectIssue:
    """Problems found while walking the project (reported as findings by the hygiene layer)."""

    kind: str  # "missing_include" | "include_cycle" | "unreadable_file" | "remote_bib_resource"
    location: Location
    detail: str


@dataclass
class TexProject:
    root: Path
    main: Path
    files: list[Path] = field(default_factory=list)  # in include order, main first
    cite_sites: list[CiteSite] = field(default_factory=list)
    bib_resources: list[BibResource] = field(default_factory=list)
    bib_style: str | None = None
    uses_biblatex: bool = False
    issues: list[ProjectIssue] = field(default_factory=list)
    encodings: dict[Path, str] = field(default_factory=dict)

    @property
    def nocite_all(self) -> bool:
        return any(site.nocite and site.key == "*" for site in self.cite_sites)

    def cited_keys(self) -> set[str]:
        return {site.key for site in self.cite_sites if site.key != "*"}


_DOCUMENTCLASS_RE = re.compile(r"\\documentclass\s*(?:\[[^\]]*\])?\s*\{([^}]*)\}")
_BEGIN_DOCUMENT_RE = re.compile(r"\\begin\s*\{document\}")
_INCLUDE_RE = re.compile(
    r"\\(?P<cmd>input|include|subfile)\s*\{(?P<path>[^}]*)\}"
    r"|\\(?P<icmd>import|subimport|inputfrom|includefrom|subinputfrom|subincludefrom)\*?\s*"
    r"\{(?P<dir>[^}]*)\}\s*\{(?P<ipath>[^}]*)\}"
    r"|\\input\s+(?P<bare>[^\s{}\\%]+)"
)
_INCLUDEONLY_RE = re.compile(r"\\includeonly\s*\{([^}]*)\}")
_BIBLIOGRAPHY_RE = re.compile(r"\\bibliography\s*\{([^}]*)\}")
_ADDBIB_RE = re.compile(
    r"\\(?:addbibresource|addglobalbib|addsectionbib)\s*(?:\[(?P<opts>[^\]]*)\])?\s*\{(?P<path>[^}]*)\}"
)
_BIBSTYLE_RE = re.compile(r"\\bibliographystyle\s*\{([^}]*)\}")
_BIBLATEX_RE = re.compile(r"\\usepackage\s*(?:\[[^\]]*\])?\s*\{[^}]*\bbiblatex\b[^}]*\}")


def _is_main_candidate(path: Path) -> bool:
    try:
        masked = mask_latex(read_text(path).text)
    except OSError:
        return False
    match = _DOCUMENTCLASS_RE.search(masked)
    if not match or match.group(1).strip() == "subfiles":
        return False
    return bool(_BEGIN_DOCUMENT_RE.search(masked))


def find_main_file(target: Path) -> Path:
    """Resolve the main .tex file for a file or directory argument."""
    if target.is_file():
        return target
    if not target.is_dir():
        raise ProjectError(f"No such file or directory: {target}")
    candidates = sorted(p for p in target.glob("*.tex") if _is_main_candidate(p))
    if not candidates:
        raise ProjectError(
            f"No main .tex file (with \\documentclass and \\begin{{document}}) found in {target}. "
            "Pass the main file explicitly."
        )
    if len(candidates) == 1:
        return candidates[0]
    for preferred in ("main.tex", "paper.tex", "ms.tex", "thesis.tex"):
        for candidate in candidates:
            if candidate.name.lower() == preferred:
                return candidate
    names = ", ".join(c.name for c in candidates)
    raise ProjectError(f"Several possible main files ({names}); pass one explicitly with --main.")


def _resolve_tex(base_dirs: list[Path], name: str) -> Path | None:
    name = name.strip().strip('"')
    if not name:
        return None
    for base in base_dirs:
        for candidate in (base / name, base / f"{name}.tex"):
            if candidate.is_file():
                return candidate
    return None


def load_project(
    target: Path,
    main: Path | None = None,
    commands: Mapping[str, CiteKind] = DEFAULT_COMMANDS,
) -> TexProject:
    """Walk the include graph starting at the main file and collect citations and bib files."""
    main_file = (main or find_main_file(target)).resolve()
    root = main_file.parent
    project = TexProject(root=root, main=main_file)
    include_only: set[str] | None = None
    visited: set[Path] = set()

    def walk(path: Path, stack: tuple[Path, ...]) -> None:
        nonlocal include_only
        try:
            source = read_text(path)
        except OSError as exc:
            project.issues.append(ProjectIssue("unreadable_file", Location(path, 1, 1), str(exc)))
            return
        visited.add(path)
        project.files.append(path)
        project.encodings[path] = source.encoding
        masked = mask_latex(source.text)
        index = LineIndex(source.text)

        def loc(offset: int) -> Location:
            line, column = index.position(offset)
            return Location(path, line, column)

        if path == main_file:
            match = _INCLUDEONLY_RE.search(masked)
            if match:
                include_only = {n.strip() for n in match.group(1).split(",") if n.strip()}
            project.uses_biblatex = bool(_BIBLATEX_RE.search(masked))

        for command in find_citations(masked, commands):
            for key in command.keys:
                project.cite_sites.append(
                    CiteSite(key.key, command.command, loc(key.offset), command.is_nocite)
                )

        for match in _BIBSTYLE_RE.finditer(masked):
            project.bib_style = match.group(1).strip()
        for match in _BIBLIOGRAPHY_RE.finditer(masked):
            for name in match.group(1).split(","):
                name = name.strip()
                if name:
                    filename = name if name.lower().endswith(".bib") else f"{name}.bib"
                    _add_bib(project, root, path.parent, filename, loc(match.start()))
        for match in _ADDBIB_RE.finditer(masked):
            options = (match.group("opts") or "").replace(" ", "").lower()
            if "location=remote" in options:
                project.issues.append(
                    ProjectIssue("remote_bib_resource", loc(match.start()), match.group("path"))
                )
                continue
            _add_bib(project, root, path.parent, match.group("path").strip(), loc(match.start()))

        for match in _INCLUDE_RE.finditer(masked):
            if match.group("cmd"):
                name = match.group("path")
                if (
                    match.group("cmd") == "include"
                    and include_only is not None
                    and name.strip().removesuffix(".tex") not in include_only
                ):
                    continue
                bases = [root, path.parent]
            elif match.group("icmd"):
                directory = match.group("dir").strip()
                name = match.group("ipath")
                if match.group("icmd").startswith("sub"):
                    bases = [path.parent / directory]
                else:
                    bases = [root / directory, Path(directory)]
            else:
                name = match.group("bare")
                bases = [root, path.parent]
            child = _resolve_tex(bases, name)
            if child is None:
                project.issues.append(ProjectIssue("missing_include", loc(match.start()), name))
                continue
            child = child.resolve()
            if child in stack:
                project.issues.append(ProjectIssue("include_cycle", loc(match.start()), name))
                continue
            if child in visited:
                continue
            walk(child, (*stack, child))

    walk(main_file, (main_file,))
    return project


def _add_bib(
    project: TexProject, root: Path, current_dir: Path, filename: str, declared_at: Location
) -> None:
    for base in (root, current_dir):
        candidate = (base / filename).resolve()
        if candidate.is_file():
            if all(r.path != candidate for r in project.bib_resources):
                project.bib_resources.append(BibResource(candidate, declared_at, True))
            return
    missing = (root / filename).resolve()
    if all(r.path != missing for r in project.bib_resources):
        project.bib_resources.append(BibResource(missing, declared_at, False))
