"""lite-pr reviews a high-risk fix once more, and never a third time.

Decision 5 (cla.io/decisions/open-issues-2026-10-13.md): on three high-risk PRs, a
second review over fixes for Important findings found new Important defects every
time. lite-pr's Review had one pass and no re-dispatch. It now runs one more pass of
the two bug-hunters over the fix diff when the PR is high risk and step 1 fixed a
Critical or Important finding, and stops there. A low-risk fix still gets no second
pass, so the cost lands only where the defects were.
"""

from __future__ import annotations

from pathlib import Path

_SKILL = (
    Path(__file__).resolve().parents[4]
    / ".claude" / "plugins" / "cla" / "skills" / "lite-pr" / "SKILL.md"
)


def _review_step(prefix: str) -> str:
    lines = _SKILL.read_text(encoding="utf-8").splitlines()
    return next(line for line in lines if line.startswith(prefix))


def test_a_high_risk_fix_gets_one_more_pass_over_its_diff():
    step = _review_step("4. **A second pass only for a high-risk fix.**")
    assert "When this Review ran at high risk and step 1 fixed a Critical or Important finding" in step
    assert "the same reviewers once more, at the same models" in step
    assert "over the fix commit's diff only" in step


def test_high_risk_is_the_level_the_review_used_not_the_literal_line():
    """lite-pr raises a missed level and treats a missing line as high without rewriting the
    PR body, so a trigger on the literal line would skip the second pass on those PRs."""
    step = _review_step("4. **A second pass only for a high-risk fix.**")
    assert "the `Risk:` line said high, you raised it, or the line was missing" in step


def test_the_second_pass_is_the_last():
    step = _review_step("4. **A second pass only for a high-risk fix.**")
    assert "then stop: there is no third pass" in step
    assert "Otherwise do NOT re-dispatch the review agents" in step, (
        "a low-risk fix, or a clean round 1, now re-dispatches the reviewers"
    )
    text = _SKILL.read_text(encoding="utf-8")
    assert "one pass, plus one pass over the fix diff of a high-risk change; never a third." in text


def test_the_report_names_the_last_unreviewed_fix_commit():
    step = _review_step("5. **Say how big the last fix commit is against what the last pass reviewed")
    assert "nobody has read those fixes" in step
    assert "If a second pass reviewed the fixes and committed none, say that the fixes were reviewed once more" in step, (
        "a clean second pass is still reported as leaving the fixes unreviewed"
    )
