"""Reading the reference list of a PDF."""

from pathlib import Path

import pytest

from paper_preflight.bib.pdftext import parse_pdf_file, reference_section
from paper_preflight.check import run_check

pytest.importorskip("pypdf")


def tiny_pdf(pages: list[list[str]]) -> bytes:
    """A PDF with one Helvetica line per string, as pypdf reads them back."""

    def escape(text: str) -> str:
        return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    objects = ["<< /Type /Catalog /Pages 2 0 R >>", ""]
    kids = []
    font = 3 + 2 * len(pages)
    for lines in pages:
        content = "BT /F1 9 Tf 50 760 Td 11 TL " + " ".join(f"({escape(x)}) Tj T*" for x in lines)
        content += " ET"
        page_number, stream_number = len(objects) + 1, len(objects) + 2
        kids.append(f"{page_number} 0 R")
        objects.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources "
            f"<< /Font << /F1 {font} 0 R >> >> /Contents {stream_number} 0 R >>"
        )
        objects.append(f"<< /Length {len(content)} >>\nstream\n{content}\nendstream")
    objects[1] = f"<< /Type /Pages /Kids [{' '.join(kids)}] /Count {len(pages)} >>"
    objects.append("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    out, offsets = b"%PDF-1.4\n", []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n{body}\nendobj\n".encode("latin-1")
    start = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    out += b"".join(f"{offset:010d} 00000 n \n".encode() for offset in offsets)
    out += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{start}\n%%EOF\n".encode()
    )
    return out


PAGES = [
    ["A Paper", "1 Introduction", "We build on prior work [1, 2].", "References",
     "[1] K. He, X. Zhang, S. Ren, and J. Sun, \"Deep residual learning for image",
     "recognition,\" in Proc. CVPR, 2016, pp. 770-778.", "7"],
    ["Preprint", "[2] D. P. Kingma and J. Ba, \"Adam: A method for stochastic optimization,\" in",
     "Proc. ICLR, 2015.", "A Proofs", "Lemma 1 holds by [1].", "8"],
]  # fmt: skip


def test_the_list_after_references_up_to_an_appendix(tmp_path: Path) -> None:
    path = tmp_path / "paper.pdf"
    path.write_bytes(tiny_pdf(PAGES))
    bib = parse_pdf_file(path)
    assert bib.derived
    assert not bib.issues
    titles = [e.text("title") for e in bib.entries]
    assert titles == [
        "Deep residual learning for image recognition",
        "Adam: A method for stochastic optimization",
    ]
    assert bib.entries[1].text("author") == "D. P. Kingma and J. Ba"


def test_running_headers_and_page_numbers_are_dropped() -> None:
    text = "\n".join(
        [
            "Intro",
            "References",
            '[1] A. B, "T one," 2020.',
            "12",
            "Preprint",
            '[2] C. D, "T two," 2021.',
            "13",
            "Preprint",
            '[3] E. F, "T three," 2022.',
            "Preprint",
        ]
    )
    first, section = reference_section(text)
    assert first == 3
    assert "Preprint" not in section
    assert "\n12\n" not in f"\n{section}\n"


def test_no_reference_list(tmp_path: Path) -> None:
    path = tmp_path / "paper.pdf"
    path.write_bytes(tiny_pdf([["A Paper", "No citations here."]]))
    bib = parse_pdf_file(path)
    assert bib.entries == []
    assert bib.issues
    assert "no reference list" in bib.issues[0].detail


def test_a_pdf_checked_on_its_own(tmp_path: Path) -> None:
    path = tmp_path / "paper.pdf"
    path.write_bytes(tiny_pdf(PAGES))
    result = run_check(path)
    assert result.entries == 2
    assert result.bib_files[0].derived


def test_a_damaged_pdf(tmp_path: Path) -> None:
    path = tmp_path / "paper.pdf"
    path.write_bytes(b"%PDF-1.4\nnot really\n")
    bib = parse_pdf_file(path)
    assert bib.entries == []
    assert bib.issues


@pytest.mark.parametrize(
    ("lines", "first_reference"),
    [
        # small capitals come out letter-spaced: "R EFERENCES"
        (["Intro", "R EFERENCES", "[1] A. B, “T one,” 2020.", "[2] C. D, “T two,” 2021."], "[1]"),
        # APS journals print no heading: the list starts at its "[1]"
        (["See [1] and [2].", "text", "[1] A. B, T one, 2020.", "[2] C. D, T two, 2021."], "[1]"),
    ],
)
def test_where_the_list_starts(lines: list[str], first_reference: str) -> None:
    _, section = reference_section("\n".join(lines))
    assert section.startswith(first_reference)
    assert "See [1]" not in section


def test_where_the_list_ends() -> None:
    lines = [
        "Short Title of the Paper",  # the running header, on every page
        "References",
        "Fernandez, P., Sander, T., and Mourachko,",
        "A. How good is post-hoc watermarking with language",  # the reference runs on
        "model rephrasing? 2025.",
        "Short Title of the Paper",
        "Hayes, J. Another one. 2024.",
        "A Proofs",  # the appendix
        "Lemma 1 holds.",
    ]
    _, section = reference_section("\n".join(lines))
    assert "How good is post-hoc" in section
    assert "Hayes, J." in section
    assert "Lemma 1" not in section


def test_spaces_a_change_of_font_swallowed() -> None:
    text = "\n".join(
        [
            "References",
            "[1] S. Moraga,Optimal approximation, Calcolo, 61 (2024).",
            "[2] J.-H. Woo.ApJ, 795(1):30, 2014. E. Xinget al. InThe Thirty Seventh Conference.",
            "[3] T. J. Green, “Provenance semirings,” inProceedings of PODS, 2007.",
            "[4] H.-P. Breuer, The Theory of Open Quantum Systems(Oxford, 2002). Y. Bengio, Y .",
        ]
    )
    _, section = reference_section(text)
    for spaced in ("Moraga, Optimal", "Woo. ApJ", "Xing et al.", "In The Thirty",
                   "in Proceedings", "Systems (Oxford", "Bengio, Y."):  # fmt: skip
        assert spaced in section, spaced
