# S5 — Semantic Scholar Graph API (anonymous)

- Date: 2026-10-03 (UTC 02:00–02:02). Client in Australia; responses came through CloudFront's SYD POP.
- Requests: 21 in total, anonymous with no `x-api-key`:
  - pass 1: 17 requests, spaced **1.2 s** apart
  - pass 2: 4 retries of failed calls, spaced **3.0 s** apart
- Scripts: `.spikes/api/s5_s2.py`. Raw responses are kept **only** in `.spikes/api/raw/s5_s2/` (git-ignored), because the S2 API licence forbids redistribution. This report quotes only field names and derived facts.

## Purpose

Find out whether anonymous Semantic Scholar is usable as a lookup source:

- title match
- DOI and arXiv lookup
- batch lookup
- merged-record identifier coverage

Also measure how often anonymous calls are throttled.

## Method

All calls used `fields=title,authors,year,venue,externalIds,publicationVenue,publicationDate,publicationTypes`.

- `GET https://api.semanticscholar.org/graph/v1/paper/search/match?query=<title>&fields=…` for titles 1–6 and 8, ICLR 2024 *Vision Transformers Need Registers* and CVPR 2025 *VGGT*.
- `GET /graph/v1/paper/DOI:<doi>?fields=…` for CVPR, BERT, Wakefield, TACL and the escaped TACL DOI.
- `GET /graph/v1/paper/ARXIV:<id>?fields=…` for 1706.03762 and 1606.08415.
- `POST /graph/v1/paper/batch?fields=…` with body `{"ids":["DOI:10.1109/CVPR.2016.90","ARXIV:1512.03385","ARXIV:1810.04805","DOI:10.18653/v1/N19-1423","ARXIV:2106.09685","ARXIV:1412.6980","DOI:10.1109/CVPR.2016.999999","DOI:10.1162/tacl_a_00276"]}`.

## Observations

### Throttling

| Pass | Spacing | Requests | 200 | 404 (expected) | **429** |
|---|---|---|---|---|---|
| 1 | 1.2 s | 17 | 10 | 1 | **6** |
| 2 | 3.0 s | 4 | 3 | 1 | 0 |

- **Pass 1 pattern.** The **first three** requests of pass 1 were already 429: match t1, t2 and t3. Later, match t8, `ARXIV:1706.03762` and `ARXIV:1606.08415` also got 429, interleaved with successes.
  - Our own rate was well under 1 request/s, so the throttle is the **shared global anonymous pool**, not a per-client limit.
  - Spacing helps, but it gives no guarantee.
- **429 response.**
  - Body: `{"message": "Too Many Requests. Please wait and try again or apply for a key for higher rate limits. …", "code": "429"}`
  - Headers: `x-amzn-errortype: TooManyRequestsException` and `x-cache: Error from cloudfront`.
  - **No `Retry-After`** and no rate-limit headers, on 429s or on 200s.
- **Infrastructure.** CloudFront → AWS API Gateway → gunicorn.
- **Latency of successes.** Min 0.19 s, median 0.61 s, max 0.95 s.

### `/paper/search/match`

- The response is `{"data":[ {paperId, externalIds, publicationVenue, title, venue, year, publicationTypes, publicationDate, authors, matchScore} ]}`, with exactly **one** best candidate.
- **No match.** The fabricated title (t8) returned **404 `{"error":"Title match not found"}`**, a clean "not found" signal.
- **Hits.** Every real title returned the correct canonical paper (matchScore about 133–245):
  - t1: NeurIPS venue
  - t3: NAACL
  - t4: ICLR
  - t5: ICLR
  - t6: the current GELU title
  - ICLR 2024 and CVPR 2025: correct records
- **Year inconsistency.** `year` follows the earliest version: the ICLR 2024 paper reports **2023**. Through the DOI route, ResNet reports **2015** while its venue is CVPR (2016).
- **`publicationTypes` is unreliable.** Conference papers often come back as `["JournalArticle","Conference"]` or just `["JournalArticle"]`.

### Merged records: identifier coverage

| Paper | externalIds present | ArXiv | DOI | DBLP key |
|---|---|---|---|---|
| ResNet (via DOI, via ARXIV, via batch) | ArXiv, CorpusId, DBLP, DOI, MAG | 1512.03385 | 10.1109/cvpr.2016.90 | conf/cvpr/HeZRS16 |
| BERT | ACL, ArXiv, CorpusId, DBLP, DOI, MAG | 1810.04805 | 10.18653/v1/N19-1423 | journals/corr/abs-1810-04805 |
| VGGT (CVPR 2025) | ArXiv, CorpusId, DBLP, DOI | 2503.11651 | 10.1109/CVPR52734.2025.00499 | conf/cvpr/WangCKV0N25 |
| ViT registers (ICLR 2024) | ArXiv, CorpusId, DBLP, DOI | 2309.16588 | **10.48550/arXiv.2309.16588** (the arXiv DOI, not a venue DOI) | journals/corr/abs-2309-16588 |
| Attention | ArXiv, CorpusId, DBLP, MAG | 1706.03762 | none (correct) | journals/corr/VaswaniSPUJGKP17 |
| LoRA | ArXiv, CorpusId, DBLP | 2106.09685 | none | conf/iclr/HuSWALWWC22 |
| Adam | ArXiv, CorpusId, DBLP, MAG | 1412.6980 | none | journals/corr/KingmaB14 |
| TACL NQ | ACL, CorpusId, DBLP, DOI, MAG | — | 10.1162/tacl_a_00276 | journals/tacl/KwiatkowskiPRCP19 |
| Wakefield | CorpusId, DOI, MAG, PubMed | — | 10.1016/S0140-6736(97)11096-0 | — |

- **Yes, merged records carry both the ArXiv and DOI IDs** (ResNet, BERT, VGGT). `DOI:` and `ARXIV:` lookups resolve to the **same `paperId`**.
- The DBLP key may point to either the CoRR record or the conference record.
- S2 is the only source in this spike set that links arXiv to the venue DOI directly. Unlike OpenAlex, it showed no 10.65215 pollution.

### Other behaviour

- **`POST /paper/batch`.** One call returned 8 results in 0.55 s. The **output array is aligned with the input order**, and an unknown DOI gives `null` in its slot.
- **Escaped TACL DOI.** `DOI:10.1162/tacl\_a\_00276` returns 404 `{"error":"Paper with id DOI:10.1162/tacl\\_a\\_00276 not found"}`.
- **Wakefield.** None of the requested fields signals a retraction. The title has **no** "RETRACTED:" prefix, and `publicationTypes` is `["JournalArticle","Review"]`. S2 cannot be used for retraction status.
- **Author names** are sometimes abbreviated, e.g. "J. Hu" for Edward J. Hu, "A. Wakefield", "T. Kwiatkowski".

## Pitfalls found

1. **Anonymous access is unreliable even at low rates:** 35% of calls failed (6 of 17) at 1.2 s spacing, including the very first call. Any feature that depends on S2 will be flaky without a key.
2. The 429 response has no `Retry-After` and no rate headers, so the client has to choose its own back-off.
3. `year` reflects the first (preprint) version, not the venue year, and `publicationTypes` is mislabelled. Do not use either for year or venue checks without cross-checking dblp or Crossref.
4. A "DOI" in `externalIds` can be the arXiv DataCite DOI, which is not a venue DOI.
5. Author names may be initials-only. Compare surnames only.
6. The licence forbids redistributing raw responses. Fixtures for tests must be **synthetic**, and any on-disk cache stays in the user's local cache directory, never in the repo.

## Recommendation for the adapter

- **Role:** **optional, best-effort** enrichment. It is mainly useful for:
  - linking arXiv to venue (externalIds ArXiv + DOI + DBLP)
  - a "does this title exist anywhere" sanity check through `search/match`, where a 404 is a clean "not found"

  Never make it the sole basis for "reference not found". Treat 404 or 429 as **inconclusive** unless dblp, Crossref or arXiv agree.
- **Endpoints:**
  - Known IDs: one `POST /paper/batch` per bibliography, chunked at ≤ 500 IDs (the documented maximum, not tested here), with an explicit `fields=` list.
  - Title-only references that other sources could not resolve: `GET /paper/search/match`.
- **Rate settings (anonymous):** one connection and **≥ 3 s between calls**.
  - On 429, back off 10 s and retry **once**. On a second 429, mark the source unavailable for the rest of the run with `source_unavailable(reason="rate_limited")` and do not retry further.
  - Keep a per-run cap of about 20 anonymous calls.
- **With an API key** (`S2_API_KEY` environment variable, sent as `x-api-key`, never logged): S2 documents a dedicated rate of about 1 request/s for keyed clients. Switch spacing to 1.1 s and raise the per-run cap. Recommend that users request a free key.
- **Unavailable detection:** 429, 5xx, timeout (15 s), or a non-JSON 200, meaning a CloudFront error page. A 404 with `{"error":"Title match not found"}` or `"Paper with id … not found"` is a definitive "not in S2". Treat it as weak negative evidence only.
- **Cache:**
  - Persist only **derived facts** in the local user cache (`~/.cache/paper-preflight`), e.g. `paperId`, `externalIds` and the match/no-match decision with a timestamp. Use a 7-day TTL.
  - Never write raw S2 JSON to the repo, test fixtures or shared reports.

## Open questions

- What is the current documented keyed rate (1 request/s?) and the batch limit (500 IDs / 10 MB?) for 2026? Confirm in the S2 API docs and licence before W1. Also confirm whether caching derived identifiers locally is allowed under the licence.
- Should the tool ship with S2 disabled by default and enable it only when `S2_API_KEY` is set? The anonymous failure rate suggests yes, with `--allow-anonymous-s2` as an opt-in.
- Can `search/match` return a confidently wrong single best match for near-duplicate titles, e.g. "Attention Is All You Need In Speech Separation"? Test in W1 with negative fixtures. The match score alone is not calibrated.
