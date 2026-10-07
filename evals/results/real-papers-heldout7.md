# Real papers (heldout7 batch)

- **Tool:** paper-preflight 0.4.1, commit 1babb2f
- **Papers:** 20 arXiv papers first submitted 2026-08-19..25, chosen mechanically (`evals/real_papers.py`, manifest `evals/real_papers_heldout7.toml`)
- **Run:** 2026-10-07, live sources (answers cached for the day, so a rerun with fixed code asks again only what changed; a cold run of 20 papers takes about 20 minutes)
- **Flags:** warnings and errors about references; every one reviewed by hand (`evals/real_papers_review.toml`)

## Summary

| References checked | Flags | Real problems | False positives | Unclear | False positives per 100 references | Cannot determine |
|---|---|---|---|---|---|---|
| 962 | 53 | 41 | 10 | 2 | 1.0 | 5% |

## By paper

| Paper | Category | References | Flags | Real | False positive | Unclear | Cannot determine |
|---|---|---|---|---|---|---|---|
| 2608.18437v2 | cs.CL | 36 | 1 | 1 | 0 | 0 | 19% |
| 2608.18474v1 | cs.CL | 36 | 10 | 10 | 0 | 0 | 0% |
| 2608.18489v1 | cs.CL | 49 | 2 | 2 | 0 | 0 | 0% |
| 2608.18404v1 | cs.LG | 47 | 3 | 3 | 0 | 0 | 4% |
| 2608.18415v2 | cs.LG | 63 | 0 | 0 | 0 | 0 | 5% |
| 2608.18419v1 | cs.LG | 45 | 7 | 7 | 0 | 0 | 4% |
| 2608.18412v1 | cs.CV | 59 | 1 | 0 | 0 | 1 | 12% |
| 2608.18413v1 | cs.CV | 38 | 3 | 3 | 0 | 0 | 3% |
| 2608.18479v1 | cs.CV | 67 | 5 | 5 | 0 | 0 | 1% |
| 2608.18409v2 | cs.AI | 20 | 0 | 0 | 0 | 0 | 0% |
| 2608.18423v2 | cs.AI | 44 | 3 | 2 | 1 | 0 | 32% |
| 2608.18863v1 | stat.ML | 26 | 1 | 1 | 0 | 0 | 0% |
| 2608.19082v1 | stat.ML | 28 | 5 | 3 | 2 | 0 | 21% |
| 2608.20184v1 | q-bio.QM | 29 | 1 | 1 | 0 | 0 | 0% |
| 2608.21349v1 | q-bio.QM | 28 | 2 | 1 | 1 | 0 | 0% |
| 2608.18420v1 | quant-ph | 39 | 1 | 0 | 0 | 1 | 3% |
| 2608.18440v2 | quant-ph | 78 | 0 | 0 | 0 | 0 | 1% |
| 2608.18464v1 | astro-ph.GA | 149 | 3 | 0 | 3 | 0 | 2% |
| 2608.18550v1 | astro-ph.GA | 45 | 3 | 0 | 3 | 0 | 0% |
| 2608.18588v1 | cs.SE | 36 | 2 | 2 | 0 | 0 | 8% |

## By rule

| Rule | Real | False positive | Unclear |
|---|---|---|---|
| REF001 | 0 | 1 | 0 |
| REF003 | 0 | 0 | 1 |
| REF010 | 1 | 1 | 0 |
| REF011 | 4 | 6 | 0 |
| REF012 | 1 | 1 | 1 |
| REF013 | 5 | 0 | 0 |
| REF014 | 0 | 1 | 0 |
| REF015 | 25 | 0 | 0 |
| REF017 | 5 | 0 | 0 |
