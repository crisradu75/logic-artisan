"""The Implement brief checks its scope against every path tasks.md names (GitHub #288).

A multi-pr chain wrote a brief whose scope allowed one line under `cla.io/`, while two
tasks named more `cla.io/` files. Full-task enumeration passed, the delegate returned
those tasks unticked, and only the Post-check found them, at the cost of a Revise pass.
"""

from __future__ import annotations

from pathlib import Path

_SKILL_DIR = (
    Path(__file__).resolve().parents[4] / ".claude" / "plugins" / "cla" / "skills" / "spec-to-pr"
)
_REF = _SKILL_DIR / "references" / "implement-delegate.md"
_PREFIX = "- **Scope covers every path a task names.**"


def _rules_section() -> str:
    text = _REF.read_text(encoding="utf-8")
    section = text.split("## Delegating Implement to one coding agent", 1)[1]
    return section.split("After the agent returns", 1)[0]


def _rule() -> str:
    found = next((line for line in _rules_section().splitlines() if line.startswith(_PREFIX)), None)
    assert found is not None, "the scope rule left the delegate's rule list"
    return found


def test_the_brief_checks_scope_against_every_task_path_before_dispatch():
    rule = _rule()
    assert "Before dispatching, grep `tasks.md` for repo paths and globs" in rule
    assert "inside the brief's scope" in rule
    assert "widen the scope" in rule, "an accidental exclusion has no default fix"


def test_a_grep_alone_is_not_the_check():
    rule = _rule()
    assert "a file it names without a path" in rule
    assert "is a miss, not a pass" in rule
    assert "any `design.md` section you inline" in rule


def test_a_path_kept_out_on_purpose_is_held_not_deferred():
    """`deferred-to-TODO` passes the Post-check undone, so a held task must not borrow the word."""
    rule = _rule()
    assert "mark every task that names it `held by orchestrator`" in rule
    assert "Held is not `deferred-to-TODO`" in rule
    assert "finish each held task yourself before the Post-check." in rule
    # Implement runs one delegate: no second dispatch may own a held task.
    assert "sibling" not in rule
    assert '"every task not held is ticked"' in rule


def test_a_held_task_is_not_a_contract_firing_in_either_rule():
    assert "is not a contract firing" in _rule()
    text = _REF.read_text(encoding="utf-8")
    firing = next((line for line in text.splitlines() if line.startswith("**Contract firings leave a trace.**")), None)
    assert firing is not None, "implement-delegate.md lost its Contract-firings rule"
    assert "(a task the brief marked `held by orchestrator` is not one)" in firing


def test_the_neighbouring_rules_count_a_held_task_as_handed_back():
    lines = _rules_section().splitlines()
    enumeration = next(line for line in lines if line.startswith("- **Full-task enumeration.**"))
    assert "`held by orchestrator` per the next rule, or a task already recorded `deferred-to-TODO` at Propose" in enumeration
    evidence = next(line for line in lines if line.startswith("- **Evidence-based terminal contract.**"))
    assert "less any tasks the brief marked held" in evidence


def test_skill_md_summary_names_the_scope_check():
    skill = (_SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
    assert "its scope covers every path they name" in skill


def test_the_rule_count_matches_the_rules_listed():
    text = _REF.read_text(encoding="utf-8")
    assert "Eight rules make the delegation safe — four about the brief, four about reading what comes back:" in text
    assert sum(line.startswith("- **") for line in _rules_section().splitlines()) == 8
