# ADR-0006: Dependency and adapted-code license policy

- Status: Accepted
- Date: 2026-10-03

## Context

The project is MIT-licensed. Several relevant tools are AGPL (PyMuPDF, most of hallucinator),
GPL (latexmk, chktex, pandoc, texlab), LPPL (TeX styles), CC BY-NC (academic-research-skills,
some models) or unlicensed (CiteAudit, SemanticCite, Paper-BibChecker).

## Decision

- Runtime dependencies of the core and default extras: MIT, BSD, Apache-2.0, ISC, MPL-2.0, PSF
  only. Enforced in CI (`pip-licenses`).
- AGPL code (PyMuPDF) may only appear as a user-installed optional extra that the core never
  imports by default.
- GPL/LGPL tools run only as external processes found on the user's machine; never linked or
  bundled. LPPL styles are only used through the user's own TeX installation.
- Code is adapted only from permissively licensed projects and recorded in
  `THIRD_PARTY_NOTICES.md` in the same commit, with an attribution comment in the source file.
- Unlicensed, CC BY-NC or copyleft projects are studied for ideas only.
- Datasets: redistributable ones are pinned by hash; others are downloaded at runtime only.

## Consequences

- PDF forensics (v0.2) must be built on pdfminer.six/pdfplumber, pypdf, pikepdf and pypdfium2.
- Some convenient libraries (e.g. Unidecode, GPL) are off-limits; we write small replacements.
