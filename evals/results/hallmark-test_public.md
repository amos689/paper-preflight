# HALLMARK evaluation

- **Tool:** paper-preflight 1.0.0 (commit 0afb1b9, before the version bump)
- **Data:** HALLMARK v1.2.3, split `test_public`
- **Run:** 2026-10-15, 5.4 min, live sources
- **Unavailable during the run:** none
- **Unparsed entries:** 0

## Summary (main types; stress types reported separately)

| Mode | Precision | Recall | F1 | False-positive rate | Coverage |
|---|---|---|---|---|---|
| fabrication | 99.0% | 50.2% | 66.7% | 0.6% | 97.7% |
| any_issue | 98.5% | 93.5% | 95.9% | 1.9% | 97.7% |

## fabrication: outcomes by hallucination type

For VALID entries a flag is a false positive; for the others, clean is a miss.

| Type | Tier | n | Flagged | Clean | Abstained |
|---|---|---|---|---|---|
| VALID | – | 312 | 0.6% | 99.4% | 0.0% |
| fabricated_doi | 1 | 29 | 100.0% | 0.0% | 0.0% |
| future_date | 1 | 29 | 0.0% | 100.0% | 0.0% |
| nonexistent_venue | 1 | 37 | 0.0% | 100.0% | 0.0% |
| placeholder_authors | 1 | 33 | 87.9% | 6.1% | 6.1% |
| chimeric_title | 2 | 23 | 52.2% | 43.5% | 4.3% |
| hybrid_fabrication | 2 | 29 | 93.1% | 0.0% | 6.9% |
| merged_citation (stress) | 2 | 29 | 62.1% | 27.6% | 10.3% |
| partial_author_list (stress) | 2 | 31 | 3.2% | 96.8% | 0.0% |
| preprint_as_published | 2 | 29 | 0.0% | 100.0% | 0.0% |
| swapped_authors | 2 | 63 | 68.3% | 27.0% | 4.8% |
| wrong_venue | 2 | 34 | 0.0% | 100.0% | 0.0% |
| arxiv_version_mismatch (stress) | 3 | 45 | 4.4% | 95.6% | 0.0% |
| near_miss_title | 3 | 40 | 17.5% | 77.5% | 5.0% |
| plausible_fabrication | 3 | 68 | 89.7% | 0.0% | 10.3% |

## any_issue: outcomes by hallucination type

For VALID entries a flag is a false positive; for the others, clean is a miss.

| Type | Tier | n | Flagged | Clean | Abstained |
|---|---|---|---|---|---|
| VALID | – | 312 | 1.9% | 98.1% | 0.0% |
| fabricated_doi | 1 | 29 | 100.0% | 0.0% | 0.0% |
| future_date | 1 | 29 | 100.0% | 0.0% | 0.0% |
| nonexistent_venue | 1 | 37 | 97.3% | 2.7% | 0.0% |
| placeholder_authors | 1 | 33 | 93.9% | 0.0% | 6.1% |
| chimeric_title | 2 | 23 | 95.7% | 0.0% | 4.3% |
| hybrid_fabrication | 2 | 29 | 93.1% | 0.0% | 6.9% |
| merged_citation (stress) | 2 | 29 | 89.7% | 0.0% | 10.3% |
| partial_author_list (stress) | 2 | 31 | 93.5% | 6.5% | 0.0% |
| preprint_as_published | 2 | 29 | 100.0% | 0.0% | 0.0% |
| swapped_authors | 2 | 63 | 93.7% | 1.6% | 4.8% |
| wrong_venue | 2 | 34 | 88.2% | 11.8% | 0.0% |
| arxiv_version_mismatch (stress) | 3 | 45 | 91.1% | 8.9% | 0.0% |
| near_miss_title | 3 | 40 | 85.0% | 10.0% | 5.0% |
| plausible_fabrication | 3 | 68 | 89.7% | 0.0% | 10.3% |
