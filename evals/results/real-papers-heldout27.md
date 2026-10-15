# Real papers (heldout27 batch)

- **Tool:** paper-preflight 0.8.0, commit 0afb1b9
- **Papers:** 20 arXiv papers first submitted 2026-03-18..24, chosen mechanically (`evals/real_papers.py`, manifest `evals/real_papers_heldout27.toml`)
- **Run:** 2026-10-15, live sources (answers cached for the day, so a rerun with fixed code asks again only what changed; a cold run of 20 papers takes about 20 minutes)
- **Flags:** warnings and errors about references; every one reviewed by hand (`evals/real_papers_review.toml`)

## Summary

| References checked | Flags | Real problems | False positives | Unclear | False positives per 100 references | Cannot determine |
|---|---|---|---|---|---|---|
| 1007 | 110 | 105 | 5 | 0 | 0.5 | 2% |

## By paper

| Paper | Category | References | Flags | Real | False positive | Unclear | Cannot determine |
|---|---|---|---|---|---|---|---|
| 2603.17231v1 | cs.CL | 55 | 3 | 3 | 0 | 0 | 2% |
| 2604.08563v1 | cs.CL | 20 | 6 | 6 | 0 | 0 | 5% |
| 2604.13058v3 | cs.CL | 45 | 6 | 5 | 1 | 0 | 13% |
| 2603.17247v1 | cs.LG | 33 | 2 | 2 | 0 | 0 | 3% |
| 2603.17248v1 | cs.LG | 31 | 1 | 0 | 1 | 0 | 10% |
| 2603.17255v1 | cs.LG | 107 | 2 | 2 | 0 | 0 | 0% |
| 2603.17227v3 | cs.CV | 51 | 2 | 2 | 0 | 0 | 0% |
| 2603.17228v1 | cs.CV | 45 | 0 | 0 | 0 | 0 | 0% |
| 2603.17240v2 | cs.CV | 65 | 21 | 21 | 0 | 0 | 0% |
| 2603.17233v2 | cs.AI | 30 | 4 | 4 | 0 | 0 | 10% |
| 2603.17310v2 | cs.AI | 47 | 13 | 13 | 0 | 0 | 4% |
| 2603.17527v2 | stat.ML | 31 | 0 | 0 | 0 | 0 | 3% |
| 2603.17551v1 | stat.ML | 25 | 31 | 30 | 1 | 0 | 4% |
| 2603.19326v1 | q-bio.QM | 50 | 1 | 1 | 0 | 0 | 2% |
| 2603.17765v1 | q-bio.QM | 21 | 8 | 8 | 0 | 0 | 5% |
| 2603.17250v1 | quant-ph | 97 | 5 | 4 | 1 | 0 | 0% |
| 2603.17253v1 | quant-ph | 76 | 2 | 2 | 0 | 0 | 0% |
| 2603.17254v3 | astro-ph.GA | 69 | 0 | 0 | 0 | 0 | 0% |
| 2603.17299v2 | astro-ph.GA | 30 | 1 | 0 | 1 | 0 | 0% |
| 2603.17266v1 | cs.SE | 79 | 2 | 2 | 0 | 0 | 3% |

## By rule

| Rule | Real | False positive | Unclear |
|---|---|---|---|
| REF001 | 1 | 0 | 0 |
| REF003 | 3 | 1 | 0 |
| REF010 | 1 | 0 | 0 |
| REF011 | 3 | 2 | 0 |
| REF012 | 1 | 2 | 0 |
| REF013 | 4 | 0 | 0 |
| REF015 | 54 | 0 | 0 |
| REF017 | 38 | 0 | 0 |
