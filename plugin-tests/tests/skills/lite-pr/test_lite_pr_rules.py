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
def test_a_bug_fix_follows_diagnose_phase_5_and_records_a_missing_seam_on_the_checks_line() -> None:
    para = _flat(_line("**A bug fix starts with its regression test.**"))
    assert "`/cla:diagnose` Phase 5" in para
    assert "see it fail, and only then fix" in para
    assert "no regression test: no correct seam for <cause>" in para
    assert "`Checks:` line" in para
    assert "write no `cla.io/feedback/` file" in para


# requirement: change-workflow / A bug fix starts with its regression test
def test_the_moved_test_first_reference_exists_and_is_named_by_full_path() -> None:
    assert "${CLAUDE_PLUGIN_ROOT}/skills/lite-pr/references/regression-test-first.md" in _SKILL
    ref = (_LITE_PR / "references" / "regression-test-first.md").read_text(encoding="utf-8")
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
    assert flat.count("`AskUserQuestion` halt") == 2
