"""Set the release version everywhere it is pinned, and open its CHANGELOG section.

    uv run python scripts/bump_version.py 0.6.0

Changes ``src/paper_preflight/__init__.py``, the three versions in ``server.json`` (the
registry entry, its PyPI package and the ``paper-preflight[mcp]==`` pin), ``space/
requirements.txt``, and turns the CHANGELOG's *Unreleased* section into ``[X.Y.Z] - today``
with its compare link. tests/test_plugin_manifests.py checks that the pins agree.
"""

from __future__ import annotations

import json
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPO = "https://github.com/amos689/paper-preflight"


def replace_once(path: Path, pattern: str, replacement: str) -> None:
    text = path.read_text(encoding="utf-8")
    new, count = re.subn(pattern, replacement, text, count=1, flags=re.MULTILINE)
    if count != 1:
        raise SystemExit(f"{path.relative_to(ROOT)}: pattern not found: {pattern}")
    path.write_text(new, encoding="utf-8", newline="\n")


def main(version: str) -> None:
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise SystemExit(f"not a version: {version}")
    init = ROOT / "src" / "paper_preflight" / "__init__.py"
    previous = re.search(r'^__version__ = "(.+)"$', init.read_text(encoding="utf-8"), re.M)
    if previous is None:
        raise SystemExit("no __version__ in __init__.py")
    old = previous.group(1)
    replace_once(init, r'^__version__ = ".+"$', f'__version__ = "{version}"')

    server_path = ROOT / "server.json"
    server = json.loads(server_path.read_text(encoding="utf-8"))
    server["version"] = version
    (package,) = server["packages"]
    package["version"] = version
    for argument in package.get("runtimeArguments", []):
        if str(argument.get("value", "")).startswith("paper-preflight[mcp]=="):
            argument["value"] = f"paper-preflight[mcp]=={version}"
    server_path.write_text(json.dumps(server, indent=2) + "\n", encoding="utf-8", newline="\n")

    replace_once(
        ROOT / "space" / "requirements.txt",
        r"^paper-preflight\[pdf\]==.+$",
        f"paper-preflight[pdf]=={version}",
    )

    changelog = ROOT / "CHANGELOG.md"
    replace_once(
        changelog,
        r"^## \[Unreleased\]\n",
        f"## [Unreleased]\n\n## [{version}] - {date.today().isoformat()}\n",
    )
    replace_once(
        changelog,
        r"^\[Unreleased\]: .+$",
        f"[Unreleased]: {REPO}/compare/v{version}...HEAD\n"
        f"[{version}]: {REPO}/compare/v{old}...v{version}",
    )
    print(f"{old} -> {version}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    main(sys.argv[1])
