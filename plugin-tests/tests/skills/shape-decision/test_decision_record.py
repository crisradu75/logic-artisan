"""shape-decision asks one question at a time and writes a record only on a yes.

Spec: openspec/specs/session-records. The axis-list and stopping behaviour is also pinned by
test_protocol_gaps.py, which carries the markers for the first requirement.
"""

from __future__ import annotations

from pathlib import Path

_DIR = Path(__file__).resolve().parents[4] / ".claude" / "plugins" / "cla" / "skills" / "shape-decision"


def _flat(path: Path) -> str:
    return " ".join(path.read_text(encoding="utf-8").split())


# requirement: session-records / A decision is shaped one question at a time until every axis is settled
def test_questions_come_one_at_a_time_with_options_pros_cons_and_one_recommendation():
    text = _flat(_DIR / "SKILL.md")
    assert "Ask one question at a time and wait for the answer" in text
    form = _flat(_DIR / "references" / "question-form.md")
    assert "Pros: ..." in form and "Cons: ..." in form
    assert "Mark exactly one option" in form
    assert "[Recommended]" in form


# requirement: session-records / A decision is saved only on an explicit yes
def test_the_record_is_written_only_after_an_explicit_yes_and_never_overwrites():
    text = _flat(_DIR / "SKILL.md")
    assert "Write nothing without an explicit yes" in text
    assert "On a yes, use `Write` to save `cla.io/decisions/{topic-slug}-{date}.md`" in text
    assert "append `-2`, `-3`, and so on; never overwrite" in text
