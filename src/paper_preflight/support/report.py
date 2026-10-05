"""``support`` reports: where the cited works confirm their citations, with the passage (S5).

Text lists the citations the tool could not confirm, with the reason, then (with ``--all``) the
confirmed ones with their quotes, and a count of each. "Could not confirm" is no accusation: a
citation is often fine where the accessible text says it in other words. JSON has everything.
"""

from __future__ import annotations

import json
from typing import Any

from rich.console import Console

from paper_preflight import __version__
from paper_preflight.support.judge import NOT_CONFIRMED, SUPPORTED
from paper_preflight.support.run import SupportItem, SupportResult

REASONS = {
    "en": {
        "SUPPORTING_PASSAGE": "the cited work says so",
        "NAME_IN_TITLE": "the citation names the cited work, and its title says so",
        "NO_TEXT": "no text of the cited work could be had",
        "ABSTRACT_ONLY": "only the abstract could be had, and it does not say so",
        "NOT_FOUND": "no passage of the accessible text says so in words close enough",
    },
    "zh": {
        "SUPPORTING_PASSAGE": "被引文献中有这样的表述",
        "NAME_IN_TITLE": "引用处点了名，被引文献的标题里就是这个名字",
        "NO_TEXT": "无法获取被引文献的文本",
        "ABSTRACT_ONLY": "只拿到了摘要，摘要中没有这样说",
        "NOT_FOUND": "可访问的文本中没有足够接近的表述",
    },
}
HEADINGS = {
    "en": {
        NOT_CONFIRMED: "Could not confirm",
        SUPPORTED: "Confirmed, with the passage",
        "summary": "{n} citations: {s} confirmed by a passage of the cited work, {c} not confirmed",
        "skipped": "{n} cited works were not looked at (not verified, or no identifier)",
        "note": (
            "An evidence finder, not a judge: a local model compared each claim with the passages "
            "of the cited work it could read. Not confirmed does not mean wrong."
        ),
    },
    "zh": {
        NOT_CONFIRMED: "未能确认",
        SUPPORTED: "已确认（附原文）",
        "summary": "共 {n} 处引用：{s} 处有被引文献原文确认，{c} 处未能确认",
        "skipped": "{n} 篇被引文献未查看（未核实，或没有可用的标识符）",
        "note": (
            "这是找证据的工具，不是裁判：本地模型把每句话与能读到的被引文献段落逐一比较。"
            "未能确认不等于引用有误。"
        ),
    },
}


def item_dict(item: SupportItem) -> dict[str, Any]:
    citation, judgement, evidence = item.citation, item.judgement, item.evidence
    return {
        "key": citation.key,
        "file": str(citation.file),
        "line": citation.line,
        "column": citation.column,
        "claim": citation.claim,
        "sentence": citation.sentence,
        "kind": citation.kind,
        "verdict": judgement.verdict,
        "reason": judgement.reason,
        "score": round(judgement.score, 3),
        "quote": judgement.quote or None,
        "passage": judgement.passage if judgement.passage >= 0 else None,
        "evidence": {
            "level": evidence.level,
            "source": evidence.source,
            "notes": list(evidence.notes),
        },
    }


def render_json(result: SupportResult, model: str) -> str:
    return json.dumps(
        {
            "tool": {"name": "paper-preflight", "version": __version__, "verifier": model},
            "citations": [item_dict(i) for i in result.items],
            "skipped": result.skipped,
        },
        ensure_ascii=False,
        indent=1,
    )


def render_text(result: SupportResult, console: Console, language: str, everything: bool) -> None:
    words, reasons = HEADINGS[language], REASONS[language]
    groups = {v: [i for i in result.items if i.judgement.verdict == v]
              for v in (NOT_CONFIRMED, SUPPORTED)}  # fmt: skip
    shown = [NOT_CONFIRMED] + ([SUPPORTED] if everything else [])
    for verdict in shown:
        if not groups[verdict]:
            continue
        console.print(f"\n[bold]{words[verdict]}[/bold] ({len(groups[verdict])})")
        for item in groups[verdict]:
            citation, judgement = item.citation, item.judgement
            console.print(f"  {citation.file.name}:{citation.line}  [cyan]{citation.key}[/cyan]")
            console.print(f"    {citation.claim}", markup=False)
            console.print(f"    → {reasons[judgement.reason]} ({item.evidence.source or '-'})")
            if judgement.quote:
                console.print(f'    "{judgement.quote}"', markup=False)
    console.print()
    console.print(words["summary"].format(
        n=len(result.items), s=len(groups[SUPPORTED]), c=len(groups[NOT_CONFIRMED]),
    ))  # fmt: skip
    if result.skipped:
        console.print(words["skipped"].format(n=len(result.skipped)))
    console.print(f"[dim]{words['note']}[/dim]")
