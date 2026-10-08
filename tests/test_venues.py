"""Venues an entry names for a work found as a preprint alone: do they exist? (C6)"""

from pathlib import Path

import pytest

from paper_preflight.bib.parse import parse_bib_text
from paper_preflight.check import VerifyOptions, verify_entries
from paper_preflight.sources.venues import same_venue, venue_core
from paper_preflight.verdict import Verdict

from .fake_web import FakeWeb


@pytest.mark.parametrize(
    ("named", "found", "same"),
    [
        ("Transactions on Machine Learning Research", "Transactions on machine learning research",
         True),
        ("Proceedings of the 40th International Conference on Machine Learning",
         "International Conference on Machine Learning", True),
        ("Workshop on Domain Generalization", "ICLR 2024 Workshop on Domain Generalization", True),
        # a book's title is no venue
        ("Journal of Adversarial Machine Learning", "Adversarial Machine Learning", False),
        ("International Conference on Quantum Machine Learning", "Quantum Machine Learning",
         False),
    ],
)  # fmt: skip
def test_the_same_venue(named: str, found: str, same: bool) -> None:
    assert same_venue(named, found) is same


def test_a_venues_core() -> None:
    assert venue_core("Proceedings of the 2nd Workshop on Domain Generalization (DG 2026)") == (
        "workshop domain generalization"
    )


GELU = """@article{gelu, title={Gaussian Error Linear Units ({GELUs})},
  author={Hendrycks, Dan and Gimpel, Kevin}, year={2016}, eprint={1606.08415},
  archivePrefix={arXiv}, journal={%s}}"""


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("venue", "reported"),
    [
        ("Symposium on Activation Functions", True),  # SYNTHETIC: in no catalogue
        # cited the way a real workshop asks to be: not looked up
        ("First Workshop on Activation Functions", False),
        ("Workshop on Activation Functions (WAF)", False),
        ("arXiv preprint arXiv:1606.08415", False),
    ],
)
async def test_a_venue_no_catalogue_has(
    recorded_web: FakeWeb, tmp_path: Path, fast: None, venue: str, reported: bool
) -> None:
    entries = parse_bib_text(GELU % venue, Path("refs.bib")).entries
    options = VerifyOptions(cache_path=tmp_path / "c.sqlite3", current_year=2026, environ={})
    _, verdicts, _ = await verify_entries(entries, options)
    rules = {f.rule_id for f in verdicts["gelu"].findings}
    assert ("REF020" in rules) is reported
    if reported:
        assert verdicts["gelu"].verdict is Verdict.METADATA_MISMATCH
