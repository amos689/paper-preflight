# S1 — dblp: search API vs. SPARQL endpoint (QLever)

- Date: 2026-10-03 (UTC 01:46–02:02). The client was in Australia, so expect a network floor of about 0.28 s to the German servers.
- Requests: 65 in total (58 to `sparql.dblp.org`, 7 to `dblp.org`), spaced 1.2–2 s apart on a single connection.
- Scripts and raw responses: `.spikes/api/s1*.py`, `.spikes/api/raw/s1_dblp/`, `.spikes/api/log_s1_dblp.jsonl` (git-ignored)

## Purpose

Find out whether dblp can be the online computer-science source for title, DOI and arXiv lookups in paper-preflight, or whether W0 must plan for a local index built from the XML dump.

## Method

- (a) `GET https://dblp.org/search/publ/api?q=<title>&format=json&h=5` for titles 1, 3, 8, and title 2 with `Accept: application/json`.
- (b) `GET|POST https://sparql.dblp.org/sparql` with `query=<SPARQL>` and `Accept: application/sparql-results+json`. One probe used `application/qlever-results+json` to get server-side timings.
- Schema discovery: a predicate histogram, plus `?p ?o` dumps of `conf/nips/VaswaniSPUJGKP17` and `journals/corr/VaswaniSPUJGKP17`.
- Lookup strategies tried for test titles 1–6 and 8, plus ICLR 2024 *Vision Transformers Need Registers* (arXiv 2309.16588) and CVPR 2025 *VGGT: Visual Geometry Grounded Transformer* (arXiv 2503.11651).
- Policy sources: `https://sparql.dblp.org/` (UI page), `https://dblp.org/xml/`, the dblp blog post "Introducing our public SPARQL query service" (2024-09-09), and the TGDK paper *The dblp Knowledge Graph and SPARQL Endpoint* (doi:10.4230/TGDK.2.2.3).

## Observations

### (a) dblp.org search API: blocked by Anubis

| Request | Status | Content-Type | Body |
|---|---|---|---|
| search t1 / t3 / t8 | 200 | text/html | Anubis challenge page, about 3 KB |
| search t2 (4th request, 1.5 s gap) | **429** | text/html | `<h1>429 Too Many Requests</h1>`, 117 B, no `Retry-After` |
| search `q=test`, about 5 min later | 200 | text/html | Anubis challenge again |
| `dblp.org/faq/...` | 200 | text/html | Anubis challenge |
| `dblp.org/xml/` (dump directory) | 200 | text/html | Apache index, **no challenge** |

- The challenge page identifies itself through four markers:
  - `<title>Making sure you&#39;re not a bot!</title>`
  - `<script id="anubis_version">"v1.27.0"`
  - `<script id="anubis_challenge">{"rules":{"algorithm":"metarefresh","difficulty":1},...}`
  - a `set-cookie: dblp_org-cookie-verification-*` header with `cache-control: no-store`
- The challenge JSON echoes our User-Agent and client IP.
- The status is **200**, so a client that only checks status codes and then parses JSON will report a "malformed body" error instead of "blocked".
- We did not try to solve or bypass the challenge.

### (b) SPARQL endpoint: reachable, fast, no bot challenge

- **Transport.** Plain `Apache/2.4.52`. GET and form-POST both work. Responses carry **no rate-limit headers** at all, only `date`, `server` and `content-type`. We saw no 429 in 58 requests at a 1.2 s spacing.
- **Freshness and licence.** The dataset node reports `<https://dblp.org/rdf/dblp.nt> dct:modified "2026-10-01T19:24:40+0200"` and licence CC0. The schema IRI is `schema-2026-09-07`. The UI page says data is "synchronized daily".
- **Size.** 8,786,100 `dblp:title` triples and 30.4 M author signatures. There are also 159 M `cito:` citation links (from OpenCitations).
- **Errors.** A malformed query returns **400** `application/json` with `{"exception":"Invalid SPARQL query: ...","metadata":{...}}`.
- **Server time vs. wall time.** For an indexed prefix-range query, QLever reported `"time":{"computeResult":"0ms","total":"1ms"}`. Wall latency is therefore almost entirely network.

**Latency by query shape** (wall clock from Australia):

| Query shape | Latency | Usable? |
|---|---|---|
| Exact literal `?pub dblp:title "Attention is All you Need."` | 0.3–0.9 s | Only with dblp's exact casing and trailing dot |
| Case-insensitive prefix range `FILTER(?t >= "lc-prefix" && ?t < "lc-prefiy")` | 0.28–1.2 s | **Yes**, primary strategy |
| `ql:contains-word` / `ql:contains-entity` text search | 0.3–3.5 s | Yes, as a fallback |
| Batch of 3 title ranges (UNION or `VALUES (?lo ?hi)`) | 0.9–1.5 s | Yes |
| Batch of 6 DOIs via `VALUES ?doi {...}` | 0.88 s | Yes |
| Full record (ordered authors, venue, DOI) for 7 IRIs | 0.95 s | Yes |
| `FILTER(LCASE(?t) = ...)`, `CONTAINS(LCASE(?t), ...)`, `REGEX(..., "i")` | **7–11 s** (full scan) | No |
| CoRR → published-version link query (5 CoRR records) | 0.9 s | Yes |

**Schema facts that matter for the adapter:**

- **Titles** keep dblp casing and end with `.`. The NIPS record is "Attention is All you Need." while the CoRR record is "Attention Is All You Need.". Exact literal lookup with the user's casing returns 0 rows.
- **Authors.** `dblp:hasSignature` links to `dblp:signatureOrdinal` (1..n), `dblp:signatureDblpName` and `dblp:signatureCreator` (a PID), plus `dblp:signatureOrcid` when known. Names carry homonym suffixes, e.g. "Xiangyu Zhang 0005" and "Jian Sun 0001"; strip `\s\d{4}$`.
- **Venue.** `dblp:publishedIn` is a short string, e.g. `NIPS`, `CVPR`, `NAACL-HLT (1)`, `ICLR`, `ICLR (Poster)`, `CoRR`, `Trans. Assoc. Comput. Linguistics`. `dblp:bibtexType` is Inproceedings or Article. `dblp:publishedInJournalVolume` holds `abs/1706.03762` for CoRR.
- **DOI** is stored as the IRI `https://doi.org/` followed by an upper-cased DOI, e.g. `10.18653/V1/N19-1423`, `10.48550/ARXIV.1706.03762`, `10.1162/TACL_A_00276`. A mixed-case IRI (`.../10.48550/arXiv.1606.08415`) returns **0 rows**. The `datacite:hasIdentifier` literal is upper-cased too.
- **Links.** `dblp:documentPage` holds all "ee" links and `dblp:primaryDocumentPage` the main one. CoRR records also carry `owl:sameAs <https://doi.org/10.48550/ARXIV.<id>>`.
- **Versions.** `dblp:isVersionOf` and `dblp:versionConcept` exist (8,977 triples) but only for `data/` records such as Zenodo-style datasets. They do **not** link CoRR records to conference papers.

**Per test item:**

| # | dblp result |
|---|---|
| 1 Attention | `conf/nips/VaswaniSPUJGKP17` (NIPS 2017, **no DOI**, ee = proceedings.neurips.cc) and `journals/corr/VaswaniSPUJGKP17` |
| 2 ResNet | `conf/cvpr/HeZRS16` (DOI `10.1109/CVPR.2016.90`) and `journals/corr/HeZRS15` |
| 3 BERT | `conf/naacl/DevlinCLT19` (DOI `10.18653/V1/N19-1423`, venue "NAACL-HLT (1)") and `journals/corr/abs-1810-04805` |
| 4 Adam | Only `journals/corr/KingmaB14`, but with `publishedIn "ICLR (Poster)"` and year 2015. dblp files ICLR 2013–15 under CoRR keys, so **the key prefix is not the venue** |
| 5 LoRA | `conf/iclr/HuSWALWWC22` (ee = OpenReview, no DOI) and `journals/corr/abs-2106-09685` |
| 6 GELU | Only `journals/corr/HendrycksG16`, titled with the **v1 title** "Bridging Nonlinearities and Stochastic Regularizers with Gaussian Error Linear Units.". Title lookup with "Gaussian Error Linear Units (GELUs)" finds **nothing** by prefix or text search. Lookup by arXiv DOI works |
| 7 Wakefield | Not in dblp (expected: medicine) |
| 8 fabricated | 0 hits by prefix and by text search |
| ICLR 2024 | `conf/iclr/DarcetOMB24` (OpenReview ee, no DOI) and the CoRR record |
| CVPR 2025 | `conf/cvpr/WangCKV0N25` (DOI `10.1109/CVPR52734.2025.00499`, CVF open-access ee) and the CoRR record |
| TACL DOI | `journals/tacl/KwiatkowskiPRCP19` when looked up as `10.1162/TACL_A_00276` (upper-cased) |

**QLever text search:**

- The legacy syntax works: `?text ql:contains-word "w"` combined with `?text ql:contains-entity ?t`. The index covers literals, including titles.
- `ql:contains-word` on its own, and the newer `SERVICE textSearch:` syntax, both returned empty bindings.
- Matching uses whole words with AND semantics. "pre-training" is split into "pre" and "training". We removed stop-words client-side.
- Results are **unranked**. "attention" AND "need" matched 230 titles, so with `LIMIT 100` the target is not guaranteed to be included. Fuzzy ranking has to happen client-side.

**Case-insensitive prefix trick.** QLever's vocabulary is sorted with a case-insensitive collation, so a lexicographic range on a lower-cased prefix returns all casings:

- The range for t1 returned 23 titles, including both "Attention is All you Need." and "Attention Is All You Need.".
- `STRSTARTS` is case-sensitive: 0 rows for lower-case input.
- `REGEX(?t, "^Deep Residual Learning for Image")` without the `i` flag still behaved case-insensitively: it also returned "Deep residual learning for image steganalysis.".
- This behaviour is **undocumented** and tied to QLever internals.

**Linking CoRR to published versions.** There is no explicit relation in dblp. Joining on the same first-author PID plus title equality after `LCASE(REPLACE(?t,"[^A-Za-z0-9]",""))` linked 4 of 5 CoRR records to their published versions in 0.9 s: HeZRS15→CVPR'16, abs-2503-11651→CVPR'25, abs-1810-04805→NAACL'19, and VaswaniSPUJGKP17→NIPS'17. Adam has no separate record.

**Policy:**

- The dblp blog calls the SPARQL service a public beta, says "be prepared for disruptions and outages", and asks users "not [to] overwhelm our live APIs". For higher rates it recommends running your own instance.
- The TGDK paper mentions rate limiting against aggressive scripting and a fixed per-query timeout.
- No numeric limits are published, and the FAQ is behind Anubis.
- Dump: `https://dblp.org/xml/dblp.xml.gz` is **1.0 GB**, regenerated daily (timestamp 2026-10-03 01:08, with an `.md5` file beside it). It is not behind Anubis.

## Pitfalls found

1. The search API returns HTTP **200 + HTML** (Anubis), not an error status. It also escalates to 429 after a handful of requests.
2. Titles have dblp casing and a trailing `.`, and DOIs are upper-cased. Normalise both sides before comparing.
3. The key namespace (`journals/corr/...`) is not the venue: Adam is ICLR 2015 under a CoRR key. Classify by `publishedIn` and `bibtexType`.
4. dblp keeps the **old** arXiv title when the title later changed (GELU). Title-only lookup gives a false "not found".
5. Text search is unranked and drops nothing on its own. Stop-word removal and LIMIT handling are our job.
6. The range-collation trick depends on QLever internals. It could silently break after an endpoint upgrade.
7. Author names carry `0001`-style homonym suffixes.
8. The endpoint is "beta" with no published SLA and no rate headers. Unavailability will show up only as timeouts, 5xx or HTML.

## Recommendation for the adapter

- **Never call `dblp.org/search/publ/api`.** Classify any dblp response as `source_unavailable(reason="bot_challenge")` if it meets any of these:
  - content-type is not JSON
  - the body contains `id="anubis_challenge"` or the title "Making sure you're not a bot!"
  - the status is 429

  Then apply a 24 h cooldown for that host, with no retries.
- **Use SPARQL as the online CS source:**
  - Limit to ≤ 1 request/s and 1 connection.
  - Set an HTTP timeout of 30 s and use POST for queries longer than about 2 KB.
  - Per reference, run at most:
    - one prefix-range query (template T1);
    - then, if no title scores ≥ 0.9 similarity, one text-search query (T2);
    - then one full-record query for the top ≤ 5 IRIs (T3).
  - Batch DOI and arXiv lookups for the whole bibliography in one `VALUES` query (T4/T5).
- **Source-unavailable rules:** connection error, timeout, 5xx, 429, non-JSON content-type or an HTML body means unavailable. Back off 60 s and then skip the source for the run. A 400 with a JSON `exception` is an internal query bug: log it and do not mark the source down.
- **Cache:** responses keyed by a normalised query hash, with a TTL of 7 days, since dblp syncs daily. Store `dct:modified` (T7) with each cache epoch.
- **Canary:** at start-up, or once a day, run T1 for "attention is all you need" and expect `conf/nips/VaswaniSPUJGKP17`. If it fails, disable the range trick and fall back to text search.
- **Local dump index:** not required for the MVP. Keep it as a W1+ option (`dblp.xml.gz` to SQLite FTS5) for offline/CI mode and as a fallback if the beta endpoint changes. Both data paths are CC0.

### Ready-to-use query templates

All templates share this prefix:

```sparql
PREFIX dblp: <https://dblp.org/rdf/schema#>
PREFIX ql:   <http://qlever.cs.uni-freiburg.de/builtin-functions/>
```

**T1: title lookup, case-insensitive prefix.** Set `lo` to the lower-cased, whitespace-collapsed first 40 characters of the title. Set `hi` to `lo` with its last character incremented. Escape `"` and `\`.

```sparql
SELECT ?pub ?t ?year ?venue ?type WHERE {
  ?pub dblp:title ?t . FILTER(?t >= "{lo}" && ?t < "{hi}")
  ?pub dblp:bibtexType ?type .
  OPTIONAL { ?pub dblp:yearOfPublication ?year } OPTIONAL { ?pub dblp:publishedIn ?venue }
} LIMIT 100
```

**T2: text-search fallback.** Use one `contains-word` per non-stop-word token of length ≥ 2, lower-cased and split on `[^0-9a-z]`.

```sparql
SELECT ?pub ?t WHERE {
  ?text ql:contains-word "deep" . ?text ql:contains-word "residual" . ?text ql:contains-word "recognition" .
  ?text ql:contains-entity ?t . ?pub dblp:title ?t .
} LIMIT 200
```

**T3: full record with ordered authors.** Assemble rows client-side, ordered by `?ord`.

```sparql
SELECT ?pub ?title ?type ?venue ?year ?doi ?primary ?ord ?name ?pid ?orcid WHERE {
  VALUES ?pub { <https://dblp.org/rec/conf/cvpr/HeZRS16> <https://dblp.org/rec/journals/corr/HeZRS15> }
  ?pub dblp:title ?title ; dblp:bibtexType ?type .
  OPTIONAL { ?pub dblp:publishedIn ?venue } OPTIONAL { ?pub dblp:yearOfPublication ?year }
  OPTIONAL { ?pub dblp:doi ?doi } OPTIONAL { ?pub dblp:primaryDocumentPage ?primary }
  ?pub dblp:hasSignature ?s . ?s dblp:signatureOrdinal ?ord ; dblp:signatureDblpName ?name ; dblp:signatureCreator ?pid .
  OPTIONAL { ?s dblp:signatureOrcid ?orcid }
} ORDER BY ?pub ?ord
# all ee links: SELECT ?pub ?ee WHERE { VALUES ?pub {...} ?pub dblp:documentPage ?ee }
```

**T4: batch DOI lookup.** DOIs must be upper-cased.

```sparql
SELECT ?doi ?pub ?t ?venue ?year WHERE {
  VALUES ?doi { <https://doi.org/10.1109/CVPR.2016.90> <https://doi.org/10.18653/V1/N19-1423> <https://doi.org/10.1162/TACL_A_00276> }
  ?pub dblp:doi ?doi ; dblp:title ?t . OPTIONAL { ?pub dblp:publishedIn ?venue } OPTIONAL { ?pub dblp:yearOfPublication ?year }
}
```

**T5: arXiv ID lookup.** Same as T4, with `<https://doi.org/10.48550/ARXIV.1606.08415>`.

**T6: link CoRR to published versions.** To go the other way, swap the roles and add `FILTER(?venue = "CoRR")`.

```sparql
SELECT ?corr ?other ?venue ?year WHERE {
  VALUES ?corr { <https://dblp.org/rec/journals/corr/abs-1810-04805> }
  ?corr dblp:title ?ct ; dblp:hasSignature ?s1 . ?s1 dblp:signatureOrdinal 1 ; dblp:signatureCreator ?a1 .
  ?other dblp:authoredBy ?a1 ; dblp:title ?ot . FILTER(?other != ?corr)
  FILTER(LCASE(REPLACE(?ot, "[^A-Za-z0-9]", "")) = LCASE(REPLACE(?ct, "[^A-Za-z0-9]", "")))
  OPTIONAL { ?other dblp:publishedIn ?venue } OPTIONAL { ?other dblp:yearOfPublication ?year }
}
```

**T7: data freshness.**

```sparql
SELECT ?m WHERE { <https://dblp.org/rdf/dblp.nt> <http://purl.org/dc/terms/modified> ?m }
```

## Open questions

- What are the actual per-IP limits and the per-query timeout? Neither is published. Ask the dblp team, mentioning our UA string, before release.
- Will dblp exempt `/search/publ/api` from Anubis for identified tools? An API-key scheme might do it.
- Is the case-insensitive range ordering a stable QLever guarantee? Check with the QLever maintainers, and keep the canary either way.
- Should a local QLever instance, or the SQLite index from the XML dump, become the default for heavy users or CI? It needs about 1 GB to download plus index build time.
- Changed arXiv titles (GELU): should we always resolve arXiv IDs through arXiv or DataCite first and treat dblp titles as secondary? Spike S4 suggests yes.
