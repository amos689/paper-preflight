"""List a batch's warnings and errors that have no review yet, for judging them by hand.

Each finding comes with its message, the record it was matched to and the entry's fields as
written, so that most can be judged without opening the paper. Verdicts go into
evals/real_papers_review.toml (correct, false_positive or unclear, with a note saying why).

    uv run python evals/review_list.py heldout11                # print to the terminal
    uv run python evals/review_list.py heldout11 --out list.md  # or write a file
    uv run python evals/review_list.py heldout11 --rule REF012 REF013
"""

from __future__ import annotations

import argparse
import json
import tomllib
from pathlib import Path

from paper_preflight.bib.parse import BibEntry, parse_bib_file

ROOT = Path(__file__).resolve().parent
FIELDS = "title author year journal booktitle doi eprint volume pages url note howpublished".split()


def entries_of(pid: str) -> dict[str, BibEntry]:
    found: dict[str, BibEntry] = {}
    for bib in (ROOT / ".data" / "real_papers" / pid).rglob("*.bib"):
        try:
            for entry in parse_bib_file(bib).entries:
                found.setdefault(entry.key, entry)
        except Exception:  # a paper's stray .bib may not parse; skip it
            continue
    return found


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("batch")
    parser.add_argument("--out", type=Path)
    parser.add_argument("--rule", nargs="+", default=[])
    args = parser.parse_args()
    name = "real_papers.toml" if args.batch == "dev" else f"real_papers_{args.batch}.toml"
    manifest = tomllib.loads((ROOT / name).read_text(encoding="utf-8"))["paper"]
    review = tomllib.loads((ROOT / "real_papers_review.toml").read_text(encoding="utf-8"))
    reviewed = review["finding"]
    blocks = []
    for paper in manifest:
        pid = paper["id"]
        report = ROOT / ".data" / "real_papers_reports" / f"{pid}.json"
        payload = json.loads(report.read_text(encoding="utf-8"))
        refs = {r["key"]: r for r in payload["references"]}
        entries = entries_of(pid)
        for finding in payload["findings"]:
            rule = finding["rule"]
            if not rule.startswith("REF") or finding["severity"] not in {"warning", "error"}:
                continue
            if args.rule and rule not in args.rule:
                continue
            fid = f"{pid}:{finding['key']}:{rule}"
            if fid in reviewed:
                continue
            entry = entries.get(finding["key"])
            written = ""
            if entry is not None:
                written = "; ".join(
                    f"{k}={v.value[:150]}" for k, v in entry.fields.items() if k in FIELDS
                )
            matched = refs.get(finding["key"], {}).get("matched")
            blocks.append(
                f"### {fid}\n- {finding['message']['en']}\n- matched: {matched}\n"
                f"- entry: {written}\n"
            )
    text = "\n".join(blocks)
    if args.out:
        args.out.write_text(text, encoding="utf-8")
    else:
        print(text)
    print(f"{len(blocks)} findings to review")


if __name__ == "__main__":
    main()
