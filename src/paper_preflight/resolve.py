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
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass, field, replace
from typing import TypeVar, cast

import httpx

from paper_preflight.bib.ids import Identifier, extract_identifiers
from paper_preflight.bib.normalize import word_count
from paper_preflight.bib.parse import BibEntry
from paper_preflight.cache import Cache
from paper_preflight.match import TITLE_VARIANT, EntryInfo, title_score
from paper_preflight.sources import (
    arxiv,
    crossref,
    datacite,
    dblp,
    doiorg,
    openalex,
    pubmed,
    semanticscholar,
)
from paper_preflight.sources.base import (
    PartialUnavailable,
    SourceClient,
    SourcePolicy,
    SourceUnavailable,
)
from paper_preflight.sources.doiorg import AgencyAnswer
from paper_preflight.sources.record import SourceRecord

T = TypeVar("T")

CS_ENTRY_TYPES = {"inproceedings", "conference", "proceedings"}
GREY_TYPES = {"book", "booklet", "manual", "misc", "online", "software", "techreport", "report",
              "phdthesis", "mastersthesis", "thesis", "unpublished", "electronic", "standard",
              "patent", "dataset"}  # fmt: skip
# Sites whose papers the sources index: a work linked there that no source knows is missing.
# A link anywhere else (a society's own proceedings site, a lab page) may be the only copy.
INDEXED_HOSTS = (
    "doi.org", "arxiv.org", "openreview.net", "proceedings.mlr.press", "jmlr.org", "nips.cc",
    "neurips.cc", "aclanthology.org", "aclweb.org", "thecvf.com", "ecva.net", "aaai.org",
    "ijcai.org", "usenix.org", "ieee.org", "acm.org", "springer.com", "sciencedirect.com",
    "elsevier.com", "wiley.com", "nature.com", "science.org", "tandfonline.com", "sagepub.com",
    "oup.com", "cambridge.org", "iop.org", "aps.org", "aip.org", "mdpi.com", "frontiersin.org",
    "plos.org", "biorxiv.org", "medrxiv.org", "nih.gov", "europepmc.org", "adsabs.harvard.edu",
    "semanticscholar.org", "dblp.org", "openalex.org", "crossref.org", "datacite.org",
    "zenodo.org", "pnas.org", "cell.com", "jstor.org", "aanda.org",
)  # fmt: skip


def unindexed_hosts(hosts: Iterable[str]) -> list[str]:
    """The hosts no source indexes (``proceedings.spp-online.org``, not ``dl.acm.org``)."""
    return [
        host
        for host in hosts
        if not any(host == known or host.endswith(f".{known}") for known in INDEXED_HOSTS)
    ]


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
    # optional sources (Semantic Scholar) that failed: reported, but never block a verdict
    optional_unavailable: dict[str, str] = field(default_factory=dict)
    arxiv_missing: list[str] = field(default_factory=list)  # arXiv IDs that do not exist
    pmid_missing: list[str] = field(default_factory=list)  # PMIDs PubMed does not know
    pmcid_missing: list[str] = field(default_factory=list)  # PMCIDs PubMed Central does not know

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
    pubmed: SourceClient
    mailto: str | None = None
    openalex_key: str | None = None
    s2: SourceClient | None = None  # only with an API key (docs/spikes/S5)
    s2_key: str | None = None

    @classmethod
    def create(
        cls,
        http: httpx.AsyncClient,
        cache: Cache,
        *,
        offline: bool = False,
        fresh_after: float | None = None,
        environ: dict[str, str] | None = None,
    ) -> Sources:
        env = environ if environ is not None else dict(os.environ)
        s2_key = env.get("S2_API_KEY") or None

        def client(policy: SourcePolicy) -> SourceClient:
            # copy the module-level policy: a client may slow itself down during a run
            return SourceClient(
                replace(policy), http, cache, offline=offline, fresh_after=fresh_after
            )

        return cls(
            doiorg=client(doiorg.POLICY),
            crossref=client(crossref.POLICY),
            datacite=client(datacite.POLICY),
            arxiv=client(arxiv.POLICY),
            dblp=client(dblp.POLICY),
            openalex=client(openalex.POLICY),
            pubmed=client(pubmed.POLICY),
            mailto=env.get("PAPER_PREFLIGHT_EMAIL") or None,
            openalex_key=env.get("OPENALEX_API_KEY") or None,
            s2=client(semanticscholar.POLICY) if s2_key else None,
            s2_key=s2_key,
        )

    def all_clients(self) -> list[SourceClient]:
        clients = [self.doiorg, self.crossref, self.datacite, self.arxiv, self.dblp, self.openalex,
                   self.pubmed]  # fmt: skip
        return clients + ([self.s2] if self.s2 is not None else [])


def looks_cs(info: EntryInfo) -> bool:
    """Entries dblp is likely to index: conference papers and arXiv/CS venues."""
    from paper_preflight.match import canonical_venue

    return info.entry_type in CS_ENTRY_TYPES or canonical_venue(info.venue) is not None


async def _guard(
    evidence: list[Evidence],
    call: Callable[[], Awaitable[T]],
    owners_of: Callable[[str], list[Evidence]] | None = None,
) -> T | None:
    """Run a source call; on unavailability record it on the affected entries.

    A batch that answered for some identifiers (:class:`PartialUnavailable`) returns what it
    found, and only the owners of the unanswered identifiers are marked (``owners_of``).
    """
    try:
        return await call()
    except PartialUnavailable as partial:
        affected = evidence
        if owners_of is not None:
            affected = [item for key in partial.missing for item in owners_of(key)]
        for item in affected:
            item.mark_unavailable(partial)
        return cast(T, partial.found)
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

    def doi_owners_of(doi: str) -> list[Evidence]:
        return by_doi.get(doi, [])

    agencies = (
        await _guard(
            doi_owners,
            lambda: doiorg.registration_agencies(sources.doiorg, by_doi),
            owners_of=doi_owners_of,
        )
        or {}
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
    # DOIs doi.org could not route (it was unavailable for them): still try Crossref directly
    crossref_dois += [
        doi
        for doi, items in by_doi.items()
        if doi not in agencies and any("doiorg" in item.unavailable for item in items)
    ]

    crossref_owners = [e for d in crossref_dois for e in by_doi.get(d, [])]
    datacite_owners = [e for d in datacite_dois for e in by_doi.get(d, [])]
    cr_records, dc_records, oa_records = await asyncio.gather(
        _guard(
            crossref_owners,
            lambda: crossref.works_by_doi(sources.crossref, crossref_dois, mailto=sources.mailto),
            owners_of=doi_owners_of,
        ),
        _guard(
            datacite_owners,
            lambda: datacite.dois(sources.datacite, datacite_dois),
            owners_of=doi_owners_of,
        ),
        _guard(
            crossref_owners,
            lambda: openalex.works_by_doi(
                sources.openalex, crossref_dois, api_key=sources.openalex_key
            ),
            owners_of=doi_owners_of,
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
    ax_records = await _guard(
        arxiv_owners,
        lambda: arxiv.by_ids(sources.arxiv, list(by_arxiv)),
        owners_of=lambda arxiv_id: by_arxiv.get(arxiv_id, []),
    )
    # IDs arXiv did not answer for (unavailable, not "no such ID") go to DataCite instead
    unanswered = {
        arxiv_id: items
        for arxiv_id, items in by_arxiv.items()
        if (ax_records is None or arxiv_id not in ax_records)
        and any("arxiv" in item.unavailable for item in items)
    }
    if unanswered:
        await _arxiv_via_datacite(unanswered, sources)
    if ax_records is not None:
        for arxiv_id, items in by_arxiv.items():
            arxiv_record = ax_records.get(arxiv_id)
            if arxiv_record is not None:
                arxiv_record = await _with_version_titles(arxiv_record, items, sources)
                ax_records[arxiv_id] = arxiv_record
            for item in items:
                if arxiv_record is not None:
                    item.anchored.append(arxiv_record)
                elif arxiv_id not in unanswered:
                    item.arxiv_missing.append(arxiv_id)

    # 3. PMIDs: PubMed is their registry, so its record anchors the entry and a PMID it does
    # not know does not exist.
    await _pubmed(evidence, sources)

    # 4. Published versions of cited preprints via dblp (CoRR record -> venue record).
    await _published_versions(evidence, by_arxiv, ax_records or {}, sources)

    # 5. Title search for entries without any anchored record.
    # A wrong or dead identifier does not mean the work does not exist, so entries whose
    # identifiers led nowhere are searched by title as well.
    unanchored = [item for item in evidence.values() if not item.anchored and item.info.title]
    await asyncio.gather(*(_title_search(item, sources) for item in unanchored))
    await _registered_years(unanchored, sources)

    # 6. Rescue: ask Semantic Scholar about what nobody else found (only with an API key).
    if sources.s2 is not None and sources.s2_key:
        s2, key = sources.s2, sources.s2_key
        lost = [i for i in unanchored if not i.candidates and word_count(i.info.title) >= 3]
        await asyncio.gather(*(_search_s2(item, s2, key) for item in lost))
    return evidence


async def _pubmed(evidence: dict[str, Evidence], sources: Sources) -> None:
    by_pmid: dict[str, list[Evidence]] = {}
    by_pmcid: dict[str, list[Evidence]] = {}
    for item in evidence.values():
        for ident in item.identifiers:
            if ident.scheme == "pmid":
                by_pmid.setdefault(ident.value, []).append(item)
            elif ident.scheme == "pmcid":
                by_pmcid.setdefault(ident.value, []).append(item)
    if by_pmcid:
        # PubMed Central knows the PMID of its articles; their PubMed records anchor the entry
        mapped = await _guard(
            [e for items in by_pmcid.values() for e in items],
            lambda: pubmed.pmids_for_pmcids(sources.pubmed, list(by_pmcid), email=sources.mailto),
            owners_of=lambda pmcid: by_pmcid.get(pmcid, []),
        )
        for pmcid, items in by_pmcid.items() if mapped is not None else ():
            pmid = mapped.get(pmcid) if mapped is not None else None
            for item in items:
                if pmid is not None:
                    owners = by_pmid.setdefault(pmid, [])
                    if item not in owners:
                        owners.append(item)
                elif pmcid not in (mapped or {}) and "pubmed" not in item.unavailable:
                    item.pmcid_missing.append(pmcid)
    if not by_pmid:
        return
    records = await _guard(
        [e for items in by_pmid.values() for e in items],
        lambda: pubmed.by_pmids(sources.pubmed, list(by_pmid), email=sources.mailto),
        owners_of=lambda pmid: by_pmid.get(pmid, []),
    )
    if records is None:
        return
    for pmid, items in by_pmid.items():
        record = records.get(pmid)
        for item in items:
            if record is not None:
                item.anchored.append(record)
            elif "pubmed" not in item.unavailable:  # unanswered is not "no such PMID"
                item.pmid_missing.append(pmid)


async def _with_version_titles(
    record: SourceRecord, owners: list[Evidence], sources: Sources
) -> SourceRecord:
    """Add every version's title when an entry's title does not match the latest one.

    arXiv titles change between versions (GELU's v1 and v2 had another title), and an entry may
    cite any version. Only papers with several versions whose latest title disagrees with an
    entry cost the extra request. The titles end up in ``alt_titles``; a record with alt titles
    (or with a single version) is one whose every title is known.
    """
    version = record.identifiers.get("arxiv_version") or "v1"
    latest = int(version[1:]) if version[1:].isdigit() else 1
    if latest <= 1:
        return record
    if all(title_score(item.info.title, record.title) >= TITLE_VARIANT for item in owners):
        return record
    base_id = record.identifiers.get("arxiv", record.source_id)
    titles = await _guard(owners, lambda: arxiv.version_titles(sources.arxiv, base_id, latest))
    return replace(record, alt_titles=tuple(titles)) if titles else record


async def _arxiv_via_datacite(by_arxiv: dict[str, list[Evidence]], sources: Sources) -> None:
    """The arXiv API refused or timed out: DataCite registers every arXiv paper as
    10.48550/arXiv.<id>, so existence and metadata can still be checked. arXiv stays recorded as
    unavailable (withdrawals and earlier version titles are only known to arXiv), and an ID
    DataCite does not return is not treated as missing.
    """
    wanted = {f"10.48550/arxiv.{arxiv_id}".lower(): arxiv_id for arxiv_id in by_arxiv}
    owners = [e for items in by_arxiv.values() for e in items]
    records = (
        await _guard(
            owners,
            lambda: datacite.dois(sources.datacite, list(wanted)),
            owners_of=lambda doi: by_arxiv.get(wanted.get(doi, ""), []),
        )
        or {}
    )
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

    def doi_owners(doi: str) -> list[Evidence]:
        return by_arxiv.get(arxiv_dois.get(doi, ""), [])

    corr_pubs = await _guard(
        owners, lambda: dblp.by_dois(sources.dblp, list(arxiv_dois)), owners_of=doi_owners
    )
    if not corr_pubs:
        return
    corr_owners: dict[str, list[Evidence]] = {}
    for doi, corr_pub in corr_pubs.items():
        corr_owners.setdefault(corr_pub, []).extend(doi_owners(doi))
    links = (
        await _guard(
            owners,
            lambda: dblp.published_versions(sources.dblp, list(corr_owners)),
            owners_of=lambda corr: corr_owners.get(corr, []),
        )
        or {}
    )
    pub_owners: dict[str, list[Evidence]] = {}
    for corr, found in links.items():
        for pub, _, _ in found:
            pub_owners.setdefault(pub, []).extend(corr_owners.get(corr, []))
    records = (
        await _guard(
            owners,
            lambda: dblp.full_records(sources.dblp, list(pub_owners)),
            owners_of=lambda pub: pub_owners.get(pub, []),
        )
        or {}
    )
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


async def _registered_years(items: list[Evidence], sources: Sources) -> None:
    """Crossref's record for candidates whose year is a year or two off the entry's.

    dblp files a journal article under its issue's year; Crossref also knows when it appeared
    online (ACM Comput. Surv. 51(5), 10.1145/3234150: online 2018, issue 2019, dblp 2019), and
    authors cite either. One batched request for all such DOIs; if Crossref cannot answer, the
    entries are judged on what was found, and nothing is marked unavailable.
    """
    wanted: dict[str, list[Evidence]] = {}
    for item in items:
        year = item.info.year
        if year is None:
            continue
        known = {r.doi for r in item.candidates if r.source == "crossref"}
        for record in item.candidates:
            doi, years = record.doi, record.all_years
            if (
                record.source != "crossref" and doi and doi not in known and years
                and year not in years and min(abs(year - y) for y in years) <= 2
            ):  # fmt: skip
                owners = wanted.setdefault(doi, [])
                if all(owner is not item for owner in owners):
                    owners.append(item)
    if not wanted:
        return
    try:
        found = await crossref.works_by_doi(sources.crossref, list(wanted), mailto=sources.mailto)
    except PartialUnavailable as partial:
        found = cast(dict[str, SourceRecord], partial.found)
    except SourceUnavailable:
        return
    for doi, record in found.items():
        for item in wanted.get(doi, []):
            item.candidates.append(record)


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


async def _search_s2(item: Evidence, client: SourceClient, api_key: str) -> None:
    """S2 is optional: a failure is kept apart so that it never blocks a verdict."""
    try:
        record = await semanticscholar.search_match(client, item.info.title, api_key)
    except SourceUnavailable as error:
        item.optional_unavailable.setdefault(error.source, error.reason.value)
        return
    item.searched.add("s2")
    if record is not None and title_score(item.info.title, record.title) >= 0.85:
        item.candidates.append(record)
    else:
        item.negative.add("s2")
