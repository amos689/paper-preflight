"""The citation-support gold set: claims from real papers, each with the text of the work it
cites, for measuring ``support`` (third-round plan, S6).

    uv run python evals/support_gold.py sample     # pick the pairs (evals/support_gold.toml)
    uv run python evals/support_gold.py fetch      # each cited work's text (evals/.data/support)
    uv run python evals/support_gold.py packets    # one annotation packet per pair

Pairs come from the real-paper batches (evals/real_papers.py), from papers whose arXiv licence
allows reuse (CC BY, CC BY-SA, CC0), and only cite works paper-preflight verified. Sampling is
mechanical and seeded: at most PER_PAPER pairs per paper, one sentence per cited work, half of
the works with an arXiv ID (whose full text is usually available) where the paper has them.

The labels are made by AI annotators, independently, and adjudicated (see
evals/support_guidelines.md); they are not expert judgements. The cited works' text is
downloaded into evals/.data/support and never committed; the packets name passages by number,
so the gold file holds no text from the cited works.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import random
import re
import sys
import tomllib
from collections import Counter
from dataclasses import asdict
from pathlib import Path
from typing import Any

import httpx

from paper_preflight.bib.ids import extract_identifiers
from paper_preflight.bib.parse import parse_bib_file
from paper_preflight.cache import Cache
from paper_preflight.resolve import Sources
from paper_preflight.support.evidence import Evidence, EvidenceFetcher, Work
from paper_preflight.support.retrieve import rank
from paper_preflight.support.sentences import CITED_WORK, citation_sentences
from paper_preflight.tex.project import ProjectError, load_project

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import real_papers  # noqa: E402

GOLD = ROOT / "support_gold.toml"
LICENCES = ROOT / "support_licences.json"  # arXiv licence per paper (OAI-PMH)
SUPPORT = ROOT / ".data" / "support"
CACHE = ROOT / ".cache" / "support.sqlite3"
REUSABLE = ("/licenses/by/", "/licenses/by-sa/", "/publicdomain/zero/")
TARGET = 250
SWAPPED = 50  # claims paired with another work the paper cites: mis-citations, for negatives
PER_PAPER = 12
MIN_CLAIM_WORDS = 6
PACKET_PASSAGES = 10
SEED = 7


def _work(entry: Any, matched: dict[str, Any] | None) -> Work | None:
    own = {i.scheme: i.value for i in extract_identifiers(entry)}
    arxiv = own.get("arxiv")
    doi = own.get("doi")
    if matched:
        if matched.get("source") == "arxiv":
            arxiv = arxiv or matched.get("id")
        doi = doi or matched.get("doi")
    if doi and doi.lower().startswith("10.48550/arxiv."):
        arxiv, doi = arxiv or doi[len("10.48550/arxiv.") :], None
    if not (arxiv or doi):
        return None
    return Work(doi=doi.lower() if doi else None, arxiv=arxiv, pmcid=own.get("pmcid"))


def _papers() -> list[str]:
    licences = json.loads(LICENCES.read_text(encoding="utf-8"))
    papers = []
    for batch in real_papers.BATCHES:
        if not real_papers.manifest(batch).exists():
            continue
        manifest = tomllib.loads(real_papers.manifest(batch).read_text(encoding="utf-8"))
        for paper in manifest["paper"]:
            licence = licences.get(re.sub(r"v\d+$", "", paper["id"]), "")
            if any(part in licence for part in REUSABLE):
                papers.append(paper["id"])
    return papers


def _pair(paper: str, sentence: Any, work: Work) -> dict[str, Any]:
    work_fields = {k: v for k, v in asdict(work).items() if v}
    ident = f"{paper}:{sentence.key}:{sentence.line}"
    packet = hashlib.sha1(json.dumps([ident, work_fields]).encode()).hexdigest()[:10]
    return {
        "id": ident, "packet": packet, "paper": paper, "key": sentence.key,
        "line": sentence.line, "kind": sentence.kind, "claim": sentence.claim,
        "sentence": sentence.sentence, "previous": sentence.previous, **work_fields,
    }  # fmt: skip


def sample() -> None:
    rng = random.Random(SEED)
    pairs: list[dict[str, Any]] = []
    swapped: list[dict[str, Any]] = []
    for paper in _papers():
        folder = real_papers.DATA / paper.replace("/", "_")
        report = real_papers.REPORTS / f"{paper.replace('/', '_')}.json"
        if not report.exists():
            continue
        refs = {r["key"]: r for r in json.loads(report.read_text(encoding="utf-8"))["references"]}
        try:
            project = load_project(folder)
        except ProjectError:
            continue
        entries = {
            e.key: e
            for r in project.bib_resources
            if r.exists
            for e in parse_bib_file(r.path).entries
        }
        by_key: dict[str, list[Any]] = {}
        everything = citation_sentences(project)
        together: dict[str, set[str]] = {}  # keys cited in one sentence: no swap among them
        for s in everything:
            together.setdefault(s.sentence, set()).add(s.key)
        for s in everything:
            ref = refs.get(s.key)
            if not ref or ref["verdict"] not in {"verified", "metadata_mismatch"}:
                continue
            if len(s.claim.split()) < MIN_CLAIM_WORDS or s.key not in entries:
                continue
            by_key.setdefault(s.key, []).append(s)
        candidates = []
        for key, sentences in sorted(by_key.items()):
            work = _work(entries[key], refs[key].get("matched"))
            if work is not None:
                candidates.append((rng.choice(sentences), work))
        with_arxiv = [c for c in candidates if c[1].arxiv]
        without = [c for c in candidates if not c[1].arxiv]
        rng.shuffle(with_arxiv)
        rng.shuffle(without)
        half = PER_PAPER // 2
        chosen = with_arxiv[:half] + without[:half]
        rest = with_arxiv[half:] + without[half:]
        chosen += rest[: PER_PAPER - len(chosen)]
        for sentence, work in chosen:
            pairs.append(_pair(paper, sentence, work))
        # one mis-citation per paper: a claim paired with another work the paper cites (one
        # with an arXiv ID, so that its full text can show the claim is absent)
        others = [c for c in with_arxiv if c not in chosen[:1]]
        if chosen and others:
            sentence = chosen[0][0]
            other_key, other = next(
                ((s.key, w) for s, w in others if s.key != sentence.key
                 and s.key not in together[sentence.sentence]), (None, None),
            )  # fmt: skip
            if other is not None:
                swapped.append({**_pair(paper, sentence, other), "swapped": other_key})
    rng.shuffle(pairs)
    pairs = pairs[:TARGET]
    kept = {p["paper"] for p in pairs}
    pairs += [p for p in swapped if p["paper"] in kept][:SWAPPED]
    pairs = sorted(pairs, key=lambda p: (p["id"], "swapped" in p))
    write_gold(pairs)
    kinds = dict(Counter(p["kind"] for p in pairs))
    papers = len({p["paper"] for p in pairs})
    print(
        len(pairs),
        "pairs from",
        papers,
        "papers;",
        kinds,
        "arXiv:",
        sum("arxiv" in p for p in pairs),
    )


HEADER = [
    "# Citation-support gold set (evals/support_gold.py): claims from CC BY, CC BY-SA and",
    "# CC0 arXiv papers, the works they cite, and AI annotators' labels",
    "# (see support_guidelines.md).",
    "",
]


def write_gold(pairs: list[dict[str, Any]]) -> None:
    lines = list(HEADER)
    for pair in pairs:
        lines.append("[[pair]]")
        lines += [f"{k} = {json.dumps(v, ensure_ascii=False)}" for k, v in pair.items()]
        lines.append("")
    GOLD.write_text("\n".join(lines), encoding="utf-8", newline="\n")


def _pairs() -> list[dict[str, Any]]:
    return list(tomllib.loads(GOLD.read_text(encoding="utf-8"))["pair"])


def _work_of(pair: dict[str, Any]) -> Work:
    return Work(doi=pair.get("doi"), arxiv=pair.get("arxiv"), pmcid=pair.get("pmcid"))


def _evidence_path(work: Work) -> Path:
    name = re.sub(r"[^\w.-]", "_", work.arxiv or work.doi or work.pmcid or "none")
    return SUPPORT / "evidence" / f"{name}.json"


def fetch() -> None:
    async def run() -> None:
        cache = Cache(CACHE)
        try:
            async with httpx.AsyncClient(follow_redirects=True) as http:
                sources = Sources.create(http, cache)
                fetcher = EvidenceFetcher(http, sources, cache, SUPPORT / "downloads")
                works = list(dict.fromkeys(_work_of(p) for p in _pairs()))
                for n, work in enumerate(works, 1):
                    path = _evidence_path(work)
                    if path.exists():
                        continue
                    found = await fetcher.evidence(work)
                    path.parent.mkdir(parents=True, exist_ok=True)
                    data = json.dumps(asdict(found), ensure_ascii=False)
                    path.write_text(data, encoding="utf-8")
                    label = work.arxiv or work.doi
                    print(f"{n}/{len(works)} {label}: {found.level} ({found.source}, "
                          f"{len(found.passages)} passages)", flush=True)  # fmt: skip
        finally:
            cache.close()

    asyncio.run(run())
    levels = Counter(
        _load(_work_of(p)).level for p in _pairs() if _evidence_path(_work_of(p)).exists()
    )
    print(dict(levels))


def _load(work: Work) -> Evidence:
    data = json.loads(_evidence_path(work).read_text(encoding="utf-8"))
    return Evidence(data["level"], data["source"], tuple(data["passages"]), tuple(data["notes"]))


def packets() -> None:
    out = SUPPORT / "packets"
    out.mkdir(parents=True, exist_ok=True)
    for pair in _pairs():
        evidence = _load(_work_of(pair))
        hits = rank(pair["claim"], evidence.passages, top=PACKET_PASSAGES)
        shown = sorted({0, *(h.index for h in hits)} & set(range(len(evidence.passages))))
        name = pair["packet"]  # opaque: the citation key would give a swapped pair away
        full = out / f"{name}.fulltext.txt"
        full.write_text(
            "\n\n".join(f"[{i}] {p}" for i, p in enumerate(evidence.passages)), encoding="utf-8"
        )
        packet = {
            "id": pair["packet"],
            "claim": pair["claim"],
            "sentence": pair["sentence"],
            "previous_sentence": pair["previous"],
            "cited_work": {k: pair[k] for k in ("doi", "arxiv", "pmcid") if k in pair},
            "evidence_level": evidence.level,
            "evidence_source": evidence.source,
            "passages": {str(i): evidence.passages[i] for i in shown},
            "full_text_file": full.name if evidence.passages else None,
            "note": f"{CITED_WORK} stands for the citation itself, used as a noun.",
        }
        (out / f"{name}.json").write_text(
            json.dumps(packet, ensure_ascii=False, indent=1), encoding="utf-8"
        )
    print(len(_pairs()), "packets in", out)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("command", choices=["sample", "fetch", "packets"])
    command = parser.parse_args().command
    {"sample": sample, "fetch": fetch, "packets": packets}[command]()


if __name__ == "__main__":
    main()
