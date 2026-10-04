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
uv run python evals/real_papers.py collect --batch heldout3   # pick and download the papers
uv run python evals/real_papers.py run --batch heldout3       # check them against live sources
uv run python evals/real_papers.py report --batch heldout3    # combine with the manual review
```

There are four batches of 20 papers, each with the same mix (cs.CL 3, cs.LG 3, cs.CV 3, cs.AI 2,
stat.ML 2, q-bio.QM 2, quant-ph 2, astro-ph.GA 2, cs.SE 1). Each was collected after the fixes
the batches before it led to, and reported as it came out; its own false positives were then
studied, which makes it development data for the next round. The numbers below are the 0.1.2
candidate's (main 43a5544):

| Batch | Papers first submitted | Role | References | Flags | Real problems | False positives | Unclear | False positives per 100 references |
|---|---|---|---|---|---|---|---|---|
| `dev` | 2026-07-01..07 | studied for 0.1.1 (#58-#69) | 924 | 73 | 66 | 1 | 6 | 0.1 |
| `heldout` | 2026-07-08..14 | held out for 0.1.1; studied for 0.1.2 (#78-#91) | 921 | 94 | 85 | 6 | 3 | 0.7 |
| `heldout2` | 2026-07-15..21 | held out for #78-#91 (3.0 as it came out); studied (#94-#98) | 983 | 55 | 46 | 4 | 5 | 0.4 |
| `heldout3` | 2026-07-22..28 | held out for #94-#98 | 814 | 107 | 92 | 14 | 1 | 1.7 |

- **On `dev`**, paper-preflight 0.1.0 raised 113 flags: 65 real problems, 42 false positives (4.5
  per 100 references). The fixes removed false positives without losing a real problem.
- **On `heldout`**, 0.1.1 found 2.3 false positives per 100 references; the fixes for 0.1.2 bring
  that to 0.7, with one more real problem found.
- **On `heldout2`**, as it came out (main f84e119): 46 real problems and 29 false positives, 3.0
  per 100 references. The false positives were a wider spread than before:
  - registry records with errors of their own (a misspelt or reordered author, a footnote
    mark, AAS title markup, Semantic Scholar dropping a word);
  - author names written another way (teams, consortia, a Vietnamese name order, a given name
    added, a family name first without a comma);
  - years that are legitimate but not the record's (a volume year, a conference year);
  - a DOI with angle brackets cut short, and a book's DOI on a chapter;
  - three real works no source indexes (REF003: a workshop paper, an anonymous OpenReview
    submission, a 1996 book chapter).

  #94-#98 removed 25 of the 29, and no real problem. The four left are registry errors: a
  misspelt and a reordered author on Crossref, a dblp alias, JMLR's volume year.
- **On `heldout3`**, 62 of the 92 real problems are published preprints (REF015). The other 30
  are invented, misspelt or misordered authors (18), DOIs written as URLs (3), titles with a
  typo or a wrong word (3), a wrong DOI and a wrong arXiv ID, NeurIPS papers cited a year late
  (2), a wrong venue and an invented paper. Of the 14 false positives:
  - 3 cite an earlier arXiv version with its own title and authors (two REF001s, one REF011);
  - 3 bind a book to a review of it in a journal (REF010, REF011, REF013);
  - 4 are titles a registry mangled: a roman numeral, a footnote mark, a dropped solar symbol,
    "(with Discussion)" (REF012);
  - and one each of a nickname (Gary for Garrison), a volume year, a web publication no source
    indexes and a garbled subscript on Crossref.
- **A held-out batch's flags are reviewed, not used to change a rule** until its numbers are
  reported. Measuring the fixes they lead to needs a new week of papers.
- The sources are not committed (arXiv's default licence does not allow redistribution); the
  manifests `evals/real_papers.toml` and `evals/real_papers_heldout*.toml` list the IDs.

## Head-to-head: Badalova & Mayr (2026)

Badalova and Mayr checked 104 references from three documents by hand (71 verified, 33
problematic) and published whether each of five tools flagged them (Zenodo
10.5281/zenodo.21457492, CC BY 4.0). `evals/run_badalova_mayr.py` runs paper-preflight on the
same references, transcribed to BibTeX as written (`evals/badalova_mayr.bib`), and reports
precision with a Wilson 95% interval: with 33 problematic references, small differences are
noise. The results are in [`results/badalova-mayr.md`](results/badalova-mayr.md).

- **Reviewing paper-preflight's flags** on references the study labels verified found five
  that carry a real error (a wrong author name, a missing title word, a broken DOI);
  `evals/badalova_mayr_review.toml` lists every judgement. A second table counts them as
  problematic for every tool.
- **This data was looked at before the reported run.** The first run measured 62.8% precision
  [47.9%, 75.6%]. Two causes of false flags found then were fixed (#72: the year in a dblp key;
  #73/#74: team authors), and four names whose letters the published CSV lost to its encoding
  were restored from the documents.

## Plain-text references: Badalova & Mayr's strings

`check references.txt` reads a reference list as formatted text. `evals/plaintext_badalova.py`
measures it on Badalova & Mayr's 104 references as the documents print them (APA, biblatex's
default style, a natbib author-year style), against the hand transcription
`evals/badalova_mayr.bib`. The text gives the transcription's title for 103 of 104
references, its first author for 103, its year for all 104 and every one of its 48 DOIs and
arXiv IDs. Checked against the live sources both ways, 102 of the 104 references are flagged,
or not, alike; the two others are names whose letters the dataset's CSV lost. The results are
in [`results/plaintext-badalova-mayr.md`](results/plaintext-badalova-mayr.md).
