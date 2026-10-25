"""shape-decision keeps the behaviours its rewrite exists to protect.

The old skill stopped at a fixed question count and missed reversibility, release
consequences and repo rules. Issue #273's gaps on outside-service concerns and
facts research already surfaced are folded into the axis list; its closing gap check is now the cold check.
Sections are found by heading or a short distinctive phrase, never by step number,
so rewording around them does not break these tests.
"""

from __future__ import annotations

from pathlib import Path

_DIR = (
    Path(__file__).resolve().parents[4]
    / ".claude" / "plugins" / "cla" / "skills" / "shape-decision"
)
_SKILL = _DIR / "SKILL.md"
_FORM = _DIR / "references" / "question-form.md"


def _text() -> str:
    return _SKILL.read_text(encoding="utf-8")


def _section(heading: str) -> str:
    """The text from a '## heading' line to the next '## ' line."""
    text = _text()
    marker = f"## {heading}\n"
    assert marker in text, f"shape-decision lost the section {heading!r}"
    body = text[text.index(marker) + len(marker):]
    return body.split("\n## ", 1)[0]


def test_model_signal_has_three_plain_tests_and_grounds_in_instruction_files():
    start = _section("Start")
    for test in ("hard to reverse", "ship to other repos or users", "several independent constraints"):
        assert test in start, f"the model signal lost the test {test!r}"
    assert "root `CLAUDE.md`" in start and "AGENTS.md" in start, "grounding lost the instruction files"


def test_axis_list_has_three_always_axes_and_the_outside_service_items():
    axes = _section("The axis list")
    assert "The first three are always listed" in axes
    for axis in ("**Reversibility**", "**Downstream consumers**", "**Release**"):
        assert axis in axes, f"the axis list lost {axis}"
    for item in (
        "rate limits",
        "timeout and retry",
        "cost or usage caps",
        "personal data in payloads",
        "abuse and injection",
        "not deterministic",
    ):
        assert item in axes, f"the outside-service items lost {item!r}"
    assert "**Noted, not asked:**" in axes
    assert "A range or a bare question number is not evidence" in axes
    assert "if no fragment can be quoted, the axis is Partial" in axes


def test_stops_on_clarity_never_on_a_question_count():
    text = _text()
    assert "Stop on clarity, never on a question count." in text
    assert "Stop asking when every axis is Clear" in _section("Asking")
    assert "3-8" not in text and "Right-size" not in text, "a question-count target came back"


def test_cold_check_cites_a_file_read_or_an_answer():
    cold = _section("Cold check")
    assert "Assume this failed in six months" in cold
    assert "a file this run read or an answer by question number" in cold


def test_persisted_file_keeps_its_bullets_including_the_noted_lines():
    assert "list every Noted line" in _section("Decision Summary")
    persist = _section("Persisting the decision")
    for bullet in (
        "- The topic, and what was inferred if it was not given",
        "- Each question asked, the chosen option, and its one-line rationale",
        "- The final Decision Summary table, with its **Noted, not asked** lines",
        "- A short closing note on why the decision matters and the natural next step",
    ):
        assert bullet in persist, f"the persisted-file list lost {bullet!r}"


def test_core_points_to_the_form_reference_which_keeps_its_two_rules():
    assert "`references/question-form.md`" in _text()
    # the reference is read by relative path; a plugin-root variable there would not resolve
    assert "${CLAUDE_PLUGIN_ROOT}" not in _FORM.read_text(encoding="utf-8")
    form = _FORM.read_text(encoding="utf-8")
    assert "When a simpler option fully meets the stated need, recommend it" in form
    assert "from the smallest change to the largest" in form
