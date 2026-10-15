# Real papers (heldout18 batch)

- **Tool:** paper-preflight 0.8.0, commit d99cac5
- **Papers:** 20 arXiv papers first submitted 2026-05-20..26, chosen mechanically (`evals/real_papers.py`, manifest `evals/real_papers_heldout18.toml`)
- **Run:** 2026-10-15, live sources (answers cached for the day, so a rerun with fixed code asks again only what changed; a cold run of 20 papers takes about 20 minutes)
- **Flags:** warnings and errors about references; every one reviewed by hand (`evals/real_papers_review.toml`)

## Summary

| References checked | Flags | Real problems | False positives | Unclear | False positives per 100 references | Cannot determine |
|---|---|---|---|---|---|---|
| 1136 | 174 | 148 | 22 | 4 | 1.9 | 5% |

## By paper

| Paper | Category | References | Flags | Real | False positive | Unclear | Cannot determine |
|---|---|---|---|---|---|---|---|
| 2607.28640v2 | cs.CL | 50 | 10 | 10 | 0 | 0 | 20% |
| 2605.20588v2 | cs.CL | 40 | 9 | 0 | 9 | 0 | 0% |
| 2605.20591v1 | cs.CL | 60 | 79 | 78 | 1 | 0 | 12% |
| 2605.20580v1 | cs.LG | 62 | 9 | 7 | 1 | 1 | 2% |
| 2605.20581v1 | cs.LG | 58 | 5 | 4 | 1 | 0 | 0% |
| 2605.22871v1 | cs.LG | 47 | 6 | 5 | 1 | 0 | 2% |
| 2605.20569v1 | cs.CV | 54 | 0 | 0 | 0 | 0 | 0% |
| 2605.20576v1 | cs.CV | 63 | 19 | 19 | 0 | 0 | 3% |
| 2605.20584v1 | cs.CV | 43 | 2 | 2 | 0 | 0 | 58% |
| 2605.20577v1 | cs.AI | 27 | 2 | 2 | 0 | 0 | 4% |
| 2607.21609v1 | cs.AI | 31 | 8 | 8 | 0 | 0 | 0% |
| 2605.21548v1 | stat.ML | 45 | 1 | 0 | 1 | 0 | 4% |
| 2605.21041v1 | stat.ML | 62 | 2 | 1 | 1 | 0 | 3% |
| 2605.22968v1 | q-bio.QM | 26 | 3 | 0 | 2 | 1 | 0% |
| 2605.25079v1 | q-bio.QM | 40 | 5 | 4 | 1 | 0 | 2% |
| 2605.20637v2 | quant-ph | 37 | 5 | 3 | 1 | 1 | 0% |
| 2605.20656v2 | quant-ph | 95 | 2 | 1 | 1 | 0 | 1% |
| 2605.20590v1 | astro-ph.GA | 131 | 4 | 2 | 2 | 0 | 2% |
| 2605.20622v1 | astro-ph.GA | 143 | 1 | 1 | 0 | 0 | 1% |
| 2605.20675v1 | cs.SE | 22 | 2 | 1 | 0 | 1 | 9% |

## By rule

| Rule | Real | False positive | Unclear |
|---|---|---|---|
| REF001 | 1 | 0 | 0 |
| REF002 | 2 | 0 | 0 |
| REF003 | 0 | 14 | 0 |
| REF010 | 0 | 1 | 0 |
| REF011 | 3 | 2 | 4 |
| REF012 | 2 | 4 | 0 |
| REF013 | 2 | 1 | 0 |
| REF015 | 52 | 0 | 0 |
| REF017 | 86 | 0 | 0 |
