# `support`: does a cited work say what the citation claims?

- **Tool:** paper-preflight 0.3.0 candidate (`paper-preflight support`, experimental), main after #116
- **Data:** the citation-support gold set, `evals/support_gold.toml`: 298 pairs of a citing sentence and a cited work. The sentences come from 55 arXiv papers of July 2026 under CC BY, CC BY-SA or CC0. 250 pairs are the papers' real citations. 48 are mis-citations made on purpose: the cited work swapped for another work the same paper cites.
- **Labels:** made by AI models, not by experts (see below)
- **Run:** 2026-10-04 and 2026-10-05, CPU, cited works' text fetched live, then scored offline

## What `support` says

For each citation, `support` reads the cited work's text, ranks its passages for the claim, and has a local model score the best ones. It says one of two things:

- **supported**: a passage scores at least 0.4, quoted word for word;
- **could not confirm**: with the reason. The reason is that no text could be had, that only the abstract could be had, or that no passage was close enough.

It never says that a citation is wrong. The reason is the last section.

## The gold set

| | Pairs |
|---|---|
| Real citations | 250 |
| … supported | 130 |
| … partially supported | 46 |
| … not supported | 8 (3%) |
| … cannot determine (text too thin, or no text) | 66 |
| Mis-citations (cited work swapped) | 48 |
| … not supported | 30 |
| … partially supported or supported (the swapped work happens to be on topic) | 16 |
| … cannot determine | 2 |

The text found for the 277 cited works (S2, #116):

| Text found | Works |
|---|---|
| Full text from the arXiv source | 120 |
| Full text from an open-access PDF | 49 |
| Full text from an arXiv PDF | 3 |
| Abstract only | 78 |
| No text | 27 |

**How the labels were made.**
1. Two AI annotators labelled each pair with text to read (270 pairs): Claude Sonnet (A) and Claude Opus (B), following `evals/support_guidelines.md`. Each saw the claim, its sentence and the cited work's text, but no verifier score.
2. They agreed on 68% of the pairs (Cohen's κ 0.55). A third, Claude Fable (C), labelled the 87 pairs they disagreed on, and the majority label stands.
3. Pairs where all three disagreed were decided by reading the evidence (`evals/support_adjudication.toml`).
4. A 20% spot check of the agreed labels re-judged 37 pairs and corrected one.
5. Pairs with no text are "cannot determine".

Steps 3 and 4 were done by the AI assistant that built `support`. The labels are therefore AI judgements throughout, and they may share a model's blind spots. Read every number below with that in mind.

## Which verifier

Each verifier reads the 4 passages ranked best for the claim. "Real citations confirmed" is the share of the 250 real citations that `support` confirms.

| Verifier | Passages | Threshold | Said "supported" | Right [95% CI] | Supported citations confirmed | Real citations confirmed | Mis-citations confirmed |
|---|---|---|---|---|---|---|---|
| FactCG-DeBERTa-v3-Large | top 4 | 0.4 | 20 | 75% [53%, 89%] | 14/130 (11%) | 19/250 (8%) | 0 |
| FactCG-DeBERTa-v3-Large | top 4 | 0.6 | 8 | 100% [68%, 100%] | 7/130 (5%) | 7/250 (3%) | 0 |
| MiniCheck-Flan-T5-Large | top 4 | 0.4 | 25 | 92% [75%, 98%] | 21/130 (16%) | 22/250 (9%) | 0 |
| MiniCheck-Flan-T5-Large | top 4 | 0.9 | 12 | 100% [76%, 100%] | 10/130 (8%) | 10/250 (4%) | 0 |
| **HHEM-2.1-open** (default) | top 4 | **0.4** | 35 | **97% [85%, 99%]** | 30/130 (23%) | 31/250 (12%) | 0 |
| HHEM-2.1-open | top 4 | 0.6 | 23 | 100% [86%, 100%] | 19/130 (15%) | 19/250 (8%) | 0 |

HHEM is right most often and confirms the most. It is also the smallest model (0.4 GB, Flan-T5-base). One of its 35 confirmations is labelled "cannot determine"; none is labelled not supported.

## How many passages to read

Reading more of a work's text finds a few more confirmations, but it is right less often. The comparison uses the 191 pairs whose cited work has full text: HHEM scored every passage (at most 400 per work), and each budget is the best score among the top k by BM25.

| Passages read | Said "supported" | Right [95% CI] | Supported citations confirmed | Real citations confirmed |
|---|---|---|---|---|
| **top 4** (default) | 35 | **97% [85%, 99%]** | 30/96 (31%) | 31/143 (22%) |
| top 8 | 39 | 92% [80%, 97%] | 32/96 (33%) | 34/143 (24%) |
| top 12 | 41 | 90% [77%, 96%] | 33/96 (34%) | 36/143 (25%) |
| top 20 | 41 | 90% [77%, 96%] | 33/96 (34%) | 36/143 (25%) |
| every passage | 45 | 89% [77%, 95%] | 36/96 (38%) | 40/143 (28%) |

The default is 4 passages at 0.4.

## Why it never says "not supported"

A low best score is weak evidence of a mis-citation. The table counts full-text pairs whose best passage scores below a threshold, and how many of them are labelled not supported. The 48 swapped citations are included, so mis-citations are far more common here than in real papers.

| Verifier | Best score below | Said | Labelled not supported |
|---|---|---|---|
| FactCG | 0.02 | 11 | 45% |
| FactCG | 0.1 | 122 | 26% |
| MiniCheck | 0.02 | 34 | 35% |
| MiniCheck | 0.1 | 142 | 27% |
| HHEM | 0.02 | 46 | 37% |
| HHEM | 0.1 | 120 | 28% |

Genuine citations often paraphrase loosely, cite a dataset or method by name, or rest on a part of the work the text does not contain. In real papers only about 3% of citations are not supported (8 of 250 here). A "not supported" verdict would therefore be wrong far more often than right, so `support` only says what it could not confirm, and why.

## Limits

- **Small and AI-labelled.** The confidence intervals are wide, and the labels are not experts'.
- **Mostly computer science and physics.** The papers are recent arXiv papers, and their cited works are mostly on arXiv too. Fields where cited works are paywalled will see far more "only the abstract" answers.
- **Abstracts rarely confirm anything.** Of the 79 real pairs with only an abstract, 2 were confirmed.
- **A claim is the sentence, or the clause, around the citation.** A citation that only names a method or dataset ("trained with Adam \cite{x} on ImageNet \cite{y}") is asked to support the whole clause, which its work seldom says.

## Speed

On a laptop CPU:
- the demo paper (11 references) takes 24 s;
- arXiv 2607.00415 (24 citations of 19 works, 8 confirmed) takes 2.5 minutes the first time. Most of that is fetching the cited works' text, since arXiv asks for one download every three seconds. A second run takes 40 s, because the downloads are cached.

## Reproduce

```bash
uv sync --extra support
uv run python evals/support_gold.py fetch            # the cited works' text (network)
uv run python evals/support_gold.py packets
uv run python evals/support_labels.py final          # final labels from the annotators' files
uv run python evals/support_eval.py score hhem       # also factcg, minicheck
uv run python evals/support_eval.py score hhem --every-passage
uv run python evals/support_eval.py report
```

The annotators' label files and the cited works' text stay out of the repository (`evals/.data/`). The gold set keeps claims, labels and identifiers only.
