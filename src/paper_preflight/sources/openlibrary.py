"""Open Library's book search: books that no DOI registry knows (C1 in the sixth-round plan).

* Asked only about books nothing else found: Goodfellow, Bengio and Courville's Deep Learning
  (MIT Press, 2016) and Golub and Van Loan's Matrix Computations have no DOI.
* Open Library's records are made by its readers, so a record only confirms a book: its title,
  an author and the year of one of its editions must all fit the entry, and a record that does
  not fit is set aside, never held against the entry.
* Its terms ask for cached answers and an identified User-Agent; unidentified requests are
  limited to one a second. The contact address (``PAPER_PREFLIGHT_EMAIL``) goes in the header,
  never in a cache key. Its data is CC0.
"""

from __future__ import annotations

from typing import Any

from paper_preflight.cache import EntryKind
from paper_preflight.sources.base import USER_AGENT, SourceClient, SourcePolicy
from paper_preflight.sources.record import Person, SourceRecord, collapse

SEARCH_URL = "https://openlibrary.org/search.json"
FIELDS = "key,title,subtitle,author_name,first_publish_year,publish_year,publisher,isbn"
POLICY = SourcePolicy(name="openlibrary", min_interval=1.0, max_concurrency=1, timeout=20.0)


def parse_doc(doc: dict[str, Any]) -> SourceRecord | None:
    key = str(doc.get("key") or "")
    title = collapse(str(doc.get("title") or ""))
    if not key or not title:
        return None
    subtitle = collapse(str(doc.get("subtitle") or ""))
    years = frozenset(int(y) for y in doc.get("publish_year") or [] if str(y).isdigit())
    first = doc.get("first_publish_year")
    publishers = doc.get("publisher") or []
    return SourceRecord(
        source="openlibrary",
        source_id=key,
        title=title,
        alt_titles=(f"{title}: {subtitle}",) if subtitle else (),
        authors=tuple(Person.from_display(collapse(str(n))) for n in doc.get("author_name") or []),
        authors_complete=False,
        year=int(first) if isinstance(first, int) else (min(years) if years else None),
        years=years,
        work_type="book",
        publisher=str(publishers[0]) if publishers else None,
        identifiers={"openlibrary": key},
        url=f"https://openlibrary.org{key}",
    )


def _classify(payload: Any) -> EntryKind:
    return EntryKind.SEARCH if (payload or {}).get("docs") else EntryKind.NEGATIVE


async def search_books(
    client: SourceClient,
    title: str,
    author: str | None,
    *,
    isbn: str | None = None,
    mailto: str | None = None,
) -> list[SourceRecord]:
    """Works matching an ISBN, or a title and an author's surname: five at most."""
    params: dict[str, Any] = {"fields": FIELDS, "limit": 5}
    if isbn:
        params["isbn"] = isbn
    else:
        params["title"] = title
        if author:
            params["author"] = author
    headers = {"User-Agent": f"{USER_AGENT} ({mailto})"} if mailto else None
    fetched = await client.get_json(SEARCH_URL, params=params, headers=headers, classify=_classify)
    docs = (fetched.data or {}).get("docs") or []
    return [record for record in (parse_doc(doc) for doc in docs) if record is not None]
