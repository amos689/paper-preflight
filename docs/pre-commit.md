# pre-commit hooks

Check a LaTeX project on every commit with [pre-commit](https://pre-commit.com). Add this to the
project's `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/amos689/paper-preflight
    rev: v0.7.0  # a release tag; `pre-commit autoupdate` moves it to the latest
    hooks:
      - id: paper-preflight-offline
```

| Hook | What it does | When to use it |
|---|---|---|
| `paper-preflight-offline` | Checks citation keys and the bibliography, and reports the reference verdicts already in the local cache. It never touches the network and takes seconds. References without a cached answer are counted, not failed. | on every commit |
| `paper-preflight` | Verifies every cited reference against the scholarly sources. The first run of a paper can take a minute. | before submitting, or in CI |

- **When the hooks run.** They check the whole project in the repository root once per commit,
  whenever a `.tex` or `.bib` file changed.
- **Pointing at the paper.** Use `args` to name the main file or extra bibliographies:

  ```yaml
      - id: paper-preflight-offline
        args: [--main, paper/main.tex]
  ```

- **Exit codes.** A commit is blocked by error findings (exit code 1). The online hook also
  blocks when a source was unavailable and the run is incomplete (exit code 2), because then the
  references cannot be called clean. `--fail-on warning` makes warnings block too; `--fail-on
  never` turns the hook into a report.
