"""The chain skills and right-model no longer contradict each other or point at nothing.

Each test pins one blocking defect a plugin analysis found. Prose has no compiler, so a test
reads the sentence that was wrong and the sentence that replaced it.
"""

from __future__ import annotations

from pathlib import Path

_SKILLS = Path(__file__).resolve().parents[4] / ".claude" / "plugins" / "cla" / "skills"


def _flat(rel: str) -> str:
    return " ".join((_SKILLS / rel).read_text(encoding="utf-8").split())


def test_multi_lite_sends_protected_changes_not_lite_ones_to_spec_to_pr():
    text = _flat("multi-lite/SKILL.md")
    assert "A change that touches a protected area belongs on `spec-to-pr`" in text
    assert "such a change belongs on `spec-to-pr`" not in text


def test_right_model_does_not_deny_the_dispatches_multi_pr_makes():
    right = _flat("right-model/SKILL.md")
    multi_pr = _flat("multi-pr/SKILL.md")
    assert "never dispatches an `Agent` itself" not in right
    assert "`multi-pr` runs whole `spec-to-pr` runs" in right
    assert "not routed per" in right or "never routed per" in right
    # the fact the old sentence contradicted still stands
    assert "Delegate bulk raw-material handling" in multi_pr


def test_multi_spec_points_at_nothing_that_does_not_exist():
    text = _flat("multi-spec/SKILL.md")
    assert "noted above" not in text
    assert "deleted unread" not in text


def test_the_shared_turn_liveness_rule_exists_and_each_chain_skill_points_at_it():
    shared = _SKILLS / "_shared" / "references" / "turn-liveness.md"
    assert shared.is_file()
    body = " ".join(shared.read_text(encoding="utf-8").split())
    assert "pending event" in body and "same message" in body and "exactly two cases" in body
    pointer = "${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/turn-liveness.md"
    for skill in ("multi-lite", "multi-pr", "multi-spec"):
        assert pointer in _flat(f"{skill}/SKILL.md"), skill


def test_no_shipped_file_cites_a_sentence_that_moved_to_turn_liveness():
    for path in _SKILLS.rglob("*.md"):
        text = " ".join(path.read_text(encoding="utf-8").split())
        assert 'SKILL.md" "Never end a turn' not in text, path
        assert '`multi-lite/SKILL.md` "Never end' not in text, path
    merge = _flat("_shared/references/chain-merge.md")
    assert "`_shared/references/turn-liveness.md` \"A watchdog\" says why `python3`" in merge
    assert "## A watchdog" in _flat("_shared/references/turn-liveness.md").replace("# turn", "# turn")


def test_right_model_names_no_unverified_keyword():
    assert "ultrathink" not in _flat("right-model/SKILL.md")


def test_multi_pr_lists_the_cite_script_and_keeps_the_blocker_list_in_the_loop_reference():
    skill = _flat("multi-pr/SKILL.md")
    assert "scripts/check_cite_drift.py` — the once-per-change cite recheck" in skill
    loop = _flat("multi-pr/references/change-loop.md")
    assert "## Mid-chain blockers" in loop
    assert "(f) a change that cannot be implemented as written" in loop
    assert "(f) a change that cannot be implemented as written" not in skill
