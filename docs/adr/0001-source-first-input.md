# ADR-0001: Source-first input; PDF only as a low-confidence fallback

- Status: Accepted
- Date: 2026-10-03

## Context

Published audits of citation checkers identify PDF reference extraction as the leading cause of
false positives (titles folded into author fields, lost entries, full-width punctuation breaking
segmentation). CI annotations and SARIF also need exact source locations, which only the LaTeX
sources can provide. Authors who run a pre-submission check almost always have their sources.

## Decision

- The primary input is a LaTeX project: `.tex` files (for citation sites), `.aux`/`.bcf` (the
  authoritative set of cited keys when present and newer than the sources) and `.bib` (structured
  fields with line positions).
- A standalone `.bib` file is accepted (verification without citation hygiene).
- `.bbl` input (v0.1.x) and plain-text reference lists / PDF (later) are separate, explicitly
  low-confidence adapters. Findings derived from them carry `confidence: low` and never produce
  `not_found` on their own.

## Consequences

- Higher precision and exact locations for SARIF/editor diagnostics.
- Benchmarks built from formatted reference strings (e.g. Badalova & Mayr) need a faithful,
  documented conversion to BibTeX; comparisons must state that inputs differ.
- Users who only have a PDF are not served well until the low-confidence adapter exists.
