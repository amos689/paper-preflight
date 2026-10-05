# Real-world recall: GPTZero's hallucinated references (NeurIPS 2025, ICLR 2026)

- **Tool:** paper-preflight 0.3.0
- **Data:** the references GPTZero's staff confirmed as hallucinated: 100 in NeurIPS 2025 papers, 51 in ICLR 2026 submissions ([NeurIPS](https://gptzero.me/news/neurips/), [ICLR](https://gptzero.me/news/iclr-2026/)). The tables are not redistributed; rows are numbered as in GPTZero's tables.
- **Input:** each reference as the paper printed it, read by paper-preflight's plain-text reader (`check refs.txt`), checked against live sources
- **Run:** 2026-10-05

## Summary

| Set | References | Flagged | Cannot determine | Missed | Disputed |
|---|---|---|---|---|---|
| iclr2026 | 51 | 41 (80%) | 10 | 0 | 0 |
| neurips2025 | 100 | 88 (88%) | 12 | 0 | 0 |
| **all** | 151 | **129 (85%)** | 22 | 0 | 0 |

## By kind of hallucination

Kinds are read from GPTZero's comments.

| Kind | Flagged | Cannot determine | Missed | Disputed |
|---|---|---|---|---|
| identifier of another work | 13 | 0 | 0 | 0 |
| incomplete identifier | 3 | 0 | 0 | 0 |
| no such work | 84 | 15 | 0 | 0 |
| other | 1 | 0 | 0 | 0 |
| real work, other details wrong | 9 | 1 | 0 | 0 |
| real work, wrong authors | 19 | 6 | 0 | 0 |

## Not flagged, reviewed

| Set | Row | Kind | Verdict | Review | Reason |
|---|---|---|---|---|---|
| iclr2026 | 4 | real work, wrong authors | cannot_determine | miss | The arXiv URL is broken by a space ('arxiv.org/ abs/2501.17727'), so the ID was not read; with no venue the entry counted as grey literature. |
| iclr2026 | 5 | real work, wrong authors | cannot_determine | miss | The plain-text reader read no authors or title (a long author list with a garbled name). |
| iclr2026 | 6 | real work, wrong authors | cannot_determine | miss | A workshop (DEEM 2020) that no queried source indexes. |
| iclr2026 | 19 | no such work | cannot_determine | miss | Garbled author ('Ishita et al. Bardhan.'): too little to search. |
| iclr2026 | 24 | real work, wrong authors | cannot_determine | miss | A real title (Colas et al., NeurIPS 2020) with another author and journal: abstained as ambiguous. |
| iclr2026 | 27 | no such work | cannot_determine | miss | The plain-text reader missed the venue ('In 2009 IEEE/WIC/ACM ...'); with no venue the entry counted as grey literature. |
| iclr2026 | 36 | real work, wrong authors | cannot_determine | miss | The plain-text reader read no authors or title (lowercase name part, 'Yun chen Chen'). |
| iclr2026 | 39 | no such work | cannot_determine | miss | A blog URL: web content is not judged. |
| iclr2026 | 45 | real work, other details wrong | cannot_determine | miss | A placeholder URL (example.com) and no venue: grey literature is not judged. |
| iclr2026 | 48 | no such work | cannot_determine | miss | A second reference number inside the reference ('[3] K. Arnold, ...') confused the plain-text reader. |
| neurips2025 | 12 | no such work | cannot_determine | miss | Short title (3 words): not searched as a 'not found' candidate. |
| neurips2025 | 14 | no such work | cannot_determine | miss | Short title (4 words) with an ICLR 2025 venue: not searched as a 'not found' candidate. |
| neurips2025 | 23 | no such work | cannot_determine | miss | A similar real title by other authors: abstained as ambiguous. |
| neurips2025 | 37 | no such work | cannot_determine | miss | The real SoftMatch title with invented authors: abstained as ambiguous. |
| neurips2025 | 40 | no such work | cannot_determine | miss | Short title (4 words) with an ICLR 2022 venue: not searched as a 'not found' candidate. |
| neurips2025 | 43 | no such work | cannot_determine | miss | The plain-text reader read no authors or title (accented first name, 'Yu' as a middle name). |
| neurips2025 | 57 | real work, wrong authors | cannot_determine | miss | The plain-text reader missed the venue ('In 37th International Conference ...'); with no venue the entry counted as grey literature. |
| neurips2025 | 58 | no such work | cannot_determine | miss | No author and a garbled title: abstained as ambiguous. |
| neurips2025 | 61 | no such work | cannot_determine | miss | The plain-text reader took the journal into the title ('$9(1): 39-56,2001$'); with no venue the entry counted as grey literature. |
| neurips2025 | 80 | no such work | cannot_determine | miss | A Distill URL: web content is not judged. |
| neurips2025 | 81 | no such work | cannot_determine | miss | No venue, as for a blog post: grey literature is not judged. |
| neurips2025 | 85 | no such work | cannot_determine | miss | A real survey title with invented authors; several surveys share the title: abstained as ambiguous. |
