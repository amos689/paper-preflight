"""The pre-commit hook definitions (.pre-commit-hooks.yaml)."""

from pathlib import Path

import yaml  # installed with pre-commit (a dev dependency)

ROOT = Path(__file__).parent.parent


def test_hooks_check_the_whole_project() -> None:
    text = (ROOT / ".pre-commit-hooks.yaml").read_text(encoding="utf-8")
    hooks = {hook["id"]: hook for hook in yaml.safe_load(text)}
    assert set(hooks) == {"paper-preflight", "paper-preflight-offline"}
    for hook in hooks.values():
        assert hook["entry"].startswith("paper-preflight check")
        assert hook["pass_filenames"] is False  # one project check per commit, not per file
        assert set(hook["types_or"]) == {"tex", "bib"}
    assert "--offline" in hooks["paper-preflight-offline"]["entry"]
    assert "--offline" not in hooks["paper-preflight"]["entry"]
