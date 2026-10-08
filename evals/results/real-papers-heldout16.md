# Real papers (heldout16 batch)

- **Tool:** paper-preflight 0.8.0 code with #191 and #193, main 7c6146c
- **Papers:** 20 arXiv papers first submitted 2026-06-10..16, chosen mechanically (`evals/real_papers.py`, manifest `evals/real_papers_heldout16.toml`)
- **Run:** 2026-10-08, live sources (answers cached for the day, so a rerun with fixed code asks again only what changed; a cold run of 20 papers takes about 20 minutes)
- **Flags:** warnings and errors about references; every one reviewed by hand (`evals/real_papers_review.toml`)

## Summary

| References checked | Flags | Real problems | False positives | Unclear | False positives per 100 references | Cannot determine |
|---|---|---|---|---|---|---|
| 983 | 90 | 71 | 18 | 1 | 1.8 | 3% |

## By paper

| Paper | Category | References | Flags | Real | False positive | Unclear | Cannot determine |
|---|---|---|---|---|---|---|---|
| 2606.11531v1 | cs.CL | 36 | 1 | 1 | 0 | 0 | 8% |
| 2606.11542v1 | cs.CL | 27 | 9 | 9 | 0 | 0 | 11% |
| 2606.11552v2 | cs.CL | 67 | 6 | 6 | 0 | 0 | 3% |
| 2606.11553v1 | cs.LG | 16 | 1 | 1 | 0 | 0 | 25% |
| 2606.11562v1 | cs.LG | 40 | 6 | 4 | 2 | 0 | 5% |
| 2606.11574v1 | cs.LG | 95 | 9 | 7 | 2 | 0 | 0% |
| 2606.11546v1 | cs.CV | 46 | 4 | 4 | 0 | 0 | 0% |
| 2606.11563v1 | cs.CV | 24 | 6 | 6 | 0 | 0 | 0% |
| 2606.11568v1 | cs.CV | 78 | 9 | 4 | 4 | 1 | 4% |
| 2606.11537v2 | cs.AI | 55 | 6 | 6 | 0 | 0 | 0% |
| 2606.11543v1 | cs.AI | 25 | 4 | 4 | 0 | 0 | 4% |
| 2606.11570v2 | stat.ML | 42 | 3 | 2 | 1 | 0 | 0% |
| 2606.11738v1 | stat.ML | 25 | 1 | 0 | 1 | 0 | 0% |
| 2606.12209v1 | q-bio.QM | 26 | 6 | 6 | 0 | 0 | 4% |
| 2606.13475v2 | q-bio.QM | 30 | 0 | 0 | 0 | 0 | 0% |
| 2606.11530v1 | quant-ph | 28 | 1 | 1 | 0 | 0 | 0% |
| 2606.11561v2 | quant-ph | 51 | 0 | 0 | 0 | 0 | 2% |
| 2606.12076v1 | astro-ph.GA | 108 | 5 | 2 | 3 | 0 | 1% |
| 2606.12249v2 | astro-ph.GA | 123 | 6 | 1 | 5 | 0 | 1% |
| 2606.11755v1 | cs.SE | 41 | 7 | 7 | 0 | 0 | 10% |

## By rule

| Rule | Real | False positive | Unclear |
|---|---|---|---|
| REF001 | 0 | 1 | 0 |
| REF002 | 4 | 0 | 0 |
| REF003 | 5 | 5 | 0 |
| REF010 | 1 | 1 | 0 |
| REF011 | 5 | 5 | 1 |
| REF012 | 4 | 2 | 0 |
| REF013 | 2 | 3 | 0 |
| REF014 | 5 | 1 | 0 |
| REF015 | 43 | 0 | 0 |
| REF017 | 2 | 0 | 0 |
