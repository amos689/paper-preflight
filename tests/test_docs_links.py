"""Links between the documentation pages lead somewhere: the file, and the heading."""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PAGES = sorted(
    [
        ROOT / "README.md",
        ROOT / "README.zh-CN.md",
        ROOT / "CONTRIBUTING.md",
        *(ROOT / "docs").glob("*.md"),
        *(ROOT / "docs" / "rules").glob("*.md"),
    ]
)
LINK = re.compile(r"\]\((?!https?:|mailto:)([^)\s]*)\)")


def _anchors(page: Path) -> set[str]:
    """GitHub's heading anchors: lower case, punctuation dropped, spaces as hyphens."""
    text = re.sub(r"```.*?```", "", page.read_text(encoding="utf-8"), flags=re.S)
    anchors = set()
    for heading in re.findall(r"^#+ (.+)$", text, re.M):
        slug = re.sub(r"[^\w\- ]", "", heading.strip().lower())
        anchors.add(slug.replace(" ", "-"))
    return anchors


@pytest.mark.parametrize("page", PAGES, ids=lambda p: p.relative_to(ROOT).as_posix())
def test_relative_links_resolve(page: Path) -> None:
    text = re.sub(r"```.*?```", "", page.read_text(encoding="utf-8"), flags=re.S)
    for target in LINK.findall(text):
        path, _, anchor = target.partition("#")
        linked = (page.parent / path).resolve() if path else page
        assert linked.exists(), f"{page.name}: {target}"
        if anchor and linked.suffix == ".md":
            assert anchor.lower() in _anchors(linked), f"{page.name}: {target}"
