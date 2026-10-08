# Real papers (heldout10 batch)

- **Tool:** paper-preflight 0.5.2, commit 3d80331
- **Papers:** 20 arXiv papers first submitted 2026-09-09..15, chosen mechanically (`evals/real_papers.py`, manifest `evals/real_papers_heldout10.toml`)
- **Run:** 2026-10-08, live sources (answers cached for the day, so a rerun with fixed code asks again only what changed; a cold run of 20 papers takes about 20 minutes)
- **Flags:** warnings and errors about references; every one reviewed by hand (`evals/real_papers_review.toml`)

## Summary

| References checked | Flags | Real problems | False positives | Unclear | False positives per 100 references | Cannot determine |
|---|---|---|---|---|---|---|
| 1067 | 98 | 83 | 14 | 1 | 1.3 | 8% |

## By paper

| Paper | Category | References | Flags | Real | False positive | Unclear | Cannot determine |
|---|---|---|---|---|---|---|---|
| 2609.09552v1 | cs.CL | 24 | 3 | 3 | 0 | 0 | 4% |
| 2609.09561v1 | cs.CL | 44 | 5 | 2 | 3 | 0 | 0% |
| 2609.09569v1 | cs.CL | 18 | 2 | 0 | 2 | 0 | 0% |
| 2609.09564v1 | cs.LG | 44 | 8 | 8 | 0 | 0 | 11% |
| 2609.09567v2 | cs.LG | 53 | 8 | 8 | 0 | 0 | 11% |
| 2609.09595v1 | cs.LG | 56 | 11 | 10 | 1 | 0 | 2% |
| 2609.09606v1 | cs.CV | 65 | 1 | 1 | 0 | 0 | 0% |
| 2609.09610v1 | cs.CV | 60 | 9 | 8 | 0 | 1 | 3% |
| 2609.09626v1 | cs.CV | 65 | 3 | 3 | 0 | 0 | 0% |
| 2609.09565v1 | cs.AI | 40 | 9 | 8 | 1 | 0 | 5% |
| 2609.09589v2 | cs.AI | 45 | 0 | 0 | 0 | 0 | 0% |
| 2609.09556v3 | stat.ML | 43 | 2 | 1 | 1 | 0 | 2% |
| 2609.09572v1 | stat.ML | 73 | 15 | 15 | 0 | 0 | 0% |
| 2609.10121v2 | q-bio.QM | 46 | 0 | 0 | 0 | 0 | 100% |
| 2609.11994v2 | q-bio.QM | 4 | 0 | 0 | 0 | 0 | 25% |
| 2609.09571v2 | quant-ph | 58 | 0 | 0 | 0 | 0 | 2% |
| 2609.09582v2 | quant-ph | 69 | 5 | 1 | 4 | 0 | 17% |
| 2609.09645v2 | astro-ph.GA | 101 | 1 | 0 | 1 | 0 | 1% |
| 2609.09729v1 | astro-ph.GA | 119 | 2 | 1 | 1 | 0 | 2% |
| 2609.09769v1 | cs.SE | 40 | 14 | 14 | 0 | 0 | 12% |

## By rule

| Rule | Real | False positive | Unclear |
|---|---|---|---|
| REF002 | 1 | 2 | 0 |
| REF003 | 3 | 1 | 1 |
| REF011 | 8 | 3 | 0 |
| REF012 | 2 | 2 | 0 |
| REF013 | 3 | 2 | 0 |
| REF014 | 0 | 2 | 0 |
| REF015 | 51 | 2 | 0 |
| REF017 | 15 | 0 | 0 |
