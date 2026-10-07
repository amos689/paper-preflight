"""A fake scholarly web for end-to-end tests: routes requests to recorded responses.

Every handler answers like the real service did during spikes S1-S4 (tests/fixtures/sources).
Unknown requests return an empty-but-valid answer, never an error, so tests fail loudly on wrong
expectations rather than on missing fixtures. Individual services can be switched to a failure
mode (bot wall, 429) to test unavailability handling.
"""

from __future__ import annotations

import json
import re
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
# Crossref's answers near "MNRAS 249, 523" (Begeman et al. 1991) and "Phys. Rev. D 70, 083509"
# (Bekenstein 2004, an article number), recorded 2026-10-07, whatever the volume and page asked
COORDINATES = {
    "Monthly Notices of the Royal Astronomical Society": "coordinates_mnras_249_523.json",
    "Physical Review D": "coordinates_prd_70_083509.json",
}
# the demo's two arXiv preprints as DataCite has them (10.48550/arXiv.<id>)
DATACITE_ARXIV = _load("datacite/dc_arxiv_demo_batch.json")["data"]
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
        # Semantic Scholar answers are SYNTHETIC (its licence forbids storing real responses):
        # lower-cased title -> paper JSON in S2's schema. Unknown titles get S2's 404.
        self.s2_papers: dict[str, dict[str, object]] = {}

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
            return self._datacite(request)
        if host == "api.openalex.org":
            return httpx.Response(200, json=_load("openalex/batch_or_doi.json"))
        if host == "export.arxiv.org":
            # explicit versions (v1,v2,...) ask for every title GELU has had
            versions = "1606.08415v1" in request.url.params.get("id_list", "")
            feed = "arxiv/idlist_gelu_versions.xml" if versions else "arxiv/idlist_multi.xml"
            return httpx.Response(
                200, text=_text(feed), headers={"content-type": "application/atom+xml"}
            )
        if host == "sparql.dblp.org":
            return self._dblp(request)
        if host == "eutils.ncbi.nlm.nih.gov":
            return self._pubmed(request)
        if host == "api.semanticscholar.org" and request.url.path.endswith("/search/match"):
            paper = self.s2_papers.get(request.url.params.get("query", "").lower())
            if paper is None:
                return httpx.Response(404, json={"error": "Title match not found"})
            return httpx.Response(200, json={"data": [paper]})
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

    def _pubmed(self, request: httpx.Request) -> httpx.Response:
        # recorded PubMed summaries of 9500320 (retracted), 31452104 and 23193287, and the PMC
        # summary of PMC3531190 (GenBank, PMID 23193287); any other ID is unknown
        database = request.url.params.get("db", "pubmed")
        recorded = _load(f"pubmed/esummary_{database}.json")
        uids = request.url.params.get("id", "").split(",")
        result: dict[str, Any] = {"uids": uids}
        for uid in uids:
            result[uid] = recorded["result"].get(
                uid, {"uid": uid, "error": "cannot get document summary"}
            )
        return httpx.Response(200, json={"header": recorded["header"], "result": result})

    def _datacite(self, request: httpx.Request) -> httpx.Response:
        wanted = set(request.url.params.get("ids", "").lower().split(","))
        items = [i for i in DATACITE_ARXIV if str(i["attributes"]["doi"]).lower() in wanted]
        return httpx.Response(200, json={"data": items})

    def _crossref(self, request: httpx.Request) -> httpx.Response:
        params = request.url.params
        if "query.author" in params:  # an untitled entry's journal coordinates
            query = params.get("query.bibliographic", "")
            for journal, name in COORDINATES.items():
                if query.startswith(journal):
                    return httpx.Response(200, json=_load(f"crossref/{name}"))
            return httpx.Response(200, json={"message": {"items": []}})
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
        if "VALUES ?pub" in query:
            # a batch may ask for several entries' records: answer each one requested
            payload = _load("dblp/full_records.json")
            rows = [
                row
                for name in ("dblp/full_records.json", "dblp/full_records_adam.json")
                for row in _load(name)["results"]["bindings"]
                if f"<{row['pub']['value']}>" in query
            ]
            payload["results"]["bindings"] = [
                row for i, row in enumerate(rows) if row not in rows[:i]
            ]
            return httpx.Response(200, json=payload)
        if " AS ?i)" in query:
            # title prefixes, ten to a query: each part answered as a single query would be
            bindings = []
            for part in query.split("{ SELECT")[1:]:
                index = re.search(r"\((\d+) AS \?i\)", part)
                for row in _prefix(part)["results"]["bindings"]:
                    bindings.append({**row, "i": {"type": "literal", "value": index.group(1)}})
            return httpx.Response(
                200, json={"head": {"vars": ["i", "pub", "t"]}, "results": {"bindings": bindings}}
            )
        return httpx.Response(200, json=_prefix(query))


def _prefix(query: str) -> Any:
    """The recorded answer to one title-prefix query."""
    if "quantum gradient folding" in query:
        return _load("dblp/prefix_t8.json")
    if "adam: a method for stochastic" in query:
        return _load("dblp/prefix_adam.json")
    if "attention is all you need" in query:
        return _load("dblp/prefix_t1.json")
    return _sparql([], ["pub", "t"])
