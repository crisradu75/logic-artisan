"""multi-spec grades the batch's total claims, not only each change on its own.

#350: the size gate graded every change alone, so a batch of individually small
changes was reviewed inline however many claims it made in total. The batch's summed
claim count (`e`, defined in review-change's checklist Step 3) now sends it to the
three-agent review at the same threshold one change uses: 25.
"""

from __future__ import annotations

import re
from pathlib import Path

_SKILLS = Path(__file__).resolve().parents[4] / ".claude" / "plugins" / "cla" / "skills"
_GATE = _SKILLS / "multi-spec" / "references" / "review-gate.md"
_SKILL = _SKILLS / "multi-spec" / "SKILL.md"
_CHECKLIST = _SKILLS / "review-change" / "references" / "checklist.md"


def _flat(path: Path) -> str:
    return re.sub(r"\s+", " ", path.read_text(encoding="utf-8"))


def _limit() -> int:
    """The single-change claim threshold, read from review-change's checklist."""
    found = re.findall(r"`e < (\d+)`", _CHECKLIST.read_text(encoding="utf-8"))
    assert len(found) == 1, (
        f"expected review-change's checklist to state one claim threshold `e < N`, found {found}"
    )
    return int(found[0])


def _step(text: str, heading: str) -> str:
    start = text.index(heading)
    end = text.find("## Step", start + len(heading))
    return text[start:] if end == -1 else text[start:end]


def test_the_gate_uses_the_single_change_threshold_for_the_batch_total():
    n = _limit()
    step3 = _step(_flat(_GATE), "## Step 3")
    assert f"Every change grades small and the batch's total `e` is under {n}" in step3
    assert f"Any change grades large, or the batch's total `e` is {n} or more" in step3
    assert "the batch's total `e` in the batch report" in step3


def test_the_step4_heading_names_both_triggers():
    n = _limit()
    heading = next(
        line for line in _GATE.read_text(encoding="utf-8").splitlines() if line.startswith("## Step 4")
    )
    assert f"batch total `e` is {n} or more" in heading, (
        "Step 4's heading names only the per-change trigger, contradicting Step 3"
    )


def test_the_skill_summary_states_the_batch_total():
    text = _flat(_SKILL)
    assert f"or the batch makes {_limit()} or more claims in total, dispatch" in text
    assert "if all are small, review inline" not in text, (
        "the summary still says all-small means inline, ignoring the batch total"
    )
