# S3 — OpenAlex (keyless)

- Date: 2026-10-03 (UTC 01:55–01:58). Client in Australia; responses came through Cloudflare's MEL POP.
- Requests: 24, at least 1.1 s apart, keyless, no `mailto`. Total spend: **$0.0103** of the $0.10 daily keyless budget.
- Scripts and raw data: `.spikes/api/s3_openalex.py`, `.spikes/api/raw/s3_openalex/`, `.spikes/api/log_s3_openalex.jsonl` (git-ignored)

## Purpose

Measure the cost and budget mechanics of keyless OpenAlex, and check OpenAlex as a source for:

- DOI lookup, single and batched
- title search
- retraction flags
- author lists
- preprint-to-published linking

## Method

- Singleton lookups: `GET https://api.openalex.org/works/doi:<doi>` for CVPR, BERT, Wakefield, TACL, the escaped TACL DOI, the arXiv DOI `10.48550/arXiv.1706.03762`, and a non-existent DOI. Also `GET /works/https://doi.org/<doi>`, and `GET /works/W…` for three work IDs.
- OR-batch: `GET /works?filter=doi:A|B|C|…&select=…&per_page=50`. One batch held 7 mixed DOIs, another 5 arXiv DOIs.
- Title search: `GET /works?filter=title.search:<title>&select=…&per_page=8` for titles 1–6 and 8, ICLR 2024 *Vision Transformers Need Registers* and CVPR 2025 *VGGT*. Also `GET /works?search=<title>`.
- `select=id,doi,title,type,publication_year,publication_date,is_retracted,ids,authorships,primary_location,locations,locations_count`
- Docs consulted: help.openalex.org "Example costs", "Pricing" and "Rate limits and authentication".

## Observations

### Budget and rate headers (every response)

```
x-ratelimit-limit: 1000            x-ratelimit-remaining: 897        (credits; 1 credit = $0.0001)
x-ratelimit-limit-usd: 0.1         x-ratelimit-remaining-usd: 0.0897
x-ratelimit-cost-usd: 0.001        x-ratelimit-credits-used: 10      (cost of THIS request)
x-ratelimit-reset: 79351           (seconds to midnight UTC)
x-ratelimit-prepaid-remaining-usd: 0   x-ratelimit-onetime-remaining: 0
```

- `access-control-expose-headers` also lists `X-RateLimit-Credits-Required`, `X-RateLimit-Cost-Required-USD` and `Retry-After`. These presumably appear on budget-exceeded responses; we did not see them.
- List responses also include `meta.cost_usd`, `meta.db_response_time_ms` and `meta.x_query.oql`, a normalised query echo.
- Infrastructure: Cloudflare, then `via: 2.0 heroku-router`. Latency: median 0.55 s, p90 1.16 s.

### Cost class per call (observed)

| Call | Cost (USD) | Credits |
|---|---|---|
| `/works/doi:<doi>` (singleton), including 404s | **0** | 0 |
| `/works/W<id>` (singleton) | **0** | 0 |
| `/works/https://doi.org/<doi>` (URL-form singleton) | **0.0001** | 1 (unexpected: use the `doi:` form) |
| `/works?filter=doi:A\|B\|…` (list + filter) | 0.0001 | 1 |
| `/works?filter=title.search:…` | **0.001** | 10 |
| `/works?search=…` (internally `fulltext.search`; db time 317 ms vs 9–24 ms) | 0.001 | 10 |

- These match the documented price list: get-single is free, list+filter is $0.10 per 1k, search is $1 per 1k.
- Keyless budget: **$0.10/day = 1000 list calls or 100 searches**; singletons are unlimited by cost. A free key gives $1/day (10×).
- The docs say that exceeding the budget, or more than 100 requests/s, returns **429**. We did not exhaust the budget (not polite), so the exact 429 body and headers are unverified.

### DOI lookups

| Input | Result |
|---|---|
| CVPR `doi:10.1109/CVPR.2016.90` | 200, `W2194775991`, `conference-paper`, 2016. Locations: the DOI, plus a stray "masterThesis" repository copy. **No arXiv location** |
| BERT `doi:10.18653/v1/N19-1423` | 200, `W2963341956`, 1 location only. **No arXiv location** |
| Wakefield | 200, **`is_retracted: true`**, title "RETRACTED: Ileal-lymphoid-…", 13 authorships, PubMed id present |
| TACL `doi:10.1162/tacl_a_00276` | 200, 18 authorships |
| Escaped TACL (`tacl%5C_a%5C_00276`) | 404, HTML Flask-style page |
| `doi:10.48550/arXiv.1706.03762` | **404** (see the pollution note below) |
| Non-existent DOI | 404, HTML |

Returned DOIs are lower-cased URLs, e.g. `https://doi.org/10.1109/cvpr.2016.90`.

### OR-batch

- 7 DOIs (4 Crossref, 2 arXiv, 1 bogus) in one call returned 4 results for $0.0001, with a db time of 24 ms. Missing DOIs are silently absent.
- 5 arXiv DOIs (`10.48550/arxiv.{1412.6980,1512.03385,1706.03762,1810.04805,2106.09685}`) returned 3 results:
  - Adam → `W1522301498`: correct.
  - ResNet arXiv → `W2949650786`: a separate work from the CVPR record.
  - **LoRA arXiv DOI → `W3168867926`, titled "LoRA Fine-Tuning of a 3B Code LLM for Algorithmic Efficiency"**. This is a corrupted title: the authors are the real LoRA authors, and the record has two extra Zenodo locations, `10.5281/zenodo.21850639/40`.
  - Attention and BERT arXiv DOIs: **not found**.

### Title search (`title.search`, per_page 8)

| Title | Count | Outcome |
|---|---|---|
| t1 Attention | 254 | Top hit `W2626778328` "Attention Is All You Need", but its **`doi` is `10.65215/2q58a426`, `type: preprint`, `publication_year: 2025`** (see below) |
| t2 ResNet | 17 | CVPR work (rank 1) and arXiv work `W2949650786` (rank 2) as **separate works**, with no cross-link |
| t3 BERT | 2 | The ACL work and a Japanese explainer article. **There is no arXiv BERT work** |
| t4 Adam | 5 | arXiv work only (2014). No ICLR record |
| t5 LoRA | 22 | **The real LoRA paper is not in the top 5**, because its title is corrupted (see above) |
| t6 GELU | 1 | arXiv work with the **current** title "Gaussian Error Linear Units (GELUs)" |
| t8 fabricated | **0** | Clean "not found" |
| ICLR 2024 | 7 | arXiv version only (`W4387225729`, 2023). No ICLR/OpenReview record |
| CVPR 2025 | 6 | CVPR DOI work and arXiv work, separate |

### Data pollution example: Attention Is All You Need

`GET /works/W2626778328` costs $0. It is the original MAG work, created 2017-06-23, last updated 2026-10-02. Its fields today:

- `doi`: `https://doi.org/10.65215/2q58a426`
- `publication_year`: 2025
- `type`: `preprint`
- 11 locations:
  - **8× `10.65215/*` posted-content**: the fake duplicates found in S2
  - `arxiv.org/abs/1706.03762`
  - `doi.org/10.48550/arxiv.1706.03762`
  - `arxiv.org/pdf/1706.03762v5`

The arXiv DOI survives only as a location, so `doi:` lookup on it returns 404. There is **no NeurIPS location**.

### Authorships

- Counts match Crossref: Wakefield 13/13 and TACL 18/18. `is_authors_truncated` was absent on singletons.
- `author_position` is first/middle/last.
- `author.display_name`, which comes from OpenAlex disambiguation, is sometimes wrong. Examples, with `raw_author_name` first:
  - "M Malik" became **"Muhammad Moiz Malik"**
  - "MA Thomson" became "M.L. Thomson"
  - "Ankur Parikh" became "Ankur P. Parikh"
  - "Lu Wang" became "Wang, Lu" (inverted)
  - "Niki Parmar" became "Niki Jitendra Parmar"
- `raw_author_name` matches the publisher metadata.

## Pitfalls found

1. **Canonical records can carry a wrong DOI, year and type** (Attention → 10.65215, 2025, preprint) or a **wrong title** (LoRA arXiv → "LoRA Fine-Tuning of a 3B Code LLM…"). The cause appears to be merges with low-quality Crossref and Zenodo deposits. OpenAlex data must never be the sole ground truth for "the DOI, title or year of paper X".
2. **Preprint and published versions are not linked.** ResNet, VGGT and the ICLR paper exist as separate works. BERT and Attention have no arXiv-linked published work at all. Locations cannot be relied on for arXiv↔venue linking.
3. arXiv DOIs (`10.48550/…`) are not reliably resolvable through `doi:`, because merged works expose a different primary DOI.
4. The URL-form singleton (`/works/https://doi.org/…`) is billed, while the `doi:` form is free.
5. Search is ten times as expensive as filter. Keyless, about 100 title searches per day are shared by **all users behind the same IP**. A single bibliography of 100 references could exhaust it.
6. `display_name` for authors is disambiguation output and sometimes wrong. Use `raw_author_name` when comparing against the bib entry.
7. 404 bodies are HTML, not JSON.

## Recommendation for the adapter

- **Role:** a **secondary/enrichment** source, not the primary verifier. The two uses with the best value per cost are:
  1. **Retraction cross-check** through free singleton `GET /works/doi:<doi>` and `is_retracted`. This complements Crossref `updated-by` and costs $0.
  2. **Batch existence and metadata cross-check** for already-known DOIs through `filter=doi:a|b|…` (≤ 50 per call, $0.0001 per call), with a `select=` list.
- **Title search:** only when the user has configured `OPENALEX_API_KEY` (read from the environment or a config file and sent as a header or `api_key` parameter, never logged), **or** when the remaining budget is at least 3× the cost of a search. Prefer `filter=title.search:` over `search=`, and add `publication_year:<y-1>-<y+1>` to narrow results.
- **Budget guard:**
  - Read `x-ratelimit-remaining-usd` and `x-ratelimit-reset` after every response and keep a per-process budget object.
  - Before each call, skip it with `source_unavailable(reason="budget")` if `remaining_usd < cost_of_next_call`.
  - On 429, treat the source as unavailable until `now + x-ratelimit-reset` (or `Retry-After`), and do not retry.
- **Source unavailable:** 429, 5xx, timeout (15 s), or a non-JSON 200 means unavailable. A 404 on a singleton means "not in OpenAlex" (informational only).
- **Matching rules when using OpenAlex results:**
  - compare `title`, `raw_author_name`s and `publication_year` against the citation
  - if the OpenAlex `doi` prefix is denylisted (10.65215) or its year is far from the citation year, ignore the `doi` field and use only the locations list (arXiv id extraction)
- **Rate:** ≤ 1 request/s and a single connection. That is far below the documented 100 requests/s; the budget is the real limit.
- **Cache:**
  - Singleton works by DOI for 7 days, since `is_retracted` changes rarely but does change.
  - Search results for 7 days.
  - Persist the daily spend counter so repeated runs on the same day do not overspend.
- **What a key changes:** the budget rises to $1/day (10×). `X-RateLimit-Prepaid-Remaining-USD` matters only for paid plans.

## Open questions

- What does the 429 response look like once the keyless budget is exhausted? Check its body and whether `Retry-After` or `X-RateLimit-Cost-Required-USD` are present. Verify with a throwaway run on a day when the budget is otherwise unused, or ask OpenAlex.
- Is the keyless $0.10 budget per IP or global? The documentation implies per IP. Users behind a university NAT may share it.
- Should we report the 10.65215 merge and the corrupted LoRA title to OpenAlex? The project could have a lightweight "upstream data issue" log.
- Is `/works/https://doi.org/...` billing intended, or a bug? Either way, use the `doi:` form.
