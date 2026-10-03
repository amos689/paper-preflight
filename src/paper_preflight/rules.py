"""Rule registry: IDs, default severities and bilingual message templates.

Rule IDs are stable public API (they appear in SARIF, suppressions and docs). Families:
CIT = citation keys and bibliography hygiene, TEX = LaTeX project structure,
REF = reference verification (see docs/adr/0002), RUN = run-level conditions, CFG = configuration.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from paper_preflight.findings import Finding, FixLevel, Location, Message, Severity


@dataclass(frozen=True)
class Rule:
    id: str
    name: str
    severity: Severity
    summary: Message
    template: Message  # str.format templates, filled with finding parameters
    fix: FixLevel | None = None


def _rule(
    rule_id: str,
    name: str,
    severity: Severity,
    summary: tuple[str, str],
    template: tuple[str, str],
    fix: FixLevel | None = None,
) -> Rule:
    return Rule(rule_id, name, severity, Message(*summary), Message(*template), fix)


E, W, I = Severity.ERROR, Severity.WARNING, Severity.INFO  # noqa: E741

RULES: dict[str, Rule] = {
    r.id: r
    for r in [
        _rule(
            "CIT001", "undefined-citation", E,
            ("Cited key is not defined", "被引用的键未定义"),
            ("Citation key '{key}' is not defined in any bibliography file ({count} use(s)).",
             "引用键 '{key}' 未在任何参考文献文件中定义（共被引用 {count} 次）。"),
        ),
        _rule(
            "CIT002", "duplicate-key", E,
            ("Entry key defined twice", "条目键重复定义"),
            ("Entry key '{key}' is already defined at line {first_line}; BibTeX ignores this one.",
             "条目键 '{key}' 已在第 {first_line} 行定义；BibTeX 会忽略这一条。"),
        ),
        _rule(
            "CIT003", "unused-entry", I,
            ("Entry is never cited", "条目未被引用"),
            ("Entry '{key}' is never cited.", "条目 '{key}' 从未被引用。"),
        ),
        _rule(
            "CIT004", "near-duplicate", W,
            ("Two entries look like the same work", "两个条目疑似同一篇文献"),
            ("Entries '{key}' and '{other}' look like the same work (same {reason}).",
             "条目 '{key}' 与 '{other}' 疑似同一篇文献（{reason_zh}相同）。"),
            FixLevel.SUGGESTION,
        ),
        _rule(
            "CIT005", "bibliography-missing", E,
            ("Bibliography file missing or unreadable", "参考文献文件缺失或无法读取"),
            ("Bibliography file '{path}' was not found or could not be read.",
             "找不到或无法读取参考文献文件 '{path}'。"),
        ),
        _rule(
            "CIT006", "missing-required-fields", I,
            ("Entry lacks required fields", "条目缺少必填字段"),
            ("Entry '{key}' (@{entry_type}) lacks required field(s): {fields}.",
             "条目 '{key}'（@{entry_type}）缺少必填字段：{fields}。"),
        ),
        _rule(
            "CIT007", "bibtex-syntax-error", E,
            ("BibTeX syntax error", "BibTeX 语法错误"),
            ("BibTeX syntax error; this entry is skipped: {detail}",
             "BibTeX 语法错误，该条目会被跳过：{detail}"),
        ),
        _rule(
            "CIT008", "duplicate-field", W,
            ("Field appears twice in an entry", "条目中字段重复"),
            ("Field '{field}' appears more than once in '{key}'; only the first value is used.",
             "条目 '{key}' 中字段 '{field}' 出现多次，只有第一个值生效。"),
        ),
        _rule(
            "TEX001", "missing-include", W,
            ("Included file not found", "找不到被包含的文件"),
            ("Included file '{name}' was not found; citations in it are not checked.",
             "找不到被包含的文件 '{name}'，其中的引用未被检查。"),
        ),
        _rule(
            "TEX002", "include-cycle", W,
            ("Include cycle", "文件循环包含"),
            ("'{name}' is included recursively; the cycle was skipped.",
             "'{name}' 被循环包含，已跳过该循环。"),
        ),
        _rule(
            "TEX003", "remote-bibliography", I,
            ("Remote bibliography not checked", "远程参考文献未检查"),
            ("Remote bibliography resource '{name}' is not checked.",
             "远程参考文献资源 '{name}' 不在检查范围内。"),
        ),
        _rule(
            "TEX004", "unreadable-source", W,
            ("Source file could not be read", "源文件无法读取"),
            ("Source file could not be read: {detail}", "源文件无法读取：{detail}"),
        ),
        _rule(
            "CFG001", "unused-suppression", I,
            ("Suppression comment had no effect", "抑制注释未生效"),
            ("Suppression of {rule} on '{key}' had no effect.",
             "对 '{key}' 的 {rule} 抑制没有起作用。"),
            FixLevel.SAFE,
        ),
        _rule(
            "REF017", "malformed-identifier", W,
            ("Identifier written incorrectly", "标识符写法错误"),
            ("The {field} of '{key}' {problem}: '{value}'. Write it as: {suggestion}",
             "条目 '{key}' 的 {field} {problem_zh}：'{value}'。应写为：{suggestion}"),
            FixLevel.SAFE,
        ),
    ]
}  # fmt: skip


class _SafeDict(dict[str, Any]):
    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def make_finding(
    rule_id: str,
    location: Location | None,
    *,
    key: str | None = None,
    field: str | None = None,
    related: tuple[Location, ...] = (),
    severity: Severity | None = None,
    **params: Any,
) -> Finding:
    rule = RULES[rule_id]
    values = _SafeDict({"key": key, "field": field, **params})
    message = Message(rule.template.en.format_map(values), rule.template.zh.format_map(values))
    data = {k: v for k, v in params.items() if isinstance(v, (str, int, float, bool, list))}
    return Finding(
        rule_id=rule_id,
        severity=severity or rule.severity,
        message=message,
        location=location,
        key=key,
        field=field,
        related=related,
        data=data,
    )
