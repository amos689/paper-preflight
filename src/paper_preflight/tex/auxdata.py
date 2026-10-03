"""Read the authoritative set of cited keys from LaTeX build artefacts.

After a compilation, ``.aux`` (BibTeX/natbib) or ``.bcf`` (biblatex) files list exactly which keys
were cited, including citations produced through macros or conditionals that a static scan of the
sources cannot resolve. When such a file is present and newer than every source file, we trust it
for the "which keys are cited" question; source scanning still provides the locations.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

from paper_preflight.textio import read_text

_CITATION_RE = re.compile(r"\\citation\{([^}]*)\}")
_BIBDATA_RE = re.compile(r"\\bibdata\{([^}]*)\}")
_BIBSTYLE_RE = re.compile(r"\\bibstyle\{([^}]*)\}")
_INPUT_RE = re.compile(r"\\@input\{([^}]*)\}")
# biblatex: \abx@aux@cite{<refsection>}{<key>} (current) or \abx@aux@cite{<key>} (old versions)
_ABX_CITE_RE = re.compile(r"\\abx@aux@cite\{([^}]*)\}(?:\{([^}]*)\})?")

_BCF_NS = "{https://sourceforge.net/projects/biblatex}"


@dataclass
class AuxData:
    source: Path
    cited_keys: set[str] = field(default_factory=set)
    nocite_all: bool = False
    bib_data: list[str] = field(default_factory=list)
    bib_style: str | None = None


def _split(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


def read_aux(aux_path: Path, _seen: set[Path] | None = None) -> AuxData:
    """Parse a BibTeX/biblatex ``.aux`` file, following ``\\@input`` of included chapters."""
    seen = _seen if _seen is not None else set()
    seen.add(aux_path.resolve())
    data = AuxData(source=aux_path)
    text = read_text(aux_path).text
    for match in _CITATION_RE.finditer(text):
        for key in _split(match.group(1)):
            if key == "*":
                data.nocite_all = True
            else:
                data.cited_keys.add(key)
    for match in _ABX_CITE_RE.finditer(text):
        key = (match.group(2) if match.group(2) is not None else match.group(1)).strip()
        if key == "*":
            data.nocite_all = True
        elif key:
            data.cited_keys.add(key)
    for match in _BIBDATA_RE.finditer(text):
        data.bib_data.extend(_split(match.group(1)))
    style = _BIBSTYLE_RE.search(text)
    if style:
        data.bib_style = style.group(1).strip()
    for match in _INPUT_RE.finditer(text):
        child = (aux_path.parent / match.group(1).strip()).resolve()
        if child.is_file() and child not in seen:
            nested = read_aux(child, seen)
            data.cited_keys |= nested.cited_keys
            data.nocite_all |= nested.nocite_all
    return data


def read_bcf(bcf_path: Path) -> AuxData:
    """Parse a biblatex control file (XML) for cite keys and data sources."""
    data = AuxData(source=bcf_path)
    root = ET.parse(bcf_path).getroot()
    for element in root.iter(f"{_BCF_NS}citekey"):
        key = (element.text or "").strip()
        if key == "*":
            data.nocite_all = True
        elif key:
            data.cited_keys.add(key)
    for element in root.iter(f"{_BCF_NS}datasource"):
        if element.get("type", "file") == "file" and element.text:
            data.bib_data.append(element.text.strip())
    return data


def find_build_data(main_tex: Path, source_files: list[Path]) -> AuxData | None:
    """Return build data if a fresh ``.bcf`` or ``.aux`` exists next to the main file.

    "Fresh" means not older than any source file; stale artefacts would misreport which keys
    are cited, so they are ignored.
    """
    newest_source = max((p.stat().st_mtime for p in source_files if p.exists()), default=0.0)
    for suffix, reader in ((".bcf", read_bcf), (".aux", read_aux)):
        candidate = main_tex.with_suffix(suffix)
        if candidate.is_file() and candidate.stat().st_mtime >= newest_source:
            try:
                return reader(candidate)
            except (OSError, ET.ParseError):
                continue
    return None
