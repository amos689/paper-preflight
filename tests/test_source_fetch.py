"""Adapter fetch functions against mocked HTTP (no network)."""

import json
from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest
import respx

from paper_preflight.cache import Cache
from paper_preflight.sources import arxiv, base, crossref, dblp, doiorg, openalex
from paper_preflight.sources.base import SourceClient, SourcePolicy

FIXTURES = Path(__file__).parent / "fixtures" / "sources"


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


def client_for(policy: SourcePolicy, http: httpx.AsyncClient, cache: Cache) -> SourceClient:
    return SourceClient(SourcePolicy(name=policy.name, min_interval=0.0), http, cache)


@pytest.mark.anyio
@respx.mock
async def test_crossref_batches_and_mailto_not_in_cache(http: httpx.AsyncClient) -> None:
    payload = json.loads((FIXTURES / "crossref/batch_filter_doi.json").read_text(encoding="utf-8"))
    route = respx.get(crossref.WORKS_URL).mock(return_value=httpx.Response(200, json=payload))
    cache = Cache(None)
    client = client_for(crossref.POLICY, http, cache)
    dois = [f"10.1/x{i}" for i in range(25)] + ["10.1109/CVPR.2016.90"]
    found = await crossref.works_by_doi(client, dois, mailto="me@example.org")
    assert route.call_count == 2  # 26 DOIs -> batches of 20 + 6
    assert "10.1109/cvpr.2016.90" in found
    first_request = route.calls[0].request
    assert "mailto=me%40example.org" in str(first_request.url)
    assert all("example.org" not in row["key"] for row in cache.export())


@pytest.mark.anyio
@respx.mock
async def test_doira_chunks_and_quotes(http: httpx.AsyncClient) -> None:
    payload = json.loads((FIXTURES / "doiorg/doira_multi.json").read_text(encoding="utf-8"))
    route = respx.get(url__startswith=doiorg.DOIRA_URL).mock(
        return_value=httpx.Response(200, json=payload)
    )
    client = client_for(doiorg.POLICY, http, Cache(None))
    answers = await doiorg.registration_agencies(
        client, ["10.1109/CVPR.2016.90", "10.48550/arXiv.1706.03762", "10.1109/CVPR.2016.999999"]
    )
    assert route.call_count == 1
    assert answers["10.48550/arxiv.1706.03762"].agency == "DataCite"
    assert answers["10.1109/cvpr.2016.999999"].exists is False


@pytest.mark.anyio
@respx.mock
async def test_arxiv_by_ids_uses_text_and_caches(http: httpx.AsyncClient) -> None:
    feed = (FIXTURES / "arxiv/idlist_multi.xml").read_text(encoding="utf-8")
    route = respx.get(arxiv.API_URL).mock(
        return_value=httpx.Response(
            200, text=feed, headers={"content-type": "application/atom+xml"}
        )
    )
    client = client_for(arxiv.POLICY, http, Cache(None))
    found = await arxiv.by_ids(client, ["1706.03762v5", "1512.03385"])
    again = await arxiv.by_ids(client, ["1706.03762", "1512.03385"])
    assert set(found) >= {"1706.03762", "1512.03385"}
    assert set(again) == set(found)
    assert route.call_count == 1  # second call served from cache (versions stripped)


@pytest.mark.anyio
@respx.mock
async def test_dblp_doi_lookup_uppercases(http: httpx.AsyncClient) -> None:
    payload = json.loads((FIXTURES / "dblp/batch_doi_upper.json").read_text(encoding="utf-8"))
    route = respx.get(dblp.SPARQL_URL).mock(return_value=httpx.Response(200, json=payload))
    client = client_for(dblp.POLICY, http, Cache(None))
    mapping = await dblp.by_dois(client, ["10.1109/cvpr.2016.90"])
    query = route.calls[0].request.url.params["query"]
    assert "<https://doi.org/10.1109/CVPR.2016.90>" in query
    assert "10.1109/cvpr.2016.90" in mapping


@pytest.mark.anyio
@respx.mock
async def test_openalex_singleton_and_key_not_cached(http: httpx.AsyncClient) -> None:
    payload = json.loads(
        (FIXTURES / "openalex/work_doi_wakefield.json").read_text(encoding="utf-8")
    )
    route = respx.get(url__startswith=openalex.WORKS_URL + "/doi:").mock(
        return_value=httpx.Response(200, json=payload)
    )
    cache = Cache(None)
    client = client_for(openalex.POLICY, http, cache)
    record = await openalex.work_by_doi(
        client, "10.1016/S0140-6736(97)11096-0", api_key="SECRET-KEY"
    )
    assert record is not None
    assert "retracted" in record.status
    assert "api_key=SECRET-KEY" in str(route.calls[0].request.url)
    assert all("SECRET" not in row["key"] for row in cache.export())
