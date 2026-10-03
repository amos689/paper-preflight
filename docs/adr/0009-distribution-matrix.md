# ADR-0009: One repository, many agent surfaces

- Status: Accepted
- Date: 2026-10-03

## Context

Fast-growing 2026 tools install in one line and support two or more agent harnesses. Agent
Skills (`SKILL.md`) are the lowest common denominator; plugin formats differ per vendor; the MCP
2026-07-28 revision is stateless and FastMCP 4 serves both protocol eras. Skills cost far fewer
context tokens than large MCP tool lists for agents that have a shell.

## Decision

- Core logic lives in one Python package; every surface is a thin shell over the CLI/library:
  - two small skills: `verified-bibtex` (never write BibTeX from memory) and `paper-preflight`
    (run the check before declaring a paper done);
  - Claude Code plugin + self-hosted marketplace (`.claude-plugin/`), Agent Plugins 1.0 root
    manifest (Codex, VS Code, Cursor, Copilot…), `gemini-extension.json`, snippets for
    Antigravity, OpenCode and DeepSeek Harness;
  - an MCP server (`[mcp]` extra) with 4–5 coarse tools and job handles for long runs;
  - pre-commit hooks; a GitHub Action in a separate repository (Marketplace allows one
    `action.yml` per repository).
- No top-level `bin/` directory (claude.ai and Cowork refuse such plugins).
- Version numbers in all manifests are synchronised by a release script.

## Consequences

- Several manifests to keep valid; CI runs `claude plugin validate --strict` and schema checks.
