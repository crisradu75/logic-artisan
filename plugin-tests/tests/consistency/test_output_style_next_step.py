"""The output style's closing `[y/n]` line names its item and binds a bare "y" to it.

Issue #449 reports both failures: a question that pointed at "that PR" with several items in
flight, and a bare "y" taken as approval for an older open question. The style loads on every
reply in every repo, so the rule lives there.
"""

from __future__ import annotations

from pathlib import Path

_STYLE = Path(__file__).resolve().parents[3] / ".claude" / "plugins" / "cla" / "output-styles" / "CLA.md"


def _section() -> str:
    text = _STYLE.read_text(encoding="utf-8")
    start = text.index("## The one recap that stays")
    end = text.index("## Length and structure", start)
    return " ".join(text[start:end].split())


def test_the_next_step_line_names_its_item_and_what_yes_does() -> None:
    section = _section()
    assert 'names the item by its full title and says what "yes" does' in section
    assert "An item with no title is named by its number or path." in section
    assert '"it", "that PR" or "the statement"' in section


def test_a_bare_y_answers_only_the_last_question() -> None:
    section = _section()
    assert 'A bare "y" answers only a question asked in the last message.' in section
    assert "If that message asked no question or a different one, confirm which item the reply means." in section
    assert "That confirmation is the turn's `[y/n]` line." in section
    assert "Never pick an older open question the reply might mean." in section
    assert "This reply rule holds in a skill run too." in section
