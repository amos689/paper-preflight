"""References too new to be indexed are searched for again on later runs (C8)."""

from pathlib import Path

import pytest

from paper_preflight.bib.parse import parse_bib_text
from paper_preflight.cache import Cache
from paper_preflight.check import TOO_NEW_SOURCE, VerifyOptions, verify_entries
from paper_preflight.verdict import Reason, Verdict

from .fake_web import FakeWeb

TITLE = "Sparse Mixtures of Linear Experts for Tabular Diffusion"  # SYNTHETIC
BIB = (
    f"@article{{new2026, title={{{TITLE}}}, author={{Doe, Jane}}, journal={{J. Tab.}}, year=2026}}"
)
RECORD = {  # SYNTHETIC: Crossref's record once the article is indexed
    "DOI": "10.1234/synthetic.2026.17", "type": "journal-article", "title": [TITLE],
    "author": [{"given": "Jane", "family": "Doe"}], "issued": {"date-parts": [[2026, 9, 30]]},
    "container-title": ["J. Tab."],
}  # fmt: skip


def searches(web: FakeWeb) -> int:
    return sum(
        "Sparse Mixtures" in r.url.params.get("query.bibliographic", "") for r in web.requests
    )


@pytest.mark.anyio
async def test_a_reference_too_new_to_be_indexed_is_searched_for_again(
    recorded_web: FakeWeb, tmp_path: Path, fast: None
) -> None:
    entries = parse_bib_text(BIB, Path("refs.bib")).entries
    cache_path = tmp_path / "cache.sqlite3"
    options = VerifyOptions(cache_path=cache_path, current_year=2026, environ={})

    _, verdicts, _ = await verify_entries(entries, options)
    assert verdicts["new2026"].verdict is Verdict.CANNOT_DETERMINE
    assert Reason.TOO_NEW in verdicts["new2026"].reasons
    asked = searches(recorded_web)

    # indexed since; the next run within a day answers from the cache, as before
    recorded_web.crossref_search["Sparse Mixtures"] = [RECORD]
    _, verdicts, _ = await verify_entries(entries, options)
    assert verdicts["new2026"].verdict is Verdict.CANNOT_DETERMINE
    assert searches(recorded_web) == asked

    # offline never asks, and keeps the mark
    offline = VerifyOptions(cache_path=cache_path, current_year=2026, environ={}, offline=True)
    _, verdicts, _ = await verify_entries(entries, offline)
    assert searches(recorded_web) == asked

    # --recheck asks again now (a day later, every run does): found, and forgotten
    recheck = VerifyOptions(cache_path=cache_path, current_year=2026, environ={}, recheck=True)
    _, verdicts, _ = await verify_entries(entries, recheck)
    assert searches(recorded_web) > asked
    assert verdicts["new2026"].verdict is Verdict.VERIFIED
    cache = Cache(cache_path)
    try:
        assert cache.get(TOO_NEW_SOURCE, f"too-new:{TITLE.lower()}") is None
    finally:
        cache.close()


@pytest.mark.anyio
async def test_a_day_later_the_search_is_asked_again(
    recorded_web: FakeWeb, tmp_path: Path, fast: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    entries = parse_bib_text(BIB, Path("refs.bib")).entries
    options = VerifyOptions(cache_path=tmp_path / "cache.sqlite3", current_year=2026, environ={})
    await verify_entries(entries, options)
    asked = searches(recorded_web)
    recorded_web.crossref_search["Sparse Mixtures"] = [RECORD]
    import paper_preflight.check as check

    now = check.time.time()
    monkeypatch.setattr(check.time, "time", lambda: now + 2 * 86_400)
    _, verdicts, _ = await verify_entries(entries, options)
    assert searches(recorded_web) > asked
    assert verdicts["new2026"].verdict is Verdict.VERIFIED
