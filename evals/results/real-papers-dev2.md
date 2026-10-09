# Real papers (dev2 batch)

- **Tool:** paper-preflight 0.8.0 code with #191, #193 and #195, main 391a0bc
- **Papers:** 20 arXiv papers first submitted 2026-06-03..09, chosen mechanically (`evals/real_papers.py`, manifest `evals/real_papers_dev2.toml`)
- **Run:** 2026-10-09, live sources (answers cached for the day, so a rerun with fixed code asks again only what changed; a cold run of 20 papers takes about 20 minutes)
- **Flags:** warnings and errors about references; every one reviewed by hand (`evals/real_papers_review.toml`)

## Summary

| References checked | Flags | Real problems | False positives | Unclear | False positives per 100 references | Cannot determine |
|---|---|---|---|---|---|---|
| 1038 | 72 | 59 | 12 | 1 | 1.2 | 4% |

## By paper

| Paper | Category | References | Flags | Real | False positive | Unclear | Cannot determine |
|---|---|---|---|---|---|---|---|
| 2606.04302v1 | cs.CL | 63 | 3 | 3 | 0 | 0 | 8% |
| 2606.04325v1 | cs.CL | 46 | 13 | 12 | 1 | 0 | 2% |
| 2606.04340v1 | cs.CL | 63 | 4 | 1 | 3 | 0 | 6% |
| 2606.04307v2 | cs.LG | 21 | 0 | 0 | 0 | 0 | 5% |
| 2606.04310v1 | cs.LG | 50 | 4 | 3 | 1 | 0 | 2% |
| 2606.04314v1 | cs.LG | 48 | 3 | 2 | 1 | 0 | 2% |
| 2606.04299v1 | cs.CV | 74 | 3 | 3 | 0 | 0 | 3% |
| 2606.04343v1 | cs.CV | 45 | 1 | 1 | 0 | 0 | 4% |
| 2606.04345v1 | cs.CV | 24 | 5 | 5 | 0 | 0 | 17% |
| 2606.04391v1 | cs.AI | 57 | 5 | 5 | 0 | 0 | 7% |
| 2607.22572v1 | cs.AI | 35 | 7 | 7 | 0 | 0 | 14% |
| 2606.04380v1 | stat.ML | 36 | 1 | 1 | 0 | 0 | 0% |
| 2606.04429v1 | stat.ML | 72 | 9 | 5 | 3 | 1 | 1% |
| 2606.06117v1 | q-bio.QM | 38 | 0 | 0 | 0 | 0 | 3% |
| 2606.06749v1 | q-bio.QM | 25 | 0 | 0 | 0 | 0 | 4% |
| 2606.04312v1 | quant-ph | 43 | 0 | 0 | 0 | 0 | 0% |
| 2606.04386v1 | quant-ph | 107 | 3 | 3 | 0 | 0 | 0% |
| 2606.04309v1 | astro-ph.GA | 62 | 1 | 0 | 1 | 0 | 0% |
| 2606.04509v1 | astro-ph.GA | 96 | 2 | 0 | 2 | 0 | 1% |
| 2606.04350v2 | cs.SE | 33 | 8 | 8 | 0 | 0 | 9% |

## By rule

| Rule | Real | False positive | Unclear |
|---|---|---|---|
| REF002 | 1 | 0 | 0 |
| REF003 | 7 | 2 | 0 |
| REF011 | 2 | 2 | 1 |
| REF012 | 3 | 2 | 0 |
| REF013 | 3 | 5 | 0 |
| REF014 | 1 | 1 | 0 |
| REF015 | 30 | 0 | 0 |
| REF017 | 12 | 0 | 0 |
