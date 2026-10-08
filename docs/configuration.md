# Configuration

Everything works without configuration. This page lists what can be set: per entry, per
project, per run and per machine.

## Silence a finding for one entry

After checking a finding, put a comment directly above the entry:

```bibtex
% preflight: ignore[REF003] reason="internal technical report, not indexed anywhere"
@techreport{lab2024internal,
  ...
}
```

- Several rules are separated by commas: `ignore[REF011, REF013]`. The reason is optional,
  for whoever reads the file next.
- The verdict stays in the JSON report; only the finding is dropped.
- A comment that silenced nothing is reported as CFG001 (an info), so stale comments do not pile
  up. Reference rules are judged only after a complete online run, since offline answers and
  outages may leave them unrun.
- Findings not tied to an entry (TEX, RUN, CIT001, CIT005, CIT007) cannot be silenced this way;
  use the project's settings.

## Project settings

Put the settings in `paper-preflight.toml` next to the paper, or in a folder above it up to the
repository's root (the folder with `.git`), or in `[tool.paper-preflight]` of
`pyproject.toml`:

```toml
ignore-rules = ["CIT003"]                     # never report these rules
ignore-keys = ["internal2024*", "draft"]      # nor anything about these entries (globs allowed)
severity = { REF015 = "info", CIT006 = "warning" }
disable-sources = ["s2", "web"]               # optional sources only
fail-on = "warning"                           # as --fail-on; the command line wins
```

| Setting | Values |
|---|---|
| `ignore-rules` | Rule IDs, see [the rules](rules/README.md) |
| `ignore-keys` | Entry keys or glob patterns (`*`, `?`, `[...]`) |
| `severity` | A table of rule ID to `"error"`, `"warning"` or `"info"` |
| `disable-sources` | `s2`, `openlibrary`, `github`, `pypi`, `cran`, `web`, `wayback` |
| `fail-on` | `"error"` (the default), `"warning"` or `"never"` |

- `check --config <path>` names the file instead of looking for it.
- The registries that judge a reference (Crossref, dblp, arXiv, DataCite, PubMed, OpenAlex,
  doi.org) cannot be turned off: without them nothing could be called verified or not found.
- A mistake in the file (an unknown setting, rule, severity or source) is an error, exit code 3,
  never silently ignored.
- The JSON report names the file in `run.notes`. The MCP server, the GitHub Action, pre-commit
  and the Python API read the same file.

## Options of `check`

| Option | Effect |
|---|---|
| `--main <file>` | The main `.tex` file, when it cannot be told |
| `--bib <file>` | A bibliography the project does not name (repeatable) |
| `--cite-command <name>` | A citation macro of your own (repeatable) |
| `--format text\|json\|sarif` | The report's format; `--output <file>` writes it to a file |
| `--fail-on error\|warning\|never` | The lowest severity that makes the exit code 1 |
| `--lang auto\|en\|zh` | The language of messages; `auto` follows `PAPER_PREFLIGHT_LANG`, then the system's locale |
| `--hide-info` | Leave infos out of the text report |
| `--details` | List every finding: by default, a suggestion that applies to many entries (published preprints, available DOIs) is one line |
| `--max-findings <n>` | At most n findings in the JSON report |
| `--offline` | No network: verify from cached answers only |
| `--refresh` | Ask every source again instead of using cached answers |
| `--recheck` | Search again now for references found too new to be indexed (otherwise once a day) |
| `--config <file>` | The settings file |

## Exit codes

| Code | Meaning |
|---|---|
| 0 | Nothing at or above `--fail-on` was found |
| 1 | Blocking findings |
| 2 | No blocking findings, but a source was unavailable and nothing could answer in its place: the paper cannot be called clean yet (RUN001) |
| 3 | Usage error, including a mistake in the settings file |
| 4 | Internal error (please report it; `PAPER_PREFLIGHT_DEBUG=1` shows the traceback) |

## Output formats

- **text**, the default, for people: findings grouped by severity, then a summary.
- **json**, for scripts: the verdict of every reference with the record it was compared to, and
  every finding. It follows [a JSON Schema](schema/check-report.schema.json); fields may be
  added, but none is removed or changes meaning without a new `schema_version`.
- **sarif**, for code scanning: GitHub shows the findings as alerts on the `.bib` lines, with
  each rule's guide.

## Environment variables

Credentials are optional, free, and never printed, logged or sent anywhere but their own
service. `paper-preflight doctor` shows which are set.

| Variable | Effect |
|---|---|
| `PAPER_PREFLIGHT_EMAIL` | A contact address: Crossref's polite pool (faster, more reliable), and the identified requests OpenAlex and Open Library ask for |
| `OPENALEX_API_KEY` | A larger OpenAlex budget, for retraction checks and its title search (which costs ten times more) |
| `S2_API_KEY` | Semantic Scholar as a rescue source for references nobody else found |
| `GITHUB_TOKEN` | GitHub's larger budget (5,000 requests an hour instead of 60) for references to repositories |
| `NCBI_API_KEY` | PubMed's larger budget (10 requests a second instead of 3) for PMIDs and PMCIDs |
| `PAPER_PREFLIGHT_CACHE_DIR` | Where the cache lives (see below) |
| `PAPER_PREFLIGHT_LANG` | `zh` or `en`, for `--lang auto` |
| `PAPER_PREFLIGHT_DEBUG` | Show the traceback of an internal error |

## The cache

Every answer is cached in one SQLite file, `cache.sqlite3`, in the user cache folder
(`~/.cache/paper-preflight` on Linux, `~/Library/Caches/paper-preflight` on macOS,
`%LOCALAPPDATA%\paper-preflight\Cache` on Windows) or in `PAPER_PREFLIGHT_CACHE_DIR`.

| Answer | Kept for |
|---|---|
| A record found | 60 days |
| A search's results | 14 days |
| Retraction and correction status | 7 days |
| "No such record" | 2 days |
| Which registry owns a DOI | 365 days |

- Re-runs are fast and ask the sources only for what changed or expired.
- `--offline` uses the cache alone: references without a cached answer are "cannot determine".
- `--refresh` asks everything again, after a record was corrected, say.
- A reference too new to be indexed is remembered and searched for again once a day, or at once
  with `--recheck`.
- Answers from Semantic Scholar are marked as not to be exported, as its licence asks.
- Deleting the file is always safe.
