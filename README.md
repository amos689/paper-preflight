<!-- mcp-name: io.github.amos689/paper-preflight -->

<div align="center">

![paper-preflight](docs/assets/brand/paper-preflight-logo.svg)

**Check every reference of a LaTeX paper against real scholarly records before you submit.<br>
No LLM guessing, no false accusations.**

[![CI](https://github.com/amos689/paper-preflight/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/amos689/paper-preflight/actions/workflows/ci.yml)
[![PyPI version](https://img.shields.io/pypi/v/paper-preflight?label=PyPI&color=2f6fb0)](https://pypi.org/project/paper-preflight/)
[![MIT license](docs/assets/badges/license.en.svg)](LICENSE)
[![paper-preflight MCP server on Glama](https://glama.ai/mcp/servers/amos689/paper-preflight/badges/score.svg)](https://glama.ai/mcp/servers/amos689/paper-preflight)

[![Python 3.11 to 3.14](docs/assets/badges/python.en.svg)](pyproject.toml)
[![Input: LaTeX, BibTeX and PDF](docs/assets/badges/input.en.svg)](#quick-start)
[![Checked against six scholarly databases](docs/assets/badges/sources.en.svg)](#how-it-works)
[![No LLM in the verdicts](docs/assets/badges/verdicts.en.svg)](#design-principles)
[![Read-only MCP tools](docs/assets/badges/mcp.en.svg)](docs/mcp.md)

[![Tested on Windows, Linux and macOS](docs/assets/badges/platforms.en.svg)](https://github.com/amos689/paper-preflight/actions/workflows/ci.yml)
[![English and Simplified Chinese](docs/assets/badges/languages.en.svg)](README.zh-CN.md)

**English** · [简体中文](README.zh-CN.md) · [Quick start](#quick-start) ·
[Releases](https://github.com/amos689/paper-preflight/releases) ·
[Feedback](https://github.com/amos689/paper-preflight/issues/new/choose)

</div>

![paper-preflight checking the demo paper: errors for an undefined citation key, a DOI that belongs to another paper, a reference no source knows, a retracted paper and a duplicate entry key; warnings for a published preprint, two entries for the same work, a wrong year and a LaTeX-escaped DOI](https://raw.githubusercontent.com/amos689/paper-preflight/main/docs/demo/demo.gif)

Language models invent references, and copy-pasted BibTeX carries wrong years, wrong authors
and dead DOIs. paper-preflight reads your `.tex` and `.bib` files and asks Crossref, dblp,
arXiv, DataCite, PubMed and OpenAlex (and Semantic Scholar, if you have a key) about every cited
work:

- Does it exist?
- Does it match what you wrote?
- Has it been retracted?
- Has the preprint you cite been published since?

When it cannot tell, it says so instead of guessing.

> **Status: v0.4, an early release.** False positives are the bugs we most want to hear
> about: please [open an issue](https://github.com/amos689/paper-preflight/issues).

The repository's [demo paper](examples/demo-paper) cites eleven works, several of them wrong on
purpose. A real run, against the live sources:

```text
$ paper-preflight check examples/demo-paper
paper-preflight 0.4.0 · main.tex · 12 entries, 12 cited keys

error   CIT001 main.tex:31
    Citation key 'nonexistent2023' is not defined in any bibliography file (1 use(s)).
error   REF001 refs.bib:43
    The doi of 'devlin2019bert' (10.1109/cvpr.2016.90) resolves to a different work in Crossref: "Deep Residual Learning for Image Recognition" (He et al., 2016).
error   REF003 refs.bib:66
    'lindqvist2024quantum' was not found in Crossref, dblp and Semantic Scholar, and every source responded. Check that the work exists and that its title is correct.
error   REF004 refs.bib:73
    'wakefield1998ileal' has been retracted (reported by Crossref, OpenAlex). Cite it only if the text discusses the retraction.
error   CIT002 refs.bib:127
    Entry key 'kingma2015adam' is already defined at line 47; BibTeX ignores this one.
warning REF015 refs.bib:31
    'he2015residual' cites a preprint that has been published in CVPR (2016), DOI 10.1109/cvpr.2016.90. Cite the published version and keep the eprint field.
warning CIT004 refs.bib:37
    Entries 'devlin2019bert' and 'he2016deep' look like the same work (same DOI).
warning REF013 refs.bib:51
    'kingma2015adam' gives the year 2016, but dblp records 2014, 2015.
warning REF017 refs.bib:111
    The doi of 'tacl2019example' contains LaTeX escapes: '10.1162/tacl\_a\_00276'. Write it as: 10.1162/tacl_a_00276
info    REF005 refs.bib:73
    'wakefield1998ileal' has a published correction (reported by Crossref).
info    REF090 refs.bib:86
    'goodfellow2016deep' could not be verified: grey literature without an identifier (book, report, software, web page).
info    REF090 refs.bib:94
    'zhou2016ml' could not be verified: non-Latin titles are not supported yet; grey literature without an identifier (book, report, software, web page).
info    CIT003 refs.bib:115
    Entry 'lecun1998gradient' is never cited.

References: 6 verified · 1 metadata mismatch · 1 identifier conflict · 1 not found · 2 cannot determine
5 error(s) · 4 warning(s) · 4 info
```

Each finding is backed by a record (or by every source answering "no"). The correct NeurIPS
paper is verified through dblp even though Crossref only holds fake copies of it, and the two
books without identifiers are reported as "cannot determine" instead of "not found".

## What it catches

| Rule | Finding |
|---|---|
| REF001 | The DOI or arXiv ID points to a different paper |
| REF002 | The DOI or arXiv ID does not exist |
| REF003 | The work was not found in any source, and every source answered |
| REF004 · REF005 | The work was retracted, or has an expression of concern or a correction |
| REF010–REF014 | Authors, title, year or venue differ from the real record |
| REF015 | A cited preprint has been formally published |
| REF016 | The registry has a DOI the entry lacks (offered as a safe fix) |
| REF017 | An identifier is written so that links break (`10.1162/tacl\_a\_00276`, `…v1`) |
| CIT001–CIT008 | Undefined, duplicate, unused or near-duplicate citation keys; broken `.bib` syntax |
| REF090 | Cannot determine, always with the reason (source unavailable, grey literature, …) |

`paper-preflight explain REF003` describes any rule.

## How accurate is it?

Four measurements, all against the live sources: hallucinations found in published papers, the
bibliographies of real papers, a head-to-head with published tools, and a public benchmark.

### On hallucinations that got past peer review

GPTZero published 151 hallucinated references it found in NeurIPS 2025 papers and ICLR 2026
submissions, each confirmed by its staff. Pasted as plain text, as the papers printed them:

| References | Flagged | Cannot determine | Verified |
|---|---|---|---|
| 151 | **139 (92%)** | 12 | **0** |

- **None of them is verified.** The 12 left undecided are web pages and blog posts, a workshop
  no source indexes, real titles given with invented authors where the sources cannot tell
  which work is meant, a real title cut short, and two references too garbled to search. Each
  is listed with its reason in [`evals/results/gptzero.md`](evals/results/gptzero.md).
- GPTZero's own tool found these, so they are the hallucinations a search can find; recall on
  every kind of hallucination is lower (see HALLMARK below).

### On real papers

Weeks of arXiv papers (20 each, cs, stat, q-bio, quant-ph and astro-ph), chosen
mechanically, each list fixed before the changes it measures, run once, with every warning and
error reviewed by hand:

| Papers first submitted | Version | References | Flags | Real problems | False positives | Unclear | False positives per 100 references |
|---|---|---|---|---|---|---|---|
| 2026-08-19..25 | 0.5.0 | 962 | 53 | 41 | 10 | 2 | 1.0 |
| 2026-08-26..09-01 | 0.5.1 | 780 | 101 | 81 | 19 | 1 | 2.4 |
| 2026-09-02..08 | 0.5.2 | 975 | 48 | 31 | 13 | 4 | 1.3 |
| 2026-09-09..15 | 0.5.3 | 1,067 | 98 | 83 | 14 | 1 | 1.3 |
| 2026-09-16..22 | 0.6.0 candidate | 868 | 89 | 76 | 13 | 0 | 1.5 |
| 2026-09-23..29 | 0.6.0 | 786 | 48 | 42 | 6 | 0 | 0.8 |
| 2026-09-30..10-06 | 0.7.0 | 1,014 | 89 | 79 | 7 | 3 | 0.7 |

- **The latest week: about one false alarm every three papers** (51 references on average),
  against 79 real problems: 47 cited preprints since published, 8 wrong years, 7 identifiers
  written as links or with LaTeX escapes, wrong authors or given names in 5 entries, 4 wrong
  venues, 5 misquoted titles and two references that match no work at all. The false alarms
  are three articles a registry dates only by their online appearance, a book against its
  online edition, two symbols a registry writes its own way, and a paper's code offered as its
  published version.
- **The two weeks before (0.6.0): 1.5, then 0.8.** 8 of the first week's 13 false alarms were
  registries' own errors (a short author list, misspelt names, an HTML entity, a typo, a wrong
  year); 5 are fixed in 0.6.0.
- **One week was over our target of 1.5** (2.4); 11 of its 19 false alarms are fixed in 0.5.2.
- **In the first week, one false alarm every two papers** (48 references on average), against
  41 real problems:
  16 errors in the entries (wrong years, given names and titles, a missing first author, one
  paper's title with another's authors, identifiers written so that links break) and 25 cited
  preprints that have since been published.
- **The false alarms are mostly registry records with errors of their own** (author lists that
  stop short, a garbled symbol, an English given name) **and collaboration names in author
  lists** ("MAGPI Team"); two come from a title cited without its last words.
- **Seven earlier batches of 20 papers were used to find false positives,** each first measured
  as it came out (0.1.0: 4.5 per 100 references; 0.1.1: 2.3; 0.1.2 before its last fixes: 3.0;
  0.1.2: 1.7; 0.2.1: 1.9; 0.3.0: 1.9; 0.4.0: 1.2). Details in
  [`evals/README.md`](evals/README.md#real-papers).

### Next to other tools

[Badalova & Mayr (2026)](https://doi.org/10.5281/zenodo.21457492) checked 104 references by hand
and published what five tools flagged. On the same references, with their labels:

| Tool | Precision [95% CI] | Recall | False flags per 100 correct references |
|---|---|---|---|
| CheckIfExist | 47.7% [36.0%, 59.6%] | 93.9% | 47.9 |
| HalluCiteChecker | 47.4% [32.5%, 62.7%] | 54.5% | 28.2 |
| Hallucinator | 50.9% [38.3%, 63.4%] | 87.9% | 39.4 |
| HalRef | 31.2% [21.9%, 42.2%] | 72.7% | 74.6 |
| RefChecker | 47.1% [35.7%, 58.8%] | 97.0% | 50.7 |
| **paper-preflight** | **72.5% [57.2%, 83.9%]** | 87.9% | **15.5** |

The sample is small, so the intervals are wide. Some flags count as false here because the study
labels a reference correct when the work exists: five of paper-preflight's flags on such
references point at real errors (a wrong author, a broken DOI). Two causes of false flags found
in this data were fixed, and four names the study's CSV garbled were restored, before the run
above; the first run measured 62.8%. See
[`evals/results/badalova-mayr.md`](evals/results/badalova-mayr.md).

### On a benchmark: HALLMARK

[HALLMARK](https://github.com/rpatrik96/hallmark) is a public benchmark of real and hallucinated
BibTeX entries.

| Split | Mode | Precision | Recall | False-positive rate | Coverage |
|---|---|---|---|---|---|
| `test_public`: 831 entries, never used during development | Any issue | 98.4% | 90.3% | 1.9% | 97.7% |
| | Fabrication | 99.0% | 50.2% | 0.6% | 97.7% |
| `dev_public`: 1,119 entries, used during development | Any issue | 97.6% | 91.7% | 2.1% | 98.9% |
| | Fabrication | 98.2% | 53.7% | 1.0% | 98.9% |

HALLMARK v1.2.3, every entry of both public splits, run with 0.7.0 on 2026-10-08. *Fabrication* counts a
wrong identifier, a work not found and no author in common; *any issue* also counts wrong
authors, title, year or venue.

- **The held-out split confirms the development numbers:** a little higher precision and one
  and a half points less recall on entries no rule was ever tuned on.
- **Every flag on a `dev_public` entry labelled VALID was checked by hand.** The 11 that remain are not
  correct citations: DOIs that belong to other papers, author lists naming people who did not
  write the paper, a shifted year and a truncated title.
- **Without them, both modes reach 100% precision and 0% false positives.** The list, each item
  with a reason one lookup confirms, is in
  [`evals/hallmark_disputed.toml`](evals/hallmark_disputed.toml).
- **What is still missed:** invented venues on papers known only as preprints (an arXiv record
  cannot contradict a venue) and author lists that merely leave people out. See
  [`evals/results/`](evals/results/) for every hallucination type.

Precision comes first: a reference is called fabricated only on positive evidence, and an
unanswered or ambiguous lookup is reported as "cannot determine", never as "not found". The
evaluation harness and every run's summary are in [`evals/`](evals/README.md).

## Quick start

With [uv](https://docs.astral.sh/uv/) nothing needs installing (or `pip install paper-preflight`):

```bash
uvx paper-preflight check path/to/paper
```

`path/to/paper` is the project directory, its main `.tex` file, or a single `.bib` file.
A project that ships no `.bib`, as many arXiv sources do, is read from its compiled `.bbl`
(checked, but never edited).

Writing in Word, Markdown or Typst? The manuscript is checked the same way:

```bash
uvx paper-preflight check paper.docx     # Word: Zotero, Mendeley or EndNote citations, or the typed list
uvx paper-preflight check paper.qmd      # Markdown, Quarto, R Markdown: [@key] against its bibliography
uvx paper-preflight check paper.typ      # Typst: @key against #bibliography(...), .bib or Hayagriva .yml
```

In a Word manuscript, citations inserted by Zotero, Mendeley or EndNote carry the reference
manager's own record of each work (field codes), which is read first; Word's source manager
next; else the reference list as typed, after its "References" heading. A bibliography may also
be checked on its own as CSL-JSON (`.json`), RIS (`.ris`) or YAML (`.yml`, Hayagriva or CSL).

No manuscript at all? A reference list as plain text works too, in the common styles (APA,
IEEE, ACM, Nature, Vancouver, Springer, Elsevier, MDPI, GOST, Chicago, MLA), one reference per
line, per paragraph or numbered:

```bash
uvx paper-preflight check references.txt
pbpaste | uvx paper-preflight check -      # or from stdin
```

Any arXiv paper, by its ID: the source is downloaded to a temporary folder, checked, and
deleted.

```bash
uvx paper-preflight check arxiv:2607.06922
```

Only the PDF? Its reference list is read too, with the `pdf` extra:

```bash
uvx --from 'paper-preflight[pdf]' paper-preflight check paper.pdf
```

| Option | Effect |
|---|---|
| `--format json` / `--format sarif` | Machine-readable output (SARIF works with GitHub code scanning) |
| `--offline` | Never touch the network; use only answers already in the local cache |
| `--refresh` | Ask every source again instead of using cached answers (after a correction, say) |
| `--recheck` | Search again now for references found too new to be indexed on earlier runs (otherwise once a day) |
| `--fail-on warning` | Make warnings fail the run too (the default is errors) |
| `--details` | List every finding; by default a suggestion that applies to many entries (published preprints, available DOIs) is one line |
| `--lang zh` | Chinese messages (also chosen automatically from your locale) |

Exit codes:

| Code | Meaning |
|---|---|
| 0 | Nothing at or above `--fail-on` was found |
| 1 | Blocking findings |
| 2 | No blocking findings, but a source was unavailable and nothing could answer in its place, so the paper cannot be called clean yet |
| 3 | Usage error |

## Fetch verified BibTeX

Instead of writing an entry from memory, ask for it by DOI, arXiv ID or title. Every field
comes from the registry record, which a comment above the entry names:

```bash
paper-preflight bib fetch 1810.04805
```

```bibtex
% Verified with paper-preflight against dblp (conf/naacl/DevlinCLT19), 2026-10-03
@inproceedings{devlin2019bert,
  title         = {{BERT:} Pre-training of Deep Bidirectional Transformers for Language Understanding},
  author        = {Devlin, Jacob and Chang, Ming-Wei and Lee, Kenton and Toutanova, Kristina},
  booktitle     = {NAACL-HLT (1)},
  year          = {2019},
  doi           = {10.18653/v1/n19-1423},
  eprint        = {1810.04805},
  archivePrefix = {arXiv},
}
```

- **Preprints:** an arXiv preprint that has been published comes back as the published version,
  with its `eprint` kept (`--prefer preprint` for the preprint itself).
- **Titles:** `--title` (with `--author`/`--year` if needed) lists the candidates instead of
  choosing when several works match.
- **Retractions:** a retracted work comes with a warning.
- **Agents:** `--format json` is for scripts and agents.

## Fix the bibliography

`bib fix` turns findings into edits of your `.bib` files, taken from the verified records. It
prints a diff and changes nothing until you add `--apply`:

```bash
paper-preflight bib fix path/to/paper --level unsafe
```

```diff
--- a/refs.bib
+++ b/refs.bib
@@ -48,7 +47,7 @@
   title     = {Adam: A Method for Stochastic Optimization},
   author    = {Kingma, Diederik P. and Ba, Jimmy},
   booktitle = {International Conference on Learning Representations (ICLR)},
-  year      = {2016},
+  year      = {2015},
 }
```

- `--level safe` (the default) only fixes what cannot change which work is cited: identifiers
  written so that links break, and DOIs the registry has but the entry lacks.
- `--level unsafe` also rewrites authors, title, year and venue from the record, and removes
  identifiers that point to another work. Review the diff first.
- Only the affected fields change; comments, formatting, line endings and encoding are kept.
  A reference nobody could find is never "fixed": only you can say what was meant.

## Silence a finding you have checked

A comment directly above an entry silences rules for that entry, with an optional reason:

```bibtex
% preflight: ignore[REF003] reason="internal technical report, not indexed anywhere"
@techreport{lab2024internal,
  ...
}
```

The verdict stays in the JSON report; only the finding is dropped. A suppression that silenced
nothing is reported as CFG001 (info), so stale comments do not pile up. Reference rules are only
judged after a complete online run, since offline answers and outages may leave them unrun.

## Experimental: find the passage behind each citation

`support` looks in each cited work for a passage that says what the citing sentence claims. It
reads the work's text: the arXiv source, an open-access full text or PDF, or else the abstract.
A small local model (HHEM-2.1-open, 0.4 GB) then scores the passages ranked best for the claim.

```bash
pip install "paper-preflight[support]"
```

```bash
paper-preflight support path/to/paper --download-model --all
```

`--download-model` fetches the model's weights once. `--all` also lists the confirmed
citations with their quotes, and `arxiv:<id>` works as a target, as it does for `check`.

- **What it says:** "confirmed", with the passage quoted word for word, or "could not
  confirm". A citation it could not confirm comes with the reason: no text, only the abstract,
  or no passage close enough. A citation that only names what it cites ("Adam \cite{...}") is
  confirmed when the cited work's title carries the name.
- **It never calls a citation wrong.** On a gold set of 298 citations, 93% of its
  confirmations were right [95% CI 82%, 98%]. But it confirms only about one real citation in
  six, and a low score pointed at a mis-citation less than half the time. The gold set's
  labels were made by AI models, not experts; see
  [`evals/results/support.md`](evals/results/support.md).
- **Or let your agent judge.** The MCP tool `preflight_cited_passages` returns each claim with
  the cited work's best passages, for Claude, Codex or another agent to judge by the same
  rules. It needs no model and no `support` extra. On 100 gold-set citations, a Claude agent
  judging from it confirmed 39% of the real ones, against HHEM's 9%, and every confirmation
  was at least partially supported (the labels come from the same model family).
- **What leaves your machine:** the claims are scored locally. Only the cited works'
  identifiers go out, to fetch their text, which is then kept in the local cache.

## Use it from your coding agent

**Claude Code** — install the plugin. It bundles an MCP server and a skill that makes Claude
check the references before calling a paper finished, fix only what is proven wrong, and never
invent a reference.

```bash
claude plugin marketplace add amos689/paper-preflight
```

```bash
claude plugin install paper-preflight@paper-preflight
```

**Codex, Gemini CLI, Copilot, Cursor and other agents** — install the same skill. It runs the
CLI when no MCP server is configured:

```bash
npx skills add amos689/paper-preflight
```

`gh skill install amos689/paper-preflight paper-preflight` installs it too.

**MCP clients (Codex, Cursor, VS Code, …)** — run `paper-preflight mcp`. The tools are
read-only and confined to your workspace; see [docs/mcp.md](docs/mcp.md).

**pre-commit** — check citation keys and cached verdicts on every commit in seconds; see
[docs/pre-commit.md](docs/pre-commit.md).

**GitHub Actions** — `uses: amos689/paper-preflight@main` checks the paper on every push, with
the report in the job summary and optional code-scanning alerts; see
[docs/github-action.md](docs/github-action.md).

## Better results with free credentials

paper-preflight works without any account. These optional environment variables make it faster
and more complete; their values are never printed or logged.

| Variable | Effect |
|---|---|
| `PAPER_PREFLIGHT_EMAIL` | Crossref's polite pool: faster, more reliable lookups |
| `OPENALEX_API_KEY` | A larger OpenAlex budget for retraction checks |
| `S2_API_KEY` | Semantic Scholar as a rescue source for references nobody else found |

`paper-preflight doctor` shows which are set and whether each source answers right now.

## How it works

1. **Source-first.** It reads the LaTeX project as LaTeX sees it: comments, `\iffalse` blocks and
   `\includeonly` are respected, `.aux` files are used when they are fresh, and the first
   definition of a duplicated key wins, as in BibTeX.
2. **Identifier-first routing.** DOIs go to their registration agency (doi.org tells which:
   Crossref, DataCite, …). arXiv IDs go to arXiv, with DataCite as a fallback, and PMIDs and
   PMCIDs to PubMed (which also marks retracted articles). Entries without identifiers are searched by
   title in dblp and Crossref. dblp is read through its SPARQL endpoint, which still answers
   scripts now that dblp's search API is behind a bot challenge.
3. **Field-by-field matching with guards.** It compares titles (including earlier arXiv version
   titles), authors (tolerating transcriptions such as Reiß/Reis), year and venue. A search
   result is used only when enough of these agree and no other work fits as well; known fake
   DOI copies are skipped.
4. **One verdict per reference:** verified, metadata mismatch, identifier conflict, not found,
   or cannot determine with a reason. "Not found" needs every required source to answer "no".
5. **No LLM anywhere in the verdict.** Answers are cached locally (SQLite), so re-runs are fast
   and `--offline` works.

## Design principles

- **Positive confirmation or abstain.** Rate limits, outages and unindexed works lead to "cannot
  determine", never to "not found".
- **Neutral wording.** Findings state observations ("not found in Crossref, dblp and Semantic
  Scholar, and every source responded"), never accusations.
- **Local-first, no telemetry.** Only the metadata of the cited works (DOIs, titles, authors) is
  sent to the public scholarly APIs above. Your manuscript never leaves your machine.

## What it will never do

Help evade plagiarism or AI-text detection, scrape paywalled or bot-protected sites, recommend
or "complete" references from memory, or name and shame authors.

## Roadmap

- Done: releases on PyPI (v0.1); references from a `.bbl`, plain text, a PDF or an arXiv ID
  (v0.2); an experimental evidence finder for citations, `support` (v0.3); installs into more
  agents, an agent-judged `support`, and recall measured on hallucinations found in published
  papers (v0.4); references without titles found by journal, volume and page, short titles and
  real titles with invented authors judged where the sources allow it (v0.5); Chinese-language
  works cited in English no longer called "not found" (v0.5.2); fewer false alarms on double
  surnames, subtitles, workshop papers and books (v0.5.3); twice as fast, and references written
  whole in a note read as plain text (v0.6); Word, Markdown, Quarto, R Markdown and Typst
  manuscripts, and CSL-JSON, RIS and YAML bibliographies (v0.7)
- Next: books, software and standards checked against their own registries, and fewer misses on
  shortened author lists, invented venues and near-miss titles (v0.8); then a stable 1.0
- Being tried: references in Chinese script, measured before anything ships

Progress is tracked in [docs/PROGRESS.md](docs/PROGRESS.md) (in Chinese) and the
[changelog](CHANGELOG.md).

## Contributing

Bug reports with a reproducible `.bib` entry are the most valuable contribution, especially
false positives. See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[MIT](LICENSE). See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) for adapted code.
