"""Books without a DOI, confirmed by Open Library (C1)."""

from pathlib import Path

import pytest

from paper_preflight.bib.parse import parse_bib_text
from paper_preflight.check import VerifyOptions, verify_entries
from paper_preflight.sources.openlibrary import parse_doc
from paper_preflight.verdict import Verdict

from .fake_web import FakeWeb

DEEP_LEARNING = {  # Open Library's work record, trimmed (CC0)
    "key": "/works/OL17801809W", "title": "Deep Learning",
    "author_name": ["Ian Goodfellow", "Yoshua Bengio", "Aaron Courville"],
    "first_publish_year": 2016, "publish_year": [2016, 2017], "publisher": ["The MIT Press"],
}  # fmt: skip
BIB = """@book{goodfellow2016deep, title={Deep learning},
  author={Goodfellow, Ian and Bengio, Yoshua and Courville, Aaron},
  year={2016}, publisher={MIT press}}
@book{goodfellow2014deep, title={Deep learning},
  author={Goodfellow, Ian and Bengio, Yoshua and Courville, Aaron},
  year={2014}, publisher={MIT press}}
"""


def test_a_work_record() -> None:
    record = parse_doc(DEEP_LEARNING)
    assert record is not None
    assert (record.source, record.title, record.year) == ("openlibrary", "Deep Learning", 2016)
    assert record.years == {2016, 2017}
    assert [p.family for p in record.authors] == ["Goodfellow", "Bengio", "Courville"]


@pytest.mark.anyio
async def test_a_book_without_a_doi_is_confirmed_by_title_author_and_edition_year(
    recorded_web: FakeWeb, tmp_path: Path, fast: None
) -> None:
    recorded_web.openlibrary["Deep learning"] = [DEEP_LEARNING]
    entries = parse_bib_text(BIB, Path("refs.bib")).entries
    options = VerifyOptions(cache_path=tmp_path / "c.sqlite3", current_year=2026, environ={})
    _, verdicts, _ = await verify_entries(entries, options)
    found = verdicts["goodfellow2016deep"]
    assert found.verdict is Verdict.VERIFIED
    assert found.record is not None
    assert found.record.source == "openlibrary"
    # no edition of 2014: set aside, never held against the entry
    other = verdicts["goodfellow2014deep"]
    assert other.verdict is Verdict.CANNOT_DETERMINE
    assert [f.rule_id for f in other.findings] == ["REF090"]
