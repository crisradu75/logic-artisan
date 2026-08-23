"""A chain skill must say how a turn ENDS, not just that it must not pause.

The two rules look like one rule and are not. "Run start-to-finish with no
'ready to continue?' pauses" forbids *asking permission*. The failure that
actually stops a chain asks nothing: the orchestrator announces the next unit,
ends the turn believing it is continuing, and nothing ever re-invokes the
session. Source: GitHub issue #130 — a chain lost ~4.5 hours with 4 of 6 changes
unstarted. Neither skill's no-pause rule covered it, because nothing was asked.

This scope pins that every chain orchestrator carries the rule, and that the rule
keeps the three properties that make it more than a restatement of the
prohibition beside it:

- `_MECHANICAL` — a check needing no judgement (is there a tool call in this
  message?) rather than a judgement about whether prose reads as an ending. The
  judgement form is the one that lost in practice.
- `_DISCRIMINATOR` — whether a *pending event* will re-invoke the session, not
  whether a question was asked.
- `_NOT_A_MECHANISM` — that announcing the next step does not wake anything.

Three design decisions, each forced by a defect this guard shipped with:

**The family is a declared literal, not a derived match.** An earlier revision
keyed it on the phrase "ready to continue". That is derivable but wrong in the
direction that bites: it EXCLUDED `spec-to-pr`, where the rule originated, and
`multi-spec`, which loops over N changes with the same between-unit seam. A
derived key cannot fail when it stops matching something it never matched.

**Markers must be ADJACENT, not merely co-present.** `in the same message` is
ordinary procedural English and appears in step prose unrelated to this rule, so
a file-wide `in` test stayed green with the liveness rule deleted. All three must
land in ONE block — a single line (the `SKILL.md` bullets are single long lines)
or one blank-line paragraph (the seam restatements are hard-wrapped).

**Adjacency is bounded by `_MAX_SPAN`, because "one block" was not enough.**
A reviewer defeated the block test by deleting a seam restatement and planting
the three markers into an unrelated 2326-character numbered step, which is one
paragraph. Measured spans of the real rule, first marker to last:

    multi-pr/SKILL.md                        871      multi-pr change-loop      255
    multi-lite/SKILL.md                      871      multi-lite candidate-loop 261
    multi-spec/SKILL.md                      741      multi-spec authoring      255
    spec-to-pr/SKILL.md                      594

Command: the block-span probe in this file's own history; re-derive with
`_span_of_best_block` below over the same files. 1200 clears the widest real
statement with ~38% headroom and rejects markers scattered across a block twice
that size.

Every looping test carries its own floor. An earlier revision put the
non-vacuity assertion in a SEPARATE test function, and pytest couples nothing —
a `-k`, a skip, or a collection error in the floor left the real test silently
green. Two of these tests were proven to pass while checking zero things.

Spec: `openspec/specs/cla-plugin/spec.md`, "Unattended-run turn liveness".
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_PLUGIN_ROOT = Path(__file__).resolve().parents[3] / ".claude" / "plugins" / "cla"
_SKILLS = _PLUGIN_ROOT / "skills"

_MECHANICAL = "in the same message"
_DISCRIMINATOR = "pending event"
_NOT_A_MECHANISM = "is not a mechanism"
_MARKERS = (_MECHANICAL, _DISCRIMINATOR, _NOT_A_MECHANISM)

# The exhaustive-set clause the spec pins. Stated identically by every family
# member so no two assert differently-sized sets.
_EXHAUSTIVE = "exactly two cases"

_MAX_SPAN = 1200

# skill -> (seam reference file, the anchor naming that seam), or None when the
# skill has no per-unit loop in a reference file. Only `spec-to-pr` may be None:
# it is the rule's origin and its phase boundaries are stated inline, so it has a
# hoisted copy to guard and no seam. That exemption is asserted, not assumed —
# an unconstrained None silently removed two of three seams from the check.
_FAMILY: dict[str, tuple[str, str] | None] = {
    "multi-pr": ("references/change-loop.md", "move to the next change"),
    "multi-lite": ("references/candidate-loop.md", "move to the next candidate"),
    "multi-spec": ("references/authoring-brief.md", "before starting the next change"),
    "spec-to-pr": None,
}
_SEAMLESS = {"spec-to-pr"}


def _lines(text: str) -> list[str]:
    """Every non-blank line, lowercased, whitespace collapsed."""
    return [" ".join(l.split()) for l in text.lower().splitlines() if l.strip()]


def _blocks(text: str) -> list[str]:
    """Lines plus blank-line paragraphs, lowercased, whitespace collapsed.

    Two granularities because the rule is written at two: a hoisted `SKILL.md`
    bullet is one very long line, a seam restatement is hard-wrapped prose.

    Collapsing whitespace is what stops a marker straddling a hard wrap
    (`in the same\\nmessage`) reading as absent — a false failure that would
    train readers to reformat prose to satisfy a matcher. It fired on this
    scope's own seam text the first time it ran.
    """
    low = text.lower()
    return _lines(text) + [
        " ".join(p.split()) for p in low.split("\n\n") if p.strip()
    ]


def _span_of_best_block(text: str, *, paragraphs: bool) -> int | None:
    """Tightest span (first marker start to last marker end) over any one block
    carrying all three markers, or None when no block does."""
    candidates = _blocks(text) if paragraphs else _lines(text)
    best = None
    for block in candidates:
        pos = [block.find(m) for m in _MARKERS]
        if any(p < 0 for p in pos):
            continue
        span = max(p + len(m) for p, m in zip(pos, _MARKERS)) - min(pos)
        if best is None or span < best:
            best = span
    return best


def _why_not(text: str, *, paragraphs: bool) -> str | None:
    """None when the rule is present and tight. Otherwise why not."""
    span = _span_of_best_block(text, paragraphs=paragraphs)
    if span is None:
        low = text.lower()
        absent = [m for m in _MARKERS if m not in low]
        if absent:
            return f"markers absent from the file entirely: {absent}"
        return "all three markers appear, but never together in one block"
    if span > _MAX_SPAN:
        return (
            f"markers share a block but span {span} chars (> {_MAX_SPAN}) — they "
            "are scattered through a large block rather than stated together"
        )
    return None


def _skill_md(name: str) -> Path:
    return _SKILLS / name / "SKILL.md"


def test_the_declared_family_matches_the_tree():
    """Non-vacuity for the constants themselves, plus a drift tripwire.

    `_MARKERS` emptied made every assertion in this file pass, because
    `all(m in block for m in ())` is vacuously true. Pin the constants before
    anything relies on them.
    """
    assert len(_MARKERS) == 3 and all(_MARKERS), (
        f"_MARKERS must hold three non-empty phrases, got {_MARKERS!r} — an "
        "empty tuple makes every check in this file vacuously pass"
    )
    assert _MAX_SPAN > 0 and _EXHAUSTIVE, "the span cap and the clause must be set"
    assert _SKILLS.is_dir(), f"{_SKILLS} is not a directory — the guard scans nothing"
    assert len(_FAMILY) >= 4, (
        f"_FAMILY declares {len(_FAMILY)} skills; the four chain orchestrators "
        "are the floor. Removing one silently shrinks every check below."
    )
    for name in _FAMILY:
        assert _skill_md(name).is_file(), (
            f"{name} is declared in _FAMILY but {_skill_md(name)} does not exist"
        )
    seamless = {n for n, v in _FAMILY.items() if v is None}
    assert seamless == _SEAMLESS, (
        f"only {sorted(_SEAMLESS)} may declare no seam; got {sorted(seamless)}. "
        "An unconstrained None is a silent opt-out — setting two entries to None "
        "left two of three seams unchecked with every test green."
    )
    # Any skill promising no inter-unit pauses is a chain orchestrator and belongs
    # in _FAMILY. This is the direction a derived key could never check.
    promising = {
        p.parent.name
        for p in _SKILLS.glob("*/SKILL.md")
        if "ready to continue" in p.read_text(encoding="utf-8").lower()
    }
    assert promising, "no SKILL.md mentions 'ready to continue' any more"
    assert promising <= set(_FAMILY), (
        f"{sorted(promising - set(_FAMILY))} mention no-pause behaviour but are "
        "not in _FAMILY, so nothing checks their turn-liveness rule"
    )


def test_every_family_skill_states_the_turn_liveness_rule():
    seen = set()
    for name in _FAMILY:
        why = _why_not(_skill_md(name).read_text(encoding="utf-8"), paragraphs=False)
        assert why is None, (
            f"{name}/SKILL.md does not carry the whole turn-liveness rule in one "
            f"bullet — {why}. The rule is only load-bearing when the mechanical "
            "check, the pending-event discriminator, and 'announcing is not a "
            "mechanism' arrive together."
        )
        seen.add(name)
    # Floor INSIDE this test. `checked == len(_FAMILY)` was the previous form and
    # is a tautology: the loop has no break, so the counter always equals the
    # length. Emptying _FAMILY made this test pass having read no file at all.
    assert seen == set(_FAMILY) and len(seen) >= 4, (
        f"checked {sorted(seen)}; expected all {len(_FAMILY)} declared skills"
    )


def test_every_family_skill_names_the_same_two_exit_cases():
    """The spec pins the exhaustive set at exactly two. A drift back to three —
    the defect this change repaired in multi-pr and multi-lite, where the added
    third case was satisfiable by writing a paragraph — passed every other
    assertion here."""
    seen = set()
    for name in _FAMILY:
        low = _skill_md(name).read_text(encoding="utf-8").lower()
        assert _EXHAUSTIVE in low, (
            f"{name}/SKILL.md does not say {_EXHAUSTIVE!r}. Every family member "
            "must name the same two legitimate conditions, or two skills assert "
            "differently-sized exhaustive sets with nothing reconciling them."
        )
        seen.add(name)
    assert seen == set(_FAMILY) and len(seen) >= 4, (
        f"checked {sorted(seen)}; expected all {len(_FAMILY)} declared skills"
    )


def test_every_family_seam_restates_the_rule():
    """The gap opens BETWEEN units, which is where the reference file carrying
    the loop has been read and closed and the orchestrator is running on the
    SKILL.md summary. The hoisted copy is not enough on its own."""
    seen = set()
    for name, seam in _FAMILY.items():
        if seam is None:
            continue
        rel, anchor = seam
        path = _SKILLS / name / Path(rel)
        assert path.is_file(), f"{path} is missing — re-point _FAMILY"
        text = path.read_text(encoding="utf-8")
        assert anchor in text.lower(), (
            f"{rel} no longer contains {anchor!r}, the seam this check anchors to"
        )
        why = _why_not(text, paragraphs=True)
        assert why is None, (
            f"{name}'s seam ({rel}) does not restate the turn-liveness rule — "
            f"{why}. The hoisted rule binds, but this is the point at which "
            "SKILL.md is no longer in front of the reader."
        )
        seen.add(name)
    assert seen == set(_FAMILY) - _SEAMLESS and len(seen) >= 3, (
        f"checked seams for {sorted(seen)}; expected "
        f"{sorted(set(_FAMILY) - _SEAMLESS)}"
    )


# --------------------------------------------------------------------------- #
# The guard's own non-vacuity, checked structurally rather than by mutation.
#
# `_MARKERS`'s floor and `_MAX_SPAN`'s cap both defend against a state the tree
# is not currently in, so a mutation over the real files cannot reach them —
# measured: both survived a batch in which every other mutant was killed. That
# is the case `_shared/references/test-quality.md` calls out, and it prefers
# this form: assert the check can still fire, which keeps holding after a later
# refactor quietly turns it into a no-op.
#
# Every attack below was proven LIVE against an earlier revision of this file by
# an independent review. They are regression tests for a vacuous guard.
# --------------------------------------------------------------------------- #

_CONTENT_CHECKS = (
    test_the_declared_family_matches_the_tree,
    test_every_family_skill_states_the_turn_liveness_rule,
    test_every_family_skill_names_the_same_two_exit_cases,
    test_every_family_seam_restates_the_rule,
)


def _surviving(checks) -> int:
    """How many checks still pass. An exception counts as a failure — loud is
    fine here; silent is the thing being tested for."""
    alive = 0
    for check in checks:
        try:
            check()
        except Exception:
            continue
        alive += 1
    return alive


def test_the_checks_all_pass_on_the_real_tree():
    """Baseline. Without this the tamper cases below are satisfiable by a guard
    that fails on everything, including the truth."""
    assert _surviving(_CONTENT_CHECKS) == len(_CONTENT_CHECKS)


@pytest.mark.parametrize(
    "name,attribute,value",
    [
        # Emptying the family made a looping test pass having read no file.
        ("the declared family is emptied", "_FAMILY", {}),
        # Emptying the markers made `all(m in block for m in ())` vacuously
        # true, so every content check passed while checking nothing.
        ("the marker set is emptied", "_MARKERS", ()),
        # An unconstrained None silenced two of three seam checks.
        (
            "seams are silenced with None",
            "_FAMILY",
            {
                "multi-pr": None,
                "multi-lite": None,
                "multi-spec": (
                    "references/authoring-brief.md",
                    "before starting the next change",
                ),
                "spec-to-pr": None,
            },
        ),
    ],
)
def test_the_guard_notices_when_its_own_state_is_gutted(
    name, attribute, value, monkeypatch
):
    module = sys.modules[__name__]
    monkeypatch.setattr(module, attribute, value)
    assert _surviving(_CONTENT_CHECKS) < len(_CONTENT_CHECKS), (
        f"every check still passed with {name} — the guard is vacuous under "
        "this tampering, which an earlier revision of it genuinely was"
    )


def test_the_adjacency_cap_is_load_bearing(monkeypatch):
    """The cap, exercised the only way it can be.

    A test that removes the cap AND supplies a wide block cannot prove anything:
    the cap is the sole check that would catch it, so asking the guard to notice
    its own disablement is incoherent. Keep the real cap and feed it the bad
    input instead — three markers spread across one large block, which is
    precisely how a reviewer defeated the unbounded 'same block' rule by folding
    a seam restatement into an unrelated numbered step.
    """
    module = sys.modules[__name__]
    scattered = (
        "in the same message "
        + ("filler " * 260)
        + "pending event "
        + ("filler " * 60)
        + "is not a mechanism"
    )
    assert len(scattered) > _MAX_SPAN, "the fixture must exceed the cap to test it"
    monkeypatch.setattr(module, "_blocks", lambda text: [scattered])

    why = _why_not("irrelevant, _blocks is stubbed", paragraphs=True)
    assert why is not None and "span" in why, (
        "three markers scattered across a block wider than the cap were accepted "
        f"as adjacent; _why_not returned {why!r}"
    )


def test_line_granularity_rejects_markers_split_across_bullets(monkeypatch):
    """Why SKILL.md is checked at LINE level and the seams at paragraph level.

    Markdown bullets are not blank-line separated, so paragraph granularity
    treats a whole hoisted list as one block and accepts a marker that has
    drifted into a neighbouring bullet. Unreachable by mutating source against a
    healthy tree — `_blocks` is a superset of `_lines` and the span function
    takes the tightest span, so adding paragraph blocks can only lower it. Feed
    it the split directly instead.
    """
    split = (
        "- **Never end a turn with nothing in flight.** status text and the "
        "next tool call go in the same message.\n"
        "- **An unrelated rule.** whether a pending event will re-invoke the "
        "session is not the point here, and announcing the next step "
        "is not a mechanism.\n"
    )
    assert _why_not(split, paragraphs=False) is not None, (
        "markers split across two adjacent bullets were accepted at line "
        "granularity — the rule can be dismantled one bullet at a time"
    )
    # And the contrast that makes the choice load-bearing rather than arbitrary:
    # at paragraph granularity the same split passes, because the bullet list is
    # a single block.
    assert _why_not(split, paragraphs=True) is None, (
        "the fixture no longer demonstrates the difference between the two "
        "granularities; rewrite it so the contrast still holds"
    )
