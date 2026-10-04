"""Merge the AI annotators' labels for the citation-support gold set (S6).

    uv run python evals/support_labels.py agreement    # agreement of annotators A and B
    uv run python evals/support_labels.py disputes     # packets A and B disagree on (for C)
    uv run python evals/support_labels.py final        # majority label, or the adjudication

Labels are JSON lines in evals/.data/support/labels/<annotator>_*.jsonl, one object per packet
as evals/support_guidelines.md describes. Adjudications (made by hand where all three
disagree, and the spot checks) are in evals/support_adjudication.toml. The final labels go into
evals/support_gold.toml, without any text of the cited works (passage numbers only).
"""

from __future__ import annotations

import argparse
import json
import sys
import tomllib
from collections import Counter
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from support_gold import write_gold

ROOT = Path(__file__).resolve().parent
LABELS = ROOT / ".data" / "support" / "labels"
GOLD = ROOT / "support_gold.toml"
ADJUDICATION = ROOT / "support_adjudication.toml"
PACKETS = ROOT / ".data" / "support" / "packets"
FINAL = ROOT / ".data" / "support" / "final_labels.json"
CLASSES = ("supported", "partially_supported", "not_supported", "cannot_determine")


def labels(annotator: str) -> dict[str, dict[str, Any]]:
    found: dict[str, dict[str, Any]] = {}
    for path in sorted(LABELS.glob(f"{annotator}_*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                item = json.loads(line)
                if item.get("label") in CLASSES:
                    found[item["id"]] = item
    return found


def kappa(a: dict[str, str], b: dict[str, str]) -> tuple[float, int]:
    """Cohen's kappa on the items both labelled."""
    common = sorted(set(a) & set(b))
    if not common:
        return 0.0, 0
    observed = sum(a[k] == b[k] for k in common) / len(common)
    pa, pb = Counter(a[k] for k in common), Counter(b[k] for k in common)
    expected = sum(pa[c] * pb[c] for c in CLASSES) / len(common) ** 2
    return (observed - expected) / (1 - expected) if expected < 1 else 1.0, len(common)


def agreement() -> None:
    a = {k: v["label"] for k, v in labels("A").items()}
    b = {k: v["label"] for k, v in labels("B").items()}
    value, n = kappa(a, b)
    agree = sum(a[k] == b[k] for k in set(a) & set(b))
    print(f"A: {len(a)}, B: {len(b)}, both: {n}, agree: {agree} ({agree / max(n, 1):.0%}), "
          f"kappa {value:.2f}")  # fmt: skip
    print("A:", dict(Counter(a.values())))
    print("B:", dict(Counter(b.values())))


def disputes() -> list[str]:
    a, b = labels("A"), labels("B")
    out = sorted(k for k in set(a) & set(b) if a[k]["label"] != b[k]["label"])
    print("\n".join(out))
    return out


def _no_text(packet: str) -> bool:
    data = json.loads((PACKETS / f"{packet}.json").read_text(encoding="utf-8"))
    return bool(data["evidence_level"] == "none")


def final() -> None:
    """The final label of every pair, written into the gold file and final_labels.json."""
    a, b, c = labels("A"), labels("B"), labels("C")
    adjudicated: dict[str, Any] = {}
    if ADJUDICATION.exists():
        adjudicated = tomllib.loads(ADJUDICATION.read_text(encoding="utf-8")).get("packet", {})
    gold = tomllib.loads(GOLD.read_text(encoding="utf-8"))["pair"]
    missing = []
    for pair in gold:
        packet = pair["packet"]
        votes = [x[packet]["label"] for x in (a, b, c) if packet in x]
        if packet in adjudicated:
            label, how = adjudicated[packet]["label"], "adjudicated"
        elif _no_text(packet):
            label, how = "cannot_determine", "no text of the cited work"
        elif len(votes) >= 2 and votes[0] == votes[1]:
            label, how = votes[0], "A and B agree"
        elif len(votes) == 3 and Counter(votes).most_common(1)[0][1] >= 2:
            label, how = Counter(votes).most_common(1)[0][0], "two of three"
        else:
            missing.append(packet)
            continue
        pair["annotators"] = votes
        pair["label"], pair["decided_by"] = label, how
    if missing:
        sys.exit(f"{len(missing)} packets need adjudication: {' '.join(missing)}")
    write_gold(gold)
    FINAL.write_text(json.dumps({p["packet"]: p["label"] for p in gold}), encoding="utf-8")
    print(dict(Counter(p["label"] for p in gold)))
    print(dict(Counter(p["decided_by"] for p in gold)))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("command", choices=["agreement", "disputes", "final"])
    {"agreement": agreement, "disputes": disputes, "final": final}[parser.parse_args().command]()


if __name__ == "__main__":
    main()
