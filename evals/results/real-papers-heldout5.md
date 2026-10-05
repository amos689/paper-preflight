# Real papers (heldout5 batch)

- **Tool:** paper-preflight 0.3.0, commit 30263bd
- **Papers:** 20 arXiv papers first submitted 2026-08-05..11, chosen mechanically (`evals/real_papers.py`, manifest `evals/real_papers_heldout5.toml`)
- **Run:** 2026-10-05, live sources (answers cached for the day, so a rerun with fixed code asks again only what changed; a cold run of 20 papers takes about 20 minutes)
- **Flags:** warnings and errors about references; every one reviewed by hand (`evals/real_papers_review.toml`)

## Summary

| References checked | Flags | Real problems | False positives | Unclear | False positives per 100 references | Cannot determine |
|---|---|---|---|---|---|---|
| 1043 | 136 | 109 | 20 | 7 | 1.9 | 6% |

## By paper

| Paper | Category | References | Flags | Real | False positive | Unclear | Cannot determine |
|---|---|---|---|---|---|---|---|
| 2608.04299v1 | cs.CL | 20 | 4 | 3 | 1 | 0 | 15% |
| 2608.04307v1 | cs.CL | 21 | 7 | 6 | 1 | 0 | 10% |
| 2608.04311v1 | cs.CL | 28 | 9 | 7 | 1 | 1 | 4% |
| 2608.04305v1 | cs.LG | 37 | 0 | 0 | 0 | 0 | 8% |
| 2608.04310v3 | cs.LG | 48 | 10 | 5 | 5 | 0 | 23% |
| 2608.04324v1 | cs.LG | 41 | 1 | 0 | 1 | 0 | 2% |
| 2608.04302v1 | cs.CV | 41 | 16 | 14 | 2 | 0 | 0% |
| 2608.04348v1 | cs.CV | 81 | 5 | 5 | 0 | 0 | 10% |
| 2608.04349v1 | cs.CV | 46 | 12 | 12 | 0 | 0 | 4% |
| 2608.04358v1 | cs.AI | 92 | 13 | 12 | 1 | 0 | 3% |
| 2608.04384v2 | cs.AI | 37 | 6 | 5 | 0 | 1 | 5% |
| 2608.05230v1 | stat.ML | 32 | 14 | 12 | 1 | 1 | 6% |
| 2608.04827v1 | stat.ML | 43 | 8 | 5 | 2 | 1 | 12% |
| 2608.05697v1 | q-bio.QM | 48 | 5 | 3 | 2 | 0 | 15% |
| 2608.05777v2 | q-bio.QM | 65 | 1 | 0 | 1 | 0 | 5% |
| 2608.04369v1 | quant-ph | 94 | 4 | 4 | 0 | 0 | 2% |
| 2608.04481v1 | quant-ph | 80 | 11 | 11 | 0 | 0 | 1% |
| 2608.04362v1 | astro-ph.GA | 42 | 1 | 1 | 0 | 0 | 0% |
| 2608.04371v1 | astro-ph.GA | 93 | 5 | 1 | 2 | 2 | 3% |
| 2608.04336v1 | cs.SE | 54 | 4 | 3 | 0 | 1 | 9% |

## By rule

| Rule | Real | False positive | Unclear |
|---|---|---|---|
| REF001 | 4 | 1 | 0 |
| REF002 | 6 | 0 | 0 |
| REF003 | 3 | 4 | 1 |
| REF011 | 17 | 9 | 1 |
| REF012 | 11 | 3 | 0 |
| REF013 | 1 | 0 | 5 |
| REF014 | 3 | 3 | 0 |
| REF015 | 53 | 0 | 0 |
| REF017 | 11 | 0 | 0 |
