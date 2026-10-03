# ADR-0005: Own thin HTTP adapters and an application-level SQLite cache

- Status: Accepted
- Date: 2026-10-03

## Context

Python client libraries for scholarly APIs differ in retry semantics and maintenance status
(pymed archived, unpywall stale, crossrefapi without releases since 2025-07). Sources tightened
their rules in 2025–2026 (Crossref limits per email, OpenAlex per-call billing, dblp bot wall,
arXiv opaque 429s). We need uniform rate limiting, unavailability detection and caching.

## Decision

- One adapter per source (~100–200 lines) on top of `httpx.AsyncClient`, declaring capability
  flags (authoritative identifiers, author-list completeness and ordering, field search support,
  local/remote).
- Per-source limiter driven by response headers where available, a concurrency cap, bounded
  retries with jitter only for idempotent transient errors, and a circuit breaker with cooldown.
- An application-level SQLite cache (not an HTTP cache): key = source + normalized request +
  schema version; tiered TTLs (positive, negative, retraction status); errors/429/challenges are
  never cached; record/replay mode for tests and benchmarks; entries from sources whose data must
  not be redistributed (Semantic Scholar) are marked non-exportable.
- Credentials and contact emails come from environment variables only and are never cached,
  logged or printed. No shared project email is ever shipped.

## Consequences

- We own more code, but the semantics needed for honest abstention live in one place.
- Contract tests per adapter using recorded responses from redistributable sources only.
