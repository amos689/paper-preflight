# Real papers (heldout19 batch)

- **Tool:** paper-preflight 0.8.0, commit d99cac5
- **Papers:** 20 arXiv papers first submitted 2026-05-13..19, chosen mechanically (`evals/real_papers.py`, manifest `evals/real_papers_heldout19.toml`)
- **Run:** 2026-10-15, live sources (answers cached for the day, so a rerun with fixed code asks again only what changed; a cold run of 20 papers takes about 20 minutes)
- **Flags:** warnings and errors about references; every one reviewed by hand (`evals/real_papers_review.toml`)

## Summary

| References checked | Flags | Real problems | False positives | Unclear | False positives per 100 references | Cannot determine |
|---|---|---|---|---|---|---|
| 1008 | 133 | 123 | 8 | 2 | 0.8 | 4% |

## By paper

| Paper | Category | References | Flags | Real | False positive | Unclear | Cannot determine |
|---|---|---|---|---|---|---|---|
| 2605.12850v2 | cs.CL | 35 | 12 | 11 | 1 | 0 | 3% |
| 2605.12882v2 | cs.CL | 53 | 10 | 10 | 0 | 0 | 0% |
| 2605.15220v1 | cs.CL | 56 | 4 | 4 | 0 | 0 | 5% |
| 2605.12843v3 | cs.LG | 57 | 8 | 7 | 1 | 0 | 4% |
| 2605.12852v1 | cs.LG | 26 | 2 | 2 | 0 | 0 | 4% |
| 2605.18835v1 | cs.LG | 40 | 4 | 4 | 0 | 0 | 0% |
| 2605.12845v1 | cs.CV | 46 | 4 | 4 | 0 | 0 | 0% |
| 2605.12851v1 | cs.CV | 17 | 6 | 6 | 0 | 0 | 12% |
| 2605.12855v1 | cs.CV | 53 | 11 | 11 | 0 | 0 | 0% |
| 2605.12838v1 | cs.AI | 21 | 5 | 5 | 0 | 0 | 5% |
| 2605.12856v2 | cs.AI | 51 | 9 | 7 | 2 | 0 | 6% |
| 2605.12899v1 | stat.ML | 78 | 4 | 3 | 1 | 0 | 5% |
| 2605.12947v1 | stat.ML | 42 | 5 | 5 | 0 | 0 | 21% |
| 2605.14812v1 | q-bio.QM | 66 | 1 | 0 | 1 | 0 | 0% |
| 2605.15364v1 | q-bio.QM | 57 | 9 | 8 | 1 | 0 | 9% |
| 2605.12955v2 | quant-ph | 36 | 4 | 3 | 0 | 1 | 0% |
| 2605.12984v1 | quant-ph | 60 | 1 | 1 | 0 | 0 | 8% |
| 2605.12973v2 | astro-ph.GA | 104 | 8 | 7 | 0 | 1 | 5% |
| 2605.13219v1 | astro-ph.GA | 62 | 4 | 4 | 0 | 0 | 2% |
| 2605.12925v4 | cs.SE | 48 | 22 | 21 | 1 | 0 | 6% |

## By rule

| Rule | Real | False positive | Unclear |
|---|---|---|---|
| REF001 | 5 | 0 | 0 |
| REF002 | 3 | 1 | 0 |
| REF003 | 1 | 3 | 0 |
| REF011 | 8 | 3 | 1 |
| REF012 | 6 | 0 | 0 |
| REF013 | 5 | 0 | 1 |
| REF015 | 62 | 0 | 0 |
| REF017 | 33 | 0 | 0 |
| REF018 | 0 | 1 | 0 |
