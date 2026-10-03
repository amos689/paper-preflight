# ADR-0002: Verdict taxonomy, abstention and exit codes

- Status: Accepted
- Date: 2026-10-03

## Context

Open-source checkers reach 31–51% precision on real papers mainly because they treat
"we could not look it up" as "it does not exist", feed grey literature into fabrication verdicts
and bind fuzzy matches as anchors. Real-world prevalence of fabricated references is low
(roughly 0.2–0.6%), so the false-alarm rate decides whether a tool is usable at all.

## Decision

Each reference gets exactly one **verdict**:

| Verdict | Meaning |
|---|---|
| `verified` | Anchored to an authoritative record; title, authors and year positively confirmed (venue may be unknown). |
| `metadata_mismatch` | The work exists, but some fields are wrong. |
| `identifier_conflict` | The DOI/arXiv ID resolves to a different work. |
| `not_found` | Every *required* source for this reference type answered "no such work", the query was of adequate quality, and the entry is not grey literature, not too new and not accepted by the user. |
| `cannot_determine` | Anything else; always carries one or more reason codes (`SOURCES_UNAVAILABLE`, `GREY_LITERATURE`, `UNINDEXED_LINK`, `OLD_WORK`, `AMBIGUOUS_CANDIDATES`, `TOO_NEW`, `INSUFFICIENT_METADATA`, `NON_LATIN_UNSUPPORTED`, `IDENTIFIER_EXISTS_NO_METADATA`, `CORRUPTED_SOURCE_RECORD`, `BUDGET_EXHAUSTED`, `OFFLINE_MODE`). |

Independent **flags**: `retracted`, `expression_of_concern`, `corrected`, `withdrawn`,
`preprint_published`.

A source is **unavailable** when it returns 429, 403 challenge responses, 5xx, times out, returns
HTML where JSON is expected (bot walls), or its budget is exhausted. Unavailability never counts as
a negative answer. We never attempt to bypass a challenge.

Wording is neutral ("not found in X, Y, Z — all responded"). The words "fabricated" or
"hallucinated" are never used without positive evidence.

**Exit codes:** 0 = no findings at/above `--fail-on` and the run is complete; 1 = blocking
findings; 2 = no blocking findings but the run is incomplete (cannot claim a pass); 3 = usage or
configuration error; 4 = internal error. Blocking findings take precedence over incompleteness
because they rest on positive evidence and must be fixed regardless.

## Consequences

- More `cannot_determine` results; we must keep them below ~25% for CS papers through better
  coverage (dblp, ACL, DataCite), not by guessing.
- Benchmarks must score abstentions explicitly (conservative/aggressive + coverage).
- `bibtexupdater` gives source outages precedence over findings; we deliberately differ.
