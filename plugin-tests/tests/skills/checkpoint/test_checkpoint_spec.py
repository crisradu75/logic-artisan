"""The checkpoint skill states each outcome the session-records spec requires of it.

Spec: openspec/specs/session-records. The secret guard that backs the no-secrets rule is proven
under guard-hooks; this file pins the skill's own text.
"""

from __future__ import annotations

from pathlib import Path

_SKILL = Path(__file__).resolve().parents[4] / ".claude" / "plugins" / "cla" / "skills" / "checkpoint" / "SKILL.md"


def _flat() -> str:
    return " ".join(_SKILL.read_text(encoding="utf-8").split())


# requirement: session-records / A checkpoint is a resumable briefing
def test_the_briefing_has_the_six_sections_in_order_and_points_at_artifacts():
    text = _flat()
    order = ["**Where things stand**", "**Landed**", "**In flight**", "**Decided**", "**Open questions**", "**Traps**"]
    positions = [text.index(heading) for heading in order]
    assert positions == sorted(positions)
    assert "each omitted entirely if genuinely empty" in text
    assert "cla.io/checkpoints/<YYYY-MM-DD>-<slug>.md" in text
    assert "**the exact next action**" in text
    assert "Point at the commit, the PR number, the decision doc" in text
    assert "Print the path and the one-line resume instruction" in text


# requirement: session-records / A checkpoint never holds a secret
def test_the_skill_forbids_copying_a_secret_and_names_the_file_instead():
    text = _flat()
    assert "Never copy a token, key, connection string, or the contents of a `.env`" in text
    assert "Name the file, not its value" in text


# requirement: session-records / A checkpoint is checked against the tree before it is followed
def test_resuming_checks_the_checkpoint_against_the_tree_and_the_tree_wins():
    text = _flat()
    assert "verify it against the tree before acting on it" in text
    assert "`git status`/`gh pr list` are the current truth" in text
    assert "the tree wins and the checkpoint is stale — say so" in text
