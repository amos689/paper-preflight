"""Ranking a cited work's passages for a claim."""

from paper_preflight.support.retrieve import rank, tokens

PASSAGES = [
    "We present a model for sentiment classification.",  # the abstract
    "Training uses Adam with a learning rate of 0.001 for ten epochs.",
    "On SST-2 the model reaches 93.5% accuracy, against 91.2% for the baseline.",
    "Related work on sentiment covers lexicons and recurrent networks.",
    "We thank the reviewers.",
    "On SST-2 accuracy is reported for every model in the table.",
]


def test_tokens_keep_numbers_whole() -> None:
    assert tokens("The model reaches 93.5% on SST-2 (Liu et al.)") == [
        "model", "reaches", "93.5%", "sst-2", "liu",
    ]  # fmt: skip


def test_the_passage_with_the_claims_numbers_comes_first() -> None:
    hits = rank("The model reaches 93.5% accuracy on SST-2.", PASSAGES, top=3)
    assert hits[0].index == 2
    assert hits[0].numbers
    assert not any(h.numbers for h in hits[1:])


def test_the_abstract_is_always_returned() -> None:
    hits = rank("learning rate of 0.001 with Adam", PASSAGES, top=2)
    assert [h.index for h in hits] == [1, 0]
    assert rank("anything", []) == []
