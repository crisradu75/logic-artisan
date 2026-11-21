"""lite-pr's bug-fix, description-rewrite and duplicate-match rules, read from its SKILL.md.

The rules are prose a model follows, so these tests read the prose: each pins the sentence that
carries the rule, so deleting it fails here.
"""

from __future__ import annotations

from pathlib import Path

_LITE_PR = Path(__file__).resolve().parents[4] / ".claude" / "plugins" / "cla" / "skills" / "lite-pr"
_SKILL = (_LITE_PR / "SKILL.md").read_text(encoding="utf-8")


def _flat(text: str) -> str:
    return " ".join(text.split())


def _line(prefix: str) -> str:
    return next(line for line in _SKILL.splitlines() if line.startswith(prefix))


# requirement: change-workflow / A bug fix starts with its regression test
def test_a_bug_fix_test_comes_in_step_1_before_the_code_change_and_records_a_missing_seam() -> None:
    step = _flat(_line("1. Make the code change."))
    assert step.index("write its regression test first") > step.index("Make the code change")
    assert "`/cla:diagnose` Phase 5" in step
    assert "only then the fix" in step
    assert "no regression test: no correct seam for <cause>" in step
    assert "`Checks:` line" in step
    assert "write no `cla.io/feedback/` file" in step


# requirement: change-workflow / A bug fix starts with its regression test
def test_a_bug_fix_test_written_after_the_fix_is_routed_to_the_stash_or_revert_check() -> None:
    step = _flat(_line("1. Make the code change."))
    assert "test comes after the fix" in step
    assert "${CLAUDE_PLUGIN_ROOT}/skills/lite-pr/references/regression-test-first.md" in step
    ref = _flat((_LITE_PR / "references" / "regression-test-first.md").read_text(encoding="utf-8"))
    assert "stash or revert the fix and watch the new test go red" in ref
    assert "non-vacuity" in ref or "not_vacuous" in ref, "the guard-shaped branch of the rule was dropped"


# requirement: change-workflow / The pull request description describes the branch as it is
def test_the_fix_round_rewrites_the_pr_description_and_keeps_the_risk_and_checks_lines() -> None:
    step = _flat(_line("3. Stage the fixed files"))
    assert "rewrite the PR description" in step
    assert "describes the branch as it is now, with no log of the review" in step
    assert "Keep the `Risk:` line on one line in its format and the `Checks:` line in its format" in step
    assert "gh pr edit --body-file" in step


# requirement: change-workflow / A duplicate match shares a concrete detail
def test_a_duplicate_match_shares_a_concrete_detail_and_is_confirmed_by_the_user() -> None:
    plan = _flat(_SKILL)
    assert "A match shares a concrete detail with the change (a function name, error text or file path), not only key words." in plan
    assert "show it and wait for their reply to confirm it" in plan


def test_the_stop_lists_name_the_git_state_halt() -> None:
    """Review of the skill found two stop lists that left out the `AskUserQuestion` halt Ship describes."""
    flat = _flat(_SKILL)
    assert flat.count("`AskUserQuestion` halt") >= 2


# requirement: change-workflow / The pull request description describes the branch as it is
def test_spec_to_pr_revise_does_not_rewrite_the_one_line_pr_body() -> None:
    """Only lite-pr rewrites the description. spec-to-pr's body is one minimal line written by Ship and
    Handoff, which keep `Stacked on #N.` and `Closes openspec/changes/<name>/.` verbatim."""
    revise = (_LITE_PR.parent / "spec-to-pr" / "references" / "revise.md").read_text(encoding="utf-8")
    assert "describes the branch as it is now" not in _flat(revise)
