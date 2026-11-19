"""The spec map's skill index lists every shipped skill once, and links only specs that exist.

`openspec/spec-map.md` ends with a `## Skills` table: each skill under
`.claude/plugins/cla/skills/` and the specs that cover it, or `none`. `check_spec_proof.py` checks
the links resolve; this test checks the rows match the skills on disk, so a skill added or removed
without its row fails here.
"""

from __future__ import annotations

import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
_MAP = _ROOT / "openspec" / "spec-map.md"
_SKILLS = _ROOT / ".claude" / "plugins" / "cla" / "skills"
_ROW = re.compile(r"^\| `/cla:([a-z0-9-]+)` \| (.+) \|$")


def _rows() -> dict[str, str]:
    section = _MAP.read_text(encoding="utf-8").split("\n## Skills\n", 1)
    assert len(section) == 2, "openspec/spec-map.md has no `## Skills` section"
    found: dict[str, str] = {}
    for line in section[1].split("\n## ", 1)[0].splitlines():
        m = _ROW.match(line)
        if m:
            assert m.group(1) not in found, f"{m.group(1)} has two rows"
            found[m.group(1)] = m.group(2)
    return found


def test_every_shipped_skill_has_one_row() -> None:
    shipped = {p.parent.name for p in _SKILLS.glob("*/SKILL.md")}
    assert shipped, "no shipped skill found; the test would pass on nothing"
    assert set(_rows()) == shipped


def test_each_row_links_existing_specs_or_says_none() -> None:
    for skill, cell in _rows().items():
        if cell == "none":
            continue
        names = re.findall(r"\[([a-z0-9-]+)\]\(specs/\1/spec\.md\)", cell)
        assert names, f"{skill}: {cell!r} is neither `none` nor spec links"
        for name in names:
            assert (_ROOT / "openspec" / "specs" / name / "spec.md").is_file(), f"{skill} links a missing spec {name}"
