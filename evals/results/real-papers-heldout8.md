# Real papers (heldout8 batch)

- **Tool:** paper-preflight 0.5.0, commit 47ac4e9
- **Papers:** 20 arXiv papers first submitted 2026-08-26..01, chosen mechanically (`evals/real_papers.py`, manifest `evals/real_papers_heldout8.toml`)
- **Run:** 2026-10-07, live sources (answers cached for the day, so a rerun with fixed code asks again only what changed; a cold run of 20 papers takes about 20 minutes)
- **Flags:** warnings and errors about references; every one reviewed by hand (`evals/real_papers_review.toml`)

## Summary

| References checked | Flags | Real problems | False positives | Unclear | False positives per 100 references | Cannot determine |
|---|---|---|---|---|---|---|
| 780 | 101 | 81 | 19 | 1 | 2.4 | 6% |

## By paper

| Paper | Category | References | Flags | Real | False positive | Unclear | Cannot determine |
|---|---|---|---|---|---|---|---|
| 2608.25243v1 | cs.CL | 44 | 7 | 6 | 1 | 0 | 0% |
| 2608.25276v1 | cs.CL | 48 | 7 | 5 | 2 | 0 | 10% |
| 2609.29549v1 | cs.CL | 35 | 5 | 2 | 3 | 0 | 6% |
| 2608.25267v1 | cs.LG | 59 | 3 | 3 | 0 | 0 | 5% |
| 2608.25282v1 | cs.LG | 42 | 3 | 3 | 0 | 0 | 5% |
| 2608.25291v1 | cs.LG | 19 | 7 | 7 | 0 | 0 | 11% |
| 2608.25251v1 | cs.CV | 29 | 10 | 8 | 2 | 0 | 0% |
| 2608.25274v1 | cs.CV | 43 | 5 | 4 | 1 | 0 | 14% |
| 2608.25299v1 | cs.CV | 53 | 3 | 3 | 0 | 0 | 2% |
| 2608.25261v1 | cs.AI | 21 | 2 | 2 | 0 | 0 | 0% |
| 2608.25275v1 | cs.AI | 22 | 3 | 3 | 0 | 0 | 5% |
| 2608.25513v1 | stat.ML | 59 | 6 | 5 | 1 | 0 | 7% |
| 2608.26219v1 | stat.ML | 30 | 3 | 0 | 3 | 0 | 0% |
| 2608.27489v1 | q-bio.QM | 39 | 19 | 19 | 0 | 0 | 21% |
| 2608.26228v1 | q-bio.QM | 42 | 4 | 4 | 0 | 0 | 0% |
| 2608.25414v2 | quant-ph | 63 | 7 | 1 | 5 | 1 | 0% |
| 2608.25455v1 | quant-ph | 19 | 0 | 0 | 0 | 0 | 0% |
| 2608.25341v1 | astro-ph.GA | 64 | 6 | 5 | 1 | 0 | 0% |
| 2608.25364v1 | astro-ph.GA | 21 | 0 | 0 | 0 | 0 | 5% |
| 2608.25241v2 | cs.SE | 28 | 1 | 1 | 0 | 0 | 50% |

## By rule

| Rule | Real | False positive | Unclear |
|---|---|---|---|
| REF001 | 4 | 0 | 0 |
| REF002 | 6 | 0 | 0 |
| REF003 | 7 | 4 | 0 |
| REF010 | 1 | 0 | 0 |
| REF011 | 17 | 6 | 0 |
| REF012 | 2 | 6 | 0 |
| REF013 | 7 | 1 | 1 |
| REF014 | 4 | 2 | 0 |
| REF015 | 28 | 0 | 0 |
| REF017 | 5 | 0 | 0 |
