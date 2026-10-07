"""Rule registry: IDs, default severities and bilingual message templates.

Rule IDs are stable public API (they appear in SARIF, suppressions and docs). Families:
CIT = citation keys and bibliography hygiene, TEX = LaTeX project structure,
REF = reference verification (see docs/adr/0002), RUN = run-level conditions, CFG = configuration.
"""

from __future__ import annotations

import re
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
        # ---- reference verification (docs/adr/0002); wording stays neutral by design
        _rule(
            "REF001", "identifier-conflict", E,
            ("Identifier points to a different work", "标识符指向另一篇作品"),
            ("The {field} of '{key}' ({identifier}) resolves to a different work in {source}: "
             "\"{found_title}\" ({found_authors}, {found_year}).",
             "条目 '{key}' 的 {field}（{identifier}）在 {source} 中指向另一篇作品："
             "\"{found_title}\"（{found_authors}，{found_year}）。"),
            FixLevel.UNSAFE,
        ),
        _rule(
            "REF002", "identifier-not-found", E,
            ("Identifier does not exist", "标识符不存在"),
            ("The {field} of '{key}' ({identifier}) does not exist: "
             "{authority} has no record of it.",
             "条目 '{key}' 的 {field}（{identifier}）不存在：{authority} 没有该标识符的记录。"),
        ),
        _rule(
            "REF003", "not-found", E,
            ("Reference not found in any source", "所有来源均未找到该文献"),
            ("'{key}' was not found in {sources}, and every source responded. "
             "Check that the work exists and that its title is correct.",
             "在 {sources_zh} 中均未找到 '{key}'，且所有来源都已正常应答。"
             "请确认该作品确实存在、标题无误。"),
        ),
        _rule(
            "REF004", "retracted", E,
            ("Cited work has been retracted", "被引作品已撤稿"),
            ("'{key}' has been {notice} (reported by {sources}). "
             "Cite it only if the text discusses the retraction.",
             "'{key}' 已{notice_zh}（依据：{sources_zh}）。"
             "除非正文讨论的就是撤稿本身，否则不应引用。"),
        ),
        _rule(
            "REF005", "concern-or-correction", W,
            ("Expression of concern or correction", "关注声明或更正"),
            ("'{key}' has {notice} (reported by {sources}).",
             "'{key}' 有{notice_zh}（依据：{sources_zh}）。"),
        ),
        _rule(
            "REF010", "authors-disjoint", E,
            ("Author list is entirely different", "作者列表完全不同"),
            ("None of the authors of '{key}' appear on the matching record in {source} "
             "({found_authors}).",
             "条目 '{key}' 的作者无一出现在 {source} 的匹配记录中（记录作者：{found_authors}）。"),
            FixLevel.UNSAFE,
        ),
        _rule(
            "REF011", "authors-differ", W,
            ("Author list differs", "作者列表部分不同"),
            ("The authors of '{key}' differ from {source}: {detail}.",
             "条目 '{key}' 的作者与 {source} 的记录不一致：{detail_zh}。"),
            FixLevel.UNSAFE,
        ),
        _rule(
            "REF012", "title-differs", W,
            ("Title differs from the record", "标题与记录不符"),
            ("The title of '{key}' differs from {source}: \"{found_title}\" ({difference}).",
             "条目 '{key}' 的标题与 {source} 的记录不符：\"{found_title}\"（{difference_zh}）。"),
            FixLevel.UNSAFE,
        ),
        _rule(
            "REF013", "year-differs", W,
            ("Year differs from the record", "年份与记录不符"),
            ("'{key}' gives the year {year}, but {source} records {found_years}.",
             "条目 '{key}' 的年份是 {year}，但 {source} 记录为 {found_years}。"),
            FixLevel.UNSAFE,
        ),
        _rule(
            "REF014", "venue-differs", W,
            ("Venue differs from the record", "发表场所与记录不符"),
            ("'{key}' names {venue} as the venue, but {source} records {found_venue}.",
             "条目 '{key}' 写的发表场所是 {venue}，但 {source} 记录为 {found_venue}。"),
            FixLevel.UNSAFE,
        ),
        _rule(
            "REF016", "identifier-available", I,
            ("A DOI can be added", "可以补充 DOI"),
            ("'{key}' has no DOI; {source} records {doi} for it. Adding it makes the reference "
             "unambiguous.",
             "条目 '{key}' 没有 DOI；{source} 记录的 DOI 是 {doi}。"
             "补上它可以让这条引用不再有歧义。"),
            FixLevel.SAFE,
        ),
        _rule(
            "REF015", "preprint-published", W,
            ("Preprint has been formally published", "预印本已正式发表"),
            ("'{key}' cites a preprint that has been published in {found_venue} "
             "({found_year}){doi_note}. Cite the published version and keep the eprint field.",
             "'{key}' 引用的预印本已正式发表于 {found_venue}（{found_year}）{doi_note_zh}。"
             "建议改引正式版本，并保留 eprint 字段。"),
            FixLevel.SUGGESTION,
        ),
        _rule(
            "REF018", "arxiv-withdrawn", W,
            ("arXiv preprint withdrawn", "arXiv 预印本已撤回"),
            ("The arXiv preprint cited by '{key}' ({identifier}) has been withdrawn.",
             "'{key}' 引用的 arXiv 预印本（{identifier}）已被撤回。"),
        ),
        _rule(
            "REF090", "cannot-determine", I,
            ("Reference could not be verified", "无法核实该文献"),
            ("'{key}' could not be verified: {reasons_text}.",
             "无法核实 '{key}'：{reasons_text_zh}。"),
        ),
        _rule(
            "RUN001", "run-incomplete", W,
            ("Run incomplete: some sources were unavailable", "运行不完整：部分来源不可用"),
            ("{count} reference(s) could not be fully checked because these sources were "
             "unavailable: {sources}. Results may change when you re-run later.",
             "有 {count} 条文献未能完整核查，因为以下来源不可用：{sources}。"
             "稍后重新运行，结果可能会变化。"),
        ),
        _rule(
            "RUN002", "checked-through-substitute", I,
            ("Checked through a substitute source", "已改用替代来源核查"),
            ("{count} reference(s) were checked through {substitutes} because {sources} did not "
             "answer. What only {sources} knows (withdrawn papers, titles of earlier versions) was "
             "not checked; re-run later for a full check.",
             "有 {count} 条文献因 {sources} 未应答，改用 {substitutes} 核查。只有 {sources} 掌握的"
             "信息（论文是否撤回、早期版本的标题）这次未能核查；稍后重新运行可完整核查。"),
        ),
    ]
}  # fmt: skip


DOCS_URL = "https://github.com/amos689/paper-preflight"


def describe(rule_id: str) -> dict[str, Any] | None:
    """A rule as data, for `explain` and the MCP server; None when the ID is unknown."""
    rule = RULES.get(rule_id.strip().upper())
    if rule is None:
        return None
    return {
        "rule": rule.id,
        "name": rule.name,
        "severity": rule.severity.value,
        "summary": {"en": rule.summary.en, "zh": rule.summary.zh},
        # placeholders read the same in both languages ({sources}, not the internal {sources_zh})
        "message_template": {
            "en": rule.template.en,
            "zh": re.sub(r"\{(\w+?)_zh\}", r"{\1}", rule.template.zh),
        },
        "fix": rule.fix.value if rule.fix else None,
        "docs": DOCS_URL,
    }


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
