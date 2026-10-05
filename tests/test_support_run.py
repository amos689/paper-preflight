"""``support`` end to end on the demo paper, against the recorded web."""

from collections.abc import Sequence
from pathlib import Path

import pytest

from paper_preflight.bib.parse import parse_bib_text
from paper_preflight.support.evidence import Work
from paper_preflight.support.judge import NOT_CONFIRMED
from paper_preflight.support.run import _once, run_support, work_for
from paper_preflight.support.sentences import citation_sentences
from paper_preflight.tex.project import load_project
from paper_preflight.verdict import Assessment, Verdict

from .fake_web import FakeWeb

pytestmark = pytest.mark.usefixtures("fast")

DEMO = Path(__file__).parent.parent / "examples" / "demo-paper"


class Never:
    def scores(self, claim: str, passages: Sequence[str]) -> list[float]:
        return [0.3] * len(passages)


def test_work_prefers_the_entrys_arxiv_version() -> None:
    (entry,) = parse_bib_text(
        "@misc{k, title={T}, eprint={1606.08415}, archivePrefix={arXiv}}", Path("r.bib")
    ).entries
    assert work_for(entry, Assessment("k", Verdict.VERIFIED)) == Work(arxiv="1606.08415")
    (doi_only,) = parse_bib_text("@misc{k, title={T}, doi={10.48550/arXiv.1606.08415}}",
                                 Path("r.bib")).entries  # fmt: skip
    assert work_for(doi_only, Assessment("k", Verdict.VERIFIED)) == Work(arxiv="1606.08415")
    (bare,) = parse_bib_text("@misc{k, title={T}}", Path("r.bib")).entries
    assert work_for(bare, Assessment("k", Verdict.VERIFIED)) is None


def test_demo_paper(recorded_web: FakeWeb, tmp_path: Path) -> None:
    result = run_support(DEMO, Never(), cache_path=tmp_path / "c.sqlite3", folder=tmp_path / "s")
    checked = {item.citation.key for item in result.items}
    assert "hendrycks2016gelu" in checked
    assert result.skipped["lindqvist2024quantum"] == "not verified (not_found)"
    assert result.skipped["devlin2019bert"] == "not verified (identifier_conflict)"
    assert result.skipped["goodfellow2016deep"] == "not verified (cannot_determine)"
    assert not checked & set(result.skipped)
    # a verifier that is never sure confirms no passage, and accuses nobody; "Adam \cite{x}" and
    # "GELU activations \cite{y}" are confirmed by the titles of the works they cite
    confirmed = {
        i.citation.key: i.judgement for i in result.items if i.judgement.verdict != NOT_CONFIRMED
    }
    assert set(confirmed) == {"kingma2015adam", "hendrycks2016gelu"}
    assert {j.reason for j in confirmed.values()} == {"NAME_IN_TITLE"}
    assert confirmed["kingma2015adam"].quote.startswith("Adam: A Method")
    assert all(item.citation.claim for item in result.items)


def test_a_work_cited_twice_in_a_sentence_is_judged_once(tmp_path: Path) -> None:
    (tmp_path / "main.tex").write_text(
        r"\documentclass{article}\begin{document}"
        "\n"
        r"Dropout \cite{a} regularises large networks well \cite{a}."
        "\n"
        r"\bibliography{r}\end{document}",
        encoding="utf-8",
    )
    sentences = citation_sentences(load_project(tmp_path))
    assert [s.key for s in sentences] == ["a", "a"]
    assert [s.column for s in _once(sentences)] == [sentences[0].column]


@pytest.fixture(autouse=True)
def _no_arxiv_wait(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("paper_preflight.support.evidence.EPRINT_INTERVAL", 0.0)
