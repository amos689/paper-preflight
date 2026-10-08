"""Does a venue exist? Catalogues of journals and conferences (C6 in the sixth-round plan).

Asked only about a venue an entry names for a work found as a preprint alone ("journal =
{Symposium on Regularization Techniques}" for arXiv 2602.12132, HALLMARK's invented venues).
A venue is known when one of these has it, under its name or a former one:

* OpenAlex's sources: journals, proceedings, book series and repositories;
* dblp's streams: conference series, journals and workshops it indexes;
* Crossref's works: the container of some work, as proceedings name it.

Only a venue none of them has is unknown; a source that does not answer leaves it unchecked.
"""

from __future__ import annotations

import re
from typing import Any

from paper_preflight.bib.normalize import title_key
from paper_preflight.sources import crossref, dblp
from paper_preflight.sources.base import SourceClient

OPENALEX_SOURCES = "https://api.openalex.org/sources"

# what a venue's name carries besides the venue: "Proceedings of the 2nd", "2026", "(ICLR)"
_PARENTHESES = re.compile(r"\([^()]*\)")
_NOISE = re.compile(
    r"\b(?:proceedings|proc|of|the|in|on|and|for|\d+(?:st|nd|rd|th)?|first|second|third|fourth|"
    r"fifth|sixth|seventh|eighth|ninth|tenth|eleventh|twelfth|thirteenth|fourteenth|fifteenth|"
    r"sixteenth|seventeenth|eighteenth|nineteenth|twentieth|annual|international|intl)\b"
)


def venue_core(name: str) -> str:
    """A venue's name without what varies between its mentions: "Proceedings of the 2nd
    Workshop on Domain Generalization (DG 2026)" and "Workshop on Domain Generalization" have the
    same core, "workshop domain generalization"."""
    key = title_key(_PARENTHESES.sub(" ", name))
    return " ".join(_NOISE.sub(" ", key).split())


def same_venue(named: str, found: str) -> bool:
    """The venue an entry names is one a catalogue has: the same core, or one core inside the
    other when it is long enough to name a venue ("workshop domain generalization" inside "iclr
    workshop domain generalization")."""
    a, b = venue_core(named), venue_core(found)
    if not a or not b:
        return False
    if a == b:
        return True
    shorter = min(a, b, key=len)
    # a book's title is no venue: "Adversarial Machine Learning" (Crossref's container of its
    # chapters) is not "Journal of Adversarial Machine Learning"
    return (
        len(shorter) >= 15
        and bool(_VENUE_WORD.search(shorter))
        and (f" {a} " in f" {b} " or f" {b} " in f" {a} ")
    )


def names_a_venue(name: str) -> bool:
    return bool(_VENUE_WORD.search(title_key(name)))


# what names a venue rather than a topic
_VENUE_WORD = re.compile(
    r"\b(?:journal|transactions|conference|symposium|workshop|letters|review|annals|bulletin|"
    r"magazine|congress|colloquium|forum|meeting|series|notes|reports|quarterly)\b"
)


async def openalex_names(
    client: SourceClient, name: str, *, api_key: str | None = None, mailto: str | None = None
) -> list[str]:
    params: dict[str, Any] = {
        "search": name,
        "per_page": 10,
        "select": "display_name,alternate_titles,abbreviated_title",
    }
    if api_key:
        params["api_key"] = api_key
    elif mailto:
        params["mailto"] = mailto
    fetched = await client.get_json(OPENALEX_SOURCES, params=params)
    names: list[str] = []
    for source in (fetched.data or {}).get("results") or []:
        names.append(str(source.get("display_name") or ""))
        names += [str(t) for t in source.get("alternate_titles") or []]
        if source.get("abbreviated_title"):
            names.append(str(source["abbreviated_title"]))
    return [n for n in names if n]


async def dblp_names(client: SourceClient, name: str) -> list[str]:
    """dblp's stream titles (current and former) that contain the venue's core words."""
    core = venue_core(name)
    words = [w for w in core.split() if len(w) >= 4][:4]
    if not words:
        return []
    filters = " ".join(f'FILTER(CONTAINS(LCASE(STR(?t)), "{w}"))' for w in words)
    query = (
        dblp.PREFIX + "PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>\n"
        "SELECT DISTINCT ?t WHERE { ?s a dblp:Stream . "
        "{ ?s dblp:streamTitle ?t } UNION { ?s dblp:formerStreamTitle ?t } "
        f"UNION {{ ?s rdfs:label ?t }} {filters} }} LIMIT 20"
    )
    fetched = await client.get_json(
        dblp.SPARQL_URL, params={"query": query}, headers=dblp.SPARQL_ACCEPT
    )
    bindings = ((fetched.data or {}).get("results") or {}).get("bindings") or []
    return [str(b["t"]["value"]) for b in bindings if b.get("t")]


async def crossref_containers(
    client: SourceClient, name: str, *, mailto: str | None = None
) -> list[str]:
    params: dict[str, Any] = {
        "query.container-title": name,
        "rows": 10,
        "select": "container-title,event",
    }
    if mailto:
        params["mailto"] = mailto
    fetched = await client.get_json(crossref.WORKS_URL, params=params)
    names: list[str] = []
    for item in ((fetched.data or {}).get("message") or {}).get("items") or []:
        names += [str(c) for c in item.get("container-title") or []]
        event = (item.get("event") or {}).get("name")
        if event:
            names.append(str(event))
    return names
