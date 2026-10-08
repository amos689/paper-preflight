"""Software and data, confirmed by GitHub, PyPI, CRAN, Hugging Face or OpenML (C2)."""

from pathlib import Path

import pytest

from paper_preflight.bib.parse import parse_bib_text
from paper_preflight.check import VerifyOptions, verify_entries
from paper_preflight.resolve import _names_the_software
from paper_preflight.sources.record import SourceRecord
from paper_preflight.sources.software import software_links
from paper_preflight.verdict import Verdict

from .fake_web import FakeWeb

LANGMEM = {  # SYNTHETIC, in the shape of GitHub's REST API
    "full_name": "langchain-ai/langmem", "name": "langmem",
    "description": "Long-term memory for agents", "created_at": "2025-01-15T10:00:00Z",
    "html_url": "https://github.com/langchain-ai/langmem",
}  # fmt: skip
LDPC = {"info": {"name": "ldpc", "summary": "Software for LDPC codes"}}  # SYNTHETIC
BIB = r"""
@misc{langmem2026, title={LangMem: Long-Term Memory for LLM Agents}, year={2026},
  howpublished={\url{https://github.com/langchain-ai/langmem}}}
@misc{gone2025, title={Gone: A Tool That Was Deleted}, year={2025},
  url={https://github.com/someone/gone-tool}}
@misc{roffe2022ldpc, title={LDPC: Python tools for low density parity check codes},
  author={Roffe, Joschka}, year={2022}, url={https://pypi.org/project/ldpc/}}
"""


def test_links_to_repositories_and_packages() -> None:
    text = (
        "https://github.com/TransformerLensOrg/TransformerLens, github.com/a/b.git, "
        "https://github.com/orgs/x, pypi.org/project/qecsim/, "
        "https://cran.r-project.org/package=ggplot2, cran.r-project.org/web/packages/lme4/"
    )
    assert software_links(text) == [
        ("github", "TransformerLensOrg/TransformerLens"),
        ("github", "a/b"),
        ("pypi", "qecsim"),
        ("cran", "ggplot2"),
        ("cran", "lme4"),
    ]
    hub = (
        "https://huggingface.co/meta-llama/Llama-3.2-1B, huggingface.co/datasets/HuggingFaceTB/"
        "stack-edu, https://huggingface.co/papers/2401.00001, huggingface.co/blog/smollm3, "
        "https://www.openml.org/d/41169, https://www.openml.org/search?type=data&sort=runs&id=42"
    )
    assert software_links(hub) == [
        ("huggingface", "models/meta-llama/Llama-3.2-1B"),
        ("huggingface", "datasets/HuggingFaceTB/stack-edu"),
        ("openml", "41169"),
        ("openml", "42"),
    ]


@pytest.mark.parametrize(
    ("title", "name", "description", "names"),
    [
        ("LangMem: Long-Term Memory for LLM Agents", "langmem", "", True),
        ("TransformerLens", "TransformerLens", "A library", True),
        ("NVIDIA Ising-Decoding", "Ising-Decoding", "", True),
        ("Hermes Agent: An Open-Source Agent Harness", "hermes-agent", "", True),
        ("Sampling profiler for Python programs", "py-spy",
         "Sampling profiler for Python programs", True),
        ("A Survey of Something Else", "langmem", "Long-term memory", False),
        ("tau^3-Bench: From Text-Only to Multimodal", "tau2-bench", "", False),
    ],
)  # fmt: skip
def test_the_title_names_the_software(title: str, name: str, description: str, names: bool) -> None:
    record = SourceRecord(source="github", source_id=name, title=description or name,
                          alt_titles=(name,))  # fmt: skip
    assert _names_the_software(title, record) is names


@pytest.mark.anyio
async def test_software_is_confirmed_by_its_registry(
    recorded_web: FakeWeb, tmp_path: Path, fast: None
) -> None:
    recorded_web.github["langchain-ai/langmem"] = LANGMEM
    recorded_web.pypi["ldpc"] = LDPC
    entries = parse_bib_text(BIB, Path("refs.bib")).entries
    options = VerifyOptions(cache_path=tmp_path / "c.sqlite3", current_year=2026, environ={})
    _, verdicts, _ = await verify_entries(entries, options)
    langmem = verdicts["langmem2026"]
    assert langmem.verdict is Verdict.VERIFIED
    assert langmem.record is not None
    assert langmem.record.source == "github"
    assert [f.rule_id for f in langmem.findings] == []
    assert verdicts["roffe2022ldpc"].verdict is Verdict.VERIFIED
    # a repository GitHub does not have: worth a look, nothing more
    gone = verdicts["gone2025"]
    assert gone.verdict is Verdict.CANNOT_DETERMINE
    assert sorted(f.rule_id for f in gone.findings) == ["REF019", "REF090"]
    (missing,) = [f for f in gone.findings if f.rule_id == "REF019"]
    assert missing.severity.value == "info"
    assert "someone/gone-tool" in missing.message.en


HUB_BIB = r"""
@misc{llama32, title={Llama-3.2-1B}, year={2024},
  url={https://huggingface.co/meta-llama/Llama-3.2-1B}}
@misc{stackedu, title={Stack-Edu}, year={2025},
  howpublished={\url{https://huggingface.co/datasets/HuggingFaceTB/stack-edu}}}
@misc{private, title={A Model Kept Private}, year={2025},
  url={https://huggingface.co/fictional-lab/private-model}}
@misc{helena, title={Helena Dataset}, year={2018}, url={https://www.openml.org/d/41169}}
@misc{nodata, title={A Dataset Never Uploaded}, year={2020},
  url={https://www.openml.org/d/99999999}}
"""


@pytest.mark.anyio
async def test_models_and_datasets_are_confirmed_by_their_hub(
    recorded_web: FakeWeb, tmp_path: Path, fast: None
) -> None:
    # SYNTHETIC, in the shape of the Hugging Face Hub's and OpenML's APIs
    recorded_web.huggingface["models/meta-llama/Llama-3.2-1B"] = {
        "id": "meta-llama/Llama-3.2-1B", "createdAt": "2024-09-18T15:03:14.000Z",
    }  # fmt: skip
    recorded_web.huggingface["datasets/HuggingFaceTB/stack-edu"] = {"id": "HuggingFaceTB/stack-edu"}
    recorded_web.openml["41169"] = {"id": "41169", "name": "helena"}
    entries = parse_bib_text(HUB_BIB, Path("refs.bib")).entries
    options = VerifyOptions(cache_path=tmp_path / "c.sqlite3", current_year=2026, environ={})
    _, verdicts, _ = await verify_entries(entries, options)
    for key, source, kind in [("llama32", "huggingface", "software"),
                              ("stackedu", "huggingface", "dataset"),
                              ("helena", "openml", "dataset")]:  # fmt: skip
        assert verdicts[key].verdict is Verdict.VERIFIED, key
        record = verdicts[key].record
        assert record is not None
        assert (record.source, record.work_type) == (source, kind)
    # the Hub's 401 is a private repository as well as none: never "does not exist"
    assert [f.rule_id for f in verdicts["private"].findings] == ["REF090"]
    # OpenML's "Unknown dataset" is: worth a look
    assert sorted(f.rule_id for f in verdicts["nodata"].findings) == ["REF019", "REF090"]
