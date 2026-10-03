"""Record the false-positive museum: real entries paper-preflight once got wrong, as test fixtures.

Each case in tests/fixtures/museum/cases.toml names a reference from an evaluation (a real
paper's .bib, or the Badalova & Mayr transcription) and the findings it must produce now. This
script writes the entry, as parsed, to a one-entry .bib and replays it offline against the
evaluation's cache, recording every cached source answer the check reads. The fixture
(tests/fixtures/museum/<name>.json) holds the entry and those answers, so tests/test_museum.py
can replay the check without the network or the evaluation data.

    uv run python evals/museum.py record            # record cases without a fixture
    uv run python evals/museum.py record --all      # re-record every case
    uv run python evals/museum.py check             # replay every fixture, print the findings

Semantic Scholar answers are never recorded (licence), and the check runs without any
credential, as the tests do.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import tomllib
from pathlib import Path
from typing import Any

from paper_preflight.bib.parse import BibEntry, parse_bib_file
from paper_preflight.cache import Cache, EntryKind
from paper_preflight.check import VerifyOptions, run_check
from paper_preflight.cli import CREDENTIAL_ENV_VARS

ROOT = Path(__file__).resolve().parent
MUSEUM = ROOT.parent / "tests" / "fixtures" / "museum"
CASES = MUSEUM / "cases.toml"
PAPERS = ROOT / ".data" / "real_papers"
CACHES = {
    "real_papers": ROOT / ".cache" / "real_papers.sqlite3",
    "badalova_mayr": ROOT / ".cache" / "badalova_mayr.sqlite3",
}


def find_entry(source: str, key: str) -> BibEntry:
    """The first definition of ``key`` in the evaluation's .bib files."""
    if source == "badalova_mayr":
        files = [ROOT / "badalova_mayr.bib"]
    else:
        paper = source.split(":", 1)[1]
        files = sorted((PAPERS / paper.replace("/", "_")).rglob("*.bib"))
    for path in files:
        for entry in parse_bib_file(path).entries:
            if entry.key == key:
                return entry
    sys.exit(f"{source}: no entry {key!r}")


def as_bib(entry: BibEntry) -> str:
    """The entry with its macros resolved, so it stands alone."""
    fields = ",\n".join(f"  {name} = {{{f.value}}}" for name, f in entry.fields.items())
    return f"@{entry.entry_type}{{{entry.key},\n{fields}\n}}\n"


def findings(bib: str, cache_path: Path) -> tuple[list[str], str]:
    """Warning and error rules for the one entry, and its verdict, from the cache only."""
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "refs.bib"
        path.write_text(bib, encoding="utf-8")
        result = run_check(path, verify=VerifyOptions(cache_path=cache_path, offline=True))
    rules = sorted(
        {
            f.rule_id
            for f in result.findings
            if f.rule_id.startswith("REF") and f.severity.value in {"warning", "error"}
        }
    )
    (assessment,) = result.verdicts.values()
    reasons = "".join(f" ({r.value})" for r in assessment.reasons)
    return rules, assessment.verdict.value + reasons


def record(case: dict[str, Any]) -> dict[str, Any]:
    entry = find_entry(case["source"], case["key"])
    bib = as_bib(entry)
    source_cache = CACHES["badalova_mayr" if case["source"] == "badalova_mayr" else "real_papers"]
    read: list[tuple[str, str]] = []
    original = Cache.get

    def logging_get(self: Cache, source: str, key: str, *, allow_stale: bool = False) -> Any:
        item = original(self, source, key, allow_stale=allow_stale)
        if item is not None:
            read.append((source, key))
        return item

    Cache.get = logging_get  # type: ignore[method-assign]
    try:
        rules, verdict = findings(bib, source_cache)
    finally:
        Cache.get = original  # type: ignore[method-assign]
    cache = Cache(source_cache)
    answers = []
    for source, key in dict.fromkeys(read):
        item = cache.get(source, key, allow_stale=True)
        if item is not None and item.exportable:
            answers.append(
                {"source": source, "key": key, "kind": item.kind.value, "payload": item.payload}
            )
    cache.close()
    return {"bib": bib, "cache": answers, "recorded": {"rules": rules, "verdict": verdict}}


def load_fixture(name: str, into: Path) -> str:
    """Write a fixture's answers into a cache at ``into``; return the entry."""
    data = json.loads((MUSEUM / f"{name}.json").read_text(encoding="utf-8"))
    cache = Cache(into)
    for item in data["cache"]:
        cache.put(item["source"], item["key"], item["payload"], EntryKind(item["kind"]))
    cache.close()
    return str(data["bib"])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("command", choices=["record", "check"])
    parser.add_argument("--all", action="store_true", help="re-record cases that have a fixture")
    args = parser.parse_args()
    for name in CREDENTIAL_ENV_VARS:  # as in the tests
        os.environ.pop(name, None)
    cases = tomllib.loads(CASES.read_text(encoding="utf-8"))["case"]
    failed = 0
    for case in cases:
        target = MUSEUM / f"{case['name']}.json"
        if args.command == "record":
            if target.exists() and not args.all:
                continue
            data = record(case)
            target.write_text(
                json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
            )
            ok = data["recorded"]["rules"] == sorted(case["expect"])
            print(f"{'ok ' if ok else 'BAD'} {case['name']}: {data['recorded']} "
                  f"({len(data['cache'])} answers)")  # fmt: skip
        else:
            with tempfile.TemporaryDirectory() as tmp:
                bib = load_fixture(case["name"], Path(tmp) / "cache.sqlite3")
                rules, verdict = findings(bib, Path(tmp) / "cache.sqlite3")
            ok = rules == sorted(case["expect"])
            print(f"{'ok ' if ok else 'BAD'} {case['name']}: {rules} {verdict}")
        failed += not ok
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
