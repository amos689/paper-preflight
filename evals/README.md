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

## Real-world hallucinations: GPTZero's lists

GPTZero published the hallucinated references it found, with its staff's confirmation: 100 in
NeurIPS 2025 papers and 51 in ICLR 2026 submissions. `evals/gptzero.py` checks each one as the
paper printed it, through the plain-text reader, and counts it as flagged (a warning or error),
cannot determine, or missed (verified). The tables are not redistributed; every reference not
flagged is reviewed in `evals/gptzero_review.toml`.

```bash
uv run python evals/gptzero.py fetch
uv run python evals/gptzero.py run
uv run python evals/gptzero.py report
```

0.3.0 flagged 129 of the 151 (85%). With the plain-text reader's fixes (#125) it flags 135 (89%),
and verifies none. Of the 16 it leaves undecided, 2 are references the plain-text reader still
cannot take apart (a garbled author list, a lower-case name part), 5 leave it with ambiguous
candidates (4 real titles given with invented authors, one garbled title), 4 give too little to
search (short or garbled titles), and 5 are web pages, blogs or an unindexed workshop. Results: [`results/gptzero.md`](results/gptzero.md).

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
uv run python evals/review_list.py heldout3 --out list.md     # the findings still to judge
uv run python evals/real_papers.py report --batch heldout3    # combine with the manual review
```

**How a change is checked.** A batch's list is committed before the changes it is to measure,
and the batch is run once with them; its false positives then become development data. Before
a change is merged, every development batch is replayed with it and compared with a replay of
the code before it: no warning or error may appear that is not a real problem.

```bash
uv run python evals/replay.py base                    # the code before the change
uv run python evals/replay.py new --against base      # verdicts moved, findings lost or gained
uv run python evals/replay.py new --against base --fill   # if the change asks something new
```

There are sixteen reported batches of 20 papers, each with the same mix (cs.CL 3, cs.LG 3, cs.CV 3, cs.AI 2,
stat.ML 2, q-bio.QM 2, quant-ph 2, astro-ph.GA 2, cs.SE 1). Each was collected after the fixes
the batches before it led to, and reported as it came out; its own false positives were then
studied, which makes it development data for the next round. The first four rows are the 0.1.2
candidate's (main 43a5544); the last twelve are each batch as it came out:

| Batch | Papers first submitted | Role | References | Flags | Real problems | False positives | Unclear | False positives per 100 references |
|---|---|---|---|---|---|---|---|---|
| `dev` | 2026-07-01..07 | studied for 0.1.1 (#58-#69) | 924 | 73 | 66 | 1 | 6 | 0.1 |
| `heldout` | 2026-07-08..14 | held out for 0.1.1; studied for 0.1.2 (#78-#91) | 921 | 94 | 85 | 6 | 3 | 0.7 |
| `heldout2` | 2026-07-15..21 | held out for #78-#91 (3.0 as it came out); studied (#94-#98) | 983 | 55 | 46 | 4 | 5 | 0.4 |
| `heldout3` | 2026-07-22..28 | held out for #94-#98 | 814 | 107 | 92 | 14 | 1 | 1.7 |
| `heldout4` | 2026-07-29..08-04 | held out for 0.2.1; studied for 0.3.0 (#112-#114) | 1,005 | 88 | 66 | 19 | 3 | 1.9 |
| `heldout5` | 2026-08-05..11 | held out for 0.3.0; studied for 0.4.0 (#126-#128) | 1,043 | 136 | 109 | 20 | 7 | 1.9 |
| `heldout6` | 2026-08-12..18 | held out for 0.4.0; studied for 0.5.0 (#139-#141) | 753 | 86 | 77 | 9 | 0 | 1.2 |
| `heldout7` | 2026-08-19..25 | held out for 0.5.0 (list committed before any change, #138); studied for 0.5.1 | 962 | 53 | 41 | 10 | 2 | 1.0 |
| `heldout8` | 2026-08-26..09-01 | held out for #148 (list committed before it, #147); studied for 0.5.2 | 780 | 101 | 81 | 19 | 1 | 2.4 |
| `heldout9` | 2026-09-02..08 | held out for 0.5.2 (#152-#154; list committed before them, #149); studied for #157 | 975 | 48 | 31 | 13 | 4 | 1.3 |
| `heldout10` | 2026-09-09..15 | held out for #157 (list committed before it, #155); studied for #160 | 1,067 | 98 | 83 | 14 | 1 | 1.3 |
| `heldout11` | 2026-09-16..22 | held out for 0.6.0 (#160-#161; list committed before them, #158); studied for #164 | 868 | 89 | 76 | 13 | 0 | 1.5 |
| `heldout12` | 2026-09-23..29 | held out for 0.6.0 with #164 (list committed before it, #163) | 786 | 48 | 42 | 6 | 0 | 0.8 |
| `heldout13` | 2026-09-30..10-06 | held out for 0.7.0 (#167; list committed before it, #165) | 1,014 | 89 | 79 | 7 | 3 | 0.7 |
| `heldout14` | 2026-06-24..30 (an earlier week) | held out for 0.8.0 (#170-#187; list committed after them, #188) | 1,127 | 143 | 132 | 10 | 1 | 0.9 |
| `heldout15` | 2026-06-17..23 (an earlier week) | held out for #191 (list committed before it, #188) | 1,093 | 136 | 96 | 39 | 1 | **3.6** |

- **On `heldout7`**, run once with every 0.5.0 change (#139-#144): 41 real problems (25
  published preprints, 5 wrong years, 5 identifiers written as URLs, 4 wrong given names or a
  missing first author, a chimera of two papers, a misworded title) and 10 false positives.
  Registries' author lists that stop short (DataCite, KISTI) give three; collaboration names
  ("MAGPI Team") two; a truncated title bound to another paper of the shorter title two; a
  Zenodo concept DOI, an English given name and a registry's garbled symbol one each.

- **On `heldout8`**, run once after #148 fixed eight of heldout7's ten false positives: 81 real
  problems (two papers alone have 33, with invented DOIs, authors and titles) and 19 false
  positives, 2.4 per 100 references, over the 1.5 gate. None comes from #148. They are other
  forms of one person's name (Yuexiang/Simon Zhai, Robert M./Mike Kirby, Balasubramanya/Balu
  Nadiga) 4, four pages of the Error Correction Zoo cited with its handbook's arXiv ID 4, real
  works not found (a Black Hat talk, a title cut short, a subtitle left out, 'Nystroem') 4, a
  dataset's name after a title ('(SimpleQA)') 2, venue names (COLING/ACL, ASPLOS in SIGARCH
  Computer Architecture News) 2, a registry's short author list 1, an `\ifmmode` in a name 1
  and an MNRAS volume year 1.

- **On `heldout9`**, run once with 0.5.2's changes (#152-#154): 31 real problems (17 published
  preprints, identifiers of other papers, wrong given names and years, identifiers written as
  URLs or placeholders) and 13 false positives, 1.3 per 100 references. They are double
  surnames ('Ramos Garea', 'Dehghani Tafti') 2, a laboratory credited as an author 1, works no
  source indexes cited as articles (a law review article, an OpenReview position paper, a
  report, a blog URL in the journal field) 4, a challenge's LNCS volume named otherwise than
  dblp names it 1, years (a workshop version, a book's online date, an MNRAS volume) 3,
  'et al.' inside a name 1 and a subtitle after a question mark 1.

- **On `heldout10`**, run once after #157 fixed eleven of heldout9's thirteen false positives:
  83 real problems (51 published preprints, 15 identifiers written as URLs or not DOIs, 8
  wrong authors or given names, 7 of them in one paper, 3 years, 3 titles no source has, two
  of them at journal coordinates that belong to other papers, 2 misquoted titles and two DOIs
  run together) and 14 false positives, 1.3 per 100 references. They are ACM Digital Library
  URLs with ACM's unregistered 10.5555 numbers 2, KDD written with an ampersand 2, preprint
  servers named as the published version (IACR ePrint, ECCC) 2, registry title artefacts
  (mojibake, italic markup as text) 2, short author lists in a record (dblp's MUC-7 appendix,
  DataCite's latest arXiv version while arXiv was down) 2, a short given name (Russ
  Salakhutdinov) 1, a book's online date (Nielsen & Chuang) 1, an ePrint copy's year against
  its conference paper 1 and literal braces in a title 1.

- **On `heldout11`**, run once with 0.6.0's changes (#160-#161): 76 real problems (51
  published preprints, 8 identifiers written as URLs, wrong or invented authors in 6 entries
  (one an ADS name with 'Jr.' where BibTeX reads the given name), 7 years, a DOI of another
  paper, a PMID that does not exist, two titles not the work's) and 13 false positives, 1.50
  per 100 references: at the 1.5 gate, so the release is measured on the next week too.
  They are registries' records with errors of their own (a short author list, misspelt or
  'Prof.' names, an HTML entity, AAS markup '[CSC]', a typo in a title, BLEU's year 2001,
  Cambridge Core's 2012 for a 2010 book) 8, real works no source indexes (a RePEc-listed
  journal, an EJDE conference volume) 2, a chapter compared with its reprint 1, a renamed
  journal 1 and an arXiv author list compared instead of the journal's 1.

- **On `heldout12`**, run once with 0.6.0 including #164: 42 real problems (24 published
  preprints, 6 identifiers written as URLs or with LaTeX escapes, wrong authors or given
  names in 7 entries, one a chimera of two papers, a DOI that does not exist, two misquoted
  titles) and 6 false positives, 0.8 per 100 references. They are a typo in arXiv's own
  title, a 2013 e-book DOI on a 1988 book, an online-first record against the issue's year,
  a journal's series label the registry leaves out of a title, and two software releases
  cited with their owner and version.
- **On `heldout15`**, a week before `dev`, run once with main 35dcdb0 (0.8.0 and #191): 96
  real problems (45 published preprints, 29 identifiers written as links, wrong names in 10
  entries, 5 misquoted titles, 4 DOIs or arXiv IDs of other works, 3 DOIs that do not exist, 2
  wrong years) and **39 false positives, 3.6 per 100 references, over the gate of 1.5**. None
  comes from #191. They are a bug of ours, 6 (DOIs ending in a parenthesis, as ASCE's
  '...13:1(6)', were cut, then reported as not existing and as written wrongly); physics and
  astronomy, 16 (collaboration papers cited by their first people, isotopes written '$^{13}$CO'
  or 'CO-13', ADS entries citing the arXiv e-print compared with the journal version, names a
  registry garbled, reordered or updated, a paper indexed under its Chinese title, a
  conference's year); years, 4 (issue years Crossref gives as the online date); workshop
  versions, venues' other names, software and datasets cited as their makers ask, reports,
  an edition in a title, romanised names and a translated title, 13. 0.54 s per reference, 5%
  cannot determine. Its false positives are studied for the next changes, which `heldout16`
  measures.
- **On `heldout14`**, a week before `dev`, run once with every change since 0.7.0 (main
  5e048db, #170-#187): 132 real problems (93 published preprints, 17 identifiers written as
  links, wrong authors or given names in 10 entries, often all of a list's given names invented,
  6 wrong years, 2 misquoted titles, a wrong venue, a DOI that does not exist, an arXiv ID of
  another paper, an author field reading 'iang et al.') and 10 false positives, 0.9 per 100
  references; 0.43 s per reference live, 3% cannot determine. They are registries' own
  writing (a title that lost its '3/4', a 'Chapter 1' prefix, 'Ueber' and 'Foerster' for
  'Über' and 'Förster', a dblp list without one author, Bas for Sebastiaan Kooijman), author
  fields written by hand ('and 324 others', 'Black et al.', OpenAI for the people of its GPT-5
  system card) and an ITU-R report no source indexes. One reference, in a journal no index
  holds, could be confirmed neither way.
- **On `heldout13`**, run once with 0.7.0's code (#167): 79 real problems (47 published
  preprints, 8 wrong years, 7 identifiers written as URLs or with LaTeX escapes, wrong authors
  or given names in 5 entries, 4 wrong venues, 5 titles misquoted or taken from the preprint,
  two references that match no work, a doi field holding two DOIs) and 7 false positives, 0.7
  per 100 references; 0.43 s per reference live. They are three articles whose volume year
  Crossref records only by the online date, a 2007 book against its 2009 online edition, two
  titles that differ only in how a registry writes a symbol (TeX markup, ADS's 'M sub sun'),
  and a paper's code on Zenodo offered as the paper's published version.

A fourteenth batch, `heldout13` (2026-09-30..10-06), was collected on 2026-10-08 and its list
committed before any change made for heldout12's false positives.

Three more, `heldout14` (2026-06-24..30), `heldout15` (06-17..23) and `heldout16` (06-10..16),
were collected on 2026-10-09 with every change since 0.7.0 merged (#170-#187), and their lists
committed before any of them was run. They are weeks *before* `dev`, never sampled until then:
a release need not wait for next week's papers to be announced. Each is the same mechanical
sample as the weekly batches and is run once. They are checked months after the papers were
written, when the works they cite are better indexed, so "too new" abstentions and registries'
first-days errors are rarer than in a fresh week: their rates may read a little better. The
next fresh week (2026-10-07..13) is run too, as a control.

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
- **On `heldout4`**, the fixes for 0.3.0 (#112-#114) leave 6 of the 19 false positives (0.6 per
  100 references, replayed offline) and every real problem.
- **On `heldout5`**, 53 of the 109 real problems are published preprints; the other 56 are
  invented or misspelt authors (17), wrong titles (11), identifiers written wrongly (URLs,
  LaTeX escapes, a missing prefix: 11), DOIs that do not exist (6), identifiers of another paper
  (4), wrong venues (3), invented works (3) and a wrong year. Of the 20 false positives:
  - 4 are UCI datasets whose DataCite record stores several creators as one name (REF011);
  - 2 are Crossref titles with an HTML entity left in them, `&lt;` and `&gt;` (REF012);
  - 2 are Zenodo software DOIs: a concept DOI titled after the latest release (REF001) and a
    GitHub release title (REF012);
  - 2 are ROUGE, whose ACL 2004 workshop Semantic Scholar files under ACL (REF014);
  - 4 are real works no queried source has: two sets of lecture notes and reports written as
    `@article`, a paper whose Semantic Scholar link was not asked, and a title without its
    subtitle (REF003);
  - 5 are names written another way: a nickname (Freddy), an English name before Chinese
    initials, a double surname cut short, a name in the other order, a character lost in
    Crossref (REF011);
  - and one is a journal code ('humr') Crossref gives as the journal title (REF014).
- **On `heldout5`**, after the fixes for 0.4.0 (#126-#128), 3 of the 20 false positives are
  left (replayed offline), and every real problem is still flagged.
- **On `heldout6`**, 41 of the 77 real problems are published preprints. The other 36 are:
  identifiers written so that links break (21, eleven of them arXiv IDs with Zotero's
  " [cs]"); invented or wrong authors (9, two with no real author at all); wrong titles (3); a
  wrong year; and two invented works. Of the 9 false positives:
  - registry errors: Crossref's 'Probelm', dblp's 'Biopolymer', an affiliation mark inside a
    Crossref name ('Asmussen c'), and dblp's joint workshop volume for STACOM;
  - real works no source describes as cited: a Substack post and a technical report written as
    papers, a database cited by its access year, an IEEE early-access year;
  - a name written family name first without a comma ('Rouse D. M.').

  15% of the references are "cannot determine". Most are in one paper whose `.bib` gives 60
  astronomy references without titles (journal, volume and page only).
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
`evals/badalova_mayr.bib`. The text gives the transcription's title for all 104
references, its first author for 103, its year for all 104 and every one of its 48 DOIs and
arXiv IDs. Checked against the live sources both ways, 102 of the 104 references are flagged,
or not, alike; the two others are names whose letters the dataset's CSV lost. The results are
in [`results/plaintext-badalova-mayr.md`](results/plaintext-badalova-mayr.md).

## PDF reference lists: the real papers' PDFs

`check paper.pdf` (the `pdf` extra) reads the reference list out of a PDF. `evals/pdf_agreement.py`
reads the PDF arXiv serves for each paper of a real-paper batch and compares it with the check of
the paper's own `.bib`. A `.bib` reference is found in the PDF when the PDF's list has its DOI or
arXiv ID, a title 90% alike, or, in a style that prints no titles, the only reference with its
first author and year. On the 20 papers of `dev` (924 references), the PDF gives 820 of them
(89%), with the same first author for 98% and the same year for 95%, and the same verdict for
756 (92%). The results, paper by paper, are in [`results/pdf-dev.md`](results/pdf-dev.md).

## Word manuscripts: the real papers' references in .docx

`check paper.docx` reads a Word manuscript: the reference manager's records in its field codes
(Zotero, Mendeley, EndNote), Word's source manager, or else the reference list as typed.
`evals/docx_agreement.py` writes each paper's cited `.bib` entries into Word documents, as a
reference manager leaves them (Zotero's CSL-JSON in field codes) and as typed lists in three
styles, APA, IEEE and NLM (rendered by citeproc-py from the CSL project's styles, which
`evals/.data/csl-styles` holds with the commit they come from), and compares each document's
check with the check of the `.bib`. On the 20 papers of `dev` (924 references), the field codes
give the same verdict for 99.6%, the typed lists for 94.0% (APA), 96.9% (IEEE) and 96.0% (NLM).
The results are in [`results/docx-agreement.md`](results/docx-agreement.md).

The styles (CC BY-SA 3.0) are not in the repository; to fetch them:

```bash
c=0151fd1ed467ec54f4f2554d68fce9ccc6ff0118
mkdir -p evals/.data/csl-styles && echo $c > evals/.data/csl-styles/COMMIT
for s in apa ieee nlm-citation-sequence-brackets; do
  curl -sL -o evals/.data/csl-styles/$s.csl \
    https://raw.githubusercontent.com/citation-style-language/styles/$c/$s.csl
done
uv run python evals/docx_agreement.py --batch dev --fill
```

## Citation support: the gold set

`support` (experimental) looks in each cited work for a passage that says what the citing
sentence claims. `evals/support_gold.toml` holds 298 pairs of a sentence and a cited work. The
sentences come from 55 arXiv papers of July 2026 under CC BY, CC BY-SA or CC0. 48 of the pairs
are mis-citations made on purpose, with the cited work swapped for another one the paper cites.
AI models labelled the pairs, as [`support_guidelines.md`](support_guidelines.md) describes:
two annotators, a third for disagreements, then an adjudication.

`evals/support_eval.py` scores the verifiers and reports how often "supported" is right and how
many citations it confirms. With HHEM, 97% of its confirmations are right, and it confirms 12%
of the real citations. Every number, and why `support` never says "not supported", is in
[`results/support.md`](results/support.md).
