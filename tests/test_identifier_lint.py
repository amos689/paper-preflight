from pathlib import Path

from paper_preflight.bib.parse import parse_bib_text
from paper_preflight.identifier_lint import check_identifier_syntax


def findings(bib: str) -> list[tuple[str, str | None, str]]:
    entries = parse_bib_text(bib, Path("refs.bib")).entries
    return [(f.field or "", f.key, f.data["detail"]) for f in check_identifier_syntax(entries)]


def test_escaped_doi_is_flagged_with_canonical_suggestion() -> None:
    entries = parse_bib_text(
        "@article{nq,\n  title = {NQ},\n  doi = {10.1162/tacl\\_a\\_00276},\n}\n", Path("refs.bib")
    ).entries
    (finding,) = check_identifier_syntax(entries)
    assert finding.rule_id == "REF017"
    assert finding.location is not None
    assert finding.location.line == 3
    assert finding.data["suggestion"] == "10.1162/tacl_a_00276"
    assert "LaTeX" in finding.message.en
    assert "转义" in finding.message.zh


def test_url_prefix_and_invalid_doi() -> None:
    assert findings("@article{a, doi = {https://doi.org/10.1109/CVPR.2016.90}}") == [
        ("doi", "a", "escaped")
    ]
    assert findings("@article{a, doi = {not-a-doi}}") == [("doi", "a", "invalid")]


def test_canonical_values_pass() -> None:
    assert findings("@article{a, doi = {10.1109/CVPR.2016.90}}") == []
    assert findings("@article{a, doi = {10.1016/S0140-6736(97)11096-0}}") == []
    assert (
        findings("@article{a, doi = {10.1002/1097-0347(200103)23:3<230::AID-HED1023>3.0.CO;2-V}}")
        == []
    )
    assert findings("@misc{a, eprint = {1706.03762}, archivePrefix = {arXiv}}") == []
    assert findings("@misc{a, eprint = {hep-th/9901001v2}, archivePrefix = {arXiv}}") == []


def test_bad_arxiv_eprint() -> None:
    assert findings("@misc{a, eprint = {1706.0376x}, archivePrefix = {arXiv}}") == [
        ("eprint", "a", "invalid-eprint")
    ]


def test_versioned_arxiv_doi_gets_a_safe_fix() -> None:
    entries = parse_bib_text("@misc{a, doi = {10.48550/arXiv.2602.12139v1}}", Path("refs.bib"))
    (finding,) = check_identifier_syntax(entries.entries)
    assert finding.rule_id == "REF017"
    assert finding.data["suggestion"] == "10.48550/arxiv.2602.12139"
    assert "version suffix" in finding.message.en
    assert "版本号后缀" in finding.message.zh
