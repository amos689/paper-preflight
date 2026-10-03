# Architecture Decision Records

Short records of decisions that shape paper-preflight. Each ADR states the context, the
decision and its consequences. Superseded ADRs are kept and marked as such.

| ADR | Title | Status |
|---|---|---|
| [0001](0001-source-first-input.md) | Source-first input; PDF only as a low-confidence fallback | Accepted |
| [0002](0002-verdicts-and-abstention.md) | Verdict taxonomy, abstention and exit codes | Accepted |
| [0003](0003-identifier-first-routing.md) | Identifier-first source routing (S2 off by default) | Accepted (spikes S1–S5) |
| [0004](0004-no-llm-in-verdicts.md) | No LLM in the verdict path | Accepted |
| [0005](0005-http-adapters-and-cache.md) | Own thin HTTP adapters and an application-level SQLite cache | Accepted |
| [0006](0006-license-policy.md) | Dependency and adapted-code license policy | Accepted |
| [0007](0007-sarif-canonical-output.md) | SARIF 2.1.0 as the canonical machine output | Accepted |
| [0008](0008-python-and-tooling.md) | Python ≥ 3.11, uv, hatchling | Accepted |
| [0009](0009-distribution-matrix.md) | One repository, many agent surfaces | Accepted |
| [0010](0010-parsing-stack.md) | Parsing stack: bibtexparser v2 + our own LaTeX tokenizer | Accepted (spikes S6, S7) |

Template: [0000-template.md](0000-template.md).
