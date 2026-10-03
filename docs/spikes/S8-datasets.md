# Spike S8: Benchmark datasets (formats, labels, pins, adaptation)

Status: done, 2026-10-03. Pins are in `evals/datasets.lock`. Data is in `evals/.data/<dataset>/` (about 10.9 MB,
excluded by `.gitignore`). Scratch scripts are in `.spikes/datasets/`: `fetch_github.py`, `inspect_*.py`, and
`write_lock.py`, which regenerates the lock.

## TL;DR

- **HALLMARK v1.2.3** (MIT): 1,950 labelled public BibTeX entries plus a 122-entry stress split. Ground truth is
  `VALID`/`HALLUCINATED`; `UNCERTAIN` is a prediction label only. 10 of 14 types are real papers with wrong metadata.
- **Badalova & Mayr** (CC BY 4.0): 104 formatted strings in a **cp850** CSV with 90 characters lost to `?`. Tool
  scores recompute exactly to paper Table 4 (precision 0.312–0.509). "Problematic" is **not subdivided**.
- **CiteTracer synthetic v2** (MIT): 2,450 citations (REAL 1023 / POTENTIAL 271 / HALLUCINATED 1156), all H records
  one-field mutations, with label-leaking fields. The ICLR real-world part is local-only, not redistributable.
- **CiteAudit**: no license, so it is pinned by commit and blob SHA-1 and fetched at runtime. `GT=true` means *real*.

## A. HALLMARK (rpatrik96/hallmark)

**Pin.** Tag `v1.2.3`, commit `75e39a08b69a…`, released 2026-09-02.
- `hallmark/evaluation/selective.py` is **absent at v1.2.3**. It is pinned separately from `main@7b9fbfa82228…`,
  where it was added on 2026-09-04 and is self-described as "staged, not wired".
- Since the tag, `main` has one data commit (`7c3559b580`). It changes `subtests` only (29 dev / 28 test entries).
  Labels, types and fields are identical to the tag (diffed locally).

**License:** MIT, so redistributable = true. We still fetch at runtime rather than vendor, because the files carry a
"do not train" canary.

| split (`data/v1.2/`) | rows | VALID | HALL. | notes |
|---|---|---|---|---|
| `dev_public.jsonl` | 1119 | 513 | 606 | all 14 types, including the 3 stress types |
| `test_public.jsonl` | 831 | 312 | 519 | all 14 types |
| `stress_test.jsonl` | 122 | 1 | 121 | the one VALID is a `__canary__` row; drop it |
| `test_hidden` | 454 | – | – | not public. README total 2,526 = 2,072 public + 454 hidden |

Baselines pinned: `bibtexupdater_{dev,test}_public.json`, `doi_only_{dev,test}_public.json`, `manifest.json`,
`results_matrix_dev_public.csv`, and the per-entry raw btu output `bibtexupdater_raw_dev_public.jsonl` (Git LFS).

**Format.** UTF-8 JSONL, one `BenchmarkEntry` per line. `raw_bibtex` is always null, and the BibTeX is rebuilt from
`fields`:

```json
{"bibtex_key": "c874720f3e08", "bibtex_type": "inproceedings", "fields": {"title": "FedNP: Towards Non-IID Federated
 Learning via Federated Neural Propagation", "author": "Xueyang Wu and Hengguan Huang and …", "year": "2023",
 "doi": "10.1609/AAAI.V37I9.26237", "booktitle": "ICML"}, "label": "HALLUCINATED", "hallucination_type":
 "wrong_venue", "difficulty_tier": 2, "explanation": "Venue changed to 'ICML' (original was different)",
 "generation_method": "perturbation", "source_conference": "AAAI", "subtests": {"doi_resolves": true,
 "title_exists": true, "authors_match": true, "venue_correct": false, "fields_complete": true,
 "cross_db_agreement": false}, "raw_bibtex": null, "schema_version": "1.0"}
```

**Label schema.** `label` is `VALID`/`HALLUCINATED`, `hallucination_type` is one of 14 values (null when VALID),
and `difficulty_tier` is 1–3. `subtests` holds six three-valued checks (`None` = field absent). `generation_method`
is scraped, perturbation, llm_generated, adversarial or real_world; 27 dev VALID entries are generated. Undocumented
audit fields leak the label: `relabeled_*` (115 dev / 84 test) and `matched_*`/`match_scores` (98 / 69).

**The 14 types.** "Fab" means a fabricated work. "Meta" means a real paper with wrong metadata. The class comes from
`EXPECTED_SUBTESTS.title_exists` plus the generator's meaning.

| type | tier | dev | test | stress | class | our likely verdict |
|---|---|---|---|---|---|---|
| fabricated_doi | 1 | 38 | 29 | – | Meta (fake DOI, real paper) | identifier_conflict |
| nonexistent_venue | 1 | 39 | 37 | – | Meta | metadata_mismatch |
| placeholder_authors | 1 | 41 | 33 | – | Meta | metadata_mismatch |
| future_date | 1 | 30 | 29 | – | Meta | metadata_mismatch |
| chimeric_title | 2 | 47 | 23 | – | **Fab** | not_found |
| wrong_venue | 2 | 47 | 34 | – | Meta | metadata_mismatch |
| swapped_authors (docs: `author_mismatch`) | 2 | 67 | 63 | – | Meta | metadata_mismatch |
| preprint_as_published | 2 | 30 | 29 | – | Meta | metadata_mismatch |
| hybrid_fabrication (real DOI + fake metadata) | 2 | 26 | 29 | – | **Fab** | identifier_conflict |
| near_miss_title (title off by 1–2 words) | 3 | 52 | 40 | – | **Fab** by label; borderline | mismatch or not_found |
| plausible_fabrication | 3 | 78 | 68 | – | **Fab** | not_found |
| merged_citation (stress) | 2 | 30 | 29 | 46 | Meta (chimera of real papers) | metadata_mismatch |
| partial_author_list (stress) | 2 | 32 | 31 | 39 | Meta | metadata_mismatch |
| arxiv_version_mismatch (stress) | 3 | 49 | 45 | 36 | Meta | metadata_mismatch |

Totals: Fab is 203 dev / 160 test / 0 stress, and Meta is 403 / 359 / 121.

**UNCERTAIN semantics** (from `metrics.py`).

`UNCERTAIN` is a prediction label alongside `VALID` and `HALLUCINATED`. `confidence` is P(the predicted label is
correct).

| mode | how UNCERTAIN is scored | how a missing prediction is scored |
|---|---|---|
| conservative (default) | **dropped** from the confusion matrix (DR, FPR, F1, MCC) and from AUROC/ECE, but counted in `coverage` | VALID |
| aggressive (`eval_mode="aggressive"`) | HALLUCINATED with confidence 0.55 | HALLUCINATED with confidence 0.55 |

Two pitfalls:
- The README says UNCERTAIN is "treated as VALID". The code excludes it.
- `coverage_adjusted_f1 = F1 × coverage`, and coverage counts UNCERTAIN, so abstaining on every hard item raises F1
  at no cost.

`selective.py` (main) adds risk-coverage/AURC (a retained UNCERTAIN counts as an error; missing predictions are
excluded), `p_hallucinated` (H→c, V→1−c, U→0.5), calibration on the flagged subset, a Brier decomposition, and
`abstention_breakdown`, which separates genuine abstentions from `[Error fallback]` API failures.

**Reference baselines:**

| baseline | split | DR | FPR | F1 | MCC | UNCERTAIN |
|---|---|---|---|---|---|---|
| bibtexupdater | dev_public | 0.865 | 0.092 | 0.890 | 0.771 | 0 |
| bibtexupdater | test_public | 0.877 | 0.115 | 0.901 | 0.750 | 0 |
| doi_only | test_public | 0.387 | 0.279 | 0.498 | 0.110 | 0 |

The bibtexupdater wrapper maps btu's `unconfirmed`, `api_error` and `skipped` to **VALID**, so its numbers are
abstain-as-negative. `doi_only` counts an entry with no DOI as VALID.

**Pitfalls:**
- Stale baselines: `doi_only_dev_public.json` used an old 1068-entry dev split, `manifest.json` F1 values are out of
  date (0.909 vs 0.890 in the file), and bibtexupdater per-type counts predate the v1.2.3 retyping of 4 entries.
- Label leaks: `url` is on 60/513 VALID dev entries but 9/606 HALLUCINATED (drop it, as `to_blind()` does), and
  `journal` appears only on HALLUCINATED entries.
- Quirks: venues are abbreviations (`NeurIPS`, `Mach. Learn.` as booktitle). 226 dev titles repeat, and one title
  can be VALID in one entry and perturbed in another. `bibtex_key` is opaque hex, and predictions must use it.

## B. Badalova & Mayr (Zenodo 10.5281/zenodo.21457492, v1.0.0)

**Pin.** Zenodo REST record 21457492 (2026-07-20; concept DOI 10.5281/zenodo.21457491), with the API record JSON
saved. The md5 of both files matches Zenodo: the CSV (46,760 B, `60ac4833…`) and `README.md` (4,595 B,
`044a050a…`). The paper is arXiv 2607.22693v2. **License:** CC BY 4.0, so redistributable = true with attribution,
and a derived BibTeX conversion may be committed with credit. It is a convenience sample, not for prevalence.

| doc | source and citation style | refs | verified | problematic |
|---|---|---|---|---|
| P1 | RenoBench (CiteX 2026), APA | 24 | 21 | 3 |
| P2 | SoFAIR (Scientific Data 2026), numeric/biblatex | 15 | 11 | 4 |
| P3 | arXiv 2510.21310v1 (NeurIPS 2025 paper from GPTZero's list), natbib-like | 65 | 39 | 26 |
| **total** | | **104** | **71** | **33** |

**Columns.** Five `document_*` columns; `reference_number` (a string such as `R4`, unique with `document_id`);
`reference` (the full formatted string); `manual_label` (`verified`/`problematic`); and one `flagged`/`not_flagged`
column per tool (`checkifexist`, `hallucitechecker`, `hallucinator`, `halref`, `refchecker`).

```
document_id,document_title,document_url,document_venue,document_year,reference_number,reference,manual_label,checkifexist,hallucitechecker,hallucinator,halref,refchecker
P1,RenoBench: A Citation Parsing Benchmark ,https://zenodo.org/records/20382199,Workshop on Citation Extraction and Parsing (CiteX),2026,R1,"Agrawal, L. A., Tan, S., …
```

**Polarity.** The positive class is `problematic`. A tool counts as `flagged` if it marked the reference as
"suspicious, mismatched, unresolved, not found, or otherwise requiring verification", so **could-not-verify counts
as a flag**.

**Subdivision of "problematic": none.** The CSV is binary. The paper lists problem kinds only in aggregate:
incorrect titles, mismatched authors or venues, bad DOIs, unverifiable references and publication-status
inconsistencies. Fabrication-only scoring therefore needs our own sub-annotation.

**Recomputed per-tool scores.** They are identical to paper Table 4:

| tool | TP | FP | FN | TN | precision | recall |
|---|---|---|---|---|---|---|
| CheckIfExist | 31 | 34 | 2 | 37 | 0.477 | 0.939 |
| HalluCiteChecker | 18 | 20 | 15 | 51 | 0.474 | 0.545 |
| Hallucinator | 29 | 28 | 4 | 43 | **0.509** | 0.879 |
| HalRef | 24 | 53 | 9 | 18 | **0.312** | 0.727 |
| RefChecker | 32 | 36 | 1 | 35 | 0.471 | 0.970 |

**Three sample references,** verbatim after cp850 decoding. Each `?` is export damage.
1. P1 R4, problematic: `Atanassova, I., Bertin, M., & Mayr, P. (2020). Synthetic versus Real Reference Strings for Citation Parsing. Proceedings of the 16th International Conference on Semantic Systems, 165?172`
2. P2 R2, verified: `James Howison and Julia Bullard. ?Software in the scientific literature: Problems with seeing, finding, and using software mentioned in the biology literature?. In: Journal of the Association for Information Science and Technology 67.9 (2015), pp. 2137?2155. doi: 10.1002/asi.23538`
3. P3 R4, problematic: `Franz Aichberger, Lily Chen, and John Smith. Semantically diverse language generation. In International Conference on Learning Representations (ICLR), 2025`

**Encoding pitfalls.** The file is not UTF-8, cp1252 decoding fails on byte 0x81, and lines end in CRLF. cp850
decodes all 13 non-ASCII bytes to plausible names (Ramé, Krüger, György, João). 58 references hold 90 literal `?`,
each standing for something lost in export: an en-dash, a curly quote, the APA ellipsis (`Pot, E., ? Hussenot,
L.`), an apostrophe, or a letter outside cp850 (`Micha? Marci?czuk`, `Ond?rej Dus`).

**Faithful BibTeX conversion** (keep the authors' errors, undo only the export's):
1. Decode as cp850 and keep `raw`. Repair export damage with logged rules: `?` between digits becomes `--`, a `?`
   pair around a title becomes quotes, ` ? ` in an author list becomes `\ldots`, and a `?` inside a word becomes
   `unknown_char` (never guessed). Better: recover the true characters from the sources (P3's arXiv LaTeX source
   likely has the original `.bib`/`.bbl`; P2 has Nature HTML; P1 a Zenodo PDF).
2. Parse with a style-aware parser (3 styles, so one rule set per document or a GROBID-like tool). **Hand-check all
   104 parses**, so that parse errors never count as verification errors.
3. Never normalise from lookups. Keep authors as written (including a fabricated "John Smith"), keep years and venues
   as written, write "et al." as `and others`, and record the inferred entry type in `note`.
4. Ship both `raw` (tests the string-parser path) and `bibtex` (tests the LaTeX path).

## C. CiteTracer (aaFrostnova/CiteTracer; HF Afrostnova/Hallucinated_Citation)

**Pin.** The repo has no tags, so it is pinned at `main@0483831f0174…` (2026-07-28). The HF revision `0e36cb80c250…`
has top-level files that are git-blob-identical to `data/synthetic_data/v2/`. **License:** MIT. Do not clone the
repo: its history is about 1.3 GB.

**Synthetic v2** (redistributable = true). It has 11 per-subtype JSON arrays, `_all_test.json` (their
concatenation, 2,450 records) and `meta.json` (ground truth keyed by `citation_id`). Excerpt (H4-0001, with `meta`
minus `seed`):

```json
{"title": "T2I-Adapter: Learning Adapters to Dig Out More Controllable Ability for Text-to-Image Diffusion Models",
 "authors": ["Chong Mou", "Xintao Wang", "…"], "venue": "Proceedings of the AAAI Conference on Artificial Intelligence",
 "year": 2022, "doi": "", "arxiv_id": "", "url": "", "volume": "38", "pages": "4296-4304", "publisher": "…",
 "location": "", "_source": "openalex", "_query_topic": "large language models", "_query_venue": "AAAI",
 "_query_year": 2024, "citation_id": "H4-0001"}
{"subtype": "H4", "label": "HALLUCINATED", "category": "Meta", "mutation_type": "date_error",
 "changed_fields": ["year"], "explanation": "Year: 2024 → 2022."}
```

**Label schema.** `label` is `REAL`, `POTENTIAL_HALLUCINATED` or `HALLUCINATED`. Each `meta` entry also has
`subtype`, `mutation_type`, `changed_fields` and `seed` (the real record). See `docs/taxonomy.md`.

| subtype | n | meaning |
|---|---|---|
| R1 / R2 / R3 | 338 / 342 / 343 | exact / format variant (lowercased title, initials, abbreviated venue; must be *verified*) / "et al."/"Others" |
| P1 | 91 | author nickname variant (Yuli for Yulia) |
| P3 | 180 | invented volume/pages/location that no source can confirm or refute |
| H1 | 200 | title: substitution 67, paraphrase 67, fabrication 66 |
| H2 | 198 | authors: add/delete 67, fabricate 66, reorder 65 |
| H3 / H4 | 197 / 195 | venue (100) or venue+year (97) / year |
| H5 / H6 | 200 / 166 | DOI fabricated or nonexistent / pages, volume, publisher or location |

R4 and P2 are documented but have no data. Every H record is a real seed with one field mutated.

**Their scoring** (`docs/metric_guide.md`). R1–R3 merge into one bucket, giving a 9×9 bucket confusion matrix with
per-bucket P/R/F1. Errors are "safe" or "dangerous" (more permissive than the truth); DER is the primary metric.
Binary detectors merge P into H. Timeouts count as H, or are excluded with coverage reported.

**Leakage pitfalls.** Strip `citation_id` (its prefix is the subtype) and every `_*` field. `_source` is `""` on all
180 P3 records, and `year != _query_year` on all H4 and P3 records and 97 H3 records. Among H records only H5 has a
DOI, and no P record has a `url`. Years go up to 2027. There is no entry-type field.

**ICLR 2026 real-world part** (redistributable = false; inspected only; aggregate figures only). 647 desk-rejected
submissions with 807 structured fabricated citations (1–19 per paper; 48 with a DOI, 297 with an arXiv ID), each
with `raw_text` plus parsed fields. The README claims 957 citations "incl. ACM CCS 2026", but the CCS part is not in
this commit. All rows are positives, so the set supports recall only.

## D. CiteAudit (shiiiikw/CiteAudit)

**Pin.** Commit `99744f032ad3b42a1d09929ddcf7f3379e7320d5`, the only commit (2026-04-30). The repo is 754 KB.
**There is no LICENSE** (the GitHub license API returns 404), so it was **not downloaded**. Redistributable = false:
fetch at runtime only.

**Files** (bytes): `README.md` 2749, `config.py` 611, `pdf_processor.py` 2663, `serp_verify.py` 27682,
`test_serp.py` 8041, `requirements.txt` 105, `.gitignore` 234, and **`data/benchmark.json` 2,757,992**. The lock pins
every file by git blob SHA-1; `benchmark.json` is `90a83ef6…`.

**Format** (per the README): 9,442 records under `data`, each `{source_type: realworld(3356)|generated(6086),
citation: str, GT: bool, Predict: bool}`. **`GT=true` means real.** `Predict` is undocumented and must be ignored.
The citations are formatted strings, so they use the B&M parser path.

## DRAFT label mapping

Our verdicts are `verified`, `metadata_mismatch`, `identifier_conflict`, `not_found` and `cannot_determine`. Flags
(`retracted`, `preprint_published`) **never make an item positive**: HALLMARK's relabel made real arXiv-cited papers
VALID, and no dataset labels retraction. Report flags separately.

| our verdict | positive under "any-issue"? | positive under "fabrication-only"? |
|---|---|---|
| verified | no | no |
| metadata_mismatch | **yes** | no (a real record was matched) |
| identifier_conflict | **yes** | **only if no title-level match** (the hybrid_fabrication pattern; needs a sub-reason) |
| not_found | **yes** | **yes** |
| cannot_determine | abstention, see below | abstention, see below |

| dataset | any-issue: GT positive (negative) | fabrication-only: GT positive (negative) |
|---|---|---|
| HALLMARK | `HALLUCINATED`, all 14 types (`VALID`) | the 4 Fab types (`VALID` + the 10 Meta types); report near_miss_title separately |
| B&M | `problematic` (`verified`) | TODO: needs our sub-annotation of the 33. Any-issue only for now |
| CiteTracer synthetic | H, with P merged per their guide; also report with P excluded (R). Native 3-class: verified→REAL, cannot_determine→POTENTIAL, the rest→HALLUCINATED, scored with SER/DER | not meaningful (single-field mutations); at most H1 `title_fabrication` (66) vs R. Use ICLR for fabrication recall |
| CiteTracer ICLR | all positive, recall only | all positive, recall only |
| CiteAudit | `GT == false` (`GT == true`) | same as any-issue (real/fake labels); verify after the runtime fetch |

## Scoring abstentions (`cannot_determine`)

Always report **coverage** (decided / total) and each metric in two modes, plus **selective** precision and recall
on decided items only:
- **Conservative:** cannot_determine → negative. This is the deployment default and matches bibtexupdater
  (`unconfirmed`→VALID) and HALLMARK (missing→VALID).
- **Aggressive:** cannot_determine → positive. This matches B&M's "flagged" and CiteTracer's timeout→HALLUCINATED.

Per dataset:
- **HALLMARK:** emit `UNCERTAIN` and run the official `evaluate(eval_mode="both")`, whose "conservative" mode is our
  selective mode. Also submit a cannot_determine→`VALID` run to compare like-for-like with bibtexupdater. Add AURC
  from the pinned `selective.py`, and report API-error fallbacks apart from genuine abstentions.
- **B&M:** the headline number is aggressive, for comparability with the 5 tools. Also show conservative.
- **CiteTracer:** map abstentions to POTENTIAL and report DER/SER.

## Recommended adapter interface

```python
class DatasetAdapter(Protocol):
    name: str                                   # == [[dataset]].name in datasets.lock
    def verify_pins(self, lock: Lock) -> None   # sha256 / git-blob check; raise on drift
    def records(self, split: str) -> Iterator[EvalRecord]

@dataclass(frozen=True)
class EvalRecord:
    ref: Reference    # what the checker sees (label-free)
    gold: Gold        # never passed to the checker

# Reference: key (opaque: HALLMARK bibtex_key, "P3-R4", hash of citation_id, CiteAudit row index),
#   input_kind ("bibtex" | "formatted_string" | "structured"), raw (exact input text or None),
#   entry_type, title, authors: list[str] (as written; "et al."/"Others" -> trailing "others"),
#   year: str (as written), venue (booktitle/journal/venue), doi, arxiv_id, url, volume, pages,
#   publisher, location (empty -> None), source_note (e.g. "cp850; '?'->'--' x2").
# Gold: dataset, split, native_label, native_subtype, generation_method,
#   pos_any_issue: bool | None, pos_fabrication: bool | None   (None = excluded under that definition)
```

Adapter rules:
- **HALLMARK:** use the `BlindEntry` view (no `url` or audit fields), skip `__canary__*`, and render with
  `to_bibtex()` so the input goes through our BibTeX parser.
- **B&M:** decode cp850, apply the logged `?` repairs, then use a frozen hand-checked parse table (to be written).
- **CiteTracer:** allow-list only the 11 bibliographic fields. **CiteAudit:** fetch at runtime, verify the blob SHA,
  and flip `GT`.

## Open items

1. Sub-annotate the 33 B&M problematic references as {nonexistent, metadata, identifier, unverifiable}, and commit
   the result as a CC BY 4.0 derivative.
2. Decide whether `identifier_conflict` carries a `title_matched` sub-reason (needed for fabrication-only scoring).
3. Re-pin HALLMARK at v1.2.4 or later. The `main` subtests fix and `selective.py` are not released yet.
4. After the first CiteAudit runtime fetch, record its sha256 and inspect `Predict` and its label distribution.
