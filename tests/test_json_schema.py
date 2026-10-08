"""The JSON report keeps to its published schema (docs/schema/check-report.schema.json)."""

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from paper_preflight.check import VerifyOptions, run_check
from paper_preflight.report.jsonout import SCHEMA_VERSION, to_json_dict

from .fake_web import FakeWeb

ROOT = Path(__file__).resolve().parent.parent
SCHEMA = json.loads((ROOT / "docs" / "schema" / "check-report.schema.json").read_text("utf-8"))
DEMO = ROOT / "examples" / "demo-paper"


def test_the_schema_is_valid_and_names_the_version() -> None:
    Draft202012Validator.check_schema(SCHEMA)
    assert SCHEMA["properties"]["schema_version"]["const"] == SCHEMA_VERSION


@pytest.mark.parametrize("offline", [False, True])
def test_a_report_keeps_to_the_schema(
    recorded_web: FakeWeb, tmp_path: Path, fast: None, offline: bool
) -> None:
    verify = VerifyOptions(cache_path=tmp_path / "c.sqlite3", offline=offline, environ={})
    payload = to_json_dict(run_check(DEMO, verify=verify))
    validator = Draft202012Validator(SCHEMA, format_checker=Draft202012Validator.FORMAT_CHECKER)
    errors = [f"{list(e.absolute_path)}: {e.message}" for e in validator.iter_errors(payload)]
    assert errors == []
    assert payload["findings"]  # the demo has findings of every severity to check


def test_an_unverified_report_keeps_to_the_schema(tmp_path: Path) -> None:
    payload = to_json_dict(run_check(DEMO))  # no verification at all
    assert payload["verification"]["mode"] == "skipped"
    assert list(Draft202012Validator(SCHEMA).iter_errors(payload)) == []
