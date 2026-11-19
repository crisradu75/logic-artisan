"""The right-model skill states each outcome the model-advice spec requires.

Spec: openspec/specs/model-advice. The skill is prose, so these tests pin the text that carries
each outcome.
"""

from __future__ import annotations

from pathlib import Path

_SKILL = Path(__file__).resolve().parents[4] / ".claude" / "plugins" / "cla" / "skills" / "right-model" / "SKILL.md"


def _flat() -> str:
    return " ".join(_SKILL.read_text(encoding="utf-8").split())


# requirement: model-advice / The cheapest tier that clears the bar is recommended
def test_five_axes_decide_the_tier_and_model_and_effort_are_named_separately():
    text = _flat()
    for axis in ("**Ambiguity**", "**Reasoning depth**", "**Stakes**", "**Scope**", "**Output shape**"):
        assert axis in text
    assert "Recommend the cheapest model and effort likely to do a described task well" in text
    assert "Name each separately, with the Step 2 signal that drove it" in text
    assert "if you cannot point to an axis, you have not classified the task yet" in text


# requirement: model-advice / The cheapest tier that clears the bar is recommended
def test_escalation_needs_a_signal_and_the_quality_floor_holds():
    text = _flat()
    assert '"it will probably get this wrong on Sonnet" justifies escalating' in text
    assert '"it would do a bit better on Opus" does not' in text
    assert "Quality floor, not a race to the bottom" in text


# requirement: model-advice / A task starts only on the user's yes
def test_the_task_is_asked_for_not_inferred_and_starts_only_after_a_yes():
    text = _flat()
    assert "Otherwise ask for it; don't infer a task from vague context" in text
    assert "Ask a short yes/no" in text
    assert "If they decline, stop after the recommendation" in text
    assert "only the user can switch the session's model and effort" in text
