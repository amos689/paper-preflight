# Compatibility

From 1.0, paper-preflight follows [Semantic Versioning](https://semver.org/): what this page
calls stable changes incompatibly only in a new major version, and the
[changelog](../CHANGELOG.md) names every change. Until 1.0, minor versions may still change it,
and the changelog says so.

## Stable

| What | The promise |
|---|---|
| Rule IDs (`REF003`, `CIT001`, ...) and their names | Never reused for another check; a retired rule's ID is not given to a new one. Suppression comments and settings keep working |
| Exit codes 0–4 | Their meanings stay as [documented](configuration.md#exit-codes) |
| The JSON report | Follows [its schema](schema/check-report.schema.json): fields may be added; none is removed, renamed or changes meaning without a new major `schema_version` |
| SARIF output | Valid SARIF 2.1.0, one rule per rule ID |
| Command-line commands and options | Kept; one is removed or changes meaning only in a major version, after a release that warns about it |
| Settings keys (`paper-preflight.toml`, `[tool.paper-preflight]`) and suppression comments | Kept; an unknown key stays an error |
| The Python API (`paper_preflight.check_paper` and the dataclasses it returns) | Names and fields kept; new optional arguments and fields may be added |
| The MCP tools' names and arguments | Kept; new optional arguments may be added |

## Not stable

- **Verdicts and findings.** They improve: a new source may verify what was undecided, a fixed
  false alarm disappears, a new rule reports what went unseen. The same paper can get a different
  report from a newer version, or from the same version on a later day, when the records change.
- **Wording.** Messages, the text report's layout, and `explain`'s text may be reworded.
- **Severities** of individual rules may be adjusted, and new rules may be added at any severity;
  the changelog names every rule that becomes an error. The settings' `severity` table and
  `fail-on` decide what blocks a build.
- **The cache's format.** An old cache may be discarded and rebuilt.
- **Internal modules.** Anything not listed above, including every module other than
  `paper_preflight`'s top-level API, may change in any release.
