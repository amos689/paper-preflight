"""A cited work's text from OpenAlex, Europe PMC (JATS) and Crossref."""

from paper_preflight.support.texts import (
    MIN_FULL_TEXT_CHARS,
    incomplete,
    inverted_abstract,
    jats_fragment_text,
    jats_passages,
)

JATS = """<?xml version="1.0" encoding="UTF-8"?>
<article xmlns:xlink="http://www.w3.org/1999/xlink" xmlns:mml="http://www.w3.org/1998/Math/MathML">
<front><article-meta>
<title-group><article-title>Ileal hyperplasia</article-title></title-group>
<abstract><sec><title>Background</title><p>We studied twelve children&nbsp;with colitis.</p></sec>
<sec><title>Findings</title><p>Onset was linked to <italic>MMR</italic> in eight.</p></sec>
</abstract>
</article-meta></front>
<body>
<sec><title>Methods</title>
<p>Children were referred to a paediatric unit.</p>
<fig id="f1"><caption><p>Endoscopy findings.</p></caption><graphic xlink:href="f1.jpg"/></fig>
<table-wrap><table><tr><td>12</td></tr></table></table-wrap>
<p>The rate was <disp-formula><tex-math>x^2</tex-math></disp-formula> per year.</p>
</sec>
</body>
<back><ref-list><ref><mixed-citation>Someone 1990.</mixed-citation></ref></ref-list></back>
</article>"""


def test_inverted_abstract() -> None:
    index = {"Attention": [0], "is": [1, 4], "all": [2], "you": [3], "fine": [5]}
    assert inverted_abstract(index) == "Attention is all you is fine"
    assert inverted_abstract(None) == ""


def test_jats_abstract_first_then_body_without_references() -> None:
    passages = jats_passages(JATS)
    assert passages[0] == (
        "We studied twelve children with colitis. Onset was linked to MMR in eight."
    )
    assert passages[1:] == [
        "Methods",
        "Children were referred to a paediatric unit.",
        "Endoscopy findings.",
        "The rate was per year.",
    ]
    assert jats_passages("<not xml") == []


def test_crossref_abstract_fragment() -> None:
    fragment = "<jats:title>Abstract</jats:title><jats:p>We show that &amp; why.</jats:p>"
    assert jats_fragment_text(fragment) == "We show that & why."


def test_what_is_no_full_text() -> None:
    long = ["word " * (MIN_FULL_TEXT_CHARS // 4)]
    assert incomplete(long) is None
    assert incomplete([]) == "no text could be extracted"
    assert "short" in (incomplete(["An abstract only."]) or "")
    assert "access page" in (incomplete(["Access through your institution", *long]) or "")


def test_passages_end_at_sentences() -> None:
    from paper_preflight.support.texts import passages_of

    text = " ".join(f"Sentence number {i} has five words." for i in range(1, 61))
    passages = passages_of(text, size=50)
    assert all(p.endswith(".") for p in passages)
    assert all(50 <= len(p.split()) < 56 for p in passages[:-1])  # whole six-word sentences
    assert " ".join(passages) == text


def test_pdf_passages_stop_at_the_references(tmp_path: object) -> None:
    import pytest

    pytest.importorskip("pypdf")
    from pathlib import Path

    from paper_preflight.support.texts import pdf_passages

    from .test_pdftext import tiny_pdf

    pdf = Path(str(tmp_path)) / "paper.pdf"
    pdf.write_bytes(
        tiny_pdf(
            [
                ["A study of conver-", "gence in deep nets.", "We show that it holds."],
                ["References", "[1] A. Author. Some paper. 2020."],
            ]
        )
    )
    (passage,) = pdf_passages(pdf)
    assert passage == "A study of convergence in deep nets. We show that it holds."
