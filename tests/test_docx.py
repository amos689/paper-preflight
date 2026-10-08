"""Word manuscripts (.docx) and CSL-JSON: built here as the tools write them, read back."""

import base64
import json
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

from paper_preflight.bib.csl import csl_fields, parse_csl_json_file
from paper_preflight.bib.docx import parse_docx_file
from paper_preflight.bib.ids import extract_identifiers
from paper_preflight.bib.ris import parse_ris_file
from paper_preflight.check import run_check
from paper_preflight.match import EntryInfo

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
B = "http://schemas.openxmlformats.org/officeDocument/2006/bibliography"

LECUN = {
    "id": "http://zotero.org/users/1/items/ABCD1234",
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
}
ADAM = {
    "id": "kingma2015adam",
    "type": "paper-conference",
    "title": "Adam: A Method for Stochastic Optimization",
    "container-title": "International Conference on Learning Representations",
    "author": [{"family": "Kingma", "given": "Diederik P."}, {"family": "Ba", "given": "Jimmy"}],
    "issued": {"date-parts": [["2015"]]},
}


def paragraph(text: str, style: str = "") -> str:
    props = f'<w:pPr><w:pStyle w:val="{style}"/></w:pPr>' if style else ""
    return f"<w:p>{props}<w:r><w:t>{escape(text)}</w:t></w:r></w:p>"


def field(instruction: str, shown: str, data: str = "") -> str:
    """A field as Word stores it: the instruction split over runs, then the text it shows."""
    begin = f"<w:fldData>{data}</w:fldData>" if data else ""
    half = len(instruction) // 2
    parts = (instruction[:half], instruction[half:])
    runs = "".join(f"<w:r><w:instrText>{escape(p)}</w:instrText></w:r>" for p in parts)
    return (
        f'<w:p><w:r><w:fldChar w:fldCharType="begin">{begin}</w:fldChar></w:r>{runs}'
        f'<w:r><w:fldChar w:fldCharType="separate"/></w:r><w:r><w:t>{escape(shown)}</w:t></w:r>'
        f'<w:r><w:fldChar w:fldCharType="end"/></w:r></w:p>'
    )


def docx(tmp_path: Path, body: str, parts: dict[str, str] | None = None) -> Path:
    path = tmp_path / "paper.docx"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(
            "word/document.xml",
            f'<w:document xmlns:w="{W}"><w:body>{body}</w:body></w:document>',
        )
        for name, xml in (parts or {}).items():
            archive.writestr(name, xml)
    return path


def zotero(*items: dict[str, object]) -> str:
    cited = [{"id": 1, "uris": [str(i["id"])], "itemData": i} for i in items]
    return "ADDIN ZOTERO_ITEM CSL_CITATION " + json.dumps({"citationItems": cited})


def test_zotero_citations_are_read_as_the_manager_holds_them(tmp_path: Path) -> None:
    body = (
        paragraph("Introduction", "Heading1")
        + field(zotero(LECUN), "(LeCun et al., 2015)")
        + paragraph("More text.")
        + field(zotero(LECUN, ADAM), "(LeCun et al., 2015; Kingma & Ba, 2015)")
    )
    bib = parse_docx_file(docx(tmp_path, body))
    assert bib.derived
    assert [e.key for e in bib.entries] == ["ref1", "kingma2015adam"]  # once each, cited twice
    lecun, adam = bib.entries
    assert (lecun.line, adam.line) == (2, 4)  # the paragraph each is first cited in
    info = EntryInfo.from_entry(lecun)
    assert (info.title, info.year, info.venue) == ("Deep learning", 2015, "Nature")
    assert [p.family for p in info.authors.people] == ["LeCun", "Bengio", "Hinton"]
    assert [str(i) for i in extract_identifiers(lecun)] == ["doi:10.1038/nature14539"]
    assert adam.entry_type == "inproceedings"


def test_mendeley_citations(tmp_path: Path) -> None:
    instruction = "ADDIN CSL_CITATION " + json.dumps(
        {
            "citationItems": [
                {"id": "x", "itemData": {**ADAM, "id": "5d0c2a1e-1111-2222-3333-444455556666"}}
            ]
        }
    )
    (entry,) = parse_docx_file(docx(tmp_path, field(instruction, "[1]"))).entries
    assert entry.key == "ref1"  # Mendeley's UUID is no citation key
    assert EntryInfo.from_entry(entry).title == "Adam: A Method for Stochastic Optimization"
    # nor its numbering of each citation's items, "ITEM-1" every time
    cited = [
        {"citationItems": [{"id": "ITEM-1", "itemData": {**i, "id": "ITEM-1"}}]}
        for i in (ADAM, LECUN)
    ]
    fields = "".join(field("ADDIN CSL_CITATION " + json.dumps(c), "[1]") for c in cited)
    assert [e.key for e in parse_docx_file(docx(tmp_path, fields)).entries] == ["ref1", "ref2"]


ENDNOTE = (
    "<EndNote><Cite><Author>He</Author><Year>2016</Year><RecNum>7</RecNum><record>"
    '<rec-number>7</rec-number><ref-type name="Conference Proceedings">10</ref-type>'
    '<contributors><authors><author><style face="normal">He, Kaiming</style></author>'
    "<author>Zhang, Xiangyu</author></authors></contributors>"
    '<titles><title><style face="normal">Deep Residual Learning for Image Recognition</style>'
    "</title><secondary-title>CVPR</secondary-title></titles><pages>770-778</pages>"
    "<dates><year>2016</year></dates><electronic-resource-num>10.1109/CVPR.2016.90"
    "</electronic-resource-num></record></Cite></EndNote>"
)


def test_endnote_citations_in_the_instruction_or_its_data(tmp_path: Path) -> None:
    (inline,) = parse_docx_file(docx(tmp_path, field("ADDIN EN.CITE " + ENDNOTE, "[1]"))).entries
    data = base64.b64encode(ENDNOTE.encode()).decode()
    (encoded,) = parse_docx_file(
        docx(tmp_path, field("ADDIN EN.CITE.DATA ", "", data=data))
    ).entries
    for entry in (inline, encoded):
        info = EntryInfo.from_entry(entry)
        assert info.title == "Deep Residual Learning for Image Recognition"
        assert [p.family for p in info.authors.people] == ["He", "Zhang"]
        assert (info.venue, info.year, entry.entry_type) == ("CVPR", 2016, "inproceedings")
        assert [str(i) for i in extract_identifiers(entry)] == ["doi:10.1109/cvpr.2016.90"]


def test_words_own_source_manager(tmp_path: Path) -> None:
    sources = (
        f'<b:Sources xmlns:b="{B}"><b:Source><b:Tag>Vas17</b:Tag>'
        "<b:SourceType>ConferenceProceedings</b:SourceType>"
        "<b:Title>Attention Is All You Need</b:Title><b:Year>2017</b:Year>"
        "<b:ConferenceName>NeurIPS</b:ConferenceName><b:Author><b:Author><b:NameList>"
        "<b:Person><b:Last>Vaswani</b:Last><b:First>Ashish</b:First></b:Person>"
        "</b:NameList></b:Author></b:Author></b:Source></b:Sources>"
    )
    path = docx(tmp_path, paragraph("Text (Vaswani 2017)."), {"customXml/item1.xml": sources})
    (entry,) = parse_docx_file(path).entries
    assert entry.key == "Vas17"
    info = EntryInfo.from_entry(entry)
    assert (info.title, info.venue, info.year) == ("Attention Is All You Need", "NeurIPS", 2017)


def test_a_typed_reference_list_after_its_heading(tmp_path: Path) -> None:
    body = (
        paragraph("Results are good [1].")
        + paragraph("References", "Heading1")
        + paragraph(
            "[1] K. He, X. Zhang, S. Ren, and J. Sun, “Deep residual learning for image "
            "recognition,” in Proc. CVPR, 2016, pp. 770–778."
        )
        + paragraph(
            "[2] Y. LeCun, Y. Bengio, and G. Hinton, “Deep learning,” Nature, vol. 521, "
            "pp. 436–444, 2015."
        )
        + paragraph("Appendix", "Heading1")
        + paragraph("[3] Not a reference, just text in the appendix.")
    )
    bib = parse_docx_file(docx(tmp_path, body))
    titles = [EntryInfo.from_entry(e).title for e in bib.entries]
    assert titles == ["Deep residual learning for image recognition", "Deep learning"]
    assert [e.line for e in bib.entries] == [3, 4]  # paragraph numbers


def test_a_typed_list_ends_where_references_do(tmp_path: Path) -> None:
    # headings are often bold text only: the list stops at a caption, a table, or text
    table = "<w:tbl><w:tr><w:tc>" + paragraph("Diet 2015 2016") + "</w:tc></w:tr></w:tbl>"
    body = (
        paragraph("References")
        + paragraph("Anderson, M. J. (2001). A new method for non-parametric multivariate "
                    "analysis of variance. Austral Ecology, 26(1), 32-46.")
        + paragraph("Figure 1. Growth performance in 2020 and 2021.")
        + table
        + paragraph("An, W. (2020). Not a reference after the captions. Aquaculture, 1, 2.")
    )  # fmt: skip
    (entry,) = parse_docx_file(docx(tmp_path, body)).entries
    assert EntryInfo.from_entry(entry).title.startswith("A new method")
    body = (
        paragraph("References")
        + paragraph("Anderson, M. J. (2001). A new method. Austral Ecology, 26(1), 32-46.")
        + paragraph("Some text.")
        + paragraph("More text.")
        + paragraph("Even more.")
        + paragraph("Later, a year: 2020.")
    )
    assert len(parse_docx_file(docx(tmp_path, body)).entries) == 1
    rows = docx(tmp_path, paragraph("References") + table)
    assert parse_docx_file(rows).entries == []  # a table is no reference list


def test_word_bibliography_paragraphs(tmp_path: Path) -> None:
    body = paragraph("Some text.") + paragraph(
        "Kingma, D. P., & Ba, J. (2015). Adam: A method for stochastic optimization. In ICLR.",
        "Bibliography",
    )
    (entry,) = parse_docx_file(docx(tmp_path, body)).entries
    assert EntryInfo.from_entry(entry).title == "Adam: A method for stochastic optimization"


def test_what_cannot_be_read_is_reported(tmp_path: Path) -> None:
    broken = tmp_path / "broken.docx"
    broken.write_bytes(b"not a zip")
    bib = parse_docx_file(broken)
    assert (bib.entries, [i.kind for i in bib.issues]) == ([], ["unreadable"])
    dtd = docx(tmp_path, "")
    with zipfile.ZipFile(dtd, "w") as archive:
        archive.writestr("word/document.xml", '<!DOCTYPE x [<!ENTITY a "b">]><w:document/>')
    assert [i.kind for i in parse_docx_file(dtd).issues] == ["unreadable"]


def test_a_manuscript_is_checked_like_any_reference_list(tmp_path: Path) -> None:
    path = docx(tmp_path, field(zotero(LECUN, ADAM), "(LeCun et al., 2015)"))
    result = run_check(path)  # offline hygiene only
    assert result.entries == 2
    assert result.bib_files[0].path == path


def test_csl_json_files(tmp_path: Path) -> None:
    path = tmp_path / "refs.json"
    path.write_text(json.dumps([LECUN, ADAM]), encoding="utf-8")
    bib = parse_csl_json_file(path)
    assert [e.key for e in bib.entries] == ["ref1", "kingma2015adam"]
    path.write_text(json.dumps({"items": [ADAM]}), encoding="utf-8")
    assert [e.key for e in parse_csl_json_file(path).entries] == ["kingma2015adam"]
    path.write_text("{not json", encoding="utf-8")
    assert [i.kind for i in parse_csl_json_file(path).issues] == ["unreadable"]


RIS = """TY  - JOUR
AU  - LeCun, Yann
AU  - Bengio, Yoshua
AU  - Hinton, Geoffrey
TI  - Deep learning
T2  - Nature
PY  - 2015/05/28/
VL  - 521
IS  - 7553
SP  - 436
EP  - 444
DO  - 10.1038/nature14539
ER  -

TY  - CPAPER
AU  - Kingma, Diederik P.
AU  - Ba, Jimmy
TI  - Adam: A Method for
  Stochastic Optimization
T2  - International Conference on Learning Representations
PY  - 2015
ER  -
"""


def test_ris_records(tmp_path: Path) -> None:
    path = tmp_path / "refs.ris"
    path.write_text(RIS, encoding="utf-8")
    lecun, adam = parse_ris_file(path).entries
    assert (lecun.line, adam.line) == (1, 15)  # each record's TY line
    info = EntryInfo.from_entry(lecun)
    assert (info.title, info.venue, info.year) == ("Deep learning", "Nature", 2015)
    assert [p.family for p in info.authors.people] == ["LeCun", "Bengio", "Hinton"]
    assert lecun.text("pages") == "436-444"
    assert [str(i) for i in extract_identifiers(lecun)] == ["doi:10.1038/nature14539"]
    assert EntryInfo.from_entry(adam).title == "Adam: A Method for Stochastic Optimization"
    assert adam.entry_type == "inproceedings"
    assert run_check(path).entries == 2


def test_csl_names_dates_and_arxiv_numbers() -> None:
    entry_type, fields = csl_fields(
        {
            "type": "article",
            "title": "A <i>sparse</i> attention",
            "number": "arXiv:2101.00001",
            "author": [
                {"family": "Waals", "non-dropping-particle": "van der", "given": "J. D."},
                {"literal": "The LIGO Scientific Collaboration"},
                {"family": "King", "given": "Martin Luther", "suffix": "Jr."},
            ],
            "issued": {"raw": "2021-01-05"},
        }
    )
    assert entry_type == "misc"
    assert fields["title"] == "A sparse attention"
    assert fields["author"] == (
        "van der Waals, J. D. and {The LIGO Scientific Collaboration} and King, Jr., Martin Luther"
    )
    assert (fields["year"], fields["eprint"], fields["archiveprefix"]) == (
        "2021",
        "2101.00001",
        "arXiv",
    )
