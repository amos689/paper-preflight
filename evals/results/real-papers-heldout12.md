# Real papers (heldout12 batch)

- **Tool:** paper-preflight 0.5.3, commit a418bad
- **Papers:** 20 arXiv papers first submitted 2026-09-23..29, chosen mechanically (`evals/real_papers.py`, manifest `evals/real_papers_heldout12.toml`)
- **Run:** 2026-10-08, live sources (answers cached for the day, so a rerun with fixed code asks again only what changed; a cold run of 20 papers takes about 20 minutes)
- **Flags:** warnings and errors about references; every one reviewed by hand (`evals/real_papers_review.toml`)

## Summary

| References checked | Flags | Real problems | False positives | Unclear | False positives per 100 references | Cannot determine |
|---|---|---|---|---|---|---|
| 786 | 48 | 42 | 6 | 0 | 0.8 | 3% |

## By paper

| Paper | Category | References | Flags | Real | False positive | Unclear | Cannot determine |
|---|---|---|---|---|---|---|---|
| 2609.27173v1 | cs.CL | 58 | 1 | 1 | 0 | 0 | 21% |
| 2609.27176v2 | cs.CL | 29 | 7 | 6 | 1 | 0 | 0% |
| 2609.27205v1 | cs.CL | 36 | 1 | 1 | 0 | 0 | 3% |
| 2609.27186v1 | cs.LG | 21 | 0 | 0 | 0 | 0 | 5% |
| 2609.27199v1 | cs.LG | 46 | 3 | 3 | 0 | 0 | 0% |
| 2609.27201v1 | cs.LG | 46 | 7 | 6 | 1 | 0 | 0% |
| 2609.27194v1 | cs.CV | 37 | 7 | 7 | 0 | 0 | 8% |
| 2609.27208v1 | cs.CV | 24 | 1 | 1 | 0 | 0 | 0% |
| 2609.27238v1 | cs.CV | 25 | 2 | 1 | 1 | 0 | 0% |
| 2610.00233v1 | cs.AI | 20 | 2 | 2 | 0 | 0 | 0% |
| 2609.27197v1 | cs.AI | 16 | 7 | 7 | 0 | 0 | 0% |
| 2609.27180v1 | stat.ML | 37 | 6 | 5 | 1 | 0 | 5% |
| 2609.27206v1 | stat.ML | 52 | 0 | 0 | 0 | 0 | 2% |
| 2609.27207v1 | q-bio.QM | 41 | 0 | 0 | 0 | 0 | 0% |
| 2609.27668v1 | q-bio.QM | 47 | 3 | 1 | 2 | 0 | 2% |
| 2609.27177v1 | quant-ph | 39 | 1 | 1 | 0 | 0 | 0% |
| 2609.27390v1 | quant-ph | 77 | 0 | 0 | 0 | 0 | 0% |
| 2609.27432v1 | astro-ph.GA | 60 | 0 | 0 | 0 | 0 | 3% |
| 2609.27460v1 | astro-ph.GA | 55 | 0 | 0 | 0 | 0 | 0% |
| 2609.27214v1 | cs.SE | 20 | 0 | 0 | 0 | 0 | 0% |

## By rule

| Rule | Real | False positive | Unclear |
|---|---|---|---|
| REF002 | 1 | 0 | 0 |
| REF003 | 0 | 1 | 0 |
| REF010 | 1 | 0 | 0 |
| REF011 | 6 | 0 | 0 |
| REF012 | 2 | 3 | 0 |
| REF013 | 1 | 2 | 0 |
| REF014 | 1 | 0 | 0 |
| REF015 | 24 | 0 | 0 |
| REF017 | 6 | 0 | 0 |
