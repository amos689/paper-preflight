# PDF reference lists (dev batch)

- **Tool:** paper-preflight 0.1.2 with the PDF reader (`check paper.pdf`, the `pdf` extra)
- **Papers:** the 20 papers of `evals/real_papers.toml` whose PDF arXiv serves; each PDF read with `check paper.pdf` (the `pdf` extra) and compared with the check of the paper's own .bib
- **Run:** 2026-10-04 (`evals/pdf_agreement.py`)

| References checked from the .bib | Found in the PDF | Same first author | Same year | Same verdict |
|---|---|---|---|---|
| 924 | 814/924 (88%) | 795/814 (98%) | 774/814 (95%) | 749/814 (92%) |

| Paper | Category | .bib references | Read from the PDF | Found | Same verdict |
|---|---|---|---|---|---|
| 2607.00339v1 | cs.CL | 45 | 45 | 40 | 40 |
| 2607.00368v1 | cs.CL | 41 | 41 | 41 | 38 |
| 2607.00415v1 | cs.CL | 23 | 22 | 21 | 21 |
| 2607.00301v1 | cs.LG | 20 | 22 | 19 | 19 |
| 2607.00325v1 | cs.LG | 22 | 21 | 21 | 21 |
| 2607.19378v3 | cs.LG | 53 | 53 | 42 | 41 |
| 2607.02582v1 | cs.CV | 33 | 33 | 23 | 22 |
| 2607.00289v1 | cs.CV | 54 | 54 | 51 | 51 |
| 2607.00293v1 | cs.CV | 72 | 72 | 69 | 69 |
| 2607.00407v2 | cs.AI | 54 | 54 | 49 | 46 |
| 2607.00454v1 | cs.AI | 17 | 17 | 17 | 17 |
| 2607.00320v1 | stat.ML | 59 | 59 | 47 | 45 |
| 2607.00877v1 | stat.ML | 45 | 45 | 39 | 37 |
| 2607.01749v1 | q-bio.QM | 65 | 65 | 65 | 62 |
| 2607.02103v1 | q-bio.QM | 25 | 25 | 22 | 20 |
| 2607.00284v1 | quant-ph | 46 | 46 | 32 | 30 |
| 2607.00307v1 | quant-ph | 35 | 35 | 29 | 27 |
| 2607.00291v1 | astro-ph.GA | 105 | 81 | 87 | 60 |
| 2607.00305v1 | astro-ph.GA | 51 | 49 | 48 | 33 |
| 2607.02583v1 | cs.SE | 59 | 59 | 52 | 50 |
