"""The codify-learnings skill states each outcome the session-learnings spec requires.

Spec: openspec/specs/session-learnings. The skill is prose, so these tests pin the text that
carries each outcome in `SKILL.md` and in `references/routing.md`, which it reads before Step 1.
"""

from __future__ import annotations

from pathlib import Path

_DIR = Path(__file__).resolve().parents[4] / ".claude" / "plugins" / "cla" / "skills" / "codify-learnings"
_SKILL = _DIR / "SKILL.md"
_ROUTING = _DIR / "references" / "routing.md"


def _flat(path: Path = _SKILL) -> str:
    return " ".join(path.read_text(encoding="utf-8").split())


# requirement: session-learnings / Failures come from the whole session
def test_the_whole_session_is_reviewed_and_no_failure_means_no_fix():
    text = _flat()
    assert "Review the **whole session from its first message**, not its tail" in text
    for kind in ("user correction or pushback", "reverted edit or abandoned approach",
                 "denied tool call or permission prompt", "wasted turn"):
        assert kind in text
    assert "Write each failure as one line with a short quote" in text
    assert "No failures: say so, and go to Step 5 with empty lists." in text


# requirement: session-learnings / At most three fixes, each answering a quoted failure
def test_at_most_three_fixes_each_quoting_its_failure():
    text = _flat()
    assert "**Each fix cites the failure it answers, quoted.**" in text
    assert "A candidate with no session failure behind it is dropped" in text
    assert "Rank by payoff and cut after the third, memory included" in text
    assert "Show only the numbered list, most valuable first" in text
    assert "up to three fixes" in _SKILL.read_text(encoding="utf-8").split("---")[1]


# requirement: session-learnings / A tool fix before a doc note
def test_a_tool_or_hook_fix_comes_before_a_doc_note():
    text, ladder = _flat(), _flat(_ROUTING)
    assert "**Prefer fixes over diagnostics.**" in text
    assert "the first fix makes the tool handle X — a script, a config, a hook, a smoke test — and a doc or memory note is at most a second aid" in text
    assert "**No hit is a new lesson**: it enters at the lowest rung that would have prevented it." in text
    assert "(tools and hooks before docs)" in text
    assert "| `script` | a script, or build/lint/test config | every run; the failure becomes impossible |" in ladder


# requirement: session-learnings / A rule that failed again is escalated
def test_a_re_offense_climbs_above_the_artifact_that_failed():
    text, ladder = _flat(), _flat(_ROUTING)
    assert "**A hit is a re-offense**: the rule existed and did not hold." in text
    assert "Its fix goes **one rung above** that artifact" in text
    assert "**A re-offense** climbs one rung above the artifact that failed." in ladder
    assert "Restating it louder on the same rung is the failure this ladder exists to stop." in ladder
    assert "or move it to a home with better reach" in ladder


# requirement: session-learnings / One prompt before anything is written
def test_one_prompt_and_nothing_written_before_the_answer():
    text = _flat()
    assert "Apply which? (y = all / n = none / indices, e.g. 1,3)" in text
    assert "**Empty input is not consent.** Ask once more; a second empty answer is `n`." in text
    assert "Nothing is written before this answer — memory included." in text


# requirement: session-learnings / A plugin fix goes upstream when the plugin is read-only
def test_a_read_only_plugin_sends_its_fix_upstream():
    text, routing = _flat(), _flat(_ROUTING)
    assert "Read-only: a fix to a plugin file goes to `/cla:report-upstream`, and its line says so." in text
    assert "Plugin root inside the repo root → **writable**. Outside, or either path unknown → **read-only**." in routing
    assert "| a `SKILL.md`, `references/**`, `hooks/**`, `lib/**`, any plugin script | edit | `/cla:report-upstream` |" in routing
    assert "send a portable fix upstream, not into a local overlay" in routing


# requirement: session-learnings / Each run is logged, and the log stays small
def test_each_run_is_logged_and_old_entries_move_whole_to_the_archive():
    text = _flat()
    assert "Prepend one entry of at most 150 words to `cla.io/lessons-learned/lessons-learned.md`" in text
    for line in ("- APPLIED 1. <title>", "- REJECTED 2. <title>", "- Re-offense: `<artifact>` → <rung>"):
        assert line in text
    assert "**Keep the live log under 6,000 words (`wc -w`).**" in text
    assert "move its oldest entries, whole and unedited" in text
    assert "`cla.io/lessons-learned/lessons-learned-archive.md`" in text
    assert "the total must match" in text
