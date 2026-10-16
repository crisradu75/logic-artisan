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


_MARK = "\x00"


_FENCE = re.compile(r"^[ \t]*(`{3,}|~{3,})")
_THEMATIC_BREAK = re.compile(r"^ {0,3}([-*_])(?:[ \t]*\1){2,}[ \t]*$")
_LIST_MARKER = re.compile(r"^[ \t]*(?=[-*] )")


def _flat(text: str) -> str:
    """Collapse line wraps and list indentation so a phrase matches across them.

    A real list marker (a hyphen or asterisk, then a space, at the start of a line after
    optional indentation) is tagged with `_MARK` first, because flattening erases the line
    starts that tell a marker from a spaced hyphen in the middle of a sentence. A line inside
    a fenced code block, and a thematic break such as `* * *` or `- - -`, is not a marker.
    """
    lines = []
    fence = ""  # the opening fence's run of characters while inside a fenced block
    for line in text.split("\n"):
        run = _FENCE.match(line)
        if fence:
            if run and run.group(1)[0] == fence[0] and len(run.group(1)) >= len(fence) \
                    and line.strip() == run.group(1):
                fence = ""
        elif run:
            fence = run.group(1)
        elif not _THEMATIC_BREAK.match(line):
            line = _LIST_MARKER.sub(_MARK, line)
        lines.append(line)
    return re.sub(r"\s+", " ", "\n".join(lines))


_BODY = _flat(_CLAUDE_MD)


def _bullet_start(body: str, at: int) -> int:
    """Index of the nearest real list marker before `at` (bold or not), or -1."""
    mark = body.rfind(_MARK, 0, at)
    return -1 if mark < 0 else mark + 1


def test_the_bullet_lookback_stops_at_a_plain_bullet() -> None:
    body = _flat("- **When a batch is run** a.\n- plain bullet with the rule here\n")
    assert not body.startswith("- **", _bullet_start(body, body.index("the rule")))
    assert body.startswith("- **", _bullet_start(body, body.index(" a. ")))


def test_a_spaced_hyphen_mid_sentence_is_not_a_bullet() -> None:
    body = _flat("- **When a batch is run** a rule that wraps\n  across lines - with a dash here.\n")
    assert body.startswith("- **", _bullet_start(body, body.index("a dash here")))


def test_an_indented_hyphen_or_asterisk_marker_is_a_bullet() -> None:
    body = _flat("- **outer** text\n  * inner marker with the rule here\n")
    assert body.startswith("* inner", _bullet_start(body, body.index("the rule")))


def test_a_fenced_line_that_looks_like_a_bullet_is_not_one() -> None:
    text = "- **outer** text\n```text\n- fenced item\n* another\n```\n- after\n"
    body = _flat(text)
    assert _bullet_start(body, body.index("fenced item")) == body.index("- **outer**")
    assert _bullet_start(body, body.index("another")) == body.index("- **outer**")
    assert body.startswith("- after", _bullet_start(body, body.index("after")))
    # A tilde fence works the same way, and an indented fence inside a list item too.
    body = _flat("- **outer**\n  ~~~\n  - fenced\n  ~~~\n")
    assert _bullet_start(body, body.index("fenced")) == body.index("- **outer**")


def test_a_longer_closing_fence_ends_the_block_and_a_shorter_one_does_not() -> None:
    body = _flat("- **outer**\n````\n```\n- still fenced\n````\n- real\n")
    assert _bullet_start(body, body.index("still fenced")) == body.index("- **outer**")
    assert body.startswith("- real", _bullet_start(body, body.index("real")))


def test_a_thematic_break_is_not_a_bullet() -> None:
    for rule in ("* * *", "- - -", "  * * *", "***", "* * * *"):
        body = _flat(f"- **outer** text\n{rule}\nthe rule here\n")
        assert _bullet_start(body, body.index("the rule")) == body.index("- **outer**"), rule
    # A hyphen item that only looks like the start of a rule is still an item.
    body = _flat("- **outer** text\n- - nested\nthe rule here\n")
    assert body.startswith("- - nested", _bullet_start(body, body.index("the rule")))


def test_text_with_no_marker_has_no_bullet() -> None:
    body = _flat("one line - with a dash and **bold** and the rule here\n")
    assert _bullet_start(body, body.index("the rule")) == -1


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
