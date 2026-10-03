# Releasing

Publishing a GitHub Release tagged `vX.Y.Z` runs [`release.yml`](../.github/workflows/release.yml):
it checks that the tag matches `__version__`, builds the sdist and wheel, smoke-tests the wheel
on the demo paper and uploads both to PyPI through
[trusted publishing](https://docs.pypi.org/trusted-publishers/). No token is stored anywhere,
and PyPI attaches [PEP 740](https://peps.python.org/pep-0740/) attestations to every file.

## One-time setup (maintainer, on pypi.org)

1. Sign in to PyPI with two-factor authentication on.
2. Before the first release, add a **pending publisher** under *Your projects → Publishing*
   (later releases reuse it):

   | Field | Value |
   |---|---|
   | PyPI project name | `paper-preflight` |
   | Owner | `amos689` |
   | Repository name | `paper-preflight` |
   | Workflow name | `release.yml` |
   | Environment name | `pypi` |

3. Optional: on GitHub, *Settings → Environments → pypi*, add yourself as a required reviewer so
   every upload waits for a click.

## Each release

1. Open a pull request that sets `__version__` in `src/paper_preflight/__init__.py`, turns the
   CHANGELOG's *Unreleased* heading into `## [X.Y.Z] - YYYY-MM-DD`, and updates the README's
   status note. Merge it when CI is green.
2. Publish the release from `main` (the notes can come from a file):

   ```bash
   gh release create vX.Y.Z --target main --title "paper-preflight X.Y.Z" --notes-file notes.md
   ```

3. Watch the *Release* workflow, then check <https://pypi.org/project/paper-preflight/> and
   `uvx paper-preflight --version`.

A release whose tag does not match `__version__` stops before anything is uploaded; fix the
version, delete the release and its tag, and publish again. PyPI never accepts the same version
twice, so a broken upload is fixed with a new patch version.

On PyPI the README's relative links point to GitHub (`hatch-fancy-pypi-readme` rewrites them
at build time).
