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
