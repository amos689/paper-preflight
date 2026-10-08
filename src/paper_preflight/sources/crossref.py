"""Crossref REST API adapter (docs/spikes/S2-crossref.md).

* Known DOIs are fetched in batches with ``filter=doi:a,doi:b`` (list pool: 1 request/s).
* ``query.bibliographic`` is used only for references without identifiers; its relevance score
  is never treated as a confidence (fake ``posted-content`` duplicates rank first).
* Retraction/correction status comes from ``updated-by`` (currently sourced from Retraction
  Watch) and from a ``RETRACTED:`` title prefix.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import replace
from typing import Any

from paper_preflight.cache import EntryKind
from paper_preflight.sources.base import PartialUnavailable, SourceClient, SourcePolicy
from paper_preflight.sources.record import Person, SourceRecord, collapse, plain_title

WORKS_URL = "https://api.crossref.org/works"
BATCH = 20
SELECT = ",".join(
    [
        "DOI", "title", "subtitle", "type", "author", "issued", "published-print",
        "published-online", "container-title", "event", "updated-by", "relation", "volume",
        "issue", "page", "publisher", "member", "prefix", "URL", "created",
        "short-container-title", "ISSN",
    ]
)  # fmt: skip
# Coordinate lookups also compare article numbers. A separate list: the fields are part of the
# cache key, and changing SELECT would orphan every cached answer (and the evaluation replays).
COORDINATE_SELECT = f"{SELECT},article-number"

POLICY = SourcePolicy(name="crossref", min_interval=1.0, max_concurrency=1)
# With a contact address (mailto) requests go to the polite pool, whose answers announce
# "x-rate-limit-limit: 3", "x-rate-limit-interval: 1s" and "x-concurrency-limit: 3" (checked
# 2026-10-08); the client slows down if the announced limit ever tightens.
POLITE_POLICY = replace(POLICY, min_interval=0.34, max_concurrency=3)
_WILEY_YEAR = re.compile(r"^10\.\d{4,9}/j\.\d{4}-\d{3}[\dx]\.(\d{4})\.\d+\.x$")
_BOOK_TYPES = frozenset({"book", "monograph", "edited-book", "reference-book"})
_IEEE_YEAR = re.compile(r"^10\.1109/[a-z]+\.(\d{4})\.\d{5,}$")
# Chinese journals' DOIs: Science Press's "10.3724/sp.j.1087.2012.00322" (J. Computer Applications
# 32(2), 2012; Crossref has 2013) and "10.11959/j.issn.2096-0271.2015030"
_CHINESE_YEAR = re.compile(r"^10\.\d{4,9}/(?:sp\.j\.\d+|j\.issn\.\d{4}-\d{3}[\dx])\.(\d{4})")
# a publisher's code for a journal given as its title: De Gruyter's "humr" for HUMOR
_JOURNAL_CODE = re.compile(r"[a-z]{2,6}")

UPDATE_STATUS = {
    "retraction": "retracted",
    "removal": "retracted",
    "partial_retraction": "partial_retraction",
    "withdrawal": "withdrawn",
    "expression_of_concern": "expression_of_concern",
    "correction": "correction",
    "corrigendum": "correction",
    "erratum": "correction",
}


def _year(item: dict[str, Any], key: str) -> int | None:
    parts = (item.get(key) or {}).get("date-parts") or [[None]]
    if parts and parts[0] and parts[0][0]:
        return int(parts[0][0])
    return None


def parse_work(item: dict[str, Any]) -> SourceRecord:
    doi = str(item.get("DOI", "")).lower()
    titles = item.get("title") or [""]
    title = plain_title(str(titles[0]))
    subtitles = [plain_title(str(s)) for s in item.get("subtitle") or [] if s]
    alt_titles = tuple(f"{title}: {s}" for s in subtitles)

    authors: list[Person] = []
    for author in item.get("author") or []:
        if "family" in author or "given" in author:
            authors.append(Person.from_parts(author.get("given"), author.get("family")))
        elif author.get("name"):
            name = collapse(str(author["name"]))
            authors.append(Person(family=name, literal=name))

    years = {
        y for y in (_year(item, k) for k in ("issued", "published-print", "published-online")) if y
    }
    if (
        doi.startswith("10.1017/cbo")
        and item.get("type") in _BOOK_TYPES
        and not item.get("published-print")
    ):
        # Cambridge Books Online put printed books online years later and deposited only that
        # date: 10.1017/cbo9780511976667 is Nielsen & Chuang's 2010 edition, "2012". No year.
        years = set()
    # Early access: IEEE and others put an article online a year or more before its issue but
    # deposit no online date, only the DOI's creation (DOI 10.1109/tpami.2023.3330794: online
    # November 2023, issue April 2024). Authors cite either year.
    created = _year(item, "created")
    if (
        item.get("type") == "journal-article"
        and not item.get("published-online")
        and created
        and years
        and 0 < min(years) - created <= 2
    ):
        years.add(created)
    # A December print date is often next year's first issue (MNRAS 500(4), cover date January
    # 2021, printed 10 December 2020); the issue's year is cited too. A book printed late in the
    # year carries next year's copyright date (Cover & Thomas, 2nd edition: printed September
    # 2005, dated 2006).
    printed = ((item.get("published-print") or {}).get("date-parts") or [[None]])[0]
    if len(printed) >= 2 and printed[0] and printed[1] == 12:
        years.add(int(printed[0]) + 1)
    if item.get("type") in _BOOK_TYPES and len(printed) >= 2 and printed[0] and printed[1] >= 9:
        years.add(int(printed[0]) + 1)
    # An article online late in the year, with no print date, is often in next year's volume
    # (Quantum Sci. Technol. 4(1) 014004: online 9 October 2018, volume 4 is 2019).
    online = ((item.get("published-online") or {}).get("date-parts") or [[None]])[0]
    if (
        item.get("type") == "journal-article"
        and not item.get("published-print")
        and (item.get("volume") or (len(online) >= 2 and online[1] == 12))
        and len(online) >= 2
        and online[0]
        and online[1] >= 10
    ):
        years.add(int(online[0]) + 1)
    # Wiley and Blackwell DOIs carry the year the article was published ("10.1046/j.1365-8711.
    # 2000.03658.x", MNRAS 319(3), December 2000); a backfile deposit may give only the year it
    # went online (2002). The DOI's year counts when it is a few years before the registered ones.
    # IEEE's journal DOIs carry the year they were assigned, at early access: "10.1109/tse.2018.
    # 2872971" was online in 2018, and Crossref has only its issue's date, 2020.
    embedded = (
        _WILEY_YEAR.match(doi)
        or _CHINESE_YEAR.match(doi)
        or (_IEEE_YEAR.match(doi) if item.get("type") == "journal-article" else None)
    )
    if embedded and years and 0 < min(years) - int(embedded.group(1)) <= 3:
        years.add(int(embedded.group(1)))
    venue = None
    containers = [
        collapse(str(c))
        for c in item.get("container-title") or []
        if c and not _JOURNAL_CODE.fullmatch(collapse(str(c)))
    ]
    if containers:
        venue = containers[0]
    elif (item.get("event") or {}).get("name"):
        venue = collapse(str(item["event"]["name"]))
    # a chapter's book series and its book ("Lecture Notes in Computer Science", "Research and
    # Advanced Technology for Digital Libraries"), a journal's ISO 4 abbreviation
    shorts = [collapse(str(c)) for c in item.get("short-container-title") or [] if c]
    aliases = tuple(dict.fromkeys(a for a in containers[1:] + shorts if a != venue))

    status: set[str] = set()
    status_sources: list[str] = []
    for update in item.get("updated-by") or []:
        flag = UPDATE_STATUS.get(str(update.get("type", "")).lower())
        if flag:
            status.add(flag)
            source = update.get("source", "unknown")
            status_sources.append(f"crossref:{source}:{update.get('DOI', '')}")
    if title.upper().startswith("RETRACTED"):
        status.add("retracted")
        status_sources.append("crossref:title-prefix")

    relations: dict[str, tuple[str, ...]] = {}
    for kind, targets in (item.get("relation") or {}).items():
        ids = tuple(str(t.get("id", "")).lower() for t in targets if t.get("id"))
        if ids:
            relations[kind] = ids

    identifiers = {"doi": doi}
    if item.get("prefix"):
        identifiers["doi_prefix"] = str(item["prefix"])
    if item.get("member"):
        identifiers["crossref_member"] = str(item["member"])

    return SourceRecord(
        source="crossref",
        source_id=doi,
        title=title,
        authors=tuple(authors),
        year=(_year(item, "issued") if years else None) or (min(years) if years else None),
        years=frozenset(years),
        venue=venue,
        work_type=item.get("type"),
        identifiers=identifiers,
        alt_titles=alt_titles,
        status=frozenset(status),
        status_sources=tuple(status_sources),
        relations=relations,
        volume=str(item["volume"]) if item.get("volume") else None,
        issue=str(item["issue"]) if item.get("issue") else None,
        # an article number stands for the pages (Phys. Rev. D 70, 083509)
        pages=str(item.get("page") or item.get("article-number") or "") or None,
        publisher=item.get("publisher"),
        url=item.get("URL"),
        venue_aliases=aliases,
        issns=frozenset(str(i).upper() for i in item.get("ISSN") or []),
    )


def parse_work_list(payload: Any) -> list[SourceRecord]:
    message = (payload or {}).get("message") or {}
    return [parse_work(item) for item in message.get("items") or []]


def _params(extra: dict[str, Any], mailto: str | None) -> dict[str, Any]:
    params = dict(extra)
    if mailto:
        params["mailto"] = mailto  # polite pool; stripped from cache keys
    return params


def _classify_list(payload: Any) -> EntryKind:
    items = ((payload or {}).get("message") or {}).get("items") or []
    return EntryKind.SEARCH if items else EntryKind.NEGATIVE


async def works_by_doi(
    client: SourceClient, dois: Iterable[str], *, mailto: str | None = None
) -> dict[str, SourceRecord]:
    """Fetch Crossref records for DOIs (case-insensitive). Missing DOIs are simply absent."""
    unique = list(dict.fromkeys(d.lower() for d in dois))

    async def fetch_chunk(chunk: list[str]) -> dict[str, Any]:
        params = _params(
            {
                "filter": ",".join(f"doi:{d}" for d in chunk),
                "rows": len(chunk),
                "select": SELECT,
            },
            mailto,
        )
        fetched = await client.get_json(WORKS_URL, params=params, classify=_classify_list)
        items = ((fetched.data or {}).get("message") or {}).get("items") or []
        return {str(item.get("DOI", "")).lower(): item for item in items}

    try:
        items = await client.batch("works", unique, fetch_chunk, chunk_size=BATCH)
    except PartialUnavailable as partial:
        raise partial.with_found(_records(partial.found)) from None
    return _records(items)


def _records(items: dict[str, Any]) -> dict[str, SourceRecord]:
    return {doi: parse_work(item) for doi, item in items.items()}


async def search_bibliographic(
    client: SourceClient, query: str, *, rows: int = 10, mailto: str | None = None
) -> list[SourceRecord]:
    """Free-text bibliographic search (title + first authors + year work best)."""
    params = _params({"query.bibliographic": query, "rows": rows, "select": SELECT}, mailto)
    fetched = await client.get_json(WORKS_URL, params=params, classify=_classify_list)
    return parse_work_list(fetched.data)


async def search_coordinates(
    client: SourceClient,
    journal: str,
    volume: str,
    page: str,
    *,
    year: int,
    author: str | None = None,
    mailto: str | None = None,
) -> list[SourceRecord]:
    """Articles near a journal, volume and first page, a year either side of the cited one (an
    article is often online a year before its issue). The caller keeps only records at exactly
    those coordinates. Twenty rows: on development data the right record was outside the first
    five for 2 of 87 entries."""
    extra = {
        "query.bibliographic": f"{journal} {volume} {page}",
        "filter": f"from-pub-date:{year - 1},until-pub-date:{year + 1}",
        "rows": 20,
        "select": COORDINATE_SELECT,
    }
    if author:
        extra["query.author"] = author
    fetched = await client.get_json(
        WORKS_URL, params=_params(extra, mailto), classify=_classify_list
    )
    return parse_work_list(fetched.data)
