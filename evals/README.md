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
