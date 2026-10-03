---
name: paper-preflight
description: Verify every reference of a LaTeX paper against real scholarly records (Crossref, dblp, arXiv, DataCite, OpenAlex) before declaring the paper finished or ready to submit, and fix what it reports without inventing anything.
when_to_use: Use before saying a LaTeX paper, thesis or report is done, ready to submit or ready to share; after adding or editing references in a .bib file; or when the user asks whether citations are real, correct or retracted.
---

# Check a paper's references before calling it done

paper-preflight checks citation keys and verifies each cited reference against real records. It
never uses an LLM to judge, and it abstains ("cannot determine") rather than guess. Your job is
to run it, fix what it proves wrong, and hand the user what only they can decide.

## Run the check

- If the `preflight_check` MCP tool is available, call it with the project directory (or the
  `.bib` file) as `path`. Page with `offset=next_offset` until `next_offset` is null.
- Otherwise run the CLI from the project root:
  `paper-preflight check . --format json`
  (or `uvx --from "paper-preflight @ git+https://github.com/amos689/paper-preflight" paper-preflight check . --format json`).
- Exit codes: 0 clean, 1 blocking findings, 2 incomplete run (a source was unavailable),
  3 usage error. `preflight_explain` (or the rule table in the output) explains any rule ID.

## Act on the findings

Fix errors first, then warnings. Re-run the check after editing.

| Rule | What to do |
|---|---|
| CIT001 undefined key | Find the intended entry in the .bib files; if it does not exist, ask the user for the source. |
| CIT002 duplicate key, CIT004 near-duplicate | Merge into one entry and update the citations. |
| REF001 identifier points to another work | Remove the wrong DOI/arXiv ID. Add the right one only if you can verify it. |
| REF002 identifier does not exist | Remove it or correct an obvious typo; never guess a replacement. |
| REF003 not found anywhere | **Do not invent or "repair" the entry.** Tell the user it was not found in any source and ask for the actual paper (a link, a PDF or a DOI). |
| REF004 retracted | Tell the user. Keep the citation only if the text discusses the retraction. |
| REF010–REF014 authors, title, year or venue differ | Correct the field from the record named in the message. |
| REF015 preprint was published | Suggest citing the published version, keeping the `eprint` field. |
| REF017 identifier written incorrectly | Apply the suggested form; it is a safe fix. |
| REF090 cannot determine | Do not guess. List these references for the user to confirm by hand, with the reason given. |

## Never

- Never write or complete a BibTeX entry from memory. Get it with
  `paper-preflight bib fetch <DOI or arXiv ID>` (or `--title "..." --author "..."`), which prints
  an entry built from the registry record; if it finds nothing, ask the user for the source.
- Never delete a reference the paper relies on without telling the user.
- Never declare the paper clean while errors remain or the run was incomplete
  (`complete: false`, exit code 2); say which sources were unavailable and re-run later.
