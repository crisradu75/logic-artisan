"""The worktree route for git_state is written once, and every git_state rule cites it.

`git_state.py` checks the checkout it is pointed at, `.` by default. The `cd` hook
blocks moving the shell, so a run whose change lives in a worktree the session is not
in got a false exit 3 on a correct run (issue #290). The route lives once, in
`bash-discipline.md`: move the session in with `EnterWorktree` and `path`, and use
`--repo-root` only with `--expect-branch` and a matching `git -C`.

The hoisted rules cite that section but do not show `--repo-root` themselves. The
skills commit with plain `git` in the session's checkout, so the flag in a rule would
point the check at a tree the commit does not touch: the wrong-branch commit this
guard exists to stop, with a passing check.
"""

from __future__ import annotations

from pathlib import Path

_SKILLS = Path(__file__).resolve().parents[3] / ".claude" / "plugins" / "cla" / "skills"
_DISCIPLINE = _SKILLS / "_shared" / "references" / "bash-discipline.md"
_TITLE = "Working on a worktree you are not in"
_SECTION = f"## {_TITLE}"
_CITE = f'"{_TITLE}"'


def _section() -> str:
    text = _DISCIPLINE.read_text(encoding="utf-8")
    assert _SECTION in text, f"bash-discipline.md lost its {_SECTION!r} heading"
    start = text.index(_SECTION)
    end = text.find("\n## ", start + len(_SECTION))
    return text[start:] if end == -1 else text[start:end]


def _git_state_rules() -> dict[str, str]:
    """Every hoisted bullet in a shipped SKILL.md that tells a run to verify git_state."""
    rules = {}
    for skill_md in sorted(_SKILLS.glob("*/SKILL.md")):
        for line in skill_md.read_text(encoding="utf-8").splitlines():
            if line.startswith("- **Verify `git_state"):
                rules[skill_md.parent.name] = line
    return rules


def test_the_route_enters_the_existing_worktree():
    body = _section()
    assert "`EnterWorktree` with `path: <abs-worktree-path>`" in body, (
        "the route no longer says to enter the EXISTING worktree with EnterWorktree's path"
    )
    assert "Do not use `/cla:new-worktree` or `EnterWorktree` with `name` for this" in body, (
        "the route no longer warns that new-worktree and EnterWorktree name create a fresh tree "
        "without the change"
    )


def test_repo_root_is_bound_to_expect_branch_and_git_c():
    body = _section()
    assert "only together with `--expect-branch <branch>`" in body, (
        "--repo-root without --expect-branch skips the branch check and exits 0 on any branch"
    )
    assert "must then use `git -C` with the same absolute path" in body, (
        "nothing ties the tree git_state checks to the tree the commit writes"
    )
    assert "**Never add `--repo-root` to silence an exit 3**" in body, (
        "the warning against silencing a real wrong-branch exit 3 is gone"
    )


def test_the_rule_scan_is_not_vacuous():
    rules = _git_state_rules()
    assert {"spec-to-pr", "multi-pr", "multi-lite", "multi-spec"} <= set(rules), (
        f"expected the four chain skills' git_state rules, found {sorted(rules)}"
    )


def test_every_git_state_rule_cites_the_route_and_shows_no_repo_root():
    for skill, rule in _git_state_rules().items():
        assert "bash-discipline.md" in rule and _CITE in rule, (
            f"{skill}/SKILL.md's git_state rule does not cite the worktree route"
        )
        assert "--repo-root" not in rule, (
            f"{skill}/SKILL.md's git_state rule shows --repo-root; its commits run in the "
            "session's checkout, so the flag would check a tree the commit does not touch"
        )
