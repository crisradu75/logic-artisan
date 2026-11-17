"""lite-pr reviews a protected-area fix once more, and never a third time.

Principle 5 (cla.io/decisions/cla-foundation-2026-11-17.md): one review, then a stakes
filter. lite-pr's Review runs one more pass of the sizing-table reviewers over the fix
diff only when step 1 applied a fix that touches a protected area, and stops there. Any
other fix gets no second pass, so the cost lands only where a defect would cost most.
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


def test_a_protected_area_fix_gets_one_more_pass_over_its_diff():
    step = _review_step("4. **A second pass only for a protected-area fix.**")
    assert "When step 1 applied a protected-area fix" in step
    assert "the same sizing-table reviewers once more, at the same models" in step
    assert "over the fix commit's diff only" in step


def test_the_second_pass_does_not_key_on_the_risk_level_or_a_severity_label():
    """The trigger is the area a fix touches. A restored `Risk:` clause or a Critical/Important
    label would send a low-stakes fix to a second review."""
    step = _review_step("4. **A second pass only for a protected-area fix.**")
    assert "Risk:" not in step and "high risk" not in step
    assert "Critical or Important" not in step


def test_the_second_pass_is_the_last():
    step = _review_step("4. **A second pass only for a protected-area fix.**")
    assert "then stop: there is no third pass" in step
    assert "Otherwise do NOT re-dispatch the review agents" in step, (
        "a low-risk fix, or a clean round 1, now re-dispatches the reviewers"
    )
    text = _SKILL.read_text(encoding="utf-8")
    assert "one pass, plus one pass over the fix diff of a protected-area fix; never a third." in text
    assert "(a second, on the fix diff, for a protected-area fix)" in text.split("\n---", 1)[0], (
        "lite-pr's description still promises a single fix round at every risk"
    )


def test_multi_lite_settles_a_finding_on_the_combined_fix_diff():
    """With two fix commits, a fix in the first can be reworked in the second. Counting a finding
    settled because one commit touched it would let a backed-out fix pass as done."""
    loop = (_SKILL.parents[1] / "multi-lite" / "references" / "candidate-loop.md").read_text(encoding="utf-8")
    assert "the combined fix diff (the first fix commit's parent to the PR head) contains a change that addresses it" in loop
    assert "already-spent one —" not in loop, "multi-lite still says lite-pr spends a single fix round"


def test_the_report_names_the_last_unreviewed_fix_commit():
    step = _review_step("5. **Say how big the last fix commit is against what the last pass reviewed")
    assert "nobody has read those fixes" in step
    assert "If a second pass reviewed the fixes and committed none, say that the fixes were reviewed once more" in step, (
        "a clean second pass is still reported as leaving the fixes unreviewed"
    )
