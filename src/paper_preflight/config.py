"""Project settings: ``paper-preflight.toml``, or ``[tool.paper-preflight]`` in ``pyproject.toml``.

    # paper-preflight.toml, next to the paper or in a folder above it
    ignore-rules = ["REF016"]                   # never report these rules
    ignore-keys = ["smith2020", "draft*"]       # nor anything about these entries
    severity = { REF015 = "info", CIT003 = "warning" }
    disable-sources = ["s2"]                    # optional sources only
    fail-on = "warning"                         # as --fail-on; the command line wins

The file is looked for from the checked path upwards, stopping at a repository's root (a folder
with ``.git``). The registries that judge a reference (Crossref, dblp, arXiv, DataCite, PubMed,
OpenAlex, doi.org) cannot be turned off: without them nothing could be called verified or not
found. Mistakes in the file are errors, never silently ignored.
"""

from __future__ import annotations

import fnmatch
import tomllib
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

from paper_preflight.findings import Finding, Severity
from paper_preflight.rules import RULES

CONFIG_FILE = "paper-preflight.toml"
OPTIONAL_SOURCES = frozenset({"s2", "openlibrary", "github", "pypi", "cran", "web", "wayback"})
FAIL_ON = ("error", "warning", "never")
_KEYS = frozenset({"ignore-rules", "ignore-keys", "severity", "disable-sources", "fail-on"})


class ConfigError(ValueError):
    """A settings file that cannot be read as written."""


@dataclass(frozen=True)
class Config:
    path: Path | None = None
    ignore_rules: frozenset[str] = frozenset()
    ignore_keys: tuple[str, ...] = ()  # names or glob patterns ("draft*")
    severity: Mapping[str, Severity] = field(default_factory=dict)
    disable_sources: frozenset[str] = frozenset()
    fail_on: str | None = None

    def ignores(self, finding: Finding) -> bool:
        if finding.rule_id in self.ignore_rules:
            return True
        key = finding.key
        return key is not None and any(fnmatch.fnmatchcase(key, p) for p in self.ignore_keys)

    def apply(self, findings: Iterable[Finding]) -> list[Finding]:
        """The findings left once ignored ones are dropped, with severities as configured."""
        kept = []
        for finding in findings:
            if self.ignores(finding):
                continue
            severity = self.severity.get(finding.rule_id)
            kept.append(replace(finding, severity=severity) if severity else finding)
        return kept


def find_config(start: Path) -> Path | None:
    """The settings file for a checked path: the nearest ``paper-preflight.toml``, or
    ``pyproject.toml`` with a ``[tool.paper-preflight]`` table, up to a repository's root."""
    folder = start.resolve()
    if not folder.is_dir():
        folder = folder.parent
    for current in (folder, *folder.parents):
        own = current / CONFIG_FILE
        if own.is_file():
            return own
        project = current / "pyproject.toml"
        if project.is_file() and "paper-preflight" in _tool_tables(project):
            return project
        if (current / ".git").exists():
            return None
    return None


def _tool_tables(path: Path) -> Mapping[str, Any]:
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError):
        return {}
    tool = data.get("tool")
    return tool if isinstance(tool, dict) else {}


def load_config(path: Path) -> Config:
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError) as exc:
        raise ConfigError(f"{path}: cannot be read ({exc})") from exc
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"{path}: not valid TOML ({exc})") from exc
    if path.name == "pyproject.toml":
        data = (data.get("tool") or {}).get("paper-preflight") or {}
    if not isinstance(data, dict):
        raise ConfigError(f"{path}: the settings must be a table")
    unknown = sorted(set(data) - _KEYS)
    if unknown:
        known = ", ".join(sorted(_KEYS))
        raise ConfigError(f"{path}: unknown setting(s) {', '.join(unknown)} (known: {known})")

    def names(key: str) -> list[str]:
        value = data.get(key, [])
        if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
            raise ConfigError(f"{path}: {key} must be a list of strings")
        return value

    rules = [r.upper() for r in names("ignore-rules")]
    _known_rules(path, "ignore-rules", rules)
    severity_table = data.get("severity", {})
    if not isinstance(severity_table, dict):
        raise ConfigError(f'{path}: severity must be a table, e.g. {{ REF015 = "info" }}')
    severity: dict[str, Severity] = {}
    for rule, level in severity_table.items():
        _known_rules(path, "severity", [rule.upper()])
        if level not in {s.value for s in Severity}:
            raise ConfigError(f"{path}: severity of {rule} must be error, warning or info")
        severity[rule.upper()] = Severity(level)
    sources = [s.lower() for s in names("disable-sources")]
    fixed = sorted(set(sources) - OPTIONAL_SOURCES)
    if fixed:
        optional = ", ".join(sorted(OPTIONAL_SOURCES))
        raise ConfigError(
            f"{path}: {', '.join(fixed)} cannot be turned off; the optional sources are {optional}"
        )
    fail_on = data.get("fail-on")
    if fail_on is not None and fail_on not in FAIL_ON:
        raise ConfigError(f"{path}: fail-on must be error, warning or never")
    return Config(
        path=path,
        ignore_rules=frozenset(rules),
        ignore_keys=tuple(names("ignore-keys")),
        severity=severity,
        disable_sources=frozenset(sources),
        fail_on=fail_on,
    )


def _known_rules(path: Path, setting: str, rules: list[str]) -> None:
    unknown = [r for r in rules if r not in RULES]
    if unknown:
        raise ConfigError(
            f"{path}: {setting} names unknown rule(s) {', '.join(unknown)} "
            "(paper-preflight explain lists them)"
        )
