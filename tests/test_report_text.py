from __future__ import annotations

import io
from pathlib import Path

from rich.console import Console

from paper_preflight.check import CheckResult
from paper_preflight.report.text import render_text
from paper_preflight.rules import make_finding


def _published(key: str):  # type: ignore[no-untyped-def]
    return make_finding(
        "REF015", None, key=key, found_venue="ACL", found_year=2019, doi_note="", doi_note_zh=""
    )


def _render(count: int, *, details: bool = False, lang: str = "en") -> str:
    findings = [_published(f"paper{i}") for i in range(count)]
    result = CheckResult(
        root=Path("."), main=None, bib_files=[], findings=findings, cited_keys=0, entries=0,
        used_build_data=None,
    )  # fmt: skip
    buffer = io.StringIO()
    render_text(result, Console(file=buffer, width=400, color_system=None), lang, True, details)
    return buffer.getvalue()


def test_many_published_preprints_are_one_line() -> None:
    text = _render(8)
    assert "REF015 ×8" in text
    assert "8 cited preprints have since been published" in text
    assert "paper0, paper1, paper2, paper3, paper4, paper5 and 2 more" in text
    assert text.count("REF015") == 1
    assert "0 error(s) · 8 warning(s)" in text  # the counts do not change


def test_details_and_small_counts_list_each_finding() -> None:
    assert _render(8, details=True).count("warning REF015") == 8
    assert _render(2).count("warning REF015") == 2  # below the threshold: listed as before


def test_grouped_line_in_chinese() -> None:
    text = _render(7, lang="zh")
    assert "有 7 条被引的预印本已正式发表" in text
    assert "paper5等 7 条" in text
