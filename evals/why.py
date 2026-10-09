"""Why a real paper's reference got its verdict: every record found for it, checked field by field.

For judging a finding or debugging a change: the entry as written, then each record reached
through the entry's identifiers ("anchored") or by searching ("candidate"), with how its title,
authors, year and venue compare. Answers come from the evaluation cache, as in a replay; with
``--against``, the reference's findings in two replays' reports are shown side by side.

    uv run python evals/why.py 2606.11568v1:li2024llava
    uv run python evals/why.py 2606.11568v1:li2024llava --against BASE NEW
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from replay import CACHE, DATA, every_answer_counts  # noqa: E402

from paper_preflight.bib.parse import BibEntry, parse_bib_file  # noqa: E402
from paper_preflight.check import VerifyOptions, verify_entries  # noqa: E402
from paper_preflight.match import evaluate  # noqa: E402

FIELDS = "title author year journal booktitle volume pages doi eprint url note".split()


def find_entry(paper: str, key: str) -> BibEntry | None:
    for bib in sorted((DATA / paper).rglob("*.bib")):
        try:
            entries = parse_bib_file(bib).entries
        except (OSError, UnicodeDecodeError, ValueError):
            continue
        entry = next((e for e in entries if e.key == key), None)
        if entry is not None:
            return entry
    return None


def show_records(paper: str, key: str) -> bool:
    entry = find_entry(paper, key)
    if entry is None:
        print(f"=== {paper}:{key}: no such entry in the paper's .bib files")
        return False
    options = VerifyOptions(cache_path=CACHE, offline=True, remember_too_new=False)
    evidence, assessments, _ = asyncio.run(verify_entries([entry], options))
    item, assessment = evidence[key], assessments[key]
    bound = assessment.record
    print(f"=== {paper}:{key}: {assessment.verdict.value}"
          + (f", bound to {bound.source}:{bound.source_id}" if bound else ""))  # fmt: skip
    for name in FIELDS:
        value = entry.text(name)
        if value:
            print(f"  {name} = {value[:160]}")
    for finding in assessment.findings:
        print(f"  {finding.rule_id} {finding.severity.value}: {finding.message.en[:200]}")
    for label, records in (("anchored", item.anchored), ("candidate", item.candidates)):
        for record in records:
            m = evaluate(item.info, record)
            checks = (
                f"title {m.title.status}, authors {m.authors.status}, year {m.year.status}, "
                f"venue {m.venue.status}"
            )
            print(f"  {label} {record.source}:{record.source_id} {record.work_type}"
                  f" years {sorted(record.all_years)} | {checks}")  # fmt: skip
            people = ", ".join(p.display for p in record.authors[:8])
            more = f" (+{len(record.authors) - 8})" if len(record.authors) > 8 else ""
            print(f"      {record.title[:120]!r} | {record.venue or ''} | {people}{more}")
    return True


def show_replays(paper: str, key: str, replays: list[Path]) -> None:
    for directory in replays:
        path = directory / f"{paper}.json"
        if not path.exists():
            print(f"  {directory.name}: no report for {paper}")
            continue
        report = json.loads(path.read_text(encoding="utf-8"))
        ref = next((r for r in report["references"] if r["key"] == key), None)
        if ref is None:
            print(f"  {directory.name}: not in the report")
            continue
        matched = ref.get("matched") or {}
        print(f"  {directory.name}: {ref['verdict']} | {matched.get('source')}:{matched.get('id')}")
        for f in report["findings"]:
            if f["key"] == key and f["rule"].startswith("REF"):
                print(f"      {f['rule']} {f['severity']}: {f['message']['en'][:170]}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("refs", nargs="+", help="paper:key, e.g. 2606.11568v1:li2024llava")
    parser.add_argument("--against", nargs=2, type=Path, metavar=("BASE", "NEW"),
                        help="two replays' report directories to compare")  # fmt: skip
    args = parser.parse_args()
    every_answer_counts()
    for spec in args.refs:
        paper, _, key = spec.partition(":")
        if show_records(paper, key) and args.against:
            show_replays(paper, key, list(args.against))


if __name__ == "__main__":
    main()
