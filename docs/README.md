# paper-preflight user guide

The [README](../README.md) is the tour; these pages are the reference. 中文用户请看
[README.zh-CN.md](../README.zh-CN.md)，规则说明页为中英双语。

## Install

paper-preflight needs Python 3.11 or later. With [uv](https://docs.astral.sh/uv/) nothing needs
installing:

```bash
uvx paper-preflight check path/to/paper
```

Or install it for good:

```bash
pip install paper-preflight
```

| Extra | Adds | Install |
|---|---|---|
| `pdf` | Reading the reference list of a PDF | `pip install "paper-preflight[pdf]"` |
| `mcp` | The MCP server for coding agents | `pip install "paper-preflight[mcp]"` |
| `support` | The experimental evidence finder, with its local model | `pip install "paper-preflight[support]"` |

`paper-preflight doctor` tells which optional credentials are set and whether each source
answers right now.

## Use it

| Task | Page |
|---|---|
| Check a LaTeX project, a Word, Markdown or Typst manuscript, a bibliography, a PDF or an arXiv paper | [Inputs](inputs.md) |
| Understand a finding, and what to do about it | [Rules](rules/README.md) |
| A finding you believe is wrong | [When a finding is wrong](false-positives.md) |
| Silence findings, settings for a project, credentials, the cache, output formats and exit codes | [Configuration](configuration.md) |
| Get a correct BibTeX entry, or fix the bibliography from the records | README: [fetch](../README.md#fetch-verified-bibtex), [fix](../README.md#fix-the-bibliography) |
| Check on every push | [GitHub Action](github-action.md) |
| Check on every commit | [pre-commit](pre-commit.md) |
| Let a coding agent check the references | [MCP server and plugin](mcp.md) |
| Call it from Python | [Python API](python-api.md) |
| Read the JSON report from a script | [JSON Schema](schema/check-report.schema.json) |
| Know what is asked of which database, and how politely | [Sources](sources.md) |
| Know what stays compatible between versions | [Compatibility](stability.md) |

## How it decides

Every reference gets one verdict:

| Verdict | Means |
|---|---|
| verified | A record of the work was found and agrees with the entry (title, authors, year) |
| metadata mismatch | The work was found, but the entry says something else about it (findings name the field) |
| identifier conflict | The entry's DOI or arXiv ID belongs to another work |
| not found | Every source that could know the work answered, and none has it |
| cannot determine | It could not be decided, and the report says why |

A finding is reported only when a record (or every source answering "no") backs it; an outage,
a rate limit or a work the indexes are known to miss leads to "cannot determine", never to "not
found". No language model takes part in any verdict. The reasoning is recorded in the
[architecture decisions](adr/README.md).

## Contribute

Building from source, the ground rules and how to report a false positive:
[CONTRIBUTING.md](../CONTRIBUTING.md). Adding a source: [Sources](sources.md#adding-a-source).
Progress, in Chinese: [PROGRESS.md](PROGRESS.md).
