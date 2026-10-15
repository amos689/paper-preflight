# Real papers (heldout28 batch)

- **Tool:** paper-preflight 0.8.0, commit 0afb1b9
- **Papers:** 20 arXiv papers first submitted 2026-03-11..17, chosen mechanically (`evals/real_papers.py`, manifest `evals/real_papers_heldout28.toml`)
- **Run:** 2026-10-15, live sources (answers cached for the day, so a rerun with fixed code asks again only what changed; a cold run of 20 papers takes about 20 minutes)
- **Flags:** warnings and errors about references; every one reviewed by hand (`evals/real_papers_review.toml`)

## Summary

| References checked | Flags | Real problems | False positives | Unclear | False positives per 100 references | Cannot determine |
|---|---|---|---|---|---|---|
| 898 | 104 | 95 | 8 | 1 | 0.9 | 4% |

## By paper

| Paper | Category | References | Flags | Real | False positive | Unclear | Cannot determine |
|---|---|---|---|---|---|---|---|
| 2603.10303v1 | cs.CL | 48 | 9 | 9 | 0 | 0 | 8% |
| 2604.00019v1 | cs.CL | 33 | 1 | 1 | 0 | 0 | 6% |
| 2603.10313v1 | cs.CL | 53 | 17 | 14 | 3 | 0 | 8% |
| 2603.10299v1 | cs.LG | 50 | 4 | 4 | 0 | 0 | 2% |
| 2603.10301v2 | cs.LG | 27 | 5 | 5 | 0 | 0 | 4% |
| 2603.10302v3 | cs.LG | 70 | 8 | 7 | 1 | 0 | 3% |
| 2603.10300v3 | cs.CV | 48 | 15 | 14 | 0 | 1 | 6% |
| 2603.10335v1 | cs.CV | 45 | 6 | 6 | 0 | 0 | 7% |
| 2603.10340v1 | cs.CV | 32 | 2 | 2 | 0 | 0 | 0% |
| 2603.10359v2 | cs.AI | 31 | 0 | 0 | 0 | 0 | 6% |
| 2603.10384v3 | cs.AI | 67 | 16 | 16 | 0 | 0 | 3% |
| 2603.10287v2 | stat.ML | 22 | 2 | 0 | 2 | 0 | 9% |
| 2603.10435v1 | stat.ML | 24 | 6 | 6 | 0 | 0 | 4% |
| 2603.10454v1 | q-bio.QM | 49 | 2 | 1 | 1 | 0 | 0% |
| 2603.12294v2 | q-bio.QM | 17 | 1 | 1 | 0 | 0 | 6% |
| 2603.10289v2 | quant-ph | 40 | 5 | 5 | 0 | 0 | 2% |
| 2603.10296v2 | quant-ph | 44 | 1 | 0 | 1 | 0 | 0% |
| 2603.10579v2 | astro-ph.GA | 79 | 2 | 2 | 0 | 0 | 4% |
| 2603.10581v2 | astro-ph.GA | 98 | 1 | 1 | 0 | 0 | 0% |
| 2603.10558v1 | cs.SE | 21 | 1 | 1 | 0 | 0 | 14% |

## By rule

| Rule | Real | False positive | Unclear |
|---|---|---|---|
| REF002 | 3 | 0 | 0 |
| REF003 | 2 | 1 | 1 |
| REF010 | 1 | 1 | 0 |
| REF011 | 1 | 2 | 0 |
| REF012 | 2 | 3 | 0 |
| REF013 | 0 | 1 | 0 |
| REF015 | 63 | 0 | 0 |
| REF017 | 23 | 0 | 0 |
