import os
import time
from pathlib import Path

import pytest

from paper_preflight.tex.auxdata import find_build_data, read_aux, read_bcf
from paper_preflight.tex.project import ProjectError, find_main_file, load_project


def write(path: Path, text: str, encoding: str = "utf-8") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode(encoding))
    return path


@pytest.fixture
def project_dir(tmp_path: Path) -> Path:
    root = tmp_path / "论文 project"  # non-ASCII path with a space
    write(
        root / "main.tex",
        "\n".join(
            [
                r"\documentclass{article}",
                r"\usepackage[numbers]{natbib}",
                r"\includeonly{chapters/one}",
                r"\begin{document}",
                r"Intro \citep{a,b}.",
                r"\input{sections/intro}",
                r"\include{chapters/one}",
                r"\include{chapters/two}",
                r"\subimport{parts/}{deep}",
                r"\input{missing_file}",
                r"% \input{commented_out}",
                r"\bibliographystyle{plainnat}",
                r"\bibliography{refs,extra}",
                r"\end{document}",
            ]
        ),
    )
    write(root / "sections" / "intro.tex", r"Background \citet{c}. \input{sections/loop}")
    write(root / "sections" / "loop.tex", r"\input{sections/intro} \cite{d}")
    write(root / "chapters" / "one.tex", r"One \cite{e}")
    write(root / "chapters" / "two.tex", r"Two \cite{excluded_by_includeonly}")
    write(root / "parts" / "deep.tex", r"Deep \cite{f} \input{leaf}")
    write(root / "parts" / "leaf.tex", "叶子节点 \\cite{g}", encoding="gb18030")
    write(root / "refs.bib", "@misc{a, title={A}}\n")
    return root


def test_load_project_walks_includes(project_dir: Path) -> None:
    project = load_project(project_dir)
    assert project.main.name == "main.tex"
    assert [s.key for s in project.cite_sites] == ["a", "b", "c", "d", "e", "f", "g"]
    names = [p.name for p in project.files]
    assert names == ["main.tex", "intro.tex", "loop.tex", "one.tex", "deep.tex", "leaf.tex"]
    assert project.bib_style == "plainnat"
    assert [(r.path.name, r.exists) for r in project.bib_resources] == [
        ("refs.bib", True),
        ("extra.bib", False),
    ]
    kinds = sorted(issue.kind for issue in project.issues)
    assert kinds == ["include_cycle", "missing_include"]
    leaf = next(p for p in project.files if p.name == "leaf.tex")
    assert project.encodings[leaf] == "gb18030"


def test_cite_site_locations(project_dir: Path) -> None:
    project = load_project(project_dir)
    site = next(s for s in project.cite_sites if s.key == "b")
    location = site.location
    assert (location.file.name, location.line, location.column) == ("main.tex", 5, 16)
    assert site.command == "citep"


def test_find_main_file_prefers_main_and_rejects_ambiguity(tmp_path: Path) -> None:
    doc = "\\documentclass{article}\n\\begin{document}x\\end{document}"
    write(tmp_path / "a.tex", doc)
    write(tmp_path / "b.tex", doc)
    with pytest.raises(ProjectError, match="Several possible main files"):
        find_main_file(tmp_path)
    write(tmp_path / "main.tex", doc)
    assert find_main_file(tmp_path).name == "main.tex"
    subfile = "\\documentclass[main.tex]{subfiles}\n\\begin{document}\\end{document}"
    write(tmp_path / "sub.tex", subfile)
    assert find_main_file(tmp_path).name == "main.tex"


def test_no_main_file(tmp_path: Path) -> None:
    write(tmp_path / "notes.tex", "just text")
    with pytest.raises(ProjectError, match="No main"):
        find_main_file(tmp_path)


def test_biblatex_remote_resource_and_nocite_all(tmp_path: Path) -> None:
    write(
        tmp_path / "main.tex",
        "\n".join(
            [
                r"\documentclass{article}",
                r"\usepackage[style=numeric]{biblatex}",
                r"\addbibresource{refs.bib}",
                r"\addbibresource[location=remote]{https://example.org/x.bib}",
                r"\begin{document}\nocite{*}\autocite{a}\end{document}",
            ]
        ),
    )
    write(tmp_path / "refs.bib", "")
    project = load_project(tmp_path)
    assert project.uses_biblatex
    assert project.nocite_all
    assert project.cited_keys() == {"a"}
    assert [i.kind for i in project.issues] == ["remote_bib_resource"]


def test_read_aux_follows_included_aux(tmp_path: Path) -> None:
    write(
        tmp_path / "main.aux",
        "\\relax\n\\citation{a,b}\n\\citation{*}\n\\@input{chap.aux}\n"
        "\\bibdata{refs,extra}\n\\bibstyle{plainnat}\n",
    )
    write(tmp_path / "chap.aux", "\\citation{c}\n\\abx@aux@cite{0}{d}\n\\abx@aux@cite{old}\n")
    data = read_aux(tmp_path / "main.aux")
    assert data.cited_keys == {"a", "b", "c", "d", "old"}
    assert data.nocite_all
    assert data.bib_data == ["refs", "extra"]
    assert data.bib_style == "plainnat"


def test_read_bcf(tmp_path: Path) -> None:
    write(
        tmp_path / "main.bcf",
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<bcf:controlfile version="3.11" xmlns:bcf="https://sourceforge.net/projects/biblatex">'
        '<bcf:bibdata section="0"><bcf:datasource type="file" datatype="bibtex">refs.bib'
        "</bcf:datasource></bcf:bibdata>"
        '<bcf:section number="0"><bcf:citekey order="1">x</bcf:citekey>'
        '<bcf:citekey order="2">y</bcf:citekey></bcf:section></bcf:controlfile>',
    )
    data = read_bcf(tmp_path / "main.bcf")
    assert data.cited_keys == {"x", "y"}
    assert data.bib_data == ["refs.bib"]


def test_find_build_data_ignores_stale_aux(tmp_path: Path) -> None:
    tex = write(tmp_path / "main.tex", "x")
    aux = write(tmp_path / "main.aux", "\\citation{a}\n")
    old = time.time() - 3600
    os.utime(aux, (old, old))
    assert find_build_data(tex, [tex]) is None
    os.utime(aux, None)
    os.utime(tex, (old, old))
    data = find_build_data(tex, [tex])
    assert data is not None
    assert data.cited_keys == {"a"}
