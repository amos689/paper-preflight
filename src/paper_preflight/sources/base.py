"""Shared HTTP behaviour for source adapters: pacing, caching and honest unavailability.

A source is *unavailable* when it rate-limits us (429), serves a bot challenge (403
``ChallengeRequired`` or an HTML page where JSON was expected), fails with 5xx, times out, or
cannot be reached. Unavailability is never a negative answer (ADR-0002): callers turn it into
"cannot determine". We never retry aggressively and never try to get around a challenge; the
source simply cools down for the rest of the run.

The cache doubles as a recording: running online with a given cache file records every
response, and running ``offline`` against that file replays them exactly (frozen benchmarks).
"""

from __future__ import annotations

import asyncio
import json
import random
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

import httpx

from paper_preflight import __version__
from paper_preflight.cache import Cache, EntryKind, request_key

USER_AGENT = f"paper-preflight/{__version__} (+https://github.com/amos689/paper-preflight)"


class UnavailableReason(StrEnum):
    OFFLINE = "offline"
    RATE_LIMITED = "rate_limited"
    CHALLENGE = "challenge"
    SERVER_ERROR = "server_error"
    TIMEOUT = "timeout"
    NETWORK = "network"
    FORBIDDEN = "forbidden"
    BUDGET = "budget_exhausted"
    COOLDOWN = "cooldown"
    BAD_RESPONSE = "bad_response"


class SourceUnavailable(Exception):
    def __init__(self, source: str, reason: UnavailableReason, detail: str = "") -> None:
        super().__init__(f"{source} unavailable: {reason.value} {detail}".strip())
        self.source = source
        self.reason = reason
        self.detail = detail


@dataclass
class SourcePolicy:
    name: str
    min_interval: float = 1.0  # seconds between request starts
    max_concurrency: int = 1
    timeout: float = 20.0
    cooldown: float = 600.0  # how long to stop asking after the source became unavailable
    retries: int = 1  # retries for timeouts and 5xx only, with backoff
    # Retries after HTTP 429 with exponential backoff (backoff, 2x, 4x ... or Retry-After if
    # longer). 0 = a 429 makes the source unavailable at once, which suits shared public pools.
    rate_limit_retries: int = 0
    backoff: float = 2.0
    exportable: bool = True  # may cached responses be exported/redistributed?


class _Retry(Exception):
    """Internal: the response asks for another attempt after ``delay`` seconds."""

    def __init__(self, delay: float) -> None:
        super().__init__(delay)
        self.delay = delay


@dataclass
class SourceStats:
    requests: int = 0
    cache_hits: int = 0
    stale_hits: int = 0
    negatives: int = 0
    unavailable: dict[str, int] = field(default_factory=dict)

    def mark_unavailable(self, reason: UnavailableReason) -> None:
        self.unavailable[reason.value] = self.unavailable.get(reason.value, 0) + 1


@dataclass(frozen=True)
class Fetched:
    """A JSON response (``data``) or a definite negative answer (``data is None``)."""

    data: Any
    status: int
    from_cache: bool


Classifier = Callable[[Any], EntryKind]

# Marker stored in the cache for "the source answered with a negative HTTP status" (e.g. 404).
_NEGATIVE_STATUS = "__negative_status__"


class SourceClient:
    def __init__(
        self,
        policy: SourcePolicy,
        http: httpx.AsyncClient,
        cache: Cache,
        *,
        offline: bool = False,
    ) -> None:
        self.policy = policy
        self.http = http
        self.cache = cache
        self.offline = offline
        self.stats = SourceStats()
        self._semaphore = asyncio.Semaphore(policy.max_concurrency)
        self._pace_lock = asyncio.Lock()
        self._next_start = 0.0
        self._cooldown_until = 0.0
        self._cooldown_reason = UnavailableReason.COOLDOWN

    @property
    def name(self) -> str:
        return self.policy.name

    def slow_down(self, min_interval: float) -> None:
        """Adapters call this when response headers announce a stricter limit."""
        self.policy.min_interval = max(self.policy.min_interval, min_interval)

    def _unavailable(
        self, reason: UnavailableReason, detail: str = "", cool: float | None = None
    ) -> SourceUnavailable:
        """Record unavailability and start a cooldown (except for offline mode)."""
        self.stats.mark_unavailable(reason)
        if reason is not UnavailableReason.OFFLINE:
            duration = cool if cool is not None else self.policy.cooldown
            self._cooldown_until = max(self._cooldown_until, time.monotonic() + duration)
            self._cooldown_reason = reason
        return SourceUnavailable(self.name, reason, detail)

    def _cooling_down(self) -> SourceUnavailable:
        """Refuse a request during cooldown, reporting the reason the cooldown started."""
        self.stats.mark_unavailable(UnavailableReason.COOLDOWN)
        return SourceUnavailable(self.name, self._cooldown_reason, "cooling down")

    async def _pace(self) -> None:
        async with self._pace_lock:
            now = time.monotonic()
            wait = self._next_start - now
            if wait > 0:
                await asyncio.sleep(wait)
            jitter = random.uniform(0, 0.1 * self.policy.min_interval)
            self._next_start = max(now, self._next_start) + self.policy.min_interval + jitter

    async def get_json(
        self,
        url: str,
        *,
        params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
        classify: Classifier = lambda _: EntryKind.POSITIVE,
        negative_statuses: tuple[int, ...] = (404,),
        cache_key: str | None = None,
    ) -> Fetched:
        """GET a JSON document (``data`` is the decoded JSON)."""
        return await self._get(
            url, params, headers, classify, negative_statuses, cache_key, expect_json=True
        )

    async def get_text(
        self,
        url: str,
        *,
        params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
        classify: Classifier = lambda _: EntryKind.POSITIVE,
        negative_statuses: tuple[int, ...] = (404,),
        cache_key: str | None = None,
    ) -> Fetched:
        """GET a non-JSON document such as an Atom feed (``data`` is the text)."""
        return await self._get(
            url, params, headers, classify, negative_statuses, cache_key, expect_json=False
        )

    async def _get(
        self,
        url: str,
        params: Mapping[str, Any] | None,
        headers: Mapping[str, str] | None,
        classify: Classifier,
        negative_statuses: tuple[int, ...],
        cache_key: str | None,
        *,
        expect_json: bool,
    ) -> Fetched:
        key = cache_key or request_key(url, params)
        cached = self.cache.get(self.name, key, allow_stale=self.offline)
        if cached is not None:
            if cached.stale:
                self.stats.stale_hits += 1
            else:
                self.stats.cache_hits += 1
            payload = cached.payload
            if isinstance(payload, dict) and _NEGATIVE_STATUS in payload:
                return Fetched(None, int(payload[_NEGATIVE_STATUS]), True)
            return Fetched(payload, 200, True)
        if self.offline:
            raise self._unavailable(UnavailableReason.OFFLINE)
        if time.monotonic() < self._cooldown_until:
            raise self._cooling_down()

        accept = "application/json" if expect_json else "application/atom+xml, application/xml"
        merged_headers = {"User-Agent": USER_AGENT, "Accept": accept}
        merged_headers.update(headers or {})
        attempt = 0  # timeouts and 5xx
        rate_limited = 0  # 429s
        while True:
            async with self._semaphore:
                await self._pace()
                self.stats.requests += 1
                try:
                    response = await self.http.get(
                        url, params=params, headers=merged_headers, timeout=self.policy.timeout
                    )
                except httpx.TimeoutException as exc:
                    timeout_error = self._retryable(UnavailableReason.TIMEOUT, str(exc), attempt)
                    if timeout_error is not None:
                        raise timeout_error from exc
                    attempt += 1
                    await asyncio.sleep(2.0 * attempt)
                    continue
                except httpx.HTTPError as exc:
                    raise self._unavailable(UnavailableReason.NETWORK, type(exc).__name__) from exc
            try:
                return self._interpret(
                    response, key, classify, negative_statuses, attempt, rate_limited, expect_json
                )
            except _Retry as retry:
                if response.status_code == 429:
                    rate_limited += 1
                else:
                    attempt += 1
                await asyncio.sleep(retry.delay)

    def _retryable(
        self, reason: UnavailableReason, detail: str, attempt: int
    ) -> SourceUnavailable | None:
        if attempt >= self.policy.retries:
            return self._unavailable(reason, detail)
        return None

    def _interpret(
        self,
        response: httpx.Response,
        key: str,
        classify: Classifier,
        negative_statuses: tuple[int, ...],
        attempt: int,
        rate_limited: int = 0,
        expect_json: bool = True,
    ) -> Fetched:
        """Turn a response into data, a negative, a retry (:class:`_Retry`) or unavailability."""
        status = response.status_code
        content_type = response.headers.get("content-type", "").lower()
        looks_html = "html" in content_type or response.text.lstrip()[:15].lower().startswith(
            ("<!doctype", "<html")
        )
        if status == 429:
            retry_after = _retry_after_seconds(response)
            if rate_limited < self.policy.rate_limit_retries:
                backoff = self.policy.backoff * 2**rate_limited
                delay = max(backoff, retry_after or 0.0)
                raise _Retry(delay + random.uniform(0, 0.25 * delay))
            raise self._unavailable(UnavailableReason.RATE_LIMITED, "HTTP 429", retry_after)
        if status == 403:
            body = response.text[:2000]
            if looks_html or "challenge" in body.lower():
                raise self._unavailable(UnavailableReason.CHALLENGE, "HTTP 403")
            raise self._unavailable(UnavailableReason.FORBIDDEN, "HTTP 403")
        if status in negative_statuses:
            self.stats.negatives += 1
            self.cache.put(
                self.name, key, {_NEGATIVE_STATUS: status}, EntryKind.NEGATIVE,
                exportable=self.policy.exportable,
            )  # fmt: skip
            return Fetched(None, status, False)
        if status >= 500:
            error = self._retryable(UnavailableReason.SERVER_ERROR, f"HTTP {status}", attempt)
            if error is not None:
                raise error
            raise _Retry(2.0 * (attempt + 1))
        if status != 200:
            raise self._unavailable(UnavailableReason.BAD_RESPONSE, f"HTTP {status}")
        if looks_html:
            # Bot walls such as Anubis answer 200 with an HTML page: not data, not a negative.
            raise self._unavailable(UnavailableReason.CHALLENGE, "HTML instead of JSON")
        data: Any
        if expect_json:
            try:
                data = response.json()
            except (json.JSONDecodeError, ValueError) as exc:
                raise self._unavailable(UnavailableReason.BAD_RESPONSE, "invalid JSON") from exc
        else:
            data = response.text
        kind = classify(data)
        self.cache.put(self.name, key, data, kind, exportable=self.policy.exportable)
        if kind is EntryKind.NEGATIVE:
            self.stats.negatives += 1
        return Fetched(data, 200, False)


def _retry_after_seconds(response: httpx.Response) -> float | None:
    value = response.headers.get("retry-after")
    if value is None:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        return None
