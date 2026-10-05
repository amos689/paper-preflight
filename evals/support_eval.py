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
import random
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
REAL_PAPERS = ROOT / ".data" / "real_papers"  # the gold set's papers (evals/real_papers.py)
REAL_REPORTS = ROOT / ".data" / "real_papers_reports"


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


def named_by_title(pairs: dict[str, Any]) -> set[str]:
    """Pairs the name check confirms: the citation is set right after a name the cited work's
    title carries ("Adam \\cite{x}"). Names are read from the papers' sources and titles from
    their check reports (evals/real_papers.py); a swapped pair's work is the other reference's."""
    from paper_preflight.support.judge import name_in_title
    from paper_preflight.support.sentences import citation_sentences
    from paper_preflight.tex.project import find_main_file, load_project

    found: set[str] = set()
    for paper in sorted({p["paper"] for p in pairs.values()}):
        folder = REAL_PAPERS / paper
        names = {
            (s.key, s.line): s.name
            for s in citation_sentences(load_project(folder, main=find_main_file(folder)))
            if s.name
        }
        report = json.loads((REAL_REPORTS / f"{paper}.json").read_text(encoding="utf-8"))
        titles = {r["key"]: r["matched"]["title"] for r in report["references"] if r["matched"]}
        for packet, pair in pairs.items():
            name = names.get((pair["key"], pair["line"]), "") if pair["paper"] == paper else ""
            work = pair.get("swapped") or pair["key"]
            if name and name_in_title(name, titles.get(work, "")):
                found.add(packet)
    return found


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
    named = named_by_title(pairs)
    hhem = _bests(SCORES / "hhem.json", pairs)
    print(f"\n== the name check: {len(named)} pairs confirmed by the cited work's title")
    for label, said in (
        ("hhem top 4 at 0.4", {p for p, b in hhem.items() if b.get("top 4", -1.0) >= 0.4}),
        ("... and the name check", {p for p, b in hhem.items() if b.get("top 4", -1.0) >= 0.4}
         | named),
    ):  # fmt: skip
        right = sum(labels[p] == "supported" for p in said)
        wrong = sum("swapped" in pairs[p] and labels[p] == "not_supported" for p in said)
        print(f"{label}: said {len(said)}, right {right / max(len(said), 1):.2f}, "
              f"supported confirmed {sum(p in said for p in supported)}/{len(supported)}, "
              f"real confirmed {sum(p in said for p in real)}/{len(real)}, "
              f"mis-citations confirmed {wrong}")  # fmt: skip


AGENT = SUPPORT / "agent"
AGENT_SAMPLE, AGENT_SEED, AGENT_CHUNK = 100, 20261005, 25


def agent_packets() -> None:
    """Write what ``preflight_cited_passages`` gives an agent, for a random sample of the gold
    set: the claim, its sentence and the cited work's 8 passages ranked for it. Agents judge
    them by the tool's rules and write one JSON line per pair to verdicts_<chunk>.jsonl:
    {"packet": ..., "verdict": "confirmed" | "not_confirmed", "quote": ..., "reason": ...}."""
    from paper_preflight.mcp_server import PASSAGE_CHARS, _clip

    pairs = tomllib.loads(GOLD.read_text(encoding="utf-8"))["pair"]
    sample = random.Random(AGENT_SEED).sample(pairs, AGENT_SAMPLE)
    AGENT.mkdir(parents=True, exist_ok=True)
    for start in range(0, len(sample), AGENT_CHUNK):
        lines = []
        for pair in sample[start : start + AGENT_CHUNK]:
            evidence = _evidence(pair["packet"])
            hits = rank(pair["claim"], evidence.passages, top=8) if evidence.passages else []
            lines.append(json.dumps({
                "packet": pair["packet"], "claim": pair["claim"], "sentence": pair["sentence"],
                "evidence_level": evidence.level,
                "passages": [_clip(evidence.passages[h.index], PASSAGE_CHARS) for h in hits],
            }, ensure_ascii=False))  # fmt: skip
        out = AGENT / f"packets_{start // AGENT_CHUNK + 1}.jsonl"
        out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"{len(sample)} pairs in {AGENT}")


def agent_score() -> None:
    """How the agents' verdicts compare with the labels, like ``report`` does for a model.
    A "confirmed" whose quote is not word for word in a passage counts as not confirmed."""
    labels: dict[str, str] = json.loads(LABELS.read_text(encoding="utf-8"))
    pairs = {p["packet"]: p for p in tomllib.loads(GOLD.read_text(encoding="utf-8"))["pair"]}
    shown = {
        item["packet"]: item
        for path in sorted(AGENT.glob("packets_*.jsonl"))
        for item in map(json.loads, path.read_text(encoding="utf-8").splitlines())
    }
    verdicts = {
        item["packet"]: item
        for path in sorted(AGENT.glob("verdicts_*.jsonl"))
        for item in map(json.loads, path.read_text(encoding="utf-8").splitlines())
        if item.get("packet") in shown
    }
    said, unquoted = [], 0
    for packet, item in verdicts.items():
        if item.get("verdict") != "confirmed":
            continue
        quote = " ".join(str(item.get("quote") or "").split())
        if quote and any(quote in " ".join(p.split()) for p in shown[packet]["passages"]):
            said.append(packet)
        else:
            unquoted += 1
    real = [p for p in verdicts if "swapped" not in pairs[p]]
    supported = [p for p in real if labels[p] == "supported"]
    right = sum(labels[p] == "supported" for p in said)
    lenient = sum(labels[p] in {"supported", "partially_supported"} for p in said)
    wrong = sum("swapped" in pairs[p] and labels[p] == "not_supported" for p in said)
    print(f"{len(verdicts)} of {len(shown)} pairs judged; {unquoted} confirmations without an "
          f"exact quote were not counted")  # fmt: skip
    found = sum(p in said for p in supported)
    print(f"said confirmed {len(said)}, right {right} ({right / max(len(said), 1):.0%}), lenient "
          f"{lenient / max(len(said), 1):.0%}; supported confirmed {found}/{len(supported)}; "
          f"real confirmed {sum(p in said for p in real)}/{len(real)}; "
          f"mis-citations confirmed {wrong}")  # fmt: skip
    hhem = _bests(SCORES / "hhem.json", pairs)
    machine = [p for p in verdicts if hhem.get(p, {}).get("top 4", -1.0) >= 0.4]
    print(f"HHEM on the same pairs: said {len(machine)}, right "
          f"{sum(labels[p] == 'supported' for p in machine)}, real confirmed "
          f"{sum(p in machine for p in real)}/{len(real)}")  # fmt: skip


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("command", choices=["score", "report", "agent-packets", "agent-score"])
    parser.add_argument("model", nargs="?", default="hhem")
    parser.add_argument(
        "--every-passage", action="store_true", help="score every passage of the full texts"
    )
    args = parser.parse_args()
    if args.command == "score":
        score(args.model, args.every_passage)
    elif args.command == "agent-packets":
        agent_packets()
    elif args.command == "agent-score":
        agent_score()
    else:
        report()


if __name__ == "__main__":
    main()
