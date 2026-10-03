"""The Claude Code plugin and marketplace manifests (docs: code.claude.com plugin reference).

`claude plugin validate --strict` needs the Claude Code CLI; these checks cover the documented
rules that matter here and keep the skill consistent with the code it describes.
"""

import json
import re
from pathlib import Path
from typing import Any

import pytest

from paper_preflight.rules import RULES

ROOT = Path(__file__).parent.parent
MARKETPLACE = ROOT / ".claude-plugin" / "marketplace.json"


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def plugin_dirs() -> list[Path]:
    return [(ROOT / p["source"]).resolve() for p in load(MARKETPLACE)["plugins"]]


def frontmatter(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    assert match, f"{path} has no frontmatter"
    fields: dict[str, str] = {}
    for line in match.group(1).splitlines():
        key, _, value = line.partition(":")
        fields[key.strip()] = value.strip()
    return fields


def test_marketplace_lists_plugins_that_exist() -> None:
    marketplace = load(MARKETPLACE)
    assert {"name", "owner", "plugins"} <= set(marketplace)
    for entry, directory in zip(marketplace["plugins"], plugin_dirs(), strict=True):
        assert entry["source"].startswith("./")
        manifest = load(directory / ".claude-plugin" / "plugin.json")
        assert manifest["name"] == entry["name"]


@pytest.mark.parametrize("directory", plugin_dirs(), ids=lambda p: p.name)
def test_plugin_has_no_bin_directory(directory: Path) -> None:
    # claude.ai and Cowork do not install a plugin with a top-level bin/ directory
    assert not (directory / "bin").exists()


@pytest.mark.parametrize("directory", plugin_dirs(), ids=lambda p: p.name)
def test_mcp_server_runs_the_mcp_command_inside_the_project(directory: Path) -> None:
    (server,) = load(directory / ".mcp.json")["mcpServers"].values()
    args = server["args"]
    assert any(arg.startswith("paper-preflight[mcp]") for arg in args)
    assert args[args.index("paper-preflight") + 1] == "mcp"
    assert args[args.index("--root") + 1] == "${CLAUDE_PROJECT_DIR}"


@pytest.mark.parametrize(
    "skill", sorted(ROOT.glob("plugins/*/skills/*/SKILL.md")), ids=lambda p: p.parent.name
)
def test_skill_frontmatter_and_references(skill: Path) -> None:
    fields = frontmatter(skill)
    assert fields["name"] == skill.parent.name
    assert re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", fields["name"])
    assert fields["description"]
    # the skill listing truncates description + when_to_use at 1,536 characters
    assert len(fields["description"]) + len(fields.get("when_to_use", "")) <= 1536
    text = skill.read_text(encoding="utf-8")
    mentioned = set(re.findall(r"\b(?:CIT|TEX|REF|RUN|CFG)\d{3}\b", text))
    assert mentioned <= set(RULES), mentioned - set(RULES)
    for tool in re.findall(r"`(preflight_\w+)`", text):
        assert tool in {"preflight_check", "preflight_explain", "preflight_bib_lookup"}, tool
