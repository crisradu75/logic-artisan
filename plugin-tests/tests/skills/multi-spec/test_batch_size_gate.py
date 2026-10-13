"""multi-spec grades the batch's total claims, not only each change on its own.

#350: the size gate graded every change alone, so a batch of individually small
changes was reviewed inline however many claims it made in total. The batch's summed
claim count (`e`, defined in review-change's checklist Step 3) now sends it to the
three-agent review at the same threshold one change uses: 25.
"""

from __future__ import annotations

from pathlib import Path

_SKILLS = Path(__file__).resolve().parents[4] / ".claude" / "plugins" / "cla" / "skills"
_GATE = _SKILLS / "multi-spec" / "references" / "review-gate.md"
_SKILL = _SKILLS / "multi-spec" / "SKILL.md"
_CHECKLIST = _SKILLS / "review-change" / "references" / "checklist.md"


def _step3() -> str:
    text = _GATE.read_text(encoding="utf-8")
    start = text.index("## Step 3")
    return text[start:text.index("\n## ", start + 1)]


def test_inline_review_needs_every_change_small_and_a_small_batch_total():
    step = _step3()
    assert "- **Every change grades small and the batch's total `e` is under 25** → no dispatch." in step
    assert "- **Any change grades large, or the batch's total `e` is 25 or more** → Step 4," in step
    assert "Record each change's grade and the batch's total `e` in the batch report." in step


def test_the_batch_threshold_is_the_single_change_threshold():
    """The batch reuses the one-change claim limit; if that limit moves, this must too."""
    assert "`e < 25`" in _CHECKLIST.read_text(encoding="utf-8"), (
        "review-change's single-change claim threshold changed; update the batch threshold "
        "in multi-spec's review-gate.md and SKILL.md to match"
    )


def test_the_skill_summary_states_the_batch_total():
    text = _SKILL.read_text(encoding="utf-8")
    assert "or the batch makes 25 or more claims in total, dispatch" in text
    assert "if all are small, review inline" not in text, (
        "the summary still says all-small means inline, ignoring the batch total"
    )
