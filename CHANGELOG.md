# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- Project scaffold: packaging, CLI entry point (`--version`, `doctor`), CI, contribution docs.
- Verdict engine: one verdict per reference (verified, metadata mismatch, identifier conflict,
  not found, cannot determine) with rules REF001-REF005, REF010-REF015, REF018, REF090 and RUN001.
- `check` verifies the cited references online by default; `--offline` answers from the local
  cache only. Text output adds a verdict summary line; JSON adds `verification` and `references`.
  Exit code 2 when a source was unavailable and nothing blocking was found.
- When the arXiv API refuses requests or times out, arXiv IDs are verified through DataCite
  (`10.48550/arXiv.<id>`); the run still reports arXiv as unavailable.
- Semantic Scholar as an optional rescue source, used only when `S2_API_KEY` is set: it is asked
  about references no other source found, stays below the keyed limit of 1 request/s, backs off
  exponentially on HTTP 429, and its outages never block a verdict. Its answers are cached
  locally but never exported (licence).
- Evaluation harness for the HALLMARK benchmark (`evals/run_hallmark.py`): flag / clean / abstain
  outcomes, fabrication-only and any-issue modes, precision, conservative recall, false-positive
  rate and coverage, broken down by hallucination type.
- `doctor` checks each source with one uncached request and reports `ok`, `unavailable` (with the
  reason: rate limit, bot wall, timeout ...) or `skipped`; `--offline` skips the check.
- MCP server (`paper-preflight mcp`, needs the `mcp` extra): read-only `preflight_check` with
  paged findings and `preflight_explain`; paths are confined to the workspace root
  (`docs/mcp.md`).
- Claude Code plugin and marketplace (`plugins/paper-preflight`): the MCP server plus a
  `paper-preflight` skill that runs the check before a paper is called finished.
- pre-commit hooks (`docs/pre-commit.md`): `paper-preflight-offline` (seconds, cached verdicts
  only) and `paper-preflight` (full online verification).
- `paper-preflight explain [RULE]`: what a rule detects, its severity, its message and whether a
  fix is safe; without an argument it lists every rule.
- First full HALLMARK dev_public results (`evals/results/hallmark-dev_public.md`), with a second
  summary that leaves out labels checked by hand and found wrong (`evals/hallmark_disputed.toml`).
