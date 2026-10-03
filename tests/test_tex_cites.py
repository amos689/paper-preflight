import pytest

from paper_preflight.tex.cites import CiteKind, command_table, find_citations
from paper_preflight.tex.mask import mask_latex
from paper_preflight.textio import LineIndex


def keys_of(tex: str, **kwargs: object) -> list[str]:
    masked = mask_latex(tex)
    return [k.key for c in find_citations(masked, **kwargs) for k in c.keys]  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("tex", "expected"),
    [
        (r"\cite{a}", ["a"]),
        (r"\citep{a, b ,c}", ["a", "b", "c"]),
        (r"\citet[p.~3]{a}", ["a"]),
        (r"\citep[see][Sec.~2]{a}", ["a"]),
        (r"\citep*{a}", ["a"]),
        (r"\Citet{a}", ["a"]),
        (r"\autocite*[12]{a}", ["a"]),
        (r"\textcite{a}", ["a"]),
        (r"\cite<e.g.,>[p.~11]{a}", ["a"]),  # apacite prenote
        (r"\citep[{see [1]}]{a}", ["a"]),  # brackets inside braces in a note
        (r"\citep [p.~2] {a}", ["a"]),  # spaces between arguments
        ("\\citep[p.~2]\n{a}", ["a"]),  # a single line break between arguments is allowed
        (r"\cites[see][12]{a}[cf.][]{b}{c}", ["a", "b", "c"]),
        (r"\parencites(global pre)(global post)[x]{a}{b}", ["a", "b"]),
        (r"\volcite[see]{3}[45]{a}", ["a"]),
        (r"\nocite{*}", ["*"]),
        (r"\cite{}", []),
        (r"\citation is a word in \citeauthor{a}", ["a"]),
    ],
)
def test_citation_forms(tex: str, expected: list[str]) -> None:
    assert keys_of(tex) == expected


def test_blank_line_ends_argument_scan() -> None:
    assert keys_of("\\citep[p.~2]\n\n{a}") == []


def test_comments_iffalse_and_verbatim_are_ignored() -> None:
    tex = "\n".join(
        [
            r"\cite{kept1} % \cite{commented}",
            r"100\% sure \cite{kept2}",  # escaped percent is not a comment
            r"\\% this is a comment after a line break \cite{commented2}",
            r"\iffalse \cite{iffalse1} \ifnum1=1 \cite{nested} \fi \cite{iffalse2} \fi"
            r" \cite{kept3}",
            r"\begin{verbatim} \cite{verb1} \end{verbatim}",
            r"\begin{comment}",
            r"\cite{commentenv}",
            r"\end{comment}",
            r"\verb|\cite{verb2}| \cite{kept4}",
        ]
    )
    assert keys_of(tex) == ["kept1", "kept2", "kept3", "kept4"]


def test_double_backslash_is_not_a_command_prefix() -> None:
    assert keys_of(r"line\\cite{a}") == []
    assert keys_of(r"line\\\cite{a}") == ["a"]


def test_custom_wrapper_commands() -> None:
    tex = r"\mycite{a} \cite{b}"
    assert keys_of(tex) == ["b"]
    assert keys_of(tex, commands=command_table(["\\mycite"])) == ["a", "b"]


def test_offsets_map_to_original_lines_and_columns_with_crlf_and_cjk() -> None:
    tex = "第一行\r\n见 \\citep{zhang2020, li2021}\r\n"
    masked = mask_latex(tex)
    assert len(masked) == len(tex)
    (command,) = find_citations(masked)
    index = LineIndex(tex)
    assert index.position(command.offset) == (2, 3)
    # "见 \citep{" is 9 code points, so the first key starts at column 10.
    assert [index.position(k.offset) for k in command.keys] == [(2, 10), (2, 21)]
    assert command.kind is CiteKind.SINGLE


def test_nocite_flag() -> None:
    (command,) = find_citations(mask_latex(r"\nocite{a,b}"))
    assert command.is_nocite
    assert [k.key for k in command.keys] == ["a", "b"]


def test_unterminated_iffalse_masks_to_end() -> None:
    assert keys_of(r"\cite{a} \iffalse \cite{b}") == ["a"]
