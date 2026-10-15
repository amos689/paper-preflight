# Real papers (heldout20 batch)

- **Tool:** paper-preflight 0.8.0, commit 68fe09a
- **Papers:** 20 arXiv papers first submitted 2026-05-06..12, chosen mechanically (`evals/real_papers.py`, manifest `evals/real_papers_heldout20.toml`)
- **Run:** 2026-10-15, live sources (answers cached for the day, so a rerun with fixed code asks again only what changed; a cold run of 20 papers takes about 20 minutes)
- **Flags:** warnings and errors about references; every one reviewed by hand (`evals/real_papers_review.toml`)

## Summary

| References checked | Flags | Real problems | False positives | Unclear | False positives per 100 references | Cannot determine |
|---|---|---|---|---|---|---|
| 950 | 133 | 126 | 7 | 0 | 0.7 | 3% |

## By paper

| Paper | Category | References | Flags | Real | False positive | Unclear | Cannot determine |
|---|---|---|---|---|---|---|---|
| 2605.04449v1 | cs.CL | 54 | 21 | 21 | 0 | 0 | 4% |
| 2605.04458v2 | cs.CL | 39 | 7 | 6 | 1 | 0 | 3% |
| 2605.04495v2 | cs.CL | 41 | 28 | 28 | 0 | 0 | 0% |
| 2605.04363v2 | cs.LG | 43 | 5 | 5 | 0 | 0 | 2% |
| 2605.04364v1 | cs.LG | 32 | 1 | 1 | 0 | 0 | 0% |
| 2605.04368v1 | cs.LG | 36 | 2 | 1 | 1 | 0 | 6% |
| 2605.04397v1 | cs.CV | 37 | 1 | 1 | 0 | 0 | 3% |
| 2605.04405v1 | cs.CV | 61 | 5 | 5 | 0 | 0 | 2% |
| 2605.04409v1 | cs.CV | 64 | 18 | 16 | 2 | 0 | 0% |
| 2605.04454v1 | cs.AI | 24 | 3 | 3 | 0 | 0 | 4% |
| 2605.04572v1 | cs.AI | 44 | 5 | 5 | 0 | 0 | 2% |
| 2605.05262v1 | stat.ML | 31 | 15 | 14 | 1 | 0 | 0% |
| 2605.04589v3 | stat.ML | 40 | 1 | 0 | 1 | 0 | 32% |
| 2605.06598v1 | q-bio.QM | 32 | 1 | 1 | 0 | 0 | 6% |
| 2605.06995v1 | q-bio.QM | 50 | 4 | 4 | 0 | 0 | 2% |
| 2605.05256v2 | quant-ph | 34 | 0 | 0 | 0 | 0 | 0% |
| 2605.04416v1 | quant-ph | 51 | 5 | 5 | 0 | 0 | 6% |
| 2605.04434v1 | astro-ph.GA | 38 | 2 | 2 | 0 | 0 | 0% |
| 2605.04537v1 | astro-ph.GA | 117 | 1 | 0 | 1 | 0 | 1% |
| 2605.04431v1 | cs.SE | 82 | 8 | 8 | 0 | 0 | 0% |

## By rule

| Rule | Real | False positive | Unclear |
|---|---|---|---|
| REF001 | 1 | 1 | 0 |
| REF002 | 5 | 0 | 0 |
| REF003 | 1 | 0 | 0 |
| REF010 | 1 | 0 | 0 |
| REF011 | 21 | 1 | 0 |
| REF012 | 2 | 2 | 0 |
| REF013 | 3 | 2 | 0 |
| REF014 | 0 | 1 | 0 |
| REF015 | 58 | 0 | 0 |
| REF017 | 34 | 0 | 0 |
