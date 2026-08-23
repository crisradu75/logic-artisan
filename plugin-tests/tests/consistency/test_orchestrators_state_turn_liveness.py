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

Two design decisions, both deliberate:

**The family is a declared literal, not a derived match.** An earlier revision
keyed it on the phrase "ready to continue", which is measurable
(`grep -ril "ready to continue" --include=SKILL.md .` hits exactly `multi-pr` and
`multi-lite`) but wrong in the direction that bites: it silently EXCLUDED
`spec-to-pr`, where this rule originated, and `multi-spec`, which loops over N
changes with the same between-unit seam. A derived key cannot fail when it stops
matching something it never matched. A literal set forces a deliberate edit when
a new chain skill appears — and that edit is the moment someone must also give it
a seam entry, which is what closes the gap below by construction.

**Markers are checked for ADJACENCY, not file-wide presence.** `in the same
message` is ordinary procedural English — it appears in `change-loop.md` step
prose unrelated to this rule — so a file-wide `in` test would stay green with the
liveness rule deleted and a stray sibling sentence carrying the phrase. All three
markers must land in ONE block: a single line (the `SKILL.md` bullets are single
long lines) or one blank-line-delimited paragraph (the seam restatements are
hard-wrapped).

Spec: `openspec/specs/cla-plugin/spec.md`, "Unattended-run turn liveness".
"""

from __future__ import annotations

from pathlib import Path

_PLUGIN_ROOT = Path(__file__).resolve().parents[3] / ".claude" / "plugins" / "cla"
_SKILLS = _PLUGIN_ROOT / "skills"

_MECHANICAL = "in the same message"
_DISCRIMINATOR = "pending event"
_NOT_A_MECHANISM = "is not a mechanism"
_MARKERS = (_MECHANICAL, _DISCRIMINATOR, _NOT_A_MECHANISM)

# skill -> (seam reference file, the anchor naming that seam) or None when the
# skill has no per-unit loop in a reference file. `spec-to-pr` is the rule's
# origin and its phase boundaries are stated inline in SKILL.md, so it has a
# hoisted copy to guard and no seam.
_FAMILY: dict[str, tuple[str, str] | None] = {
    "multi-pr": ("references/change-loop.md", "move to the next change"),
    "multi-lite": ("references/candidate-loop.md", "move to the next candidate"),
    "multi-spec": ("references/authoring-brief.md", "before starting the next change"),
    "spec-to-pr": None,
}


def _blocks(text: str) -> list[str]:
    """Every single line, plus every blank-line-delimited paragraph, lowercased.

    Two granularities because the rule is written at two: a hoisted `SKILL.md`
    bullet is one very long line, while a seam restatement in a reference file is
    hard-wrapped across several. Checking both keeps the adjacency requirement
    real without forcing either file to be reformatted.

    Whitespace inside each block is collapsed to single spaces. Without that, a
    marker straddling a hard wrap (`in the same\\nmessage`) reads as absent and
    the guard fails on formatting rather than on substance — a false failure that
    trains readers to reformat prose to satisfy a matcher. Real, not theoretical:
    it fired on this scope's own seam text the first time it ran.
    """
    low = text.lower()
    return _lines(text) + [
        " ".join(p.split()) for p in low.split("\n\n") if p.strip()
    ]


def _lines(text: str) -> list[str]:
    """Every non-blank line, lowercased, with whitespace collapsed."""
    return [
        " ".join(line.split())
        for line in text.lower().splitlines()
        if line.strip()
    ]


def _missing_markers(text: str, *, paragraphs: bool) -> list[str]:
    """The markers absent from EVERY block. Empty means one block holds all three.

    `paragraphs=False` restricts the check to single lines, which is the correct
    granularity for a hoisted `SKILL.md` rule: it lives in exactly one bullet, and
    markdown bullets are NOT blank-line separated, so paragraph granularity treats
    a whole bullet list as one block and accepts a marker that has drifted into a
    neighbouring bullet. A mutant proved that: moving "is not a mechanism" out of
    the rule into an adjacent bullet SURVIVED until this split existed. Seam
    restatements are genuine hard-wrapped prose paragraphs, so they pass True.
    """
    blocks = _blocks(text) if paragraphs else _lines(text)
    for block in blocks:
        if all(m in block for m in _MARKERS):
            return []
    # No block carried all three; report which are absent file-wide, since that
    # is the actionable half — a marker present but scattered is a different fix
    # from one that was deleted.
    low = text.lower()
    scattered = [m for m in _MARKERS if m in low]
    absent = [m for m in _MARKERS if m not in low]
    return absent or [f"present but never adjacent: {scattered}"]


def _skill_md(name: str) -> Path:
    return _SKILLS / name / "SKILL.md"


def test_the_declared_family_matches_the_tree():
    """Non-vacuity partner AND a drift tripwire.

    `==` rather than `>=` deliberately: a new chain orchestrator must be added
    here by hand, and that edit is where its seam entry gets written too.
    """
    assert _SKILLS.is_dir(), f"{_SKILLS} is not a directory — the guard scans nothing"
    for name in _FAMILY:
        assert _skill_md(name).is_file(), (
            f"{name} is declared in _FAMILY but {_skill_md(name)} does not exist — "
            "the skill was renamed or removed; update _FAMILY deliberately"
        )
    # Any skill promising no inter-unit pauses is a chain orchestrator and belongs
    # in _FAMILY. This is the direction the old derived key could not check.
    promising = {
        p.parent.name
        for p in _SKILLS.glob("*/SKILL.md")
        if "ready to continue" in p.read_text(encoding="utf-8").lower()
    }
    assert promising, (
        "no SKILL.md promises 'ready to continue' pauses any more — either the "
        "convention changed or the tree moved; re-derive _FAMILY deliberately"
    )
    assert promising <= set(_FAMILY), (
        f"{sorted(promising - set(_FAMILY))} promise no inter-unit pauses but are "
        "not in _FAMILY, so nothing checks their turn-liveness rule"
    )


def test_every_family_skill_states_the_turn_liveness_rule():
    checked = 0
    for name in _FAMILY:
        missing = _missing_markers(
            _skill_md(name).read_text(encoding="utf-8"), paragraphs=False
        )
        assert not missing, (
            f"{name}/SKILL.md has no single block carrying the whole turn-liveness "
            f"rule — {missing}. All three markers must sit in one bullet: the rule "
            "is only load-bearing if the mechanical check, the pending-event "
            "discriminator, and 'announcing is not a mechanism' arrive together."
        )
        checked += 1
    assert checked == len(_FAMILY), (
        f"checked {checked} of {len(_FAMILY)} family skills — the loop above ran "
        "short, so this test proved less than it claims"
    )


def test_every_family_seam_restates_the_rule():
    """The gap opens BETWEEN units, which is where the reference file carrying the
    loop has been read and closed and the orchestrator is running on the SKILL.md
    summary. The hoisted copy is not enough on its own."""
    checked = 0
    for name, seam in _FAMILY.items():
        if seam is None:
            continue
        rel, anchor = seam
        path = _SKILLS / name / Path(rel)
        assert path.is_file(), (
            f"{path} is missing — {name}'s seam moved; re-point _FAMILY rather "
            "than deleting the check"
        )
        text = path.read_text(encoding="utf-8")
        assert anchor in text.lower(), (
            f"{rel} no longer contains {anchor!r}, the seam this check is anchored "
            "to; re-point _FAMILY rather than deleting the check"
        )
        missing = _missing_markers(text, paragraphs=True)
        assert not missing, (
            f"{name}'s seam ({rel}) does not restate the turn-liveness rule — "
            f"{missing}. The hoisted rule in SKILL.md binds, but this is the point "
            "at which that file is no longer in front of the reader."
        )
        checked += 1

    expected = sum(1 for v in _FAMILY.values() if v is not None)
    assert checked == expected, (
        f"checked {checked} seams, expected {expected} — the loop ran short and "
        "this test proved less than it claims"
    )
    assert checked > 0, "no family skill declares a seam file; nothing was checked"
