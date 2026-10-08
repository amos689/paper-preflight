"""Web pages an entry links to: does the link still open, and has the Wayback Machine a copy?
(C4 in the sixth-round plan).

Web pages are never judged true or false. A link that is gone (HTTP 404 or 410) and that the
Wayback Machine never archived is worth a look, no more (REF021, an info). Anything else a page
answers (401, 403, 429, a server error, a timeout) tells nothing: many sites turn tools away.
Only the status is read: a HEAD request, confirmed by a GET whose body is never read when it
says the page is gone. No request goes to the user's own machine or network.
"""

from __future__ import annotations

import ipaddress
from typing import Any
from urllib.parse import urlsplit

from paper_preflight.sources.base import SourceClient, SourcePolicy

WAYBACK_API = "https://archive.org/wayback/available"
LINK_POLICY = SourcePolicy(name="web", min_interval=0.1, max_concurrency=4, timeout=10.0)
WAYBACK_POLICY = SourcePolicy(name="wayback", min_interval=0.5, max_concurrency=2, timeout=20.0)


def public_url(url: str) -> bool:
    """An http(s) link to a named or public host: not localhost, not a private address."""
    parts = urlsplit(url.strip())
    host = (parts.hostname or "").lower()
    if parts.scheme not in {"http", "https"} or not host or host == "localhost":
        return False
    if host.endswith((".local", ".localhost", ".internal")):
        return False
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return "." in host
    return address.is_global


async def link_gone(client: SourceClient, url: str) -> bool | None:
    """True when the page is gone (404, 410), False when it opens, None when it cannot tell."""
    status = await client.head_status(url)
    if status is None:
        return None
    if status in (404, 410):
        return True
    return False if status < 400 else None


async def archived(client: SourceClient, url: str) -> bool:
    """Whether the Wayback Machine has a copy of the page."""
    fetched = await client.get_json(WAYBACK_API, params={"url": url})
    closest: Any = (((fetched.data or {}).get("archived_snapshots") or {}).get("closest")) or {}
    return bool(closest.get("available"))
