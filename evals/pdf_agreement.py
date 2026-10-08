"""How well paper-preflight reads a PDF's reference list: the real papers' PDFs against their .bib.

For each paper of a real-paper batch (evals/real_papers.py), the PDF arXiv serves is read with
`check paper.pdf` and compared with the check of the paper's own .bib from the same batch:

* found: references of the .bib check that the PDF's list holds (the title read from the PDF is
  the .bib title, 90% similar or more);
* first author, year: of those, the first author's family name and the year read from the PDF;
* same verdict: of those, the PDF reference has the .bib reference's verdict.

    uv run python evals/pdf_agreement.py --batch dev   # needs evals/real_papers.py run first

The PDFs are downloaded once from export.arxiv.org (one request every 3.5 s) into
evals/.data/real_papers_pdf and never committed.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import tomllib
from datetime import UTC, datetime
from difflib import SequenceMatcher
from pathlib import Path

import httpx

from paper_preflight import __version__
from paper_preflight.bib.names import parse_authors
from paper_preflight.bib.normalize import fold
from paper_preflight.bib.parse import BibEntry, parse_bib_file
from paper_preflight.check import VerifyOptions, run_check

sys.path.insert(0, str(Path(__file__).resolve().parent))
import real_papers

ROOT = Path(__file__).resolve().parent
PDFS = ROOT / ".data" / "real_papers_pdf"
PDF_URL = "https://export.arxiv.org/pdf/"


def words(text: str | None) -> str:
    return " ".join(fold(text or "").split())


def family(entry: BibEntry) -> str:
    people = parse_authors(entry.text("author")).people
    return fold(people[0].family or people[0].literal).split(" ")[-1] if people else ""


def identifiers(entry: BibEntry) -> set[str]:
    return {(entry.text(f) or "").lower() for f in ("doi", "eprint") if entry.text(f)}


def counterpart(entry: BibEntry, read: list[BibEntry]) -> BibEntry | None:
    """The reference read from the PDF that is the .bib entry: the same DOI or arXiv ID, else a
    title 90% alike, else, where the PDF's style prints no title, the only reference with the
    same first author and year."""
    ids = identifiers(entry)
    for candidate in read:
        if ids & identifiers(candidate):
            return candidate
    title = words(entry.text("title"))
    if title:
        scored = [(SequenceMatcher(None, words(r.text("title")), title).ratio(), r) for r in read]
        best = max(scored, key=lambda pair: pair[0], default=None)
        if best is not None and best[0] >= 0.9:
            return best[1]
    untitled = [
        r for r in read
        if not r.text("title") and family(r) == family(entry) and family(entry)
        and (r.text("year") or "") == (entry.text("year") or "")
    ]  # fmt: skip
    return untitled[0] if len(untitled) == 1 else None


def download(ids: list[str]) -> None:
    PDFS.mkdir(parents=True, exist_ok=True)
    with httpx.Client(headers=real_papers.HEADERS, timeout=120, follow_redirects=True) as http:
        for arxiv_id in ids:
            path = PDFS / f"{arxiv_id.replace('/', '_')}.pdf"
            if path.exists():
                continue
            response = http.get(PDF_URL + arxiv_id)
            time.sleep(real_papers.DELAY)
            if response.status_code == 200 and response.content[:5] == b"%PDF-":
                path.write_bytes(response.content)
            else:
                print(f"  {arxiv_id}: no PDF (HTTP {response.status_code})", flush=True)


def bib_entries(arxiv_id: str) -> dict[str, BibEntry]:
    folder = real_papers.DATA / arxiv_id.replace("/", "_")
    entries: dict[str, BibEntry] = {}
    for path in sorted(folder.rglob("*.bib")):
        for entry in parse_bib_file(path).entries:
            entries.setdefault(entry.key, entry)
    return entries


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--batch", choices=sorted(real_papers.BATCHES), default="dev")
    batch = parser.parse_args().batch
    papers = tomllib.loads(real_papers.manifest(batch).read_text(encoding="utf-8"))["paper"]
    download([p["id"] for p in papers])
    totals = {"references": 0, "found": 0, "author": 0, "year": 0, "verdict": 0}
    rows = []
    for paper in papers:
        arxiv_id = paper["id"]
        pdf = PDFS / f"{arxiv_id.replace('/', '_')}.pdf"
        report = real_papers.REPORTS / f"{arxiv_id.replace('/', '_')}.json"
        if not pdf.exists() or not report.exists():
            continue
        checked = json.loads(report.read_text(encoding="utf-8"))
        verdicts = {r["key"]: r["verdict"] for r in checked["references"]}
        entries = bib_entries(arxiv_id)
        result = run_check(
            pdf, verify=VerifyOptions(cache_path=real_papers.CACHE, remember_too_new=False)
        )
        read = result.bib_files[0].entries
        found = author = year = same = 0
        for key, verdict in verdicts.items():
            entry = entries.get(key)
            if entry is None:
                continue
            best = counterpart(entry, read)
            if best is None:
                continue
            found += 1
            author += family(best) == family(entry)
            year += (best.text("year") or "") == (entry.text("year") or "")
            pdf_verdict = result.verdicts.get(best.key)
            same += pdf_verdict is not None and pdf_verdict.verdict.value == verdict
        n = len(verdicts)
        rows.append((arxiv_id, paper["category"], n, len(read), found, author, year, same))
        for name, value in zip(totals, (n, found, author, year, same), strict=True):
            totals[name] += value
        print(f"  {arxiv_id}: {found}/{n} found, {same} same verdict", flush=True)

    def pct(part: int, whole: int) -> str:
        return f"{part}/{whole} ({part / whole:.0%})" if whole else "-"

    lines = [
        f"# PDF reference lists ({batch} batch)",
        "",
        f"- **Tool:** paper-preflight {__version__}, commit {real_papers.source_commit()}",
        f"- **Papers:** the {len(rows)} papers of `evals/{real_papers.manifest(batch).name}` "
        "whose PDF arXiv serves; each PDF read with `check paper.pdf` (the `pdf` extra) and "
        "compared with the check of the paper's own .bib",
        f"- **Run:** {datetime.now(UTC):%Y-%m-%d} (`evals/pdf_agreement.py`)",
        "",
        "| References checked from the .bib | Found in the PDF | Same first author | Same year | "
        "Same verdict |",
        "|---|---|---|---|---|",
        f"| {totals['references']} | {pct(totals['found'], totals['references'])} | "
        f"{pct(totals['author'], totals['found'])} | {pct(totals['year'], totals['found'])} | "
        f"{pct(totals['verdict'], totals['found'])} |",
        "",
        "| Paper | Category | .bib references | Read from the PDF | Found | Same verdict |",
        "|---|---|---|---|---|---|",
    ]
    lines += [
        f"| {pid} | {cat} | {n} | {read} | {found} | {same} |"
        for pid, cat, n, read, found, _, _, same in rows
    ]
    out = ROOT / "results" / f"pdf-{batch}.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print("\n".join(lines[:10]))


if __name__ == "__main__":
    main()
