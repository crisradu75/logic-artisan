"""The diagnose skill states each outcome the failure-diagnosis spec requires.

Spec: openspec/specs/failure-diagnosis. The skill is prose, so these tests pin the text that carries
each outcome, and the one fact that is not prose: the debug tag it writes is the tag the other two
homes of that pattern search for.
"""

from __future__ import annotations

import re
from pathlib import Path

_PLUGIN = Path(__file__).resolve().parents[4] / ".claude" / "plugins" / "cla"
_SKILL = _PLUGIN / "skills" / "diagnose" / "SKILL.md"
_SHIP = _PLUGIN / "skills" / "_shared" / "references" / "ship.md"
_HOOK = _PLUGIN / "hooks" / "ask-staged-debug-tag.py"


def _flat(path: Path = _SKILL) -> str:
    return " ".join(path.read_text(encoding="utf-8").split())


def _order(text: str, *phrases: str) -> None:
    at = [text.index(p) for p in phrases]
    assert at == sorted(at), f"out of order: {phrases}"


# requirement: failure-diagnosis / A reproduce loop comes before any fix
def test_the_loop_is_built_and_confirmed_before_any_hypothesis_and_its_absence_stops_the_run():
    text = _flat()
    assert "one command reproduces the failure and exits non-zero" in text
    assert "exits zero against a known-good state" in text
    assert "No buildable loop is a stop, not a licence to proceed." in text
    assert "say what you tried, and hand back" in text
    assert "the loop's output matches the reported symptom in specifics" in text
    _order(text, "## Phase 1 — a deterministic pass/fail loop", "## Phase 2 — reproduce, and confirm",
           "## Phase 3 — rank falsifiable hypotheses, before touching anything")


# requirement: failure-diagnosis / Causes are ranked and written down before any edit
def test_hypotheses_are_ranked_falsifiable_and_pruned_only_by_a_present_user():
    text = _flat()
    assert "Write 3–5 hypotheses" in text and "**what would prove it wrong**" in text
    assert "Not before an `Edit`. Not after." in text
    assert "**The discriminator is whether an invoker is present to answer, not which skill called**" in text
    assert "**Attended** — show the ranked list and let the user prune it" in text
    assert "**Unattended** — proceed on the top hypothesis without asking. Write the full ranked list into the report" in text
    assert "The caller declared the mode." in text and "Neither.** Assume nobody is there. → **unattended**" in text


# requirement: failure-diagnosis / The regression test fails before the fix
def test_the_test_fails_before_the_fix_or_a_finding_is_written():
    text = _flat()
    assert "Write a test that fails for the confirmed cause" in text
    assert "Run it, see it fail, and only then fix." in text
    assert '**"There is no correct seam" is a finding, not an obstacle.**' in text
    assert "Write it as a dated finding into `cla.io/feedback/`" in text
    assert "Next step: `/cla:shape-decision`." in text
    _order(text, "## Phase 4 — instrument one variable at a time", "## Phase 5 — the regression test comes before the fix")


# requirement: failure-diagnosis / No debug tag is left behind
def test_every_tag_is_removed_and_a_grep_proves_it_before_the_commit():
    text = _flat()
    assert "**Every `[DEBUG-xxxx]` tag is removed. Prove it with a grep that returns nothing:**" in text
    assert 'grep -rn "\\[DEBUG-" <the paths this run touched>' in _SKILL.read_text(encoding="utf-8")
    assert "A non-zero hit count is a halt, not a warning." in text
    _order(text, "A non-zero hit count is a halt", "**The commit message states the confirmed hypothesis**")


# requirement: failure-diagnosis / The commit names the confirmed cause
def test_the_commit_message_states_the_confirmed_cause():
    text = _flat()
    assert "**The commit message states the confirmed hypothesis**, not the symptom and not the edit" in text
    assert "the commit message names the cause" in text


# requirement: failure-diagnosis / No debug tag is left behind
def test_the_skill_and_the_ship_scan_name_every_home_of_the_tag():
    """Regression: both once said the pattern lives in two files, missing the guard hook that also
    searches for it, so a rename following that prose left the hook checking nothing."""
    skill, ship = _flat(), _flat(_SHIP)
    assert "**The tag pattern lives in three files, and a rename must touch all three.**" in skill
    for text in (skill, ship):
        assert "${CLAUDE_PLUGIN_ROOT}/hooks/ask-staged-debug-tag.py" in text
    assert "skills/diagnose/SKILL.md` Phase 6 and in the guard hook" in ship
    assert "two files" not in skill and "touch both" not in ship
    # The three homes agree on the tag itself.
    tag = re.search(r'TAG = "\[" \+ "(DEBUG-)"', _HOOK.read_text(encoding="utf-8")).group(1)
    assert f"[{tag}xxxx]" in skill and f'"\\[{tag}"' in ship
