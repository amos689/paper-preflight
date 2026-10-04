# Real papers (heldout3 batch)

- **Tool:** paper-preflight 0.2.0, commit 33364b7
- **Papers:** 20 arXiv papers first submitted 2026-07-22..28, chosen mechanically (`evals/real_papers.py`, manifest `evals/real_papers_heldout3.toml`)
- **Run:** 2026-10-04, live sources (answers cached for the day, so a rerun with fixed code asks again only what changed; a cold run of 20 papers takes about 20 minutes)
- **Flags:** warnings and errors about references; every one reviewed by hand (`evals/real_papers_review.toml`)

## Summary

| References checked | Flags | Real problems | False positives | Unclear | False positives per 100 references | Cannot determine |
|---|---|---|---|---|---|---|
| 831 | 96 | 92 | 3 | 1 | 0.4 | 3% |

## By paper

| Paper | Category | References | Flags | Real | False positive | Unclear | Cannot determine |
|---|---|---|---|---|---|---|---|
| 2607.19678v1 | cs.CL | 26 | 9 | 9 | 0 | 0 | 0% |
| 2607.19686v3 | cs.CL | 56 | 3 | 3 | 0 | 0 | 0% |
| 2607.19691v2 | cs.CL | 25 | 6 | 5 | 0 | 1 | 0% |
| 2607.21647v1 | cs.LG | 39 | 0 | 0 | 0 | 0 | 8% |
| 2607.19659v1 | cs.LG | 24 | 1 | 1 | 0 | 0 | 4% |
| 2609.17560v1 | cs.LG | 47 | 1 | 1 | 0 | 0 | 2% |
| 2607.22722v1 | cs.CV | 26 | 1 | 1 | 0 | 0 | 0% |
| 2607.19669v1 | cs.CV | 48 | 2 | 1 | 1 | 0 | 4% |
| 2607.19711v1 | cs.CV | 50 | 3 | 3 | 0 | 0 | 0% |
| 2607.19767v1 | cs.AI | 9 | 1 | 1 | 0 | 0 | 0% |
| 2607.27230v2 | cs.AI | 47 | 15 | 15 | 0 | 0 | 19% |
| 2607.19689v1 | stat.ML | 40 | 3 | 3 | 0 | 0 | 2% |
| 2607.19692v1 | stat.ML | 39 | 4 | 4 | 0 | 0 | 5% |
| 2607.20044v1 | q-bio.QM | 35 | 4 | 4 | 0 | 0 | 3% |
| 2607.20215v1 | q-bio.QM | 17 | 1 | 0 | 1 | 0 | 0% |
| 2607.19702v1 | quant-ph | 22 | 0 | 0 | 0 | 0 | 5% |
| 2607.19770v1 | quant-ph | 16 | 1 | 1 | 0 | 0 | 0% |
| 2607.19640v1 | astro-ph.GA | 107 | 22 | 22 | 0 | 0 | 1% |
| 2607.19717v2 | astro-ph.GA | 106 | 2 | 1 | 1 | 0 | 0% |
| 2607.19653v1 | cs.SE | 52 | 17 | 17 | 0 | 0 | 13% |

## By rule

| Rule | Real | False positive | Unclear |
|---|---|---|---|
| REF001 | 2 | 0 | 0 |
| REF003 | 1 | 0 | 0 |
| REF010 | 2 | 0 | 0 |
| REF011 | 15 | 0 | 1 |
| REF012 | 4 | 2 | 0 |
| REF013 | 2 | 1 | 0 |
| REF014 | 1 | 0 | 0 |
| REF015 | 62 | 0 | 0 |
| REF017 | 3 | 0 | 0 |
