# Python API

`paper_preflight.check_paper()` runs the same checks as `paper-preflight check` and returns
plain, frozen dataclasses: for scripts, notebooks, other tools and agents that call Python.

```python
import paper_preflight

report = paper_preflight.check_paper("paper/")  # a LaTeX project, a manuscript or a .bib

report.complete  # False when a source needed did not answer (exit code 2)
report.verification  # "online" | "offline" | "skipped"
report.blocking("error")  # True when the CLI would exit with 1 at --fail-on error

for ref in report.references:  # one per checked reference
    print(ref.key, ref.verdict, ref.reasons)
    if ref.matched:  # the record it was compared with
        print("  ", ref.matched.source, ref.matched.id, ref.matched.doi)
    for finding in ref.findings:
        print("  ", finding.rule, finding.severity, finding.message)

for finding in report.findings:  # every finding, errors first
    print(finding.file, finding.line, finding.rule, finding.message)

report.to_dict()  # the JSON report, as --format json writes it
```

## Arguments

| Argument | Default | Meaning |
|---|---|---|
| `path` | | A LaTeX project folder or main `.tex`, a Markdown/Quarto/Typst/Word manuscript, or a reference list (`.bib`, `.bbl`, CSL-JSON, RIS, YAML, plain text, PDF) |
| `online` | `True` | Verify references against the sources; `False` runs only the offline citation rules |
| `cache` | `"default"` | The answer cache: `"default"` is the CLI's, a path names another, `None` keeps one in memory for this call |
| `settings` | `"find"` | The project settings: `"find"` looks for `paper-preflight.toml` or `[tool.paper-preflight]` as the CLI does, a path names a file, `None` uses none |
| `main` | `None` | The main `.tex` file, when it cannot be found |
| `extra_bib` | `()` | More `.bib` files to read |
| `language` | `"en"` | Messages in English or Chinese (`"zh"`) |

Credentials come from the environment, as for the CLI (`PAPER_PREFLIGHT_EMAIL`, `S2_API_KEY`,
`GITHUB_TOKEN`, ...). A mistake in the settings file raises `paper_preflight.config.ConfigError`;
a project that cannot be read raises `paper_preflight.tex.project.ProjectError`.

## Results

| Class | Fields |
|---|---|
| `Report` | `path`, `complete`, `verification`, `references`, `findings`, `result` (the internal result, not a stable API), `blocking(fail_on)`, `to_dict()` |
| `Reference` | `key`, `verdict` (`verified`, `metadata_mismatch`, `identifier_conflict`, `not_found`, `cannot_determine`), `reasons`, `matched`, `findings` |
| `MatchedRecord` | `source`, `id`, `title`, `year`, `venue`, `doi` |
| `Finding` | `rule`, `severity` (`error`, `warning`, `info`), `message`, `key`, `field`, `file`, `line`, `id` (stable across runs) |

Enumerations are strings, as in the JSON report. Like the report, these classes may gain fields;
none is removed or changes meaning without a new major version. `paper-preflight explain <rule>`
describes each rule.
