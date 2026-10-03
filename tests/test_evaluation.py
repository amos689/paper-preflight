import json
from pathlib import Path

from paper_preflight.bib.parse import parse_bib_text
from paper_preflight.evaluation.hallmark import (
    MODES,
    Example,
    Outcome,
    load,
    predict,
    render_markdown,
    score,
    to_bibtex,
)
from paper_preflight.findings import Location, Severity
from paper_preflight.rules import make_finding
from paper_preflight.verdict import Assessment, Reason, Verdict


def row(key: str, label: str, kind: str | None = None, **fields: str) -> dict[str, object]:
    return {
        "bibtex_key": key, "bibtex_type": "inproceedings", "label": label,
        "hallucination_type": kind, "fields": fields or {"Title": "A Title", "year": "2021"},
    }  # fmt: skip


def test_load_skips_the_canary_and_normalises_fields(tmp_path: Path) -> None:
    path = tmp_path / "split.jsonl"
    rows = [
        row("__canary__x", "VALID"),
        row("v1", "VALID"),
        row("h1", "HALLUCINATED", "plausible_fabrication"),
        row("h2", "HALLUCINATED", "merged_citation"),
    ]
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    examples = load(path)
    assert [e.key for e in examples] == ["v1", "h1", "h2"]
    assert examples[0].fields == {"title": "A Title", "year": "2021"}
    assert (examples[1].hallucinated, examples[1].tier, examples[1].stress) == (True, 3, False)
    assert examples[2].stress


def test_to_bibtex_round_trips_through_the_parser() -> None:
    example = Example(
        key="k1", entry_type="inproceedings", hallucinated=False, kind=None, tier=None,
        fields={
            "title": "Unbalanced {brace in a\n title", "author": "Simon Reiß and Ann Lee",
            "year": "2021", "doi": "10.1109/CVPR46437.2021.00143",
        },
    )  # fmt: skip
    (entry,) = parse_bib_text(to_bibtex(example), Path("x.bib")).entries
    assert entry.key == "k1"
    assert entry.text("title") == "Unbalanced brace in a title"
    assert entry.text("author") == "Simon Reiß and Ann Lee"
    assert entry.text("doi") == "10.1109/CVPR46437.2021.00143"


def assessment(verdict: Verdict, *rules: tuple[str, Severity | None]) -> Assessment:
    location = Location(Path("x.bib"), 1)
    findings = tuple(make_finding(rule, location, key="k", severity=sev) for rule, sev in rules)
    reasons = (Reason.GREY_LITERATURE,) if verdict is Verdict.CANNOT_DETERMINE else ()
    return Assessment("k", verdict, reasons=reasons, findings=findings)


def test_predict_by_mode() -> None:
    fabrication, any_issue = MODES["fabrication"], MODES["any_issue"]
    not_found = assessment(Verdict.NOT_FOUND, ("REF003", None))
    wrong_year = assessment(Verdict.METADATA_MISMATCH, ("REF013", None))
    omitted_authors = assessment(Verdict.VERIFIED, ("REF011", Severity.INFO))
    published_preprint = assessment(Verdict.VERIFIED, ("REF015", None))
    abstained = assessment(Verdict.CANNOT_DETERMINE, ("REF090", None))
    assert predict(not_found, fabrication) == "flag"
    assert (predict(wrong_year, fabrication), predict(wrong_year, any_issue)) == ("clean", "flag")
    assert predict(omitted_authors, any_issue) == "clean"  # info findings never count
    assert predict(published_preprint, any_issue) == "clean"  # advice, not a hallucination
    assert predict(abstained, any_issue) == "abstain"


def example(key: str, kind: str | None) -> Example:
    return Example(key, "inproceedings", {}, kind is not None, kind, None if kind is None else 3)


def test_scores() -> None:
    examples = [
        example("v1", None), example("v2", None), example("v3", None), example("v4", None),
        example("h1", "plausible_fabrication"), example("h2", "plausible_fabrication"),
        example("h3", "near_miss_title"), example("s1", "merged_citation"),
    ]  # fmt: skip
    outcomes: dict[str, Outcome] = {
        "v1": "clean", "v2": "clean", "v3": "flag", "v4": "abstain",
        "h1": "flag", "h2": "flag", "h3": "abstain", "s1": "flag",
    }  # fmt: skip
    scores = score(examples, {"fabrication": outcomes})["fabrication"]
    assert scores.precision == 2 / 3  # stress entries are not part of the main scores
    assert scores.recall == 2 / 3  # the abstention on h3 counts as a miss
    assert scores.false_positive_rate == 1 / 4
    assert scores.coverage == 5 / 7
    assert scores.stress.flag == 1
    assert scores.by_type["plausible_fabrication"].flag == 2
    markdown = render_markdown({"fabrication": scores}, {"Data": "synthetic"})
    assert "| fabrication | 66.7% | 66.7% |" in markdown
    assert "| merged_citation (stress) |" in markdown
