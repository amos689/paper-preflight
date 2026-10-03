"""The false-positive museum: real references paper-preflight once got wrong, replayed offline.

Each case (tests/fixtures/museum/cases.toml) holds one entry from an evaluation and the source
answers its check read, recorded by evals/museum.py. A fix that brings back an old false
positive, or hides a real problem, changes the rules a case produces.
"""

import json
import tomllib
from pathlib import Path
from typing import Any

import pytest

from paper_preflight.cache import Cache, EntryKind
from paper_preflight.check import VerifyOptions, run_check

MUSEUM = Path(__file__).parent / "fixtures" / "museum"
CASES: list[dict[str, Any]] = tomllib.loads((MUSEUM / "cases.toml").read_text(encoding="utf-8"))[
    "case"
]


@pytest.mark.parametrize("case", CASES, ids=[case["name"] for case in CASES])
def test_museum(case: dict[str, Any], tmp_path: Path) -> None:
    fixture = json.loads((MUSEUM / f"{case['name']}.json").read_text(encoding="utf-8"))
    cache = Cache(tmp_path / "cache.sqlite3")
    for answer in fixture["cache"]:
        cache.put(answer["source"], answer["key"], answer["payload"], EntryKind(answer["kind"]))
    cache.close()
    bib = tmp_path / "refs.bib"
    bib.write_text(fixture["bib"], encoding="utf-8")

    result = run_check(
        bib, verify=VerifyOptions(cache_path=tmp_path / "cache.sqlite3", offline=True)
    )

    rules = {
        f.rule_id
        for f in result.findings
        if f.rule_id.startswith("REF") and f.severity.value in {"warning", "error"}
    }
    assert sorted(rules) == sorted(case["expect"]), case["note"]
    (assessment,) = result.verdicts.values()
    assert "OFFLINE_MODE" not in {r.value for r in assessment.reasons}  # the recording is complete
