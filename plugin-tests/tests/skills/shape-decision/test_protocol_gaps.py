"""shape-decision closes the three gaps issue #273 found.

An 8-question run on an LLM-backed feature produced a Decision Summary with five
severe gaps that an independent reviewer found in one pass: no rate limit or cost
cap, no timeout or retry, personal data in logs, facts an earlier research pass had
already surfaced but nobody asked about, and a schema mismatch. The protocol now
carries an external-dependency checklist, a map of what the session already learned,
and a gap check between the summary and the offer to persist. A concern noted but not
asked stays in the summary and in the persisted file, so nothing drops out silently.

Steps are found by their bold titles, not their numbers, so renumbering the rules
does not break these tests.
"""

from __future__ import annotations

from pathlib import Path

_SKILL = (
    Path(__file__).resolve().parents[4]
    / ".claude" / "plugins" / "cla" / "skills" / "shape-decision" / "SKILL.md"
)
_OUTSIDE = "**When the topic adds a call to an outside service**"
_MAPPED = "**Map what this session already learned.**"
_SUMMARY = "**Summarize at the end.**"
_GAP = "**Look for a severe gap before offering to persist.**"
_PERSIST = "**Offer to persist.**"


def _text() -> str:
    return _SKILL.read_text(encoding="utf-8")


def _step(title: str) -> str:
    """The one line that starts with this bold title."""
    text = _text()
    assert title in text, f"shape-decision lost the step {title!r}"
    start = text.index(title)
    end = text.find("\n", start)
    return text[start:] if end == -1 else text[start:end]


def test_an_outside_service_triggers_the_dependency_checklist():
    step = _step(_OUTSIDE)
    for concern in (
        "rate limit",
        "timeout and retry",
        "cost or usage caps",
        "personal data",
        "abuse and injection",
        "not deterministic",
    ):
        assert concern in step, f"the outside-service checklist lost {concern!r}"
    assert "or a one-line note that it is accepted or deferred and why" in step, (
        "a checklist item can be dismissed without a recorded reason"
    )


def test_earlier_research_maps_to_a_question_or_a_note():
    step = _step(_MAPPED)
    assert '"considered, not asked because …"' in step
    assert "must not silently drop out of the question set" in step


def test_both_checks_run_before_the_question_set_is_formed():
    text = _text()
    form = text.index('Formulate the question set per the "Right-size the question count" rule')
    assert text.index(_OUTSIDE) < form
    assert text.index(_MAPPED) < form


def test_noted_concerns_reach_the_opening_the_summary_and_the_file():
    text = _text()
    assert 'say "Prior research: none."' in text, (
        "a skipped research map looks the same as an empty one"
    )
    assert "list every **Noted, not asked** line from Getting started steps 3 and 4" in _step(
        _SUMMARY
    ), "deferred concerns no longer reach the Decision Summary"
    assert "- The final Decision Summary table, with its Noted, not asked lines" in text, (
        "deferred concerns no longer reach the persisted decisions file"
    )


def test_the_gap_check_shows_its_probes_and_loops_back():
    step = _step(_GAP)
    assert "show one line for each, naming what you examined" in step, (
        "the gap check can be satisfied by a bare 'no gaps found'"
    )
    assert "cannot hold as decided" in step, "the schema-mismatch probe is gone"
    assert "ask it, redraw the summary, then run this check again" in step
    assert "Only after all three lines may you say that no gap was found" in step


def test_the_gap_check_sits_between_the_summary_and_the_persist_offer():
    text = _text()
    assert text.index(_SUMMARY) < text.index(_GAP) < text.index(_PERSIST)
    assert "After the gap check, ask" in _step(_PERSIST)
