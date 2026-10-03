"""Run paper-preflight on a HALLMARK split against the real scholarly sources.

    uv run python evals/run_hallmark.py --split dev_public --sample 120
    uv run python evals/run_hallmark.py --split dev_public            # the whole split

The data must be present in evals/.data/ (see evals/datasets.lock). Answers are cached in
evals/.cache/ (git-ignored), so an interrupted or repeated run only asks for what is missing.
Credentials come from the environment exactly as for `paper-preflight check`.

Writes evals/results/hallmark-<split>[-sample<N>].md (the summary, committed) and a .jsonl file
with one line per entry (git-ignored).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import random
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

import httpx

from paper_preflight import __version__
from paper_preflight.bib.parse import BibEntry, parse_bib_text
from paper_preflight.cache import Cache
from paper_preflight.evaluation.hallmark import (
    MODES,
    Example,
    Outcome,
    load,
    load_disputed,
    predict,
    render_markdown,
    score,
    to_bibtex,
)
from paper_preflight.resolve import Sources, resolve
from paper_preflight.verdict import Assessment, assess_all

ROOT = Path(__file__).resolve().parent
DATA = ROOT / ".data" / "hallmark" / "v1.2.3" / "data" / "v1.2"
CHUNK = 50


def stratified(examples: list[Example], size: int, seed: int) -> list[Example]:
    """Half VALID entries, half spread evenly over the hallucination types."""
    rng = random.Random(seed)
    groups: dict[str, list[Example]] = {}
    for example in examples:
        groups.setdefault(example.kind or "VALID", []).append(example)
    valid = groups.pop("VALID", [])
    picked = rng.sample(valid, min(len(valid), size // 2))
    per_type = max(1, (size - len(picked)) // max(1, len(groups)))
    for kind in sorted(groups):
        picked += rng.sample(groups[kind], min(per_type, len(groups[kind])))
    return picked


async def assess_examples(
    examples: list[Example], cache_path: Path, *, offline: bool, year: int
) -> tuple[dict[str, Assessment], Counter[str], list[str]]:
    cache = Cache(cache_path)
    assessments: dict[str, Assessment] = {}
    unavailable: Counter[str] = Counter()
    unparsed: list[str] = []
    try:
        async with httpx.AsyncClient(follow_redirects=True) as http:
            sources = Sources.create(http, cache, offline=offline)
            for start in range(0, len(examples), CHUNK):
                entries: list[BibEntry] = []
                for example in examples[start : start + CHUNK]:
                    parsed = parse_bib_text(to_bibtex(example), Path(f"{example.key}.bib"))
                    if parsed.entries:
                        entries.append(parsed.entries[0])
                    else:
                        unparsed.append(example.key)
                evidence = await resolve(entries, sources)
                for item in evidence.values():
                    unavailable.update(f"{s} ({r})" for s, r in item.unavailable.items())
                assessments.update(assess_all(entries, evidence, current_year=year))
                done = min(start + CHUNK, len(examples))
                print(f"  {done}/{len(examples)} assessed", flush=True)
    finally:
        cache.close()
    return assessments, unavailable, unparsed


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--split", default="dev_public", help="dev_public, test_public, ...")
    parser.add_argument("--sample", type=int, default=0, help="stratified sample size (0 = all)")
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--offline", action="store_true", help="answer from the cache only")
    args = parser.parse_args()

    examples = load(DATA / f"{args.split}.jsonl")
    if args.sample:
        examples = stratified(examples, args.sample, args.seed)
    name = f"hallmark-{args.split}" + (f"-sample{args.sample}" if args.sample else "")
    year = datetime.now(UTC).year
    print(f"{name}: {len(examples)} entries", flush=True)

    started = time.monotonic()
    cache = ROOT / ".cache" / "hallmark.sqlite3"
    assessments, unavailable, unparsed = asyncio.run(
        assess_examples(examples, cache, offline=args.offline, year=year)
    )
    minutes = (time.monotonic() - started) / 60

    outcomes: dict[str, dict[str, Outcome]] = {
        mode: {key: predict(a, rules) for key, a in assessments.items()}
        for mode, rules in MODES.items()
    }
    scores = score(examples, outcomes)
    disputed = load_disputed(ROOT / "hallmark_disputed.toml")
    kept = [e for e in examples if e.key not in disputed]
    undisputed = score(kept, outcomes)

    results = ROOT / "results"
    results.mkdir(exist_ok=True)
    with (results / f"{name}.jsonl").open("w", encoding="utf-8", newline="\n") as handle:
        for example in examples:
            assessment = assessments.get(example.key)
            handle.write(
                json.dumps(
                    {
                        "key": example.key,
                        "label": "HALLUCINATED" if example.hallucinated else "VALID",
                        "type": example.kind,
                        "verdict": assessment.verdict.value if assessment else None,
                        "reasons": [r.value for r in assessment.reasons] if assessment else [],
                        "rules": sorted({f.rule_id for f in assessment.findings})
                        if assessment
                        else [],
                        **{mode: outcomes[mode].get(example.key) for mode in MODES},
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
    header = {
        "Tool": f"paper-preflight {__version__}",
        "Data": f"HALLMARK v1.2.3, split `{args.split}`"
        + (f", stratified sample of {len(examples)} (seed {args.seed})" if args.sample else ""),
        "Run": f"{datetime.now(UTC):%Y-%m-%d}, {minutes:.1f} min"
        + (", offline (cache only)" if args.offline else ", live sources"),
        "Unavailable during the run": ", ".join(f"{k}: {v}" for k, v in unavailable.most_common())
        or "none",
        "Unparsed entries": str(len(unparsed)),
    }
    markdown = render_markdown(scores, header, undisputed, len(examples) - len(kept))
    (results / f"{name}.md").write_text(markdown, encoding="utf-8", newline="\n")
    print(markdown)


if __name__ == "__main__":
    main()
