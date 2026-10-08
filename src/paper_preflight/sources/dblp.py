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

from paper_preflight.bib.normalize import fold
from paper_preflight.cache import EntryKind
from paper_preflight.sources.base import PartialUnavailable, SourceClient, SourcePolicy
from paper_preflight.sources.record import Person, SourceRecord, collapse, plain_title

SPARQL_URL = "https://sparql.dblp.org/sparql"
PREFIX = "PREFIX dblp: <https://dblp.org/rdf/schema#>\n"
REC = "https://dblp.org/rec/"

POLICY = SourcePolicy(name="dblp", min_interval=1.0, max_concurrency=1, timeout=30.0)
SPARQL_ACCEPT = {"Accept": "application/sparql-results+json"}
CHUNK = 50  # IRIs or DOIs per batch query; keeps the GET request short
TITLE_CHUNK = 10  # title prefixes per query: ten range scans take about a second together
# dblp's streams of preprints and technical reports: another copy of a preprint, never its
# published version (arXiv 2108.03171 is in ECCC 2021 and at ITCS 2022; only ITCS counts)
PREPRINT_ARCHIVES = frozenset(
    {"CoRR", "IACR Cryptol. ePrint Arch.", "Electron. Colloquium Comput. Complex."}
)


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def prefix_range(title: str, length: int = 40) -> tuple[str, str]:
    """A folded prefix of the title and its successor, for a range filter on dblp:title.

    dblp's SPARQL engine compares strings with a collation that ignores punctuation and
    accents, so the two bounds must differ in a letter it does not ignore. A prefix that ended
    in ":" gave the empty range "...control:" to "...control;" and lost a real ICML paper (a
    HALLMARK VALID entry reported as not found). The prefix therefore ends in an ASCII letter
    below "z", and the upper bound is that letter's successor.
    """
    low = fold(collapse(title))[:length]
    while low and not ("a" <= low[-1] <= "y"):
        low = low[:-1]
    if not low:
        return "", "￿"
    return low, low[:-1] + chr(ord(low[-1]) + 1)


def title_prefix_query(title: str) -> str:
    low, high = prefix_range(title)
    return PREFIX + (
        "SELECT ?pub ?t WHERE {\n"
        f'  ?pub dblp:title ?t . FILTER(?t >= "{_escape(low)}" && ?t < "{_escape(high)}")\n'
        "} LIMIT 100"
    )


def title_prefixes_query(lows: list[str]) -> str:
    """One query for several title prefixes; ``?i`` says which prefix a row answers."""
    parts = []
    for i, low in enumerate(lows):
        high = low[:-1] + chr(ord(low[-1]) + 1)
        parts.append(
            f"  {{ SELECT ?pub ?t ({i} AS ?i) WHERE {{ ?pub dblp:title ?t . "
            f'FILTER(?t >= "{_escape(low)}" && ?t < "{_escape(high)}") }} LIMIT 100 }}'
        )
    return PREFIX + "SELECT ?i ?pub ?t WHERE {\n" + "\n  UNION\n".join(parts) + "\n}"


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
    """dblp titles end with a period that is not part of the title, and may keep TeX math
    ("The Optimal Hard Threshold for Singular Values is \\(4/\\sqrt {3}\\)")."""
    title = plain_title(collapse(title))
    return title[:-1] if title.endswith(".") and not title.endswith("..") else title


def parse_title_candidates(payload: Any) -> list[tuple[str, str]]:
    return [(row["pub"], clean_title(row.get("t", ""))) for row in _bindings(payload)]


def parse_full_records(payload: Any) -> dict[str, SourceRecord]:
    return records_from_rows(_bindings(payload))


_KEY_YEAR_RE = re.compile(r"(\d{2})[a-z]?$")
# a year in a DOI's suffix: the ACL Anthology's "10.18653/v1/2024.findings-acl.833"
_DOI_YEAR = re.compile(r"/(?:v\d+/)?((?:19|20)\d\d)\.")


def key_year(key: str, year: int | None) -> int | None:
    """The year in a dblp key ("conf/birws/AtanassovaB24") when it is next to the recorded one.

    dblp records a workshop under the year its proceedings appeared, which may be the year after
    the workshop (BIR 2024, published 2025), while its key keeps the year the entry was made
    for. Authors cite either.
    """
    match = _KEY_YEAR_RE.search(key.rsplit("/", 1)[-1])
    if match is None or year is None:
        return None
    century = year - year % 100
    for candidate in (c + int(match.group(1)) for c in (century, century - 100, century + 100)):
        if abs(candidate - year) == 1:  # 1999 and "...00" too
            return candidate
    return None


def records_from_rows(rows: Iterable[dict[str, str]]) -> dict[str, SourceRecord]:
    grouped: dict[str, dict[str, Any]] = {}
    for row in rows:
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
        doi_year = _DOI_YEAR.search(identifiers.get("doi", ""))
        key_digits = _KEY_YEAR_RE.search(key.rsplit("/", 1)[-1])
        if (
            year is not None
            and doi_year is not None
            and key_digits is not None
            and int(doi_year.group(1)) % 100 == int(key_digits.group(1))
            and abs(int(doi_year.group(1)) - year) >= 2
        ):
            # dblp files "conf/acl/ShaoLF0LQ24" (10.18653/v1/2024.findings-acl.833) under 2014
            year = int(doi_year.group(1))
        work_type = row.get("type", "").rsplit("#", 1)[-1].lower() or None
        if key.startswith("data/"):
            # dblp's research data and code ("data/12/HichamRGM26", a Zenodo DOI), typed Misc
            work_type = "dataset"
        records[key] = SourceRecord(
            source="dblp",
            source_id=key,
            title=clean_title(row.get("title", "")),
            authors=authors,
            authors_complete=True,
            year=year,
            years=frozenset(y for y in (year, key_year(key, year)) if y),
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


async def title_candidates_many(
    client: SourceClient, titles: Iterable[str]
) -> dict[str, list[tuple[str, str]]]:
    """(pub, title) candidates for each title, ten prefixes per query, cached per prefix.

    Keyed by the prefix (``prefix_range(title)[0]``); a title without a letter to search for
    gets no candidates.
    """

    async def fetch_chunk(chunk: list[str]) -> dict[str, Any]:
        found: dict[str, list[list[str]]] = {low: [] for low in chunk}
        for row in _bindings(await _select(client, title_prefixes_query(chunk))):
            found[chunk[int(row["i"])]].append([row["pub"], clean_title(row.get("t", ""))])
        return {low: rows for low, rows in found.items() if rows}

    def as_tuples(found: dict[str, Any]) -> dict[str, list[tuple[str, str]]]:
        return {low: [(pub, title) for pub, title in rows] for low, rows in found.items()}

    lows = [low for low in (prefix_range(t)[0] for t in titles) if low]
    try:
        found = await client.batch(
            "prefix", lows, fetch_chunk, chunk_size=TITLE_CHUNK, kind=EntryKind.SEARCH
        )
    except PartialUnavailable as partial:
        raise partial.with_found(as_tuples(partial.found)) from None
    return as_tuples(found)


# The batch lookups below are cached per IRI or DOI (SourceClient.batch), so a later run whose
# batch has other companions, or an --offline run, reuses every answer it already has.


async def full_records(client: SourceClient, pubs: Iterable[str]) -> dict[str, SourceRecord]:
    """Full records keyed by dblp key (the IRI without its prefix)."""

    async def fetch_chunk(chunk: list[str]) -> dict[str, Any]:
        rows: dict[str, list[dict[str, str]]] = {}
        for row in _bindings(await _select(client, full_records_query(chunk))):
            rows.setdefault(row["pub"], []).append(row)
        return rows

    def records(found: dict[str, Any]) -> dict[str, SourceRecord]:
        return records_from_rows(row for rows in found.values() for row in rows)

    try:
        found = await client.batch("rec", pubs, fetch_chunk, chunk_size=CHUNK)
    except PartialUnavailable as partial:
        raise partial.with_found(records(partial.found)) from None
    return records(found)


async def by_dois(client: SourceClient, dois: Iterable[str]) -> dict[str, str]:
    """Map lower-cased DOIs (incl. arXiv DOIs) to dblp record IRIs."""

    async def fetch_chunk(chunk: list[str]) -> dict[str, Any]:
        result: dict[str, str] = {}
        for row in _bindings(await _select(client, doi_query(chunk))):
            doi = re.sub(r"^https?://doi\.org/", "", row["doi"]).lower()
            result[doi] = row["pub"]
        return result

    return await client.batch("doi", (d.lower() for d in dois), fetch_chunk, chunk_size=CHUNK)


async def published_versions(
    client: SourceClient, corr_pubs: Iterable[str]
) -> dict[str, list[tuple[str, str, int | None]]]:
    """For CoRR records, the non-CoRR records by the same first author with the same title."""

    async def fetch_chunk(chunk: list[str]) -> dict[str, Any]:
        links: dict[str, list[list[Any]]] = {}
        for row in _bindings(await _select(client, corr_link_query(chunk))):
            venue = row.get("venue", "")
            if venue in PREPRINT_ARCHIVES:
                continue
            year = int(row["year"]) if row.get("year", "").isdigit() else None
            links.setdefault(row["corr"], []).append([row["other"], venue, year])
        return links

    def as_tuples(found: dict[str, Any]) -> dict[str, list[tuple[str, str, int | None]]]:
        return {corr: [(o, v, y) for o, v, y in rows] for corr, rows in found.items()}

    try:
        found = await client.batch("corr", corr_pubs, fetch_chunk, chunk_size=CHUNK)
    except PartialUnavailable as partial:
        raise partial.with_found(as_tuples(partial.found)) from None
    return as_tuples(found)
