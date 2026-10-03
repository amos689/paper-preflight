"""Reading compiled bibliographies (.bbl) when a project ships no .bib (real arXiv sources)."""

from pathlib import Path

import pytest

from paper_preflight.bib.bbl import parse_bbl_text
from paper_preflight.check import run_check
from paper_preflight.fixes import plan

NATBIB = r"""\begin{thebibliography}{3}
\providecommand{\natexlab}[1]{#1}

\bibitem[Ye et~al.(2018)Ye, Qian, and Zhang]{ye2018customized}
Peng Ye, Julian Qian, and Li~Zhang.
\newblock Customized regression model for airbnb dynamic pricing.
\newblock In \emph{Proceedings of the 24th ACM SIGKDD international conference on
  knowledge discovery \& data mining}, pages 932--940, 2018.

\bibitem[Alberti(1994)]{Alberti94}
G.~Alberti.
\newblock On the structure of singular sets of convex functions.
\newblock \emph{Calculus of Variations and Partial Differential Equations},
  2\penalty0 (1):\penalty0 17--27, 1994.
\newblock \doi{10.1007/BF01234313}.

\bibitem[Allen-Zhu and Li(2023)]{allen2023physics}
Zeyuan Allen-Zhu and Yuanzhi Li.
\newblock Physics of language models: Part 3.2, knowledge manipulation.
\newblock \emph{arXiv preprint arXiv:2309.14402}, 2023.

\end{thebibliography}
"""


def test_natbib_items_become_entries() -> None:
    bib = parse_bbl_text(NATBIB, Path("main.bbl"))
    assert bib.derived
    ye, alberti, allen = bib.entries
    assert (ye.key, ye.entry_type) == ("ye2018customized", "inproceedings")
    assert ye.text("author") == "Peng Ye and Julian Qian and Li Zhang"
    assert ye.text("title") == "Customized regression model for airbnb dynamic pricing"
    assert ye.text("booktitle").startswith("Proceedings of the 24th ACM SIGKDD")
    assert ye.text("year") == "2018"
    assert ye.line == 4  # findings point at the item in the .bbl
    assert alberti.text("journal") == "Calculus of Variations and Partial Differential Equations"
    assert (alberti.text("doi"), alberti.text("year")) == ("10.1007/BF01234313", "1994")
    assert (allen.text("eprint"), allen.text("year")) == ("2309.14402", "2023")


@pytest.mark.parametrize(
    ("item", "expected"),
    [
        # elsarticle and revtex: one \bibinfo per field and per author
        (r"\bibitem[{Yao et~al.(2013)}]{yao}\bibinfo{author}{S.~Yao}, \bibinfo{author}{Y.~Zhu},"
         r"\newblock \bibinfo{title}{Advances in targeting {cell} signalling},"
         r"\newblock \bibinfo{journal}{Nature Reviews Drug Discovery} \bibinfo{year}{2013}.",
         {"author": "S. Yao and Y. Zhu", "title": "Advances in targeting cell signalling",
          "journal": "Nature Reviews Drug Discovery", "year": "2013"}),
        # a link around the title, and the DOI it holds
        (r"\bibitem[Chen(2024)]{chen}Guiming Chen and Shunian Chen."
         r"\newblock \href{https://doi.org/10.18653/v1/2024.emnlp-main.474}{Humans or {LLMs} as"
         r" the judge?} \newblock In \emph{Proceedings of EMNLP}, 2024.",
         {"title": "Humans or LLMs as the judge?", "doi": "10.18653/v1/2024.emnlp-main.474"}),
        # APA: family names first, the year after them
        (r"\bibitem{aycock}Aycock, S., Stap, D., \& Sima'an, K. (2025)."
         r"\newblock Can LLMs really learn to translate?",
         {"author": "Aycock, S. and Stap, D. and Sima'an, K.", "year": "2025"}),
        # IEEEtran: no \newblock, the title in quotes
        (r"\bibitem{he}K.~He and J.~Sun, ``Deep residual learning for image recognition,'' in"
         r" \emph{Proc. CVPR}, 2016, pp. 770--778.",
         {"author": "K. He and J. Sun", "title": "Deep residual learning for image recognition"}),
        # a physics style gives no title: the item is known by its DOI and its authors
        (r"\bibitem{prl}J.N. Ginocchio, A.S. de~Castro, Phys. Rev. Lett. \textbf{78}, 436 (1997)."
         r"\newblock \doi{http://dx.doi.org/10.1103/PhysRevLett.78.436}.",
         {"doi": "10.1103/PhysRevLett.78.436", "year": "1997", "title": None,
          "author": "J.N. Ginocchio and A.S. de Castro"}),
        # one author and "et al.": not an inverted name
        (r"\bibitem{knoth}Petr Knoth et~al. \newblock CORE: A global aggregation service for"
         r" open access papers. \newblock \emph{Scientific Data}, 10:366, 2023.",
         {"author": "Petr Knoth and others"}),
        # ACL: the year after the authors
        (r"\bibitem[{Cobbe et~al.(2021)}]{cobbe}Karl Cobbe, Vineet Kosaraju, and John Schulman."
         r" 2021. \newblock Training verifiers to solve math word problems."
         r" \newblock \emph{Preprint}, arXiv:2110.14168.",
         {"author": "Karl Cobbe and Vineet Kosaraju and John Schulman", "year": "2021",
          "eprint": "2110.14168"}),
        # a book: its title in italics
        (r"\bibitem[Rubinstein(2004)]{cem}Reuven~Y Rubinstein and Dirk~P Kroese."
         r"\newblock \emph{The cross-entropy method: a unified approach}, volume 133."
         r"\newblock Springer, 2004.",
         {"title": "The cross-entropy method: a unified approach", "year": "2004"}),
        # Springer LNCS: "Family, I.: Title. In: Venue (year)"
        (r"\bibitem{cao}Cao, J., Zhang, X., Carenini, G.: Multi2: Multi-agent test-time scalable"
         r" framework. In: Proceedings of the 5th New Frontiers in Summarization Workshop."
         r" pp. 135--156 (2025)",
         {"author": "Cao, J. and Zhang, X. and Carenini, G.",
          "title": "Multi2: Multi-agent test-time scalable framework", "year": "2025"}),
        # AAS: no title; "\dodoi" for the DOI
        (r"\bibitem[{{Belfiore} {et~al.}(2019)}]{bel}{Belfiore}, F., {Vincenzo}, F., \&"
         r" {Matteucci}, F. 2019, \mnras, 487, 456, \dodoi{10.1093/mnras/stz1165}",
         {"author": "Belfiore, F. and Vincenzo, F. and Matteucci, F.", "year": "2019",
          "doi": "10.1093/mnras/stz1165", "title": None}),
        # Chicago/INFORMS: only the first author inverted, the year after the authors
        (r"\bibitem[{Saad et~al.(2023)Saad, Blanchard, and Verzelen}]{saad}Saad, El~Mehdi,"
         r" Gilles Blanchard, Nicolas Verzelen. 2023. \newblock Covariance-adaptive best arm"
         r" identification. \newblock {\it Advances in NeurIPS\/}, vol.~36. 73287--73298.",
         {"author": "Saad, El Mehdi and Gilles Blanchard and Nicolas Verzelen", "year": "2023"}),
        # Elsevier numbered: "I. Family, Title, in: Venue, year"
        (r"\bibitem{zhao}R.~Zhao, C.~De~Sa, Z.~Zhang, Improving neural network quantization"
         r" without retraining, in: International Conference on Machine Learning, 2019.",
         {"author": "R. Zhao and C. De Sa and Z. Zhang", "year": "2019",
          "title": "Improving neural network quantization without retraining",
          "booktitle": "International Conference on Machine Learning"}),
        # ... with the year in parentheses and the link after a \newblock
        (r"\bibitem{vgg}K.~Simonyan, A.~Zisserman, Very deep convolutional networks for"
         r" large-scale image recognition (2015). \newblock \href {http://arxiv.org/abs/1409.1556}"
         r" {\path{arXiv:1409.1556}}.",
         {"author": "K. Simonyan and A. Zisserman", "eprint": "1409.1556", "year": "2015",
          "title": "Very deep convolutional networks for large-scale image recognition"}),
    ],
)  # fmt: skip
def test_bibliography_styles(item: str, expected: dict[str, str | None]) -> None:
    text = "\\begin{thebibliography}{1}\n" + item + "\n\\end{thebibliography}\n"
    (entry,) = parse_bbl_text(text, Path("main.bbl")).entries
    for field, value in expected.items():
        assert entry.text(field) == value, field


BIBLATEX = r"""\refsection{0}
  \datalist[entry]{nty/global//global/global}
    \entry{vaswani2017}{inproceedings}{}
      \name{author}{2}{}{%
        {{hash=1}{%
           family={Vaswani},
           familyi={V\bibinitperiod},
           given={Ashish},
           giveni={A\bibinitperiod},
        }}%
        {{hash=2}{%
           family={Shazeer},
           given={Noam},
        }}%
      }
      \list{publisher}{1}{%
        {Curran}%
      }
      \field{booktitle}{Advances in Neural Information Processing Systems}
      \field{title}{Attention is All you Need}
      \field{year}{2017}
      \verb{doi}
      \verb 10.5555/3295222.3295349
      \endverb
    \endentry
  \enddatalist
\endrefsection
"""


def test_biblatex_entries() -> None:
    (entry,) = parse_bbl_text(BIBLATEX, Path("main.bbl")).entries
    assert (entry.key, entry.entry_type) == ("vaswani2017", "inproceedings")
    assert entry.text("author") == "Vaswani, Ashish and Shazeer, Noam"
    assert entry.text("title") == "Attention is All you Need"
    assert entry.text("doi") == "10.5555/3295222.3295349"


def test_a_project_with_only_a_bbl(tmp_path: Path) -> None:
    (tmp_path / "main.tex").write_text(
        "\\documentclass{article}\\begin{document}\\cite{Alberti94}\\cite{missing}"
        "\\bibliography{refs}\\end{document}\n",
        encoding="utf-8",
    )
    (tmp_path / "main.bbl").write_text(NATBIB, encoding="utf-8")
    result = run_check(tmp_path)
    rules = {(f.rule_id, f.key) for f in result.findings}
    assert ("CIT001", "missing") in rules  # cited, in no bibliography
    assert not any(rule == "CIT005" for rule, _ in rules)  # refs.bib missing: the .bbl stands in
    assert any("main.bbl" in note for note in result.notes)
    assert result.entries == 3
    assert plan(result.findings, result.bib_files, level="unsafe") == []  # never edits a .bbl


def test_a_bbl_checked_on_its_own(tmp_path: Path) -> None:
    path = tmp_path / "refs.bbl"
    path.write_text(NATBIB, encoding="utf-8")
    result = run_check(path)
    assert result.entries == 3
    assert result.bib_files[0].derived
