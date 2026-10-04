"""How well paper-preflight reads plain-text references: Badalova & Mayr's strings.

Badalova and Mayr's dataset (Zenodo 10.5281/zenodo.21457492, CC BY 4.0) gives each of its 104
references as the formatted string from the document: APA (P1), biblatex's default style (P2)
and a natbib author-year style (P3). evals/badalova_mayr.bib transcribes each one into BibTeX
by hand. This script writes the strings as a numbered plain-text list, reads it with
paper-preflight's plain-text reader, and compares every reference with its transcription: the
title, the first author's family name, the year and the DOI or arXiv ID.

    uv run python evals/plaintext_badalova.py           # field agreement, offline
    uv run python evals/plaintext_badalova.py --check   # also verify both, live, and compare

The CSV lost some characters to its encoding: letters outside Latin-1, curly apostrophes, P1's
ellipsis before the last of many authors (APA 7) and P2's quotation marks around titles all
became "?". The transcription restores them from the documents. This script restores only the
punctuation, where its place is unambiguous: an apostrophe between a letter and "s", "t", "re",
"ll", "ve", "d" or "m"; P1's ellipsis after ", " before a name; P2's quotation marks, where a "?"
opens after ". " and closes before ". In:" or ". en.". Lost letters stay lost.
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from datetime import UTC, datetime
from difflib import SequenceMatcher
from pathlib import Path

from paper_preflight import __version__
from paper_preflight.bib.names import parse_authors
from paper_preflight.bib.normalize import fold
from paper_preflight.bib.parse import BibEntry, parse_bib_file
from paper_preflight.bib.plaintext import parse_plaintext
from paper_preflight.check import CheckResult, VerifyOptions, run_check

ROOT = Path(__file__).resolve().parent
CSV = ROOT / ".data" / "badalova_mayr" / "manual_reference_verification_dataset.csv"
LIST = ROOT / ".data" / "badalova_mayr" / "references.txt"
BIB = ROOT / "badalova_mayr.bib"
CACHE = ROOT / ".cache" / "badalova_mayr.sqlite3"
RESULTS = ROOT / "results" / "plaintext-badalova-mayr.md"
QUOTED = re.compile(r"(?<=\. )\?(.+?)\?(?=\.?\s+(?:In:|en\.))")
APOSTROPHE = re.compile(r"(?<=[A-Za-z])\?(?=(?:s|t|re|ll|ve|d|m)\b)")
ELLIPSIS = re.compile(r"(?<=, )\?(?= [A-Z])")


def references() -> list[tuple[str, str]]:
    """(key, reference as written) in the dataset's order."""
    with CSV.open(encoding="cp850", newline="") as handle:
        rows = list(csv.DictReader(handle))
    found = []
    for row in rows:
        text = APOSTROPHE.sub("’", " ".join(row["reference"].split()))
        if row["document_id"] == "P1":
            text = ELLIPSIS.sub("…", text)
        if row["document_id"] == "P2":
            text = QUOTED.sub(lambda m: f"“{m.group(1)}”", text)
        found.append((f"{row['document_id']}{row['reference_number']}".lower(), text))
    return found


def words(text: str | None) -> str:
    return " ".join(fold(text or "").split())


def first_family(entry: BibEntry) -> str:
    people = parse_authors(entry.text("author")).people
    return fold(people[0].family or people[0].literal) if people else ""


def identifiers(entry: BibEntry) -> set[str]:
    return {(entry.text(f) or "").lower() for f in ("doi", "eprint") if entry.text(f)}


def agreement(read: BibEntry, written: BibEntry) -> dict[str, bool | None]:
    ids = identifiers(written)
    return {
        "title": SequenceMatcher(
            None, words(read.text("title")), words(written.text("title"))
        ).ratio()
        >= 0.9,
        "first author": first_family(read) == first_family(written),
        "year": (read.text("year") or "") == (written.text("year") or ""),
        "identifier": ids <= identifiers(read) if ids else None,
    }


def flags(result: CheckResult) -> dict[str, set[str]]:
    found: dict[str, set[str]] = {}
    for finding in result.findings:
        if (
            finding.key
            and finding.rule_id.startswith("REF")
            and finding.severity.value
            in {
                "warning",
                "error",
            }
        ):
            found.setdefault(finding.key, set()).add(finding.rule_id)
    return found


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="also verify both, live")
    check = parser.parse_args().check
    refs = references()
    LIST.write_text(
        "".join(f"[{n}] {text}\n" for n, (_, text) in enumerate(refs, start=1)), encoding="utf-8"
    )
    read = parse_plaintext(LIST.read_text(encoding="utf-8"), LIST).entries
    if len(read) != len(refs):
        sys.exit(f"read {len(read)} references, expected {len(refs)}")
    written = {e.key: e for e in parse_bib_file(BIB).entries}
    keys = {f"ref{n}": key for n, (key, _) in enumerate(refs, start=1)}
    scores = {
        key: agreement(entry, written[keys[entry.key]])
        for key, entry in zip(keys, read, strict=True)
    }

    lines = [
        "# Plain-text references: Badalova & Mayr (2026)",
        "",
        f"- **Tool:** paper-preflight {__version__}",
        "- **Data:** the 104 references of Badalova & Mayr's dataset as formatted strings (APA, "
        "biblatex, natbib author-year; Zenodo 10.5281/zenodo.21457492, CC BY 4.0), read by "
        "`check references.txt`, against the hand transcription `evals/badalova_mayr.bib`",
        f"- **Run:** {datetime.now(UTC):%Y-%m-%d} (`evals/plaintext_badalova.py`)",
        "",
        "| Document (style) | References | Title | First author | Year | DOI or arXiv ID |",
        "|---|---|---|---|---|---|",
    ]
    styles = {"p1": "P1 (APA)", "p2": "P2 (biblatex)", "p3": "P3 (natbib author-year)"}
    groups = {name: [k for k in keys if keys[k].startswith(prefix)] for prefix, name in
              styles.items()} | {"**All**": list(keys)}  # fmt: skip
    for name, members in groups.items():
        cells = []
        for field in ("title", "first author", "year", "identifier"):
            judged = [scores[k][field] for k in members if scores[k][field] is not None]
            cells.append(f"{sum(map(bool, judged))}/{len(judged)}")
        lines.append(f"| {name} | {len(members)} | " + " | ".join(cells) + " |")
    misses = [
        (keys[k], [f for f, ok in s.items() if ok is False]) for k, s in scores.items()
        if any(ok is False for ok in s.values())
    ]  # fmt: skip
    lines += ["", "Read differently from the transcription:", ""]
    lines += [f"- {key.upper()}: {', '.join(fields)}" for key, fields in misses] or ["- none"]
    lines += [
        "",
        "P1R14's title keeps the version the document adds (\"Marlowe: ... Instrument (Version "
        '0.1)"), which the transcription leaves out. P2R13 (and P3R29 below) lose letters the '
        'CSV dropped ("Micha? Marci?czuk", "Kamile? Luko?iut?e"), which the transcription '
        "restores from the documents.",
    ]

    if check:
        options = VerifyOptions(cache_path=CACHE)
        from_text = flags(run_check(LIST, verify=options))
        from_bib = flags(run_check(BIB, verify=options))
        same = sum(
            bool(from_text.get(k)) == bool(from_bib.get(keys[k])) for k in keys
        )  # fmt: skip
        lines += [
            "",
            "## Verified both ways",
            "",
            f"Flagged (a warning or an error) or not, the same for {same} of {len(keys)} "
            "references read from the text and from the transcription.",
            "",
        ]
        for k in keys:
            text_rules, bib_rules = from_text.get(k, set()), from_bib.get(keys[k], set())
            if bool(text_rules) != bool(bib_rules):
                lines.append(
                    f"- {keys[k].upper()}: text {sorted(text_rules) or 'clean'}, "
                    f"transcription {sorted(bib_rules) or 'clean'}"
                )
    RESULTS.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
