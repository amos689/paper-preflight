"""Gather evidence about every reference from scholarly sources (docs/adr/0003).

The resolver only *collects*; it never decides. For each entry it records

* the records reached through the entry's own identifiers ("anchored" records),
* candidates found by title search for entries that have no usable identifier,
* published versions of cited preprints,
* and, crucially, which sources answered and which were unavailable — so that the verdict
  layer can tell "not found" (every source answered no) from "cannot determine".

Requests are batched across the whole bibliography and each source paces itself.
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field, replace
from typing import TypeVar

import httpx

from paper_preflight.bib.ids import Identifier, extract_identifiers
from paper_preflight.bib.normalize import word_count
from paper_preflight.bib.parse import BibEntry
from paper_preflight.cache import Cache
from paper_preflight.match import EntryInfo, title_score
from paper_preflight.sources import arxiv, crossref, datacite, dblp, doiorg, openalex
from paper_preflight.sources.base import SourceClient, SourcePolicy, SourceUnavailable
from paper_preflight.sources.doiorg import AgencyAnswer
from paper_preflight.sources.record import SourceRecord

T = TypeVar("T")

CS_ENTRY_TYPES = {"inproceedings", "conference", "proceedings"}
GREY_TYPES = {"book", "booklet", "manual", "misc", "online", "software", "techreport", "report",
              "phdthesis", "mastersthesis", "thesis", "unpublished", "electronic", "standard",
              "patent", "dataset"}  # fmt: skip


@dataclass
class Evidence:
    key: str
    info: EntryInfo
    identifiers: list[Identifier]
    doi_agency: dict[str, AgencyAnswer] = field(default_factory=dict)
    anchored: list[SourceRecord] = field(default_factory=list)
    candidates: list[SourceRecord] = field(default_factory=list)
    published_versions: list[SourceRecord] = field(default_factory=list)
    status_records: list[SourceRecord] = field(default_factory=list)  # e.g. OpenAlex retraction
    searched: set[str] = field(default_factory=set)  # sources asked by title
    negative: set[str] = field(default_factory=set)  # sources that answered "no such work"
    unavailable: dict[str, str] = field(default_factory=dict)  # source -> reason
    arxiv_missing: list[str] = field(default_factory=list)  # arXiv IDs that do not exist

    def mark_unavailable(self, error: SourceUnavailable) -> None:
        self.unavailable.setdefault(error.source, error.reason.value)


@dataclass
class Sources:
    doiorg: SourceClient
    crossref: SourceClient
    datacite: SourceClient
    arxiv: SourceClient
    dblp: SourceClient
    openalex: SourceClient
    mailto: str | None = None
    openalex_key: str | None = None

    @classmethod
    def create(
        cls,
        http: httpx.AsyncClient,
        cache: Cache,
        *,
        offline: bool = False,
        environ: dict[str, str] | None = None,
    ) -> Sources:
        env = environ if environ is not None else dict(os.environ)

        def client(policy: SourcePolicy) -> SourceClient:
            # copy the module-level policy: a client may slow itself down during a run
            return SourceClient(replace(policy), http, cache, offline=offline)

        return cls(
            doiorg=client(doiorg.POLICY),
            crossref=client(crossref.POLICY),
            datacite=client(datacite.POLICY),
            arxiv=client(arxiv.POLICY),
            dblp=client(dblp.POLICY),
            openalex=client(openalex.POLICY),
            mailto=env.get("PAPER_PREFLIGHT_EMAIL") or None,
            openalex_key=env.get("OPENALEX_API_KEY") or None,
        )

    def all_clients(self) -> list[SourceClient]:
        return [self.doiorg, self.crossref, self.datacite, self.arxiv, self.dblp, self.openalex]


def looks_cs(info: EntryInfo) -> bool:
    """Entries dblp is likely to index: conference papers and arXiv/CS venues."""
    from paper_preflight.match import canonical_venue

    return info.entry_type in CS_ENTRY_TYPES or canonical_venue(info.venue) is not None


async def _guard(evidence: list[Evidence], call: Callable[[], Awaitable[T]]) -> T | None:
    """Run a source call; on unavailability record it on every affected entry and return None."""
    try:
        return await call()
    except SourceUnavailable as error:
        for item in evidence:
            item.mark_unavailable(error)
        return None


async def resolve(entries: list[BibEntry], sources: Sources) -> dict[str, Evidence]:
    evidence: dict[str, Evidence] = {}
    for entry in entries:
        if entry.key in evidence:
            continue  # BibTeX uses the first definition of a duplicate key (CIT002 reports it)
        evidence[entry.key] = Evidence(
            key=entry.key, info=EntryInfo.from_entry(entry), identifiers=extract_identifiers(entry)
        )

    # 1. DOIs: registration agency for all, then batched lookups per agency.
    by_doi: dict[str, list[Evidence]] = {}
    for item in evidence.values():
        for ident in item.identifiers:
            if ident.scheme == "doi":
                by_doi.setdefault(ident.value, []).append(item)
    doi_owners = [e for items in by_doi.values() for e in items]
    agencies = (
        await _guard(doi_owners, lambda: doiorg.registration_agencies(sources.doiorg, by_doi)) or {}
    )
    for doi, items in by_doi.items():
        answer = agencies.get(doi)
        for item in items:
            if answer is not None:
                item.doi_agency[doi] = answer

    crossref_dois = [d for d, a in agencies.items() if a.agency == "Crossref"]
    datacite_dois = [d for d, a in agencies.items() if a.agency == "DataCite"]
    other_dois = [
        (d, a.agency) for d, a in agencies.items() if a.agency not in (None, "Crossref", "DataCite")
    ]
    if not agencies and by_doi:  # doi.org unavailable: still try Crossref directly
        crossref_dois = list(by_doi)

    crossref_owners = [e for d in crossref_dois for e in by_doi.get(d, [])]
    datacite_owners = [e for d in datacite_dois for e in by_doi.get(d, [])]
    cr_records, dc_records, oa_records = await asyncio.gather(
        _guard(
            crossref_owners,
            lambda: crossref.works_by_doi(sources.crossref, crossref_dois, mailto=sources.mailto),
        ),
        _guard(datacite_owners, lambda: datacite.dois(sources.datacite, datacite_dois)),
        _guard(
            crossref_owners,
            lambda: openalex.works_by_doi(
                sources.openalex, crossref_dois, api_key=sources.openalex_key
            ),
        ),
    )
    for doi, record in {**(cr_records or {}), **(dc_records or {})}.items():
        for item in by_doi.get(doi, []):
            item.anchored.append(record)
    for doi, record in (oa_records or {}).items():
        for item in by_doi.get(doi, []):
            item.status_records.append(record)
    for doi, agency in other_dois:
        await _content_negotiation(doi, agency or "", by_doi.get(doi, []), sources)

    # 2. arXiv IDs (from eprint/journal/url fields and from DataCite arXiv DOIs).
    by_arxiv: dict[str, list[Evidence]] = {}
    for item in evidence.values():
        ids = {i.value for i in item.identifiers if i.scheme == "arxiv"}
        ids |= {r.identifiers["arxiv"] for r in item.anchored if "arxiv" in r.identifiers}
        for arxiv_id in ids:
            by_arxiv.setdefault(arxiv_id, []).append(item)
    arxiv_owners = [e for items in by_arxiv.values() for e in items]
    ax_records = await _guard(arxiv_owners, lambda: arxiv.by_ids(sources.arxiv, list(by_arxiv)))
    if ax_records is None and by_arxiv:
        await _arxiv_via_datacite(by_arxiv, sources)
    if ax_records is not None:
        for arxiv_id, items in by_arxiv.items():
            arxiv_record = ax_records.get(arxiv_id)
            for item in items:
                if arxiv_record is not None:
                    item.anchored.append(arxiv_record)
                else:
                    item.arxiv_missing.append(arxiv_id)

    # 3. Published versions of cited preprints via dblp (CoRR record -> venue record).
    await _published_versions(evidence, by_arxiv, ax_records or {}, sources)

    # 4. Title search for entries without any anchored record.
    # A wrong or dead identifier does not mean the work does not exist, so entries whose
    # identifiers led nowhere are searched by title as well.
    unanchored = [item for item in evidence.values() if not item.anchored and item.info.title]
    await asyncio.gather(*(_title_search(item, sources) for item in unanchored))
    return evidence


async def _arxiv_via_datacite(by_arxiv: dict[str, list[Evidence]], sources: Sources) -> None:
    """The arXiv API refused or timed out: DataCite registers every arXiv paper as
    10.48550/arXiv.<id>, so existence and metadata can still be checked. arXiv stays recorded as
    unavailable (withdrawals and earlier version titles are only known to arXiv), and an ID
    DataCite does not return is not treated as missing.
    """
    wanted = {f"10.48550/arxiv.{arxiv_id}".lower(): arxiv_id for arxiv_id in by_arxiv}
    owners = [e for items in by_arxiv.values() for e in items]
    records = await _guard(owners, lambda: datacite.dois(sources.datacite, list(wanted))) or {}
    for doi, record in records.items():
        for item in by_arxiv.get(wanted.get(doi, ""), []):
            if all(r.source_id != record.source_id for r in item.anchored):
                item.anchored.append(record)


async def _content_negotiation(
    doi: str, agency: str, owners: list[Evidence], sources: Sources
) -> None:
    record = await _guard(owners, lambda: doiorg.csl_record(sources.doiorg, doi, agency))
    if record is not None:
        for item in owners:
            item.anchored.append(record)


async def _published_versions(
    evidence: dict[str, Evidence],
    by_arxiv: dict[str, list[Evidence]],
    ax_records: dict[str, SourceRecord],
    sources: Sources,
) -> None:
    if not by_arxiv:
        return
    owners = [e for items in by_arxiv.values() for e in items]
    arxiv_dois = {f"10.48550/arxiv.{a}".lower(): a for a in by_arxiv}
    corr_pubs = await _guard(owners, lambda: dblp.by_dois(sources.dblp, list(arxiv_dois)))
    if not corr_pubs:
        return
    corr_values = list(corr_pubs.values())
    links = await _guard(owners, lambda: dblp.published_versions(sources.dblp, corr_values)) or {}
    venue_pubs = {pub for found in links.values() for pub, _, _ in found}
    records = await _guard(owners, lambda: dblp.full_records(sources.dblp, venue_pubs)) or {}
    for doi, corr_pub in corr_pubs.items():
        arxiv_id = arxiv_dois.get(doi)
        for pub, _, _ in links.get(corr_pub, []):
            record = records.get(pub.removeprefix(dblp.REC))
            if record is None:
                continue
            for item in by_arxiv.get(arxiv_id or "", []):
                item.published_versions.append(record)


async def _title_search(item: Evidence, sources: Sources) -> None:
    info = item.info
    tasks: list[Awaitable[None]] = []
    if looks_cs(info) or info.entry_type not in GREY_TYPES:
        tasks.append(_search_dblp(item, sources))
    tasks.append(_search_crossref(item, sources))
    await asyncio.gather(*tasks)


async def _search_dblp(item: Evidence, sources: Sources) -> None:
    item.searched.add("dblp")
    candidates = await _guard([item], lambda: dblp.title_candidates(sources.dblp, item.info.title))
    if candidates is None:
        return
    close = [pub for pub, title in candidates if title_score(item.info.title, title) >= 0.85][:5]
    if not close:
        item.negative.add("dblp")
        return
    records = await _guard([item], lambda: dblp.full_records(sources.dblp, close))
    item.candidates.extend((records or {}).values())


async def _search_crossref(item: Evidence, sources: Sources) -> None:
    info = item.info
    if word_count(info.title) < 3:
        return  # too little to search for meaningfully
    item.searched.add("crossref")
    surnames = " ".join(p.family for p in info.authors.people[:3])
    query = " ".join(x for x in (info.title, surnames, str(info.year or "")) if x)
    records = await _guard(
        [item],
        lambda: crossref.search_bibliographic(
            sources.crossref, query, rows=10, mailto=sources.mailto
        ),
    )
    if records is None:
        return
    close = [r for r in records if title_score(info.title, r.title) >= 0.85]
    if close:
        item.candidates.extend(close)
    else:
        item.negative.add("crossref")
