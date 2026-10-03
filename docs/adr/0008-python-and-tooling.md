# ADR-0008: Python ≥ 3.11, uv, hatchling

- Status: Accepted
- Date: 2026-10-03

## Context

Python 3.10 reached end of life on 2026-10-01. The scholarly-tooling ecosystem is Python
(bibtexparser, pylatexenc, acl-anthology which needs > 3.11, pdfminer, NLI models). Agent skills
recommend `uvx` for one-line execution.

## Decision

- `requires-python = ">=3.11"`; CI covers 3.11–3.14 on Linux, macOS and Windows.
- uv for environments, locking and `uvx` distribution; hatchling as build backend.
- Typer + Rich for the CLI, pydantic v2 for models, ruff for lint/format, mypy strict for `src/`,
  pytest (+ respx, hypothesis) for tests.
- The base install stays small and pure-Python so that `uvx` cold starts stay fast (Codex allows
  10 s for MCP server start-up); heavy features live in extras (`[mcp]`, `[pdf]`, `[claims]`).

## Consequences

- Users on old Pythons get a clear install error; `uvx` fetches a suitable interpreter anyway.
