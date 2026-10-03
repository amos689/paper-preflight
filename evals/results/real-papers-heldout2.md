# Real papers (heldout2 batch)

- **Tool:** paper-preflight 0.1.2 candidate, commit f84e119 (main after #91)
- **Papers:** 20 arXiv papers first submitted 2026-07-15..21, chosen mechanically (`evals/real_papers.py`, manifest `evals/real_papers_heldout2.toml`)
- **Run:** 2026-10-03, live sources (answers cached for the day, so a rerun with fixed code asks again only what changed; a cold run of 20 papers takes about 20 minutes)
- **Flags:** warnings and errors about references; every one reviewed by hand (`evals/real_papers_review.toml`)

## Summary

| References checked | Flags | Real problems | False positives | Unclear | False positives per 100 references | Cannot determine |
|---|---|---|---|---|---|---|
| 983 | 80 | 47 | 28 | 5 | 2.8 | 7% |

## By paper

| Paper | Category | References | Flags | Real | False positive | Unclear | Cannot determine |
|---|---|---|---|---|---|---|---|
| 2607.13394v1 | cs.CL | 62 | 5 | 1 | 4 | 0 | 21% |
| 2607.13399v1 | cs.CL | 31 | 3 | 2 | 1 | 0 | 6% |
| 2609.13158v1 | cs.CL | 65 | 10 | 9 | 1 | 0 | 6% |
| 2607.13380v1 | cs.LG | 28 | 2 | 1 | 1 | 0 | 0% |
| 2607.13389v1 | cs.LG | 20 | 8 | 7 | 1 | 0 | 5% |
| 2607.13395v1 | cs.LG | 72 | 4 | 4 | 0 | 0 | 3% |
| 2607.13343v1 | cs.CV | 54 | 4 | 1 | 3 | 0 | 7% |
| 2607.13345v2 | cs.CV | 43 | 3 | 1 | 2 | 0 | 0% |
| 2607.13361v1 | cs.CV | 23 | 8 | 7 | 0 | 1 | 0% |
| 2607.13344v1 | cs.AI | 39 | 5 | 3 | 2 | 0 | 13% |
| 2607.13396v2 | cs.AI | 48 | 4 | 1 | 2 | 1 | 12% |
| 2607.13402v1 | stat.ML | 22 | 1 | 0 | 0 | 1 | 0% |
| 2607.13414v1 | stat.ML | 36 | 4 | 1 | 2 | 1 | 6% |
| 2607.14163v1 | q-bio.QM | 75 | 2 | 0 | 2 | 0 | 0% |
| 2607.15309v1 | q-bio.QM | 41 | 3 | 2 | 1 | 0 | 0% |
| 2607.13342v1 | quant-ph | 57 | 4 | 2 | 2 | 0 | 4% |
| 2607.13351v1 | quant-ph | 74 | 2 | 1 | 1 | 0 | 14% |
| 2607.13711v2 | astro-ph.GA | 22 | 1 | 0 | 1 | 0 | 0% |
| 2607.13739v1 | astro-ph.GA | 142 | 3 | 1 | 2 | 0 | 1% |
| 2609.11941v1 | cs.SE | 29 | 4 | 3 | 0 | 1 | 48% |

## By rule

| Rule | Real | False positive | Unclear |
|---|---|---|---|
| REF001 | 1 | 1 | 0 |
| REF002 | 0 | 1 | 0 |
| REF003 | 0 | 3 | 1 |
| REF010 | 1 | 5 | 0 |
| REF011 | 4 | 9 | 2 |
| REF012 | 1 | 4 | 0 |
| REF013 | 4 | 3 | 2 |
| REF014 | 0 | 1 | 0 |
| REF015 | 20 | 0 | 0 |
| REF017 | 16 | 1 | 0 |
