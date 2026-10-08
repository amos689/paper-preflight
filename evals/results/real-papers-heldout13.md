# Real papers (heldout13 batch)

- **Tool:** paper-preflight 0.6.0, commit 63dcd71
- **Papers:** 20 arXiv papers first submitted 2026-09-30..06, chosen mechanically (`evals/real_papers.py`, manifest `evals/real_papers_heldout13.toml`)
- **Run:** 2026-10-08, live sources (answers cached for the day, so a rerun with fixed code asks again only what changed; a cold run of 20 papers takes about 20 minutes)
- **Flags:** warnings and errors about references; every one reviewed by hand (`evals/real_papers_review.toml`)

## Summary

| References checked | Flags | Real problems | False positives | Unclear | False positives per 100 references | Cannot determine |
|---|---|---|---|---|---|---|
| 1014 | 89 | 79 | 7 | 3 | 0.7 | 3% |

## By paper

| Paper | Category | References | Flags | Real | False positive | Unclear | Cannot determine |
|---|---|---|---|---|---|---|---|
| 2609.38718v1 | cs.CL | 71 | 11 | 11 | 0 | 0 | 0% |
| 2609.38792v1 | cs.CL | 55 | 9 | 9 | 0 | 0 | 11% |
| 2609.38795v2 | cs.CL | 44 | 6 | 6 | 0 | 0 | 2% |
| 2609.38744v1 | cs.LG | 40 | 4 | 3 | 1 | 0 | 5% |
| 2609.38764v1 | cs.LG | 39 | 7 | 7 | 0 | 0 | 5% |
| 2609.38767v2 | cs.LG | 49 | 0 | 0 | 0 | 0 | 6% |
| 2609.38680v1 | cs.CV | 40 | 0 | 0 | 0 | 0 | 0% |
| 2609.38683v1 | cs.CV | 39 | 5 | 3 | 0 | 2 | 3% |
| 2609.38689v1 | cs.CV | 50 | 15 | 15 | 0 | 0 | 4% |
| 2609.38684v1 | cs.AI | 39 | 1 | 1 | 0 | 0 | 3% |
| 2610.00353v1 | cs.AI | 33 | 1 | 1 | 0 | 0 | 6% |
| 2609.38916v1 | stat.ML | 55 | 12 | 10 | 2 | 0 | 4% |
| 2609.39020v1 | stat.ML | 56 | 2 | 0 | 2 | 0 | 2% |
| 2610.08843v1 | q-bio.QM | 27 | 2 | 2 | 0 | 0 | 7% |
| 2610.02247v1 | q-bio.QM | 29 | 6 | 6 | 0 | 0 | 0% |
| 2609.38678v1 | quant-ph | 65 | 1 | 0 | 1 | 0 | 2% |
| 2609.38687v1 | quant-ph | 37 | 0 | 0 | 0 | 0 | 5% |
| 2609.38937v1 | astro-ph.GA | 152 | 5 | 4 | 1 | 0 | 1% |
| 2609.39040v1 | astro-ph.GA | 71 | 1 | 0 | 0 | 1 | 0% |
| 2609.38762v1 | cs.SE | 23 | 1 | 1 | 0 | 0 | 0% |

## By rule

| Rule | Real | False positive | Unclear |
|---|---|---|---|
| REF002 | 1 | 0 | 0 |
| REF003 | 2 | 0 | 0 |
| REF011 | 5 | 0 | 2 |
| REF012 | 5 | 2 | 1 |
| REF013 | 8 | 4 | 0 |
| REF014 | 4 | 0 | 0 |
| REF015 | 47 | 1 | 0 |
| REF017 | 7 | 0 | 0 |
