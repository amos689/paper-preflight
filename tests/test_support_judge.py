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


def test_a_name_the_title_carries_confirms_its_citation() -> None:
    from paper_preflight.support.judge import name_in_title

    assert name_in_title("Adam", "Adam: A Method for Stochastic Optimization")
    assert name_in_title("Dropout", "Dropout - a simple way to prevent overfitting")
    assert name_in_title("BERT", "BERT: Pre-training of Deep Bidirectional Transformers")
    assert name_in_title("GPT-4", "GPT-4 Technical Report")
    assert name_in_title("GELU", "Gaussian Error Linear Units (GELUs)")
    assert name_in_title("ImageNet", "ImageNet Large Scale Visual Recognition Challenge")
    # a plain word only as the title's own name; an acronym only as a whole word
    assert not name_in_title("Adam", "On the convergence of Adam and beyond")
    assert not name_in_title("Diffusion", "High-Resolution Image Synthesis with Latent Diffusion")
    assert not name_in_title("GPT", "GPT-4 Technical Report")
    assert not name_in_title("", "Adam: A Method")
    assert not name_in_title("Adam", "")
    title = "Adam: A Method for Stochastic Optimization"
    claim = "We train with a learning rate of 0.001."
    named = judge(claim, evidence(FULL_TEXT, ABSTRACT_TEXT, RESULT), Overlap(), name="Adam",
                  title=title)  # fmt: skip
    assert (named.verdict, named.reason, named.quote) == (SUPPORTED, "NAME_IN_TITLE", title)
    no_text = judge(claim, evidence(NONE), Overlap(), name="Adam", title=title)
    assert (no_text.verdict, no_text.reason) == (SUPPORTED, "NAME_IN_TITLE")
    other = judge(claim, evidence(NONE), Overlap(), name="Adam", title="Attention Is All You Need")
    assert (other.verdict, other.reason) == (NOT_CONFIRMED, "NO_TEXT")
