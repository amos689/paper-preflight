"""docs/rules/ says what `explain` says: every rule has a guide and an up-to-date page."""

import importlib.util
import re
from pathlib import Path
from types import ModuleType

from paper_preflight.guides import GUIDES
from paper_preflight.rules import RULES

ROOT = Path(__file__).resolve().parent.parent


def _generator() -> ModuleType:
    spec = importlib.util.spec_from_file_location("rule_docs", ROOT / "scripts" / "rule_docs.py")
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_every_rule_has_a_guide_in_both_languages() -> None:
    assert set(GUIDES) == set(RULES)
    for rule_id, guide in GUIDES.items():
        for part in (guide.checks, guide.wrong, guide.action):
            assert part.en.strip(), rule_id
            assert part.zh.strip(), rule_id
            assert re.search(r"[一-鿿]", part.zh), rule_id  # the Chinese is Chinese


def test_the_pages_are_up_to_date() -> None:
    wanted = _generator().pages()
    on_disk = set((ROOT / "docs" / "rules").glob("*.md"))
    assert on_disk == set(wanted), "run: uv run python scripts/rule_docs.py"
    for path, text in wanted.items():
        assert path.read_text(encoding="utf-8") == text, (
            f"{path.name} is out of date: run uv run python scripts/rule_docs.py"
        )


def test_links_between_pages_resolve() -> None:
    folder = ROOT / "docs" / "rules"
    for page in folder.glob("*.md"):
        for target in re.findall(r"\]\(([^)#]+)(?:#[^)]*)?\)", page.read_text(encoding="utf-8")):
            if not target.startswith("http"):
                assert (folder / target).exists(), (page.name, target)
