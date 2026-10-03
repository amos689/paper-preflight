# GitHub Action

Check a paper's references on every push or pull request. The action lives in this repository:

```yaml
name: References
on: [push, pull_request]

jobs:
  references:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      security-events: write  # only needed for the SARIF upload below
    steps:
      - uses: actions/checkout@v7
      - id: refs
        uses: amos689/paper-preflight@main  # pin a release tag once one is published
        env:  # optional, from repository secrets; values are never printed
          PAPER_PREFLIGHT_EMAIL: ${{ secrets.PAPER_PREFLIGHT_EMAIL }}
        with:
          path: paper  # the project directory, main .tex file or .bib file
      - if: always()
        uses: github/codeql-action/upload-sarif@v4
        with:
          sarif_file: ${{ steps.refs.outputs.sarif }}
```

## Inputs

| Input | Default | Meaning |
|---|---|---|
| `path` | `.` | Project directory, main `.tex` file, or a `.bib` file |
| `fail-on` | `error` | Lowest severity that fails the step: `error`, `warning` or `never` |
| `offline` | `false` | Use only answers already in the cache |
| `sarif` | `paper-preflight.sarif` | Where to write the SARIF report; empty to skip |
| `lang` | `en` | Message language: `en` or `zh` |

Outputs: `sarif` (the report's path) and `exit-code`:

| Code | Meaning |
|---|---|
| 0 | Clean |
| 1 | Blocking findings |
| 2 | Incomplete run: a source was unavailable, so the paper cannot be called clean |
| 3 | Usage error |

## Behaviour

- **Report.** The human-readable report goes to the job summary, and the findings can show up
  as code-scanning alerts on the `.bib` lines through the SARIF upload.
- **Caching.** Answers are cached per bibliography (`actions/cache`, keyed by the `.bib` files),
  so re-runs are fast and the scholarly sources see fewer requests.
- **Installation.** The action builds paper-preflight from its own checkout; no PyPI release is
  needed.
