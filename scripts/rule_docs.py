"""Write docs/rules/: one page per rule and an index, from rules.py and guides.py.

    uv run python scripts/rule_docs.py

The pages say what `paper-preflight explain <RULE>` says, in English and Chinese; SARIF reports
link to them. tests/test_rule_docs.py fails when a page is out of date: run this to update.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs" / "rules"

FAMILIES = [
    ("REF", "Reference verification", "文献核查"),
    ("CIT", "Citation keys and the bibliography", "引用键与参考文献文件"),
    ("TEX", "LaTeX project structure", "LaTeX 项目结构"),
    ("RUN", "The run", "运行状态"),
    ("CFG", "Configuration", "配置"),
]
SEVERITY_ZH = {"error": "错误", "warning": "警告", "info": "提示"}
FIX_EN = {
    "safe": "`bib fix` (the default, safe level)",
    "unsafe": "`bib fix --level unsafe`: review the diff before applying it",
    "suggestion": "by hand, as the message suggests",
}
FIX_ZH = {
    "safe": "`bib fix`（默认的 safe 级别）",
    "unsafe": "`bib fix --level unsafe`：应用前请先检查差异",
    "suggestion": "按消息中的建议手动修改",
}


def _code(template: str) -> str:
    return "\n".join(f"    {line}" for line in template.splitlines())


# findings tied to an entry, which a comment above the entry can silence
_ENTRY_RULES = frozenset({"CIT002", "CIT003", "CIT004", "CIT006", "CIT008"})


def _silence(rule_id: str, lang: str) -> list[str]:
    settings = f'ignore-rules = ["{rule_id}"]'
    if lang == "en":
        lines = [f"To turn it off for the whole project: `{settings}` in the project's settings."]
        if rule_id.startswith("REF") or rule_id in _ENTRY_RULES:
            lines = [
                "To silence it for one entry once you have checked it, put a comment above the "
                "entry:",
                "",
                f'    % preflight: ignore[{rule_id}] reason="..."',
                "",
                *lines,
            ]
    else:
        lines = [f"对整个项目关闭此规则：在项目设置中写 `{settings}`。"]
        if rule_id.startswith("REF") or rule_id in _ENTRY_RULES:
            lines = [
                "核对之后，如需对某个条目消除此规则，在条目上方加注释：",
                "",
                f'    % preflight: ignore[{rule_id}] reason="..."',
                "",
                *lines,
            ]
    return [*lines, ""]


def page(rule_id: str) -> str:
    from paper_preflight.rules import describe

    d = describe(rule_id)
    assert d is not None
    guide, fix = d["guide"], d["fix"]
    lines = [
        f"# {d['rule']} · {d['name']}",
        "",
        "<!-- Written by scripts/rule_docs.py from src/paper_preflight/rules.py and guides.py:"
        " edit those, not this page. -->",
        "",
        f"**{d['summary']['en']}** · {d['summary']['zh']}",
        "",
        "| | |",
        "|---|---|",
        f"| Severity · 严重度 | {d['severity']} · {SEVERITY_ZH[d['severity']]} |",
        f"| Fix · 修复 | {FIX_EN[fix] if fix else 'none'} · {FIX_ZH[fix] if fix else '无'} |",
        "",
        "## English",
        "",
        "Message:",
        "",
        _code(d["message_template"]["en"]),
        "",
        f"**What it checks.** {guide['checks']['en']}",
        "",
        f"**When it can be wrong.** {guide['wrong']['en']}",
        "",
        f"**What to do.** {guide['action']['en']}",
        "",
        *_silence(d["rule"], "en"),
        "## 中文",
        "",
        "消息：",
        "",
        _code(d["message_template"]["zh"]),
        "",
        f"**检查什么。** {guide['checks']['zh']}",
        "",
        f"**什么时候可能误报。** {guide['wrong']['zh']}",
        "",
        f"**怎么处理。** {guide['action']['zh']}",
        "",
        *_silence(d["rule"], "zh"),
        f"[All rules · 全部规则](README.md) · `paper-preflight explain {d['rule']}`",
        "",
    ]
    return "\n".join(lines)


def index() -> str:
    from paper_preflight.rules import RULES

    lines = [
        "# Rules · 规则",
        "",
        "<!-- Written by scripts/rule_docs.py: edit src/paper_preflight/rules.py and guides.py."
        " -->",
        "",
        "Every finding names its rule. `paper-preflight explain <RULE>` prints the same page in "
        "the terminal. Rules can be silenced for one entry with "
        '`% preflight: ignore[RULE] reason="..."` above it, or for the whole project in '
        "[the project's settings](../../README.md#project-settings).",
        "",
        "每条报告都注明了规则编号。`paper-preflight explain <规则>` 会在终端里显示同样的说明。"
        '可以在条目上方加 `% preflight: ignore[规则] reason="..."` 对单个条目消除某条规则，'
        "也可以在[项目设置](../../README.zh-CN.md#项目设置)中对整个项目关闭。",
        "",
    ]
    for prefix, title, title_zh in FAMILIES:
        rules = sorted((r for r in RULES.values() if r.id.startswith(prefix)), key=lambda r: r.id)
        lines += [
            f"## {title} · {title_zh}",
            "",
            "| Rule | Severity | Finding | 说明 |",
            "|---|---|---|---|",
        ]
        lines += [
            f"| [{r.id}]({r.id}.md) | {r.severity.value} | {r.summary.en} | {r.summary.zh} |"
            for r in rules
        ]
        lines.append("")
    return "\n".join(lines)


def pages() -> dict[Path, str]:
    from paper_preflight.rules import RULES

    out = {DOCS / "README.md": index()}
    for rule_id in RULES:
        out[DOCS / f"{rule_id}.md"] = page(rule_id)
    return out


def main() -> None:
    DOCS.mkdir(parents=True, exist_ok=True)
    wanted = pages()
    for stale in set(DOCS.glob("*.md")) - set(wanted):
        stale.unlink()
    for path, text in wanted.items():
        with path.open("w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
    print(f"{len(wanted)} pages in {DOCS.relative_to(ROOT)}", file=sys.stderr)


if __name__ == "__main__":
    main()
