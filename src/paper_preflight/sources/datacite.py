"""DataCite REST adapter: arXiv DOIs (10.48550), Zenodo and other DataCite DOIs."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from paper_preflight.cache import EntryKind
from paper_preflight.sources.base import SourceClient, SourcePolicy
from paper_preflight.sources.record import Person, SourceRecord, collapse, plain_title

DOIS_URL = "https://api.datacite.org/dois"
BATCH = 25
FIELDS = "doi,titles,creators,publicationYear,version,types,url,identifiers,publisher,dates"

POLICY = SourcePolicy(name="datacite", min_interval=1.0)


def parse_doi(data: dict[str, Any]) -> SourceRecord:
    attributes = data.get("attributes") or {}
    doi = str(attributes.get("doi") or data.get("id") or "").lower()
    titles = [plain_title(str(t.get("title", ""))) for t in attributes.get("titles") or []]
    authors: list[Person] = []
    for creator in attributes.get("creators") or []:
        if creator.get("nameType") == "Organizational" or not (
            creator.get("familyName") or creator.get("givenName")
        ):
            name = collapse(str(creator.get("name", "")))
            if "," in name and creator.get("nameType") != "Organizational":
                authors.append(Person.from_display(name))
            else:
                authors.append(Person(family=name, literal=name))
        else:
            authors.append(Person.from_parts(creator.get("givenName"), creator.get("familyName")))
    year = attributes.get("publicationYear")
    years = {int(year)} if year else set()
    for date in attributes.get("dates") or []:
        value = str(date.get("date", ""))[:4]
        if value.isdigit():
            years.add(int(value))
    identifiers = {"doi": doi}
    for ident in attributes.get("identifiers") or []:
        if str(ident.get("identifierType", "")).lower() == "arxiv":
            identifiers["arxiv"] = str(ident.get("identifier"))
    if "arxiv" not in identifiers and doi.startswith("10.48550/arxiv."):
        identifiers["arxiv"] = doi.removeprefix("10.48550/arxiv.")
    types = attributes.get("types") or {}
    publisher = (
        attributes.get("publisher") if isinstance(attributes.get("publisher"), str) else None
    )
    return SourceRecord(
        source="datacite",
        source_id=doi,
        title=titles[0] if titles else "",
        alt_titles=tuple(titles[1:]),
        authors=tuple(authors),
        year=int(year) if year else None,
        years=frozenset(years),
        venue=publisher,
        # lower-cased like the other sources ("Preprint" -> "preprint"), so preprint checks apply
        work_type=str(types.get("resourceTypeGeneral") or "").lower() or None,
        identifiers=identifiers,
        publisher=publisher,
        url=attributes.get("url"),
    )


def parse_dois(payload: Any) -> list[SourceRecord]:
    data = (payload or {}).get("data")
    if isinstance(data, dict):
        return [parse_doi(data)]
    return [parse_doi(item) for item in data or []]


def _classify(payload: Any) -> EntryKind:
    return EntryKind.POSITIVE if (payload or {}).get("data") else EntryKind.NEGATIVE


async def dois(client: SourceClient, values: Iterable[str]) -> dict[str, SourceRecord]:
    unique = list(dict.fromkeys(v.lower() for v in values))
    found: dict[str, SourceRecord] = {}
    for start in range(0, len(unique), BATCH):
        chunk = unique[start : start + BATCH]
        params = {"ids": ",".join(chunk), "fields[dois]": FIELDS, "page[size]": len(chunk)}
        fetched = await client.get_json(DOIS_URL, params=params, classify=_classify)
        for record in parse_dois(fetched.data):
            found[record.source_id] = record
    return found
