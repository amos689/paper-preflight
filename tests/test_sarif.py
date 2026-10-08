import json
from pathlib import Path

import jsonschema
import pytest

from paper_preflight.check import run_check
from paper_preflight.report.sarif import to_sarif_dict

ROOT = Path(__file__).resolve().parent.parent

SCHEMA = json.loads(
    (Path(__file__).parent / "fixtures" / "schemas" / "sarif-schema-2.1.0.json").read_text(
        encoding="utf-8"
    )
)


@pytest.fixture
def project(tmp_path: Path) -> Path:
    root = tmp_path / "论文"
    root.mkdir()
    (root / "main.tex").write_text(
        "\\documentclass{article}\\begin{document}\n\\cite{a,missing}\n\\cite{missing}\n"
        "\\bibliography{refs}\\end{document}\n",
        encoding="utf-8",
    )
    (root / "refs.bib").write_text(
        "@article{a, author={A, B}, title={T}, journal={J}, year={2020}, doi={10.1/x}}\n"
        "@article{b, author={A, B}, title={U}, journal={J}, year={2020}, doi={10.1/X}}\n",
        encoding="utf-8",
    )
    return root


def test_sarif_is_schema_valid(project: Path) -> None:
    sarif = to_sarif_dict(run_check(project), uri_base=project.parent)
    jsonschema.validate(sarif, SCHEMA)


def test_sarif_content(project: Path) -> None:
    sarif = to_sarif_dict(run_check(project), uri_base=project.parent)
    run = sarif["runs"][0]
    rule_ids = [r["id"] for r in run["tool"]["driver"]["rules"]]
    assert rule_ids == sorted(rule_ids)
    for rule in run["tool"]["driver"]["rules"]:  # code scanning shows the rule's guide
        assert (ROOT / "docs" / "rules" / f"{rule['id']}.md").exists()
        assert rule["helpUri"].endswith(f"/docs/rules/{rule['id']}.md")
        assert "**What to do.**" in rule["help"]["markdown"]
    by_rule = {r["ruleId"]: r for r in run["results"]}
    undefined = by_rule["CIT001"]
    assert undefined["level"] == "error"
    location = undefined["locations"][0]["physicalLocation"]
    assert location["artifactLocation"] == {
        "uri": "%E8%AE%BA%E6%96%87/main.tex",
        "uriBaseId": "SRCROOT",
    }
    assert location["region"] == {"startLine": 2, "startColumn": 9}
    assert undefined["relatedLocations"][0]["physicalLocation"]["region"]["startLine"] == 3
    assert undefined["properties"]["bibKey"] == "missing"
    assert run["results"][-1]["level"] == "note"  # infos last
    assert all(r["ruleIndex"] == rule_ids.index(r["ruleId"]) for r in run["results"])
    assert run["originalUriBaseIds"]["SRCROOT"]["uri"].endswith("/")


def test_files_outside_base_use_absolute_uris(project: Path, tmp_path: Path) -> None:
    other_base = tmp_path / "elsewhere"
    other_base.mkdir()
    sarif = to_sarif_dict(run_check(project), uri_base=other_base)
    uri = sarif["runs"][0]["results"][0]["locations"][0]["physicalLocation"]["artifactLocation"]
    assert uri["uri"].startswith("file:///")
    assert "uriBaseId" not in uri
    jsonschema.validate(sarif, SCHEMA)
