# Third-party notices

paper-preflight adapts ideas, algorithms and test cases from other open-source
projects. Every piece of adapted code is listed here with its original license
and copyright notice, and the corresponding source file carries a short
attribution comment.

Only permissively licensed sources (MIT, BSD, Apache-2.0, ISC) are adapted.
Projects under GPL, AGPL, LPPL, CC BY-NC or without a license are studied for
ideas only; no code is copied from them.

## Adapted code

_None yet._ Entries are added in the same commit that introduces adapted code,
using this format:

```
### <project> (<license>)
Source: <url>@<commit>
Copyright: <copyright line from the original LICENSE>
Used in: src/paper_preflight/<module>.py
What: <one line>
<full license text or SPDX reference + required NOTICE text>
```

## Planned adaptations (not yet included)

| Project | License | Planned use |
|---|---|---|
| gianlucasb/hallucinator (hallucinator-core, MIT option) | AGPL-3.0-or-later OR MIT | Title normalization and matching rules |
| rpatrik96/bibtexupdater | MIT | Verdict semantics, preprint upgrade via Crossref relations |
| Hylouis233/bibverify | MIT | Weighted match assessment, non-destructive merge |
| chrisyangsong/citegate | MIT | Retraction union, CI annotations |
| isaaccorley/skills (bib-audit) | MIT | False-positive regression cases |
| yuchenlin/rebiber | MIT | Digit-preserving title keys |
| markrussinovich/refchecker | MIT | Wrong-paper match guard |
| delip/clibib | MIT | Refuse-to-guess on ambiguous queries |
| acl-org/aclpubcheck | MIT | PDF margin/font checks (v0.2) |
| google-research/arxiv-latex-cleaner | Apache-2.0 | Comment and `\iffalse` stripping semantics |
