"""Head-to-head on Badalova & Mayr (2026): paper-preflight next to five published tools.

Badalova and Mayr checked 104 references from three documents by hand (71 verified, 33
problematic) and recorded whether each of five tools flagged them: CheckIfExist,
HalluCiteChecker, Hallucinator, HalRef and RefChecker (Zenodo 10.5281/zenodo.21457492,
CC BY 4.0). Their references are formatted strings; evals/badalova_mayr.bib transcribes each one
into BibTeX as written, errors included, so that paper-preflight sees what the tools saw.

    uv run python evals/run_badalova_mayr.py

Two ways to count paper-preflight, since the study counts "unresolved, needs checking" as
flagged: *strict* flags a reference with a warning or an error; *inclusive* also counts "cannot
determine". Precision comes with a Wilson 95% interval: with 33 problematic references, small
differences are noise.

The study labels a reference "verified" when the work exists, so a flag on one is not always
wrong: the reference may still carry a wrong author or title, or cite a preprint since published.
evals/badalova_mayr_review.toml records a hand check of each such flag. A second table counts
the references found to carry a real error as problematic, for every tool alike, and adds a
paper-preflight row without the flags that are only REF015 advice.
"""

from __future__ import annotations

import csv
import math
import re
import subprocess
import sys
import tomllib
from datetime import UTC, datetime
from pathlib import Path

from paper_preflight import __version__
from paper_preflight.check import VerifyOptions, run_check
from paper_preflight.verdict import Verdict

ROOT = Path(__file__).resolve().parent
CSV = ROOT / ".data" / "badalova_mayr" / "manual_reference_verification_dataset.csv"
BIB = ROOT / "badalova_mayr.bib"
CACHE = ROOT / ".cache" / "badalova_mayr.sqlite3"
RESULTS = ROOT / "results" / "badalova-mayr.md"
REVIEW = ROOT / "badalova_mayr_review.toml"
TOOLS = ["checkifexist", "hallucitechecker", "hallucinator", "halref", "refchecker"]
NAMES = {
    "checkifexist": "CheckIfExist", "hallucitechecker": "HalluCiteChecker",
    "hallucinator": "Hallucinator", "halref": "HalRef", "refchecker": "RefChecker",
}  # fmt: skip


def wilson(successes: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 1.0)
    p = successes / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return (max(0.0, centre - half), min(1.0, centre + half))


def row(name: str, labels: dict[str, str], flagged: set[str]) -> str:
    tp = sum(1 for k, v in labels.items() if v == "problematic" and k in flagged)
    fp = sum(1 for k, v in labels.items() if v == "verified" and k in flagged)
    problematic = sum(1 for v in labels.values() if v == "problematic")
    verified = len(labels) - problematic
    low, high = wilson(tp, tp + fp)
    precision = f"{tp / (tp + fp):.1%} [{low:.1%}, {high:.1%}]" if tp + fp else "–"
    return (
        f"| {name} | {tp + fp} | {tp} | {fp} | {precision} | {tp / problematic:.1%} | "
        f"{100 * fp / verified:.1f} |"
    )


def table(labels: dict[str, str], keys: dict[str, dict[str, str]]) -> list[str]:
    return [
        "| Tool | Flagged | Problematic flagged | Verified flagged | Precision [95% CI] | "
        "Recall | False flags per 100 verified |",
        "|---|---|---|---|---|---|---|",
        *[
            row(NAMES[t], labels, {k for k, r in keys.items() if r[t].strip() == "flagged"})
            for t in TOOLS
        ],
    ]


def source_commit() -> str:
    """The commit of the checked-out code: results name it, as the version lags between releases."""
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=True
        )
    except (OSError, subprocess.CalledProcessError):
        return "unknown"
    return out.stdout.strip()


def order(key: str) -> tuple[str, int]:
    return key[:2], int(re.sub(r"\D", "", key[2:]) or 0)


def main() -> None:
    with CSV.open(encoding="cp850", newline="") as handle:
        rows = list(csv.DictReader(handle))
    keys = {f"{r['document_id']}{r['reference_number']}".lower(): r for r in rows}
    labels = {k: r["manual_label"].strip() for k, r in keys.items()}
    review: dict[str, dict[str, str]] = tomllib.loads(REVIEW.read_text(encoding="utf-8"))[
        "reference"
    ]

    started = datetime.now(UTC)
    result = run_check(BIB, verify=VerifyOptions(cache_path=CACHE))
    minutes = (datetime.now(UTC) - started).total_seconds() / 60
    flags: dict[str, set[str]] = {}
    for f in result.findings:
        if f.key and f.rule_id.startswith("REF") and f.severity.value in {"warning", "error"}:
            flags.setdefault(f.key, set()).add(f.rule_id)
    strict = set(flags)
    abstained = {k for k, a in result.verdicts.items() if a.verdict is Verdict.CANNOT_DETERMINE}
    advice_only = {k for k, rules in flags.items() if rules <= {"REF015"}}
    erroneous = {k for k, r in review.items() if r["kind"] == "metadata_error"}
    relabelled = {k: "problematic" if k in erroneous else v for k, v in labels.items()}
    on_verified = sorted((k for k in strict if labels.get(k) == "verified"), key=order)
    unreviewed = [k for k in on_verified if k not in review]
    missing = sorted(set(labels) - set(result.verdicts))

    lines = [
        "# Head-to-head: Badalova & Mayr (2026)",
        "",
        f"- **Tool:** paper-preflight {__version__}, commit {source_commit()}",
        "- **Data:** 104 references from three documents, checked by hand (71 verified, 33 "
        "problematic); the five tools' results as published (Zenodo 10.5281/zenodo.21457492, "
        "CC BY 4.0). Transcribed to BibTeX as written: `evals/badalova_mayr.bib`",
        f"- **Run:** {started:%Y-%m-%d}, {minutes:.1f} min, live sources"
        + (f"; not assessed: {', '.join(missing)}" if missing else ""),
        "",
        "## The study's labels",
        "",
        *table(labels, keys),
        row("**paper-preflight** (warnings and errors)", labels, strict),
        row('paper-preflight (also "cannot determine")', labels, strict | abstained),
        "",
        "## References with a real error counted as problematic",
        "",
        "The study labels a reference verified when the work exists. Reviewing paper-preflight's "
        f"flags on such references found {len(erroneous)} that carry a real error (a wrong "
        "author name, a missing title word, a broken DOI; listed below). Here they count as "
        "problematic for every tool. Only the references paper-preflight flagged were reviewed, "
        "so errors that only another tool noticed are not counted: read this table as a check "
        "of the labels, not as a fair ranking. The last row also leaves out paper-preflight's "
        "flags that are only REF015, the advice that a cited preprint has a published version.",
        "",
        *table(relabelled, keys),
        row("**paper-preflight** (warnings and errors)", relabelled, strict),
        row(
            "paper-preflight (warnings and errors, without REF015 advice)",
            relabelled,
            strict - advice_only,
        ),
        "",
        "The study's sample is small and was chosen to contain problems (one of the documents "
        "came from GPTZero's list of NeurIPS 2025 papers with hallucinated references), so the "
        "recall here is not representative; precision and false flags on verified references "
        "are the comparison that matters.",
        "",
        "## Flags on references the study labels verified",
        "",
        "| Reference | Findings | Review | Note |",
        "|---|---|---|---|",
        *[
            f"| {k.upper()} | {', '.join(sorted(flags[k]))} | "
            f"{review.get(k, {}).get('kind', '**not reviewed**')} | "
            f"{review.get(k, {}).get('note', '')} |"
            for k in on_verified
        ],
        "",
        "## paper-preflight per reference",
        "",
        "| Reference | Label | Verdict | Findings |",
        "|---|---|---|---|",
    ]
    for key in sorted(labels, key=order):
        assessment = result.verdicts.get(key)
        rules = sorted({f.rule_id for f in result.findings if f.key == key})
        lines.append(
            f"| {key.upper()} | {labels[key]} | "
            f"{assessment.verdict.value if assessment else 'not assessed'} | {', '.join(rules)} |"
        )
    RESULTS.parent.mkdir(exist_ok=True)
    RESULTS.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print("\n".join(lines[: lines.index("## Flags on references the study labels verified")]))
    if unreviewed:
        print("not reviewed:", *unreviewed, file=sys.stderr)


if __name__ == "__main__":
    main()
