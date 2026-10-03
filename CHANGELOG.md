# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Fixed

- An entry citing an earlier arXiv version (matched through that version's title) is no longer
  reported for its author order when a later version reordered the authors (REF011).
- A given name in another language's form ("Grigoris" for Gregory, "Giorgos" for George) or a
  Polish diminutive ("Tomek" for Tomasz) is the same person, not another author (REF011).

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

[Unreleased]: https://github.com/amos689/paper-preflight/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/amos689/paper-preflight/releases/tag/v0.1.0
