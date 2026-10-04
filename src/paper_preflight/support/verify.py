"""Local verifier models: how strongly a passage supports a claim (S4). Needs the ``support``
extra (PyTorch, transformers).

Each model is called the way its authors' own inference code calls it:

* **FactCG-DeBERTa-v3-Large** (MIT; Lei et al., NAACL 2025): the passage and claim in FactCG's
  instruction template, a two-way classifier, label 1 = supported;
* **MiniCheck-Flan-T5-Large** (MIT; Tang et al., EMNLP 2024): ``predict: passage</s>claim``,
  one decoder step, the probability of token 209 ("1") against token 3 ("0");
* **HHEM-2.1-open** (Apache-2.0; Vectara): Flan-T5-base with a token-classification head on
  HHEM's premise/hypothesis prompt, label 1 = consistent. Its weights are loaded into the
  standard transformers class, so no code from the model repository runs.

Weights come from the Hugging Face cache; ``download`` fetches them the first time, after the
user agreed (they are 0.4 to 3 GB).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

FACTCG = "yaxili96/FactCG-DeBERTa-v3-Large"
MINICHECK = "lytang/MiniCheck-Flan-T5-Large"
HHEM = "vectara/hallucination_evaluation_model"
HHEM_FOUNDATION = "google/flan-t5-base"
FACTCG_TEMPLATE = (
    "{text_a}\n\nChoose your answer: based on the paragraph above can we conclude that "
    '"{text_b}"?\n\nOPTIONS:\n- Yes\n- No\nI think the answer is '
)
HHEM_PROMPT = (
    "<pad> Determine if the hypothesis is true given the premise?\n\n"
    "Premise: {text1}\n\nHypothesis: {text2}"
)
BATCH = 8
MAX_TOKENS = 2048


class SupportExtraMissing(RuntimeError):
    """PyTorch or transformers is not installed."""


def _torch() -> Any:
    try:
        import torch
        import transformers  # noqa: F401
    except ImportError as exc:  # pragma: no cover - depends on the environment
        raise SupportExtraMissing(
            "checking citation support needs the support extra: "
            "pip install 'paper-preflight[support]'"
        ) from exc
    return torch


def _batches(items: Sequence[Any], size: int = BATCH) -> list[Sequence[Any]]:
    return [items[i : i + size] for i in range(0, len(items), size)]


class FactCG:
    name = "factcg"

    def __init__(self, *, local_only: bool = True) -> None:
        torch = _torch()
        from transformers import AutoConfig, AutoModelForSequenceClassification, AutoTokenizer

        config = AutoConfig.from_pretrained(FACTCG, num_labels=2, local_files_only=local_only)
        self.tokenizer = AutoTokenizer.from_pretrained(FACTCG, local_files_only=local_only)
        self.model = AutoModelForSequenceClassification.from_pretrained(
            FACTCG, config=config, local_files_only=local_only
        ).eval()
        self.torch = torch

    def scores(self, claim: str, passages: Sequence[str]) -> list[float]:
        out: list[float] = []
        for batch in _batches(passages):
            texts = [FACTCG_TEMPLATE.format(text_a=p, text_b=claim) for p in batch]
            inputs = self.tokenizer(
                texts, max_length=MAX_TOKENS, truncation=True, padding="longest",
                return_tensors="pt",
            )  # fmt: skip
            with self.torch.no_grad():
                logits = self.model(**inputs).logits
            out.extend(self.torch.softmax(logits, dim=-1)[:, 1].tolist())
        return out


class MiniCheck:
    name = "minicheck"

    def __init__(self, *, local_only: bool = True) -> None:
        torch = _torch()
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

        self.tokenizer = AutoTokenizer.from_pretrained(MINICHECK, local_files_only=local_only)
        self.model = AutoModelForSeq2SeqLM.from_pretrained(
            MINICHECK, local_files_only=local_only
        ).eval()
        self.torch = torch

    def scores(self, claim: str, passages: Sequence[str]) -> list[float]:
        out: list[float] = []
        eos = self.tokenizer.eos_token
        for batch in _batches(passages):
            texts = [f"predict: {p}{eos}{claim}" for p in batch]
            inputs = self.tokenizer(
                texts, max_length=MAX_TOKENS, truncation=True, padding=True, return_tensors="pt"
            )
            start = self.torch.zeros((len(texts), 1), dtype=self.torch.long)
            with self.torch.no_grad():
                logits = self.model(**inputs, decoder_input_ids=start).logits.squeeze(1)
            labels = logits[:, self.torch.tensor([3, 209])]  # "0" (no support) and "1"
            out.extend(self.torch.softmax(labels, dim=-1)[:, 1].tolist())
        return out


class Hhem:
    name = "hhem"

    def __init__(self, *, local_only: bool = True) -> None:
        torch = _torch()
        from huggingface_hub import hf_hub_download
        from safetensors.torch import load_file
        from transformers import AutoConfig, AutoTokenizer, T5ForTokenClassification

        config = AutoConfig.from_pretrained(HHEM_FOUNDATION, local_files_only=local_only)
        config.num_labels = 2
        self.model: Any = T5ForTokenClassification(config)
        self.model.eval()  # type: ignore[no-untyped-call,unused-ignore]
        weights = load_file(hf_hub_download(HHEM, "model.safetensors", local_files_only=local_only))
        state = {k.removeprefix("t5."): v for k, v in weights.items() if k.startswith("t5.")}
        self.model.load_state_dict(state, strict=False)
        self.tokenizer = AutoTokenizer.from_pretrained(HHEM_FOUNDATION, local_files_only=local_only)
        self.torch = torch

    def scores(self, claim: str, passages: Sequence[str]) -> list[float]:
        out: list[float] = []
        for batch in _batches(passages):
            texts = [HHEM_PROMPT.format(text1=p, text2=claim) for p in batch]
            inputs = self.tokenizer(
                texts, max_length=MAX_TOKENS, truncation=True, padding=True, return_tensors="pt"
            )
            with self.torch.no_grad():
                logits = self.model(**inputs).logits[:, 0, :]
            out.extend(self.torch.softmax(logits, dim=-1)[:, 1].tolist())
        return out


VERIFIERS: dict[str, type[FactCG | MiniCheck | Hhem]] = {
    "factcg": FactCG, "minicheck": MiniCheck, "hhem": Hhem,
}  # fmt: skip
# what each verifier downloads the first time: (repository, files, size, licence)
DOWNLOADS: dict[str, list[tuple[str, list[str]]]] = {
    "factcg": [(FACTCG, ["*.json", "*.safetensors", "spm.model"])],
    "minicheck": [(MINICHECK, ["*.json", "pytorch_model.bin", "spiece.model"])],
    "hhem": [
        (HHEM, ["*.json", "*.safetensors"]),
        (HHEM_FOUNDATION, ["config.json", "tokenizer*", "spiece.model", "special_tokens_map.json"]),
    ],
}
SIZES = {"factcg": "1.7 GB, MIT", "minicheck": "3.1 GB, MIT", "hhem": "0.4 GB, Apache-2.0"}
_MAIN_FILE = {
    "factcg": (FACTCG, "model.safetensors"),
    "minicheck": (MINICHECK, "pytorch_model.bin"),
    "hhem": (HHEM, "model.safetensors"),
}


def is_cached(name: str) -> bool:
    """Whether the verifier's weights are already in the Hugging Face cache."""
    from huggingface_hub import try_to_load_from_cache

    repo, filename = _MAIN_FILE[name]
    return isinstance(try_to_load_from_cache(repo, filename), str)


def download(name: str) -> None:
    """Fetch the verifier's weights into the Hugging Face cache (the user asked for it)."""
    from huggingface_hub import snapshot_download

    for repo, patterns in DOWNLOADS[name]:
        snapshot_download(repo, allow_patterns=patterns)
