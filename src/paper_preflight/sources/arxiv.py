"""arXiv API adapter (Atom feed). One connection, at least 3 s between calls (arXiv terms).

* ``by_ids`` batches up to 50 IDs; results come back unordered and missing IDs are just absent.
* ``version_titles`` fetches every version of a paper, because titles change between versions
  (GELU) and a citation may legitimately use an older title.
* Withdrawal is only visible as free text in ``arxiv:comment``.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from collections.abc import Iterable
from typing import Any

from paper_preflight.cache import EntryKind
from paper_preflight.sources.base import PartialUnavailable, SourceClient, SourcePolicy
from paper_preflight.sources.record import Person, SourceRecord, collapse

API_URL = "https://export.arxiv.org/api/query"
BATCH = 50
NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "arxiv": "http://arxiv.org/schemas/atom",
    "opensearch": "http://a9.com/-/spec/opensearch/1.1/",
}
_ID_RE = re.compile(r"arxiv\.org/abs/(?P<id>.+?)(?P<version>v\d+)?$")
_WITHDRAWN_RE = re.compile(r"\bwithdra", re.IGNORECASE)

POLICY = SourcePolicy(name="arxiv", min_interval=3.1, max_concurrency=1, timeout=30.0)


def _text(element: ET.Element, path: str) -> str | None:
    found = element.find(path, NS)
    return collapse(found.text) if found is not None and found.text else None


def parse_feed(xml_text: str) -> list[SourceRecord]:
    root = ET.fromstring(xml_text)
    records: list[SourceRecord] = []
    for entry in root.findall("atom:entry", NS):
        raw_id = _text(entry, "atom:id") or ""
        match = _ID_RE.search(raw_id)
        if not match:
            continue  # error entries have no arXiv abs id
        base_id = match.group("id")
        version = match.group("version")
        title = _text(entry, "atom:title") or ""
        authors = tuple(
            Person.from_display(collapse(name.text or ""))
            for name in entry.findall("atom:author/atom:name", NS)
            if name.text
        )
        published = _text(entry, "atom:published") or ""
        updated = _text(entry, "atom:updated") or ""
        years = {int(d[:4]) for d in (published, updated) if d[:4].isdigit()}
        comment = _text(entry, "arxiv:comment") or ""
        journal_ref = _text(entry, "arxiv:journal_ref")
        doi = _text(entry, "arxiv:doi")
        identifiers = {"arxiv": base_id, "arxiv_doi": f"10.48550/arxiv.{base_id}".lower()}
        if version:
            identifiers["arxiv_version"] = version
        if doi:
            identifiers["doi"] = doi.lower()
        relations: dict[str, tuple[str, ...]] = {}
        if journal_ref:
            relations["journal_ref"] = (journal_ref,)
        if doi:
            relations["published_doi"] = (doi.lower(),)
        records.append(
            SourceRecord(
                source="arxiv",
                source_id=base_id,
                title=title,
                authors=authors,
                year=int(published[:4]) if published[:4].isdigit() else None,
                years=frozenset(years),
                venue="arXiv",
                work_type="preprint",
                identifiers=identifiers,
                status=frozenset({"withdrawn"}) if _WITHDRAWN_RE.search(comment) else frozenset(),
                status_sources=("arxiv:comment",) if _WITHDRAWN_RE.search(comment) else (),
                relations=relations,
                url=f"https://arxiv.org/abs/{base_id}",
            )
        )
    return records


def total_results(xml_text: str) -> int:
    root = ET.fromstring(xml_text)
    found = root.find("opensearch:totalResults", NS)
    return int(found.text) if found is not None and found.text else 0


async def _feed(client: SourceClient, params: dict[str, Any]) -> str:
    def classify(payload: Any) -> EntryKind:
        return EntryKind.POSITIVE if "<entry>" in str(payload) else EntryKind.NEGATIVE

    fetched = await client.get_text(API_URL, params=params, classify=classify)
    return str(fetched.data or "")


async def by_ids(client: SourceClient, ids: Iterable[str]) -> dict[str, SourceRecord]:
    """Latest-version records keyed by base arXiv ID (without version)."""
    unique = list(dict.fromkeys(re.sub(r"v\d+$", "", i) for i in ids))

    async def fetch_chunk(chunk: list[str]) -> dict[str, Any]:
        feed = await _feed(client, {"id_list": ",".join(chunk), "max_results": len(chunk)})
        return split_feed(feed)

    try:
        entries = await client.batch("abs", unique, fetch_chunk, chunk_size=BATCH)
    except PartialUnavailable as partial:
        raise partial.with_found(_from_entries(partial.found)) from None
    return _from_entries(entries)


def split_feed(xml_text: str) -> dict[str, str]:
    """Each entry of an Atom feed as a stand-alone feed, keyed by base arXiv ID (for caching)."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return {}
    out: dict[str, str] = {}
    for entry in root.findall("atom:entry", NS):
        match = _ID_RE.search(_text(entry, "atom:id") or "")
        if match:
            out[match.group("id")] = (
                f'<feed xmlns="{NS["atom"]}">{ET.tostring(entry, encoding="unicode")}</feed>'
            )
    return out


def _from_entries(entries: dict[str, Any]) -> dict[str, SourceRecord]:
    found: dict[str, SourceRecord] = {}
    for feed in entries.values():
        for record in parse_feed(str(feed)):
            found[record.source_id] = record
    return found


async def version_titles(client: SourceClient, base_id: str, latest: int) -> list[str]:
    """Titles of versions v1..v<latest> in order (duplicates removed)."""
    ids = ",".join(f"{base_id}v{n}" for n in range(1, latest + 1))
    feed = await _feed(client, {"id_list": ids, "max_results": latest})
    titles: list[str] = []
    for record in parse_feed(feed):
        if record.title not in titles:
            titles.append(record.title)
    return titles


async def search_title(
    client: SourceClient, title: str, *, max_results: int = 5
) -> list[SourceRecord]:
    phrase = re.sub(r"[\"()]", " ", title)
    feed = await _feed(
        client, {"search_query": f'ti:"{collapse(phrase)}"', "max_results": max_results}
    )
    return parse_feed(feed)
