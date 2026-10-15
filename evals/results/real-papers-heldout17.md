# Real papers (heldout17 batch)

- **Tool:** paper-preflight 0.8.0, commit d99cac5
- **Papers:** 20 arXiv papers first submitted 2026-10-07..13, chosen mechanically (`evals/real_papers.py`, manifest `evals/real_papers_heldout17.toml`)
- **Run:** 2026-10-15, live sources (answers cached for the day, so a rerun with fixed code asks again only what changed; a cold run of 20 papers takes about 20 minutes)
- **Flags:** warnings and errors about references; every one reviewed by hand (`evals/real_papers_review.toml`)

## Summary

| References checked | Flags | Real problems | False positives | Unclear | False positives per 100 references | Cannot determine |
|---|---|---|---|---|---|---|
| 991 | 81 | 76 | 4 | 1 | 0.4 | 4% |

## By paper

| Paper | Category | References | Flags | Real | False positive | Unclear | Cannot determine |
|---|---|---|---|---|---|---|---|
| 2610.09321v1 | cs.CL | 38 | 1 | 0 | 1 | 0 | 8% |
| 2610.09372v1 | cs.CL | 21 | 0 | 0 | 0 | 0 | 0% |
| 2610.09384v1 | cs.CL | 44 | 3 | 3 | 0 | 0 | 11% |
| 2610.09247v1 | cs.LG | 38 | 16 | 16 | 0 | 0 | 0% |
| 2610.09250v1 | cs.LG | 52 | 3 | 3 | 0 | 0 | 0% |
| 2610.09255v1 | cs.LG | 20 | 1 | 1 | 0 | 0 | 0% |
| 2610.09242v1 | cs.CV | 27 | 1 | 1 | 0 | 0 | 4% |
| 2610.09252v1 | cs.CV | 20 | 1 | 1 | 0 | 0 | 0% |
| 2610.09253v1 | cs.CV | 25 | 0 | 0 | 0 | 0 | 20% |
| 2610.09239v1 | cs.AI | 53 | 2 | 1 | 1 | 0 | 2% |
| 2610.09294v1 | cs.AI | 69 | 3 | 3 | 0 | 0 | 17% |
| 2610.09505v1 | stat.ML | 33 | 5 | 5 | 0 | 0 | 3% |
| 2610.09530v1 | stat.ML | 78 | 6 | 6 | 0 | 0 | 4% |
| 2610.10913v1 | q-bio.QM | 105 | 11 | 10 | 1 | 0 | 4% |
| 2610.11694v1 | q-bio.QM | 40 | 6 | 6 | 0 | 0 | 0% |
| 2610.09322v1 | quant-ph | 60 | 9 | 9 | 0 | 0 | 7% |
| 2610.09341v1 | quant-ph | 37 | 0 | 0 | 0 | 0 | 3% |
| 2610.09500v1 | astro-ph.GA | 75 | 0 | 0 | 0 | 0 | 4% |
| 2610.09564v1 | astro-ph.GA | 115 | 7 | 5 | 1 | 1 | 0% |
| 2610.09267v1 | cs.SE | 41 | 6 | 6 | 0 | 0 | 2% |

## By rule

| Rule | Real | False positive | Unclear |
|---|---|---|---|
| REF002 | 2 | 0 | 0 |
| REF003 | 0 | 1 | 0 |
| REF011 | 4 | 1 | 1 |
| REF012 | 7 | 1 | 0 |
| REF013 | 7 | 1 | 0 |
| REF015 | 24 | 0 | 0 |
| REF017 | 31 | 0 | 0 |
| REF018 | 1 | 0 | 0 |
