# Plain-text references: Badalova & Mayr (2026)

- **Tool:** paper-preflight 0.6.0
- **Data:** the 104 references of Badalova & Mayr's dataset as formatted strings (APA, biblatex, natbib author-year; Zenodo 10.5281/zenodo.21457492, CC BY 4.0), read by `check references.txt`, against the hand transcription `evals/badalova_mayr.bib`
- **Run:** 2026-10-08 (`evals/plaintext_badalova.py`)

| Document (style) | References | Title | First author | Year | DOI or arXiv ID |
|---|---|---|---|---|---|
| P1 (APA) | 24 | 24/24 | 24/24 | 24/24 | 11/11 |
| P2 (biblatex) | 15 | 15/15 | 14/15 | 15/15 | 13/13 |
| P3 (natbib author-year) | 65 | 65/65 | 65/65 | 65/65 | 24/24 |
| **All** | 104 | 104/104 | 103/104 | 104/104 | 48/48 |

Read differently from the transcription:

- P2R13: first author

P2R13 (and P3R29 below) lose letters the CSV dropped ("Micha? Marci?czuk", "Kamile? Luko?iut?e"), which the transcription restores from the documents.

## Verified both ways

Flagged (a warning or an error) or not, the same for 102 of 104 references read from the text and from the transcription.

- P2R13: text ['REF011'], transcription clean
- P3R29: text ['REF011'], transcription clean
