"""The output style's closing `[y/n]` line names its item and binds a bare "y" to it.

With several items in flight, "Do you want that PR built? [y/n]" could not be answered
without asking back. A bare "y" was once read as approval for an older open question.
The style loads on every reply in every repo, so the rule lives there.
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
    assert '"it", "that PR" or "the statement"' in section


def test_a_bare_y_answers_only_the_last_question() -> None:
    section = _section()
    assert 'A bare "y" answers only the question in the last message.' in section
    assert "confirm in one line which item the reply means" in section
    assert "Never pick an older open question it might mean." in section
