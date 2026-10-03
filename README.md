# paper-preflight

**English** · [简体中文](README.zh-CN.md)

[![CI](https://github.com/amos689/paper-preflight/actions/workflows/ci.yml/badge.svg)](https://github.com/amos689/paper-preflight/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
![Python 3.11–3.14](https://img.shields.io/badge/python-3.11%E2%80%933.14-blue.svg)

**Check every reference of a LaTeX paper against real scholarly records before you submit.
No LLM guessing, no false accusations.**

Language models invent references, and copy-pasted BibTeX carries wrong years, wrong authors
and dead DOIs. paper-preflight reads your `.tex` and `.bib` files and asks Crossref, dblp,
arXiv, DataCite and OpenAlex (and Semantic Scholar, if you have a key) about every cited work:

- Does it exist?
- Does it match what you wrote?
- Has it been retracted?
- Has the preprint you cite been published since?

When it cannot tell, it says so instead of guessing.

> **Status: early release.** The checks below work today; install from GitHub until the first
> PyPI release (v0.1, planned for November 2026).

The repository's [demo paper](examples/demo-paper) cites eleven works, several of them wrong on
purpose. A real run, against the live sources:

```text
$ paper-preflight check examples/demo-paper
paper-preflight 0.0.1.dev0 · main.tex · 12 entries, 12 cited keys

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
    'kingma2015adam' gives the year 2016, but dblp records 2015.
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

paper-preflight is measured on [HALLMARK](https://github.com/rpatrik96/hallmark), a public
benchmark of real and hallucinated BibTeX entries, against the live sources.

| Mode | Precision | Recall | False-positive rate | Coverage |
|---|---|---|---|---|
| Fabrication: wrong identifier, not found, no author in common | 98.0% | 49.9% | 1.0% | 96.6% |
| Any issue: also wrong authors, title, year or venue | 97.2% | 77.8% | 2.1% | 96.6% |

HALLMARK v1.2.3 `dev_public`, all 1,119 entries, run on 2026-10-03.

- **Every flag on an entry labelled VALID was checked by hand.** The 11 that remain are not
  correct citations: DOIs that belong to other papers, author lists naming people who did not
  write the paper, a shifted year and a truncated title.
- **Without them, both modes reach 100% precision and 0% false positives.** The list, each item
  with a reason one lookup confirms, is in
  [`evals/hallmark_disputed.toml`](evals/hallmark_disputed.toml).
- **Recall is the open front.** Invented venue names and near-miss titles are mostly missed
  today. See [`evals/results/hallmark-dev_public.md`](evals/results/hallmark-dev_public.md) for
  every hallucination type.

Precision comes first: a reference is called fabricated only on positive evidence, and an
unanswered or ambiguous lookup is reported as "cannot determine", never as "not found". The
evaluation harness and every run's summary are in [`evals/`](evals/README.md).

## Quick start

You need [uv](https://docs.astral.sh/uv/).

```bash
uvx --from git+https://github.com/amos689/paper-preflight paper-preflight check path/to/paper
```

`path/to/paper` is the project directory, its main `.tex` file, or a single `.bib` file.

| Option | Effect |
|---|---|
| `--format json` / `--format sarif` | Machine-readable output (SARIF works with GitHub code scanning) |
| `--offline` | Never touch the network; use only answers already in the local cache |
| `--fail-on warning` | Make warnings fail the run too (the default is errors) |
| `--lang zh` | Chinese messages (also chosen automatically from your locale) |

Exit codes:

| Code | Meaning |
|---|---|
| 0 | Nothing at or above `--fail-on` was found |
| 1 | Blocking findings |
| 2 | No blocking findings, but a source was unavailable, so the paper cannot be called clean yet |
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

**Codex, Cursor, VS Code and other MCP clients** — run `paper-preflight mcp`. The tools are
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
   Crossref, DataCite, …). arXiv IDs go to arXiv, with DataCite as a fallback. Entries without
   identifiers are searched by title in dblp and Crossref.
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

- The first PyPI release (v0.1)
- Chinese-language references (v0.2)

Progress is tracked in [docs/PROGRESS.md](docs/PROGRESS.md) (in Chinese) and the
[changelog](CHANGELOG.md).

## Contributing

Bug reports with a reproducible `.bib` entry are the most valuable contribution, especially
false positives. See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[MIT](LICENSE). See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) for adapted code.
