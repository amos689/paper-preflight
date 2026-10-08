"""Markdown (Pandoc, Quarto, R Markdown) and Typst manuscripts, read as projects.

They are checked as a LaTeX project is: the keys they cite (Pandoc's ``[@key]`` and ``@key``,
Typst's ``@key`` and ``#cite(<key>)``) against the bibliography files they name (YAML front
matter or ``_quarto.yml``'s ``bibliography:``, Typst's ``#bibliography("refs.bib")``).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from paper_preflight.tex.project import BibResource, CiteSite, Location, ProjectError, TexProject
from paper_preflight.textio import LineIndex, read_text

MARKDOWN = frozenset({".md", ".markdown", ".qmd", ".rmd"})
TYPST = frozenset({".typ"})

# Pandoc's citation key: after a character that is not part of a word (so no e-mail address),
# "@" and a key; trailing punctuation belongs to the sentence
_PANDOC_CITE = re.compile(
    r"(?<![\w@.\\])-?@(?:\{(?P<braced>[^{}\s]+)\}|(?P<key>[\w][\w:.#$%&+?<>~/-]*))"
)
# Quarto's cross-references use the same syntax: @fig-x, @tbl-x, @sec-x ...
_QUARTO_REFERENCE = re.compile(
    r"(?:fig|tbl|sec|eq|lst|thm|lem|cor|prp|cnj|def|exm|exr|nte|tip|wrn|imp|cau)-"
)
_FENCE = re.compile(r"^(```|~~~)")
_INLINE_CODE = re.compile(r"`[^`\n]*`")
_FRONT_MATTER = re.compile(r"\A---[ \t]*\r?\n(.*?)\r?\n(?:---|\.\.\.)[ \t]*(?:\r?\n|\Z)", re.S)
_YAML_KEY = re.compile(r"^bibliography:[ \t]*(.*)$", re.M)
# Quarto's include shortcode: {{< include _setup.qmd >}}
_INCLUDE = re.compile(r"\{\{<\s*include\s+([^\s>]+)\s*>\}\}")

# "@preview/cetz:0.2.0" is a package, not a citation
_TYPST_CITE = re.compile(
    r"(?<![\w@])@(?P<key>[\w][\w:.-]*[\w])(?![\w/])|#cite\(\s*<(?P<label>[^<>\s]+)>"
)
_TYPST_LABEL = re.compile(r"<(?P<label>[\w][\w:.-]*)>")
_TYPST_BIBLIOGRAPHY = re.compile(r"#bibliography\(\s*(\([^()]*\)|\"[^\"]*\")")
_TYPST_COMMENT = re.compile(r"//[^\n]*|/\*.*?\*/", re.S)
_STRING = re.compile(r"\"([^\"]+)\"")


def is_document(path: Path) -> bool:
    return path.suffix.lower() in MARKDOWN | TYPST


def find_document(target: Path) -> Path | None:
    """The manuscript to check: the file given, or in a folder without a LaTeX file, the one
    Markdown or Typst file that names a bibliography (a Quarto project's first chapter)."""
    if target.is_file():
        return target if is_document(target) else None
    if not target.is_dir() or any(target.glob("*.tex")):
        return None
    candidates = sorted(p for p in target.iterdir() if p.is_file() and is_document(p))
    with_bibliography = [p for p in candidates if _declares_bibliography(p)]
    if len(with_bibliography) == 1:
        return with_bibliography[0]
    quarto = target / "_quarto.yml"
    if quarto.is_file() and _yaml_bibliography(
        quarto.read_text(encoding="utf-8", errors="replace")
    ):
        chapters = [p for p in candidates if p.suffix.lower() == ".qmd"]
        if chapters:
            return chapters[0]
    index = [p for p in candidates if p.stem == "index" and p.suffix.lower() == ".rmd"]
    if (target / "_bookdown.yml").is_file() and index:
        return index[0]  # a bookdown book starts at index.Rmd
    if len(with_bibliography) > 1:
        names = ", ".join(p.name for p in with_bibliography)
        raise ProjectError(f"several manuscripts name a bibliography ({names}); give one")
    return None


def _declares_bibliography(path: Path) -> bool:
    try:
        text = read_text(path).text
    except OSError:
        return False
    if path.suffix.lower() in TYPST:
        return bool(_TYPST_BIBLIOGRAPHY.search(_TYPST_COMMENT.sub("", text)))
    front = _FRONT_MATTER.match(text)
    return bool(front and _yaml_bibliography(front.group(1)))


def _yaml_bibliography(yaml: str) -> list[tuple[str, int]]:
    """The files of a YAML ``bibliography:`` key, each with its line: one value, a flow list
    ``[a.bib, b.bib]`` or a block list."""
    match = _YAML_KEY.search(yaml)
    if match is None:
        return []
    line = yaml.count("\n", 0, match.start()) + 1
    value = match.group(1).strip()
    if value:
        names = value.strip("[]").split(",") if value.startswith("[") else [value]
        return [(n.strip().strip("'\""), line) for n in names if n.strip()]
    found = []
    for number, text in enumerate(yaml[match.end() :].splitlines()[1:], start=line + 1):
        item = re.match(r"^\s+-\s*(.+?)\s*$", text)
        if item is None:
            if text.strip():
                break
            continue
        found.append((item.group(1).strip("'\""), number))
    return found


def _resource(name: str, base: Path, at: Location) -> BibResource:
    path = (base / name).resolve()
    return BibResource(path=path, declared_at=at, exists=path.is_file())


def _markdown_sites(path: Path, text: str) -> list[CiteSite]:
    index = LineIndex(text)
    sites = []
    front = _FRONT_MATTER.match(text)
    skip_to = front.end() if front else 0
    in_fence = False
    offset = 0
    for line in text.splitlines(keepends=True):
        start = offset
        offset += len(line)
        if start < skip_to:
            continue
        if _FENCE.match(line.lstrip()):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        visible = _INLINE_CODE.sub(lambda m: " " * len(m.group(0)), line)
        for match in _PANDOC_CITE.finditer(visible):
            key = match.group("braced") or match.group("key").rstrip(".:;,?!")
            if not key or _QUARTO_REFERENCE.match(key):
                continue
            row, column = index.position(start + match.start())
            sites.append(CiteSite(key, "@", Location(path, row, column), nocite=False))
    return sites


def _typst_sites(path: Path, text: str) -> list[CiteSite]:
    index = LineIndex(text)
    # blank out comments and raw blocks, keeping offsets
    hidden = _TYPST_COMMENT.sub(lambda m: re.sub(r"[^\n]", " ", m.group(0)), text)
    hidden = re.sub(r"```.*?```", lambda m: re.sub(r"[^\n]", " ", m.group(0)), hidden, flags=re.S)
    labels = {m.group("label") for m in _TYPST_LABEL.finditer(hidden)}
    sites = []
    for match in _TYPST_CITE.finditer(hidden):
        key = match.group("key") or match.group("label")
        if match.group("key") and key in labels:
            continue  # a reference to a label in the document (@fig:x), not a citation
        row, column = index.position(match.start())
        sites.append(CiteSite(key, "@", Location(path, row, column), nocite=False))
    return sites


def load_document_project(main: Path) -> TexProject:
    main = main.resolve()
    source = read_text(main)
    project = TexProject(root=main.parent, main=main, files=[main])
    project.encodings[main] = source.encoding
    text = source.text
    if main.suffix.lower() in TYPST:
        project.cite_sites = _typst_sites(main, text)
        visible = _TYPST_COMMENT.sub("", text)
        for match in _TYPST_BIBLIOGRAPHY.finditer(visible):
            row = text.count("\n", 0, text.find(match.group(0))) + 1
            for name in _STRING.findall(match.group(1)):
                project.bib_resources.append(_resource(name, main.parent, Location(main, row, 1)))
        return project
    project.cite_sites = _markdown_sites(main, text)
    front = _FRONT_MATTER.match(text)
    declared = _yaml_bibliography(front.group(1)) if front else []
    for name, row in declared:
        project.bib_resources.append(_resource(name, main.parent, Location(main, row + 1, 1)))
    quarto = main.parent / "_quarto.yml"
    documents: list[Path] = []
    if quarto.is_file():
        settings = quarto.read_text(encoding="utf-8", errors="replace")
        config = _yaml(settings)
        if not declared:
            for name, row in _yaml_bibliography(settings) or _nested_bibliography(config, settings):
                project.bib_resources.append(_resource(name, main.parent, Location(quarto, row, 1)))
        # a Quarto book cites across its chapters, wherever they are
        documents = _quarto_documents(config, main.parent)
    bookdown = main.parent / "_bookdown.yml"
    if bookdown.is_file():  # an R Markdown book: its chapters share index.Rmd's bibliography
        config = _yaml(bookdown.read_text(encoding="utf-8", errors="replace"))
        documents += _bookdown_documents(config, main.parent)
    seen = {main}
    for document in [main, *documents]:
        for found in (document, *_included(document)):
            if found in seen:
                continue
            seen.add(found)
            project.files.append(found)
            project.cite_sites += _markdown_sites(found, read_text(found).text)
    return project


def _yaml(text: str) -> Any:
    try:
        return yaml.safe_load(text)
    except yaml.YAMLError:
        return None


def _strings(value: Any, key: str | None = None) -> list[tuple[str | None, str]]:
    """Every string in a YAML document, with the key it is under."""
    if isinstance(value, str):
        return [(key, value)]
    if isinstance(value, dict):
        return [found for k, v in value.items() for found in _strings(v, str(k))]
    if isinstance(value, list):
        return [found for v in value for found in _strings(v, key)]
    return []


def _nested_bibliography(config: Any, source: str) -> list[tuple[str, int]]:
    """``bibliography:`` under another key (``book:``, ``format: html:``), with its line."""
    found = []
    for key, value in _strings(config):
        if key == "bibliography":
            at = source.find(value)
            found.append((value, source.count("\n", 0, at) + 1 if at >= 0 else 1))
    return found


def _quarto_documents(config: Any, base: Path) -> list[Path]:
    """The documents a Quarto project renders: those its _quarto.yml names (a book's chapters
    and appendices, in parts or not, a website's pages), then those at its top level."""
    found: list[Path] = []
    for _key, value in _strings(config):
        if Path(value).suffix.lower() not in MARKDOWN:
            continue
        try:
            paths = sorted(base.glob(value)) if "*" in value else [base / value]
            found += [p.resolve() for p in paths if p.is_file()]
        except (OSError, ValueError, NotImplementedError):  # "/abs/*.qmd", a name too long
            continue
    found += sorted(p.resolve() for p in base.glob("*.qmd"))
    return list(dict.fromkeys(found))


def _bookdown_documents(config: Any, base: Path) -> list[Path]:
    """The chapters of a bookdown book: its ``rmd_files`` (a list, or one per output format),
    else every .Rmd at its top level (and in ``rmd_subdir``) not starting with "_"."""
    config = config if isinstance(config, dict) else {}
    named = [value for _key, value in _strings(config.get("rmd_files"))]
    if named:
        paths = [base / name for name in named]
    else:
        folders = [base]
        subdir = config.get("rmd_subdir")
        if subdir is True:
            folders += sorted(p for p in base.rglob("*") if p.is_dir() and "_" not in p.name[:1])
        elif subdir:
            folders += [base / name for _key, name in _strings(subdir)]
        paths = [
            p
            for folder in folders
            for p in sorted(folder.glob("*.[Rr]md"))
            if not p.name.startswith("_")
        ]
    return list(dict.fromkeys(p.resolve() for p in paths if p.is_file()))


def _included(document: Path, seen: frozenset[Path] = frozenset()) -> list[Path]:
    """The files a document includes ({{< include >}}), and theirs, relative to each file."""
    try:
        text = read_text(document).text
    except OSError:
        return []
    found: list[Path] = []
    for match in _INCLUDE.finditer(text):
        path = (document.parent / match.group(1)).resolve()
        if path.is_file() and path not in seen | {document, *found}:
            found.append(path)
            found += [p for p in _included(path, seen | {document, *found}) if p not in found]
    return found
