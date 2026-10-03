# ADR-0004: No LLM in the verdict path

- Status: Accepted
- Date: 2026-10-03

## Context

On HALLMARK `test_public`, frontier LLM judges show false-positive rates of roughly 0.19–0.56,
and search-augmented LLMs produce fully correct BibTeX only about half the time. Sending
reference lists of unpublished manuscripts to hosted LLMs also conflicts with some venues'
confidentiality rules. Our core promise is "no LLM guessing".

## Decision

- Verdicts, field comparisons and fix patches are computed deterministically from source records.
- No bibliographic field is ever generated or "completed" by a language model.
- The tool never recommends additional references.
- Optional LLM features (v0.3 claim-support triage) are off by default, may only reason over
  retrieved evidence, are re-checked deterministically (e.g. quotes must be exact substrings), and
  warn about confidentiality before sending anything to a hosted model.

## Consequences

- Reproducible results from recorded responses; benchmarks can be replayed.
- Some cases an LLM could "explain" remain `cannot_determine`; that is acceptable.
