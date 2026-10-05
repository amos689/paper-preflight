"""DataCite REST adapter: arXiv DOIs (10.48550), Zenodo and other DataCite DOIs."""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any

from paper_preflight.cache import EntryKind
from paper_preflight.sources.base import PartialUnavailable, SourceClient, SourcePolicy
from paper_preflight.sources.record import Person, SourceRecord, collapse, plain_title

DOIS_URL = "https://api.datacite.org/dois"
BATCH = 25
FIELDS = "doi,titles,creators,publicationYear,version,types,url,identifiers,publisher,dates"

POLICY = SourcePolicy(name="datacite", min_interval=1.0)
# Zenodo titles a GitHub release "owner/repo: tag" ("pyRiemann/pyRiemann: v0.10"); the work is
# the repository, as its citation names it
# Zenodo titles a GitHub release "owner/repo: tag", with the tag after the repository's name
# ("tystan/simplexity: simplexity v0.1.1") or followed by its notes ("explosion/spaCy: v3.7.2:
# Fixes for APIs and requirements"); a concept DOI carries the latest release's title
_GITHUB_RELEASE = re.compile(r"^[\w.-]+/([\w.-]+): (?:[\w.-]+ )?v?\d[\w.+-]*(?::.*)?$")
# Repositories deposit dataset and software creators as they please, and often not all of them
_PARTIAL_AUTHORS = frozenset({"dataset", "software"})


def parse_doi(data: dict[str, Any]) -> SourceRecord:
    attributes = data.get("attributes") or {}
    doi = str(attributes.get("doi") or data.get("id") or "").lower()
    titles = [plain_title(str(t.get("title", ""))) for t in attributes.get("titles") or []]
    release = _GITHUB_RELEASE.match(titles[0]) if titles else None
    if release:
        titles = [release.group(1), *titles]
    authors: list[Person] = []
    for creator in attributes.get("creators") or []:
        if creator.get("nameType") == "Organizational" or not (
            creator.get("familyName") or creator.get("givenName")
        ):
            name = collapse(str(creator.get("name", "")))
            parts = [p.strip() for p in name.split(",") if p.strip()]
            if len(parts) > 1 and all(len(p.split()) > 1 for p in parts):
                # several people in one name, as UCI deposits them: "Barry Becker, Ronny Kohavi"
                authors.extend(Person.from_display(p) for p in parts)
            elif "," in name and creator.get("nameType") != "Organizational":
                authors.append(Person.from_display(name))
            else:
                authors.append(Person(family=name, literal=name))
        elif not creator.get("givenName") and " " in str(creator.get("familyName")):
            # Zenodo puts a GitHub user's whole name in familyName ("Ines Montani")
            authors.append(Person.from_display(collapse(str(creator["familyName"]))))
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
    work_type = str(types.get("resourceTypeGeneral") or "").lower() or None
    publisher = (
        attributes.get("publisher") if isinstance(attributes.get("publisher"), str) else None
    )
    if release:  # a software release: its year is the release's, not the cited software's
        year, years = None, set()
    return SourceRecord(
        source="datacite",
        source_id=doi,
        title=titles[0] if titles else "",
        alt_titles=tuple(titles[1:]),
        authors=tuple(authors),
        authors_complete=work_type not in _PARTIAL_AUTHORS,
        authors_ordered=work_type != "software",  # Zenodo orders a repository's contributors
        year=int(year) if year else None,
        years=frozenset(years),
        venue=publisher,
        # lower-cased like the other sources ("Preprint" -> "preprint"), so preprint checks apply
        work_type=work_type,
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

    async def fetch_chunk(chunk: list[str]) -> dict[str, Any]:
        params = {"ids": ",".join(chunk), "fields[dois]": FIELDS, "page[size]": len(chunk)}
        fetched = await client.get_json(DOIS_URL, params=params, classify=_classify)
        data = (fetched.data or {}).get("data") or []
        items = [data] if isinstance(data, dict) else data
        return {parse_doi(item).source_id: item for item in items}

    try:
        items = await client.batch("dois", unique, fetch_chunk, chunk_size=BATCH)
    except PartialUnavailable as partial:
        raise partial.with_found({k: parse_doi(v) for k, v in partial.found.items()}) from None
    return {doi: parse_doi(item) for doi, item in items.items()}
