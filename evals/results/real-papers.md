# Real papers (dev batch)

- **Tool:** paper-preflight 0.1.2 candidate, commit f84e119 (main after #91)
- **Papers:** 20 arXiv papers first submitted 2026-07-01..07, chosen mechanically (`evals/real_papers.py`, manifest `evals/real_papers.toml`)
- **Run:** 2026-10-03, live sources (answers cached for the day, so a rerun with fixed code asks again only what changed; a cold run of 20 papers takes about 20 minutes)
- **Flags:** warnings and errors about references; every one reviewed by hand (`evals/real_papers_review.toml`)

## Summary

| References checked | Flags | Real problems | False positives | Unclear | False positives per 100 references | Cannot determine |
|---|---|---|---|---|---|---|
| 924 | 73 | 66 | 1 | 6 | 0.1 | 6% |

## By paper

| Paper | Category | References | Flags | Real | False positive | Unclear | Cannot determine |
|---|---|---|---|---|---|---|---|
| 2607.00339v1 | cs.CL | 45 | 3 | 3 | 0 | 0 | 4% |
| 2607.00368v1 | cs.CL | 41 | 3 | 3 | 0 | 0 | 5% |
| 2607.00415v1 | cs.CL | 23 | 2 | 2 | 0 | 0 | 9% |
| 2607.00301v1 | cs.LG | 20 | 4 | 4 | 0 | 0 | 0% |
| 2607.00325v1 | cs.LG | 22 | 2 | 2 | 0 | 0 | 0% |
| 2607.19378v3 | cs.LG | 53 | 8 | 8 | 0 | 0 | 13% |
| 2607.02582v1 | cs.CV | 33 | 1 | 1 | 0 | 0 | 39% |
| 2607.00289v1 | cs.CV | 54 | 0 | 0 | 0 | 0 | 0% |
| 2607.00293v1 | cs.CV | 72 | 9 | 9 | 0 | 0 | 3% |
| 2607.00407v2 | cs.AI | 54 | 12 | 12 | 0 | 0 | 7% |
| 2607.00454v1 | cs.AI | 17 | 3 | 3 | 0 | 0 | 0% |
| 2607.00320v1 | stat.ML | 59 | 0 | 0 | 0 | 0 | 8% |
| 2607.00877v1 | stat.ML | 45 | 4 | 4 | 0 | 0 | 2% |
| 2607.01749v1 | q-bio.QM | 65 | 0 | 0 | 0 | 0 | 0% |
| 2607.02103v1 | q-bio.QM | 25 | 3 | 3 | 0 | 0 | 12% |
| 2607.00284v1 | quant-ph | 46 | 1 | 1 | 0 | 0 | 7% |
| 2607.00307v1 | quant-ph | 35 | 6 | 6 | 0 | 0 | 3% |
| 2607.00291v1 | astro-ph.GA | 105 | 3 | 0 | 1 | 2 | 1% |
| 2607.00305v1 | astro-ph.GA | 51 | 6 | 4 | 0 | 2 | 2% |
| 2607.02583v1 | cs.SE | 59 | 3 | 1 | 0 | 2 | 12% |

## By rule

| Rule | Real | False positive | Unclear |
|---|---|---|---|
| REF001 | 3 | 0 | 0 |
| REF002 | 1 | 0 | 0 |
| REF011 | 7 | 1 | 1 |
| REF012 | 4 | 0 | 3 |
| REF013 | 5 | 0 | 2 |
| REF014 | 1 | 0 | 0 |
| REF015 | 40 | 0 | 0 |
| REF017 | 5 | 0 | 0 |
