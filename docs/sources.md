# Sources

paper-preflight asks public scholarly databases about the works a paper cites. Only metadata of
the cited works (identifiers, titles, author names, years, venues) is sent; the manuscript never
leaves your machine. Every source is asked through one client that keeps to its published rate
limit, caches every answer, and treats a rate limit, a bot challenge, a timeout or an outage as
"unavailable", never as "no such work".

## What is asked of which source

| Source | Asked about | Notes |
|---|---|---|
| [doi.org](https://www.doi.org/) | Which registry owns each DOI, and whether it exists at all | One call routes every DOI; a DOI doi.org does not know is REF002 |
| [Crossref](https://www.crossref.org/) | DOIs it registered; title searches; retractions, corrections and expressions of concern (with Retraction Watch's data); container titles for venues | Faster with `PAPER_PREFLIGHT_EMAIL` (the polite pool) |
| [dblp](https://dblp.org/) | Computer science: title searches, records with ordered authors, published versions of arXiv preprints, its streams of conferences and journals | Read through its SPARQL endpoint; its search API is behind a bot wall and never used |
| [arXiv](https://arxiv.org/) | arXiv IDs: every version's title and authors, withdrawals | One request every three seconds, as its terms ask |
| [DataCite](https://datacite.org/) | DOIs it registered: arXiv's (10.48550), Zenodo's and other repositories' | Stands in for arXiv when arXiv does not answer (RUN002) |
| [PubMed](https://pubmed.ncbi.nlm.nih.gov/) | PMIDs and PMCIDs, and articles marked retracted | Authoritative for PMIDs |
| [OpenAlex](https://openalex.org/) | Retraction cross-checks, existence checks, its catalogue of journals and proceedings for venues | Never anchors a reference alone: merged records can be polluted. `OPENALEX_API_KEY` raises the budget |
| [Semantic Scholar](https://www.semanticscholar.org/) | A rescue title search for references nobody else found | Only with `S2_API_KEY`; its answers are never exported, and its years and types are not trusted |
| [Open Library](https://openlibrary.org/) | Books without a DOI that nothing else found | A record confirms a book only when title, an author and an edition's year all fit |
| [GitHub](https://github.com/), [PyPI](https://pypi.org/), [CRAN](https://cran.r-project.org/) (via [R-hub's crandb](https://crandb.r-pkg.org/)) | Repositories and packages an entry links to, when nothing else found it | Authors and years are never compared: software is cited by version, and owners are accounts |
| The linked web page, and the [Wayback Machine](https://web.archive.org/) | Whether a page nothing else found still opens, and whether it was archived | Only the status is read (a HEAD request, confirmed by a GET whose body is never read); no request goes to private or local addresses |

Semantic Scholar, Open Library, GitHub, PyPI, CRAN, the web check and the Wayback Machine are
optional: `disable-sources` in [the settings](configuration.md#project-settings) turns them
off. The others judge the references and cannot be turned off.

## What is never done

- No scraping of sites that forbid automated access (Google Scholar, CNKI, Wanfang, VIP, Baidu
  Scholar, publishers' paywalled pages), and no attempt to get around a bot challenge.
- No credential is printed, logged, cached or sent anywhere but its own service.
- No source's answers are redistributed against its licence: Semantic Scholar's are marked
  non-exportable in the cache, and the tests use synthetic data for it.

## Adding a source

A new source is welcome when it holds records the others miss and its terms allow programs to
ask. Open an issue first: the [ground rules](../CONTRIBUTING.md#ground-rules) apply, and the
[architecture decisions](adr/README.md) (0002 on abstaining, 0003 on routing, 0005 on adapters
and the cache) explain the shape.

1. **Read the terms.** Note the rate limit, whether an identified User-Agent or a key is asked
   for, and whether answers may be cached and redistributed. A source behind a bot challenge is
   not usable.
2. **Write the adapter** in `src/paper_preflight/sources/<name>.py`: a `SourcePolicy` with the
   source's rate limit (`min_interval`, `max_concurrency`, `timeout`; `exportable=False` if its
   licence forbids redistribution), and functions that take a `SourceClient` and return
   `SourceRecord`s (`sources/record.py`). Use `client.get_json` or `client.get_text`: they pace
   requests, cache answers by kind (`EntryKind`) and raise `SourceUnavailable` for rate limits,
   challenges, timeouts and outages. Never turn unavailability into a negative answer.
3. **Register it** in `Sources` (`resolve.py`): a field, a client in `Sources.create` (through
   `optional(...)` and `config.OPTIONAL_SOURCES` if the paper can be judged without it) and an
   entry in `all_clients`. Give it a display name in `bibtex.SOURCE_NAMES` and a probe in
   `connectivity.py` for `doctor`.
4. **Ask it only when it can help:** for references of the kind it holds, usually only when no
   other source found them. Records whose authors or years are unreliable go into
   `verdict.AUTHORS_NOT_CHECKED_AGAINST`, or carry no year: a record may confirm what it knows,
   never contradict what it does not.
5. **Test it** against `tests/fake_web.py`, with synthetic responses or recorded ones the licence
   allows (CONTRIBUTING lists which). Cover the source answering, not having the record, and
   being unavailable.
6. **Measure it** before asking for a merge: the replay of the development papers
   (`evals/replay.py`) must gain no false positive, and `evals/live_smoke.py` must pass against
   the live sources. Say in the pull request what it verified that was undecided before.
7. **Document it** in this table, the README's list of sources and the CHANGELOG.
