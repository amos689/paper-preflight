"""Word manuscripts against their .bib: the same references, read from a .docx, should get the
same verdicts.

For each paper of a real-paper batch, the .bib entries the paper cites are written into Word
documents in two ways:

* with field codes, as Zotero writes them (one CSL-JSON item per citation);
* as a typed reference list, each reference rendered by citeproc-py in a citation style (APA,
  IEEE, NLM/Vancouver), one paragraph each under a "References" heading.

Each document and the paper itself are checked with the same code (from the evaluation cache;
``--fill`` asks the sources for what the cache lacks), and every reference is compared: did the
reader recover its title, first author and year, and does it get the same verdict as from the
.bib? The styles come from the CSL project (evals/.data/csl-styles, see evals/README.md).

    uv run python evals/docx_agreement.py --batch dev --fill
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
import tomllib
import zipfile
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from citeproc import (  # noqa: E402
    Citation,
    CitationItem,
    CitationStylesBibliography,
    CitationStylesStyle,
    formatter,
)
from citeproc.source.json import CiteProcJSON  # noqa: E402

from paper_preflight.bib.ids import extract_identifiers  # noqa: E402
from paper_preflight.bib.normalize import fold, title_key  # noqa: E402
from paper_preflight.bib.parse import BibEntry  # noqa: E402
from paper_preflight.cache import Cache  # noqa: E402
from paper_preflight.check import CheckResult, VerifyOptions, run_check  # noqa: E402
from paper_preflight.match import EntryInfo  # noqa: E402

DATA = ROOT / ".data" / "real_papers"
CACHE = ROOT / ".cache" / "real_papers.sqlite3"
STYLES = ROOT / ".data" / "csl-styles"
RESULTS = ROOT / "results" / "docx-agreement.md"
W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
STYLE_FILES = {
    "apa": "apa.csl",
    "ieee": "ieee.csl",
    "nlm": "nlm-citation-sequence-brackets.csl",
}
_CSL_TYPES = {
    "article": "article-journal",
    "inproceedings": "paper-conference",
    "conference": "paper-conference",
    "incollection": "chapter",
    "inbook": "chapter",
    "book": "book",
    "phdthesis": "thesis",
    "mastersthesis": "thesis",
    "techreport": "report",
}


def every_answer_counts() -> None:
    get = Cache.get

    def stale_too(self: Cache, source: str, key: str, allow_stale: bool = False) -> Any:
        return get(self, source, key, allow_stale=True)

    Cache.get = stale_too  # type: ignore[method-assign]


def csl_item(entry: BibEntry) -> dict[str, Any]:
    """The entry as a reference manager would hold it."""
    info = EntryInfo.from_entry(entry)
    item: dict[str, Any] = {
        "id": entry.key,
        "type": _CSL_TYPES.get(entry.entry_type, "article"),
        "title": info.title,
        "author": [
            {"literal": p.literal} if p.literal else {"family": p.family, "given": p.given}
            for p in info.authors.people
        ],
    }
    if info.year:
        item["issued"] = {"date-parts": [[info.year]]}
    if info.venue:
        item["container-title"] = info.venue
    for name, field in (("volume", "volume"), ("number", "issue"), ("pages", "page")):
        if entry.text(name):
            item[field] = entry.text(name)
    for identifier in extract_identifiers(entry):
        if identifier.scheme == "doi" and "DOI" not in item:
            item["DOI"] = identifier.value
        elif identifier.scheme == "arxiv" and "number" not in item:
            item["number"] = f"arXiv:{identifier.value}"
    return item


def rendered(item: dict[str, Any], style: CitationStylesStyle, number: int) -> str:
    """One reference in the style, numbered as the n-th of a list (rendered alone, every
    reference would say "1." or "[1]")."""
    source = CiteProcJSON([item])
    bibliography = CitationStylesBibliography(style, source, formatter.plain)
    bibliography.register(Citation([CitationItem(item["id"])]))
    text = " ".join(str(bibliography.bibliography()[0]).split())
    # the n-th number, and the tab Word puts after it (plain text from citeproc-py has none)
    return _NUMBER.sub(lambda m: m.group(0).replace("1", str(number), 1) + " ", text, count=1)


_NUMBER = re.compile(r"^\s*(?:\[1\]|1\.)")


def paragraph(text: str) -> str:
    return f'<w:p><w:r><w:t xml:space="preserve">{escape(text)}</w:t></w:r></w:p>'


def zotero_field(item: dict[str, Any]) -> str:
    cited = {"citationItems": [{"id": 1, "uris": [item["id"]], "itemData": item}]}
    instruction = "ADDIN ZOTERO_ITEM CSL_CITATION " + json.dumps(cited, ensure_ascii=False)
    return (
        '<w:p><w:r><w:fldChar w:fldCharType="begin"/></w:r>'
        f'<w:r><w:instrText xml:space="preserve">{escape(instruction)}</w:instrText></w:r>'
        '<w:r><w:fldChar w:fldCharType="separate"/></w:r><w:r><w:t>[1]</w:t></w:r>'
        '<w:r><w:fldChar w:fldCharType="end"/></w:r></w:p>'
    )


def write_docx(path: Path, body: str) -> Path:
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(
            "word/document.xml",
            f'<w:document xmlns:w="{W}"><w:body>{body}</w:body></w:document>',
        )
    return path


def verdicts(result: CheckResult) -> dict[str, str]:
    return {key: assessment.verdict.value for key, assessment in result.verdicts.items()}


def fields_of(result: CheckResult) -> dict[str, tuple[str, str, int | None]]:
    out = {}
    for bib in result.bib_files:
        for entry in bib.entries:
            info = EntryInfo.from_entry(entry)
            first = fold(info.authors.people[0].family) if info.authors.people else ""
            out[entry.key] = (title_key(info.title), first, info.year)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--batch", default="dev")
    parser.add_argument("--fill", action="store_true", help="fetch the answers the cache lacks")
    parser.add_argument("--style", nargs="+", default=list(STYLE_FILES), choices=list(STYLE_FILES))
    parser.add_argument("--limit", type=int, default=0, help="papers to use (0 = all)")
    args = parser.parse_args()
    every_answer_counts()
    options = VerifyOptions(cache_path=CACHE, offline=not args.fill)
    name = "real_papers.toml" if args.batch == "dev" else f"real_papers_{args.batch}.toml"
    papers = [p["id"] for p in tomllib.loads((ROOT / name).read_text(encoding="utf-8"))["paper"]]
    papers = papers[: args.limit] if args.limit else papers
    styles = {
        s: CitationStylesStyle(str(STYLES / STYLE_FILES[s]), validate=False) for s in args.style
    }
    tally: dict[str, dict[str, int]] = {}
    work = Path(tempfile.mkdtemp())
    for pid in papers:
        paper = run_check(DATA / pid.replace("/", "_"), verify=options)
        expected = verdicts(paper)
        truth = fields_of(paper)
        entries = {e.key: e for b in paper.bib_files for e in b.entries if e.key in expected}
        keys = list(entries)
        items = [csl_item(entries[k]) for k in keys]
        variants: dict[str, tuple[Path, list[str]]] = {
            "field codes": (
                write_docx(work / f"{pid}-fields.docx", "".join(map(zotero_field, items))),
                keys,
            )
        }
        for style_name, style in styles.items():
            lines, order = [], []
            for key, item in zip(keys, items, strict=True):
                try:
                    lines.append(rendered(item, style, len(lines) + 1))
                    order.append(key)
                except Exception:  # citeproc-py fails on a few items; they are left out
                    continue
            body = (
                paragraph("Introduction text.")
                + paragraph("References")
                + "".join(map(paragraph, lines))
            )
            variants[style_name] = (write_docx(work / f"{pid}-{style_name}.docx", body), order)
        for label, (path, order) in variants.items():
            result = run_check(path, verify=options)
            got = verdicts(result)
            read = fields_of(result)
            row = tally.setdefault(
                label,
                dict.fromkeys(
                    ("references", "read", "title", "first author", "year", "same verdict",
                     "abstained"),
                    0,
                ),
            )  # fmt: skip
            # both documents keep the references in the order written: the n-th read is the n-th
            positions = list(read)
            for index, key in enumerate(order):
                row["references"] += 1
                if index >= len(positions):
                    continue
                mine = positions[index]
                row["read"] += 1
                title, author, year = read[mine]
                true_title, true_author, true_year = truth.get(key, ("", "", None))
                row["title"] += title == true_title
                row["first author"] += author == true_author
                row["year"] += year == true_year
                verdict = got.get(mine)
                row["same verdict"] += verdict == expected[key]
                row["abstained"] += (
                    verdict == "cannot_determine" and expected[key] != "cannot_determine"
                )
        print(pid, {k: v["same verdict"] for k, v in tally.items()}, flush=True)
    commit = (STYLES / "COMMIT").read_text().strip()[:7]
    lines = [
        "# Word manuscripts against their .bib",
        "",
        f"- **Data:** the {args.batch} batch of real papers ({len(papers)} papers); each paper's"
        " cited .bib entries written into Word documents (`evals/docx_agreement.py`)",
        f"- **Styles:** CSL styles at commit {commit}, rendered by citeproc-py",
        "",
        "| Document | References | Read | Title | First author | Year | Same verdict "
        "| Abstained instead |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for label, row in tally.items():
        n = row["references"] or 1
        lines.append(
            f"| {label} | {row['references']} | {row['read']} | {row['title'] / n:.1%} | "
            f"{row['first author'] / n:.1%} | {row['year'] / n:.1%} | "
            f"{row['same verdict'] / n:.1%} | {row['abstained']} |"
        )
    RESULTS.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
