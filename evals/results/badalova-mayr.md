# Head-to-head: Badalova & Mayr (2026)

- **Tool:** paper-preflight 0.1.2 candidate, commit f84e119 (main after #91)
- **Data:** 104 references from three documents, checked by hand (71 verified, 33 problematic); the five tools' results as published (Zenodo 10.5281/zenodo.21457492, CC BY 4.0). Transcribed to BibTeX as written: `evals/badalova_mayr.bib`
- **Run:** 2026-10-03, 0.0 min, live sources

## The study's labels

| Tool | Flagged | Problematic flagged | Verified flagged | Precision [95% CI] | Recall | False flags per 100 verified |
|---|---|---|---|---|---|---|
| CheckIfExist | 65 | 31 | 34 | 47.7% [36.0%, 59.6%] | 93.9% | 47.9 |
| HalluCiteChecker | 38 | 18 | 20 | 47.4% [32.5%, 62.7%] | 54.5% | 28.2 |
| Hallucinator | 57 | 29 | 28 | 50.9% [38.3%, 63.4%] | 87.9% | 39.4 |
| HalRef | 77 | 24 | 53 | 31.2% [21.9%, 42.2%] | 72.7% | 74.6 |
| RefChecker | 68 | 32 | 36 | 47.1% [35.7%, 58.8%] | 97.0% | 50.7 |
| **paper-preflight** (warnings and errors) | 41 | 29 | 12 | 70.7% [55.5%, 82.4%] | 87.9% | 16.9 |
| paper-preflight (also "cannot determine") | 55 | 33 | 22 | 60.0% [46.8%, 71.9%] | 100.0% | 31.0 |

## References with a real error counted as problematic

The study labels a reference verified when the work exists. Reviewing paper-preflight's flags on such references found 5 that carry a real error (a wrong author name, a missing title word, a broken DOI; listed below). Here they count as problematic for every tool. Only the references paper-preflight flagged were reviewed, so errors that only another tool noticed are not counted: read this table as a check of the labels, not as a fair ranking. The last row also leaves out paper-preflight's flags that are only REF015, the advice that a cited preprint has a published version.

| Tool | Flagged | Problematic flagged | Verified flagged | Precision [95% CI] | Recall | False flags per 100 verified |
|---|---|---|---|---|---|---|
| CheckIfExist | 65 | 33 | 32 | 50.8% [38.9%, 62.5%] | 86.8% | 48.5 |
| HalluCiteChecker | 38 | 18 | 20 | 47.4% [32.5%, 62.7%] | 47.4% | 30.3 |
| Hallucinator | 57 | 31 | 26 | 54.4% [41.6%, 66.6%] | 81.6% | 39.4 |
| HalRef | 77 | 28 | 49 | 36.4% [26.5%, 47.5%] | 73.7% | 74.2 |
| RefChecker | 68 | 34 | 34 | 50.0% [38.4%, 61.6%] | 89.5% | 51.5 |
| **paper-preflight** (warnings and errors) | 41 | 34 | 7 | 82.9% [68.7%, 91.5%] | 89.5% | 10.6 |
| paper-preflight (warnings and errors, without REF015 advice) | 35 | 34 | 1 | 97.1% [85.5%, 99.5%] | 89.5% | 1.5 |

The study's sample is small and was chosen to contain problems (one of the documents came from GPTZero's list of NeurIPS 2025 papers with hallucinated references), so the recall here is not representative; precision and false flags on verified references are the comparison that matters.

## Flags on references the study labels verified

| Reference | Findings | Review | Note |
|---|---|---|---|
| P1R1 | REF015 | advice | arXiv 2507.19457 (GEPA) was published at ICLR 2026. |
| P1R20 | REF015 | advice | arXiv 2505.15948 has a published version (WOOC 2025, 10.5281/zenodo.16367716). |
| P2R3 | REF003 | false_positive | A poster abstract at the 1st SciNLP workshop (2020) that no queried source indexes; the study's manual check found it. |
| P2R7 | REF011 | metadata_error | The first author of 10.1371/journal.pone.0157989 is Geraint Duck; the reference says 'Goran Duck'. |
| P3R3 | REF015 | advice | arXiv 1904.09751 (The Curious Case of Neural Text Degeneration) is ICLR 2020. |
| P3R12 | REF011 | metadata_error | DeBERTa (ICLR 2021) is by He, Xiaodong Liu, Gao and Chen; the reference says 'Weizhu Liu'. |
| P3R13 | REF015 | advice | arXiv 1804.07461 (GLUE) is BlackboxNLP@EMNLP 2018, 10.18653/v1/w18-5446. |
| P3R14 | REF012 | metadata_error | The ACL 2017 title is 'TriviaQA: A Large Scale Distantly Supervised Challenge Dataset for Reading Comprehension'; the reference drops 'Dataset'. |
| P3R33 | REF017 | metadata_error | The DOI is written '0.18653/v1/2024.acl-long.276'; the real one is 10.18653/v1/2024.acl-long.276. |
| P3R37 | REF015 | advice | arXiv 2402.03563 was published at ICML 2024. |
| P3R51 | REF011 | metadata_error | The NeurIPS 2011 paper's third author is Jeffrey Pennington; the reference says 'Jeffrey Pennin'. |
| P3R54 | REF015 | advice | arXiv 2305.19187 was published in TMLR (2024). |

## paper-preflight per reference

| Reference | Label | Verdict | Findings |
|---|---|---|---|
| P1R1 | verified | verified | REF015 |
| P1R2 | verified | cannot_determine | REF016, REF090 |
| P1R3 | verified | verified |  |
| P1R4 | problematic | not_found | REF003 |
| P1R5 | verified | cannot_determine | REF090 |
| P1R6 | verified | cannot_determine | REF090 |
| P1R7 | verified | verified |  |
| P1R8 | verified | cannot_determine | REF090 |
| P1R9 | verified | cannot_determine | REF090 |
| P1R10 | verified | verified |  |
| P1R11 | verified | verified |  |
| P1R12 | verified | verified |  |
| P1R13 | verified | verified |  |
| P1R14 | verified | verified |  |
| P1R15 | verified | verified | REF016 |
| P1R16 | problematic | metadata_mismatch | REF014, REF016 |
| P1R17 | verified | cannot_determine | REF090 |
| P1R18 | verified | verified |  |
| P1R19 | verified | cannot_determine | REF090 |
| P1R20 | verified | verified | REF015 |
| P1R21 | problematic | cannot_determine | REF090 |
| P1R22 | verified | verified |  |
| P1R23 | verified | verified |  |
| P1R24 | verified | verified |  |
| P2R1 | problematic | identifier_conflict | REF001 |
| P2R2 | verified | verified |  |
| P2R3 | verified | not_found | REF003 |
| P2R4 | verified | verified |  |
| P2R5 | verified | verified |  |
| P2R6 | problematic | cannot_determine | REF002, REF090 |
| P2R7 | verified | metadata_mismatch | REF011 |
| P2R8 | verified | verified |  |
| P2R9 | problematic | not_found | REF002, REF003 |
| P2R10 | problematic | metadata_mismatch | REF011 |
| P2R11 | verified | verified |  |
| P2R12 | verified | verified |  |
| P2R13 | verified | verified | REF011 |
| P2R14 | verified | verified |  |
| P2R15 | verified | verified | REF011 |
| P3R1 | verified | verified |  |
| P3R2 | verified | verified |  |
| P3R3 | verified | verified | REF015 |
| P3R4 | problematic | cannot_determine | REF090 |
| P3R5 | problematic | cannot_determine | REF090 |
| P3R6 | problematic | cannot_determine | REF017, REF090 |
| P3R7 | problematic | cannot_determine | REF017, REF090 |
| P3R8 | problematic | cannot_determine | REF017, REF090 |
| P3R9 | problematic | not_found | REF003 |
| P3R10 | problematic | cannot_determine | REF017, REF090 |
| P3R11 | verified | verified | REF016 |
| P3R12 | verified | metadata_mismatch | REF011 |
| P3R13 | verified | verified | REF015 |
| P3R14 | verified | metadata_mismatch | REF012, REF016 |
| P3R15 | verified | verified |  |
| P3R16 | verified | verified |  |
| P3R17 | verified | verified |  |
| P3R18 | verified | cannot_determine | REF090 |
| P3R19 | problematic | metadata_mismatch | REF011, REF013, REF014 |
| P3R20 | problematic | not_found | REF003 |
| P3R21 | problematic | not_found | REF003 |
| P3R22 | problematic | not_found | REF003 |
| P3R23 | verified | verified |  |
| P3R24 | problematic | not_found | REF003 |
| P3R25 | problematic | identifier_conflict | REF001 |
| P3R26 | problematic | not_found | REF003 |
| P3R27 | problematic | not_found | REF003 |
| P3R28 | verified | verified | REF016 |
| P3R29 | verified | verified |  |
| P3R30 | verified | verified |  |
| P3R31 | verified | verified | REF016 |
| P3R32 | verified | verified |  |
| P3R33 | verified | verified | REF016, REF017 |
| P3R34 | verified | verified | REF016 |
| P3R35 | problematic | not_found | REF003 |
| P3R36 | problematic | not_found | REF003 |
| P3R37 | verified | verified | REF015 |
| P3R38 | verified | verified |  |
| P3R39 | verified | verified |  |
| P3R40 | verified | verified | REF016 |
| P3R41 | verified | verified | REF016 |
| P3R42 | verified | verified | REF016 |
| P3R43 | verified | verified |  |
| P3R44 | verified | verified | REF016 |
| P3R45 | verified | verified |  |
| P3R46 | verified | verified |  |
| P3R47 | verified | verified | REF016 |
| P3R48 | problematic | not_found | REF003 |
| P3R49 | problematic | not_found | REF003 |
| P3R50 | problematic | cannot_determine | REF090 |
| P3R51 | verified | metadata_mismatch | REF011 |
| P3R52 | problematic | not_found | REF003 |
| P3R53 | problematic | identifier_conflict | REF001 |
| P3R54 | verified | verified | REF015 |
| P3R55 | problematic | metadata_mismatch | REF011, REF016 |
| P3R56 | verified | verified |  |
| P3R57 | problematic | metadata_mismatch | REF011, REF016 |
| P3R58 | problematic | metadata_mismatch | REF011 |
| P3R59 | problematic | metadata_mismatch | REF011 |
| P3R60 | verified | cannot_determine | REF090 |
| P3R61 | verified | cannot_determine | REF090 |
| P3R62 | verified | verified |  |
| P3R63 | verified | verified |  |
| P3R64 | verified | verified |  |
| P3R65 | verified | verified |  |
