"""The spec-writing rules tell the author what to do with a code/spec mismatch.

Spec authoring reads `rules.specs` in `openspec/config.yaml`, which `cla-setup`
seeds. The rule that a mismatch found while writing specs is fixed in the same
change, with a regression test, must be in both copies.
"""

from __future__ import annotations

from pathlib import Path

_REPO = Path(__file__).resolve().parents[4]
_FILES = [
    _REPO / "openspec" / "config.yaml",
    _REPO / ".claude" / "plugins" / "cla" / "skills" / "cla-setup" / "SKILL.md",
]
_RULE = (
    "Fix each code and spec mismatch found while writing specs in the same change, "
    "with a regression test. File an issue only when the fix is blocked outside the repo."
)


# requirement: change-workflow / Specs follow the repo's authoring rules
def test_a_spec_code_mismatch_is_fixed_in_the_same_change():
    missing = []
    for p in _FILES:
        text = p.read_text(encoding="utf-8")
        start = text.index("\n  specs:\n")
        # The specs list runs to the next artifact key, `  tasks:`.
        specs = text[start : text.index("\n  tasks:\n", start)]
        if _RULE not in specs:
            missing.append(str(p.relative_to(_REPO)))
    assert missing == []
