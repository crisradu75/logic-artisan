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


# scenario: change-authoring / Authoring a scenario
def test_the_brief_and_the_rules_name_the_marker_and_the_manual_line():
    brief = _read(_BRIEF)
    assert "a comment line `scenario: <spec> / <heading>` above it" in brief
    assert f"or a tasks.md line {_MANUAL}, naming the heading" in brief
    config = _read(_CONFIG)
    assert f"a test task whose test carries a {_MARKER} comment line above it, or a line {_MANUAL}." in config


# scenario: change-authoring / A pure heading rename
def test_a_pure_rename_is_exempt():
    assert "A pure heading rename and a scenario carried forward unchanged in a MODIFIED block are exempt." in _read(_BRIEF)
    assert "A pure heading rename, or a scenario carried forward unchanged in a MODIFIED block, needs neither." in _read(_CONFIG)


# scenario: change-authoring / Authoring a heading that is already taken
def test_headings_are_unique_within_a_spec():
    assert "**Scenario headings are unique within one spec**" in _read(_BRIEF)
    assert "Keep every scenario heading unique within its spec, so `<spec> / <heading>` names exactly one scenario." in _read(_CONFIG)


# scenario: change-review / A scenario with no proof
def test_the_review_flags_a_scenario_with_no_proof():
    assert f"or a tasks.md line {_MANUAL}. A scenario with neither is the finding." in _read(_CHECKLIST)


# scenario: change-review / A repeated scenario heading
def test_the_review_flags_a_repeated_heading():
    assert "- **Repeated scenario heading.**" in _read(_CHECKLIST)
    assert "A heading the delta adds that repeats another in the same spec is **Important**." in _read(_DISPATCH)


# scenario: change-review / A test task that names no marker
def test_a_missing_marker_is_only_a_suggestion():
    assert f"A test task that does not name the {_MARKER} comment its test will carry is a **Suggestion**, not a blocker." in _read(_CHECKLIST)
    assert f"A test task that names no {_MARKER} marker is a **Suggestion**." in _read(_DISPATCH)


_LIVE_SPECS = _REPO / "openspec" / "specs"


def _live_specs() -> list[Path]:
    return sorted(_LIVE_SPECS.glob("*/spec.md"))


def test_the_old_manual_format_is_gone():
    specs = _live_specs()
    # Its own floor: the shipped .md files alone clear the total, so a glob that
    # stopped matching the live specs would pass silently without this.
    assert len(specs) >= 6, f"found {len(specs)} live specs under {_LIVE_SPECS}"
    sites = [_CONFIG, *(_REPO / ".claude" / "plugins" / "cla").rglob("*.md"), *specs]
    stale = [str(p.relative_to(_REPO)) for p in sites if "`manual: <reason>`" in _read(p)]
    assert len(sites) > 50, "the scan found too few files to mean anything"
    assert not stale, f"still using `manual: <reason>`: {stale}"


def test_every_scenario_marker_names_a_live_scenario():
    """A `scenario: <spec> / <heading>` comment is a claim that the test proves
    that scenario. One naming a spec or heading that no longer exists proves
    nothing and reads as coverage, which is what a spec move or a heading
    rename leaves behind unless something checks."""
    import re

    live = set()
    for spec in _live_specs():
        text = _read(spec)
        live |= {(spec.parent.name, h.strip()) for h in re.findall(r"^#### Scenario: (.+)$", text, re.M)}
    assert len(live) >= 250, f"only {len(live)} live scenarios found"
    markers = []
    for test in sorted((_REPO / "plugin-tests").rglob("*.py")):
        for m in re.finditer(r"^\s*# scenario: ([a-z0-9-]+) / (.+?)\s*$", _read(test), re.M):
            markers.append((test.relative_to(_REPO), m.group(1), m.group(2)))
    assert len(markers) >= 10, f"only {len(markers)} scenario markers found"
    dangling = [f"{t}: {cap} / {h}" for t, cap, h in markers if (cap, h) not in live]
    assert not dangling, f"scenario markers naming no live scenario: {dangling}"
