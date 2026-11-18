"""The three places that take a rejected-alternatives snapshot forbid the `git show HEAD` form alike.

`spec-to-pr`'s Revise, `multi-spec`'s review gate and the shared review sweeps each read `design.md`
before a fix round. `git show HEAD:<path>` fails on a change dir not yet committed, and on one with
uncommitted edits it returns older text, so a remedy is judged against the wrong snapshot. One file
once softened the rule to "Avoid"; the protected reading holds in all three.
"""

from __future__ import annotations

from pathlib import Path

import pytest

_SKILLS = Path(__file__).resolve().parents[3] / ".claude" / "plugins" / "cla" / "skills"
_SITES = [
    "spec-to-pr/references/revise.md",
    "multi-spec/references/review-gate.md",
    "_shared/references/review-sweeps.md",
]


@pytest.mark.parametrize("rel", _SITES)
def test_each_snapshot_site_says_never_git_show_head(rel):
    text = (_SKILLS / rel).read_text(encoding="utf-8")
    assert "Never `git show HEAD:<path>`" in text
    assert "Avoid `git show HEAD" not in text and "Not `git show HEAD" not in text
