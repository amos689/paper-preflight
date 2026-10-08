"""Replay the real-paper batches with the working tree's code and compare with an earlier replay.

A change is merged only when this shows no new false positive on the development batches
(see evals/README.md). Each paper's report is written to OUT; with ``--against``, every verdict
that moved and every warning or error lost or gained is printed with its review verdict from
evals/real_papers_review.toml ("unreviewed" when nobody has judged it yet).

    uv run python evals/replay.py OUT                          # a baseline: write the reports
    uv run python evals/replay.py OUT --against BASE           # compare with a baseline
    uv run python evals/replay.py OUT --against BASE --fill    # fetch answers the cache lacks
    uv run python evals/replay.py OUT --batch heldout9 heldout10

Offline by default: answers come from the evaluation cache, stale or not, and a reference whose
answer is missing is reported as offline. ``--fill`` asks the sources for the missing answers
only (a change that sends a new query needs it), and keeps every cached one.
"""

from __future__ import annotations

import argparse
import json
import sys
import tomllib
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from real_papers import BATCHES  # noqa: E402

from paper_preflight.cache import Cache  # noqa: E402
from paper_preflight.check import VerifyOptions, run_check  # noqa: E402
from paper_preflight.report.jsonout import to_json_dict  # noqa: E402

DATA = ROOT / ".data" / "real_papers"
CACHE = ROOT / ".cache" / "real_papers.sqlite3"
REVIEW = ROOT / "real_papers_review.toml"


def papers(batch: str) -> list[str]:
    name = "real_papers.toml" if batch == "dev" else f"real_papers_{batch}.toml"
    manifest = tomllib.loads((ROOT / name).read_text(encoding="utf-8"))
    return [paper["id"] for paper in manifest["paper"]]


def flagged(payload: dict[str, Any]) -> set[tuple[str, str]]:
    return {
        (f["key"], f["rule"])
        for f in payload["findings"]
        if f["rule"].startswith("REF") and f["severity"] in {"warning", "error"}
    }


def every_answer_counts() -> None:
    """Use every cached answer, stale or not: the replay must see what the run saw."""
    get = Cache.get

    def stale_too(self: Cache, source: str, key: str, allow_stale: bool = False) -> Any:
        return get(self, source, key, allow_stale=True)

    Cache.get = stale_too  # type: ignore[method-assign]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("out", type=Path, help="directory for this replay's reports")
    parser.add_argument("--against", type=Path, help="an earlier replay's directory")
    parser.add_argument("--batch", nargs="+", default=list(BATCHES), choices=list(BATCHES))
    parser.add_argument("--fill", action="store_true", help="fetch the answers the cache lacks")
    args = parser.parse_args()
    every_answer_counts()
    review = tomllib.loads(REVIEW.read_text(encoding="utf-8"))["finding"]
    args.out.mkdir(parents=True, exist_ok=True)
    moves: Counter[tuple[str | None, str]] = Counter()
    lost: Counter[str] = Counter()
    gained: Counter[str] = Counter()
    for batch in args.batch:
        for pid in papers(batch):
            name = f"{pid.replace('/', '_')}.json"
            result = run_check(
                DATA / pid.replace("/", "_"),
                verify=VerifyOptions(cache_path=CACHE, offline=not args.fill),
            )
            new = to_json_dict(result)
            (args.out / name).write_text(json.dumps(new, ensure_ascii=False), encoding="utf-8")
            if args.against is None:
                continue
            old = json.loads((args.against / name).read_text(encoding="utf-8"))
            before = {r["key"]: r["verdict"] for r in old["references"]}
            for ref in new["references"]:
                if before.get(ref["key"]) != ref["verdict"]:
                    moves[(before.get(ref["key"]), ref["verdict"])] += 1
                    print("VERDICT", batch, pid, ref["key"], before.get(ref["key"]), "->",
                          ref["verdict"])  # fmt: skip
            for label, keys, tally in (
                ("LOST", flagged(old) - flagged(new), lost),
                ("GAINED", flagged(new) - flagged(old), gained),
            ):
                for key, rule in sorted(keys):
                    verdict = review.get(f"{pid}:{key}:{rule}", {}).get("verdict", "unreviewed")
                    tally[verdict] += 1
                    print(label, batch, pid, key, rule, verdict)
    if args.against is not None:
        print("verdict moves:", dict(moves))
        print("lost:", dict(lost), "gained:", dict(gained))


if __name__ == "__main__":
    main()
