"""Revise records what started each later round, and the retro judges each arm apart (#357).

Round 2 has two triggers since decision 5: a fixed Critical, or a fixed Important on a
high-risk PR. Counted together, a weak Important arm could pull the yield under half and
the retro would propose `--pr-rounds 1`, removing the Critical arm with it.
"""

from __future__ import annotations

from pathlib import Path

_SKILLS = Path(__file__).resolve().parents[4] / ".claude" / "plugins" / "cla" / "skills"


def _line(rel: str, prefix: str) -> str:
    lines = (_SKILLS / rel).read_text(encoding="utf-8").splitlines()
    found = next((line for line in lines if line.lstrip().startswith(prefix)), None)
    assert found is not None, f"{rel} lost the line starting {prefix!r}"
    return found


def test_revise_records_the_trigger_on_every_later_round():
    step = _line("spec-to-pr/references/revise.md", "4. **Record the round now:**")
    for value in ("`critical`", "`high-important`", "`reentry`", "`resume`"):
        assert value in step
    assert "On a round after the first, add `\"trigger\"`" in step


def test_the_retro_judges_each_arm_apart():
    text = (_SKILLS / "spec-to-pr-retro" / "SKILL.md").read_text(encoding="utf-8")
    assert "Judge each arm on its own, over eight or more changes in that arm" in text
    assert "- `high-important` under half: that trigger has stopped paying; propose dropping it" in text
    assert "propose nothing that would also remove the arm still paying" in text
    assert "- Both under half: round 2 has stopped paying; propose `--pr-rounds 1` as the default." in text


def test_the_schema_example_carries_a_trigger_on_round_2():
    schema = (_SKILLS / "_shared" / "references" / "run-log-schema.md").read_text(encoding="utf-8")
    assert '{"round": 2, "found": 1, "trigger": "critical"}' in schema
    assert "Round 1 never carries it." in schema
