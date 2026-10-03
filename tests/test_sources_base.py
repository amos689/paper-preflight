from collections.abc import AsyncIterator

import httpx
import pytest
import respx

from paper_preflight.cache import Cache, EntryKind
from paper_preflight.sources import base
from paper_preflight.sources.base import (
    SourceClient,
    SourcePolicy,
    SourceUnavailable,
    UnavailableReason,
)

URL = "https://api.example.org/works"


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    async def instant(_: float) -> None:
        return None

    monkeypatch.setattr(base.asyncio, "sleep", instant)


@pytest.fixture
async def http() -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient() as client:
        yield client


def make(http: httpx.AsyncClient, cache: Cache | None = None, **kwargs: object) -> SourceClient:
    policy = SourcePolicy(name="example", min_interval=0.0, **kwargs)  # type: ignore[arg-type]
    return SourceClient(policy, http, cache or Cache(None))


@pytest.mark.anyio
@respx.mock
async def test_json_is_cached_and_credentials_do_not_matter(http: httpx.AsyncClient) -> None:
    route = respx.get(URL).mock(return_value=httpx.Response(200, json={"title": "T"}))
    client = make(http)
    first = await client.get_json(URL, params={"q": "x", "mailto": "a@b.c"})
    second = await client.get_json(URL, params={"q": "x", "mailto": "other@b.c"})
    assert first.data == second.data == {"title": "T"}
    assert (first.from_cache, second.from_cache) == (False, True)
    assert route.call_count == 1
    assert client.stats.requests == 1
    assert client.stats.cache_hits == 1


@pytest.mark.anyio
@respx.mock
async def test_404_is_a_cached_negative(http: httpx.AsyncClient) -> None:
    respx.get(URL).mock(return_value=httpx.Response(404, json={"message": "not found"}))
    client = make(http)
    result = await client.get_json(URL)
    assert result.data is None
    assert result.status == 404
    again = await client.get_json(URL)
    assert again.from_cache
    assert again.data is None


@pytest.mark.anyio
@respx.mock
async def test_classified_negative_keeps_its_payload_in_cache(http: httpx.AsyncClient) -> None:
    respx.get(URL).mock(return_value=httpx.Response(200, json={"items": []}))
    client = make(http)

    def classify(data: object) -> EntryKind:
        return EntryKind.NEGATIVE if not data["items"] else EntryKind.SEARCH  # type: ignore[index]

    first = await client.get_json(URL, classify=classify)
    second = await client.get_json(URL, classify=classify)
    assert first.data == second.data == {"items": []}
    assert client.stats.negatives == 1


@pytest.mark.anyio
@respx.mock
async def test_rate_limit_makes_source_unavailable_then_cooldown(http: httpx.AsyncClient) -> None:
    route = respx.get(URL).mock(
        return_value=httpx.Response(429, headers={"retry-after": "30"}, text="Rate exceeded.")
    )
    client = make(http)
    with pytest.raises(SourceUnavailable) as first:
        await client.get_json(URL)
    assert first.value.reason is UnavailableReason.RATE_LIMITED
    for attempt in range(3):
        with pytest.raises(SourceUnavailable) as later:
            await client.get_json(URL, params={"other": attempt})
        # the original reason is kept, so reports say *why* the source is unavailable
        assert later.value.reason is UnavailableReason.RATE_LIMITED
        assert later.value.detail == "cooling down"
    assert route.call_count == 1  # no hammering during cooldown, however many calls follow
    assert client.stats.unavailable == {"rate_limited": 1, "cooldown": 3}


@pytest.mark.anyio
@respx.mock
async def test_html_with_200_is_a_bot_challenge_not_a_negative(http: httpx.AsyncClient) -> None:
    respx.get(URL).mock(
        return_value=httpx.Response(
            200, text="<!doctype html><title>Making sure you're not a bot!</title>",
            headers={"content-type": "text/html"},
        )
    )  # fmt: skip
    cache = Cache(None)
    client = make(http, cache)
    with pytest.raises(SourceUnavailable) as caught:
        await client.get_json(URL)
    assert caught.value.reason is UnavailableReason.CHALLENGE
    assert cache.stats() == {}  # challenges are never cached


@pytest.mark.anyio
@respx.mock
async def test_403_challenge(http: httpx.AsyncClient) -> None:
    respx.get(URL).mock(return_value=httpx.Response(403, json={"name": "ChallengeRequiredError"}))
    with pytest.raises(SourceUnavailable) as caught:
        await make(http).get_json(URL)
    assert caught.value.reason is UnavailableReason.CHALLENGE


@pytest.fixture
def delays(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    recorded: list[float] = []

    async def record(delay: float) -> None:
        recorded.append(delay)

    monkeypatch.setattr(base.asyncio, "sleep", record)
    return recorded


@pytest.mark.anyio
@respx.mock
async def test_rate_limit_retries_back_off_exponentially(
    http: httpx.AsyncClient, delays: list[float]
) -> None:
    route = respx.get(URL).mock(
        side_effect=[httpx.Response(429), httpx.Response(429), httpx.Response(200, json={"a": 1})]
    )
    result = await make(http, rate_limit_retries=3, backoff=2.0).get_json(URL)
    assert result.data == {"a": 1}
    assert route.call_count == 3
    assert len(delays) == 2
    assert 2.0 <= delays[0] <= 2.5  # backoff, plus up to 25% jitter
    assert 4.0 <= delays[1] <= 5.0  # doubled


@pytest.mark.anyio
@respx.mock
async def test_rate_limit_backoff_honours_a_longer_retry_after(
    http: httpx.AsyncClient, delays: list[float]
) -> None:
    respx.get(URL).mock(
        side_effect=[
            httpx.Response(429, headers={"retry-after": "10"}),
            httpx.Response(200, json={"a": 1}),
        ]
    )
    await make(http, rate_limit_retries=1).get_json(URL)
    assert delays[0] >= 10.0


@pytest.mark.anyio
@respx.mock
async def test_rate_limit_retries_run_out(http: httpx.AsyncClient, delays: list[float]) -> None:
    route = respx.get(URL).mock(return_value=httpx.Response(429))
    with pytest.raises(SourceUnavailable) as caught:
        await make(http, rate_limit_retries=2).get_json(URL)
    assert caught.value.reason is UnavailableReason.RATE_LIMITED
    assert route.call_count == 3  # the first try and two retries, then the source cools down


@pytest.mark.anyio
@respx.mock
async def test_server_error_is_retried_once(http: httpx.AsyncClient) -> None:
    route = respx.get(URL).mock(
        side_effect=[httpx.Response(503), httpx.Response(200, json={"ok": True})]
    )
    result = await make(http).get_json(URL)
    assert result.data == {"ok": True}
    assert route.call_count == 2


@pytest.mark.anyio
@respx.mock
async def test_timeouts_exhaust_retries(http: httpx.AsyncClient) -> None:
    respx.get(URL).mock(side_effect=httpx.ReadTimeout("slow"))
    with pytest.raises(SourceUnavailable) as caught:
        await make(http).get_json(URL)
    assert caught.value.reason is UnavailableReason.TIMEOUT


@pytest.mark.anyio
@respx.mock
async def test_offline_mode_replays_cache_including_stale(http: httpx.AsyncClient) -> None:
    cache = Cache(None)
    cache.put("example", "api.example.org/works", {"t": 1}, EntryKind.POSITIVE, ttl=-1)
    policy = SourcePolicy(name="example", min_interval=0.0)
    client = SourceClient(policy, http, cache, offline=True)
    result = await client.get_json(URL)
    assert result.data == {"t": 1}
    assert client.stats.stale_hits == 1
    with pytest.raises(SourceUnavailable) as caught:
        await client.get_json(URL, params={"missing": 1})
    assert caught.value.reason is UnavailableReason.OFFLINE


@pytest.mark.anyio
@respx.mock
async def test_non_exportable_policy_marks_cache_entries(http: httpx.AsyncClient) -> None:
    respx.get(URL).mock(return_value=httpx.Response(200, json={"x": 1}))
    cache = Cache(None)
    await make(http, cache, exportable=False).get_json(URL)
    assert cache.export() == []
