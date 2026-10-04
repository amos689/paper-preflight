# Real papers (heldout4 batch)

- **Tool:** paper-preflight 0.2.0, commit 33364b7
- **Papers:** 20 arXiv papers first submitted 2026-07-29..04, chosen mechanically (`evals/real_papers.py`, manifest `evals/real_papers_heldout4.toml`)
- **Run:** 2026-10-04, live sources (answers cached for the day, so a rerun with fixed code asks again only what changed; a cold run of 20 papers takes about 20 minutes)
- **Flags:** warnings and errors about references; every one reviewed by hand (`evals/real_papers_review.toml`)

## Summary

| References checked | Flags | Real problems | False positives | Unclear | False positives per 100 references | Cannot determine |
|---|---|---|---|---|---|---|
| 1005 | 88 | 66 | 19 | 3 | 1.9 | 6% |

## By paper

| Paper | Category | References | Flags | Real | False positive | Unclear | Cannot determine |
|---|---|---|---|---|---|---|---|
| 2607.26368v2 | cs.CL | 27 | 1 | 1 | 0 | 0 | 19% |
| 2607.26375v1 | cs.CL | 108 | 12 | 4 | 7 | 1 | 11% |
| 2607.26397v1 | cs.CL | 55 | 6 | 4 | 2 | 0 | 2% |
| 2608.14642v1 | cs.LG | 30 | 1 | 0 | 1 | 0 | 7% |
| 2607.26357v1 | cs.LG | 35 | 0 | 0 | 0 | 0 | 11% |
| 2607.26358v2 | cs.LG | 48 | 2 | 2 | 0 | 0 | 6% |
| 2607.26381v1 | cs.CV | 50 | 2 | 2 | 0 | 0 | 2% |
| 2607.26395v1 | cs.CV | 43 | 1 | 0 | 1 | 0 | 0% |
| 2607.26411v1 | cs.CV | 58 | 20 | 19 | 1 | 0 | 0% |
| 2607.26367v1 | cs.AI | 40 | 3 | 2 | 1 | 0 | 25% |
| 2608.00065v3 | cs.AI | 28 | 2 | 1 | 1 | 0 | 4% |
| 2607.26414v1 | stat.ML | 63 | 3 | 2 | 1 | 0 | 5% |
| 2607.26792v1 | stat.ML | 21 | 4 | 4 | 0 | 0 | 0% |
| 2607.28514v1 | q-bio.QM | 105 | 4 | 4 | 0 | 0 | 7% |
| 2608.00098v1 | q-bio.QM | 17 | 10 | 10 | 0 | 0 | 18% |
| 2607.26438v1 | quant-ph | 51 | 4 | 3 | 0 | 1 | 2% |
| 2607.26445v1 | quant-ph | 78 | 8 | 3 | 4 | 1 | 1% |
| 2607.26713v1 | astro-ph.GA | 46 | 1 | 1 | 0 | 0 | 2% |
| 2607.27001v1 | astro-ph.GA | 61 | 0 | 0 | 0 | 0 | 2% |
| 2607.26390v3 | cs.SE | 41 | 4 | 4 | 0 | 0 | 22% |

## By rule

| Rule | Real | False positive | Unclear |
|---|---|---|---|
| REF001 | 2 | 0 | 0 |
| REF002 | 1 | 0 | 0 |
| REF003 | 1 | 1 | 0 |
| REF011 | 11 | 10 | 1 |
| REF012 | 6 | 5 | 0 |
| REF013 | 3 | 3 | 1 |
| REF014 | 0 | 0 | 1 |
| REF015 | 35 | 0 | 0 |
| REF017 | 7 | 0 | 0 |
