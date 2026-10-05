---
name: paper-preflight
description: Verify every reference of a LaTeX paper against real scholarly records (Crossref, dblp, arXiv, DataCite, OpenAlex) before declaring the paper finished or ready to submit, and fix what it reports without inventing anything.
when_to_use: Use before saying a LaTeX paper, thesis or report is done, ready to submit or ready to share; after adding or editing references in a .bib file; or when the user asks whether citations are real, correct or retracted.
license: MIT
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
  (or `uvx paper-preflight check . --format json`; without uv, `pip install paper-preflight`).
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

Safe fixes (identifier formatting, missing DOIs) can be applied with
`paper-preflight bib fix <path> --apply`. For authors, title, year or venue, show the user the
diff from `paper-preflight bib fix <path> --level unsafe` before applying it.

## Does the cited work say it? (when the user asks)

When the user asks whether citations are supported, call `preflight_cited_passages` with a
cited key. For each sentence citing it, the tool returns the claim and the cited work's passages
ranked for that claim. Judge each claim yourself, and report it as one of two things:

- **confirmed**: a passage states the claim; quote the passage word for word. A citation set
  right after a name ("Adam \cite{...}") is also confirmed when `name_in_title` is true.
- **could not confirm**: give the reason. It is that there is no text, that only the abstract
  is available, or that no passage says it.

Never call a citation wrong or invented on this evidence. The text may say it in other words,
or be only an abstract. Without the MCP server, `paper-preflight support` does the same with a
local model (the `support` extra).

## Never

- Never write or complete a BibTeX entry from memory. Get it with the `preflight_bib_lookup`
  MCP tool, or `paper-preflight bib fetch <DOI or arXiv ID>` (or `--title "..." --author "..."`),
  which build the entry from the registry record; if nothing is found, ask the user for the source.
- Never delete a reference the paper relies on without telling the user.
- Never declare the paper clean while errors remain or the run was incomplete
  (`complete: false`, exit code 2); say which sources were unavailable and re-run later.
