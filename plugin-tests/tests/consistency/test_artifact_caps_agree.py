"""The artifact caps are stated where authors and reviewers read them.

A change's proposal, design and tasks have word caps, and a task names no line
number. The caps live in the rules OpenSpec injects (`openspec/config.yaml`, seeded
by `cla-setup`; `test_cla_setup_rules_match_config.py` pins those two as identical)
and in the `review-change` checklist, whose findings the rules back. The checklist
is prose a model reads, so this pins what text can show: each limit is stated on
both sides, and the earlier "one page" and "line-number drift" wordings are gone.
"""

from __future__ import annotations

import re
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
_CONFIG = _REPO / "openspec" / "config.yaml"
_CHECKLIST = _REPO / ".claude/plugins/cla/skills/review-change/references/checklist.md"


def _rules(artifact: str) -> str:
    text = _CONFIG.read_text(encoding="utf-8")
    match = re.search(rf"^  {artifact}:\n((?:    .*\n)+)", text.replace("\r\n", "\n"), re.M)
    assert match, f"openspec/config.yaml: no rules.{artifact} block"
    return match.group(1)


def _checklist() -> str:
    return _CHECKLIST.read_text(encoding="utf-8").replace("\r\n", "\n")


def test_the_rules_state_each_cap():
    assert "about 400 words" in _rules("proposal")
    assert "about 800 words" in _rules("design")
    tasks = _rules("tasks")
    assert "about 40 words" in tasks
    assert "one behaviour" in tasks
    assert "no file path with a line number" in tasks


def test_the_checklist_flags_a_task_that_names_a_line():
    text = _checklist()
    # `0e` was the line-number drift check, which read the cited line to confirm it.
    assert "Line-number drift" not in text
    line = next(ln for ln in text.splitlines() if ln.startswith("0e. "))
    assert "names a line" in line
    assert "`file.py:12`" in line
    assert "**Important**" in line


def test_the_checklist_flags_each_over_cap_artifact():
    size = next(ln for ln in _checklist().splitlines() if ln.startswith("- **Size.**"))
    assert "proposal over about 400 words" in size
    assert "design.md over about 800" in size
    assert "task over about 40 words" in size
    assert "one page" not in size
