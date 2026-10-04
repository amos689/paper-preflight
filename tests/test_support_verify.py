"""The local verifiers reproduce their authors' reference scores (only where the weights are
cached: CI does not download 5 GB of models)."""

import os

import pytest

pytest.importorskip("torch")
pytest.importorskip("transformers")

from huggingface_hub import try_to_load_from_cache

from paper_preflight.support import verify


def cached(repo: str, filename: str) -> bool:
    return isinstance(try_to_load_from_cache(repo, filename), str)


@pytest.fixture(autouse=True)
def _offline(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")


@pytest.mark.skipif(
    not cached(verify.MINICHECK, "pytorch_model.bin"), reason="MiniCheck weights not cached"
)
def test_minicheck_matches_its_model_card() -> None:
    doc = (
        "A group of students gather in the school library to study for their upcoming final exams."
    )
    model = verify.MiniCheck()
    yes = model.scores("The students are preparing for an examination.", [doc])[0]
    no = model.scores("The students are on vacation.", [doc])[0]
    assert (round(yes, 4), round(no, 4)) == (0.9806, 0.0071)


@pytest.mark.skipif(not cached(verify.HHEM, "model.safetensors"), reason="HHEM weights not cached")
def test_hhem_matches_its_model_card_without_remote_code() -> None:
    model = verify.Hhem()
    pairs = [
        ("I am in California", "I am in United States."),
        ("I am in United States", "I am in California."),
    ]
    scores = [model.scores(hypothesis, [premise])[0] for premise, hypothesis in pairs]
    assert [round(s, 3) for s in scores] == [0.647, 0.129]


@pytest.mark.skipif(
    not cached(verify.FACTCG, "model.safetensors"), reason="FactCG weights not cached"
)
def test_factcg_separates_support_from_contradiction() -> None:
    doc = (
        "A group of students gather in the school library to study for their upcoming final exams."
    )
    model = verify.FactCG()
    yes = model.scores("The students are preparing for an examination.", [doc])[0]
    no = model.scores("The students are on vacation.", [doc])[0]
    assert yes > 0.9 > 0.1 > no
