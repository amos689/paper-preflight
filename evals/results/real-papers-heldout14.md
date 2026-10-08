# Real papers (heldout14 batch)

- **Tool:** paper-preflight 0.7.0 code at main 5e048db (#187), run from commit 46870ab (the frozen list, no code change)
- **Papers:** 20 arXiv papers first submitted 2026-06-24..30, chosen mechanically (`evals/real_papers.py`, manifest `evals/real_papers_heldout14.toml`)
- **Run:** 2026-10-08, live sources (answers cached for the day, so a rerun with fixed code asks again only what changed; a cold run of 20 papers takes about 20 minutes)
- **Flags:** warnings and errors about references; every one reviewed by hand (`evals/real_papers_review.toml`)

## Summary

| References checked | Flags | Real problems | False positives | Unclear | False positives per 100 references | Cannot determine |
|---|---|---|---|---|---|---|
| 1127 | 143 | 132 | 10 | 1 | 0.9 | 3% |

## By paper

| Paper | Category | References | Flags | Real | False positive | Unclear | Cannot determine |
|---|---|---|---|---|---|---|---|
| 2608.26131v1 | cs.CL | 51 | 31 | 30 | 1 | 0 | 4% |
| 2606.25331v1 | cs.CL | 48 | 20 | 20 | 0 | 0 | 2% |
| 2608.20375v1 | cs.CL | 32 | 7 | 6 | 1 | 0 | 3% |
| 2606.25265v1 | cs.LG | 43 | 3 | 3 | 0 | 0 | 0% |
| 2606.25274v2 | cs.LG | 41 | 4 | 4 | 0 | 0 | 5% |
| 2606.25285v1 | cs.LG | 43 | 0 | 0 | 0 | 0 | 0% |
| 2606.25245v2 | cs.CV | 61 | 4 | 4 | 0 | 0 | 7% |
| 2606.25255v2 | cs.CV | 26 | 1 | 1 | 0 | 0 | 0% |
| 2606.25273v1 | cs.CV | 45 | 5 | 5 | 0 | 0 | 0% |
| 2607.02542v1 | cs.AI | 26 | 15 | 14 | 1 | 0 | 0% |
| 2607.22643v1 | cs.AI | 57 | 14 | 13 | 1 | 0 | 2% |
| 2606.25269v1 | stat.ML | 25 | 4 | 4 | 0 | 0 | 0% |
| 2606.25601v3 | stat.ML | 115 | 6 | 5 | 1 | 0 | 6% |
| 2606.28418v1 | q-bio.QM | 33 | 13 | 10 | 3 | 0 | 6% |
| 2606.27168v1 | q-bio.QM | 62 | 7 | 7 | 0 | 0 | 0% |
| 2606.25260v1 | quant-ph | 33 | 2 | 2 | 0 | 0 | 3% |
| 2606.25261v1 | quant-ph | 102 | 4 | 1 | 2 | 1 | 7% |
| 2606.25263v1 | astro-ph.GA | 62 | 0 | 0 | 0 | 0 | 0% |
| 2606.25359v1 | astro-ph.GA | 193 | 0 | 0 | 0 | 0 | 2% |
| 2606.25257v1 | cs.SE | 29 | 3 | 3 | 0 | 0 | 3% |

## By rule

| Rule | Real | False positive | Unclear |
|---|---|---|---|
| REF001 | 1 | 0 | 0 |
| REF002 | 1 | 0 | 0 |
| REF003 | 0 | 1 | 1 |
| REF010 | 1 | 1 | 0 |
| REF011 | 10 | 4 | 0 |
| REF012 | 2 | 4 | 0 |
| REF013 | 6 | 0 | 0 |
| REF014 | 1 | 0 | 0 |
| REF015 | 93 | 0 | 0 |
| REF017 | 17 | 0 | 0 |
