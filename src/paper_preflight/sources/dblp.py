"""dblp via its SPARQL endpoint (QLever). The search API sits behind a bot wall and is never used.

Query templates follow docs/spikes/S1-dblp-sparql.md:

* T1 title lookup by a lower-cased prefix range (QLever collates case-insensitively);
* T3 full records with ordered authors;
* T4/T5 batch lookups by DOI / arXiv DOI (dblp stores DOIs upper-cased);
* T6 linking CoRR (arXiv) records to published versions via first author + normalised title.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any

from paper_preflight.cache import EntryKind
from paper_preflight.sources.base import SourceClient, SourcePolicy
from paper_preflight.sources.record import Person, SourceRecord, collapse

SPARQL_URL = "https://sparql.dblp.org/sparql"
PREFIX = "PREFIX dblp: <https://dblp.org/rdf/schema#>\n"
REC = "https://dblp.org/rec/"

POLICY = SourcePolicy(name="dblp", min_interval=1.0, max_concurrency=1, timeout=30.0)
SPARQL_ACCEPT = {"Accept": "application/sparql-results+json"}


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def prefix_range(title: str, length: int = 40) -> tuple[str, str]:
    """Lower-cased, whitespace-collapsed prefix and its successor for a range filter."""
    low = collapse(title).lower()[:length].rstrip()
    high = low[:-1] + chr(ord(low[-1]) + 1) if low else "￿"
    return low, high


def title_prefix_query(title: str) -> str:
    low, high = prefix_range(title)
    return PREFIX + (
        "SELECT ?pub ?t WHERE {\n"
        f'  ?pub dblp:title ?t . FILTER(?t >= "{_escape(low)}" && ?t < "{_escape(high)}")\n'
        "} LIMIT 100"
    )


def full_records_query(pubs: Iterable[str]) -> str:
    values = " ".join(f"<{p}>" for p in pubs)
    return PREFIX + (
        "SELECT ?pub ?title ?type ?venue ?year ?doi ?primary ?ord ?name WHERE {\n"
        f"  VALUES ?pub {{ {values} }}\n"
        "  ?pub dblp:title ?title ; dblp:bibtexType ?type .\n"
        "  OPTIONAL { ?pub dblp:publishedIn ?venue }\n"
        "  OPTIONAL { ?pub dblp:yearOfPublication ?year }\n"
        "  OPTIONAL { ?pub dblp:doi ?doi } OPTIONAL { ?pub dblp:primaryDocumentPage ?primary }\n"
        "  OPTIONAL { ?pub dblp:hasSignature ?s . ?s dblp:signatureOrdinal ?ord ;"
        " dblp:signatureDblpName ?name . }\n"
        "} ORDER BY ?pub ?ord"
    )


def doi_query(dois: Iterable[str]) -> str:
    values = " ".join(f"<https://doi.org/{d.upper()}>" for d in dois)
    return PREFIX + (
        f"SELECT ?doi ?pub WHERE {{\n  VALUES ?doi {{ {values} }}\n  ?pub dblp:doi ?doi .\n}}"
    )


def corr_link_query(corr_pubs: Iterable[str]) -> str:
    values = " ".join(f"<{p}>" for p in corr_pubs)
    return PREFIX + (
        "SELECT ?corr ?other ?venue ?year WHERE {\n"
        f"  VALUES ?corr {{ {values} }}\n"
        "  ?corr dblp:title ?ct ; dblp:hasSignature ?s1 . ?s1 dblp:signatureOrdinal 1 ;"
        " dblp:signatureCreator ?a1 .\n"
        "  ?other dblp:authoredBy ?a1 ; dblp:title ?ot . FILTER(?other != ?corr)\n"
        '  FILTER(LCASE(REPLACE(?ot, "[^A-Za-z0-9]", "")) =\n'
        '         LCASE(REPLACE(?ct, "[^A-Za-z0-9]", "")))\n'
        "  OPTIONAL { ?other dblp:publishedIn ?venue }\n"
        "  OPTIONAL { ?other dblp:yearOfPublication ?year }\n"
        "}"
    )


def _bindings(payload: Any) -> list[dict[str, str]]:
    rows = ((payload or {}).get("results") or {}).get("bindings") or []
    return [{k: str(v.get("value", "")) for k, v in row.items()} for row in rows]


def clean_title(title: str) -> str:
    """dblp titles end with a period that is not part of the title."""
    title = collapse(title)
    return title[:-1] if title.endswith(".") and not title.endswith("..") else title


def parse_title_candidates(payload: Any) -> list[tuple[str, str]]:
    return [(row["pub"], clean_title(row.get("t", ""))) for row in _bindings(payload)]


def parse_full_records(payload: Any) -> dict[str, SourceRecord]:
    grouped: dict[str, dict[str, Any]] = {}
    for row in _bindings(payload):
        pub = row["pub"]
        entry = grouped.setdefault(pub, {"row": row, "authors": {}})
        if row.get("ord") and row.get("name"):
            entry["authors"][int(row["ord"])] = row["name"]
    records: dict[str, SourceRecord] = {}
    for pub, entry in grouped.items():
        row = entry["row"]
        key = pub.removeprefix(REC)
        authors = tuple(Person.from_display(entry["authors"][i]) for i in sorted(entry["authors"]))
        identifiers = {"dblp": key}
        doi = row.get("doi", "")
        if doi:
            doi = re.sub(r"^https?://doi\.org/", "", doi).lower()
            if doi.startswith("10.48550/arxiv."):
                identifiers["arxiv"] = doi.removeprefix("10.48550/arxiv.")
                identifiers["arxiv_doi"] = doi
            else:
                identifiers["doi"] = doi
        year = int(row["year"]) if row.get("year", "").isdigit() else None
        work_type = row.get("type", "").rsplit("#", 1)[-1].lower() or None
        records[key] = SourceRecord(
            source="dblp",
            source_id=key,
            title=clean_title(row.get("title", "")),
            authors=authors,
            authors_complete=True,
            year=year,
            years=frozenset({year} if year else set()),
            venue=row.get("venue") or None,
            work_type=work_type,
            identifiers=identifiers,
            url=f"https://dblp.org/rec/{key}",
        )
    return records


async def _select(client: SourceClient, query: str) -> Any:
    def classify(payload: Any) -> EntryKind:
        return EntryKind.SEARCH if _bindings(payload) else EntryKind.NEGATIVE

    fetched = await client.get_json(
        SPARQL_URL, params={"query": query}, headers=SPARQL_ACCEPT, classify=classify
    )
    return fetched.data


async def title_candidates(client: SourceClient, title: str) -> list[tuple[str, str]]:
    return parse_title_candidates(await _select(client, title_prefix_query(title)))


async def full_records(client: SourceClient, pubs: Iterable[str]) -> dict[str, SourceRecord]:
    pub_list = list(dict.fromkeys(pubs))
    if not pub_list:
        return {}
    return parse_full_records(await _select(client, full_records_query(pub_list)))


async def by_dois(client: SourceClient, dois: Iterable[str]) -> dict[str, str]:
    """Map lower-cased DOIs (incl. arXiv DOIs) to dblp record IRIs."""
    doi_list = list(dict.fromkeys(d.lower() for d in dois))
    if not doi_list:
        return {}
    result: dict[str, str] = {}
    for row in _bindings(await _select(client, doi_query(doi_list))):
        doi = re.sub(r"^https?://doi\.org/", "", row["doi"]).lower()
        result[doi] = row["pub"]
    return result


async def published_versions(
    client: SourceClient, corr_pubs: Iterable[str]
) -> dict[str, list[tuple[str, str, int | None]]]:
    """For CoRR records, the non-CoRR records by the same first author with the same title."""
    pubs = list(dict.fromkeys(corr_pubs))
    if not pubs:
        return {}
    links: dict[str, list[tuple[str, str, int | None]]] = {}
    for row in _bindings(await _select(client, corr_link_query(pubs))):
        venue = row.get("venue", "")
        if venue == "CoRR":
            continue
        year = int(row["year"]) if row.get("year", "").isdigit() else None
        links.setdefault(row["corr"], []).append((row["other"], venue, year))
    return links
