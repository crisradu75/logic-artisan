"""The scenario-to-test link uses one format at every site that states it.

A test claims a scenario with a comment line `scenario: <spec> / <heading>`
above it; a hand-checked scenario is a tasks.md line
`manual: <heading>: <reason>`. Both name the heading, so a guard can match
them, which is why scenario headings must be unique within one spec. The
convention follows crisradu75/interoga-ro#711, whose guard a later CLA change
ports. Until then these tests only pin that the authoring brief, the review
checklist and the seeded rules say the same thing, and that the older
`manual: <reason>` form is gone from every site.
"""

from __future__ import annotations

from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
_SKILLS = _REPO / ".claude" / "plugins" / "cla" / "skills"
_BRIEF = _SKILLS / "multi-spec" / "references" / "authoring-brief.md"
_CHECKLIST = _SKILLS / "review-change" / "references" / "checklist.md"
# The three dispatched agents' prompts, read only on a large change.
_DISPATCH = _SKILLS / "review-change" / "references" / "dispatch.md"
_CONFIG = _REPO / "openspec" / "config.yaml"

_MARKER = "`scenario: <spec> / <heading>`"
_MANUAL = "`manual: <heading>: <reason>`"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# scenario: cla-plugin / Authoring a scenario
def test_the_brief_and_the_rules_name_the_marker_and_the_manual_line():
    brief = _read(_BRIEF)
    assert "a comment line `scenario: <spec> / <heading>` above it" in brief
    assert f"or a tasks.md line {_MANUAL}, naming the heading" in brief
    config = _read(_CONFIG)
    assert f"a test task whose test carries a {_MARKER} comment line above it, or a line {_MANUAL}." in config


# scenario: cla-plugin / A pure heading rename
def test_a_pure_rename_is_exempt():
    assert "A pure heading rename and a scenario carried forward unchanged in a MODIFIED block are exempt." in _read(_BRIEF)
    assert "A pure heading rename, or a scenario carried forward unchanged in a MODIFIED block, needs neither." in _read(_CONFIG)


# scenario: cla-plugin / Authoring a heading that is already taken
def test_headings_are_unique_within_a_spec():
    assert "**Scenario headings are unique within one spec**" in _read(_BRIEF)
    assert "Keep every scenario heading unique within its spec, so `<spec> / <heading>` names exactly one scenario." in _read(_CONFIG)


# scenario: cla-plugin / A scenario with no proof
def test_the_review_flags_a_scenario_with_no_proof():
    assert f"or a tasks.md line {_MANUAL}. A scenario with neither is the finding." in _read(_CHECKLIST)


# scenario: cla-plugin / A repeated scenario heading
def test_the_review_flags_a_repeated_heading():
    assert "- **Repeated scenario heading.**" in _read(_CHECKLIST)
    assert "A heading the delta adds that repeats another in the same spec is **Important**." in _read(_DISPATCH)


# scenario: cla-plugin / A test task that names no marker
def test_a_missing_marker_is_only_a_suggestion():
    assert f"A test task that does not name the {_MARKER} comment its test will carry is a **Suggestion**, not a blocker." in _read(_CHECKLIST)
    assert f"A test task that names no {_MARKER} marker is a **Suggestion**." in _read(_DISPATCH)


def test_the_old_manual_format_is_gone():
    sites = [_CONFIG, *(_REPO / ".claude" / "plugins" / "cla").rglob("*.md"), _REPO / "openspec" / "specs" / "cla-plugin" / "spec.md"]
    stale = [str(p.relative_to(_REPO)) for p in sites if "`manual: <reason>`" in _read(p)]
    assert len(sites) > 50, "the scan found too few files to mean anything"
    assert not stale, f"still using `manual: <reason>`: {stale}"
