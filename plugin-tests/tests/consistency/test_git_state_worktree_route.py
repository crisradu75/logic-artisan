"""The git_state rules name the worktree route, and the route is written once.

`git_state.py` checks the checkout it is pointed at, `.` by default. The `cd` hook
blocks moving the shell, so an orchestrator that commits to a worktree with
`git -C <worktree>` while its session sits in the primary checkout got a false
exit 3 on a correct run (issue #290): every documented invocation omitted
`--repo-root`. The route lives once, in `bash-discipline.md`; each skill rule that
tells a run to check git state before its own commits names the flag and cites it.

lite-pr is deliberately absent. Its commit runs through `commit-push-pr` in the
session's own checkout, so `--repo-root` there would point the check at a tree
the commit does not touch.
"""

from __future__ import annotations

from pathlib import Path

import pytest

_SKILLS = Path(__file__).resolve().parents[3] / ".claude" / "plugins" / "cla" / "skills"
_DISCIPLINE = _SKILLS / "_shared" / "references" / "bash-discipline.md"
_SECTION = "## Working on a worktree you are not in"
_CITE = '"Working on a worktree you are not in"'
_RULE_FILES = ["spec-to-pr", "multi-pr", "multi-lite", "multi-spec"]


def _section(text: str) -> str:
    start = text.index(_SECTION)
    end = text.find("\n## ", start + len(_SECTION))
    return text[start:] if end == -1 else text[start:end]


def test_bash_discipline_holds_the_route():
    body = _section(_DISCIPLINE.read_text(encoding="utf-8"))
    assert "--repo-root" in body, "the route section no longer names git_state's --repo-root"
    assert "EnterWorktree" in body, (
        "the route section no longer says how to run a command that has no directory option"
    )
    assert "exit 3" in body, (
        "the route section no longer warns against using --repo-root to silence a real exit 3"
    )


@pytest.mark.parametrize("skill", _RULE_FILES)
def test_each_git_state_rule_names_the_flag_and_cites_the_route(skill):
    lines = [
        line
        for line in (_SKILLS / skill / "SKILL.md").read_text(encoding="utf-8").splitlines()
        if line.startswith("- **Verify `git_state")
    ]
    assert len(lines) == 1, f"{skill}/SKILL.md: expected one hoisted git_state rule, found {len(lines)}"
    rule = lines[0]
    assert "--repo-root" in rule, (
        f"{skill}/SKILL.md's git_state rule does not show --repo-root"
    )
    assert "bash-discipline.md" in rule and _CITE in rule, (
        f"{skill}/SKILL.md's git_state rule does not cite the worktree route"
    )
