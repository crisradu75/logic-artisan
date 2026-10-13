"""shape-decision closes the three gaps issue #273 found.

An 8-question run on an LLM-backed feature produced a Decision Summary with five
severe gaps that an independent reviewer found in one pass: no rate limit or cost
cap, no timeout or retry, personal data in logs, facts an earlier research pass had
already surfaced but nobody asked about, and a schema mismatch. The protocol now
carries an external-dependency checklist, a map of what the session already learned,
and a gap check between the summary and the offer to persist.
"""

from __future__ import annotations

from pathlib import Path

_SKILL = (
    Path(__file__).resolve().parents[4]
    / ".claude" / "plugins" / "cla" / "skills" / "shape-decision" / "SKILL.md"
)


def _text() -> str:
    return _SKILL.read_text(encoding="utf-8")


def test_an_outside_service_triggers_the_dependency_checklist():
    text = _text()
    assert "**When the topic adds a call to an outside service**" in text
    for concern in (
        "rate limits",
        "timeout and retry",
        "cost or usage caps",
        "personal data",
        "abuse and injection",
        "not deterministic",
    ):
        assert concern in text, f"the outside-service checklist lost {concern!r}"


def test_earlier_research_maps_to_a_question_or_a_note():
    assert "**Map what this session already learned.**" in _text()
    assert '"considered, not asked because …"' in _text()


def test_both_checks_run_before_the_question_set_is_formed():
    text = _text()
    form = text.index('Formulate the question set per the "Right-size the question count" rule')
    assert text.index("**When the topic adds a call to an outside service**") < form
    assert text.index("**Map what this session already learned.**") < form


def test_the_gap_check_sits_between_the_summary_and_the_persist_offer():
    text = _text()
    summary = text.index("8. **Summarize at the end.**")
    gap = text.index("9. **Look for a severe gap before offering to persist.**")
    persist = text.index("10. **Offer to persist.**")
    assert summary < gap < persist
