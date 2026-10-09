# Real papers (dev3 batch)

- **Tool:** paper-preflight 0.8.0 code with #191, #193 and #195, main 391a0bc
- **Papers:** 20 arXiv papers first submitted 2026-05-27..06-02, chosen mechanically (`evals/real_papers.py`, manifest `evals/real_papers_dev3.toml`)
- **Run:** 2026-10-09, live sources (answers cached for the day, so a rerun with fixed code asks again only what changed; a cold run of 20 papers takes about 20 minutes)
- **Flags:** warnings and errors about references; every one reviewed by hand (`evals/real_papers_review.toml`)

## Summary

| References checked | Flags | Real problems | False positives | Unclear | False positives per 100 references | Cannot determine |
|---|---|---|---|---|---|---|
| 881 | 105 | 89 | 14 | 2 | 1.6 | 4% |

## By paper

| Paper | Category | References | Flags | Real | False positive | Unclear | Cannot determine |
|---|---|---|---|---|---|---|---|
| 2605.27805v1 | cs.CL | 49 | 11 | 11 | 0 | 0 | 8% |
| 2605.27808v1 | cs.CL | 30 | 7 | 7 | 0 | 0 | 10% |
| 2605.27832v1 | cs.CL | 61 | 7 | 7 | 0 | 0 | 3% |
| 2605.27782v1 | cs.LG | 45 | 4 | 3 | 1 | 0 | 11% |
| 2605.27786v3 | cs.LG | 38 | 1 | 1 | 0 | 0 | 5% |
| 2605.27790v2 | cs.LG | 25 | 2 | 2 | 0 | 0 | 0% |
| 2606.00109v1 | cs.CV | 29 | 2 | 2 | 0 | 0 | 0% |
| 2605.27884v1 | cs.CV | 68 | 4 | 3 | 1 | 0 | 0% |
| 2605.27891v1 | cs.CV | 32 | 9 | 9 | 0 | 0 | 12% |
| 2605.27784v2 | cs.AI | 36 | 1 | 1 | 0 | 0 | 0% |
| 2605.27785v1 | cs.AI | 21 | 3 | 2 | 1 | 0 | 29% |
| 2605.27794v1 | stat.ML | 41 | 8 | 6 | 2 | 0 | 0% |
| 2605.27991v4 | stat.ML | 78 | 3 | 1 | 2 | 0 | 1% |
| 2605.29587v1 | q-bio.QM | 34 | 7 | 7 | 0 | 0 | 0% |
| 2605.30399v1 | q-bio.QM | 38 | 13 | 10 | 3 | 0 | 11% |
| 2605.27841v2 | quant-ph | 43 | 0 | 0 | 0 | 0 | 2% |
| 2605.27915v2 | quant-ph | 62 | 9 | 8 | 1 | 0 | 0% |
| 2605.27903v1 | astro-ph.GA | 31 | 2 | 0 | 2 | 0 | 0% |
| 2605.28005v2 | astro-ph.GA | 66 | 4 | 1 | 1 | 2 | 0% |
| 2605.27880v1 | cs.SE | 54 | 8 | 8 | 0 | 0 | 2% |

## By rule

| Rule | Real | False positive | Unclear |
|---|---|---|---|
| REF001 | 1 | 1 | 0 |
| REF003 | 0 | 1 | 0 |
| REF011 | 6 | 3 | 0 |
| REF012 | 3 | 6 | 2 |
| REF013 | 5 | 3 | 0 |
| REF015 | 51 | 0 | 0 |
| REF017 | 23 | 0 | 0 |
