# MCP server

`paper-preflight mcp` runs a [Model Context Protocol](https://modelcontextprotocol.io) server on
stdio, so coding agents can check a paper's references themselves. It needs the `mcp` extra.

Until the first PyPI release, install it from GitHub. Afterwards, `paper-preflight[mcp]` alone
will do.

```bash
uvx --from "paper-preflight[mcp]" paper-preflight mcp
```

## Claude Code plugin

The repository is also a Claude Code plugin marketplace. The plugin bundles this MCP server
(confined to the open project) and a `paper-preflight` skill that tells Claude to run the check
before calling a paper finished, fix what it proves wrong and never invent a reference. It needs
[uv](https://docs.astral.sh/uv/) for `uvx`.

```bash
claude plugin marketplace add amos689/paper-preflight
```

```bash
claude plugin install paper-preflight@paper-preflight
```

Inside Claude Code the same commands are `/plugin marketplace add amos689/paper-preflight` and
`/plugin install paper-preflight@paper-preflight`.

## Tools

| Tool | What it does | Annotations |
|---|---|---|
| `preflight_check` | Verifies every cited reference of a LaTeX project (or a `.bib` file) and checks citation keys. Returns a summary (counts, one verdict per reference, whether the run was complete) and the findings, most severe first, `max_findings` at a time; `next_offset` pages through the rest. Options: `path`, `offline`, `max_findings`, `offset`, `include_info`, `lang` (`en`/`zh`). | read-only, idempotent, open world |
| `preflight_bib_lookup` | Returns a BibTeX entry for a DOI, an arXiv ID or a title, built from the registry record instead of written from memory; lists candidates when a title is ambiguous. A published preprint comes back as its published version with the eprint kept. | read-only, idempotent, open world |
| `preflight_bib_fix` | Proposes edits to the .bib files from the verified records as a unified diff, without writing anything: `level` `safe` (identifier formatting, missing DOIs) or `unsafe` (also authors, title, year, venue, wrong identifiers, a preprint's published version); `keys` limits it to some entries. | read-only, idempotent, open world |
| `preflight_cited_passages` | For each sentence that cites `key`: the claim, and the passages of the cited work (its arXiv source, an open-access full text or PDF, or its abstract) ranked best for it, `max_passages` at a time, for the agent to judge whether the work supports the claim. `name_in_title` tells when a citation set right after a name ("Adam \cite{...}") is named by the work's title. The tool's description asks the agent to confirm only with a quoted passage and never to call a citation wrong. | read-only, idempotent, open world |
| `preflight_explain` | Explains a rule (`REF003`, `CIT001`, ...): what it detects, its severity, its message and whether a fix is safe. | read-only, idempotent |

- **Nothing in the workspace is written.** The only state is the local response cache, shared
  with the CLI, and the cited works' text that `preflight_cited_passages` downloads into it.
- **Paths outside the workspace root are refused.** The root is the directory the server was
  started in, or `--root`.
- **Credentials come from the environment,** exactly as for the CLI: `PAPER_PREFLIGHT_EMAIL`,
  `OPENALEX_API_KEY`, `S2_API_KEY`.
- **The first check of a paper may take a minute** (each source is queried politely). Later
  checks are served from the cache. `offline: true` never touches the network.

## Configuration

Replace the `uvx` arguments with `paper-preflight mcp` if it is installed.

**Claude Code**

```bash
claude mcp add paper-preflight -- uvx --from "paper-preflight[mcp]" paper-preflight mcp
```

**Codex** (`~/.codex/config.toml`)

```toml
[mcp_servers.paper-preflight]
command = "uvx"
args = ["--from", "paper-preflight[mcp]", "paper-preflight", "mcp"]
```

**Cursor** (`.cursor/mcp.json`)

```json
{
  "mcpServers": {
    "paper-preflight": {
      "command": "uvx",
      "args": ["--from", "paper-preflight[mcp]", "paper-preflight", "mcp"]
    }
  }
}
```

**VS Code** (`.vscode/mcp.json`)

```json
{
  "servers": {
    "paper-preflight": {
      "type": "stdio",
      "command": "uvx",
      "args": ["--from", "paper-preflight[mcp]", "paper-preflight", "mcp"]
    }
  }
}
```
