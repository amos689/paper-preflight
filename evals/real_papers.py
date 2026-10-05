"""Evaluate paper-preflight on the bibliographies of real papers (release gate G3).

Benchmarks such as HALLMARK perturb real entries; real `.bib` files are messier (books, theses,
workshop papers, odd fields). This script measures how often paper-preflight raises a warning or
an error on a real paper's reference that is in fact correct.

    uv run python evals/real_papers.py collect --batch heldout  # pick and download the papers
    uv run python evals/real_papers.py run --batch heldout      # check them against live sources
    uv run python evals/real_papers.py report --batch heldout   # combine with the manual review

Selection is mechanical, so that nobody picks papers the tool happens to handle well: for each
arXiv category, papers first submitted in a fixed week are taken in submission order, and a paper
is kept when its source contains a main .tex file and a .bib file with at least MIN_ENTRIES
entries, until the category's quota is met. Sources go to evals/.data/real_papers/ and are never
committed (arXiv's default licence does not allow redistribution); the manifest lists the IDs.

There are six batches, each a later week. "dev" (papers first submitted 2026-07-01..07) was
used to find false positives and fix them for 0.1.1. "heldout" (2026-07-08..14) was collected
after those fixes and reported as it came out for 0.1.1; its false positives were then studied
and fixed for 0.1.2. "heldout2" (2026-07-15..21) was collected after those fixes and reported as
it came out; its false positives missed 0.1.2's gate and were studied and fixed in turn.
"heldout3" (2026-07-22..28) measured those fixes for 0.1.2; its false positives were then
studied and fixed for 0.2.1, which "heldout4" (2026-07-29..08-04) measures; its false positives
were fixed for 0.3.0, which "heldout5" (2026-08-05..11) measures. Numbers on a batch whose flags
were studied are optimistic.

Every flagged reference is then reviewed by hand against the registries and recorded in
evals/real_papers_review.toml as "correct" (the entry really is wrong), "false_positive" (the
entry is right, the tool is wrong) or "unclear", with a reason one lookup can confirm.
"""

from __future__ import annotations

import argparse
import gzip
import io
import json
import subprocess
import sys
import tarfile
import time
import tomllib
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

import httpx

from paper_preflight import __version__
from paper_preflight.bib.parse import parse_bib_file
from paper_preflight.check import VerifyOptions, run_check
from paper_preflight.report.jsonout import to_json_dict
from paper_preflight.tex.project import ProjectError, load_project

ROOT = Path(__file__).resolve().parent
DATA = ROOT / ".data" / "real_papers"
REPORTS = ROOT / ".data" / "real_papers_reports"
REVIEW = ROOT / "real_papers_review.toml"
CACHE = ROOT / ".cache" / "real_papers.sqlite3"

# first submitted in one week (UTC)
BATCHES = {
    "dev": ("202607010000", "202607072359"),
    "heldout": ("202607080000", "202607142359"),  # held out for 0.1.1, then studied for 0.1.2
    "heldout2": ("202607150000", "202607212359"),  # held out for 0.1.2, then studied for it
    "heldout3": ("202607220000", "202607282359"),  # held out for 0.1.2's fixes, then studied
    "heldout4": ("202607290000", "202608042359"),  # held out for 0.2.1's fixes, then studied
    "heldout5": ("202608050000", "202608112359"),  # held out for 0.3.0's fixes
}
QUOTAS = {
    "cs.CL": 3, "cs.LG": 3, "cs.CV": 3, "cs.AI": 2, "stat.ML": 2,
    "q-bio.QM": 2, "quant-ph": 2, "astro-ph.GA": 2, "cs.SE": 1,
}  # fmt: skip
MIN_ENTRIES = 20
API = "https://export.arxiv.org/api/query"
EPRINT = "https://export.arxiv.org/e-print/"
DELAY = 3.5  # arXiv asks for at most one request every three seconds
HEADERS = {"User-Agent": "paper-preflight-eval (https://github.com/amos689/paper-preflight)"}
ATOM = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}


# ---------------------------------------------------------------- collect
def source_commit() -> str:
    """The commit of the checked-out code: results name it, as the version lags between releases."""
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=True
        )
    except (OSError, subprocess.CalledProcessError):
        return "unknown"
    return out.stdout.strip()


def manifest(batch: str) -> Path:
    return ROOT / ("real_papers.toml" if batch == "dev" else f"real_papers_{batch}.toml")


def results(batch: str) -> Path:
    return ROOT / "results" / ("real-papers.md" if batch == "dev" else f"real-papers-{batch}.md")


def polite_get(http: httpx.Client, url: str, **kwargs: Any) -> httpx.Response:
    """GET with arXiv's pause after every request, retrying its occasional 503s."""
    for attempt in range(5):
        response = http.get(url, **kwargs)
        time.sleep(DELAY * (1 + 4 * attempt * (response.status_code == 503)))
        if response.status_code != 503:
            return response
    return response


def candidates(
    http: httpx.Client, category: str, start: int, window: tuple[str, str]
) -> list[tuple[str, str]]:
    query = f"cat:{category} AND submittedDate:[{window[0]} TO {window[1]}]"
    params: dict[str, str | int] = {"search_query": query, "start": start, "max_results": 50,
              "sortBy": "submittedDate", "sortOrder": "ascending"}  # fmt: skip
    response = polite_get(http, API, params=params)
    response.raise_for_status()
    out = []
    for entry in ET.fromstring(response.text).findall("atom:entry", ATOM):
        arxiv_id = (entry.findtext("atom:id", "", ATOM) or "").rsplit("/abs/", 1)[-1]
        primary = entry.find("arxiv:primary_category", ATOM)
        # cross-lists are kept out: each paper belongs to the category it is counted in
        if primary is not None and primary.get("term") == category:
            out.append((arxiv_id, " ".join((entry.findtext("atom:title", "", ATOM)).split())))
    return out


def extract(content: bytes, target: Path) -> None:
    target.mkdir(parents=True, exist_ok=True)
    try:
        with tarfile.open(fileobj=io.BytesIO(content), mode="r:*") as archive:
            archive.extractall(target, filter="data")  # no absolute paths, no ".."
        return
    except tarfile.ReadError:
        pass
    data = gzip.decompress(content) if content[:2] == b"\x1f\x8b" else content
    if data.lstrip()[:1] == b"\\" or b"\\documentclass" in data[:20000]:
        (target / "main.tex").write_bytes(data)


def suitable(folder: Path) -> tuple[bool, str, int]:
    bibs = [p for p in folder.rglob("*.bib") if p.is_file()]
    entries = sum(len(parse_bib_file(p).entries) for p in bibs)
    if entries < MIN_ENTRIES:
        return False, "no .bib with enough entries" if bibs else "no .bib file", entries
    try:
        load_project(folder)
    except ProjectError as error:
        return False, f"no main .tex ({error})", entries
    return True, "", entries


def collect(batch: str) -> None:
    window = BATCHES[batch]
    selected: list[dict[str, Any]] = []
    skipped: dict[str, Counter[str]] = {}
    with httpx.Client(headers=HEADERS, timeout=60, follow_redirects=True) as http:
        for category, quota in QUOTAS.items():
            kept, start, reasons = 0, 0, Counter[str]()
            while kept < quota:
                found = candidates(http, category, start, window)
                if not found:
                    break
                start += 50
                for arxiv_id, title in found:
                    if kept == quota:
                        break
                    folder = DATA / arxiv_id.replace("/", "_")
                    if not folder.exists():
                        response = polite_get(http, EPRINT + arxiv_id)
                        if response.status_code != 200:
                            reasons[f"source unavailable ({response.status_code})"] += 1
                            continue
                        extract(response.content, folder)
                    ok, reason, entries = suitable(folder)
                    if not ok:
                        reasons[reason.split(" (")[0]] += 1
                        continue
                    kept += 1
                    selected.append({"id": arxiv_id, "category": category, "title": title,
                                     "bib_entries": entries})  # fmt: skip
                    print(f"  {category}: {arxiv_id} ({entries} entries) {title[:60]}", flush=True)
            skipped[category] = reasons
    lines = [
        "# Real papers for evals/real_papers.py (generated by `collect`; do not edit by hand).",
        f'batch = "{batch}"',
        f'window = ["{window[0]}", "{window[1]}"]',
        f"min_entries = {MIN_ENTRIES}",
        "",
    ]
    for paper in selected:
        lines += ["[[paper]]", f'id = "{paper["id"]}"', f'category = "{paper["category"]}"',
                  f"title = {json.dumps(paper['title'], ensure_ascii=False)}",
                  f"bib_entries = {paper['bib_entries']}", ""]  # fmt: skip
    for category, reasons in skipped.items():
        if reasons:
            lines += [f'[skipped."{category}"]']
            lines += [f"{json.dumps(r)} = {n}" for r, n in sorted(reasons.items())] + [""]
    manifest(batch).write_text("\n".join(lines), encoding="utf-8", newline="\n")
    print(f"{len(selected)} papers -> {manifest(batch).name}")


# ---------------------------------------------------------------- run


def run(batch: str) -> None:
    papers = tomllib.loads(manifest(batch).read_text(encoding="utf-8"))["paper"]
    REPORTS.mkdir(parents=True, exist_ok=True)
    for paper in papers:
        folder = DATA / paper["id"].replace("/", "_")
        started = time.monotonic()
        result = run_check(folder, verify=VerifyOptions(cache_path=CACHE))
        seconds = time.monotonic() - started
        payload = to_json_dict(result)
        payload["eval"] = {
            "id": paper["id"], "seconds": round(seconds, 1), "commit": source_commit(),
        }  # fmt: skip
        out = REPORTS / f"{paper['id'].replace('/', '_')}.json"
        out.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
        counts = payload["verification"]["verdicts"]
        print(
            f"  {paper['id']}: {len(result.verdicts)} refs, {seconds:.0f} s, {counts}", flush=True
        )


# ---------------------------------------------------------------- report


def flagged(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Warnings and errors about a reference: what a user would be asked to act on."""
    return [
        f for f in payload["findings"]
        if f["rule"].startswith("REF") and f["severity"] in {"warning", "error"}
    ]  # fmt: skip


def finding_id(paper_id: str, finding: dict[str, Any]) -> str:
    return f"{paper_id}:{finding.get('key')}:{finding['rule']}"


def report(batch: str) -> None:
    papers = tomllib.loads(manifest(batch).read_text(encoding="utf-8"))["paper"]
    review: dict[str, dict[str, str]] = {}
    if REVIEW.exists():
        review = tomllib.loads(REVIEW.read_text(encoding="utf-8")).get("finding", {})
    rows, unreviewed = [], []
    totals: Counter[str] = Counter()
    rules: Counter[tuple[str, str]] = Counter()
    commits: set[str] = set()
    for paper in papers:
        payload = json.loads(
            (REPORTS / f"{paper['id'].replace('/', '_')}.json").read_text(encoding="utf-8")
        )
        verdicts = payload["verification"]["verdicts"]
        refs = sum(verdicts.values())
        flags = flagged(payload)
        outcome: Counter[str] = Counter()
        for f in flags:
            label = review.get(finding_id(paper["id"], f), {}).get("verdict", "unreviewed")
            outcome[label] += 1
            rules[(f["rule"], label)] += 1
            if label == "unreviewed":
                unreviewed.append(finding_id(paper["id"], f))
        totals.update({"refs": refs, "flags": len(flags), **outcome,
                       "cannot": verdicts.get("cannot_determine", 0)})  # fmt: skip
        commits.add(payload["eval"].get("commit", "unknown"))
        rows.append(
            f"| {paper['id']} | {paper['category']} | {refs} | {len(flags)} | "
            f"{outcome['correct']} | {outcome['false_positive']} | {outcome['unclear']} | "
            f"{verdicts.get('cannot_determine', 0) / max(refs, 1):.0%} |"
        )
    refs = max(totals["refs"], 1)
    window = BATCHES[batch]
    lines = [
        f"# Real papers ({batch} batch)",
        "",
        f"- **Tool:** paper-preflight {__version__}, commit {', '.join(sorted(commits))}",
        f"- **Papers:** {len(papers)} arXiv papers first submitted {window[0][:4]}-"
        f"{window[0][4:6]}-{window[0][6:8]}..{window[1][6:8]}, chosen mechanically "
        f"(`evals/real_papers.py`, manifest `evals/{manifest(batch).name}`)",
        f"- **Run:** {datetime.now(UTC):%Y-%m-%d}, live sources (answers cached for the day, so "
        "a rerun with fixed code asks again only what changed; a cold run of 20 papers takes "
        "about 20 minutes)",
        "- **Flags:** warnings and errors about references; every one reviewed by hand "
        "(`evals/real_papers_review.toml`)",
        "",
        "## Summary",
        "",
        "| References checked | Flags | Real problems | False positives | Unclear | "
        "False positives per 100 references | Cannot determine |",
        "|---|---|---|---|---|---|---|",
        f"| {totals['refs']} | {totals['flags']} | {totals['correct']} | "
        f"{totals['false_positive']} | {totals['unclear']} | "
        f"{100 * totals['false_positive'] / refs:.1f} | {totals['cannot'] / refs:.0%} |",
        "",
        "## By paper",
        "",
        "| Paper | Category | References | Flags | Real | False positive | Unclear | "
        "Cannot determine |",
        "|---|---|---|---|---|---|---|---|",
        *rows,
        "",
        "## By rule",
        "",
        "| Rule | Real | False positive | Unclear |",
        "|---|---|---|---|",
        *[
            f"| {rule} | {rules[(rule, 'correct')]} | {rules[(rule, 'false_positive')]} | "
            f"{rules[(rule, 'unclear')]} |"
            for rule in sorted({r for r, _ in rules})
        ],
        "",
    ]
    if unreviewed:
        lines += [f"**{len(unreviewed)} flags are not reviewed yet.**", ""]
    results(batch).write_text("\n".join(lines), encoding="utf-8", newline="\n")
    print("\n".join(lines))
    if unreviewed:
        print("unreviewed:", *unreviewed, sep="\n  ", file=sys.stderr)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("command", choices=["collect", "run", "report"])
    parser.add_argument("--batch", choices=sorted(BATCHES), default="dev")
    args = parser.parse_args()
    {"collect": collect, "run": run, "report": report}[args.command](args.batch)


if __name__ == "__main__":
    main()
