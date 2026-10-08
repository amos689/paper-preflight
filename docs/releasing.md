# Releasing

Publishing a GitHub Release tagged `vX.Y.Z` runs [`release.yml`](../.github/workflows/release.yml):
it checks that the tag matches `__version__`, builds the sdist and wheel, smoke-tests the wheel
on the demo paper and uploads both to PyPI through
[trusted publishing](https://docs.pypi.org/trusted-publishers/), then publishes `server.json` to
the [MCP Registry](https://github.com/modelcontextprotocol/registry) with GitHub's OIDC token.
No token is stored anywhere, and PyPI attaches [PEP 740](https://peps.python.org/pep-0740/)
attestations to every file.

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

1. Open a pull request made with `uv run python scripts/bump_version.py X.Y.Z`: it sets
   `__version__`, the three versions in `server.json` and the Space's pin (a test keeps them
   equal), and turns the CHANGELOG's *Unreleased* section into `## [X.Y.Z] - YYYY-MM-DD` with
   its compare link. Update the README's numbers and roadmap by hand. Merge it when CI is green.
2. Publish the release from `main` (the notes can come from a file):

   ```bash
   gh release create vX.Y.Z --target <full SHA of main> --title "vX.Y.Z" --notes-file notes.md
   ```

3. Watch the *Release* workflow, then check <https://pypi.org/project/paper-preflight/>,
   `uvx paper-preflight --version`, and the registry entry:
   `curl "https://registry.modelcontextprotocol.io/v0.1/servers?search=io.github.amos689/paper-preflight"`.
   The registry checks ownership through the
   `<!-- mcp-name: io.github.amos689/paper-preflight -->` line at the top of the README, which
   must therefore be in the PyPI description of that very version.

If the *mcp-registry* job fails (the registry down, say), re-run it from the workflow page, or
publish by hand from the repository root with `mcp-publisher login github` (a device code on
github.com) and `mcp-publisher publish`.

A release whose tag does not match `__version__` stops before anything is uploaded; fix the
version, delete the release and its tag, and publish again. PyPI never accepts the same version
twice, so a broken upload is fixed with a new patch version.

On PyPI the README's relative links point to GitHub (`hatch-fancy-pypi-readme` rewrites them
at build time).
