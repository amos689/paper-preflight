import time
from pathlib import Path

import pytest

from paper_preflight.cache import Cache, EntryKind, request_key


def test_request_key_strips_credentials_and_sorts() -> None:
    a = request_key(
        "https://api.crossref.org/works", {"query": "attention", "mailto": "me@x.org", "rows": 5}
    )
    b = request_key("https://API.crossref.org/works", {"rows": 5, "query": "attention"})
    assert a == b == "api.crossref.org/works?query=attention&rows=5"
    c = request_key("https://api.openalex.org/works?filter=doi:10.1/x&api_key=SECRET")
    assert "SECRET" not in c
    assert c == "api.openalex.org/works?filter=doi:10.1/x"


def test_put_get_and_expiry(tmp_path: Path) -> None:
    cache = Cache(tmp_path / "c.sqlite3")
    cache.put("crossref", "k1", {"title": "机器学习"}, EntryKind.POSITIVE)
    item = cache.get("crossref", "k1")
    assert item is not None
    assert item.payload == {"title": "机器学习"}
    assert item.kind is EntryKind.POSITIVE
    cache.put("crossref", "k2", {"found": False}, EntryKind.NEGATIVE, ttl=-1)
    assert cache.get("crossref", "k2") is None
    stale = cache.get("crossref", "k2", allow_stale=True)
    assert stale is not None
    assert stale.stale
    assert cache.purge_expired() == 1
    cache.close()


def test_persistence_and_stats(tmp_path: Path) -> None:
    path = tmp_path / "sub" / "c.sqlite3"
    cache = Cache(path)
    cache.put("openalex", "a", 1, EntryKind.POSITIVE)
    cache.put("openalex", "b", 2, EntryKind.SEARCH)
    cache.put("s2", "c", 3, EntryKind.POSITIVE, exportable=False)
    cache.close()
    reopened = Cache(path)
    assert reopened.stats() == {"openalex": {"positive": 1, "search": 1}, "s2": {"positive": 1}}
    exported = reopened.export()
    assert {e["source"] for e in exported} == {"openalex"}  # S2 data is never exported
    assert reopened.invalidate(source="openalex", kind=EntryKind.SEARCH) == 1
    reopened.close()


@pytest.mark.parametrize("kind", list(EntryKind))
def test_default_ttls_are_positive(kind: EntryKind) -> None:
    cache = Cache(None)
    before = time.time()
    cache.put("x", "k", None, kind)
    item = cache.get("x", "k")
    assert item is not None
    assert item.expires_at > before
