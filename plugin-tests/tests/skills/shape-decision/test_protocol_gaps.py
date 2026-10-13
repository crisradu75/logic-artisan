"""shape-decision closes the three gaps issue #273 found.

An 8-question run on an LLM-backed feature produced a Decision Summary with five
severe gaps that an independent reviewer found in one pass: no rate limit or cost
cap, no timeout or retry, personal data in logs, facts an earlier research pass had
already surfaced but nobody asked about, and a schema mismatch. The protocol now
carries an external-dependency checklist, a map of what the session already learned,
and a bounded gap check between the summary and the offer to persist.

Every concern that is not asked, whichever step drops it, becomes one labelled
**Noted, not asked** line, and that line reaches the opening, the summary and the
persisted file, so nothing drops out silently.

Steps are found by their bold titles, not their numbers, so renumbering the rules
does not break these tests.
"""

from __future__ import annotations

from pathlib import Path

_SKILL = (
    Path(__file__).resolve().parents[4]
    / ".claude" / "plugins" / "cla" / "skills" / "shape-decision" / "SKILL.md"
)
_LABEL = "**Noted, not asked**"
_OUTSIDE = "**When the topic adds a call to an outside service**"
_MAPPED = "**Map what this session already learned.**"
_ADAPTIVE = "**Adaptive flow.**"
_SUMMARY = "**Summarize at the end.**"
_GAP = "**Look for a severe gap before offering to persist.**"
_PERSIST = "**Offer to persist.**"
_OPENING = "6. State the topic"


def _text() -> str:
    return _SKILL.read_text(encoding="utf-8")


def _step(title: str) -> str:
    """From this title to the next numbered line at the same indent: one step, sub-bullets included."""
    text = _text()
    assert title in text, f"shape-decision lost the step {title!r}"
    start = text.index(title)
    rest = text[start:].splitlines()
    lines = [rest[0]]
    for line in rest[1:]:
        if not line.startswith("   "):
            break
        lines.append(line)
    return "\n".join(lines)


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
    assert "`**Noted, not asked:** <concern> — accepted or deferred, and why`" in step, (
        "a checklist item can be dismissed without a labelled, reasoned line"
    )


def test_earlier_research_maps_to_a_question_or_a_labelled_line():
    step = _step(_MAPPED)
    assert "`**Noted, not asked:** <concern> — considered, not asked because …`" in step
    assert "must not silently drop out of the question set" in step


def test_both_checks_run_before_the_question_set_is_formed():
    text = _text()
    form = text.index('Formulate the question set per the "Right-size the question count" rule')
    assert text.index(_OUTSIDE) < form
    assert text.index(_MAPPED) < form


def test_a_question_skipped_by_adaptive_flow_keeps_its_concern():
    step = _step(_ADAPTIVE)
    assert "skip them silently" not in step
    assert f"carried a concern from Getting started step 3 or 4 becomes a {_LABEL} line" in step


def test_the_opening_lists_the_noted_lines_and_names_what_was_mapped():
    step = _step(_OPENING)
    assert f"Then list the {_LABEL} lines from steps 3 and 4" in step
    assert '"Prior research: <the reads and reports mapped>", or "Prior research: none."' in step
    assert step.index("revision-support note") < step.index(_LABEL), (
        "the noted lines now sit between the topic and the revision note, against rule 7"
    )


def test_noted_lines_reach_the_summary_and_the_persisted_file():
    assert f"list every {_LABEL} line, whatever step wrote it" in _step(_SUMMARY)
    assert f"- The final Decision Summary table, with its {_LABEL} lines" in _text()


def test_the_gap_check_shows_three_probes_and_is_bounded():
    step = _step(_GAP)
    for probe in (
        "a load-bearing axis nobody asked about",
        "a decision that contradicts a fact you read",
        "a choice the code or data cannot hold as decided",
    ):
        assert probe in step, f"the gap check lost the probe {probe!r}"
    assert "Show one line for each probe, naming what you examined." in step
    assert "Only after all three lines may you say that no gap was found." in step
    assert "ask it, redraw the summary, then run this check again" in step
    assert "Run it no more than two times" in step, "the gap check can loop without end"
    assert f"or one the user declines to answer, becomes a {_LABEL} line" in step


def test_the_gap_check_sits_between_the_summary_and_the_persist_offer():
    text = _text()
    assert text.index(_SUMMARY) < text.index(_GAP) < text.index(_PERSIST)
    assert "After the gap check, ask" in _step(_PERSIST)
