# Real papers (heldout24 batch)

- **Tool:** paper-preflight 0.8.0, commit 6fa65e6
- **Papers:** 20 arXiv papers first submitted 2026-04-08..14, chosen mechanically (`evals/real_papers.py`, manifest `evals/real_papers_heldout24.toml`)
- **Run:** 2026-10-15, live sources (answers cached for the day, so a rerun with fixed code asks again only what changed; a cold run of 20 papers takes about 20 minutes)
- **Flags:** warnings and errors about references; every one reviewed by hand (`evals/real_papers_review.toml`)

## Summary

| References checked | Flags | Real problems | False positives | Unclear | False positives per 100 references | Cannot determine |
|---|---|---|---|---|---|---|
| 1088 | 194 | 181 | 7 | 6 | 0.6 | 5% |

## By paper

| Paper | Category | References | Flags | Real | False positive | Unclear | Cannot determine |
|---|---|---|---|---|---|---|---|
| 2605.26438v1 | cs.CL | 34 | 7 | 7 | 0 | 0 | 35% |
| 2604.06542v1 | cs.CL | 19 | 4 | 4 | 0 | 0 | 0% |
| 2604.06543v2 | cs.CL | 46 | 7 | 7 | 0 | 0 | 9% |
| 2604.06537v1 | cs.LG | 20 | 2 | 1 | 1 | 0 | 5% |
| 2604.06558v1 | cs.LG | 29 | 5 | 4 | 1 | 0 | 3% |
| 2604.07383v2 | cs.LG | 76 | 8 | 8 | 0 | 0 | 1% |
| 2604.06576v1 | cs.CV | 78 | 1 | 1 | 0 | 0 | 0% |
| 2604.06614v2 | cs.CV | 53 | 7 | 7 | 0 | 0 | 0% |
| 2604.06622v1 | cs.CV | 43 | 0 | 0 | 0 | 0 | 0% |
| 2604.06562v1 | cs.AI | 80 | 26 | 22 | 2 | 2 | 6% |
| 2604.06628v2 | cs.AI | 56 | 5 | 5 | 0 | 0 | 9% |
| 2604.06864v1 | stat.ML | 21 | 1 | 0 | 1 | 0 | 10% |
| 2604.07169v3 | stat.ML | 38 | 2 | 2 | 0 | 0 | 3% |
| 2604.07576v1 | q-bio.QM | 128 | 13 | 10 | 0 | 3 | 6% |
| 2604.18603v1 | q-bio.QM | 60 | 79 | 78 | 1 | 0 | 2% |
| 2604.06574v1 | quant-ph | 49 | 8 | 8 | 0 | 0 | 6% |
| 2604.06584v1 | quant-ph | 54 | 8 | 7 | 1 | 0 | 2% |
| 2604.06585v1 | astro-ph.GA | 85 | 3 | 2 | 0 | 1 | 4% |
| 2604.06648v1 | astro-ph.GA | 89 | 8 | 8 | 0 | 0 | 3% |
| 2604.06559v1 | cs.SE | 30 | 0 | 0 | 0 | 0 | 13% |

## By rule

| Rule | Real | False positive | Unclear |
|---|---|---|---|
| REF001 | 10 | 0 | 0 |
| REF002 | 3 | 0 | 0 |
| REF003 | 2 | 0 | 0 |
| REF010 | 2 | 0 | 0 |
| REF011 | 20 | 3 | 4 |
| REF012 | 9 | 3 | 0 |
| REF013 | 0 | 1 | 2 |
| REF014 | 3 | 0 | 0 |
| REF015 | 60 | 0 | 0 |
| REF017 | 72 | 0 | 0 |
