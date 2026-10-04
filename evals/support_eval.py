"""Measure ``support``'s verifiers on the gold set (third-round plan, S4 and S5).

    uv run python evals/support_eval.py score hhem     # scores per pair (CPU: a few minutes)
    uv run python evals/support_eval.py score hhem --every-passage   # (CPU: about 20 minutes)
    uv run python evals/support_eval.py report         # each verifier against the labels

``support`` is an evidence finder: it says "supported" with a quote, or "could not confirm".
For every pair the claim's passages are ranked as ``support`` ranks them (S3) and scored by
the verifier; ``report`` tries thresholds and passage budgets and reports, for each:

* precision of "supported" (gate 0.9; "lenient" also counts partially supported claims);
* recall: the share of supported citations it confirms;
* the share of all real citations it confirms, and how many mis-citations it confirmed.

The threshold and passage budget chosen here become ``support``'s defaults. The labels are AI
annotators' (evals/support_guidelines.md), not experts'.
"""

from __future__ import annotations

import argparse
import json
import time
import tomllib
from pathlib import Path
from typing import Any

from paper_preflight.support.evidence import FULL_TEXT, Evidence
from paper_preflight.support.retrieve import rank

ROOT = Path(__file__).resolve().parent
GOLD = ROOT / "support_gold.toml"
SUPPORT = ROOT / ".data" / "support"
SCORES = SUPPORT / "scores"
LABELS = ROOT / ".data" / "support" / "final_labels.json"


def _evidence(packet: str) -> Evidence:
    data = json.loads((SUPPORT / "packets" / f"{packet}.json").read_text(encoding="utf-8"))
    full = SUPPORT / "packets" / f"{packet}.fulltext.txt"
    passages: list[str] = []
    if full.exists() and data["full_text_file"]:
        for block in full.read_text(encoding="utf-8").split("\n\n"):
            passages.append(block.split("] ", 1)[1] if block.startswith("[") else block)
    return Evidence(data["evidence_level"], data["evidence_source"], tuple(passages))


MAX_PASSAGES = 400  # every-passage scoring reads at most this many passages of a work


def score(model: str, every_passage: bool = False) -> None:
    """Score each pair's top-ranked passages (``<model>.json``), or, with ``every_passage``,
    every passage of the full texts (``<model>_all.json``, for choosing the passage budget)."""
    from paper_preflight.support.verify import VERIFIERS

    verifier = VERIFIERS[model]()
    SCORES.mkdir(parents=True, exist_ok=True)
    out = SCORES / f"{model}_all.json" if every_passage else SCORES / f"{model}.json"
    done: dict[str, Any] = json.loads(out.read_text(encoding="utf-8")) if out.exists() else {}
    pairs = tomllib.loads(GOLD.read_text(encoding="utf-8"))["pair"]
    started = time.time()
    for n, pair in enumerate(pairs, 1):
        if pair["packet"] in done:
            continue
        evidence = _evidence(pair["packet"])
        if every_passage:
            if evidence.level != FULL_TEXT:
                continue
            passages = list(evidence.passages[:MAX_PASSAGES])
            done[pair["packet"]] = [round(s, 4) for s in verifier.scores(pair["claim"], passages)]
        else:
            hits = rank(pair["claim"], evidence.passages) if evidence.passages else []
            scores = verifier.scores(pair["claim"], [evidence.passages[h.index] for h in hits])
            done[pair["packet"]] = {
                "level": evidence.level,
                "passages": [h.index for h in hits],
                "scores": [round(s, 4) for s in scores],
            }
        if n % 10 == 0:
            out.write_text(json.dumps(done), encoding="utf-8")
            print(f"{n}/{len(pairs)} {time.time() - started:.0f} s", flush=True)
    out.write_text(json.dumps(done), encoding="utf-8")


def _bests(path: Path, pairs: dict[str, Any]) -> dict[str, dict[str, float]]:
    """The best passage score per pair, for each passage budget the file allows: "top 4" for a
    score file of ranked passages; "top k" and "all" for one with every passage's score."""
    data = json.loads(path.read_text(encoding="utf-8"))
    out: dict[str, dict[str, float]] = {}
    for packet, item in data.items():
        if isinstance(item, dict):  # the top-ranked passages only
            out[packet] = {"top 4": max(item["scores"], default=-1.0)}
            continue
        evidence = _evidence(packet)  # every passage's score, in passage order
        ranked = [h.index for h in rank(pairs[packet]["claim"], evidence.passages, top=10**6)]
        out[packet] = {
            f"top {k}": max((item[i] for i in ranked[:k] if i < len(item)), default=-1.0)
            for k in (4, 8, 12, 20)
        }
        out[packet]["all"] = max(item, default=-1.0)
    return out


def report() -> None:
    """Evidence-finder metrics: how often "supported" is right, and how many it finds."""
    labels: dict[str, str] = json.loads(LABELS.read_text(encoding="utf-8"))
    pairs = {p["packet"]: p for p in tomllib.loads(GOLD.read_text(encoding="utf-8"))["pair"]}
    real = [p for p in labels if "swapped" not in pairs[p]]
    supported = [p for p in real if labels[p] == "supported"]
    print(f"{len(labels)} pairs: {len(real)} real citations ({len(supported)} supported), "
          f"{len(labels) - len(real)} mis-citations")  # fmt: skip
    for path in sorted(SCORES.glob("*.json")):
        bests = _bests(path, pairs)
        budgets = sorted({b for v in bests.values() for b in v})
        for budget in budgets:
            print(f"\n== {path.stem}, {budget} passages ({len(bests)} pairs scored)")
            print("support_at | said | precision | lenient | recall | real confirmed | "
                  "mis-citations confirmed")  # fmt: skip
            for at in (0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9):
                said = [p for p, b in bests.items() if b.get(budget, -1.0) >= at]
                strict = sum(labels[p] == "supported" for p in said) / max(len(said), 1)
                lenient = sum(labels[p] in {"supported", "partially_supported"} for p in said)
                found = sum(p in said for p in supported) / max(len(supported), 1)
                share = sum(p in said for p in real) / max(len(real), 1)
                wrong = sum("swapped" in pairs[p] and labels[p] == "not_supported" for p in said)
                print(f"{at:>10} | {len(said):>4} | {strict:>9.2f} | "
                      f"{lenient / max(len(said), 1):>7.2f} | {found:>6.2f} | {share:>14.0%} | "
                      f"{wrong:>23}")  # fmt: skip


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("command", choices=["score", "report"])
    parser.add_argument("model", nargs="?", default="hhem")
    parser.add_argument(
        "--every-passage", action="store_true", help="score every passage of the full texts"
    )
    args = parser.parse_args()
    if args.command == "score":
        score(args.model, args.every_passage)
    else:
        report()


if __name__ == "__main__":
    main()
