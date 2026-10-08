"""Software registries: GitHub repositories, PyPI and CRAN packages (C2 in the sixth-round plan).

* Asked only about references that link to a repository or a package and that nothing else
  found: "TransformerLens" (github.com/TransformerLensOrg/TransformerLens), "LDPC: Python tools
  for low density parity check codes" (pypi.org/project/ldpc).
* A record confirms the link: the repository or package exists, and its name or description is
  the entry's title. Its owner is an account, not the people who wrote the software, so authors
  are never compared; nor is the year, since software is cited by the version used.
* A link to a repository or package that does not exist is worth a look (REF019, an info).
* GitHub allows 60 requests an hour without a token, 5,000 with one (``GITHUB_TOKEN``, sent as
  a header, never part of a cache key or a report). PyPI's JSON API and CRAN's through
  crandb.r-pkg.org (R-hub) need no account. Answers are cached like every source's.
"""

from __future__ import annotations

import re
from typing import Any

from paper_preflight.cache import EntryKind
from paper_preflight.sources.base import SourceClient, SourcePolicy
from paper_preflight.sources.record import SourceRecord, collapse

GITHUB_API = "https://api.github.com/repos"
PYPI_API = "https://pypi.org/pypi"
CRAN_API = "https://crandb.r-pkg.org"

GITHUB_POLICY = SourcePolicy(name="github", min_interval=0.5, max_concurrency=2, timeout=15.0)
PYPI_POLICY = SourcePolicy(name="pypi", min_interval=0.2, max_concurrency=2, timeout=15.0)
CRAN_POLICY = SourcePolicy(name="cran", min_interval=0.5, max_concurrency=1, timeout=15.0)

# github.com/{owner}/{repo}, pypi.org/project/{name}, cran.r-project.org/package={name} and
# cran.r-project.org/web/packages/{name}
_GITHUB = re.compile(r"github\.com/([A-Za-z0-9-]{1,39})/([A-Za-z0-9._-]{1,100})", re.I)
_PYPI = re.compile(r"pypi\.(?:org|python\.org)/(?:project|pypi)/([A-Za-z0-9._-]+)", re.I)
_CRAN = re.compile(
    r"cran\.r-project\.org/(?:package=|web/packages/)([A-Za-z][A-Za-z0-9.]*[A-Za-z0-9])", re.I
)
# github.com paths that are not repositories
_NOT_REPOS = frozenset({"orgs", "features", "topics", "sponsors", "settings", "marketplace"})


def software_links(text: str) -> list[tuple[str, str]]:
    """The repositories and packages a text links to: ("github", "owner/repo"), ("pypi",
    "name"), ("cran", "name")."""
    found: list[tuple[str, str]] = []
    for match in _GITHUB.finditer(text):
        owner, repo = match.group(1), re.sub(r"\.git$", "", match.group(2).rstrip("."))
        if owner.lower() not in _NOT_REPOS and repo:
            found.append(("github", f"{owner}/{repo}"))
    found += [("pypi", m.group(1).rstrip(".")) for m in _PYPI.finditer(text)]
    found += [("cran", m.group(1)) for m in _CRAN.finditer(text)]
    return list(dict.fromkeys(found))


def _classify(payload: Any) -> EntryKind:
    return EntryKind.POSITIVE


async def github_repo(
    client: SourceClient, full_name: str, *, token: str | None = None
) -> SourceRecord | None:
    """The repository, or None when GitHub has no such repository (404)."""
    headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    fetched = await client.get_json(f"{GITHUB_API}/{full_name}", headers=headers)
    data = fetched.data or {}
    if not data.get("full_name"):
        return None
    name = str(data["name"])
    description = collapse(str(data.get("description") or ""))
    created = str(data.get("created_at") or "")[:4]
    return SourceRecord(
        source="github",
        source_id=str(data["full_name"]),
        title=description or name,
        alt_titles=(name,),
        authors_complete=False,
        year=int(created) if created.isdigit() else None,
        work_type="software",
        identifiers={"github": str(data["full_name"])},
        url=str(data.get("html_url") or f"https://github.com/{full_name}"),
    )


async def pypi_package(client: SourceClient, name: str) -> SourceRecord | None:
    fetched = await client.get_json(f"{PYPI_API}/{name}/json")
    info = (fetched.data or {}).get("info") or {}
    if not info.get("name"):
        return None
    summary = collapse(str(info.get("summary") or ""))
    return SourceRecord(
        source="pypi",
        source_id=str(info["name"]),
        title=summary or str(info["name"]),
        alt_titles=(str(info["name"]),),
        authors_complete=False,
        work_type="software",
        identifiers={"pypi": str(info["name"])},
        url=f"https://pypi.org/project/{info['name']}/",
    )


async def cran_package(client: SourceClient, name: str) -> SourceRecord | None:
    fetched = await client.get_json(f"{CRAN_API}/{name}")
    data = fetched.data or {}
    if not data.get("Package"):
        return None
    title = collapse(str(data.get("Title") or ""))
    return SourceRecord(
        source="cran",
        source_id=str(data["Package"]),
        title=title or str(data["Package"]),
        alt_titles=(str(data["Package"]),),
        authors_complete=False,
        work_type="software",
        identifiers={"cran": str(data["Package"])},
        url=f"https://CRAN.R-project.org/package={data['Package']}",
    )
