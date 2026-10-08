"""Application-level SQLite cache for source responses (ADR-0005).

* Keys are ``(source, normalised request, schema version)``. Credentials (API keys, contact
  emails) are stripped from request keys so they never reach the cache file.
* Entries carry a kind with its own TTL: positive results live long, negative results short
  (indexing lag), retraction status is refreshed weekly. Errors, rate-limit responses and bot
  challenges are never stored — callers simply do not ``put`` them.
* Entries from sources whose data must not be redistributed (Semantic Scholar) are flagged
  ``exportable = False`` and excluded from exports.
* In offline mode callers may read expired ("stale") entries.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any
from urllib.parse import urlencode, urlsplit

CACHE_SCHEMA = 1
DAY = 86_400.0

# Request parameters that identify the caller, not the query: never part of a cache key.
CREDENTIAL_PARAMS = frozenset({"api_key", "apikey", "key", "mailto", "email", "token", "tool"})


class EntryKind(StrEnum):
    POSITIVE = "positive"  # a record was found
    NEGATIVE = "negative"  # the source answered "no such record"
    SEARCH = "search"  # a search result list
    STATUS = "status"  # retraction / correction status
    META = "meta"  # registration-agency lookups and similar slow-changing facts


DEFAULT_TTL: dict[EntryKind, float] = {
    EntryKind.POSITIVE: 60 * DAY,
    EntryKind.NEGATIVE: 2 * DAY,
    EntryKind.SEARCH: 14 * DAY,
    EntryKind.STATUS: 7 * DAY,
    EntryKind.META: 365 * DAY,
}


@dataclass(frozen=True)
class CachedItem:
    payload: Any
    kind: EntryKind
    stored_at: float
    expires_at: float
    exportable: bool

    @property
    def stale(self) -> bool:
        return time.time() >= self.expires_at


def request_key(url: str, params: Mapping[str, Any] | None = None) -> str:
    """Normalise a request into a cache key: host + path + sorted non-credential params."""
    parts = urlsplit(url)
    query_items = [
        (k, str(v))
        for k, v in sorted((params or {}).items())
        if k.lower() not in CREDENTIAL_PARAMS and v is not None
    ]
    query = urlencode(query_items)
    base = f"{parts.netloc.lower()}{parts.path}"
    if parts.query:
        filtered = "&".join(
            q
            for q in sorted(parts.query.split("&"))
            if q.split("=", 1)[0].lower() not in CREDENTIAL_PARAMS
        )
        base += "?" + filtered
        if query:
            base += "&" + query
    elif query:
        base += "?" + query
    return base


class Cache:
    """A small thread-safe SQLite key/value store with per-entry expiry."""

    def __init__(self, path: Path | None) -> None:
        self.path = path
        if path is not None:
            path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(
            str(path) if path is not None else ":memory:", check_same_thread=False
        )
        self._lock = threading.Lock()
        with self._lock:
            if path is not None:
                self._db.execute("PRAGMA journal_mode=WAL")
            self._db.execute(
                """CREATE TABLE IF NOT EXISTS entries (
                    source TEXT NOT NULL,
                    key TEXT NOT NULL,
                    schema INTEGER NOT NULL,
                    kind TEXT NOT NULL,
                    stored_at REAL NOT NULL,
                    expires_at REAL NOT NULL,
                    exportable INTEGER NOT NULL,
                    payload TEXT NOT NULL,
                    PRIMARY KEY (source, key, schema)
                )"""
            )
            self._db.commit()

    def get(self, source: str, key: str, *, allow_stale: bool = False) -> CachedItem | None:
        with self._lock:
            row = self._db.execute(
                "SELECT kind, stored_at, expires_at, exportable, payload FROM entries "
                "WHERE source = ? AND key = ? AND schema = ?",
                (source, key, CACHE_SCHEMA),
            ).fetchone()
        if row is None:
            return None
        item = CachedItem(
            payload=json.loads(row[4]),
            kind=EntryKind(row[0]),
            stored_at=row[1],
            expires_at=row[2],
            exportable=bool(row[3]),
        )
        if item.stale and not allow_stale:
            return None
        return item

    def put(
        self,
        source: str,
        key: str,
        payload: Any,
        kind: EntryKind,
        *,
        ttl: float | None = None,
        exportable: bool = True,
    ) -> None:
        now = time.time()
        expires = now + (ttl if ttl is not None else DEFAULT_TTL[kind])
        data = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        with self._lock:
            self._db.execute(
                "INSERT OR REPLACE INTO entries VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (source, key, CACHE_SCHEMA, kind.value, now, expires, int(exportable), data),
            )
            self._db.commit()

    def delete(self, source: str, key: str) -> None:
        with self._lock:
            self._db.execute(
                "DELETE FROM entries WHERE source = ? AND key = ? AND schema = ?",
                (source, key, CACHE_SCHEMA),
            )
            self._db.commit()

    def invalidate(self, source: str | None = None, kind: EntryKind | None = None) -> int:
        clauses, args = [], []
        if source is not None:
            clauses.append("source = ?")
            args.append(source)
        if kind is not None:
            clauses.append("kind = ?")
            args.append(kind.value)
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        with self._lock:
            cursor = self._db.execute("DELETE FROM entries" + where, args)
            self._db.commit()
        return cursor.rowcount

    def purge_expired(self) -> int:
        with self._lock:
            cursor = self._db.execute("DELETE FROM entries WHERE expires_at <= ?", (time.time(),))
            self._db.commit()
        return cursor.rowcount

    def stats(self) -> dict[str, dict[str, int]]:
        with self._lock:
            rows = self._db.execute(
                "SELECT source, kind, COUNT(*) FROM entries GROUP BY source, kind"
            ).fetchall()
        result: dict[str, dict[str, int]] = {}
        for source, kind, count in rows:
            result.setdefault(source, {})[kind] = count
        return result

    def export(self) -> list[dict[str, Any]]:
        """Exportable entries only (used to build shareable fixtures)."""
        with self._lock:
            rows = self._db.execute(
                "SELECT source, key, kind, payload FROM entries WHERE exportable = 1 "
                "ORDER BY source, key"
            ).fetchall()
        return [
            {"source": s, "key": k, "kind": kind, "payload": json.loads(p)}
            for s, k, kind, p in rows
        ]

    def close(self) -> None:
        with self._lock:
            self._db.close()
