# ADR-0010: Parsing stack — bibtexparser v2 + our own LaTeX tokenizer

- Status: Accepted (based on spikes S6 and S7, 2026-10-03)
- Date: 2026-10-03

## Context

Spike S6 (bibtexparser 2.1.0) showed:

- Entries and **fields** expose `start_line` (0-based), and each block keeps its `raw` text — enough
  for SARIF locations and for text-level, format-preserving patches.
- An entry with a duplicate field is moved out of `library.entries` into
  `failed_blocks` (`DuplicateFieldKeyBlock`); duplicate keys become `DuplicateBlockKeyBlock`.
  Both still carry the parsed entry, so we must salvage them instead of silently losing them.
- An unbalanced brace aborts only the broken entry (`ParsingFailedBlock`); later entries parse.
- Comments outside entries survive as `ImplicitComment` blocks with line numbers, so
  `% preflight: ignore[...]` lines can be attached to the following entry.
- `LatexDecodingMiddleware` turns `10.1162/tacl\_a\_00276` into `10.1162/tacl_a_00276`; CRLF input
  parses identically; CJK names split sensibly (`张, 三` → last `张`, first `三`).
- The library logs parse errors to stderr; we must route its logger into our diagnostics.

Spike S7 (tree-sitter-language-pack 1.20.0) showed the LaTeX grammar handles `\citet[p.~3]{…}`,
`\autocite*`, `\input`/`\include`, `%` comments and `\iffalse…\fi` correctly, but:

- grammars are **downloaded from the network on first use** (≈5 s, then cached), which conflicts
  with local-first/offline operation and adds supply-chain surface;
- biblatex multicite (`\cites[..][..]{a}[..][..]{b}`) and user-defined wrappers (`\mycite`) are
  parsed only as generic commands.

## Decision

- `.bib`: bibtexparser `>=2.0,<3`, parsed twice where needed (raw values for patches/identifiers,
  decoded values for matching), salvaging entries from duplicate-field/duplicate-key blocks.
- `.tex`: our own tokenizer (comment and `\iffalse` stripping, include resolution, a configurable
  citation-command table seeded from tree-sitter-latex's MIT grammar, explicit multicite parsing),
  producing file/line/column for every citation site.
- tree-sitter is not a runtime dependency.

## Consequences

- We maintain the tokenizer and its tests (every citation form, nested braces, verbatim
  environments, comments, `\iffalse`, CRLF, non-ASCII paths).
- No network access is needed to parse a project.
