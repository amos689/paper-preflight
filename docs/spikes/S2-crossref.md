# S2 — Crossref REST API, public pool (no mailto)

- Date: 2026-10-03 (UTC 01:54–01:56). Client in Australia.
- Requests: 29, with at least 1.1 s between them on a single connection. We sent no `mailto` and no token. The User-Agent was `paper-preflight-spike/0.0 (+https://github.com/paper-preflight/paper-preflight)`.
- Scripts and raw data: `.spikes/api/s2_crossref.py`, `.spikes/api/raw/s2_crossref/`, `.spikes/api/log_s2_crossref.jsonl` (git-ignored)

## Purpose

Establish the keyless behaviour of Crossref, which is the primary DOI source:

- rate headers
- record shape
- batch DOI fetch
- bibliographic title search quality
- retraction and relation data
- handling of malformed (LaTeX-escaped) DOIs

## Method

- Single records: `GET https://api.crossref.org/works/{doi}` for `10.1109/CVPR.2016.90`, `10.18653/v1/N19-1423`, Wakefield `10.1016/S0140-6736(97)11096-0`, and TACL `10.1162/tacl_a_00276`.
- Edge cases:
  - the escaped TACL DOI (URL-encoded `%5C`, and a raw backslash)
  - an arXiv DataCite DOI, plus `/works/{doi}/agency`
  - a non-existent DOI `10.1109/CVPR.2016.999999`
  - a lower-cased DOI
- Batch: `GET /works?filter=doi:A,doi:B,...&rows=20&select=DOI,title,type,author,issued,container-title,updated-by,relation`
- Title search: `GET /works?query.bibliographic=<title>&rows=8&select=DOI,title,type,author,issued,container-title,score,prefix,member,publisher`, run for titles 1, 2, 3 and 8, ICLR 2024 *Vision Transformers Need Registers*, CVPR 2025 *VGGT*, and author-enriched variants.
- Prefix 10.65215: `GET /prefixes/10.65215`, `filter=prefix:10.65215`, and `query.bibliographic` combined with `filter=prefix:10.65215` and with `filter=type:posted-content`.
- Retraction notices: `filter=updates:{doi}`. Relation samples: `filter=relation.type:has-preprint` and `filter=relation.type:is-preprint-of`.

## Observations

### Rate and pool headers

The single-record and list endpoints sit in different pools with different limits:

| Endpoint class | `x-api-pool` | `x-rate-limit-limit` / interval | `x-concurrency-limit` |
|---|---|---|---|
| `/works/{doi}`, `/prefixes/{p}`, `/works/{doi}/agency` | `public-single` | **5 / 1s** | 1 |
| `/works?…` (filter, query) | `public-array` | **1 / 1s** | 1 |

- Server: `Jetty(9.4.40.v20210413)`. We got no 429 in 29 calls at ≥ 1.1 s spacing and saw no `Retry-After` header.
- Latency: median 0.42 s, p90 0.75 s, max 0.86 s. The first call was about 0.65 s and repeats were about 0.22 s.
- doi.org content negotiation for Crossref DOIs redirects to `api.crossref.org/v1/works/{doi}/transform`, which counts in the **same** `public-single` pool (see S4).

### `/works/{doi}` record shape

The top-level keys include:

- `DOI`, `title[]`, `subtitle[]`, `original-title`, `short-title`
- `author[]`, `container-title[]`, `short-container-title`, `event`, `type`
- `issued`, `published`, `published-print`, `published-online`, `created`, `deposited`, `indexed`
- `relation`, `updated-by` (when present), `publisher`, `member`, `prefix`
- `reference[]`, `is-referenced-by-count`, `resource`, `link`, `score`

Details that matter for the adapter:

- **DOI case.** `DOI` comes back **lower-cased** even for upper-case input: `"10.1109/cvpr.2016.90"`. A lower-case request resolves the same record.
- **Authors.** `author[]` is ordered, and each entry carries `sequence` (`first`/`additional`) and `given`/`family`. Organisations use `name` instead. Counts: CVPR 4, Wakefield 13, TACL 18.
- **Dates** are `date-parts` arrays of varying precision. BERT has `issued [[2019]]`, CVPR `[[2016,6]]`, Wakefield `[[1998,2]]`. Use `issued` as the canonical year.
- **Container titles** are long, e.g. `"2016 IEEE Conference on Computer Vision and Pattern Recognition (CVPR)"`, or the full NAACL proceedings title. Venue matching against short names such as "CVPR" or "NAACL" needs alias handling.
- **Title whitespace.** The TACL title contains an embedded whitespace run: `"Natural Questions: A Benchmark for Question Answering                     Research"`. Always collapse whitespace.
- **Relations.** `relation` was `{}` for CVPR, BERT, TACL and Wakefield.

### Batch DOI fetch in one request

`filter=doi:10.1109/CVPR.2016.90,doi:10.18653/v1/N19-1423,doi:<Wakefield>,doi:10.1162/tacl_a_00276,doi:10.1109/CVPR.2016.999999` returned 200 in 0.69 s with `total-results: 4`. The non-existent DOI is **silently absent**. A comma between repeated `doi:` filters acts as OR. This call lands in the `public-array` pool (1 request/s).

### `query.bibliographic` (title only, rows=8)

| Title | Correct record present? | Notes |
|---|---|---|
| t1 Attention | **No.** NeurIPS 2017 has no Crossref DOI | The top 8 are look-alikes: Springer chapter "Is Attention All You Need?" (33.28), SSRN posted-content, a Bloomsbury "All You Need Is LSD". `total-results` = 1,243,868 |
| t2 ResNet | Yes, **rank 3** (31.90) | Rank 1 is a Wiley posted-content item (31.97), rank 2 an MDPI survey "Deep Residual Learning for Image Recognition: A Survey" (31.92) |
| t3 BERT | Yes, **rank 2** (48.59) | Rank 1 is an IEEE `component` "Spectrum-BERT: ..." at 53.11 |
| t8 fabricated | No hit with a similar title | The top item is a related title at 34.31. `total-results` = 1,214,842, so the count is meaningless |
| ICLR 2024 (+ authors, year) | No. ICLR registers no DOIs | Neighbours from the same authors and topic, e.g. NeurIPS 2025 "Vision Transformers Don't Need Trained Registers" |
| CVPR 2025 (+ authors, year) | Yes, rank 1, **101.65** vs 60.20 | `10.1109/cvpr52734.2025.00499` |
| t2 + authors + year | Yes, rank 1, **57.95** vs 33.17 | Adding authors and year sharpens the score gap a lot |

### Bogus `posted-content` duplicates, prefix 10.65215

- **Owner.** `GET /prefixes/10.65215` gives member 54718, "Shenzhen Medical Academy of Research and Translation". The prefix holds 279 works, all `posted-content` with subtype `preprint`. `resource.primary.URL` points to `langtaosha.org.cn/.../preprint/view/...`.
- **Copies of t1.** `query.bibliographic=Attention Is All You Need` with `filter=prefix:10.65215` returns 13 hits. At least 8 distinct DOIs are titled exactly "Attention Is All You Need" and list Vaswani, Shazeer, Parmar, Uszkoreit and others: `ysbyhc05`, `pc26a033`, `ctdc8e75`, `r5bs2d54`, `2q58a426`, `mdcm8z23`, `nxvz2v36`, `ne77pf66`.
  - Their `issued` date is **2025-08-23** and they were created 2025-11-12.
  - They are chained to each other with `relation.is-version-of`, asserted by the subject.
  - `is-referenced-by-count` is 24, so people are already citing them.
- **They win author-enriched searches.** With the query "Attention Is All You Need Vaswani Shazeer Parmar Uszkoreit 2017", **the top 7 results are all 10.65215 copies** (score about 85). The next real item scores 34.33. A matcher that checks only title and authors would assign a fake DOI to the NeurIPS paper.
- **They do not win title-only searches.** With the title alone they rank just below the top 8 (about 29.7).
- **Title 2 is not copied.** For t2, 10.65215 returns only unrelated cryo-EM preprints.
- **Downstream impact.** OpenAlex has merged these DOIs into the canonical "Attention" work (see S3).

### Retraction data (Wakefield)

`updated-by` on `10.1016/s0140-6736(97)11096-0` holds two entries:

```json
{"DOI":"10.1016/s0140-6736(04)15715-2","type":"correction","label":"Correction","source":"retraction-watch","updated":{"date-time":"2004-03-06T00:00:00Z"},"record-id":"17269"}
{"DOI":"10.1016/s0140-6736(10)60175-4","type":"retraction","label":"Retraction","source":"retraction-watch","updated":{"date-time":"2010-02-06T00:00:00Z"},"record-id":"4036"}
```

- Both entries come from **`source: "retraction-watch"`**. There is no publisher-sourced (`"publisher"`) entry for this item.
- The title itself carries the prefix `"RETRACTED: "`.
- `filter=updates:<doi>` returns both notices as `journal-article` records with a matching `update-to[]`. The 2004 one is "Retraction of an interpretation", typed as a correction.

### Preprint relations

- `filter=relation.type:has-preprint` gives 576,654 works. Example: `10.1158/1078-0432.ccr-15-3036` has `has-preprint: [{"id-type":"doi","id":"10.1158/1078-0432.c.6526710.v1","asserted-by":"object"}, ...]`.
- `filter=relation.type:is-preprint-of` gives 842,624 works. Example: `10.1364/opticaopen.29459153.v1` has `is-preprint-of: [{"id":"10.1364/OE.572415","asserted-by":"subject"}]`.
- None of the CS test items carry these relations. arXiv DOIs are DataCite DOIs, and IEEE and ACL records do not link to them.

### Malformed and non-Crossref DOIs

| Input | Result |
|---|---|
| `10.1162/tacl\_a\_00276` (sent as `%5C_`, or as a raw backslash) | **404** `text/plain` "Resource not found." (19 B) |
| `10.1109/CVPR.2016.999999` | 404, same body |
| `10.48550/arXiv.1706.03762` (DataCite) | 404 at `/works`. `/works/{doi}/agency` returns 200 `{"agency":{"id":"datacite"}}` |
| `10.1109/cvpr.2016.90` (lower-case) | 200, same record |

## Pitfalls found

1. **The relevance score is not a confidence measure.** Look-alike titles, `component` records (figure or supplement DOIs) and SSRN or Research Square `posted-content` regularly outrank the true record. `total-results` is always in the millions.
2. **Fake-duplicate preprints (10.65215)** are exact copies of famous titles and author lists, and they rank **first** when the query includes the authors. Only the year (2025 vs 2017), the type (`posted-content`) and the publisher give them away.
3. A 404 at `/works/{doi}` does not mean "the DOI does not exist". The DOI may belong to DataCite (arXiv, Zenodo). Confirm with doi.org `doiRA` (S4).
4. A 404 body is plain text, not JSON. Do not parse it.
5. Retraction info in `updated-by` currently comes from Retraction Watch. Do not filter on `source == "publisher"`.
6. DOIs come back lower-cased and titles may contain whitespace runs or HTML entities (`&lt;b&gt;` seen in 10.65215 titles). Normalise both before comparing.
7. The list pool is limited to **1 request/s with concurrency 1**, which is five times stricter than single-DOI lookups.

## Recommendation for the adapter

- **Endpoints:**
  - Known DOI: `GET /works/{doi}`, URL-encoded with `/` kept.
  - Several DOIs: `GET /works?filter=doi:a,doi:b,...&rows=<n>&select=DOI,title,author,issued,container-title,type,updated-by,relation,member,prefix,publisher`. Use chunks of 20, then match returned DOIs case-insensitively.
  - Title-only reference: `GET /works?query.bibliographic=<title + first 2–3 author family names + year>&rows=10&select=...`.
- **Rate settings (keyless):** one connection; single-record calls ≤ 2/s; list and search calls ≤ 1/s. Read `x-rate-limit-*`, `x-concurrency-limit` and `x-api-pool` on every response and adapt to them.
  - On 429 or 503, honour `Retry-After` if present, otherwise back off 2 s, then 8 s, then mark the source unavailable for the run.
  - With a `mailto` (user opt-in only) or a Crossref Metadata Plus token, requests move to the polite or Plus pools with higher limits. Read the limits from the headers rather than hard-coding them.
- **DOI normalisation before any call:**
  - Undo LaTeX escapes: `\_` becomes `_`, and `{\_}`, `\%`, `\&` are unescaped.
  - Strip `https://doi.org/`, `doi:` and trailing `.,;)`.
  - Validate against `^10\.\d{4,9}/\S+$`.
  - Compare case-insensitively.
  - Treat an escaped DOI that resolves only after unescaping as a **warning** ("DOI contains LaTeX escape"), not as an error.
- **Candidate scoring.** Never trust `score` on its own. Accept a candidate only if all of these hold:
  - normalised-title similarity ≥ 0.92, after collapsing whitespace, stripping HTML and lower-casing
  - author-surname overlap ≥ 50% with first-author agreement
  - `|issued.year - cited_year| ≤ 1`, or ≤ 2 for preprint-to-published pairs
  - `type` is in an allowlist (`journal-article`, `proceedings-article`, `book-chapter`, `book`, `posted-content`, `report`, `dissertation`, `monograph`)

  Drop `component`, `peer-review`, `grant` and `dataset` unless the citation itself says dataset. Rank `posted-content` below published types. Treat `posted-content` whose issued year is well after the cited year as **suspicious**, and keep a configurable prefix and member denylist seeded with `10.65215` / member 54718.
- **Retraction status:** read `updated-by[*].type` for `retraction`, `withdrawal`, `expression_of_concern`, `correction` and `removal`, keeping `source` and `updated.date-time`. Also flag a `RETRACTED:` title prefix. Cross-check with OpenAlex `is_retracted` (S3).
- **Source unavailable:** network error, timeout (use 20 s), 5xx, 429, or a non-JSON body on a 200. A 404 on `/works/{doi}` means "not a Crossref DOI", and the agency or doiRA check decides between "DataCite" and "nonexistent".
- **Cache:**
  - DOI records for 30 days, but re-check `updated-by` at most 7 days old when reporting retraction status.
  - `query.bibliographic` results for 7 days, keyed by normalised query.
  - Store `indexed.date-time`.

## Open questions

- Should the 10.65215 denylist live in the source or in a user-updatable data file? It should be tracked in an ADR, together with a heuristic for "exact copy of a famous title with a later year".
- Should the tool ask users for an optional `mailto` (opt-in, never default) to get polite-pool limits? It may be needed for bibliographies with more than 200 entries.
- Could `query.bibliographic` with the full raw reference string (as BibTeX renders it) rank better than title plus authors plus year? Not tested here.
- Does Crossref expose a publisher-sourced retraction for Wakefield in any other field, such as an `update-to` on the notice from the publisher? Only Retraction Watch provenance was observed.
