"""Markdown (Pandoc, Quarto, R Markdown) and Typst manuscripts checked as projects."""

import json
from pathlib import Path

import pytest

from paper_preflight.check import run_check
from paper_preflight.tex.documents import find_document, load_document_project
from paper_preflight.tex.project import ProjectError

BIB = """@article{lecun2015deep,
  title = {Deep learning},
  author = {LeCun, Yann and Bengio, Yoshua and Hinton, Geoffrey},
  journal = {Nature},
  year = {2015},
}
@inproceedings{kingma2015adam,
  title = {Adam: A Method for Stochastic Optimization},
  author = {Kingma, Diederik P. and Ba, Jimmy},
  booktitle = {ICLR},
  year = {2015},
}
@misc{unused2020,
  title = {Never Cited},
  author = {Nobody, Ann},
  year = {2020},
}
"""

MARKDOWN = """---
title: "A paper"
bibliography: refs.bib
---

Deep networks [@lecun2015deep; see @kingma2015adam, p. 3] work. As @lecun2015deep showed,
and as [-@missing2021] did not. See @fig-results and @sec-intro.

Write to me@example.org. Inline `@notacite` and

```python
x = "@neither"
```
"""


def keys(project) -> list[str]:
    return [site.key for site in project.cite_sites]


def test_a_markdown_manuscript(tmp_path: Path) -> None:
    (tmp_path / "refs.bib").write_text(BIB, encoding="utf-8")
    paper = tmp_path / "paper.md"
    paper.write_text(MARKDOWN, encoding="utf-8")
    project = load_document_project(paper)
    assert keys(project) == ["lecun2015deep", "kingma2015adam", "lecun2015deep", "missing2021"]
    assert [r.path.name for r in project.bib_resources] == ["refs.bib"]
    assert project.cite_sites[0].location.line == 6
    result = run_check(paper)  # offline hygiene: an undefined key, an uncited entry
    rules = {(f.rule_id, f.key) for f in result.findings}
    assert ("CIT001", "missing2021") in rules
    assert result.cited_keys == 3
    assert find_document(tmp_path) == paper  # the folder: its one manuscript with a bibliography


def test_a_block_list_of_bibliographies_in_csl_json_and_ris(tmp_path: Path) -> None:
    (tmp_path / "a.json").write_text(
        json.dumps([{"id": "lecun2015deep", "type": "article-journal", "title": "Deep learning"}]),
        encoding="utf-8",
    )
    (tmp_path / "b.ris").write_text(
        "TY  - JOUR\nID  - adam\nTI  - Adam: A Method for Stochastic Optimization\nER  - \n",
        encoding="utf-8",
    )
    paper = tmp_path / "paper.qmd"
    paper.write_text(
        "---\nbibliography:\n  - a.json\n  - 'b.ris'\n---\n\n[@lecun2015deep] and @adam.\n",
        encoding="utf-8",
    )
    result = run_check(paper)
    assert result.entries == 2
    assert not [f for f in result.findings if f.rule_id == "CIT001"]


def test_a_quarto_book(tmp_path: Path) -> None:
    (tmp_path / "refs.bib").write_text(BIB, encoding="utf-8")
    (tmp_path / "_quarto.yml").write_text(
        "project:\n  type: book\nbibliography: refs.bib\n", encoding="utf-8"
    )
    (tmp_path / "index.qmd").write_text("# Preface\n\nSee [@lecun2015deep].\n", encoding="utf-8")
    (tmp_path / "methods.qmd").write_text("We use @kingma2015adam.\n", encoding="utf-8")
    document = find_document(tmp_path)
    assert document is not None
    project = load_document_project(document)
    assert sorted(keys(project)) == ["kingma2015adam", "lecun2015deep"]
    assert [r.path.name for r in project.bib_resources] == ["refs.bib"]


def test_a_quarto_book_with_chapters_in_folders(tmp_path: Path) -> None:
    # chapters in parts and folders, an include, the bibliography under "book:"
    (tmp_path / "refs.bib").write_text(BIB, encoding="utf-8")
    (tmp_path / "_quarto.yml").write_text(
        "project:\n  type: book\nbook:\n  bibliography: refs.bib\n  chapters:\n"
        "    - index.qmd\n    - part: Basics\n      chapters:\n"
        "        - chapters/one/intro.qmd\n  appendices:\n    - chapters/solutions.qmd\n",
        encoding="utf-8",
    )
    (tmp_path / "index.qmd").write_text("# Preface\n", encoding="utf-8")
    (tmp_path / "chapters" / "one").mkdir(parents=True)
    (tmp_path / "chapters" / "one" / "intro.qmd").write_text(
        "See [@lecun2015deep].\n\n{{< include ../_common.qmd >}}\n", encoding="utf-8"
    )
    (tmp_path / "chapters" / "_common.qmd").write_text("As @kingma2015adam.\n", encoding="utf-8")
    (tmp_path / "chapters" / "solutions.qmd").write_text("[@lecun2015deep]\n", encoding="utf-8")
    project = load_document_project(tmp_path / "index.qmd")
    assert sorted(keys(project)) == ["kingma2015adam", "lecun2015deep", "lecun2015deep"]
    assert [r.path.name for r in project.bib_resources] == ["refs.bib"]
    assert project.bib_resources[0].declared_at.line == 4
    assert len(project.files) == 4


def test_a_bookdown_book(tmp_path: Path) -> None:
    (tmp_path / "book.bib").write_text(BIB, encoding="utf-8")
    (tmp_path / "_bookdown.yml").write_text(
        'rmd_files: ["index.Rmd", "02-methods.Rmd"]\n', encoding="utf-8"
    )
    (tmp_path / "index.Rmd").write_text(
        "---\nbibliography: [book.bib]\n---\n\n# Preface\n\nSee \\@ref(fig:x).\n",
        encoding="utf-8",
    )
    (tmp_path / "02-methods.Rmd").write_text(
        "We use @kingma2015adam.\n\n```{r}\nx <- 1 # @lecun2015deep\n```\n", encoding="utf-8"
    )
    (tmp_path / "99-unused.Rmd").write_text("[@lecun2015deep]\n", encoding="utf-8")
    document = find_document(tmp_path)
    assert document is not None
    assert document.name == "index.Rmd"
    project = load_document_project(document)
    assert keys(project) == ["kingma2015adam"]  # the files named, code chunks left out
    (tmp_path / "_bookdown.yml").write_text("new_session: yes\n", encoding="utf-8")
    assert sorted(keys(load_document_project(document))) == ["kingma2015adam", "lecun2015deep"]


TYPST = """#import "@preview/cetz:0.2.0": canvas
#set page(paper: "a4")
// @commented out
= Introduction <intro>
Deep learning @lecun2015deep works, as in @intro and #cite(<kingma2015adam>).
See @missing2021.

#bibliography("refs.bib")
"""


def test_a_typst_manuscript(tmp_path: Path) -> None:
    (tmp_path / "refs.bib").write_text(BIB, encoding="utf-8")
    paper = tmp_path / "paper.typ"
    paper.write_text(TYPST, encoding="utf-8")
    project = load_document_project(paper)
    assert keys(project) == ["lecun2015deep", "kingma2015adam", "missing2021"]
    assert [r.path.name for r in project.bib_resources] == ["refs.bib"]
    assert project.bib_resources[0].declared_at.line == 8
    result = run_check(tmp_path)
    assert ("CIT001", "missing2021") in {(f.rule_id, f.key) for f in result.findings}


HAYAGRIVA = """# Typst's own bibliography format
lecun2015deep:
  type: article
  title: Deep learning
  author: ["LeCun, Yann", "Bengio, Yoshua", "Hinton, Geoffrey"]
  date: 2015-05-28
  page-range: 436-444
  serial-number:
    doi: 10.1038/nature14539
  parent:
    type: periodical
    title: Nature
    volume: 521

2015-adam:
  type: article
  title: "Adam: A Method for Stochastic Optimization"
  author:
    - name: Kingma
      given-name: Diederik P.
    - Ba, Jimmy
  date: 2015
  parent:
    type: proceedings
    title: International Conference on Learning Representations
  serial-number:
    arxiv: "1412.6980"
"""


def test_a_typst_manuscript_with_a_hayagriva_bibliography(tmp_path: Path) -> None:
    (tmp_path / "works.yml").write_text(HAYAGRIVA, encoding="utf-8")
    paper = tmp_path / "paper.typ"
    paper.write_text(
        'Deep nets @lecun2015deep and @2015-adam.\n#bibliography("works.yml")\n', encoding="utf-8"
    )
    result = run_check(paper)
    (bib,) = result.bib_files
    lecun, adam = bib.entries
    assert (lecun.key, adam.key) == ("lecun2015deep", "2015-adam")  # keys kept as written
    assert (lecun.line, adam.line) == (2, 15)
    assert lecun.text("journal") == "Nature"
    assert lecun.text("doi") == "10.1038/nature14539"
    assert (adam.entry_type, adam.text("eprint")) == ("inproceedings", "1412.6980")
    assert "Kingma" in (adam.text("author") or "")
    assert not [f for f in result.findings if f.rule_id == "CIT001"]


def test_pandoc_csl_yaml(tmp_path: Path) -> None:
    (tmp_path / "refs.yaml").write_text(
        "references:\n- id: 1999-knuth\n  type: book\n  title: The Art of Computer Programming\n"
        "  author:\n  - family: Knuth\n    given: Donald\n  issued:\n    date-parts: [[1997]]\n",
        encoding="utf-8",
    )
    paper = tmp_path / "paper.md"
    paper.write_text("---\nbibliography: refs.yaml\n---\n\nSee @1999-knuth.\n", encoding="utf-8")
    result = run_check(paper)
    assert [e.key for e in result.bib_files[0].entries] == ["1999-knuth"]
    assert not [f for f in result.findings if f.rule_id == "CIT001"]


def test_latex_wins_and_two_manuscripts_need_a_choice(tmp_path: Path) -> None:
    (tmp_path / "a.md").write_text("---\nbibliography: r.bib\n---\n", encoding="utf-8")
    (tmp_path / "b.md").write_text("---\nbibliography: r.bib\n---\n", encoding="utf-8")
    with pytest.raises(ProjectError):
        find_document(tmp_path)
    (tmp_path / "main.tex").write_text("\\documentclass{article}", encoding="utf-8")
    assert find_document(tmp_path) is None
