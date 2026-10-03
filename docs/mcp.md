# MCP server

`paper-preflight mcp` runs a [Model Context Protocol](https://modelcontextprotocol.io) server on
stdio, so coding agents can check a paper's references themselves. It needs the `mcp` extra.

Until the first PyPI release, install it from GitHub. Afterwards, `paper-preflight[mcp]` alone
will do.

```bash
uvx --from "paper-preflight[mcp] @ git+https://github.com/amos689/paper-preflight" paper-preflight mcp
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
| `preflight_explain` | Explains a rule (`REF003`, `CIT001`, ...): what it detects, its severity, its message and whether a fix is safe. | read-only, idempotent |

- **Nothing in the workspace is written.** The only state is the local response cache, shared
  with the CLI.
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
claude mcp add paper-preflight -- uvx --from "paper-preflight[mcp] @ git+https://github.com/amos689/paper-preflight" paper-preflight mcp
```

**Codex** (`~/.codex/config.toml`)

```toml
[mcp_servers.paper-preflight]
command = "uvx"
args = ["--from", "paper-preflight[mcp] @ git+https://github.com/amos689/paper-preflight", "paper-preflight", "mcp"]
```

**Cursor** (`.cursor/mcp.json`)

```json
{
  "mcpServers": {
    "paper-preflight": {
      "command": "uvx",
      "args": ["--from", "paper-preflight[mcp] @ git+https://github.com/amos689/paper-preflight", "paper-preflight", "mcp"]
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
      "args": ["--from", "paper-preflight[mcp] @ git+https://github.com/amos689/paper-preflight", "paper-preflight", "mcp"]
    }
  }
}
```
