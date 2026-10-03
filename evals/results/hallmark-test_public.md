# HALLMARK evaluation

- **Tool:** paper-preflight 0.1.2 candidate, commit 43a5544 (main after #98)
- **Data:** HALLMARK v1.2.3, split `test_public`
- **Run:** 2026-10-03, live sources (answers from the local cache of earlier live runs)
- **Unavailable during the run:** none
- **Unparsed entries:** 0

## Summary (main types; stress types reported separately)

| Mode | Precision | Recall | F1 | False-positive rate | Coverage |
|---|---|---|---|---|---|
| fabrication | 99.0% | 49.0% | 65.6% | 0.6% | 97.0% |
| any_issue | 97.9% | 88.9% | 93.2% | 2.6% | 97.0% |

## fabrication: outcomes by hallucination type

For VALID entries a flag is a false positive; for the others, clean is a miss.

| Type | Tier | n | Flagged | Clean | Abstained |
|---|---|---|---|---|---|
| VALID | – | 312 | 0.6% | 99.4% | 0.0% |
| fabricated_doi | 1 | 29 | 100.0% | 0.0% | 0.0% |
| future_date | 1 | 29 | 0.0% | 100.0% | 0.0% |
| nonexistent_venue | 1 | 37 | 0.0% | 100.0% | 0.0% |
| placeholder_authors | 1 | 33 | 87.9% | 6.1% | 6.1% |
| chimeric_title | 2 | 23 | 47.8% | 43.5% | 8.7% |
| hybrid_fabrication | 2 | 29 | 93.1% | 0.0% | 6.9% |
| merged_citation (stress) | 2 | 29 | 62.1% | 27.6% | 10.3% |
| partial_author_list (stress) | 2 | 31 | 3.2% | 93.5% | 3.2% |
| preprint_as_published | 2 | 29 | 0.0% | 100.0% | 0.0% |
| swapped_authors | 2 | 63 | 65.1% | 27.0% | 7.9% |
| wrong_venue | 2 | 34 | 0.0% | 100.0% | 0.0% |
| arxiv_version_mismatch (stress) | 3 | 45 | 4.4% | 95.6% | 0.0% |
| near_miss_title | 3 | 40 | 17.5% | 77.5% | 5.0% |
| plausible_fabrication | 3 | 68 | 86.8% | 0.0% | 13.2% |

## any_issue: outcomes by hallucination type

For VALID entries a flag is a false positive; for the others, clean is a miss.

| Type | Tier | n | Flagged | Clean | Abstained |
|---|---|---|---|---|---|
| VALID | – | 312 | 2.6% | 97.4% | 0.0% |
| fabricated_doi | 1 | 29 | 100.0% | 0.0% | 0.0% |
| future_date | 1 | 29 | 100.0% | 0.0% | 0.0% |
| nonexistent_venue | 1 | 37 | 75.7% | 24.3% | 0.0% |
| placeholder_authors | 1 | 33 | 93.9% | 0.0% | 6.1% |
| chimeric_title | 2 | 23 | 91.3% | 0.0% | 8.7% |
| hybrid_fabrication | 2 | 29 | 93.1% | 0.0% | 6.9% |
| merged_citation (stress) | 2 | 29 | 89.7% | 0.0% | 10.3% |
| partial_author_list (stress) | 2 | 31 | 9.7% | 87.1% | 3.2% |
| preprint_as_published | 2 | 29 | 100.0% | 0.0% | 0.0% |
| swapped_authors | 2 | 63 | 90.5% | 1.6% | 7.9% |
| wrong_venue | 2 | 34 | 88.2% | 11.8% | 0.0% |
| arxiv_version_mismatch (stress) | 3 | 45 | 91.1% | 8.9% | 0.0% |
| near_miss_title | 3 | 40 | 70.0% | 25.0% | 5.0% |
| plausible_fabrication | 3 | 68 | 86.8% | 0.0% | 13.2% |
