# Real papers (heldout11 batch)

- **Tool:** paper-preflight 0.5.3, commit e6c07a2
- **Papers:** 20 arXiv papers first submitted 2026-09-16..22, chosen mechanically (`evals/real_papers.py`, manifest `evals/real_papers_heldout11.toml`)
- **Run:** 2026-10-08, live sources (answers cached for the day, so a rerun with fixed code asks again only what changed; a cold run of 20 papers takes about 20 minutes)
- **Flags:** warnings and errors about references; every one reviewed by hand (`evals/real_papers_review.toml`)

## Summary

| References checked | Flags | Real problems | False positives | Unclear | False positives per 100 references | Cannot determine |
|---|---|---|---|---|---|---|
| 868 | 89 | 76 | 13 | 0 | 1.5 | 4% |

## By paper

| Paper | Category | References | Flags | Real | False positive | Unclear | Cannot determine |
|---|---|---|---|---|---|---|---|
| 2609.17956v3 | cs.CL | 33 | 11 | 9 | 2 | 0 | 0% |
| 2609.18047v1 | cs.CL | 31 | 4 | 3 | 1 | 0 | 13% |
| 2609.18135v1 | cs.CL | 45 | 12 | 12 | 0 | 0 | 7% |
| 2609.17942v1 | cs.LG | 64 | 1 | 0 | 1 | 0 | 3% |
| 2609.17943v1 | cs.LG | 48 | 1 | 0 | 1 | 0 | 10% |
| 2609.17997v1 | cs.LG | 30 | 7 | 7 | 0 | 0 | 7% |
| 2609.17953v1 | cs.CV | 50 | 7 | 7 | 0 | 0 | 10% |
| 2609.18034v1 | cs.CV | 43 | 9 | 9 | 0 | 0 | 0% |
| 2609.18037v1 | cs.CV | 34 | 1 | 1 | 0 | 0 | 0% |
| 2609.17969v1 | cs.AI | 64 | 10 | 10 | 0 | 0 | 3% |
| 2609.17983v1 | cs.AI | 17 | 3 | 3 | 0 | 0 | 0% |
| 2609.18118v1 | stat.ML | 32 | 3 | 3 | 0 | 0 | 0% |
| 2609.19202v1 | stat.ML | 27 | 4 | 4 | 0 | 0 | 11% |
| 2609.18631v1 | q-bio.QM | 60 | 2 | 0 | 2 | 0 | 3% |
| 2609.21394v1 | q-bio.QM | 34 | 1 | 0 | 1 | 0 | 0% |
| 2609.17979v1 | quant-ph | 37 | 3 | 1 | 2 | 0 | 0% |
| 2609.17991v1 | quant-ph | 33 | 5 | 5 | 0 | 0 | 12% |
| 2609.18006v1 | astro-ph.GA | 33 | 0 | 0 | 0 | 0 | 0% |
| 2609.18160v1 | astro-ph.GA | 91 | 4 | 1 | 3 | 0 | 1% |
| 2609.18291v1 | cs.SE | 62 | 1 | 1 | 0 | 0 | 8% |

## By rule

| Rule | Real | False positive | Unclear |
|---|---|---|---|
| REF001 | 1 | 0 | 0 |
| REF002 | 1 | 0 | 0 |
| REF003 | 2 | 2 | 0 |
| REF010 | 1 | 0 | 0 |
| REF011 | 5 | 5 | 0 |
| REF012 | 0 | 2 | 0 |
| REF013 | 7 | 3 | 0 |
| REF014 | 0 | 1 | 0 |
| REF015 | 51 | 0 | 0 |
| REF017 | 8 | 0 | 0 |
