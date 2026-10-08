"""paper-preflight: a pre-submission integrity gate for LaTeX papers.

    import paper_preflight
    report = paper_preflight.check_paper("paper/")

See :mod:`paper_preflight.api`. The API is imported on first use, so that the command line
starts without it.
"""

from __future__ import annotations

from typing import Any

__version__ = "0.7.0"
__all__ = ["Finding", "MatchedRecord", "Reference", "Report", "__version__", "check_paper"]

_API = frozenset({"Finding", "MatchedRecord", "Reference", "Report", "check_paper"})


def __getattr__(name: str) -> Any:
    if name in _API:
        from paper_preflight import api

        return getattr(api, name)
    raise AttributeError(f"module 'paper_preflight' has no attribute {name!r}")
