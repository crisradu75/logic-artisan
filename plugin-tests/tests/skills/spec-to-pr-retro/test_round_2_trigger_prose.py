"""Revise records what started each later round, and the retro judges each arm apart (#357).

Round 2 has one trigger since principle 5 (2026-11-17): a fix that touches a protected area.
A re-entry on still-open findings is a second kind of round. The retro judges each arm apart,
so a weak re-entry arm cannot hide or drag down the protected arm.
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
    for value in ("`protected`", "`reentry`", "`unknown`"):
        assert value in step
    assert "On a round after the first, add `\"trigger\"`" in step


def test_the_retro_judges_each_arm_apart():
    text = (_SKILLS / "spec-to-pr-retro" / "SKILL.md").read_text(encoding="utf-8")
    assert "An arm is **judged** once it holds eight or more changes" in text
    assert "If the `protected` arm is judged and under half, round 2 has stopped paying: propose `--pr-rounds 1`" in text
    assert "Otherwise report the counts only and propose nothing" in text
    assert "first rule that matches" not in text
    assert "The totals are not a fallback" in text
    assert "the arms can add up to more than the total" in text


def test_the_schema_example_carries_a_trigger_on_round_2():
    schema = (_SKILLS / "_shared" / "references" / "run-log-schema.md").read_text(encoding="utf-8")
    assert '{"round": 2, "found": 1, "trigger": "protected"}' in schema
    assert "Round 1 never carries it, and the check refuses a later round without it." in schema


def test_revise_states_the_trigger_precedence_and_forbids_dropping_it():
    step = _line("spec-to-pr/references/revise.md", "4. **Record the round now:**")
    assert "taking the first that applies: `protected` if the round before applied a protected-area fix; else `reentry`" in step
    assert "never drop the field to clear a refusal" in step


def test_handoff_answers_a_trigger_refusal_with_unknown_never_a_guess():
    step = _line("spec-to-pr/references/handoff.md", "**`log_run.py` refuses a record off the shape**")
    assert 'gets `"trigger": "unknown"` on that round: never guess `protected`' in step


def test_every_writer_trigger_is_documented():
    import log_run

    schema = (_SKILLS / "_shared" / "references" / "run-log-schema.md").read_text(encoding="utf-8")
    step = _line("spec-to-pr/references/revise.md", "4. **Record the round now:**")
    for value in log_run.ROUND_TRIGGERS:
        assert f"`{value}`" in schema and f"`{value}`" in step, value
