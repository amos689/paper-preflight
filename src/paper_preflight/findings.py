"""Findings: the single model every check produces and every reporter consumes."""

from __future__ import annotations

import contextlib
import hashlib
from dataclasses import dataclass
from dataclasses import field as dataclass_field
from enum import StrEnum
from pathlib import Path
from typing import Any


class Severity(StrEnum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"

    @property
    def rank(self) -> int:
        return {"error": 3, "warning": 2, "info": 1}[self.value]


class FixLevel(StrEnum):
    SAFE = "safe"
    UNSAFE = "unsafe"
    SUGGESTION = "suggestion"


@dataclass(frozen=True)
class Message:
    en: str
    zh: str

    def get(self, lang: str) -> str:
        return self.zh if lang.startswith("zh") else self.en


@dataclass(frozen=True)
class Location:
    file: Path
    line: int  # 1-based
    column: int = 1  # 1-based, Unicode code points

    def display(self, base: Path | None = None) -> str:
        path = self.file
        if base is not None:
            with contextlib.suppress(ValueError):
                path = self.file.relative_to(base)
        return f"{path.as_posix()}:{self.line}"


@dataclass(frozen=True)
class Finding:
    rule_id: str
    severity: Severity
    message: Message
    location: Location | None
    key: str | None = None  # BibTeX key, when the finding is about an entry
    field: str | None = None  # BibTeX field, when the finding is about one field
    related: tuple[Location, ...] = ()
    data: dict[str, Any] = dataclass_field(default_factory=dict, compare=False, hash=False)

    @property
    def fingerprint(self) -> str:
        """Stable across line moves: derived from rule, key, field and the detail payload."""
        detail = self.data.get("detail", "")
        basis = "|".join([self.rule_id, self.key or "", self.field or "", str(detail)])
        if self.key is None and self.location is not None:
            basis += "|" + self.location.file.name
        return "f-" + hashlib.sha1(basis.encode("utf-8")).hexdigest()[:10]

    def to_dict(self, base: Path | None = None) -> dict[str, Any]:
        location: dict[str, Any] | None = None
        if self.location is not None:
            location = {
                "file": self._rel(self.location.file, base),
                "line": self.location.line,
                "column": self.location.column,
            }
        return {
            "id": self.fingerprint,
            "rule": self.rule_id,
            "severity": self.severity.value,
            "key": self.key,
            "field": self.field,
            "location": location,
            "related": [
                {"file": self._rel(r.file, base), "line": r.line, "column": r.column}
                for r in self.related
            ],
            "message": {"en": self.message.en, "zh": self.message.zh},
            "data": self.data,
        }

    @staticmethod
    def _rel(path: Path, base: Path | None) -> str:
        if base is not None:
            try:
                return path.relative_to(base).as_posix()
            except ValueError:
                pass
        return path.as_posix()


def sort_findings(findings: list[Finding]) -> list[Finding]:
    """Most severe first, then by file and line."""
    return sorted(
        findings,
        key=lambda f: (
            -f.severity.rank,
            f.location.file.as_posix() if f.location else "",
            f.location.line if f.location else 0,
            f.rule_id,
        ),
    )
