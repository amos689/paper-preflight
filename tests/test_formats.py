"""The same works, written in every bibliography format read, are read the same."""

import json
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

import pytest

from paper_preflight.bib.csl import parse_csl_json_file
from paper_preflight.bib.docx import parse_docx_file
from paper_preflight.bib.ids import extract_identifiers
from paper_preflight.bib.parse import BibFile, parse_bib_file
from paper_preflight.bib.ris import parse_ris_file
from paper_preflight.bib.yamlbib import parse_yaml_bibliography

BIBTEX = r"""
@article{lecun2015deep,
  author = {LeCun, Yann and Bengio, Yoshua and Hinton, Geoffrey},
  title = {Deep learning},
  journal = {Nature},
  volume = {521},
  pages = {436--444},
  year = {2015},
  doi = {10.1038/nature14539},
}
@inproceedings{vaswani2017attention,
  author = {Vaswani, Ashish and Shazeer, Noam and Parmar, Niki},
  title = {Attention Is All You Need},
  booktitle = {Advances in Neural Information Processing Systems},
  year = {2017},
  eprint = {1706.03762},
  archiveprefix = {arXiv},
}
@book{goodfellow2016deep,
  author = {Goodfellow, Ian and Bengio, Yoshua and Courville, Aaron},
  title = {Deep Learning},
  publisher = {MIT Press},
  year = {2016},
}
"""

CSL = [
    {
        "id": "lecun2015deep",
        "type": "article-journal",
        "title": "Deep learning",
        "container-title": "Nature",
        "volume": "521",
        "page": "436-444",
        "DOI": "10.1038/nature14539",
        "author": [
            {"family": "LeCun", "given": "Yann"},
            {"family": "Bengio", "given": "Yoshua"},
            {"family": "Hinton", "given": "Geoffrey"},
        ],
        "issued": {"date-parts": [[2015, 5, 28]]},
    },
    {
        "id": "vaswani2017attention",
        "type": "paper-conference",
        "title": "Attention Is All You Need",
        "container-title": "Advances in Neural Information Processing Systems",
        "number": "arXiv:1706.03762",
        "author": [
            {"family": "Vaswani", "given": "Ashish"},
            {"family": "Shazeer", "given": "Noam"},
            {"family": "Parmar", "given": "Niki"},
        ],
        "issued": {"date-parts": [[2017]]},
    },
    {
        "id": "goodfellow2016deep",
        "type": "book",
        "title": "Deep Learning",
        "publisher": "MIT Press",
        "author": [
            {"family": "Goodfellow", "given": "Ian"},
            {"family": "Bengio", "given": "Yoshua"},
            {"family": "Courville", "given": "Aaron"},
        ],
        "issued": {"date-parts": [[2016]]},
    },
]

RIS = """TY  - JOUR
ID  - lecun2015deep
AU  - LeCun, Yann
AU  - Bengio, Yoshua
AU  - Hinton, Geoffrey
TI  - Deep learning
T2  - Nature
PY  - 2015/05/28/
VL  - 521
SP  - 436
EP  - 444
DO  - 10.1038/nature14539
ER  -

TY  - CPAPER
ID  - vaswani2017attention
AU  - Vaswani, Ashish
AU  - Shazeer, Noam
AU  - Parmar, Niki
TI  - Attention Is All You Need
T2  - Advances in Neural Information Processing Systems
PY  - 2017
UR  - https://arxiv.org/abs/1706.03762
ER  -

TY  - BOOK
ID  - goodfellow2016deep
AU  - Goodfellow, Ian
AU  - Bengio, Yoshua
AU  - Courville, Aaron
TI  - Deep Learning
PB  - MIT Press
PY  - 2016
ER  -
"""

HAYAGRIVA = """lecun2015deep:
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
vaswani2017attention:
  type: article
  title: Attention Is All You Need
  author: ["Vaswani, Ashish", "Shazeer, Noam", "Parmar, Niki"]
  date: 2017
  serial-number:
    arxiv: "1706.03762"
  parent:
    type: proceedings
    title: Advances in Neural Information Processing Systems
goodfellow2016deep:
  type: book
  title: Deep Learning
  author: ["Goodfellow, Ian", "Bengio, Yoshua", "Courville, Aaron"]
  date: 2016
  publisher: MIT Press
"""


def _docx(path: Path) -> Path:
    """Zotero's field codes, one citation per work."""
    body = ""
    for item in CSL:
        cited = {"citationItems": [{"id": 1, "uris": [item["id"]], "itemData": item}]}
        instruction = "ADDIN ZOTERO_ITEM CSL_CITATION " + json.dumps(cited)
        body += (
            '<w:p><w:r><w:fldChar w:fldCharType="begin"/></w:r>'
            f"<w:r><w:instrText>{escape(instruction)}</w:instrText></w:r>"
            '<w:r><w:fldChar w:fldCharType="separate"/></w:r><w:r><w:t>(x)</w:t></w:r>'
            '<w:r><w:fldChar w:fldCharType="end"/></w:r></w:p>'
        )
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(
            "word/document.xml",
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            f"<w:body>{body}</w:body></w:document>",
        )
    return path


def _read(fmt: str, tmp_path: Path) -> BibFile:
    if fmt == "bib":
        (tmp_path / "refs.bib").write_text(BIBTEX, encoding="utf-8")
        return parse_bib_file(tmp_path / "refs.bib")
    if fmt == "csl-json":
        (tmp_path / "refs.json").write_text(json.dumps(CSL), encoding="utf-8")
        return parse_csl_json_file(tmp_path / "refs.json")
    if fmt == "csl-yaml":
        import yaml

        (tmp_path / "refs.yaml").write_text(yaml.safe_dump({"references": CSL}), encoding="utf-8")
        return parse_yaml_bibliography(tmp_path / "refs.yaml")
    if fmt == "ris":
        (tmp_path / "refs.ris").write_text(RIS, encoding="utf-8")
        return parse_ris_file(tmp_path / "refs.ris")
    if fmt == "hayagriva":
        (tmp_path / "refs.yml").write_text(HAYAGRIVA, encoding="utf-8")
        return parse_yaml_bibliography(tmp_path / "refs.yml")
    return parse_docx_file(_docx(tmp_path / "paper.docx"))


def _as_read(bib: BibFile) -> list[tuple[object, ...]]:
    from paper_preflight.match import EntryInfo

    read = []
    for entry in bib.entries:
        info = EntryInfo.from_entry(entry)
        read.append(
            (
                info.title,
                tuple((p.family, p.given) for p in info.authors.people),
                info.year,
                info.venue,
                info.entry_type,
                sorted(str(i) for i in extract_identifiers(entry)),
            )
        )
    return read


@pytest.mark.parametrize("fmt", ["csl-json", "csl-yaml", "ris", "hayagriva", "docx"])
def test_every_format_reads_as_bibtex_does(fmt: str, tmp_path: Path) -> None:
    expected = _as_read(_read("bib", tmp_path))
    assert _as_read(_read(fmt, tmp_path)) == expected
