# Inputs

`paper-preflight check <path>` takes a manuscript, a bibliography on its own, a PDF or an arXiv
paper. Manuscripts get the full check: citation keys against the bibliography (CIT rules) and
every cited reference against the scholarly records (REF rules). A bibliography on its own gets
the reference checks, for all of its entries.

Files read from a compiled or formatted form (`.bbl`, Word, plain text, PDF) are marked
*derived*: they are checked, but `bib fix` never edits them.

## LaTeX projects

```bash
paper-preflight check paper/            # the project folder
paper-preflight check paper/main.tex    # or its main file
```

- **The main file** is the `.tex` file with `\documentclass` and `\begin{document}` (a
  `subfiles` child does not count). When there are several, `main.tex`, `paper.tex`, `ms.tex` or
  `thesis.tex` is taken; otherwise name it with `--main`.
- **Included files** are followed through `\input`, `\include` and `\subfile`, as LaTeX sees
  them: comments, `\iffalse ... \fi` blocks and `\includeonly` are respected. A missing file is
  TEX001, a cycle TEX002.
- **Bibliographies** come from `\bibliography{...}` and `\addbibresource{...}`; `--bib` adds
  others. A remote `\addbibresource[location=remote]` is not downloaded (TEX003).
- **Citation commands** of natbib, biblatex (with `\cites` and `\volcite`), apacite, the
  harvard and chicago styles and bibentry are known. `--cite-command mycite` adds your own.
- **Build files.** After a compilation, the `.aux` (BibTeX) or `.bcf` (biblatex) lists exactly
  which keys were cited, including through macros a static reading cannot follow. When it is
  newer than every source file, it decides which keys count as cited.
- **No `.bib`?** A project that ships only its compiled `.bbl`, as many arXiv sources do, is
  read from it: biblatex's `\entry` records, `\bibinfo` tags (elsarticle, revtex) and BibTeX's
  `\bibitem` lists.

## Word, Markdown, Quarto, R Markdown and Typst

```bash
paper-preflight check paper.docx
paper-preflight check paper.qmd     # also .md and .Rmd
paper-preflight check paper.typ
```

- **Word (`.docx`).** References are taken from the first of: the citations Zotero, Mendeley or
  EndNote wrote into the text (field codes, with the reference manager's exact fields and
  identifiers); Word's own source manager; the reference list as typed, in Word's
  "Bibliography" style or after a "References" heading. Positions are paragraph numbers.
- **Markdown, Quarto and R Markdown.** Pandoc's `[@key]` and `@key` citations, checked against
  the files named by `bibliography:` in the YAML front matter or in `_quarto.yml`.
- **Typst.** `@key` and `#cite(<key>)`, checked against `#bibliography("refs.bib")` (BibTeX or
  Hayagriva YAML).

## A bibliography on its own

```bash
paper-preflight check refs.bib
paper-preflight check library.json   # CSL-JSON, as Zotero exports it
paper-preflight check export.ris     # RIS
paper-preflight check refs.yml       # Hayagriva or CSL YAML
paper-preflight check main.bbl
```

Every entry is checked, cited or not.

## Plain text

```bash
paper-preflight check references.txt
pbpaste | paper-preflight check -
```

A reference list pasted from a PDF, a web page or a document: one reference per line, per
paragraph or numbered (`[1]`, `1.`). The common styles are read: APA, IEEE, ACM, ACL, Chicago,
MLA, Nature, Vancouver, Springer LNCS, Elsevier, MDPI, GOST and natbib's. Each reference
becomes an entry keyed `ref1`, `ref2`, .... Reading a formatted reference is guesswork where
BibTeX is not: a reference whose title or authors cannot be told apart is checked by its
identifiers, or reported as "cannot determine".

## PDF

```bash
uvx --from 'paper-preflight[pdf]' paper-preflight check paper.pdf
```

The text of the PDF's reference section is read as plain text, with the `pdf` extra. A scanned
PDF (images, no text layer) has nothing to read.

## An arXiv paper

```bash
paper-preflight check arxiv:2607.06922
```

The paper's source is downloaded from arXiv to a temporary folder, checked as a LaTeX project
and deleted. A paper submitted as a PDF only is read as a PDF (with the `pdf` extra).

## Languages of the references

Titles in Latin script are checked in any language. Titles in other scripts (Chinese,
Japanese, Cyrillic, ...) are reported as "cannot determine" for now, and a Chinese-language work
cited by a translated English title too, since the open indexes rarely hold the translation.
