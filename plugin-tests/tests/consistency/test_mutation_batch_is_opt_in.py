"""CLAUDE.md states that a mutation batch is opt-in, not a required step.

Owner decision, 2026-10-14: a `mutate.py` batch runs only when the owner asks for it, or
when a guard hook under `.claude/plugins/cla/hooks/` is rewritten. Breaking each review
fix by hand, once, stays required. The rule is prose that nothing compiles, and the
wording it replaced ("also run a mutation batch", a table row requiring one) read as a
requirement to every agent that opened the file. Each test below fails if that wording
comes back or if the opt-in wording is removed.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

_CLAUDE_MD = (Path(__file__).resolve().parents[3] / "CLAUDE.md").read_text(encoding="utf-8")


def _flat(text: str) -> str:
    """Collapse line wraps and list indentation so a phrase matches across them."""
    return re.sub(r"\s+", " ", text)


_BODY = _flat(_CLAUDE_MD)


def _bullet_start(body: str, at: int) -> int:
    """Index of the nearest list bullet before `at` (bold or not), or -1; flattened bullets follow a space."""
    return body.rfind(" - ", 0, at) + 1 or -1


def test_the_bullet_lookback_stops_at_a_plain_bullet() -> None:
    body = "intro - **When a batch is run** a. - plain bullet with the rule here"
    assert not body.startswith("- **", _bullet_start(body, body.index("the rule")))
    assert body.startswith("- **", _bullet_start(body, body.index(" a. ")))


def _check_4() -> str:
    start = _BODY.find("Fixing a defect a review found?")
    end = _BODY.find("Changed a function's signature?")
    assert 0 <= start < end, "CLAUDE.md check 4 or check 5 heading moved; update this slice"
    return _BODY[start:end]


def test_check_4_says_a_batch_is_opt_in() -> None:
    check = _check_4()
    assert "A mutation batch is opt-in" in check
    assert "only when the owner asks for it" in check
    assert "when a guard hook" in check
    assert "is rewritten" in check
    assert "A checker or a guard test does not trigger one" in check


def test_check_4_no_longer_requires_a_batch() -> None:
    check = _check_4()
    assert "also run a mutation batch" not in check
    assert "guard or checker lines" not in check


def test_check_4_keeps_the_by_hand_floor() -> None:
    """Dropping the opt-in must not drop the one check that stays everywhere."""
    assert "Break the fix and confirm a test fails, then restore it" in _BODY
    assert "That is the whole floor" in _BODY


def test_the_table_row_does_not_require_a_batch() -> None:
    row = next(
        (line for line in _CLAUDE_MD.splitlines() if line.startswith("| Fixing a defect a review found")),
        None,
    )
    assert row is not None, "the 'Fixing a defect a review found' table row is gone"
    assert "only when the owner asks" in row
    assert "guard hook is rewritten" in row
    # The old row required a batch for any guard hook or checker.
    assert "or checker" not in row


@pytest.mark.parametrize(
    "rule",
    [
        "`mutate.py` stays serial",
        "never run `mutate.py` while a review agent reads the same tree",
        "a clean mutation run",
        "a KILLED mutant is not a pass",
        "a SURVIVOR is not automatically a finding",
    ],
)
def test_batch_rules_apply_only_when_a_batch_is_run(rule: str) -> None:
    """Each batch-only rule is worded as conditional, so none reads as a required step."""
    hits = [m.start() for m in re.finditer(re.escape(rule), _BODY)]
    assert hits, f"CLAUDE.md no longer states {rule!r}; the rule was dropped"
    for at in hits:
        # Anchor on the nearest earlier bullet start, however long its lead-in; it must be bold.
        bullet = _bullet_start(_BODY, at)
        assert bullet >= 0 and _BODY.startswith("- **", bullet), f"{rule!r} is not inside a bold list bullet"
        assert _BODY[bullet + 4 :].startswith(
            ("When a mutation batch is run", "When a batch is run")
        ), f"{rule!r} is not worded as applying only when a batch is run"
