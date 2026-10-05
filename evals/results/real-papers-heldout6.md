# Real papers (heldout6 batch)

- **Tool:** paper-preflight 0.3.0, commit f06720f
- **Papers:** 20 arXiv papers first submitted 2026-08-12..18, chosen mechanically (`evals/real_papers.py`, manifest `evals/real_papers_heldout6.toml`)
- **Run:** 2026-10-05, live sources (answers cached for the day, so a rerun with fixed code asks again only what changed; a cold run of 20 papers takes about 20 minutes)
- **Flags:** warnings and errors about references; every one reviewed by hand (`evals/real_papers_review.toml`)

## Summary

| References checked | Flags | Real problems | False positives | Unclear | False positives per 100 references | Cannot determine |
|---|---|---|---|---|---|---|
| 753 | 86 | 77 | 9 | 0 | 1.2 | 15% |

## By paper

| Paper | Category | References | Flags | Real | False positive | Unclear | Cannot determine |
|---|---|---|---|---|---|---|---|
| 2608.11528v1 | cs.CL | 37 | 3 | 3 | 0 | 0 | 0% |
| 2609.22097v1 | cs.CL | 75 | 8 | 8 | 0 | 0 | 8% |
| 2608.11531v1 | cs.CL | 21 | 6 | 6 | 0 | 0 | 10% |
| 2608.11541v1 | cs.LG | 35 | 0 | 0 | 0 | 0 | 3% |
| 2608.11560v1 | cs.LG | 26 | 3 | 3 | 0 | 0 | 4% |
| 2609.30275v1 | cs.LG | 17 | 0 | 0 | 0 | 0 | 6% |
| 2608.11518v1 | cs.CV | 26 | 3 | 1 | 2 | 0 | 12% |
| 2608.11537v1 | cs.CV | 46 | 4 | 4 | 0 | 0 | 0% |
| 2608.11546v2 | cs.CV | 37 | 6 | 6 | 0 | 0 | 5% |
| 2608.11583v1 | cs.AI | 31 | 5 | 5 | 0 | 0 | 3% |
| 2608.11584v1 | cs.AI | 37 | 23 | 23 | 0 | 0 | 8% |
| 2608.11544v2 | stat.ML | 46 | 2 | 0 | 2 | 0 | 9% |
| 2608.12973v2 | stat.ML | 32 | 2 | 2 | 0 | 0 | 0% |
| 2608.16951v1 | q-bio.QM | 31 | 10 | 7 | 3 | 0 | 19% |
| 2608.15843v1 | q-bio.QM | 21 | 2 | 1 | 1 | 0 | 10% |
| 2608.11516v1 | quant-ph | 36 | 5 | 5 | 0 | 0 | 3% |
| 2608.11556v1 | quant-ph | 42 | 0 | 0 | 0 | 0 | 7% |
| 2608.11575v1 | astro-ph.GA | 86 | 2 | 2 | 0 | 0 | 88% |
| 2608.11729v1 | astro-ph.GA | 31 | 0 | 0 | 0 | 0 | 3% |
| 2608.11744v1 | cs.SE | 40 | 2 | 1 | 1 | 0 | 8% |

## By rule

| Rule | Real | False positive | Unclear |
|---|---|---|---|
| REF003 | 2 | 2 | 0 |
| REF010 | 2 | 1 | 0 |
| REF011 | 7 | 1 | 0 |
| REF012 | 3 | 2 | 0 |
| REF013 | 1 | 2 | 0 |
| REF014 | 0 | 1 | 0 |
| REF015 | 41 | 0 | 0 |
| REF017 | 21 | 0 | 0 |
