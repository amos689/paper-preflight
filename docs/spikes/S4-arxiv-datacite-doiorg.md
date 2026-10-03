# S4 — arXiv API, DataCite REST, doi.org (doiRA, Handle API, content negotiation)

- Date: 2026-10-03 (UTC 01:58–02:00). Client in Australia.
- Requests:
  - arXiv: 9, one connection, ≥ 3.2 s apart
  - DataCite: 6
  - doi.org: 9, including 2 redirected content-negotiation calls, ≥ 1.1 s apart
- Scripts and raw data: `.spikes/api/s4_arxiv.py`, `.spikes/api/s4_datacite_doiorg.py`, `.spikes/api/raw/s4_*` (git-ignored)

## Purpose

Settle three questions for W0:

- How to resolve arXiv IDs, including version titles, journal_ref and withdrawn papers.
- What DataCite returns for arXiv DOIs.
- How to tell "DOI does not exist" apart from "DOI exists at another registration agency" cheaply and in batch.

## Method

- arXiv: `GET https://export.arxiv.org/api/query`, with these parameters:
  - `id_list=1706.03762,1512.03385,1810.04805,1412.6980,2106.09685,1606.08415,2309.16588,2503.11651` (8 IDs, one call)
  - `id_list=1606.08415v1,…,v5`, plus a non-existent ID `1706.99999` and a malformed ID `1706.0376x`
  - title searches: `search_query=ti:"Attention Is All You Need"`, `ti:"Gaussian Error Linear Units"`, and `ti:"Quantum Gradient Folding" AND au:Lindqvist`
  - withdrawn papers: `search_query=co:"withdrawn"&sortBy=submittedDate&sortOrder=descending`, then `id_list=2609.32356v1,2609.32356v3,1207.7214`
- DataCite:
  - `GET https://api.datacite.org/dois/10.48550/arXiv.1706.03762` (and `/1606.08415`, a non-existent arXiv DOI, and a Crossref DOI)
  - `GET /dois?query=doi:("…" OR "…")`
  - `GET /dois?ids=a,b`
- doi.org:
  - `GET https://doi.org/doiRA/<d1>,<d2>,…` with 6 DOIs
  - `GET https://doi.org/api/handles/<doi>?type=URL`
  - `GET https://doi.org/<doi>` with `Accept: application/vnd.citationstyles.csl+json`, for a Crossref DOI, a DataCite DOI, a non-existent DOI and the escaped TACL DOI

## Observations — arXiv

- **Transport.** `server: Google Frontend` with `via: 1.1 google, 1.1 varnish ×3` and `x-cache: MISS`. Responses are `application/atom+xml`. **No 429 in 9 calls** at about 3.2 s spacing, and no rate-limit headers. Latency: median 0.39 s, max 2.0 s (one `ti:` search).
- **Multi-ID call.** One request returned all 8 entries, **but not in `id_list` order** (1512.03385 came first). Map results by `<id>`.
- **Per-entry fields:**
  - `<id>http://arxiv.org/abs/1706.03762v7</id>`: the latest version is encoded in the ID.
  - `<published>`: the v1 date (2017-06-12).
  - `<updated>`: the date of the version returned (2023-08-02 for v7).
  - `<title>` contains line breaks, so collapse whitespace.
  - `<author><name>` keeps raw spacing, e.g. `" The ATLAS Collaboration"` with a leading space.
  - `<arxiv:comment>` often carries the venue, e.g. "CVPR 2025, Project Page: …" or "Published as a conference paper at the 3rd International Conference for Learning…".
- **`journal_ref` and `arxiv:doi`.** These are empty for all 8 test papers, because the authors never set them. They are populated when authors do set them: `1207.7214` has `journal_ref "Phys.Lett. B716 (2012) 1-29"`, `arxiv:doi 10.1016/j.physletb.2012.08.020`, and a `<link title="doi" href="https://doi.org/…">`.
- **Per-version titles.** Request versioned IDs in one call; each entry's `updated` is that version's date.

  | Version | Title | updated |
  |---|---|---|
  | 1606.08415v1 | Bridging Nonlinearities and Stochastic Regularizers with Gaussian Error Linear Units | 2016-06-27 |
  | v2 | (same as v1) | 2016-07-08 |
  | v3 | Gaussian Error Linear Units (GELUs) | 2018-11-11 |
  | v4 | (same as v3) | 2020-07-08 |
  | v5 | (same as v3) | 2023-06-06 |

- **Non-existent and malformed IDs.** `1706.99999` and `1706.0376x` both return **HTTP 200** with `opensearch:totalResults 0` and no `<entry>`. There is no error entry. "Not found" equals "ID missing from the returned feed".
- **Title search.**
  - `ti:"Attention Is All You Need"`: 36 results, target first.
  - `ti:"Gaussian Error Linear Units"`: 2 results, target first.
  - The fabricated title with its author: 0 results.
  - Results are relevance-ranked, but phrase queries need the exact current title.
- **Withdrawn papers.**
  - There is **no structured flag**. `co:"withdrawn"` matches 7,282 papers.
  - The withdrawal shows only in the latest version's `<arxiv:comment>`, e.g. "This paper is withdrawn. The manuscript is incomplete…" or "Withdrawn by the authors: …".
  - The v1 entry keeps full metadata and the abstract is unchanged, and a PDF link is still emitted for the withdrawn version.

## Observations — DataCite

- `GET /dois/10.48550/arXiv.1706.03762` returned 200 in 1.2 s; repeat calls took about 0.3 s. Server: `nginx + Passenger`; **no rate-limit headers**, only `x-request-id`.
- **Attributes of an arXiv DOI record:**
  - `doi`: lower-cased (`"10.48550/arxiv.1706.03762"`)
  - `titles`: **latest version only** (GELU gives "Gaussian Error Linear Units (GELUs)")
  - `creators[]`: in order, `nameType: Personal`, with `givenName` and `familyName`
  - `publicationYear`: 2017; `publisher`: "arXiv"
  - `types.resourceTypeGeneral`: `Preprint`, with citeproc type `article`
  - `version`: `"7"` (GELU has `5`)
  - `dates[]`: `Submitted` and `Updated` entries per version, tagged by `dateInformation: "v1".."v7"`
  - `url`: `https://arxiv.org/abs/1706.03762`
  - `subjects`: arXiv categories
  - `relatedIdentifiers`: **`[]`**. There are no IsVersionOf or IsPreprintOf links to the published version.
- **Not found.** Both a non-existent arXiv DOI and a Crossref DOI asked of DataCite return **404** `{"errors":[{"status":"404","title":"The resource you are looking for doesn't exist."}]}`.
- **Batch.**
  - `/dois?query=doi:("10.48550/arxiv.1706.03762" OR "…1810.04805" OR "…2106.09685")&fields[dois]=doi,titles,publicationYear,creators,version` returned 3 of 3 in 1.24 s.
  - `/dois?ids=10.48550/arxiv.1706.03762,10.48550/arxiv.1810.04805` returned 2 of 2 in 0.33 s.
  - Sparse fieldsets (`fields[dois]=`) work.

## Observations — doi.org

**doiRA, multi-DOI.** One call (0.44 s, Cloudflare) answered all 6 DOIs, **in input order**:

```json
[{"DOI":"10.1109/CVPR.2016.90","RA":"Crossref"},
 {"DOI":"10.48550/arXiv.1706.03762","RA":"DataCite"},
 {"DOI":"10.1162/tacl_a_00276","RA":"Crossref"},
 {"DOI":"10.1162/tacl\\_a\\_00276","status":"DOI does not exist"},
 {"DOI":"10.1109/CVPR.2016.999999","status":"DOI does not exist"},
 {"DOI":"10.99999/nonexistent-prefix","status":"DOI does not exist"}]
```

**Handle API.** `GET https://doi.org/api/handles/<doi>?type=URL` takes about 0.22 s:

- Existing DOI: **200** `{"responseCode":1,"handle":"10.1109/CVPR.2016.90","values":[{"type":"URL","data":{"value":"http://ieeexplore.ieee.org/document/7780459/"},…}]}`
- Missing DOI, including the escaped TACL DOI: **404** `{"responseCode":100,"handle":"…"}`

**Content negotiation** (`Accept: application/vnd.citationstyles.csl+json`):

- **Crossref DOI.**
  - doi.org answers **302** to `https://api.crossref.org/v1/works/10.1109%2FCVPR.2016.90/transform`, which returns 200 `application/vnd.citationstyles.csl+json` in 0.92 s in total.
  - The response carries Crossref's `x-api-pool: public-single` headers, so it **counts against the Crossref pool**.
  - The body is CSL plus Crossref extras: `title` and `container-title` as strings, `author[].sequence`, `issued`, `DOI` lower-cased, and `relation`.
- **DataCite DOI.**
  - **302** to `https://data.crosscite.org/10.48550%2FarXiv.1706.03762`, then 200 in 1.6 s.
  - CSL fields: `type` "article", `version` "7", `publisher` "arXiv", `DOI` "10.48550/ARXIV.1706.03762" (**upper-cased**), and no `container-title`.
- **Missing or escaped DOI.** **404** `text/html` with the doi.org page "Error: DOI Not Found" (10 KB).

## Pitfalls found

1. arXiv returns entries in arbitrary order, and missing IDs are just absent with HTTP 200. Map by ID and treat absence as "not found".
2. arXiv, DataCite and dblp disagree on titles when a title changed: dblp keeps v1 (S1), while arXiv-latest, DataCite and OpenAlex have the current title. **A citation may legitimately use either title.** Fetch all versions' titles from arXiv before reporting a mismatch.
3. Withdrawal shows only as free-text in `<arxiv:comment>`, with no machine flag. Also, `journal_ref` and `arxiv:doi` are mostly empty for ML papers, so arXiv alone cannot link to the venue version.
4. DataCite arXiv records have no `relatedIdentifiers`, so they cannot link arXiv to the published version either.
5. DOI case differs by source: DataCite REST is lower-case, DataCite CSL upper-case, Crossref lower-case, dblp upper-case. Always compare case-insensitively.
6. Content negotiation through doi.org silently consumes the Crossref rate pool and adds a redirect hop. Calling the agency API directly is cheaper.
7. LaTeX-escaped DOIs (`\_`) are "DOI does not exist" everywhere: Crossref, DataCite, doiRA, the Handle API and S2. The escape must be undone client-side.

## Recommendation for the adapter

**arXiv adapter:**

- Endpoint `https://export.arxiv.org/api/query?id_list=<≤ 50 ids>&max_results=<n>`.
- **One connection, ≥ 3 s between calls**, following arXiv's API terms.
- Batch all arXiv IDs from a bibliography into as few calls as possible.
- For title-mismatch checks, issue one extra call with all versioned IDs `<id>v1…v<latest>` and collect the set of historical titles.
- Use title search (`ti:"…"`) only as a fallback for unresolved CS references.
- Withdrawn detection: run `re.search(r"\bwithdraw", comment, re.I)` on the latest version and report it as "possibly withdrawn" (warning, not error).
- Unavailable: timeout (20 s), 5xx or 429, or a non-Atom body.
- Cache: entries for 7 days, version titles for 30 days (old versions are immutable).

**DataCite adapter:**

- Use `GET /dois?ids=<comma list>&fields[dois]=doi,titles,creators,publicationYear,version,types,url` for any DOIs that doiRA says are DataCite (arXiv, Zenodo, and others).
- Single lookup: `GET /dois/<doi>`. 404 JSON means not a DataCite DOI.
- No published limits: stay at 1 request/s.
- Cache for 7 days.

**DOI existence checks via doi.org:**

1. Normalise the DOI: undo LaTeX escapes, strip the URL prefix and trailing punctuation.
2. Run **one `doiRA` call for the whole bibliography**. Chunk it at about 50 DOIs to keep URLs under about 4 KB; this limit is untested.
3. Route each DOI by the answer: `RA: Crossref` → Crossref adapter; `RA: DataCite` → DataCite adapter; another RA (mEDRA, JaLC, KISTI, …) → content negotiation fallback; `status: "DOI does not exist"` → **error "DOI not registered"**. If the original string contained a LaTeX escape and the unescaped form exists, downgrade this to a warning.
4. Use the Handle API (`responseCode` 1 vs 100) as a per-DOI confirmation when doiRA is ambiguous or unavailable.

Further doi.org rules:

- Use content negotiation only for agencies without a direct adapter.
- Unavailable: network error, 5xx, 429, or a Cloudflare HTML page on a 200 for `doiRA` or `api/handles`.
- Cache: positive doiRA results for 30 days; negative results for 1 day, since a DOI may have just been registered.

## Open questions

- What is the maximum number of DOIs per `doiRA` call, and does doi.org rate-limit it? Neither is documented; ask DOI Foundation support or probe gently in W1.
- Should a "withdrawn" heuristic also inspect the abstract and title (e.g. "This paper has been withdrawn")? We need a few known withdrawn CS examples for tests, kept as synthetic fixtures.
- DataCite's `ids=` parameter: what are the page size and maximum batch size? Untested beyond 2 IDs, but `query=doi:(… OR …)` also works.
- arXiv now runs behind Google Frontend and varnish. Do the API's rate limits and 429 behaviour differ from the classic export server? We saw no 429 at 1 request per 3.2 s.
