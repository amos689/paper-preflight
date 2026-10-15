# Real papers (heldout21 batch)

- **Tool:** paper-preflight 0.8.0, commit 68fe09a
- **Papers:** 20 arXiv papers first submitted 2026-04-29..05-05, chosen mechanically (`evals/real_papers.py`, manifest `evals/real_papers_heldout21.toml`)
- **Run:** 2026-10-15, live sources (answers cached for the day, so a rerun with fixed code asks again only what changed; a cold run of 20 papers takes about 20 minutes)
- **Flags:** warnings and errors about references; every one reviewed by hand (`evals/real_papers_review.toml`)

## Summary

| References checked | Flags | Real problems | False positives | Unclear | False positives per 100 references | Cannot determine |
|---|---|---|---|---|---|---|
| 1118 | 106 | 84 | 19 | 3 | 1.7 | 2% |

## By paper

| Paper | Category | References | Flags | Real | False positive | Unclear | Cannot determine |
|---|---|---|---|---|---|---|---|
| 2604.26209v1 | cs.CL | 43 | 5 | 5 | 0 | 0 | 7% |
| 2605.00905v1 | cs.CL | 19 | 0 | 0 | 0 | 0 | 11% |
| 2604.26243v1 | cs.CL | 36 | 7 | 6 | 0 | 1 | 8% |
| 2604.26188v1 | cs.LG | 35 | 4 | 4 | 0 | 0 | 0% |
| 2604.26256v2 | cs.LG | 48 | 9 | 8 | 1 | 0 | 4% |
| 2604.27003v1 | cs.LG | 35 | 10 | 10 | 0 | 0 | 0% |
| 2604.26186v1 | cs.CV | 44 | 4 | 3 | 1 | 0 | 0% |
| 2604.26218v1 | cs.CV | 45 | 5 | 5 | 0 | 0 | 0% |
| 2604.26221v1 | cs.CV | 43 | 6 | 6 | 0 | 0 | 2% |
| 2604.26211v1 | cs.AI | 30 | 7 | 6 | 1 | 0 | 10% |
| 2607.16198v1 | cs.AI | 126 | 15 | 11 | 3 | 1 | 0% |
| 2604.26673v1 | stat.ML | 49 | 10 | 7 | 3 | 0 | 2% |
| 2604.27025v2 | stat.ML | 49 | 2 | 1 | 0 | 1 | 2% |
| 2605.00272v2 | q-bio.QM | 58 | 1 | 0 | 1 | 0 | 0% |
| 2605.00479v1 | q-bio.QM | 45 | 2 | 1 | 1 | 0 | 7% |
| 2604.26263v3 | quant-ph | 48 | 8 | 7 | 1 | 0 | 4% |
| 2604.26267v2 | quant-ph | 54 | 0 | 0 | 0 | 0 | 0% |
| 2604.26195v1 | astro-ph.GA | 155 | 3 | 0 | 3 | 0 | 1% |
| 2604.26389v1 | astro-ph.GA | 111 | 6 | 2 | 4 | 0 | 2% |
| 2604.26192v1 | cs.SE | 45 | 2 | 2 | 0 | 0 | 4% |

## By rule

| Rule | Real | False positive | Unclear |
|---|---|---|---|
| REF001 | 3 | 0 | 0 |
| REF002 | 5 | 0 | 0 |
| REF003 | 0 | 7 | 1 |
| REF011 | 8 | 1 | 1 |
| REF012 | 4 | 4 | 0 |
| REF013 | 4 | 4 | 1 |
| REF014 | 0 | 2 | 0 |
| REF015 | 42 | 0 | 0 |
| REF017 | 18 | 0 | 0 |
| REF020 | 0 | 1 | 0 |
