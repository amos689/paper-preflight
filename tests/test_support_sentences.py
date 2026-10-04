"""Citation sentences: what each citation in a LaTeX paper is asked to support."""

from pathlib import Path

import pytest

from paper_preflight.support.sentences import CITED_WORK, CitationSentence, citation_sentences
from paper_preflight.tex.project import load_project

PAPER = r"""\documentclass{article}
\newcommand{\method}{SimCLR}
\begin{document}
\section{Introduction}
Transformers~\cite{vaswani2017} have replaced recurrent networks in machine translation, while
convolutional models remain strong for vision tasks~\citep{he2016,tan2019}. We follow
\citet{devlin2019} and fine-tune \method{} on GLUE. Our model reaches $95.1\%$ accuracy on
SST-2, compared to 93.5\% reported by Liu et al.~\cite{liu2019}.\footnote{See also the
leaderboard of \cite{wang2018}.}

% A commented citation \cite{hidden}
\begin{figure}
\caption{Results from \citet{smith2020} on ImageNet.}
\end{figure}
As shown in Fig.~\ref{fig:x}, scaling laws \citep[e.g.,][]{kaplan2020} hold for model sizes
between $10^7$ and $10^{9}$ parameters. Prior work, e.g.\ \cite{a2020}, studied this too.
\begin{equation}
  y = f(x) \cite{inmath}
\end{equation}
\end{document}
"""


@pytest.fixture
def found(tmp_path: Path) -> dict[str, CitationSentence]:
    (tmp_path / "main.tex").write_text(PAPER, encoding="utf-8")
    return {s.key: s for s in citation_sentences(load_project(tmp_path))}


def test_every_citation_in_prose_has_its_sentence(found: dict[str, CitationSentence]) -> None:
    assert set(found) == {
        "vaswani2017", "he2016", "tan2019", "devlin2019", "liu2019", "wang2018", "smith2020",
        "kaplan2020", "a2020",
    }  # fmt: skip
    # not a commented-out citation, nor one inside a displayed formula
    assert found["vaswani2017"].line == 5


def test_citations_in_different_clauses_get_their_clause(
    found: dict[str, CitationSentence],
) -> None:
    assert found["vaswani2017"].claim == (
        "Transformers have replaced recurrent networks in machine translation"
    )
    assert found["he2016"].claim == "convolutional models remain strong for vision tasks."
    assert found["tan2019"].claim == found["he2016"].claim  # one command, one clause
    assert found["he2016"].sentence.startswith("Transformers have replaced")


def test_a_citation_used_as_a_noun_is_named(found: dict[str, CitationSentence]) -> None:
    assert found["devlin2019"].claim == f"We follow {CITED_WORK} and fine-tune SimCLR on GLUE."
    assert found["smith2020"].claim == f"Results from {CITED_WORK} on ImageNet."  # a caption
    assert found["wang2018"].claim == f"See also the leaderboard of {CITED_WORK}."  # a footnote


def test_a_parenthetical_citation_used_as_a_noun_is_named(tmp_path: Path) -> None:
    (tmp_path / "main.tex").write_text(
        r"""\documentclass{article}\begin{document}
The closest to our work are \cite{a} and \cite{b}. \cite{a} demonstrates that personas
shape the representations. Deep networks generalise well. \cite{c}
They are hard to explain.
\end{document}""",
        encoding="utf-8",
    )
    found = citation_sentences(load_project(tmp_path))
    claims = [(s.key, s.claim) for s in found]
    assert claims[:3] == [
        ("a", f"The closest to our work are {CITED_WORK} and {CITED_WORK}."),
        ("b", f"The closest to our work are {CITED_WORK} and {CITED_WORK}."),
        ("a", f"{CITED_WORK} demonstrates that personas shape the representations."),
    ]
    # a citation after a sentence's full stop, before the next sentence, belongs to the first
    assert claims[3] == ("c", "Deep networks generalise well.")


def test_numbers_and_abbreviations_survive(found: dict[str, CitationSentence]) -> None:
    liu = found["liu2019"]
    assert liu.claim == (
        "Our model reaches 95.1% accuracy on SST-2, compared to 93.5% reported by Liu et al."
    )
    assert liu.kind == "result"
    assert liu.previous.startswith("We follow")
    kaplan = found["kaplan2020"]
    assert "between 10^7 and 10^9 parameters" in kaplan.claim  # not "107 and 109"
    assert kaplan.claim.startswith("As shown in Fig. [ref], scaling laws hold")
    assert found["a2020"].claim == "Prior work, e.g., studied this too."  # "e.g." ends nothing


def test_kinds() -> None:
    from paper_preflight.support.sentences import _kind

    assert _kind("We adopt the optimiser of [cited work].") == "method"
    assert _kind("Attention was introduced for translation.") == "background"
    assert _kind("BERT was released in 2018.") == "background"  # a year is no result
    assert _kind("It reaches 3.2 BLEU more.") == "result"
