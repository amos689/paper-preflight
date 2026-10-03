"""Human-readable terminal report."""

from __future__ import annotations

from rich.cells import cell_len
from rich.console import Console
from rich.text import Text

from paper_preflight.check import CheckResult
from paper_preflight.findings import Severity

_STYLE = {Severity.ERROR: "bold red", Severity.WARNING: "yellow", Severity.INFO: "cyan"}
_LABEL = {
    "en": {Severity.ERROR: "error", Severity.WARNING: "warning", Severity.INFO: "info"},
    "zh": {Severity.ERROR: "错误", Severity.WARNING: "警告", Severity.INFO: "提示"},
}


def render_text(
    result: CheckResult, console: Console, lang: str = "en", show_info: bool = True
) -> None:
    zh = lang.startswith("zh")
    labels = _LABEL["zh" if zh else "en"]
    main = result.main.relative_to(result.root).as_posix() if result.main else None
    header = f"paper-preflight {result.tool_version}"
    if main:
        header += f" · {main}"
    if zh:
        header += f" · {result.entries} 条参考文献，{result.cited_keys} 个被引用的键"
    else:
        header += f" · {result.entries} entries, {result.cited_keys} cited keys"
    console.print(header, style="bold", highlight=False)
    if result.used_build_data:
        note = (
            f"（被引用的键取自 {result.used_build_data}）"
            if zh
            else f"(cited keys taken from {result.used_build_data})"
        )
        console.print(note, style="dim", highlight=False)
    for message in result.notes:
        console.print(message, style="dim", highlight=False)

    shown = [f for f in result.findings if show_info or f.severity is not Severity.INFO]
    if shown:
        console.print()
    for finding in shown:
        line = Text()
        label = labels[finding.severity]
        line.append(label + " " * max(1, 8 - cell_len(label)), style=_STYLE[finding.severity])
        line.append(f"{finding.rule_id} ", style="bold")
        if finding.location is not None:
            line.append(finding.location.display(result.root), style="dim")
        console.print(line, highlight=False)
        console.print(Text("    " + finding.message.get(lang)), highlight=False)

    console.print()
    errors = result.count(Severity.ERROR)
    warnings = result.count(Severity.WARNING)
    infos = result.count(Severity.INFO)
    if zh:
        summary = f"错误 {errors} · 警告 {warnings} · 提示 {infos}"
    else:
        summary = f"{errors} error(s) · {warnings} warning(s) · {infos} info"
    style = "bold red" if errors else ("yellow" if warnings else "green")
    verification = verification_line(result, zh)
    if verification:
        console.print(verification, highlight=False)
    console.print(summary, style=style, highlight=False)


_VERDICT_LABEL = {
    "verified": ("verified", "已核实"),
    "metadata_mismatch": ("metadata mismatch", "元数据不符"),
    "identifier_conflict": ("identifier conflict", "标识符冲突"),
    "not_found": ("not found", "未找到"),
    "cannot_determine": ("cannot determine", "无法确定"),
}


def verification_line(result: CheckResult, zh: bool) -> str:
    """``References: 9 verified · 1 not found · 2 cannot determine (offline: 2 not verified)``."""
    if result.verification == "skipped":
        return ""
    if not result.verdicts:
        return "参考文献核查：没有需要核查的条目" if zh else "References: none to verify"
    parts = [
        f"{_VERDICT_LABEL[verdict][1]} {n}" if zh else f"{n} {_VERDICT_LABEL[verdict][0]}"
        for verdict, n in result.verdict_counts().items()
        if n
    ]
    line = ("参考文献核查：" if zh else "References: ") + " · ".join(parts)
    if result.unverified_offline:
        n = result.unverified_offline
        line += (
            f"（离线模式：{n} 条没有缓存结果，未核查）"
            if zh
            else f" (offline: {n} without a cached answer, not verified)"
        )
    return line
