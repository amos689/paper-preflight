"""Real-world recall: the hallucinated references GPTZero found in NeurIPS and ICLR papers.

GPTZero published two tables of hallucinated citations, each checked by its staff:
- 100 in 53 papers accepted to NeurIPS 2025 (https://gptzero.me/news/neurips/);
- 51 in 50 ICLR 2026 submissions (https://gptzero.me/news/iclr-2026/, 2025-12-05).

Each row quotes one reference as the paper printed it, and GPTZero's comment on why it is
fabricated. This script writes the references as a numbered plain-text list, checks it as
`paper-preflight check refs.txt` would, and counts each reference as:
- **flagged**: a warning or error about it;
- **cannot determine**: no warning or error, and no verdict either;
- **missed**: verified without a warning or error.

    uv run python evals/gptzero.py fetch      # download both tables (evals/.data/gptzero)
    uv run python evals/gptzero.py run        # check the references against live sources
    uv run python evals/gptzero.py report     # combine with the review (evals/gptzero_review.toml)

The tables are GPTZero's and are not committed. Only the counts, and row numbers with our
verdicts, are published. The rows are the hallucinations GPTZero's own tool found and its staff
confirmed, so the recall measured here is recall on that kind of hallucination, not on all.
Each reference that is missed or undetermined is reviewed by hand in evals/gptzero_review.toml:
"miss" when GPTZero's comment holds, "disputed" when the reference turns out to be correct.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import subprocess
import sys
import tomllib
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
from real_papers import source_commit

from paper_preflight import __version__
from paper_preflight.check import VerifyOptions, run_check
from paper_preflight.report.jsonout import to_json_dict

ROOT = Path(__file__).resolve().parent
DATA = ROOT / ".data" / "gptzero"
CACHE = ROOT / ".cache" / "gptzero.sqlite3"
REVIEW = ROOT / "gptzero_review.toml"
RESULTS = ROOT / "results" / "gptzero.md"
SHEET = "https://docs.google.com/spreadsheets/d/{}/export?format=csv"
# name: (sheet id, title column, SHA-256 of the table as reviewed)
SETS = {
    "neurips2025": (
        "14hIuCK7HCnGhdCuxfwp1wIYbbHMn-K3FNvY9NgWGW0Y",
        "Published Paper",
        "7af222edbe52d06b356f3e998109c2cbd16f0420bd80ec8c25e00865c4ef4658",
    ),
    "iclr2026": (
        "1WIf6EGQXN9TMCeH7d18GWC4H14Sb9h5NBKTB_3vawD8",
        "Title",
        "cabb793d42282d11d84c45c8fd26d423b1482477d193bc5c0ed27efabbe0ccbc",
    ),
}
FLAG_SEVERITIES = {"warning", "error"}
# GPTZero's comments, sorted into the kinds of hallucination (first match wins)
KINDS = [
    (
        "identifier of another work",
        r"(arxiv id|doi|url)\b.*\b(different|another|leads to|links to|third paper)",
    ),
    ("incomplete identifier", r"\b(incomplete|xxxx|placeholder)\b"),
    ("no such work", r"no (clear )?(match|author|title)|doesn.t exist|does not exist|no exact"),
    (
        "real work, wrong authors",
        r"\bauthors?\b.*\b(wrong|fabricated|not on|incorrect|do not|don.t match|different|omitted"
        r"|added|except)\b",
    ),
    (
        "real work, other details wrong",
        r"\b(title|year|date|page|publisher|doi)\b.*\b(partially|similar|only|don.t|doesn.t|off"
        r"|fabricated|wrong|hallucinated|different)\b|similar|loosely matches|matches this",
    ),
]


def table(name: str) -> Path:
    return DATA / f"{name}.csv"


def rows(name: str) -> list[dict[str, str]]:
    """The table's rows, each with "title", "reference" and "comment"."""
    _, title_column, _ = SETS[name]
    with table(name).open(encoding="utf-8", newline="") as handle:
        found = []
        for row in csv.DictReader(handle):
            columns = {k.strip().lower(): v for k, v in row.items() if k}
            found.append({
                "title": " ".join(row[title_column].split()),
                "reference": " ".join(columns["example of verified hallucination"].split()),
                "comment": " ".join(columns["comment"].split()),
            })  # fmt: skip
    return found


def kind(comment: str) -> str:
    text = comment.lower()
    return next((label for label, pattern in KINDS if re.search(pattern, text)), "other")


def fetch(_: argparse.Namespace) -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    with httpx.Client(follow_redirects=True, timeout=60) as http:
        for name, (sheet, _, expected) in SETS.items():
            content = http.get(SHEET.format(sheet)).raise_for_status().content
            table(name).write_bytes(content)
            digest = hashlib.sha256(content).hexdigest()
            note = "as reviewed" if digest == expected else f"CHANGED since the review ({digest})"
            print(f"{name}: {len(rows(name))} references, {note}")


def run(args: argparse.Namespace) -> None:
    for name in args.sets:
        listing = DATA / f"{name}.txt"
        references = rows(name)
        listing.write_text(
            "\n\n".join(f"[{n}] {row['reference']}" for n, row in enumerate(references, 1)) + "\n",
            encoding="utf-8",
        )
        result = run_check(listing, verify=VerifyOptions(cache_path=CACHE, remember_too_new=False))
        payload = to_json_dict(result)
        run_date = f"{datetime.now(UTC):%Y-%m-%d}"
        payload["eval"] = {"set": name, "version": __version__, "run": run_date}
        (DATA / f"{name}.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8"
        )
        print(f"{name}: {len(result.verdicts)} of {len(references)} references read")


def outcomes(name: str) -> list[dict[str, Any]]:
    """Per row: the verdict, the flags, and how the row counts."""
    payload = json.loads((DATA / f"{name}.json").read_text(encoding="utf-8"))
    verdicts = {v["key"]: v for v in payload["references"]}
    flags: dict[str, list[str]] = {}
    for finding in payload["findings"]:
        if finding["severity"] in FLAG_SEVERITIES and finding.get("key"):
            flags.setdefault(finding["key"], []).append(finding["rule"])
    found = []
    for n, row in enumerate(rows(name), 1):
        key = f"ref{n}"
        verdict = verdicts.get(key, {}).get("verdict", "not read")
        rules = flags.get(key, [])
        status = "flagged" if rules else ("missed" if verdict == "verified" else "cannot determine")
        found.append({"row": n, "key": key, "verdict": verdict, "rules": rules, "status": status,
                      "kind": kind(row["comment"]), **row})  # fmt: skip
    return found


def _code() -> str:
    """The commit the report is made with, and whether src/ has changes not committed yet."""
    command = ["git", "status", "--porcelain", "--", "src"]
    try:
        changed = subprocess.run(command, capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        changed = ""
    note = " with changes to src/ not yet committed" if changed else ""
    return f"commit {source_commit()}{note}"


def report(args: argparse.Namespace) -> None:
    review = tomllib.loads(REVIEW.read_text(encoding="utf-8")) if REVIEW.exists() else {}
    lines = [
        "# Real-world recall: GPTZero's hallucinated references (NeurIPS 2025, ICLR 2026)",
        "",
        f"- **Tool:** paper-preflight {__version__} ({_code()})",
        "- **Data:** the references GPTZero's staff confirmed as hallucinated: 100 in NeurIPS 2025 "
        "papers, 51 in ICLR 2026 submissions ([NeurIPS](https://gptzero.me/news/neurips/), "
        "[ICLR](https://gptzero.me/news/iclr-2026/)). The tables are not redistributed; rows are "
        "numbered as in GPTZero's tables.",
        "- **Input:** each reference as the paper printed it, read by paper-preflight's "
        "plain-text reader (`check refs.txt`), checked against live sources",
        f"- **Run:** {datetime.now(UTC):%Y-%m-%d}",
        "",
    ]
    summary = ["| Set | References | Flagged | Cannot determine | Missed | Disputed |",
               "|---|---|---|---|---|---|"]  # fmt: skip
    by_kind: Counter[tuple[str, str]] = Counter()
    totals: Counter[str] = Counter()
    unreviewed, details = [], []
    for name in args.sets:
        found = outcomes(name)
        decided = review.get(name, {})
        counts: Counter[str] = Counter()
        for item in found:
            judged = decided.get(str(item["row"]), {})
            status = "disputed" if judged.get("verdict") == "disputed" else item["status"]
            counts[status] += 1
            by_kind[(item["kind"], status)] += 1
            if item["status"] != "flagged":
                if not judged:
                    unreviewed.append(f"{name}:{item['row']}")
                details.append(
                    f"| {name} | {item['row']} | {item['kind']} | {item['verdict']} | "
                    f"{judged.get('verdict', 'unreviewed')} | {judged.get('reason', '')} |"
                )
        total = len(found)
        totals.update(counts)
        totals["all"] += total
        summary.append(
            f"| {name} | {total} | {counts['flagged']} ({counts['flagged'] / total:.0%}) | "
            f"{counts['cannot determine']} | {counts['missed']} | {counts['disputed']} |"
        )
    everything, flagged = totals["all"], totals["flagged"]
    summary.append(
        f"| **all** | {everything} | **{flagged} ({flagged / everything:.0%})** "
        f"| {totals['cannot determine']} | {totals['missed']} | {totals['disputed']} |"
    )
    kinds = sorted({k for k, _ in by_kind})
    lines += ["## Summary", "", *summary, "", "## By kind of hallucination", "",
              "Kinds are read from GPTZero's comments.", "",
              "| Kind | Flagged | Cannot determine | Missed | Disputed |", "|---|---|---|---|---|",
              *[f"| {k} | {by_kind[(k, 'flagged')]} | {by_kind[(k, 'cannot determine')]} | "
                f"{by_kind[(k, 'missed')]} | {by_kind[(k, 'disputed')]} |" for k in kinds],
              "", "## Not flagged, reviewed", "",
              "| Set | Row | Kind | Verdict | Review | Reason |", "|---|---|---|---|---|---|",
              *details, ""]  # fmt: skip
    if unreviewed:
        lines += [f"**{len(unreviewed)} rows are not reviewed yet.**", ""]
        print("unreviewed:", *unreviewed, sep="\n  ", file=sys.stderr)
    RESULTS.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    print("\n".join(lines))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("command", choices=["fetch", "run", "report"])
    parser.add_argument("--sets", nargs="+", choices=sorted(SETS), default=sorted(SETS))
    args = parser.parse_args()
    {"fetch": fetch, "run": run, "report": report}[args.command](args)


if __name__ == "__main__":
    main()
