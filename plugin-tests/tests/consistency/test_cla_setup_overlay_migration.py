"""cla-setup's overlay migration keeps every rule an overlay states.

Part 2 is a read-and-reason pass with no script, so what it does is only what its
prose says. A review found the first cut moved whole dated incidents to the
lessons log, rules inside them included, although most skills never read that
log; it also counted any path as a fact, which would have moved the memory
location only codify-learnings reads. These tests pin the sentences that stop
both, and that the two skills still read those rule-owned paths from the overlay.

The terminology entry format has one home, a shared reference both cla-setup and
shape-decision point at.
"""

from __future__ import annotations

from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
_SKILLS = _REPO / ".claude" / "plugins" / "cla" / "skills"
_CLA_SETUP = _SKILLS / "cla-setup" / "SKILL.md"
_TERMS = _SKILLS / "_shared" / "references" / "terminology-format.md"


def _flat(path: Path) -> str:
    return " ".join(path.read_text(encoding="utf-8").split())


# requirement: repo-context / Repo facts and overlay rules on setup
def test_a_rule_inside_an_incident_stays_in_the_overlay():
    text = _flat(_CLA_SETUP)
    for sentence in (
        "A dated incident's story goes to `cla.io/lessons-learned/`, and any rule it states stays in the overlay",
        "Pull out every rule it states for this repo",
        "and sort that as a rule; the rest is story",
        "Keep every rule as written, and each rule pulled out of an incident as one or two lines",
        "Move the incident's story to `cla.io/lessons-learned/lessons-learned.md`",
        "When unsure whether a line is a rule, call it one",
    ):
        assert sentence in text, sentence


# requirement: repo-context / Repo facts and overlay rules on setup
def test_a_path_only_one_rule_uses_stays_with_that_rule():
    text = _flat(_CLA_SETUP)
    assert "**with any path or command only that rule uses**" in text
    assert "unless only a rule in this overlay uses it" in text
    # The two readers that depend on it still look in the overlay.
    codify = _flat(_SKILLS / "codify-learnings" / "SKILL.md")
    assert "`cla.io/overlays/codify-learnings.md`, if present, says where memory lives" in codify
    assert "the memory index (skip it if the overlay does not say where it is" in codify
    checklist = _flat(_SKILLS / "review-change" / "references" / "checklist.md")
    assert "**Its repo-specific review checks come from `cla.io/overlays/review-change.md` when that file is present** — the domain checks 0f–0i" in checklist


# requirement: repo-context / Repo facts and overlay rules on setup
def test_the_old_sync_context_pointer_is_scaffolding():
    """An overlay holding only that pointer, headings and comments has no rule, so
    it is proposed for deletion."""
    text = _flat(_CLA_SETUP)
    assert "**scaffolding** — headings, HTML comments, and the old pointer that sent readers to the retired `sync-context` skill" in text
    assert "Drop duplicates and scaffolding. An overlay left with no rule is proposed for **deletion**" in text


def test_the_terminology_format_has_one_home():
    terms = _flat(_TERMS)
    assert "**Term**: one-sentence definition — what it IS, not what it does. _Avoid_: rejected-alias-1, rejected-alias-2" in terms
    pointer = "`${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/terminology-format.md`"
    for reader in (_CLA_SETUP, _SKILLS / "shape-decision" / "SKILL.md"):
        text = _flat(reader)
        assert pointer in text, reader
        assert "_Avoid_: rejected-alias" not in text, f"{reader} restates the entry format"
