# Real papers (heldout25 batch)

- **Tool:** paper-preflight 0.8.0, commit 6fa65e6
- **Papers:** 20 arXiv papers first submitted 2026-04-01..07, chosen mechanically (`evals/real_papers.py`, manifest `evals/real_papers_heldout25.toml`)
- **Run:** 2026-10-15, live sources (answers cached for the day, so a rerun with fixed code asks again only what changed; a cold run of 20 papers takes about 20 minutes)
- **Flags:** warnings and errors about references; every one reviewed by hand (`evals/real_papers_review.toml`)

## Summary

| References checked | Flags | Real problems | False positives | Unclear | False positives per 100 references | Cannot determine |
|---|---|---|---|---|---|---|
| 763 | 86 | 80 | 6 | 0 | 0.8 | 3% |

## By paper

| Paper | Category | References | Flags | Real | False positive | Unclear | Cannot determine |
|---|---|---|---|---|---|---|---|
| 2604.00344v1 | cs.CL | 42 | 12 | 10 | 2 | 0 | 5% |
| 2604.00375v1 | cs.CL | 51 | 18 | 18 | 0 | 0 | 6% |
| 2604.00443v1 | cs.CL | 29 | 5 | 5 | 0 | 0 | 24% |
| 2604.00342v1 | cs.LG | 19 | 3 | 3 | 0 | 0 | 0% |
| 2604.00385v2 | cs.LG | 42 | 2 | 2 | 0 | 0 | 0% |
| 2604.00394v2 | cs.LG | 22 | 3 | 3 | 0 | 0 | 0% |
| 2604.00360v1 | cs.CV | 68 | 3 | 2 | 1 | 0 | 0% |
| 2604.03314v3 | cs.CV | 42 | 4 | 4 | 0 | 0 | 0% |
| 2604.00372v1 | cs.CV | 49 | 4 | 4 | 0 | 0 | 0% |
| 2606.15504v2 | cs.AI | 29 | 0 | 0 | 0 | 0 | 0% |
| 2604.00356v1 | cs.AI | 21 | 0 | 0 | 0 | 0 | 0% |
| 2604.00432v1 | stat.ML | 22 | 1 | 1 | 0 | 0 | 5% |
| 2604.00697v1 | stat.ML | 36 | 3 | 3 | 0 | 0 | 8% |
| 2604.01252v1 | q-bio.QM | 42 | 5 | 4 | 1 | 0 | 2% |
| 2604.01385v1 | q-bio.QM | 37 | 1 | 1 | 0 | 0 | 0% |
| 2604.00417v2 | quant-ph | 31 | 2 | 2 | 0 | 0 | 0% |
| 2604.00434v1 | quant-ph | 30 | 4 | 3 | 1 | 0 | 0% |
| 2604.00578v2 | astro-ph.GA | 22 | 8 | 8 | 0 | 0 | 9% |
| 2604.00661v1 | astro-ph.GA | 71 | 3 | 3 | 0 | 0 | 3% |
| 2604.00422v1 | cs.SE | 58 | 5 | 4 | 1 | 0 | 0% |

## By rule

| Rule | Real | False positive | Unclear |
|---|---|---|---|
| REF002 | 1 | 0 | 0 |
| REF003 | 2 | 1 | 0 |
| REF010 | 0 | 1 | 0 |
| REF011 | 8 | 1 | 0 |
| REF012 | 5 | 2 | 0 |
| REF013 | 6 | 1 | 0 |
| REF014 | 2 | 0 | 0 |
| REF015 | 42 | 0 | 0 |
| REF017 | 14 | 0 | 0 |
