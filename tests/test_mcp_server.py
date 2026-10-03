"""The MCP server, through FastMCP's in-memory client and the recorded web (conftest.py)."""

import shutil
from pathlib import Path
from typing import Any

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

from paper_preflight.mcp_server import create_server

from .fake_web import FakeWeb

DEMO = Path(__file__).parent.parent / "examples" / "demo-paper"
pytestmark = pytest.mark.usefixtures("fast")


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    root = tmp_path / "workspace"
    shutil.copytree(DEMO, root / "paper")
    return root


async def call(root: Path, tool: str, **arguments: Any) -> Any:
    server = create_server(root, cache_path=root.parent / "cache.sqlite3")
    async with Client(server) as client:
        result = await client.call_tool(tool, arguments)
    return result.data


@pytest.mark.anyio
async def test_tools_are_few_and_read_only(workspace: Path) -> None:
    async with Client(create_server(workspace)) as client:
        tools = {tool.name: tool for tool in await client.list_tools()}
    assert set(tools) == {"preflight_check", "preflight_explain", "preflight_bib_lookup"}
    for tool in tools.values():
        assert tool.annotations is not None
        assert tool.annotations.read_only_hint is True
    assert tools["preflight_check"].annotations.open_world_hint is True  # type: ignore[union-attr]


@pytest.mark.anyio
async def test_check_the_demo_paper(workspace: Path) -> None:
    data = await call(workspace, "preflight_check", path="paper")
    summary = data["summary"]
    assert summary["complete"] is True
    assert summary["verification"] == "online"
    assert summary["verdicts"]["not_found"] == 1
    assert summary["verdicts"]["identifier_conflict"] == 1
    rules = [f["rule"] for f in data["findings"]]
    assert {"CIT001", "REF001", "REF003", "REF004"} <= set(rules)
    assert all(f["severity"] != "info" for f in data["findings"])  # info only when asked
    first = data["findings"][0]
    assert first["severity"] == "error"
    assert first["location"].startswith("paper/")  # relative to the workspace root
    assert data["next_offset"] is None


@pytest.mark.anyio
async def test_findings_come_in_pages(workspace: Path) -> None:
    page = await call(workspace, "preflight_check", path="paper", max_findings=3, include_info=True)
    assert page["returned"] == 3
    assert page["next_offset"] == 3
    rest = await call(
        workspace, "preflight_check", path="paper", offset=3, max_findings=100, include_info=True
    )
    assert rest["next_offset"] is None
    assert page["total"] == rest["total"] == 3 + rest["returned"]
    ids = [f["id"] for f in page["findings"] + rest["findings"]]
    assert len(set(ids)) == len(ids)


@pytest.mark.anyio
async def test_chinese_messages(workspace: Path) -> None:
    data = await call(workspace, "preflight_check", path="paper", lang="zh")
    assert any("均未找到" in f["message"] for f in data["findings"])


@pytest.mark.anyio
async def test_offline_check_makes_no_request(workspace: Path, recorded_web: FakeWeb) -> None:
    data = await call(workspace, "preflight_check", path="paper", offline=True)
    assert recorded_web.requests == []
    assert data["summary"]["verification"] == "offline"
    assert data["summary"]["unverified_offline"] > 0


@pytest.mark.anyio
@pytest.mark.parametrize("path", ["..", "../../etc", "/"])
async def test_paths_outside_the_workspace_are_refused(workspace: Path, path: str) -> None:
    with pytest.raises(ToolError, match="outside the workspace"):
        await call(workspace, "preflight_check", path=path)


@pytest.mark.anyio
async def test_missing_path_and_unknown_rule(workspace: Path) -> None:
    with pytest.raises(ToolError, match="does not exist"):
        await call(workspace, "preflight_check", path="no-such-paper")
    with pytest.raises(ToolError, match="Unknown rule"):
        await call(workspace, "preflight_explain", rule_id="XYZ999")


@pytest.mark.anyio
async def test_explain(workspace: Path) -> None:
    data = await call(workspace, "preflight_explain", rule_id="ref003")
    assert data["rule"] == "REF003"
    assert data["severity"] == "error"
    assert data["summary"]["zh"] == "所有来源均未找到该文献"


@pytest.mark.anyio
async def test_stdio_server_speaks_only_the_protocol(workspace: Path) -> None:
    # A real subprocess: anything printed to stdout besides MCP messages would break clients.
    import os
    import sys

    from fastmcp.client.transports import StdioTransport

    transport = StdioTransport(
        command=sys.executable,
        args=["-c", "from paper_preflight.cli import app; app()", "mcp", "--root", str(workspace)],
        env={**os.environ, "PAPER_PREFLIGHT_CACHE_DIR": str(workspace.parent / "cache")},
    )
    async with Client(transport) as client:
        names = {tool.name for tool in await client.list_tools()}
        explained = await client.call_tool("preflight_explain", {"rule_id": "CIT001"})
    assert names == {"preflight_check", "preflight_explain", "preflight_bib_lookup"}
    assert explained.data["rule"] == "CIT001"


@pytest.mark.anyio
async def test_bib_lookup_by_identifier_and_title(workspace: Path) -> None:
    found = await call(workspace, "preflight_bib_lookup", identifier="10.1109/CVPR.2016.90")
    assert found["status"] == "found"
    assert found["bibtex"].startswith("% Verified with paper-preflight against Crossref")
    assert "@inproceedings{he2016deep," in found["bibtex"]
    published = await call(workspace, "preflight_bib_lookup", identifier="arXiv:1512.03385")
    assert published["published_version_of"] == "1512.03385"
    by_title = await call(
        workspace, "preflight_bib_lookup", title="Attention Is All You Need", author="Vaswani"
    )
    assert "@inproceedings{vaswani2017attention," in by_title["bibtex"]
    missing = await call(
        workspace, "preflight_bib_lookup",
        title="Quantum Gradient Folding for Sparse Mixture-of-Experts Transformers",
    )  # fmt: skip
    assert (missing["status"], missing["bibtex"]) == ("not_found", None)


@pytest.mark.anyio
async def test_bib_lookup_needs_exactly_one_query(workspace: Path) -> None:
    with pytest.raises(ToolError, match="either"):
        await call(workspace, "preflight_bib_lookup")
    with pytest.raises(ToolError, match="not a DOI"):
        await call(workspace, "preflight_bib_lookup", identifier="hello")
