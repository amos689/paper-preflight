# Real papers (heldout15 batch)

- **Tool:** paper-preflight 0.8.0 code with #191, main 35dcdb0
- **Papers:** 20 arXiv papers first submitted 2026-06-17..23, chosen mechanically (`evals/real_papers.py`, manifest `evals/real_papers_heldout15.toml`)
- **Run:** 2026-10-08, live sources (answers cached for the day, so a rerun with fixed code asks again only what changed; a cold run of 20 papers takes about 20 minutes)
- **Flags:** warnings and errors about references; every one reviewed by hand (`evals/real_papers_review.toml`)

## Summary

| References checked | Flags | Real problems | False positives | Unclear | False positives per 100 references | Cannot determine |
|---|---|---|---|---|---|---|
| 1093 | 136 | 96 | 39 | 1 | 3.6 | 5% |

## By paper

| Paper | Category | References | Flags | Real | False positive | Unclear | Cannot determine |
|---|---|---|---|---|---|---|---|
| 2608.21365v1 | cs.CL | 24 | 1 | 0 | 1 | 0 | 0% |
| 2606.18587v1 | cs.CL | 33 | 5 | 4 | 1 | 0 | 0% |
| 2606.18606v1 | cs.CL | 22 | 6 | 6 | 0 | 0 | 0% |
| 2606.18561v1 | cs.LG | 54 | 15 | 10 | 5 | 0 | 7% |
| 2607.13046v1 | cs.LG | 38 | 2 | 2 | 0 | 0 | 5% |
| 2606.18621v2 | cs.LG | 56 | 2 | 0 | 2 | 0 | 0% |
| 2606.20725v1 | cs.CV | 34 | 11 | 11 | 0 | 0 | 3% |
| 2606.18553v1 | cs.CV | 18 | 3 | 3 | 0 | 0 | 0% |
| 2606.18554v1 | cs.CV | 38 | 20 | 19 | 1 | 0 | 3% |
| 2606.18557v1 | cs.AI | 53 | 9 | 6 | 3 | 0 | 17% |
| 2606.18598v1 | cs.AI | 52 | 5 | 5 | 0 | 0 | 44% |
| 2606.18567v1 | stat.ML | 56 | 12 | 4 | 8 | 0 | 7% |
| 2606.18729v3 | stat.ML | 53 | 1 | 1 | 0 | 0 | 8% |
| 2606.18575v1 | q-bio.QM | 60 | 7 | 1 | 5 | 1 | 5% |
| 2606.19396v1 | q-bio.QM | 39 | 5 | 4 | 1 | 0 | 0% |
| 2606.18552v2 | quant-ph | 50 | 20 | 18 | 2 | 0 | 2% |
| 2606.18580v1 | quant-ph | 53 | 0 | 0 | 0 | 0 | 0% |
| 2606.18637v1 | astro-ph.GA | 109 | 5 | 1 | 4 | 0 | 4% |
| 2606.18849v1 | astro-ph.GA | 206 | 6 | 0 | 6 | 0 | 0% |
| 2606.18976v1 | cs.SE | 45 | 1 | 1 | 0 | 0 | 7% |

## By rule

| Rule | Real | False positive | Unclear |
|---|---|---|---|
| REF001 | 3 | 2 | 0 |
| REF002 | 3 | 3 | 0 |
| REF003 | 1 | 4 | 1 |
| REF010 | 0 | 1 | 0 |
| REF011 | 9 | 12 | 0 |
| REF012 | 4 | 5 | 0 |
| REF013 | 2 | 6 | 0 |
| REF014 | 0 | 3 | 0 |
| REF015 | 45 | 0 | 0 |
| REF017 | 29 | 3 | 0 |
