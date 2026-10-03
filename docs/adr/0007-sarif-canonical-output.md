# ADR-0007: SARIF 2.1.0 as the canonical machine output

- Status: Accepted
- Date: 2026-10-03

## Context

GitHub code scanning only accepts SARIF 2.1.0 (≤10 MB gzipped, ≤25,000 results per run,
deduplication via `partialFingerprints`). None of the citation checkers we studied emit SARIF.
Agents prefer compact JSON; humans prefer terminal and HTML output.

## Decision

- Internally, findings are a single typed model. Emitters: terminal, JSON (versioned schema,
  paginated for agents), SARIF 2.1.0, HTML, Markdown and GitHub annotations.
- SARIF is the canonical interchange format for CI; it is validated against the official schema
  in tests. `partialFingerprints` derive from rule ID + BibTeX key + field (not line hashes, which
  drift when entries are reordered).
- We write our own small SARIF emitter (the `sarif-om` package has been unmaintained since 2019).

## Consequences

- Every finding needs a precise location (file, line, column), reinforcing ADR-0001.
