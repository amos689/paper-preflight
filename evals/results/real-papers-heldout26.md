# Real papers (heldout26 batch)

- **Tool:** paper-preflight 0.8.0, commit 0afb1b9
- **Papers:** 20 arXiv papers first submitted 2026-03-25..31, chosen mechanically (`evals/real_papers.py`, manifest `evals/real_papers_heldout26.toml`)
- **Run:** 2026-10-15, live sources (answers cached for the day, so a rerun with fixed code asks again only what changed; a cold run of 20 papers takes about 20 minutes)
- **Flags:** warnings and errors about references; every one reviewed by hand (`evals/real_papers_review.toml`)

## Summary

| References checked | Flags | Real problems | False positives | Unclear | False positives per 100 references | Cannot determine |
|---|---|---|---|---|---|---|
| 809 | 220 | 209 | 8 | 3 | 1.0 | 4% |

## By paper

| Paper | Category | References | Flags | Real | False positive | Unclear | Cannot determine |
|---|---|---|---|---|---|---|---|
| 2603.23797v1 | cs.CL | 35 | 12 | 12 | 0 | 0 | 3% |
| 2603.23848v1 | cs.CL | 24 | 7 | 7 | 0 | 0 | 4% |
| 2603.23911v1 | cs.CL | 44 | 19 | 17 | 2 | 0 | 0% |
| 2603.23805v1 | cs.LG | 43 | 5 | 5 | 0 | 0 | 2% |
| 2603.26778v1 | cs.LG | 34 | 9 | 8 | 0 | 1 | 9% |
| 2603.23823v1 | cs.LG | 34 | 7 | 6 | 0 | 1 | 0% |
| 2603.26779v2 | cs.CV | 34 | 8 | 8 | 0 | 0 | 3% |
| 2603.26780v1 | cs.CV | 29 | 2 | 2 | 0 | 0 | 3% |
| 2603.23864v1 | cs.CV | 73 | 23 | 23 | 0 | 0 | 0% |
| 2603.23838v1 | cs.AI | 58 | 12 | 12 | 0 | 0 | 5% |
| 2603.23840v1 | cs.AI | 34 | 14 | 14 | 0 | 0 | 0% |
| 2603.23835v1 | stat.ML | 34 | 2 | 2 | 0 | 0 | 0% |
| 2604.00038v1 | stat.ML | 9 | 3 | 1 | 2 | 0 | 0% |
| 2603.24745v1 | q-bio.QM | 38 | 3 | 3 | 0 | 0 | 8% |
| 2603.27017v2 | q-bio.QM | 41 | 3 | 1 | 2 | 0 | 2% |
| 2603.23813v1 | quant-ph | 40 | 63 | 62 | 0 | 1 | 15% |
| 2603.23936v1 | quant-ph | 66 | 0 | 0 | 0 | 0 | 6% |
| 2603.23872v1 | astro-ph.GA | 27 | 9 | 8 | 1 | 0 | 7% |
| 2603.23981v1 | astro-ph.GA | 73 | 3 | 2 | 1 | 0 | 1% |
| 2603.23806v2 | cs.SE | 39 | 16 | 16 | 0 | 0 | 13% |

## By rule

| Rule | Real | False positive | Unclear |
|---|---|---|---|
| REF001 | 1 | 0 | 1 |
| REF003 | 0 | 1 | 1 |
| REF010 | 1 | 1 | 0 |
| REF011 | 9 | 1 | 0 |
| REF012 | 4 | 2 | 0 |
| REF013 | 3 | 1 | 1 |
| REF014 | 0 | 1 | 0 |
| REF015 | 103 | 0 | 0 |
| REF017 | 88 | 0 | 0 |
| REF020 | 0 | 1 | 0 |
