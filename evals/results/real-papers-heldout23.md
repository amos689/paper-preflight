# Real papers (heldout23 batch)

- **Tool:** paper-preflight 0.8.0, commit 6fa65e6
- **Papers:** 20 arXiv papers first submitted 2026-04-15..21, chosen mechanically (`evals/real_papers.py`, manifest `evals/real_papers_heldout23.toml`)
- **Run:** 2026-10-15, live sources (answers cached for the day, so a rerun with fixed code asks again only what changed; a cold run of 20 papers takes about 20 minutes)
- **Flags:** warnings and errors about references; every one reviewed by hand (`evals/real_papers_review.toml`)

## Summary

| References checked | Flags | Real problems | False positives | Unclear | False positives per 100 references | Cannot determine |
|---|---|---|---|---|---|---|
| 1341 | 226 | 194 | 28 | 4 | 2.1 | 5% |

## By paper

| Paper | Category | References | Flags | Real | False positive | Unclear | Cannot determine |
|---|---|---|---|---|---|---|---|
| 2604.13368v1 | cs.CL | 17 | 0 | 0 | 0 | 0 | 6% |
| 2604.13371v1 | cs.CL | 30 | 14 | 13 | 0 | 1 | 23% |
| 2604.13398v1 | cs.CL | 52 | 10 | 10 | 0 | 0 | 4% |
| 2604.14237v1 | cs.LG | 40 | 1 | 1 | 0 | 0 | 2% |
| 2604.13366v2 | cs.LG | 27 | 4 | 4 | 0 | 0 | 0% |
| 2604.13386v1 | cs.LG | 17 | 7 | 7 | 0 | 0 | 12% |
| 2604.13367v1 | cs.CV | 37 | 17 | 17 | 0 | 0 | 0% |
| 2604.13383v1 | cs.CV | 58 | 8 | 6 | 2 | 0 | 0% |
| 2604.13403v1 | cs.CV | 49 | 20 | 20 | 0 | 0 | 2% |
| 2604.13392v2 | cs.AI | 33 | 12 | 11 | 1 | 0 | 3% |
| 2604.13395v1 | cs.AI | 40 | 8 | 7 | 1 | 0 | 2% |
| 2604.13484v1 | stat.ML | 39 | 4 | 3 | 1 | 0 | 3% |
| 2604.13525v1 | stat.ML | 49 | 25 | 23 | 2 | 0 | 0% |
| 2604.15391v1 | q-bio.QM | 83 | 7 | 6 | 1 | 0 | 4% |
| 2604.15520v1 | q-bio.QM | 34 | 0 | 0 | 0 | 0 | 3% |
| 2604.13363v1 | quant-ph | 41 | 26 | 26 | 0 | 0 | 0% |
| 2604.13375v2 | quant-ph | 430 | 56 | 34 | 20 | 2 | 8% |
| 2604.13374v2 | astro-ph.GA | 95 | 3 | 2 | 0 | 1 | 5% |
| 2604.13408v1 | astro-ph.GA | 123 | 2 | 2 | 0 | 0 | 0% |
| 2604.13462v1 | cs.SE | 47 | 2 | 2 | 0 | 0 | 30% |

## By rule

| Rule | Real | False positive | Unclear |
|---|---|---|---|
| REF001 | 12 | 0 | 0 |
| REF002 | 8 | 1 | 0 |
| REF003 | 0 | 1 | 0 |
| REF010 | 1 | 1 | 0 |
| REF011 | 31 | 15 | 1 |
| REF012 | 8 | 7 | 3 |
| REF013 | 5 | 3 | 0 |
| REF014 | 7 | 0 | 0 |
| REF015 | 61 | 0 | 0 |
| REF017 | 61 | 0 | 0 |
