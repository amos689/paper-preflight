# Real papers (heldout22 batch)

- **Tool:** paper-preflight 0.8.0, commit 9b01194
- **Papers:** 20 arXiv papers first submitted 2026-04-22..28, chosen mechanically (`evals/real_papers.py`, manifest `evals/real_papers_heldout22.toml`)
- **Run:** 2026-10-15, live sources (answers cached for the day, so a rerun with fixed code asks again only what changed; a cold run of 20 papers takes about 20 minutes)
- **Flags:** warnings and errors about references; every one reviewed by hand (`evals/real_papers_review.toml`)

## Summary

| References checked | Flags | Real problems | False positives | Unclear | False positives per 100 references | Cannot determine |
|---|---|---|---|---|---|---|
| 910 | 126 | 114 | 11 | 1 | 1.2 | 4% |

## By paper

| Paper | Category | References | Flags | Real | False positive | Unclear | Cannot determine |
|---|---|---|---|---|---|---|---|
| 2604.20117v1 | cs.CL | 23 | 11 | 11 | 0 | 0 | 0% |
| 2604.20131v1 | cs.CL | 48 | 6 | 5 | 1 | 0 | 10% |
| 2604.20135v1 | cs.CL | 30 | 5 | 5 | 0 | 0 | 0% |
| 2604.20079v1 | cs.LG | 50 | 20 | 16 | 3 | 1 | 6% |
| 2604.20082v1 | cs.LG | 49 | 8 | 8 | 0 | 0 | 2% |
| 2604.20083v1 | cs.LG | 54 | 1 | 1 | 0 | 0 | 2% |
| 2604.22847v1 | cs.CV | 46 | 6 | 6 | 0 | 0 | 9% |
| 2604.20093v1 | cs.CV | 55 | 8 | 8 | 0 | 0 | 0% |
| 2604.20128v1 | cs.CV | 53 | 6 | 6 | 0 | 0 | 4% |
| 2605.23930v1 | cs.AI | 18 | 5 | 4 | 1 | 0 | 11% |
| 2604.20133v3 | cs.AI | 26 | 4 | 4 | 0 | 0 | 31% |
| 2604.20296v1 | stat.ML | 41 | 2 | 1 | 1 | 0 | 0% |
| 2604.20301v1 | stat.ML | 30 | 6 | 6 | 0 | 0 | 0% |
| 2604.20263v1 | q-bio.QM | 52 | 6 | 5 | 1 | 0 | 6% |
| 2604.20615v3 | q-bio.QM | 89 | 8 | 7 | 1 | 0 | 1% |
| 2604.20088v3 | quant-ph | 40 | 4 | 4 | 0 | 0 | 8% |
| 2604.20103v1 | quant-ph | 26 | 4 | 4 | 0 | 0 | 0% |
| 2604.20080v1 | astro-ph.GA | 77 | 0 | 0 | 0 | 0 | 1% |
| 2604.20344v1 | astro-ph.GA | 60 | 6 | 4 | 2 | 0 | 0% |
| 2604.20926v3 | cs.SE | 43 | 10 | 9 | 1 | 0 | 7% |

## By rule

| Rule | Real | False positive | Unclear |
|---|---|---|---|
| REF001 | 2 | 0 | 0 |
| REF002 | 1 | 0 | 0 |
| REF003 | 3 | 2 | 1 |
| REF011 | 12 | 4 | 0 |
| REF012 | 1 | 2 | 0 |
| REF013 | 2 | 1 | 0 |
| REF014 | 1 | 1 | 0 |
| REF015 | 69 | 0 | 0 |
| REF017 | 23 | 0 | 0 |
| REF020 | 0 | 1 | 0 |
