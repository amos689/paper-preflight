# ADR-0003: Identifier-first source routing

- Status: Accepted (based on spikes S1–S5, 2026-10-03)
- Date: 2026-10-03

## Context

Spikes S1–S5 (`docs/spikes/`) measured keyless behaviour of every candidate source:

- **dblp** search API: HTTP 200 + Anubis HTML challenge, then 429. **dblp SPARQL** (QLever): no
  challenge, 0.3–1.2 s per query, CC0, daily sync, no published limits (public beta). Exact-title
  literals fail (dblp casing + trailing dot); a lower-cased prefix range works (undocumented
  collation behaviour); text search works but is unranked. dblp keeps the **v1 arXiv title**
  (GELU). CoRR records can be linked to published versions via first-author PID + normalised title.
- **Crossref**: `public-single` 5 req/s, `public-array` (filter/search) 1 req/s, concurrency 1.
  Multi-DOI `filter=doi:a,doi:b` works. `query.bibliographic` scores are not confidences; famous
  titles have dozens of fake `posted-content` duplicates (prefix 10.65215, member 54718) that rank
  **first** once author names are added. Retractions arrive in `updated-by` (source
  `retraction-watch`). A 404 means "not a Crossref DOI", not "no such DOI".
- **OpenAlex**: singleton `GET /works/doi:<doi>` is free; OR-filter $0.0001; search $0.001; keyless
  budget $0.10/day (~100 searches). Canonical records can carry a **wrong DOI/year/type** (Attention
  merged with 10.65215 copies) or a **wrong title** (LoRA arXiv). Preprints and published versions
  are separate, unlinked works. `is_retracted` is reliable.
- **arXiv**: `id_list` batches work (unordered results, missing IDs simply absent); per-version
  titles are retrievable; `journal_ref`/`doi` are mostly empty for ML papers; withdrawal is only
  free text in `<arxiv:comment>`.
- **DataCite**: arXiv DOIs resolve with ordered creators and the latest title; no links to the
  published version; batch via `/dois?ids=`.
- **doi.org**: one `doiRA/<d1>,<d2>,...` call returns the registration agency or "DOI does not
  exist" for many DOIs, in order. LaTeX-escaped DOIs do not exist anywhere.
- **Semantic Scholar** (anonymous): 6 of 17 calls returned 429 at 1.2 s spacing (shared global
  pool), no `Retry-After`. Merged records carry ArXiv + DOI + DBLP ids, the most direct
  arXiv↔venue link of all sources (when a key makes the API dependable). `year` is the preprint
  year; there is no retraction signal. The licence forbids redistribution.

## Decision

**1. Identifier normalisation first.** Undo LaTeX escapes, strip URL/`doi:` prefixes and trailing
punctuation, compare DOIs case-insensitively. An escaped DOI that resolves only after unescaping
is a warning (REF017), not an error.

**2. DOI routing.** One `doiRA` call per ~50 DOIs, then:

| doiRA answer | Next step |
|---|---|
| Crossref | Crossref `filter=doi:` batches of 20 (or `/works/{doi}`); OpenAlex singleton for `is_retracted` |
| DataCite | DataCite `/dois?ids=` batch (arXiv DOIs also feed the arXiv path) |
| other RA (mEDRA, JaLC, KISTI…) | doi.org CSL-JSON content negotiation |
| CNKI / ISTIC | existence only (`IDENTIFIER_EXISTS_NO_METADATA`); full support in v0.2-zh |
| "DOI does not exist" | REF002, confirmed with the Handle API when doiRA is ambiguous |

**3. arXiv routing.** `id_list` batches (≤ 50 IDs, one connection, ≥ 3 s apart); per-version titles
are fetched only when a title mismatch must be explained. Withdrawal comments → REF018 (warning).

**4. References without identifiers.**

- CS-like (conference/workshop, or journal in dblp): dblp SPARQL — batch DOI/arXiv lookups (T4/T5),
  prefix-range title lookup (T1), text-search fallback (T2), full records (T3).
- Everything else: Crossref `query.bibliographic` with title + first authors + year; OpenAlex
  `title.search` only with `OPENALEX_API_KEY` or while the remaining budget is ≥ 3× the call cost.
- arXiv title search (`ti:"…"`) for entries that mention arXiv but carry no ID.

**5. Candidate acceptance (never trust a source's relevance score).** Title similarity ≥ 0.92 after
normalisation, author-surname overlap with first-author agreement, year within ±1 (±2 for
preprint/published pairs), type allow-list (drop `component`, `peer-review`, `grant`), and a
user-updatable **suspicious-prefix denylist** seeded with 10.65215 (member 54718). OpenAlex records
whose DOI prefix is denylisted or whose year is far from the citation year are not trusted.

**6. Preprint → published.** Keyless: dblp CoRR→venue link (T6), arXiv `journal_ref`/`doi`,
Crossref `is-preprint-of`. With `S2_API_KEY`: Semantic Scholar merged records.

**7. Retraction status** is the union of Crossref `updated-by` (retraction, withdrawal, expression of
concern, correction, removal — any `source`), OpenAlex `is_retracted`, and a `RETRACTED:` title
prefix. Refreshed weekly; forced fresh in `--final`/CI mode.

**8. Semantic Scholar is off by default.** It is enabled when `S2_API_KEY` is set (≈1.1 s spacing),
or anonymously with `--allow-anonymous-s2` (≥ 3 s spacing, ≤ 20 calls per run, one retry on 429).
Only derived facts (paperId, external IDs, match decision) are cached locally, marked
non-exportable; raw responses are never written to the repository or reports.

**9. "Not found" (REF003) requires two independent negative answers** from available sources
appropriate to the reference type (e.g. dblp + Crossref for CS papers, Crossref + OpenAlex for
others), after title variants were tried. A single negative is `cannot_determine`
(`SINGLE_SOURCE_NEGATIVE`).

**10. Pacing defaults (keyless):** dblp SPARQL ≤ 1 req/s; Crossref single ≤ 2 req/s and list ≤ 1
req/s (adapted to `x-rate-limit-*` headers); OpenAlex ≤ 1 req/s with a persisted daily budget guard;
arXiv ≥ 3 s; DataCite ≤ 1 req/s; doi.org ≤ 1 req/s. All with one connection per source.

**11. dblp canary:** once per day the adapter checks that the prefix-range lookup for "attention is
all you need" still returns `conf/nips/VaswaniSPUJGKP17`; if not, it falls back to text search only.
A local dblp index (XML dump, ~1 GB) remains a v0.1.x option for offline/CI use.

## Consequences

- A typical 50–80 reference CS paper needs roughly 10–30 requests when identifiers are present and
  more for identifier-less entries; most time is spent waiting for polite pacing.
- Keyless operation is fully supported; keys (OpenAlex, S2) improve coverage and speed.
- The denylist, venue alias table and dblp query templates are data files that need maintenance.
- `cannot_determine` will be more frequent for non-CS references without identifiers in keyless
  mode; this is the intended trade-off for precision.
