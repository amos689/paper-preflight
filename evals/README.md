# Evaluation

paper-preflight is scored on public benchmarks of hallucinated references. The benchmark data
is not committed: `evals/datasets.lock` pins every file by SHA-256, and spike S8
(`docs/spikes/S8-datasets.md`) records where each dataset comes from.

## HALLMARK

[HALLMARK](https://github.com/rpatrik96/hallmark) v1.2.3 (MIT) labels BibTeX entries VALID or
HALLUCINATED, with 14 hallucination types in three difficulty tiers. Three types (merged
citations, partial author lists, arXiv version mismatches) are stress tests that HALLMARK
evaluates separately; so do we.

```bash
uv run python evals/run_hallmark.py --split dev_public --sample 120   # stratified sample
uv run python evals/run_hallmark.py --split dev_public                # all 1119 entries
```

The run queries the real sources with your credentials from the environment, exactly like
`paper-preflight check`, and takes about 2 seconds per entry on a cold cache. Answers are cached
in `evals/.cache/`, so an interrupted or repeated run only asks for what is missing.

### How a prediction is scored

Each entry ends in one of three outcomes. There is no forced yes/no:

| Outcome | Meaning |
|---|---|
| flag | a finding from the mode's rule set was raised |
| clean | a definite verdict without such a finding |
| abstain | `cannot_determine`: the tool declined to judge (ADR-0002) |

| Mode | Rules that count as a flag |
|---|---|
| `fabrication` | REF001 (identifier points elsewhere), REF002 (identifier does not exist), REF003 (not found), REF010 (no author in common) |
| `any_issue` | the above plus REF011–REF014 (authors, title, year, venue differ) |

Info-level findings never count. REF015 (a cited preprint was published), REF004/REF005
(retractions, corrections) and REF017 (identifier formatting) are advice about real works, not
hallucinations, so they do not count either.

- **Precision** is computed over flags.
- **Recall** is conservative: an abstention on a hallucinated entry counts as a miss.
- **Coverage** is the share of entries with a definite answer.
- **False-positive rate** is the share of VALID entries that were flagged; for a pre-submission
  gate this matters most.

### Results

`evals/results/hallmark-<split>[-sample<N>].md` holds the summary of a run (committed); the
`.jsonl` next to it has one line per entry (git-ignored).

### Held-out split

Rules are developed and their misses studied on `dev_public` only. `test_public` is run to
check that the numbers generalise, and its individual entries are not inspected to change a
rule, so that it stays a fair estimate. (HALLMARK's `test_hidden` split is not public.)

### Disputed labels

Some entries HALLMARK labels VALID are not correct citations: their DOI points to another paper,
or their author list names people who did not write the paper. Each one was checked by hand
against the registries; `evals/hallmark_disputed.toml` lists them with a reason that one lookup
can confirm. Results are always reported as HALLMARK labels them, and every summary adds a
second table without the disputed entries, so both numbers are visible. Reports of further
label problems are welcome as issues.

## Real papers

Benchmarks perturb real entries; real `.bib` files are messier: books, theses, talks, software,
workshop papers, odd fields. `evals/real_papers.py` checks the bibliographies of arXiv papers
chosen mechanically: in each category, papers first submitted in one week, in submission order,
kept when their source has a main `.tex` and a `.bib` with at least 20 entries. Every warning
and error is then reviewed by hand and recorded in `evals/real_papers_review.toml` as
*correct* (the entry really has the problem), *false positive* or *unclear*, with a reason one
lookup can confirm.

```bash
uv run python evals/real_papers.py collect --batch heldout   # pick and download the papers
uv run python evals/real_papers.py run --batch heldout       # check them against live sources
uv run python evals/real_papers.py report --batch heldout    # combine with the manual review
```

There are two batches of 20 papers, each with the same mix (cs.CL 3, cs.LG 3, cs.CV 3, cs.AI 2,
stat.ML 2, q-bio.QM 2, quant-ph 2, astro-ph.GA 2, cs.SE 1):

| Batch | Papers first submitted | Role | References | Flags | Real problems | False positives | Unclear | False positives per 100 references |
|---|---|---|---|---|---|---|---|---|
| `dev` | 2026-07-01..07 | its false positives were studied and fixed (#58–#69) | 924 | 72 | 65 | 1 | 6 | 0.1 |
| `heldout` | 2026-07-08..14 | collected after those fixes, reported as it came out | 921 | 109 | 84 | 21 | 4 | 2.3 |

- **On `dev`**, paper-preflight 0.1.0 raised 113 flags: 65 real problems, 42 false positives (4.5
  per 100 references). The fixes removed false positives without losing a real problem.
- **On `heldout`**, 56 of the 84 real problems are cited preprints that have since been
  published (REF015, advice); the other 28 are errors in the entry: wrong or invented authors,
  DOIs that do not exist or belong to another paper, wrong titles, a DOI written as a URL. Of
  the 21 false positives, 7 are real works no source indexes (a talk, papers from the 1950s and
  60s: REF003), and most others are records of a related publication of the same title (a thesis
  abstract, a technical report, the arXiv order of authors: REF011-REF013). The first run of
  this batch, before #72-#74, found 2.4 false positives per 100 references.
- **The held-out flags were reviewed, not used to change a rule.** Fixing what they show would
  make this batch a development batch; measuring those fixes will need a new week of papers.
- The sources are not committed (arXiv's default licence does not allow redistribution); the
  manifests `evals/real_papers.toml` and `evals/real_papers_heldout.toml` list the IDs.
