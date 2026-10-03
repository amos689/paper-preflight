# Real papers (heldout batch)

- **Tool:** paper-preflight 0.1.0, commit 37191c7
- **Papers:** 20 arXiv papers first submitted 2026-07-08..14, chosen mechanically (`evals/real_papers.py`, manifest `evals/real_papers_heldout.toml`)
- **Run:** 2026-10-03, live sources (answers cached for the day, so a rerun with fixed code asks again only what changed; a cold run of 20 papers takes about 20 minutes)
- **Flags:** warnings and errors about references; every one reviewed by hand (`evals/real_papers_review.toml`)

## Summary

| References checked | Flags | Real problems | False positives | Unclear | False positives per 100 references | Cannot determine |
|---|---|---|---|---|---|---|
| 921 | 109 | 84 | 21 | 4 | 2.3 | 6% |

## By paper

| Paper | Category | References | Flags | Real | False positive | Unclear | Cannot determine |
|---|---|---|---|---|---|---|---|
| 2607.06974v1 | cs.CL | 56 | 15 | 14 | 1 | 0 | 0% |
| 2607.07047v3 | cs.CL | 56 | 9 | 6 | 2 | 1 | 0% |
| 2607.07050v6 | cs.CL | 33 | 2 | 2 | 0 | 0 | 6% |
| 2607.06879v1 | cs.LG | 53 | 1 | 1 | 0 | 0 | 4% |
| 2607.06922v1 | cs.LG | 50 | 8 | 4 | 4 | 0 | 4% |
| 2607.06924v1 | cs.LG | 18 | 3 | 3 | 0 | 0 | 0% |
| 2607.06871v1 | cs.CV | 38 | 12 | 12 | 0 | 0 | 3% |
| 2607.06872v2 | cs.CV | 36 | 3 | 1 | 2 | 0 | 25% |
| 2607.06875v1 | cs.CV | 40 | 12 | 11 | 1 | 0 | 8% |
| 2607.20518v1 | cs.AI | 31 | 6 | 6 | 0 | 0 | 29% |
| 2608.28607v1 | cs.AI | 18 | 4 | 1 | 1 | 2 | 0% |
| 2607.07008v1 | stat.ML | 32 | 0 | 0 | 0 | 0 | 22% |
| 2607.07232v1 | stat.ML | 57 | 2 | 2 | 0 | 0 | 4% |
| 2608.04024v1 | q-bio.QM | 50 | 8 | 6 | 2 | 0 | 10% |
| 2607.07425v1 | q-bio.QM | 54 | 4 | 1 | 3 | 0 | 6% |
| 2607.06888v1 | quant-ph | 62 | 4 | 2 | 2 | 0 | 2% |
| 2607.16271v1 | quant-ph | 55 | 0 | 0 | 0 | 0 | 5% |
| 2607.06891v2 | astro-ph.GA | 39 | 9 | 8 | 0 | 1 | 3% |
| 2607.06902v1 | astro-ph.GA | 81 | 3 | 1 | 2 | 0 | 2% |
| 2607.06873v1 | cs.SE | 62 | 4 | 3 | 1 | 0 | 5% |

## By rule

| Rule | Real | False positive | Unclear |
|---|---|---|---|
| REF001 | 2 | 0 | 0 |
| REF002 | 2 | 0 | 0 |
| REF003 | 0 | 7 | 0 |
| REF010 | 2 | 0 | 0 |
| REF011 | 11 | 3 | 1 |
| REF012 | 3 | 5 | 2 |
| REF013 | 1 | 5 | 1 |
| REF015 | 56 | 1 | 0 |
| REF017 | 7 | 0 | 0 |
