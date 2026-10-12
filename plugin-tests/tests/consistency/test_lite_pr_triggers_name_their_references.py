"""lite-pr's SKILL.md keeps a trigger for each rule moved into a reference.

The Measured-by rules, the mutation gate and the /cla:diagnose escalation live in
`lite-pr/references/`, read only when SKILL.md's one-line trigger says to. Deleting
a trigger leaves the reference in place and every other guard green (the
mutation-gate guard finds its site by walking the tree), while the rule silently
stops being read. This names each trigger path and requires the file behind it.
"""

from __future__ import annotations

from pathlib import Path

import pytest

_LITE_PR = Path(__file__).resolve().parents[3] / ".claude" / "plugins" / "cla" / "skills" / "lite-pr"
_PREFIX = "${CLAUDE_PLUGIN_ROOT}/skills/lite-pr/references/"


@pytest.mark.parametrize("name", ["measured-by.md", "mutation-gate.md", "diagnose-escalation.md"])
def test_skill_md_names_each_moved_reference_by_full_path(name: str) -> None:
    skill = (_LITE_PR / "SKILL.md").read_text(encoding="utf-8")
    assert _PREFIX + name in skill, f"lite-pr/SKILL.md lost its trigger to read references/{name}"
    assert (_LITE_PR / "references" / name).is_file(), f"references/{name} is missing"
