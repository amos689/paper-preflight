# Expected findings for the demo paper

This table is the acceptance target for the end-to-end tests. "Offline" rows are detected without
network access; "online" rows need reference verification (milestones W2–W3).
"✅ engine" means the verdict engine produces the finding (`tests/test_verdict.py` runs the demo
against recorded responses); `paper-preflight check` does not run online verification yet.

| Key | Planted problem | Expected rule | Mode | Status |
|---|---|---|---|---|
| `nonexistent2023` | cited but missing from refs.bib | CIT001 error | offline | ✅ |
| `kingma2015adam` (2nd) | duplicate key | CIT002 error | offline | ✅ |
| `lecun1998gradient` | never cited | CIT003 info | offline | ✅ |
| `devlin2019bert` | shares its DOI with `he2016deep` | CIT004 warning | offline | ✅ |
| `commented_out_key`, `inside_iffalse_key` | commented out / inside `\iffalse` | no finding | offline | ✅ |
| `tacl2019example` | DOI written with LaTeX escapes (`\_`) | REF017 warning (safe fix) | offline | ✅ |
| `devlin2019bert` | DOI belongs to the ResNet paper | REF001 error | online | ✅ engine |
| `kingma2015adam` | year 2016, published 2015 | REF013 warning | online | ✅ engine |
| `he2015residual` | arXiv preprint published at CVPR 2016 | REF015 warning | online | ✅ engine |
| `lindqvist2024quantum` | fabricated, fictional authors | REF003 error | online | ✅ engine |
| `wakefield1998ileal` | retracted (2010) | REF004 error | online | ✅ engine |
| `goodfellow2016deep` | book without identifiers | REF090 info (`GREY_LITERATURE`) | online | ✅ engine |
| `zhou2016ml` | Chinese book without identifiers | REF090 info (`NON_LATIN_UNSUPPORTED`) | online | ✅ engine |
| `vaswani2017attention` | correct; no Crossref DOI exists, fake 10.65215 copies do | verified, no finding | online | ✅ engine |
| `he2016deep` | correct | verified, no finding | online | ✅ engine |
| `hendrycks2016gelu` | correct; title changed between arXiv versions | verified, no finding | online | ✅ engine |
| `tacl2019example` | otherwise correct (authors end with "and others") | no metadata finding | online | ✅ engine |
