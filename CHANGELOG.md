# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Fixed

Eleven of the nineteen false positives on the ninth batch of real papers (heldout8):

- A title cited without its subtitle counts when the part before the colon has five words, not
  only thirty characters ("An Image is Worth 16x16 Words"); a title cut short that search finds
  only as a longer title, by the entry's own authors, binds to it (ChestX-ray8). Such records
  are kept apart from the search candidates, so they make no entry ambiguous.
- A dataset's or system's name after a title ("... Models (SimpleQA)") is not a title
  difference when the title matches word for word without it (REF012).
- A middle name's nickname ("Robert M." publishing as "Mike") is the same person (REF011);
  APS's `\ifmmode … \else … \fi` inside a name keeps its text branch.
- A joint meeting names each of its venues ("COLING/ACL 2006" is ACL's too), and ACM's SIG
  newsletters (SIGARCH Computer Architecture News for ASPLOS) are no other venue (REF014).
- Black Hat and DEF CON talks are unindexed venues, not "not found" (REF003).
- An MNRAS article online in December with no print date or volume yet counts next year's
  volume year (REF013).
- A footnote Crossref ran into a title ("...Network**Based on ...") is removed, so Hecht-
  Nielsen's 1992 chapter is verified against its own record.

Not fixed: two other forms of a person's name ('Simon' for Yuexiang, 'Balu'), four pages of a
reference site cited with its handbook's arXiv ID, one registry's short author list and one
transliterated title ('Nystroem').

## [0.5.1] - 2026-10-07

A compliance fix (CNKI DOIs) and eight fewer false positives. On a new held-out week of real
papers, run once with these changes: 2.4 false positives per 100 references, over the 1.5
target; none comes from this release's changes, and they are the next fixes.

### Fixed

- A CNKI DOI is no longer resolved. doi.org answers content negotiation for CNKI's DOIs with a
  redirect to chndoi.org, whose robots.txt disallows every agent, and the check followed it. A
  CNKI DOI is now known to exist from doi.org's agency lookup (doiRA) and is otherwise left
  undetermined, as the reference says.

Eight of the ten false positives on the eighth batch of real papers (heldout7):

- A person missing from the matched record is reported only when every record of the work
  reached through the entry's identifiers leaves them out: registries' author lists stop short
  (ESO's DataCite records, KISTI's), and the arXiv record has the full list (REF011).
- A collaboration in the author list ("MAGPI Team") pairs with the record's longer name for it
  ("And The MAGPI Team"); "RDKit Contributors" and the like are groups, not missing people.
- Software cited by its name matches a Zenodo release titled by its repository
  ("rdkit/rdkit: 2026_09_1 (Q3 2026) Release"), which a concept DOI resolves to (REF001).
- A title cut short, by the entry's own authors, binds to the paper it shortens instead of
  another paper with the shorter title: "Connectivity of Soft Random Geometric Graphs [over
  Annuli]" is reported as a title missing words (REF012), not as wrong authors and venue.

The other two are a registry's English given name for an author and its garbled symbol
("Rnu" for R_V). On the development batches the changes also find two titles cut short; no
real problem is lost, and HALLMARK and GPTZero are unchanged.

## [0.5.0] - 2026-10-07

Catches more, abstains less, misfires less. On a new held-out week of real papers, collected
before any change in this release: 1.0 false positives per 100 references (0.4.0: 1.2). GPTZero's
151 hallucinated references: 139 flagged (0.4.0: 135), none verified. HALLMARK `test_public`:
fabrication recall 50.2% (49.0%), false-positive rate 1.9% (2.2%).

### Added

- Journal articles cited without a title ("MNRAS 249, 523", as astronomy and physics cite) are
  looked up on Crossref by journal, volume and first page. The record found is used only when
  its volume and first page are those cited and its first author is the entry's; the JSON
  report flags the reference `coordinates`. Nothing found leaves the reference undetermined,
  never "not found", and a failed lookup does not make the run incomplete. On the seventh batch
  of real papers, references that could not be determined fall from 15.4% to 6.4%.

### Fixed

Seven of the nine false positives on the seventh batch of real papers:

- Names written family name first with initials and no comma ("Rouse D. M.") pair with the
  registry's full names (REF010).
- An affiliation mark or look-alike symbol in a registry's name ("Asmussen c", "S⊘ren") is no
  longer an author difference (REF011).
- A database or data collection cited by the year it was used is no longer a year error
  (REF013); nor is an IEEE article cited by its early-access year, which its DOI names
  ("tse.2018.…", Crossref having only the 2020 issue).
- A workshop in a joint volume dblp names by acronyms ("CMRxRecon/MBAS/STACOM@MICCAI") is no
  longer another venue (REF014).
- A Substack post, and a report or thesis written under another entry type whose venue names
  the report and its institution, are web content and grey literature, not "not found"
  (REF003). A bare "Technical Report" naming no one still is.

The other two are typos in the registries' titles ("Probelm", "Biopolymer"). Tolerating them
would hide more typos in entries than registries make, so they stay.

In plain-text lists (and PDFs), a name with a lower-case part among proper names ("Yun chen
Chen", as PDFs and generated lists write them) no longer stops the authors and title from
being read. One more of GPTZero's 151 hallucinated references is flagged (136), and two more
references of the development PDFs are found.

`bib fix` no longer writes REF017's advice into a file: an invalid DOI or arXiv ID was replaced
by "(remove or correct the field)" or "(correct the arXiv ID)", even at the safe level. Such
fields are now left for a person to correct. An arXiv ID exported with its subject class
("2311.07911 [cs]", as Zotero writes it) gets the bare ID as its fix.

### Changed

- A work found under two records whose titles differ only in hyphens or spaces (a preprint's
  "Trade-off", its proceedings' "Tradeoff") is one work, not two: invented authors on a real
  title are reported (REF010) instead of abstained on as ambiguous. GPTZero's hallucinated
  references: 137 of 151 flagged.
- A title of three or four words can be "not found" (REF003) at a conference or journal dblp
  indexes in full, in a past year ("Spectral contrastive graph clustering" at ICLR 2022), when
  every source answered. Not when a found title is the entry's and more: that is a real paper
  cited by its first words. Elsewhere short titles still name topics, not papers. GPTZero: 139
  of 151; HALLMARK `test_public` fabrication recall 49.3% -> 50.2%, at the same false-positive
  rate; no change on the seven development batches of real papers.

## [0.4.1] - 2026-10-07

Smoother first runs. An overloaded arXiv API no longer leaves every run "incomplete" when DataCite
has already answered, and a sound paper's report no longer lists the same suggestion a dozen
times. Findings are unchanged: a replay of the sixth held-out batch gives identical results.

### Changed

- When the arXiv API does not answer but DataCite does (it registers every arXiv paper), the
  run is no longer incomplete (exit code 2) for those references: a new info finding, RUN002,
  says they were checked through DataCite and that withdrawals and earlier version titles were
  not. Seen live: arXiv's API is often overloaded, and every run then ended "incomplete".
- The text report summarises a suggestion that applies to three or more entries (REF015 published
  preprints, REF016 available DOIs) in one line; `--details` lists each. JSON, SARIF and the counts
  are unchanged.
- MCP: every tool parameter has a description in the tool schema (none had one), and each
  tool says when to use it instead of the others.
- README: a logo, badges and a centred header; the roadmap no longer lists an online demo as
  done (the Hugging Face Space was not set up).

## [0.4.0] - 2026-10-05

Measured in the wild, tried in the browser. On the 151 hallucinated references GPTZero found in
NeurIPS 2025 papers and ICLR 2026 submissions, 135 are flagged and none is verified. On a
seventh batch of real papers, collected after every fix in this release (753 references), 1.2
false positives per 100 references (0.3.0: 1.9 on the sixth batch). New: an online demo, the
skill in more agents, and citation support judged by your own agent.

### Added

- An MCP tool, `preflight_cited_passages`: for each sentence citing a key, the claim and the
  cited work's passages ranked for it, for the agent itself to judge whether the work supports
  the claim. It needs no model and no `support` extra. The skill tells the agent how to judge:
  confirm only with a quoted passage, never call a citation wrong.
- `support` confirms a citation set right after a name ("Adam \cite{kingma}", "ImageNet
  \cite{deng}") when the cited work's title carries that name. On the gold set this confirms 41
  of 250 real citations instead of 31; 93% of the confirmations are right, and no mis-citation
  is confirmed.
- An online demo for Hugging Face Spaces (`space/`). It takes an arXiv ID, an uploaded file
  (`.bib`, `.bbl`, `.tex`, `.txt`, `.pdf`, or a `.zip` of a LaTeX project such as Overleaf's
  source download) or pasted references, and shows the report, the suggested `.bib` fixes and
  JSON and SARIF downloads. It checks up to 300 references, deletes the files after the run and
  holds no API keys. `.github/workflows/space.yml` publishes it on every release once the
  `HF_SPACE` variable and `HF_TOKEN` secret are set.
- The skill installs into Codex, Gemini CLI, GitHub Copilot, Cursor and other agents with
  `npx skills add amos689/paper-preflight` or `gh skill install amos689/paper-preflight
  paper-preflight`; without an MCP server, it runs the CLI. Its frontmatter now names its
  licence.

### Fixed

- Registry records in odd forms no longer make a correct entry look wrong. These were false
  positives in the sixth batch of real papers:
  - DataCite creators deposited as one name ("Barry Becker, Ronny Kohavi", for UCI datasets);
    a dataset's or software's record may also list only some of its authors, and Zenodo may
    put a whole name in the family name or list contributors in its own order;
  - Zenodo titles of GitHub releases, also on concept DOIs ("explosion/spaCy: v3.7.2: Fixes
    ..."): the repository's name is the title, and a release's year is not compared;
  - software cited by its name and what it does ("spaCy: Industrial-strength Natural Language
    Processing in Python");
  - Crossref titles with entities escaped twice ("&amp;lt;");
  - a publisher's journal code given as the journal ("humr" for HUMOR);
  - a letter a registry lost in a name ("Sch" + U+FFFD + "nle").

  Semantic Scholar's venue no longer raises REF014: it files workshops under their conference
  (ROUGE's ACL 2004 workshop under ACL).
- A work cited without its subtitle is found: a search result that is the entry's title plus
  a subtitle is compared in full, however different the two titles look as strings ("Resource
  Allocation for Multi-source Multi-relay Wireless Networks", cited without ": A Multi-Armed
  Bandit Approach", was reported as not found).
- More names written another way are one person:
  - Freddy for Frederic;
  - an English name before the initials of two or more given names ("Ricky T. Q." for dblp's
    Tian Qi Chen);
  - a double surname cited by its first part ("Raymond" for Raymond-Saez);
  - a name in the other order, with initials ("Karthikeyan, P." for Crossref's "K. Palanisamy").
- The plain-text reader (pasted lists, `.txt` and PDFs) reads more references in full. It now
  handles:
  - authors whose first name starts with an accented capital ("Étienne Pardoux");
  - a title that ends in a question mark and runs into its journal;
  - venues that start with an edition or a year ("In 37th International Conference ...",
    "In 2009 IEEE/WIC/ACM ...");
  - a year after a title with no venue ("Title, 2025.");
  - an arXiv link broken by a space after the slash, LaTeX dollar signs, and a reference
    numbered twice.

  On GPTZero's 151 confirmed hallucinated references, 135 are flagged instead of 129.
- `support` no longer stops when a cited work's text is a PDF and pypdf is not installed: the
  work is read from its abstract, with a note to install the `pdf` extra.

## [0.3.0] - 2026-10-05

An experimental evidence finder for citations, and fixes for the fifth real-paper batch's
false positives. On that batch, 6 of its 19 false positives remain (0.6 per 100 references),
and all 66 real problems are still flagged. The fixes were made for this batch, so these are
development numbers; a sixth batch, collected after this release, will measure them held out.

### Added

- `paper-preflight support` (experimental): for each citation, looks for a passage of the
  cited work that says what the citing sentence claims. It reads the work's arXiv source, an
  open-access full text or PDF, or its abstract, and a local model (HHEM-2.1-open by default;
  `--model minicheck` or `factcg`) scores the passages ranked best for the claim. A citation is
  either confirmed, with the passage quoted, or not confirmed, with the reason; it is never
  called wrong. Needs the new `support` extra (PyTorch, transformers); the model's weights are
  downloaded only with `--download-model`. On an AI-labelled gold set of 298 citations
  (`evals/support_gold.toml`), 97% of its confirmations are right and it confirms 12% of real
  citations; see `evals/results/support.md`.

### Fixed

- A cited book is no longer bound to a later chapter of the same title that reprints it, a
  volume of a multi-volume book matches a record that leaves the volume out of its title
  ("The Quantum Theory of Fields. Vol. 2: ..."), and a JMLR paper may carry the year after
  dblp's volume year (JMLR cites 18(167) as 2018; dblp files volume 18 under 2017).
- Names written another way are one person: initials without dots ("Brown, JR" for John R.
  Brown, as Google Scholar exports them), a generational suffix ("Smith IV, David H",
  "David H. Smith IV" against a record's Smith with suffix IV), Danny for Daniel, and an
  organisation named "... Research" first on arXiv ("Cursor Research") is no first author.
- Titles lost the words set with `\texttt`, `\textsf`, `\textup`, `\textmd` or `\mbox`
  ("\texttt{torch.compile}: ..." was read as ": ..."); they are kept now.
- A chapter's title field that also names its book or proceedings ("Quarks and Strings on a
  Lattice, in New Phenomena in Subnuclear Physics") is not a reworded title, and TeX math left
  in dblp's titles is converted before comparing.

## [0.2.1] - 2026-10-04

Fewer false alarms: the fixes for the fourth real-paper batch's false positives. On a fifth
batch collected afterwards (1,005 references), 1.9 false positives per 100 references
(0.2.0: 2.1), short of the 1.5 aimed for; on HALLMARK's held-out split, 2.2% false flags on
valid entries (0.2.0: 2.6%).

### Fixed

- An entry citing an earlier arXiv version is checked against that version's title and
  authors: arXiv records keep every version's author list, not only its title, so a v1 with
  another first author (AstroCLIP) or two more authors is no identifier conflict or author
  mismatch. Versions are now fetched whenever an entry does not fit the latest version
  exactly, for all papers in one request per 50 versions, which also lets reworded preprint
  titles be reported. Old-style IDs (`astro-ph/0501436`) are left out, as the API fails on
  them.
- A LaTeX source that declares no bibliography (no `\bibliography`, no `\addbibresource`) but
  has exactly one `.bib` next to its main file is checked against that `.bib`; CIT005 still
  reports the missing declaration, and the report says where the references came from.
- A cited book is not bound to a journal's review of it, which carries the book's title (a
  journal article of at most four pages found by title search for a `@book` entry).
- A reworded title is not reported when the entry leaves out a short name before the colon
  ("Manifold-Constrained Hyper-Connections" for "mHC: Manifold-Constrained Hyper-Connections").
- A record with only the latest title and another author order (DataCite's arXiv DOIs) is
  "cannot determine" rather than an identifier conflict while the versions are unknown.
- Registry title artefacts are not reported as rewording: a part's number in roman numerals
  for digits ("Seyfert Nuclei. II." for "... 2:"), a footnote mark on the last word
  ("Absorption1"), a symbol dropped after a one-letter quantity ("Z$_{solar}$" for "Z"), and a
  journal's "(with Discussion)" note.
- Gary and Garrison are one given name (Garrison W. Cottrell, "Gary Cottrell" on dblp), and an
  entry cited from a web-only publication (Transformer Circuits Thread, LessWrong, the AI
  Alignment Forum, The Gradient) that no source finds is "cannot determine", not "not found".

## [0.2.0] - 2026-10-04

Check references without a .bib: a compiled `.bbl`, a plain-text list, a PDF, or an arXiv
paper by its ID. Verdicts are unchanged from 0.1.2.

### Added

- A project that ships no `.bib`, as many arXiv sources do, is read from its compiled `.bbl`
  (biblatex, natbib, IEEEtran, Springer LNCS, Elsevier, AAS and physics styles); `check
  refs.bbl` works too. On six real papers that ship both, the `.bbl` gives the `.bib`'s verdict
  for 286 of 315 references.
- `check references.txt`, or `check -` from stdin, reads a reference list as plain text:
  numbered, one per line or paragraph, or wrapped; APA, IEEE, ACM/ACL, natbib, Nature,
  Vancouver, Springer, Elsevier, SIAM, Chicago, MLA, biblatex and AAS. On Badalova & Mayr's 104
  references as printed, it reads the hand transcription's title for 103, first author for
  103, year for all and every DOI and arXiv ID (`evals/plaintext_badalova.py`).
- `check paper.pdf`, with the new `pdf` extra (pypdf), reads the reference list out of a PDF.
  On the PDFs of 20 real papers, 88% of the references checked from their `.bib` are found and
  92% of those get the same verdict (`evals/pdf_agreement.py`).
- `check arxiv:<id>` downloads an arXiv paper's source into a temporary folder, checks it and
  deletes it; a paper submitted without source is checked as its PDF.
- References read from a `.bbl`, text or a PDF are named `ref1`, `ref2`, ... at their lines and
  are never edited by `bib fix`.

## [0.1.2] - 2026-10-04

Fewer false alarms again, measured on two more weeks of papers. On 20 arXiv papers collected
after every fix in this release, false positives are 1.7 per 100 references, with 92 real
problems found (0.1.1 measured 2.3 on its own held-out batch); on the three earlier batches,
used to find false positives, 0.1 to 0.7. Next to five published tools on Badalova & Mayr's
hand-checked references, precision is 72.5% [57.2%, 83.9%]. HALLMARK precision is unchanged,
recall slightly higher. Checks show their progress, and a cold check of a paper with 50
references takes 52 s instead of 140 s.

### Fixed

- A work from before 1990 that no source knows is no longer called not found: it is
  `cannot_determine` with the new reason `OLD_WORK` (REF003; real papers of the 1950s and 60s
  in mechanics and physics are in no index).
- Another kind of publication of the same title is not taken for the cited one: a thesis is no
  journal article, a book chapter no conference paper, software no paper (REF013).
- An entry naming its venue but carrying an arXiv URL is compared with whichever version it
  fits, the preprint or the published version at that venue and year (REF011: an ICML entry
  lists the ICML author order, not arXiv's).
- A dblp record a year or two off the entry gets Crossref's record as well, which knows when a
  journal article appeared online (REF013: ACM Comput. Surv., online 2018, issue 2019).
- REF015 names the published version by the preprint's own authors, not a paper of the same
  title by the first author with others.
- A Wiley or Blackwell DOI's year counts when Crossref's backfile deposit is later (REF013:
  10.1046/j.1365-8711.2000.03658.x is MNRAS, December 2000; Crossref says 2002).
- Titles lose more registry artefacts: IEEE's "[Review Article]", a letter Crossref lost
  (U+FFFD), a record without the entry's subtitle, Zenodo's "owner/repo: v0.10" (REF012).
- The pattern of venue names that still mean a preprint had backspace characters where `\b`
  was meant; a test now fails on any control character in the source.
- Wiley's SICI DOIs keep their bracketed part
  (`10.1002/1097-0347(200103)23:3<230::AID-HED1023>3.0.CO;2-V`): cut at `<`, they were
  reported as not existing (REF002) and given a broken canonical form (REF017).
- A group of authors written another way is the group: word order, hyphens and footnote marks
  do not count (`{LLM-Core Xiaomi}` is arXiv's "Xiaomi LLM-Core Team"; `Kimi-Team`; Crossref's
  "The Tabula Sapiens Consortium*") (REF010/REF011).
- A consortium credited for the people a record lists (Cell's COMBAT Consortium), or a record
  naming only an organisation (dblp's "DeepSeek-AI"), leaves the authors uncompared instead of
  "no author in common" (REF010); a lab the entry names next to its author is no missing
  person ("Kevin Lu and Thinking Machines Lab") (REF011).
- One person's name split another way, or with a name left out, is that person: Crossref's
  given name "Do", family name "Long" for Do Xuan Long, arXiv's "De Luo" for "De Luo, Henry",
  "De La Torre" with no given name (REF011).
- Titles lose more registry artefacts: the AAS journals' old markup in Crossref titles
  (`[ITAL]`, `[CLC]`), Semantic Scholar's ". Plates." and the leading article it drops; and
  Springer's @Inbook export, which keeps the paper's title in `chapter`, is read as meant
  (REF012).
- An article online in October to December with no print date may be cited with next year's
  volume; a proceedings volume a year after the meeting matches when the entry's venue names
  the meeting's year ("Proceedings of SAT-2003") (REF013).
- A book reached through a chapter's DOI is the book the chapter is in, not another work
  (REF001); a workshop at another meeting is the work's workshop version, not a wrong venue
  (REF014).

### Added

- Two reasons for "cannot determine" instead of "not found" (REF003): `UNINDEXED_VENUE`, a
  workshop paper or a book chapter from before 2000 that no source knows, and `ANONYMOUS`, an
  anonymous submission under review ("Anonymous Authors" at OpenReview).
- A journal named in an entry is compared with the record's even when neither is recognised:
  another venue only if the names share no word or abbreviation (REF014). Crossref's ISO 4
  abbreviations and ISSNs count as names of the venue.
- A title of eight words or more, word for word one work's, binds that work even a few years
  off and by other authors, so references with invented authors, venue and year are reported
  instead of left undecided (REF010/REF011, REF013, REF014).
- Progress while references are searched: the CLI's status line counts them and estimates the
  time left; the MCP tool sends progress notifications.
- A false-positive museum: real references paper-preflight once got wrong, and real problems it
  must keep finding, replayed offline as tests (`tests/fixtures/museum/`).
- Two more batches of real papers in the evaluation (first submitted 2026-07-15..21 and
  07-22..28), each collected after the fixes before it and reported as it came out; every flag
  is reviewed by hand in `evals/real_papers_review.toml`.
- A weekly check of the demo paper against the live sources, also run on pull requests that
  change how the sources are asked (`.github/workflows/live.yml`).

### Changed

- dblp is asked ten titles to a query and fifty records to a query: a paper with 50
  references takes 52 s on a cold cache instead of 140 s.
- Crossref is asked for container abbreviations and ISSNs too; every cached Crossref answer is
  fetched once more.

## [0.1.1] - 2026-10-03

Fewer false alarms on real bibliographies. On the references of 20 arXiv papers used to find
them, false positives fell from 4.5 to 0.1 per 100 references with every real problem still
found; on 20 papers collected afterwards, 2.3 per 100. Next to five published tools on Badalova
& Mayr's hand-checked references, precision is 69.2% [53.6%, 81.4%] (the best of the five:
50.9%). HALLMARK results are unchanged.

### Fixed

- Early-access journal articles: when Crossref has no online date, the year the DOI was
  created (up to two years before the issue) counts too, so an IEEE article cited with its
  online year is no longer told to use the print year (REF013).
- A journal issue printed in December counts for the next year too (MNRAS 500(4), cover date
  January 2021, printed December 2020), so the issue's year is not reported (REF013).
- An entry that names where the work appeared (booktitle or journal) cites that version even
  when the venue is not recognised and the entry keeps its arXiv eprint: no more REF015
  telling it to cite the published version it already cites.
- An organisation leading a record's author list ("OpenAI" before Josh Achiam on the GPT-4
  report) is not taken for the first author when the entry leaves it out (REF011).
- An entry citing an earlier arXiv version (matched through that version's title) is no longer
  reported for its author order when a later version reordered the authors (REF011).
- A published version's year a year or two after the only record found, a preprint (dblp lists
  ICLR 2026 papers as 2025 CoRR preprints until it adds the conference), is no longer
  reported; with a published record of the work known, the year is checked as before.
- A given name in another language's form ("Grigoris" for Gregory, "Giorgos" for George) or a
  Polish diminutive ("Tomek" for Tomasz) is the same person, not another author (REF011).
- A name written family name first without a comma ("Zhang C.", which BibTeX reads as given
  name Zhang) or filed that way by a registry ("Shwetha S") is matched as meant, instead of
  being reported as other authors (REF010/REF011).
- An apostrophe's form does not make another person: Crossref's curly "O’Connell" is the
  entry's "O'Connell" (REF010/REF011).
- Registry names are read as written: a family name repeated in its original script
  ("Lin 林, Lihwai 俐 暉" on Crossref) or carrying a suffix ("Davidson Jr.") is the
  same person, and co-authors sharing a surname are paired by given name as a whole, so one
  Lin no longer takes the Lin another needs (REF011).
- Titles lose the markup registries and ADS exports carry: tags escaped as entities, ADS's
  `<ASTROBJ>`, a whole LaTeX document around a formula, `\raisebox`, and the TeX that arXiv
  keeps in titles; the solar symbol ⊙ reads as "sun" (REF012).
- A record with the same title and authors but another venue and year is the same authors'
  other publication ("The Solar Chemical Composition": ASP Conf. Ser. 2005 and Nuclear Physics
  A 2006), not the cited one with a wrong year (REF013).
- An entry linking to a site no source indexes (a society's own proceedings site) is no longer
  called not found when no source knows it: it is `cannot_determine` with the new reason
  `UNINDEXED_LINK` (REF003).
- The year in a dblp key counts when it is next to the recorded one: a workshop filed under the
  year its proceedings appeared (BIR 2024 in dblp as 2025, key `conf/birws/AtanassovaB24`)
  may be cited with the workshop's year (REF013).
- A team is one author named by its project: arXiv's "Gemma Team" is the entry's `{Gemma}`,
  `Gemma Team` or `Team, Gemma`, DataCite's "Euclid Collaboration" its `Collaboration, Euclid`
  (REF010/REF011).

### Added

- Two evaluations on real data: the bibliographies of 40 arXiv papers from July 2026 in two
  batches, every flag reviewed by hand (`evals/real_papers.py`), and a head-to-head with five
  published tools on Badalova & Mayr's references (`evals/run_badalova_mayr.py`). The README's
  accuracy section leads with them.
- A demo GIF of a real run in the README, made by `docs/demo/make_gif.py`.

## [0.1.0] - 2026-10-03

The first release.

### Added

- Project scaffold: packaging, CLI entry point (`--version`, `doctor`), CI, contribution docs.
- Verdict engine: one verdict per reference (verified, metadata mismatch, identifier conflict,
  not found, cannot determine) with rules REF001-REF005, REF010-REF015, REF018, REF090 and RUN001.
  Search results with another title and no author in common are other works: they no longer
  keep an entry nobody found from being reported as not found (REF003).
- `check` verifies the cited references online by default; `--offline` answers from the local
  cache only. Text output adds a verdict summary line; JSON adds `verification` and `references`.
  Exit code 2 when a source was unavailable and nothing blocking was found.
- `--refresh` (`check`, `bib fetch`, `bib fix`) asks every source again instead of using cached
  answers; within the run each answer is still asked for once. It contradicts `--offline`.
- The JSON report records what each source did (`verification.sources`: requests, cache hits,
  stale hits, negatives and unavailability by reason), so a run can be audited and compared.
- Releases are published to PyPI from GitHub Releases through trusted publishing, with PEP 740
  attestations (`release.yml`, `docs/releasing.md`); the PyPI page links back to GitHub.
- When the arXiv API refuses requests or times out, arXiv IDs are verified through DataCite
  (`10.48550/arXiv.<id>`); the run still reports arXiv as unavailable.
- Semantic Scholar as an optional rescue source, used only when `S2_API_KEY` is set: it is asked
  about references no other source found, stays below the keyed limit of 1 request/s, backs off
  exponentially on HTTP 429, and its outages never block a verdict. Its answers are cached
  locally but never exported (licence).
- PubMed (NCBI E-utilities) verifies PMIDs: its record anchors the entry, a PMID it does not
  know is REF002, and articles it marks as retracted get REF004. `doctor` checks it too.
- PMCIDs are verified too: PubMed Central gives their PMID, whose PubMed record anchors the
  entry; a PMCID it does not know is REF002.
- Evaluation harness for the HALLMARK benchmark (`evals/run_hallmark.py`): flag / clean / abstain
  outcomes, fabrication-only and any-issue modes, precision, conservative recall, false-positive
  rate and coverage, broken down by hallucination type.
- `doctor` checks each source with one uncached request and reports `ok`, `unavailable` (with the
  reason: rate limit, bot wall, timeout ...) or `skipped`; `--offline` skips the check.
- MCP server (`paper-preflight mcp`, needs the `mcp` extra): read-only `preflight_check` with
  paged findings and `preflight_explain`; paths are confined to the workspace root
  (`docs/mcp.md`).
- Claude Code plugin and marketplace (`plugins/paper-preflight`): the MCP server plus a
  `paper-preflight` skill that runs the check before a paper is called finished.
- pre-commit hooks (`docs/pre-commit.md`): `paper-preflight-offline` (seconds, cached verdicts
  only) and `paper-preflight` (full online verification).
- `paper-preflight explain [RULE]`: what a rule detects, its severity, its message and whether a
  fix is safe; without an argument it lists every rule.
- CFG001: a `% preflight: ignore[...]` comment that silenced nothing is reported (info), among
  the rules that ran on its entry; unknown rule names always are. Documented in the README.
- First full HALLMARK dev_public results (`evals/results/hallmark-dev_public.md`), with a second
  summary that leaves out labels checked by hand and found wrong (`evals/hallmark_disputed.toml`).
- `bib fetch <DOI|arXiv ID>` or `bib fetch --title ...`: a BibTeX entry built from the registry
  record (published versions of preprints keep their eprint; retracted works warn; ambiguous
  titles list candidates; `--format json` for agents).
- MCP tool `preflight_bib_lookup`: `bib fetch` for agents.
- `bib fix`: edits the .bib files from the verified records, as a diff or with `--apply`;
  `--level safe` (identifier formatting, missing DOIs) or `unsafe` (also authors, title, year,
  venue, wrong identifiers). Only the affected fields change. REF016 offers a missing DOI.
- GitHub Action (`action.yml`): runs the check, writes the job summary and a SARIF report,
  caches answers per bibliography (`docs/github-action.md`).
- Identifier lookups (doi.org, Crossref, DataCite, OpenAlex, arXiv, and dblp's published-version
  links) are cached per identifier, so adding an entry no longer makes its batch companions
  unverifiable in `--offline` runs, nor hides their published versions (REF015).
- REF014 also reports an invented venue on a paper whose venue is known: an unrecognised name
  that shares no word or abbreviation with the recorded venue (abbreviations stay unknown).
- REF012 also reports a title that is close to the record's but has other words ("towards" for
  "for", "Hidden" for "Latent") and names them; spelling, hyphenation, "&", math and
  "RETRACTED:" notices do not count, nor do preprints whose earlier titles are unknown.
- REF011 also reports an author whose surname is right but whose given name belongs to someone
  else ("Aviral Sharma" for Archit Sharma). Initials, short forms, middle names, hyphenation,
  transcriptions and common nicknames (Bill, Misha) agree.
- More venues are recognised for REF014: AISTATS, UAI, COLT, CoRL, TMLR, IJCV, WWW, WSDM, CIKM,
  ICASSP, Interspeech, MICCAI, ICRA, IROS, WACV and BMVC. URLs in a venue field are ignored.
- An unrecognised venue is also reported when it names something the recorded venue does not
  ("International Conference on Quantum Machine Learning" for ICML). Abbreviations, ordinals,
  series and publishers (PMLR, LNCS, OpenReview) never count, only booktitle and journal are
  judged, and a workshop must share no word at all with the recorded venue.
- The same recognised venue now counts as evidence when binding a search result: a four- or
  five-word title at the same venue in the same year names one work (wrong authors become
  REF010 instead of "cannot determine"), and a year more than three years off is no reprint
  when the venue is the same (REF013).
- A search result by the same people at the same venue in the same year binds when its title
  is one or two words off, even below the usual similarity threshold; REF012 names the words.

[Unreleased]: https://github.com/amos689/paper-preflight/compare/v0.4.0...HEAD
[0.4.0]: https://github.com/amos689/paper-preflight/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/amos689/paper-preflight/compare/v0.2.1...v0.3.0
[0.2.1]: https://github.com/amos689/paper-preflight/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/amos689/paper-preflight/compare/v0.1.2...v0.2.0
[0.1.2]: https://github.com/amos689/paper-preflight/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/amos689/paper-preflight/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/amos689/paper-preflight/releases/tag/v0.1.0
