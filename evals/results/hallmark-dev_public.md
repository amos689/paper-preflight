# HALLMARK evaluation

- **Tool:** paper-preflight 0.6.0 (main a418bad)
- **Data:** HALLMARK v1.2.3, split `dev_public`
- **Run:** 2026-10-08, 0.1 min, live sources
- **Unavailable during the run:** none
- **Unparsed entries:** 0

## Summary (main types; stress types reported separately)

| Mode | Precision | Recall | F1 | False-positive rate | Coverage |
|---|---|---|---|---|---|
| fabrication | 98.2% | 53.7% | 69.5% | 1.0% | 98.9% |
| any_issue | 97.6% | 91.7% | 94.6% | 2.1% | 98.9% |

## Summary without the 11 disputed labels

The same run, leaving out 11 entries labelled VALID that are not correct citations (each checked by hand; see `evals/hallmark_disputed.toml`).

| Mode | Precision | Recall | F1 | False-positive rate | Coverage |
|---|---|---|---|---|---|
| fabrication | 100.0% | 53.7% | 69.9% | 0.0% | 98.9% |
| any_issue | 100.0% | 91.7% | 95.7% | 0.0% | 98.9% |

## fabrication: outcomes by hallucination type

For VALID entries a flag is a false positive; for the others, clean is a miss.

| Type | Tier | n | Flagged | Clean | Abstained |
|---|---|---|---|---|---|
| VALID | – | 513 | 1.0% | 99.0% | 0.0% |
| fabricated_doi | 1 | 38 | 100.0% | 0.0% | 0.0% |
| future_date | 1 | 30 | 0.0% | 100.0% | 0.0% |
| nonexistent_venue | 1 | 39 | 0.0% | 100.0% | 0.0% |
| placeholder_authors | 1 | 41 | 97.6% | 2.4% | 0.0% |
| chimeric_title | 2 | 47 | 44.7% | 53.2% | 2.1% |
| hybrid_fabrication | 2 | 26 | 96.2% | 0.0% | 3.8% |
| merged_citation (stress) | 2 | 30 | 76.7% | 20.0% | 3.3% |
| partial_author_list (stress) | 2 | 32 | 3.1% | 87.5% | 9.4% |
| preprint_as_published | 2 | 30 | 0.0% | 100.0% | 0.0% |
| swapped_authors | 2 | 67 | 71.6% | 26.9% | 1.5% |
| wrong_venue | 2 | 47 | 6.4% | 93.6% | 0.0% |
| arxiv_version_mismatch (stress) | 3 | 49 | 0.0% | 100.0% | 0.0% |
| near_miss_title | 3 | 52 | 40.4% | 59.6% | 0.0% |
| plausible_fabrication | 3 | 78 | 89.7% | 0.0% | 10.3% |

## any_issue: outcomes by hallucination type

For VALID entries a flag is a false positive; for the others, clean is a miss.

| Type | Tier | n | Flagged | Clean | Abstained |
|---|---|---|---|---|---|
| VALID | – | 513 | 2.1% | 97.9% | 0.0% |
| fabricated_doi | 1 | 38 | 100.0% | 0.0% | 0.0% |
| future_date | 1 | 30 | 100.0% | 0.0% | 0.0% |
| nonexistent_venue | 1 | 39 | 71.8% | 28.2% | 0.0% |
| placeholder_authors | 1 | 41 | 100.0% | 0.0% | 0.0% |
| chimeric_title | 2 | 47 | 97.9% | 0.0% | 2.1% |
| hybrid_fabrication | 2 | 26 | 96.2% | 0.0% | 3.8% |
| merged_citation (stress) | 2 | 30 | 96.7% | 0.0% | 3.3% |
| partial_author_list (stress) | 2 | 32 | 6.2% | 84.4% | 9.4% |
| preprint_as_published | 2 | 30 | 100.0% | 0.0% | 0.0% |
| swapped_authors | 2 | 67 | 97.0% | 1.5% | 1.5% |
| wrong_venue | 2 | 47 | 76.6% | 23.4% | 0.0% |
| arxiv_version_mismatch (stress) | 3 | 49 | 89.8% | 10.2% | 0.0% |
| near_miss_title | 3 | 52 | 86.5% | 13.5% | 0.0% |
| plausible_fabrication | 3 | 78 | 89.7% | 0.0% | 10.3% |
