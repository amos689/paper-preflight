"""Reading a plain-text reference list: pasted from Word, a web page or a PDF."""

from pathlib import Path

import pytest
from typer.testing import CliRunner

from paper_preflight.bib.plaintext import parse_plaintext, parse_reference, split_references
from paper_preflight.check import run_check
from paper_preflight.cli import app
from paper_preflight.fixes import plan
from paper_preflight.identifier_lint import check_identifier_syntax


@pytest.mark.parametrize(
    ("text", "starts"),
    [
        # numbered, a reference running over two lines
        ("[1] A. Smith, “One,” 2020.\n[2] B. Lee,\n“Two,” 2021.\n",
         [(1, "A. Smith"), (2, "B. Lee")]),
        ("1. Smith, J. One. 2020.\n2. Lee, K. Two. 2021.\n", [(1, "Smith"), (2, "Lee")]),
        # paragraphs
        ("Smith, J. (2020).\nOne.\n\nLee, K. (2021). Two.\n", [(1, "Smith"), (4, "Lee")]),
        # one per line, as pasted from Word
        ("Smith, J. (2020). One.\nLee, K. (2021). Two.\n", [(1, "Smith"), (2, "Lee")]),
        # lines wrapped as in a PDF: a reference ends at a line ending in a period
        (
            "Smith, J. and Lee, K. A long title that\nwraps. Nature 1, 2 (2020).\n"
            "Wu, X. Another title that runs on\nto the next line. Science 3, 4 (2021).\n"
            "Li, Y. A third title, again too long for\none line. Cell 5, 6 (2022).\n",
            [(1, "Smith"), (3, "Wu"), (5, "Li")],
        ),
    ],
)  # fmt: skip
def test_split_references(text: str, starts: list[tuple[int, str]]) -> None:
    found = split_references(text)
    assert [(line, ref.split(",")[0].split(" ")[0]) for line, ref in found] == [
        (line, first.split(" ")[0]) for line, first in starts
    ]


def test_a_word_broken_at_a_line_end_is_joined() -> None:
    ((_, reference),) = split_references("[1] A. Smith, “Deep lan-\nguage models,” 2020.\n[2] x\n")[
        :1
    ]
    assert "language models" in reference


@pytest.mark.parametrize(
    ("reference", "expected"),
    [
        # IEEE
        ("K. He, X. Zhang, S. Ren, and J. Sun, “Deep residual learning for image recognition,” in "
         "Proc. IEEE Conf. Comput. Vis. Pattern Recognit. (CVPR), 2016, pp. 770–778.",
         {"author": "K. He and X. Zhang and S. Ren and J. Sun", "year": "2016",
          "title": "Deep residual learning for image recognition", "type": "inproceedings"}),
        # APA, with a DOI link
        ("Lopez, P. (2009). GROBID: Combining automatic bibliographic data recognition and term "
         "extraction for scholarship publications. In Research and Advanced Technology for "
         "Digital Libraries (pp. 473–474). https://doi.org/10.1007/978-3-642-04346-8_62",
         {"author": "Lopez, P.", "year": "2009", "doi": "10.1007/978-3-642-04346-8_62",
          "title": "GROBID: Combining automatic bibliographic data recognition and term "
                   "extraction for scholarship publications"}),
        # APA with an organisation as author
        ("CiteX. (2026). CiteX: Workshop on Citation Extraction and Parsing. https://example.org",
         {"author": "CiteX", "year": "2026", "url": "https://example.org"}),
        # ACM / ACL: the year after the authors
        ("Ashish Vaswani, Noam Shazeer, Niki Parmar, et al. 2017. Attention is all you need. In "
         "Advances in Neural Information Processing Systems, pages 5998–6008.",
         {"author": "Ashish Vaswani and Noam Shazeer and Niki Parmar and others", "year": "2017",
          "title": "Attention is all you need",
          "booktitle": "Advances in Neural Information Processing Systems"}),
        # natbib: authors. title. venue, year; an arXiv preprint
        ("Ilya Loshchilov and Frank Hutter. Decoupled weight decay regularization. arXiv preprint "
         "arXiv:1711.05101, 2017",
         {"author": "Ilya Loshchilov and Frank Hutter", "title": "Decoupled weight decay "
          "regularization", "eprint": "1711.05101", "year": "2017"}),
        # Nature
        ("Silver, D. et al. Mastering the game of Go with deep neural networks and tree search. "
         "Nature 529, 484–489 (2016).",
         {"author": "Silver, D. and others", "journal": "Nature", "year": "2016",
          "title": "Mastering the game of Go with deep neural networks and tree search"}),
        # Vancouver
        ("Vaswani A, Shazeer N, Parmar N, et al. Attention is all you need. Adv Neural Inf "
         "Process Syst. 2017;30:5998-6008.",
         {"author": "Vaswani, A. and Shazeer, N. and Parmar, N. and others", "year": "2017",
          "title": "Attention is all you need", "journal": "Adv Neural Inf Process Syst"}),
        # Springer LNCS
        ("He, K., Zhang, X., Ren, S., Sun, J.: Deep residual learning for image recognition. In: "
         "CVPR, pp. 770–778 (2016)",
         {"author": "He, K. and Zhang, X. and Ren, S. and Sun, J.", "booktitle": "CVPR",
          "title": "Deep residual learning for image recognition", "year": "2016"}),
        # Elsevier numbered
        ("K. He, X. Zhang, S. Ren, J. Sun, Deep residual learning for image recognition, in: "
         "CVPR, 2016, pp. 770–778.",
         {"author": "K. He and X. Zhang and S. Ren and J. Sun", "booktitle": "CVPR",
          "title": "Deep residual learning for image recognition", "year": "2016"}),
        # Chicago author-date, the title in quotes after the year
        ("He, Kaiming, Xiangyu Zhang, Shaoqing Ren, and Jian Sun. 2016. “Deep Residual Learning "
         "for Image Recognition.” In Proceedings of the IEEE Conference on Computer Vision and "
         "Pattern Recognition, 770–78.",
         {"author": "He, Kaiming and Xiangyu Zhang and Shaoqing Ren and Jian Sun", "year": "2016",
          "title": "Deep Residual Learning for Image Recognition"}),
        # MLA
        ("LeCun, Yann, Yoshua Bengio, and Geoffrey Hinton. \"Deep learning.\" Nature 521.7553 "
         "(2015): 436-444.",
         {"author": "LeCun, Yann and Yoshua Bengio and Geoffrey Hinton", "title": "Deep learning",
          "journal": "Nature", "year": "2015"}),
        # biblatex: "In:" before a journal with its volume, a language code, an ISSN, a visit
        ("Petr Knoth et al. “CORE: A Global Aggregation Service for Open Access Papers”. en. In: "
         "Scientific Data 10.1 (June 2023). issn: 2052-4463. doi: 10.1038/s41597-023-02208-w. "
         "url: https://www.nature.com/articles/s41597-023-02208-w (visited on 04/24/2025).",
         {"author": "Petr Knoth and others", "journal": "Scientific Data", "year": "2023",
          "doi": "10.1038/s41597-023-02208-w", "type": "article"}),
        # an arXiv ID never filled in, and a DOI written wrongly, are kept as written
        ("Nuo Lou and et al. Dsp: Diffusion-based span prediction for masked text modeling. arXiv "
         "preprint arXiv:2305.XXXX, 2023",
         {"author": "Nuo Lou and others", "eprint": "2305.XXXX"}),
        ("Ilia Kulikov. Importance of search. 2019. doi: 0.18653/v1/W19-8609.",
         {"doi": "0.18653/v1/W19-8609"}),
        # APA with a group first and APA 7's ellipsis before the last of many authors
        ("Gemma, Kamath, A., Ferret, J., … Hussenot, L. (2025). Gemma 3 Technical Report. "
         "https://arxiv.org/abs/2503.19786",
         {"author": "Gemma and Kamath, A. and Ferret, J. and Hussenot, L. and others",
          "eprint": "2503.19786"}),
        ("Yang, A., Lin, H., & al., et. (2025). Qwen2.5 Technical Report.",
         {"author": "Yang, A. and Lin, H. and others"}),
        # a venue's acronym in parentheses is part of its name
        ("Sebastian Pado and Christopher D Manning. Machine translation evaluation with textual "
         "entailment features. In Proceedings of the Fourth Workshop on Statistical Machine "
         "Translation (WMT), pages 37–41, 2009",
         {"booktitle": "Proceedings of the Fourth Workshop on Statistical Machine Translation "
                       "(WMT)"}),
        # a technical report, and pages right after the title
        ("Augustine Kong. A note on importance sampling using standardized weights. University "
         "of Chicago, Dept. of Statistics, Tech. Rep, 348:14, 1992",
         {"type": "techreport", "institution": "University of Chicago, Dept. of Statistics, "
                                               "Tech. Rep"}),
        ("Ilia Kulikov and Jason Weston. Importance of search and evaluation strategies in neural "
         "dialogue modeling. pp. 76–87, 01 2019. doi: 10.18653/v1/W19-8609.",
         {"title": "Importance of search and evaluation strategies in neural dialogue modeling"}),
        # a title with no authors
        ("ANSI/NISO Z39.96-2024: JATS: Journal Article Tag Suite (2024).",
         {"title": "ANSI/NISO Z39.96-2024: JATS: Journal Article Tag Suite", "year": "2024",
          "author": None}),
    ],
)  # fmt: skip
def test_reference_styles(reference: str, expected: dict[str, str | None]) -> None:
    entry_type, fields = parse_reference(reference)
    for name, value in expected.items():
        if name == "type":
            assert entry_type == value
        else:
            assert fields.get(name) == value, name


LIST = """References

[1] K. He, X. Zhang, S. Ren, and J. Sun, “Deep residual learning for image recognition,” in
    Proc. CVPR, 2016, pp. 770–778.
[2] Lopez, P. (2009). GROBID: Combining Automatic Bibliographic Data Recognition and Term
    Extraction for Scholarship Publications. https://doi.org/10.1007/978-3-642-04346-8_62
"""


def test_a_list_becomes_derived_entries() -> None:
    bib = parse_plaintext(LIST, Path("refs.txt"))
    assert bib.derived
    assert [(e.key, e.line) for e in bib.entries] == [("ref1", 3), ("ref2", 5)]
    assert bib.entries[1].text("doi") == "10.1007/978-3-642-04346-8_62"
    assert bib.entries[0].fields["title"].line == 3


def test_identifiers_are_read_as_written() -> None:
    text = "[1] M. M. and M. O., “Inforex,” in RANLP, 2019. doi: 10.26615/978-954-452-056-4_083.\n"
    (entry,) = parse_plaintext(text, Path("refs.txt")).entries
    assert entry.fields["doi"].raw == "{10.26615/978-954-452-056-4_083}"
    assert check_identifier_syntax([entry]) == []  # no LaTeX escape to report (REF017)


def test_a_list_checked_on_its_own(tmp_path: Path) -> None:
    path = tmp_path / "refs.txt"
    path.write_text(LIST, encoding="utf-8")
    result = run_check(path)
    assert result.entries == 2
    assert plan(result.findings, result.bib_files, level="unsafe") == []  # never edited


def test_a_list_from_stdin() -> None:
    result = CliRunner().invoke(app, ["check", "-", "--offline", "-f", "json"], input=LIST)
    assert result.exit_code in {0, 2}, result.output
    assert '"entries": 2' in result.output.replace(" ", "").replace('"entries":2', '"entries": 2')
