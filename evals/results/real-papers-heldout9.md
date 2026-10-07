# Real papers (heldout9 batch)

- **Tool:** paper-preflight 0.5.1, commit 4c1e1ef
- **Papers:** 20 arXiv papers first submitted 2026-09-02..08, chosen mechanically (`evals/real_papers.py`, manifest `evals/real_papers_heldout9.toml`)
- **Run:** 2026-10-07, live sources (answers cached for the day, so a rerun with fixed code asks again only what changed; a cold run of 20 papers takes about 20 minutes)
- **Flags:** warnings and errors about references; every one reviewed by hand (`evals/real_papers_review.toml`)

## Summary

| References checked | Flags | Real problems | False positives | Unclear | False positives per 100 references | Cannot determine |
|---|---|---|---|---|---|---|
| 975 | 48 | 31 | 13 | 4 | 1.3 | 5% |

## By paper

| Paper | Category | References | Flags | Real | False positive | Unclear | Cannot determine |
|---|---|---|---|---|---|---|---|
| 2609.01971v2 | cs.CL | 40 | 4 | 2 | 1 | 1 | 5% |
| 2609.02954v1 | cs.CL | 41 | 4 | 2 | 1 | 1 | 20% |
| 2609.02015v1 | cs.CL | 24 | 0 | 0 | 0 | 0 | 4% |
| 2609.01967v1 | cs.LG | 20 | 0 | 0 | 0 | 0 | 15% |
| 2609.02006v1 | cs.LG | 28 | 5 | 4 | 1 | 0 | 4% |
| 2609.02018v1 | cs.LG | 62 | 2 | 1 | 1 | 0 | 3% |
| 2609.01963v1 | cs.CV | 61 | 2 | 2 | 0 | 0 | 0% |
| 2609.05532v1 | cs.CV | 34 | 4 | 2 | 2 | 0 | 3% |
| 2609.01997v1 | cs.CV | 48 | 3 | 2 | 1 | 0 | 10% |
| 2609.01982v2 | cs.AI | 35 | 5 | 4 | 0 | 1 | 29% |
| 2609.02029v1 | cs.AI | 38 | 2 | 1 | 1 | 0 | 11% |
| 2609.01999v1 | stat.ML | 32 | 5 | 5 | 0 | 0 | 9% |
| 2609.02138v1 | stat.ML | 43 | 0 | 0 | 0 | 0 | 0% |
| 2609.02963v1 | q-bio.QM | 39 | 1 | 1 | 0 | 0 | 0% |
| 2609.04261v1 | q-bio.QM | 22 | 3 | 1 | 2 | 0 | 0% |
| 2609.01988v1 | quant-ph | 28 | 1 | 1 | 0 | 0 | 0% |
| 2609.01993v2 | quant-ph | 62 | 1 | 1 | 0 | 0 | 2% |
| 2609.02167v1 | astro-ph.GA | 73 | 1 | 0 | 1 | 0 | 0% |
| 2609.02179v1 | astro-ph.GA | 208 | 2 | 2 | 0 | 0 | 0% |
| 2610.00027v1 | cs.SE | 37 | 3 | 0 | 2 | 1 | 8% |

## By rule

| Rule | Real | False positive | Unclear |
|---|---|---|---|
| REF001 | 3 | 0 | 0 |
| REF003 | 0 | 5 | 0 |
| REF010 | 0 | 1 | 0 |
| REF011 | 2 | 3 | 2 |
| REF012 | 3 | 0 | 0 |
| REF013 | 0 | 3 | 2 |
| REF014 | 1 | 1 | 0 |
| REF015 | 17 | 0 | 0 |
| REF017 | 5 | 0 | 0 |
