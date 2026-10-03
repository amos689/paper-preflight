# HALLMARK evaluation

- **Tool:** paper-preflight 0.0.1.dev0
- **Data:** HALLMARK v1.2.3, split `dev_public`
- **Run:** 2026-10-03, 1.9 min, live sources
- **Unavailable during the run:** none
- **Unparsed entries:** 0
- **Note:** the live run predates `evals/hallmark_disputed.toml`; the summary without disputed labels comes from replaying it from the cache (`--offline`), which reproduced every per-type result.

## Summary (main types; stress types reported separately)

| Mode | Precision | Recall | F1 | False-positive rate | Coverage |
|---|---|---|---|---|---|
| fabrication | 98.0% | 49.9% | 66.1% | 1.0% | 96.6% |
| any_issue | 97.0% | 72.9% | 83.3% | 2.1% | 96.6% |

## Summary without the 11 disputed labels

The same run, leaving out 11 entries labelled VALID that are not correct citations (each checked by hand; see `evals/hallmark_disputed.toml`).

| Mode | Precision | Recall | F1 | False-positive rate | Coverage |
|---|---|---|---|---|---|
| fabrication | 100.0% | 49.9% | 66.6% | 0.0% | 96.6% |
| any_issue | 100.0% | 72.9% | 84.3% | 0.0% | 96.6% |

## fabrication: outcomes by hallucination type

For VALID entries a flag is a false positive; for the others, clean is a miss.

| Type | Tier | n | Flagged | Clean | Abstained |
|---|---|---|---|---|---|
| VALID | – | 513 | 1.0% | 99.0% | 0.0% |
| fabricated_doi | 1 | 38 | 100.0% | 0.0% | 0.0% |
| future_date | 1 | 30 | 0.0% | 100.0% | 0.0% |
| nonexistent_venue | 1 | 39 | 0.0% | 100.0% | 0.0% |
| placeholder_authors | 1 | 41 | 92.7% | 2.4% | 4.9% |
| chimeric_title | 2 | 47 | 36.2% | 53.2% | 10.6% |
| hybrid_fabrication | 2 | 26 | 80.8% | 0.0% | 19.2% |
| merged_citation (stress) | 2 | 30 | 53.3% | 20.0% | 26.7% |
| partial_author_list (stress) | 2 | 32 | 3.1% | 87.5% | 9.4% |
| preprint_as_published | 2 | 30 | 0.0% | 100.0% | 0.0% |
| swapped_authors | 2 | 67 | 65.7% | 26.9% | 7.5% |
| wrong_venue | 2 | 47 | 6.4% | 91.5% | 2.1% |
| arxiv_version_mismatch (stress) | 3 | 49 | 0.0% | 95.9% | 4.1% |
| near_miss_title | 3 | 52 | 38.5% | 53.8% | 7.7% |
| plausible_fabrication | 3 | 78 | 84.6% | 0.0% | 15.4% |

## any_issue: outcomes by hallucination type

For VALID entries a flag is a false positive; for the others, clean is a miss.

| Type | Tier | n | Flagged | Clean | Abstained |
|---|---|---|---|---|---|
| VALID | – | 513 | 2.1% | 97.9% | 0.0% |
| fabricated_doi | 1 | 38 | 100.0% | 0.0% | 0.0% |
| future_date | 1 | 30 | 100.0% | 0.0% | 0.0% |
| nonexistent_venue | 1 | 39 | 0.0% | 100.0% | 0.0% |
| placeholder_authors | 1 | 41 | 95.1% | 0.0% | 4.9% |
| chimeric_title | 2 | 47 | 89.4% | 0.0% | 10.6% |
| hybrid_fabrication | 2 | 26 | 80.8% | 0.0% | 19.2% |
| merged_citation (stress) | 2 | 30 | 73.3% | 0.0% | 26.7% |
| partial_author_list (stress) | 2 | 32 | 6.2% | 84.4% | 9.4% |
| preprint_as_published | 2 | 30 | 73.3% | 26.7% | 0.0% |
| swapped_authors | 2 | 67 | 85.1% | 7.5% | 7.5% |
| wrong_venue | 2 | 47 | 46.8% | 51.1% | 2.1% |
| arxiv_version_mismatch (stress) | 3 | 49 | 83.7% | 12.2% | 4.1% |
| near_miss_title | 3 | 52 | 46.2% | 46.2% | 7.7% |
| plausible_fabrication | 3 | 78 | 84.6% | 0.0% | 15.4% |
