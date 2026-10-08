# Real-world recall: GPTZero's hallucinated references (NeurIPS 2025, ICLR 2026)

- **Tool:** paper-preflight 0.8.0 (commit a46524c)
- **Data:** the references GPTZero's staff confirmed as hallucinated: 100 in NeurIPS 2025 papers, 51 in ICLR 2026 submissions ([NeurIPS](https://gptzero.me/news/neurips/), [ICLR](https://gptzero.me/news/iclr-2026/)). The tables are not redistributed; rows are numbered as in GPTZero's tables.
- **Input:** each reference as the paper printed it, read by paper-preflight's plain-text reader (`check refs.txt`), checked against live sources
- **Run:** 2026-10-08

## Summary

| Set | References | Flagged | Cannot determine | Missed | Disputed |
|---|---|---|---|---|---|
| iclr2026 | 51 | 47 (92%) | 4 | 0 | 0 |
| neurips2025 | 100 | 95 (95%) | 5 | 0 | 0 |
| **all** | 151 | **142 (94%)** | 9 | 0 | 0 |

## By kind of hallucination

Kinds are read from GPTZero's comments.

| Kind | Flagged | Cannot determine | Missed | Disputed |
|---|---|---|---|---|
| identifier of another work | 13 | 0 | 0 | 0 |
| incomplete identifier | 3 | 0 | 0 | 0 |
| no such work | 92 | 7 | 0 | 0 |
| other | 1 | 0 | 0 | 0 |
| real work, other details wrong | 9 | 1 | 0 | 0 |
| real work, wrong authors | 24 | 1 | 0 | 0 |

## Not flagged, reviewed

| Set | Row | Kind | Verdict | Review | Reason |
|---|---|---|---|---|---|
| iclr2026 | 6 | real work, wrong authors | cannot_determine | miss | A workshop (DEEM 2020) that no queried source indexes. |
| iclr2026 | 19 | no such work | cannot_determine | miss | Garbled author ('Ishita et al. Bardhan.'): too little to search. |
| iclr2026 | 39 | no such work | cannot_determine | miss | A blog URL: web content is not judged. |
| iclr2026 | 45 | real work, other details wrong | cannot_determine | miss | A placeholder URL (example.com) and no venue: grey literature is not judged. |
| neurips2025 | 23 | no such work | cannot_determine | miss | A similar real title by other authors: abstained as ambiguous. |
| neurips2025 | 58 | no such work | cannot_determine | miss | No author and a garbled title: abstained as ambiguous. |
| neurips2025 | 80 | no such work | cannot_determine | miss | A Distill URL: web content is not judged. |
| neurips2025 | 81 | no such work | cannot_determine | miss | No venue, as for a blog post: grey literature is not judged. |
| neurips2025 | 85 | no such work | cannot_determine | miss | A real survey title with invented authors; several surveys share the title: abstained as ambiguous. |
