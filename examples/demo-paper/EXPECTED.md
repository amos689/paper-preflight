# Expected findings for the demo paper

This table is the acceptance target for the end-to-end tests. "Offline" rows are detected without
network access; "online" rows need reference verification (milestones W2–W3).
`paper-preflight check examples/demo-paper` verifies the references online (`--offline` answers
from the cache only). `tests/test_verdict.py` and `tests/test_check_online.py` run the demo
against recorded responses. A live run on 2026-10-03 matched every row, except that arXiv was
refusing requests at the time, so `hendrycks2016gelu` came out as "cannot determine" (RUN001);
since then arXiv IDs fall back to DataCite (`10.48550/arXiv.<id>`) when that happens.

| Key | Planted problem | Expected rule | Mode | Status |
|---|---|---|---|---|
| `nonexistent2023` | cited but missing from refs.bib | CIT001 error | offline | ✅ |
| `kingma2015adam` (2nd) | duplicate key | CIT002 error | offline | ✅ |
| `lecun1998gradient` | never cited | CIT003 info | offline | ✅ |
| `devlin2019bert` | shares its DOI with `he2016deep` | CIT004 warning | offline | ✅ |
| `commented_out_key`, `inside_iffalse_key` | commented out / inside `\iffalse` | no finding | offline | ✅ |
| `tacl2019example` | DOI written with LaTeX escapes (`\_`) | REF017 warning (safe fix) | offline | ✅ |
| `devlin2019bert` | DOI belongs to the ResNet paper | REF001 error | online | ✅ |
| `kingma2015adam` | year 2016, published 2015 | REF013 warning | online | ✅ |
| `he2015residual` | arXiv preprint published at CVPR 2016 | REF015 warning | online | ✅ |
| `lindqvist2024quantum` | fabricated, fictional authors | REF003 error | online | ✅ |
| `wakefield1998ileal` | retracted (2010) | REF004 error | online | ✅ |
| `goodfellow2016deep` | book without identifiers | REF090 info (`GREY_LITERATURE`) | online | ✅ |
| `zhou2016ml` | Chinese book without identifiers | REF090 info (`NON_LATIN_UNSUPPORTED`) | online | ✅ |
| `vaswani2017attention` | correct; no Crossref DOI exists, fake 10.65215 copies do | verified, no finding | online | ✅ |
| `he2016deep` | correct | verified, no finding | online | ✅ |
| `hendrycks2016gelu` | correct; title changed between arXiv versions | verified, no finding | online | ✅ |
| `tacl2019example` | otherwise correct (authors end with "and others") | no metadata finding | online | ✅ |
