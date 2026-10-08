"""Web pages an entry links to: gone, and never archived? (C4)"""

from pathlib import Path

import pytest

from paper_preflight.bib.parse import parse_bib_text
from paper_preflight.check import VerifyOptions, verify_entries
from paper_preflight.sources.web import public_url

from .fake_web import FakeWeb

BIB = r"""
@misc{gone, title={A Blog Post That Was Taken Down}, year={2021},
  howpublished={\url{https://blog.example-lab.org/posts/old}}}
@misc{kept, title={A Blog Post the Wayback Machine Kept}, year={2021},
  url={https://blog.example-lab.org/posts/kept}}
@misc{live, title={A Blog Post Still Online}, year={2021},
  url={https://blog.example-lab.org/posts/live}}
@misc{headless, title={A Dataset Page That Answers Only GET}, year={2021},
  url={https://data.example-lab.org/datasets/pokemon}}
"""


def test_only_public_links_are_asked_about() -> None:
    assert public_url("https://blog.example-lab.org/posts/old")
    assert not public_url("http://localhost:8000/report")
    assert not public_url("http://192.168.1.10/data.csv")
    assert not public_url("ftp://example.org/file")
    assert public_url("http://8.8.8.8/")


@pytest.mark.anyio
async def test_a_page_that_is_gone_with_no_archived_copy(
    recorded_web: FakeWeb, tmp_path: Path, fast: None
) -> None:
    recorded_web.gone |= {
        "https://blog.example-lab.org/posts/old", "https://blog.example-lab.org/posts/kept",
    }  # fmt: skip
    recorded_web.archived.add("https://blog.example-lab.org/posts/kept")
    recorded_web.head_only_404.add("https://data.example-lab.org/datasets/pokemon")
    entries = parse_bib_text(BIB, Path("refs.bib")).entries
    options = VerifyOptions(cache_path=tmp_path / "c.sqlite3", current_year=2026, environ={})
    _, verdicts, _ = await verify_entries(entries, options)
    rules = {key: sorted(f.rule_id for f in a.findings) for key, a in verdicts.items()}
    assert rules["gone"] == ["REF021", "REF090"]
    (note,) = [f for f in verdicts["gone"].findings if f.rule_id == "REF021"]
    assert note.severity.value == "info"  # web pages are never judged true or false
    assert rules["kept"] == ["REF090"]
    assert rules["live"] == ["REF090"]
    assert rules["headless"] == ["REF090"]  # HEAD said 404, GET has the last word
    # disable-sources = ["web"] in the project's settings: no link is tried
    options = VerifyOptions(
        cache_path=tmp_path / "off.sqlite3", current_year=2026, environ={},
        disabled_sources=frozenset({"web"}),
    )  # fmt: skip
    _, verdicts, _ = await verify_entries(entries, options)
    assert not any(f.rule_id == "REF021" for f in verdicts["gone"].findings)
