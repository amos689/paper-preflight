"""Score paper-preflight on the HALLMARK benchmark (rpatrik96/hallmark, MIT; evals/datasets.lock).

Each benchmark entry is a BibTeX entry labelled VALID or HALLUCINATED with one of 14
hallucination types. HALLMARK evaluates three of them (merged citations, partial author lists,
arXiv version mismatches) separately as stress tests, and so do we.

A prediction is one of three outcomes, never a forced yes/no:

* ``flag``    — a finding from the chosen rule set (see :data:`MODES`) was raised;
* ``clean``   — a definite verdict without such a finding;
* ``abstain`` — ``cannot_determine``: the tool declined to judge (ADR-0002).

Precision is computed over flags; recall counts an abstention as a miss (conservative); coverage
is the share of entries that got a definite answer. Nothing here calls an LLM.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from paper_preflight.findings import Severity
from paper_preflight.verdict import Assessment, Verdict

Outcome = Literal["flag", "clean", "abstain"]

STRESS_TYPES = frozenset({"merged_citation", "partial_author_list", "arxiv_version_mismatch"})
TIERS = {
    "fabricated_doi": 1, "nonexistent_venue": 1, "placeholder_authors": 1, "future_date": 1,
    "chimeric_title": 2, "wrong_venue": 2, "swapped_authors": 2, "preprint_as_published": 2,
    "hybrid_fabrication": 2, "merged_citation": 2, "partial_author_list": 2,
    "near_miss_title": 3, "plausible_fabrication": 3, "arxiv_version_mismatch": 3,
}  # fmt: skip

# The development plan's two scoring modes. REF015 (published preprint), REF004/005 (retraction
# notices) and REF017 (identifier formatting) are advice about real works, not hallucinations.
FABRICATION_RULES = frozenset({"REF001", "REF002", "REF003", "REF010"})
ANY_ISSUE_RULES = FABRICATION_RULES | {"REF011", "REF012", "REF013", "REF014"}
MODES: dict[str, frozenset[str]] = {
    "fabrication": FABRICATION_RULES,
    "any_issue": ANY_ISSUE_RULES,
}


@dataclass(frozen=True)
class Example:
    key: str
    entry_type: str
    fields: Mapping[str, str]
    hallucinated: bool
    kind: str | None  # hallucination type; None for VALID entries
    tier: int | None

    @property
    def stress(self) -> bool:
        return self.kind in STRESS_TYPES


def load(path: Path) -> list[Example]:
    """Read a HALLMARK split (JSON lines), skipping the do-not-train canary entries."""
    examples: list[Example] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            key = str(row["bibtex_key"])
            if key.startswith("__canary__"):
                continue
            kind = row.get("hallucination_type")
            examples.append(
                Example(
                    key=key,
                    entry_type=str(row.get("bibtex_type") or "misc"),
                    fields={str(k).lower(): str(v) for k, v in (row.get("fields") or {}).items()},
                    hallucinated=row.get("label") == "HALLUCINATED",
                    kind=str(kind) if kind else None,
                    tier=TIERS.get(str(kind)) if kind else None,
                )
            )
    return examples


def _balanced(value: str) -> bool:
    depth = 0
    for char in value:
        depth += {"{": 1, "}": -1}.get(char, 0)
        if depth < 0:
            return False
    return depth == 0


def to_bibtex(example: Example) -> str:
    """The entry as BibTeX text, so it goes through the same parser as a user's .bib file."""
    lines = [f"@{example.entry_type}{{{example.key},"]
    for name, value in example.fields.items():
        text = re.sub(r"\s+", " ", value).strip()
        if not _balanced(text):
            text = text.replace("{", "").replace("}", "")
        lines.append(f"  {name} = {{{text}}},")
    lines.append("}")
    return "\n".join(lines) + "\n"


def predict(assessment: Assessment, rules: frozenset[str]) -> Outcome:
    flagged = any(
        f.rule_id in rules and f.severity is not Severity.INFO for f in assessment.findings
    )
    if flagged:
        return "flag"
    if assessment.verdict is Verdict.CANNOT_DETERMINE:
        return "abstain"
    return "clean"


@dataclass
class Counts:
    total: int = 0
    flag: int = 0
    clean: int = 0
    abstain: int = 0

    def add(self, outcome: Outcome) -> None:
        self.total += 1
        setattr(self, outcome, getattr(self, outcome) + 1)


@dataclass
class Scores:
    mode: str
    valid: Counts = field(default_factory=Counts)
    hallucinated: Counts = field(default_factory=Counts)  # main types only
    by_type: dict[str, Counts] = field(default_factory=dict)
    by_tier: dict[int, Counts] = field(default_factory=dict)
    stress: Counts = field(default_factory=Counts)

    @property
    def precision(self) -> float | None:
        flagged = self.hallucinated.flag + self.valid.flag
        return self.hallucinated.flag / flagged if flagged else None

    @property
    def recall(self) -> float | None:
        """Conservative: an abstention on a hallucinated entry counts as a miss."""
        total = self.hallucinated.total
        return self.hallucinated.flag / total if total else None

    @property
    def false_positive_rate(self) -> float | None:
        return self.valid.flag / self.valid.total if self.valid.total else None

    @property
    def coverage(self) -> float | None:
        total = self.valid.total + self.hallucinated.total
        decided = total - self.valid.abstain - self.hallucinated.abstain
        return decided / total if total else None

    @property
    def f1(self) -> float | None:
        p, r = self.precision, self.recall
        if p is None or r is None or p + r == 0:
            return None
        return 2 * p * r / (p + r)


def score(
    examples: Iterable[Example], outcomes: Mapping[str, Mapping[str, Outcome]]
) -> dict[str, Scores]:
    """``outcomes[mode][key]`` → scores per mode."""
    result = {mode: Scores(mode) for mode in outcomes}
    for example in examples:
        for mode, per_key in outcomes.items():
            outcome = per_key.get(example.key)
            if outcome is None:
                continue
            scores = result[mode]
            if not example.hallucinated:
                scores.valid.add(outcome)
                continue
            kind = example.kind or "unknown"
            scores.by_type.setdefault(kind, Counts()).add(outcome)
            if example.stress:
                scores.stress.add(outcome)
                continue
            scores.hallucinated.add(outcome)
            if example.tier is not None:
                scores.by_tier.setdefault(example.tier, Counts()).add(outcome)
    return result


def _pct(value: float | None) -> str:
    return "–" if value is None else f"{100 * value:.1f}%"


def _rate(counts: Counts, outcome: Outcome) -> str:
    return _pct(getattr(counts, outcome) / counts.total) if counts.total else "–"


def render_markdown(scores: Mapping[str, Scores], header: Mapping[str, str]) -> str:
    out = ["# HALLMARK evaluation", ""]
    out += [f"- **{name}:** {value}" for name, value in header.items()]
    out += ["", "## Summary (main types; stress types reported separately)", ""]
    out += ["| Mode | Precision | Recall | F1 | False-positive rate | Coverage |"]
    out += ["|---|---|---|---|---|---|"]
    for mode, s in scores.items():
        out.append(
            f"| {mode} | {_pct(s.precision)} | {_pct(s.recall)} | {_pct(s.f1)} "
            f"| {_pct(s.false_positive_rate)} | {_pct(s.coverage)} |"
        )
    for mode, s in scores.items():
        out += ["", f"## {mode}: outcomes by hallucination type", ""]
        out += [
            "For VALID entries a flag is a false positive; for the others, clean is a miss.",
            "",
        ]
        out += ["| Type | Tier | n | Flagged | Clean | Abstained |", "|---|---|---|---|---|---|"]
        valid = s.valid
        out.append(
            f"| VALID | – | {valid.total} | {_rate(valid, 'flag')} | {_rate(valid, 'clean')} "
            f"| {_rate(valid, 'abstain')} |"
        )
        for kind, counts in sorted(s.by_type.items(), key=lambda kv: (TIERS.get(kv[0], 9), kv[0])):
            label = f"{kind} (stress)" if kind in STRESS_TYPES else kind
            out.append(
                f"| {label} | {TIERS.get(kind, '–')} | {counts.total} | {_rate(counts, 'flag')} "
                f"| {_rate(counts, 'clean')} | {_rate(counts, 'abstain')} |"
            )
    return "\n".join(out) + "\n"


def summary_counts(outcomes: Mapping[str, Outcome]) -> dict[str, int]:
    return dict(Counter(outcomes.values()))
