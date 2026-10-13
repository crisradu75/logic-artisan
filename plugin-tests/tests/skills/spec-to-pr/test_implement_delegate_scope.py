"""The Implement brief checks its scope against every path tasks.md names (GitHub #288).

A multi-pr chain wrote a brief whose scope allowed one line under `cla.io/`, while two
tasks named more `cla.io/` files. Full-task enumeration passed, the delegate returned
those tasks unticked, and only the Post-check found them, at the cost of a Revise pass.
"""

from __future__ import annotations

from pathlib import Path

_REF = (
    Path(__file__).resolve().parents[4]
    / ".claude" / "plugins" / "cla" / "skills" / "spec-to-pr" / "references" / "implement-delegate.md"
)


def _rule(prefix: str) -> str:
    lines = _REF.read_text(encoding="utf-8").splitlines()
    found = next((line for line in lines if line.startswith(prefix)), None)
    assert found is not None, f"implement-delegate.md lost the rule starting {prefix!r}"
    return found


def test_the_brief_checks_scope_against_every_task_path_before_dispatch():
    rule = _rule("- **Scope covers every path a task names.**")
    assert "Before dispatching, grep `tasks.md` for repo paths and globs" in rule
    assert "confirm each one lies inside the brief's scope" in rule


def test_a_deliberately_excluded_path_is_named_and_its_task_deferred():
    rule = _rule("- **Scope covers every path a task names.**")
    assert "put it in the do-not-touch slot and mark its task deferred in the brief" in rule


def test_the_rule_count_matches_the_rules_listed():
    text = _REF.read_text(encoding="utf-8")
    assert "Eight rules make the delegation safe — four about the brief, four about reading what comes back:" in text
    section = text.split("## Delegating Implement to one coding agent", 1)[1]
    listed = section.split("After the agent returns", 1)[0]
    assert sum(line.startswith("- **") for line in listed.splitlines()) == 8
