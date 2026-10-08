"""The requirement-to-test link uses one format at every site that states it.

Proof is per requirement: scenarios are examples, not test contracts. A test
claims a requirement with a comment line `requirement: <spec> / <heading>`
above it; a hand-checked requirement is a tasks.md line
`manual: <heading>: <reason>`. OpenSpec already refuses two requirements with
one heading in a spec, so `<spec> / <heading>` names one requirement. These
tests pin that the seeded rules and the review say the same thing, that the
retired forms (`manual: <reason>`, and the per-scenario `scenario:` marker) are
gone, and that every marker names a live requirement. The file keeps its old
name so the mutation batch beside it still maps by name.
"""

from __future__ import annotations

import re
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
_PLUGIN = _REPO / ".claude" / "plugins" / "cla"
_SKILLS = _PLUGIN / "skills"
_BRIEF = _SKILLS / "multi-spec" / "references" / "authoring-brief.md"
_CHECKLIST = _SKILLS / "review-change" / "references" / "checklist.md"
# The three dispatched agents' prompts, read only on a large change.
_DISPATCH = _SKILLS / "review-change" / "references" / "dispatch.md"
_CONFIG = _REPO / "openspec" / "config.yaml"

_MARKER = "`requirement: <spec> / <heading>`"
_MANUAL = "`manual: <heading>: <reason>`"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# requirement: change-authoring / Every new or modified scenario names its proof
def test_the_rules_ask_for_proof_per_requirement():
    config = _read(_CONFIG)
    assert (
        f"Give each requirement this change adds or modifies a test task whose test carries a {_MARKER} "
        f"comment line above it, or a line {_MANUAL}. Scenarios are examples, not one test each." in config
    )


# requirement: change-authoring / The authoring brief points to the stock limits and asks for no doc-sync task
def test_the_brief_applies_the_rules_instead_of_copying_them():
    brief = _read(_BRIEF)
    assert "**Apply `openspec/config.yaml` `rules:`**" in brief
    copies = [s for s in ("500 characters", "≤500", "manual: <heading>", "<spec> / <heading>") if s in brief]
    assert not copies, f"the authoring brief restates the rules: {copies}"


# requirement: change-authoring / Scenario headings are unique within one spec
def test_headings_are_unique_within_a_spec():
    assert "Keep every scenario heading unique within its spec, so `<spec> / <heading>` names exactly one scenario." in _read(_CONFIG)


# requirement: change-review / A scenario with no proof is an Important finding
def test_the_review_flags_a_requirement_with_no_proof():
    assert f"or a tasks.md line {_MANUAL}. A requirement with neither is the finding." in _read(_CHECKLIST)
    assert "A requirement with neither is **Important**." in _read(_DISPATCH)


# requirement: change-review / A repeated scenario heading is an Important finding
def test_the_review_flags_a_repeated_heading():
    assert "- **Repeated scenario heading.**" in _read(_CHECKLIST)
    assert "A heading the delta adds that repeats another in the same spec is **Important**." in _read(_DISPATCH)


# requirement: change-review / A test task naming no marker is a Suggestion
def test_a_missing_marker_is_only_a_suggestion():
    assert f"A test task that does not name the {_MARKER} comment its test will carry is a **Suggestion**, not a blocker." in _read(_CHECKLIST)
    assert f"A test task that names no {_MARKER} marker is a **Suggestion**." in _read(_DISPATCH)


_LIVE_SPECS = _REPO / "openspec" / "specs"


def _live_specs() -> list[Path]:
    return sorted(_LIVE_SPECS.glob("*/spec.md"))


def test_the_retired_formats_are_gone():
    specs = _live_specs()
    # Its own floor: the shipped .md files alone clear the total, so a glob that
    # stopped matching the live specs would pass silently without this.
    assert len(specs) >= 6, f"found {len(specs)} live specs under {_LIVE_SPECS}"
    shipped = [_CONFIG, *_PLUGIN.rglob("*.md")]
    assert len(shipped) > 50, "the scan found too few files to mean anything"
    stale = [str(p.relative_to(_REPO)) for p in [*shipped, *specs] if "`manual: <reason>`" in _read(p)]
    assert not stale, f"still using `manual: <reason>`: {stale}"
    # The live specs still describe the per-scenario marker until they are
    # rewritten, so this half reads the rules and the plugin only.
    stale = [str(p.relative_to(_REPO)) for p in shipped if "`scenario: <spec> / <heading>`" in _read(p)]
    assert not stale, f"still asking for a per-scenario marker: {stale}"


def _markers(prefix: str) -> list[tuple[Path, str, str]]:
    found = []
    for test in sorted((_REPO / "plugin-tests").rglob("*.py")):
        for m in re.finditer(rf"^\s*# {prefix}: ([a-z0-9-]+) / (.+?)\s*$", _read(test), re.M):
            found.append((test.relative_to(_REPO), m.group(1), m.group(2)))
    return found


def test_every_requirement_marker_names_a_live_requirement():
    """A `requirement: <spec> / <heading>` comment is a claim that the test
    proves that requirement. One naming a spec or heading that no longer exists
    proves nothing and reads as coverage, which is what a spec rewrite or a
    heading rename leaves behind unless something checks."""
    specs = _live_specs()
    live = set()
    for spec in specs:
        live |= {(spec.parent.name, h.strip()) for h in re.findall(r"^### Requirement: (.+)$", _read(spec), re.M)}
    # OpenSpec refuses a spec with no requirement, so fewer than one per spec
    # means the heading pattern stopped matching.
    assert len(live) >= len(specs) >= 6, f"only {len(live)} live requirements in {len(specs)} specs"
    markers = _markers("requirement")
    assert len(markers) >= 10, f"only {len(markers)} requirement markers found"
    dangling = [f"{t}: {cap} / {h}" for t, cap, h in markers if (cap, h) not in live]
    assert not dangling, f"requirement markers naming no live requirement: {dangling}"


def test_no_test_carries_the_retired_scenario_marker():
    # A leftover `# scenario:` line is matched by nothing above, so it would
    # read as proof while no check looks at it.
    old = [f"{t}: {cap} / {h}" for t, cap, h in _markers("scenario")]
    assert not old, f"retired per-scenario markers: {old}"
