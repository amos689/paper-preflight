"""A fake scholarly web for end-to-end tests: routes requests to recorded responses.

Every handler answers like the real service did during spikes S1-S4 (tests/fixtures/sources).
Unknown requests return an empty-but-valid answer, never an error, so tests fail loudly on wrong
expectations rather than on missing fixtures. Individual services can be switched to a failure
mode (bot wall, 429) to test unavailability handling.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.parse import unquote

import httpx

FIXTURES = Path(__file__).parent / "fixtures" / "sources"


def _load(name: str) -> Any:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _text(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


CROSSREF_ITEMS = {
    i["DOI"].lower(): i for i in _load("crossref/batch_filter_doi.json")["message"]["items"]
}
DBLP_ARXIV_CORR = {
    "10.48550/ARXIV.1512.03385": "https://dblp.org/rec/journals/corr/HeZRS15",
    "10.48550/ARXIV.1606.08415": "https://dblp.org/rec/journals/corr/HendrycksG16",
    "10.48550/ARXIV.1706.03762": "https://dblp.org/rec/journals/corr/VaswaniSPUJGKP17",
}


def _sparql(rows: list[dict[str, str]], variables: list[str]) -> dict[str, Any]:
    return {
        "head": {"vars": variables},
        "results": {
            "bindings": [
                {k: {"type": "literal", "value": v} for k, v in row.items()} for row in rows
            ]
        },
    }


class FakeWeb:
    def __init__(self) -> None:
        self.failing: dict[str, str] = {}  # host fragment -> "html" | "429"
        self.requests: list[httpx.Request] = []

    def fail(self, host_fragment: str, mode: str = "html") -> None:
        self.failing[host_fragment] = mode

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        url = str(request.url)
        for fragment, mode in self.failing.items():
            if fragment in url:
                if mode == "429":
                    return httpx.Response(429, text="Rate exceeded.")
                return httpx.Response(
                    200, text="<!doctype html><title>Making sure you're not a bot!</title>",
                    headers={"content-type": "text/html"},
                )  # fmt: skip
        host = request.url.host
        if host == "doi.org" and request.url.path.startswith("/doiRA/"):
            return self._doira(request)
        if host == "api.crossref.org":
            return self._crossref(request)
        if host == "api.datacite.org":
            return httpx.Response(200, json={"data": []})
        if host == "api.openalex.org":
            return httpx.Response(200, json=_load("openalex/batch_or_doi.json"))
        if host == "export.arxiv.org":
            return httpx.Response(
                200, text=_text("arxiv/idlist_multi.xml"),
                headers={"content-type": "application/atom+xml"},
            )  # fmt: skip
        if host == "sparql.dblp.org":
            return self._dblp(request)
        return httpx.Response(404, json={})

    def _doira(self, request: httpx.Request) -> httpx.Response:
        dois = unquote(request.url.path.removeprefix("/doiRA/")).split(",")
        answers = []
        for doi in dois:
            if doi.lower().startswith("10.48550/"):
                answers.append({"DOI": doi, "RA": "DataCite"})
            elif doi.lower() in CROSSREF_ITEMS:
                answers.append({"DOI": doi, "RA": "Crossref"})
            else:
                answers.append({"DOI": doi, "status": "DOI does not exist"})
        return httpx.Response(200, json=answers)

    def _crossref(self, request: httpx.Request) -> httpx.Response:
        params = request.url.params
        if "filter" in params:
            wanted = [f.removeprefix("doi:").lower() for f in params["filter"].split(",")]
            items = [CROSSREF_ITEMS[d] for d in wanted if d in CROSSREF_ITEMS]
            return httpx.Response(200, json={"message": {"items": items}})
        query = params.get("query.bibliographic", "")
        if "Quantum Gradient Folding" in query:
            return httpx.Response(200, json=_load("crossref/biblio_t8.json"))
        if "Deep Residual Learning" in query:
            return httpx.Response(200, json=_load("crossref/biblio_t2.json"))
        if "Attention Is All You Need" in query:  # ranks the fake 10.65215 copies first
            return httpx.Response(200, json=_load("crossref/biblio_t1_withauthors.json"))
        return httpx.Response(200, json={"message": {"items": []}})

    def _dblp(self, request: httpx.Request) -> httpx.Response:
        query = request.url.params.get("query", "")
        if "dblp:doi ?doi ." in query and "VALUES ?doi" in query:
            rows = [
                {"doi": f"https://doi.org/{doi}", "pub": pub}
                for doi, pub in DBLP_ARXIV_CORR.items()
                if f"<https://doi.org/{doi}>" in query
            ]
            return httpx.Response(200, json=_sparql(rows, ["doi", "pub"]))
        if "authoredBy" in query:
            return httpx.Response(200, json=_load("dblp/link_corr_to_conf.json"))
        if "VALUES ?pub" in query and "KingmaB14" in query:
            return httpx.Response(200, json=_load("dblp/full_records_adam.json"))
        if "VALUES ?pub" in query:
            return httpx.Response(200, json=_load("dblp/full_records.json"))
        if "quantum gradient folding" in query:
            return httpx.Response(200, json=_load("dblp/prefix_t8.json"))
        if "adam: a method for stochastic" in query:
            return httpx.Response(200, json=_load("dblp/prefix_adam.json"))
        if "attention is all you need" in query:
            return httpx.Response(200, json=_load("dblp/prefix_t1.json"))
        return httpx.Response(200, json=_sparql([], ["pub", "t"]))
