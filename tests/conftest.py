"""Shared fixtures. Tests never touch the network: `check` answers from a recorded web."""

from pathlib import Path

import httpx
import pytest

from paper_preflight import check
from paper_preflight.cli import CREDENTIAL_ENV_VARS
from paper_preflight.sources import base
from paper_preflight.sources.base import SourcePolicy

from .fake_web import FakeWeb


@pytest.fixture(autouse=True)
def recorded_web(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> FakeWeb:
    """Route every `check` run to the recorded web and a per-test cache directory.

    Credentials are cleared so that results never depend on the keys of whoever runs the tests
    (and real keys never reach even the fake web). Tests that need one set it themselves.
    """
    web = FakeWeb()
    monkeypatch.setattr(check, "make_transport", lambda: httpx.MockTransport(web))
    monkeypatch.setenv("PAPER_PREFLIGHT_CACHE_DIR", str(tmp_path / "cache"))
    for name in CREDENTIAL_ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    return web


@pytest.fixture
def fast(monkeypatch: pytest.MonkeyPatch) -> None:
    """No pacing delays: sources still go through their clients, just without sleeping."""

    async def instant(_: float) -> None:
        return None

    monkeypatch.setattr(base.asyncio, "sleep", instant)
    original_init = base.SourceClient.__init__

    def init(
        self: base.SourceClient, policy: SourcePolicy, *args: object, **kwargs: object
    ) -> None:
        policy.min_interval = 0.0
        original_init(self, policy, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(base.SourceClient, "__init__", init)
