"""Judging a claim against a cited work's text, with a stand-in verifier."""

from collections.abc import Sequence

from paper_preflight.support.evidence import ABSTRACT, FULL_TEXT, NONE, Evidence
from paper_preflight.support.judge import NOT_CONFIRMED, SUPPORTED, judge
from paper_preflight.support.retrieve import tokens


class Overlap:
    """Share of the claim's words found in the passage: a stand-in for a verifier model."""

    def scores(self, claim: str, passages: Sequence[str]) -> list[float]:
        wanted = set(tokens(claim))
        return [len(wanted & set(tokens(p))) / max(len(wanted), 1) for p in passages]


ABSTRACT_TEXT = "We present a sentiment model."
RESULT = "Training took a day. On SST-2 the model reaches 93.5% accuracy. Code is public."


def evidence(level: str, *passages: str) -> Evidence:
    return Evidence(level, "test", tuple(passages))


def test_a_supporting_passage_is_quoted_exactly() -> None:
    found = judge(
        "The model reaches 93.5% accuracy on SST-2.",
        evidence(FULL_TEXT, ABSTRACT_TEXT, RESULT),
        Overlap(),
    )
    assert (found.verdict, found.reason, found.passage) == (SUPPORTED, "SUPPORTING_PASSAGE", 1)
    assert found.quote == "On SST-2 the model reaches 93.5% accuracy."
    assert found.quote in RESULT


def test_nothing_is_ever_called_unsupported() -> None:
    claim = "Quantum annealing solves protein folding exactly."
    full = judge(claim, evidence(FULL_TEXT, ABSTRACT_TEXT, RESULT), Overlap())
    assert (full.verdict, full.reason) == (NOT_CONFIRMED, "NOT_FOUND")
    abstract = judge(claim, evidence(ABSTRACT, ABSTRACT_TEXT), Overlap())
    assert (abstract.verdict, abstract.reason) == (NOT_CONFIRMED, "ABSTRACT_ONLY")
    nothing = judge(claim, evidence(NONE), Overlap())
    assert (nothing.verdict, nothing.reason) == (NOT_CONFIRMED, "NO_TEXT")
