"""A measurement claim must name the command that produced it, at the commit.

The project's own pre-ship guidance has said this for months and it kept failing
anyway, in work that was otherwise careful — several separate escapes in a single
session, every one of them caught by review rather than by the author. The
diagnosis was not that the rule is unclear. It is that the rule had **no
chokepoint**:

    grep -rin "five checks\\|check 3" .claude/plugins/cla/     -> 0 hits

No shipped asset referenced it at all. And of the five such checks the project
states, exactly one has a moment-of-edit mechanism — `hooks/warn-wholesale-rewrite.py`,
wired on the `Write` matcher in `hooks/hooks.json`, for the rewrote-a-file check.

    ls .claude/plugins/cla/hooks/*.py                          -> 13

Thirteen files: ten leaf hooks, two dispatchers and `_dispatch_lib.py`. Reading
the other nine leaf hooks, none addresses the remaining four checks — they cover
destructive git, `cd` in bash, recursive delete, worktree path escape, heredoc
escape mangling, stacked-PR merge, stray scratch artifacts, comment date rot, and
commit provenance. Project guidance loads at session start;
the claims get written hundreds of tool calls later, by which time the rule is out
of context and the claim already reads as settled.

So the rule is attached to a place the author is **already stopping and already
assembling claims**: the pre-commit step in the Ship phase. Its output is an
artifact rather than an answer — one `Measured-by: <command> — <claim>` git
trailer per claim, in the commit message, where a reader can re-run it. A step
whose discharge is "yes" certifies whatever it stopped checking; a step whose
discharge is a runnable command string is falsifiable by running it.

**Why this is not a keyword scan over the diff.** That was the obvious design and
it is measured to be the wrong one. The same idea was already built and withdrawn
once in this repo for the sibling case (a scan of ticked task bodies — see
`openspec/specs/cla-plugin/spec.md`, "Completeness signals read the claim, not the
glyph", and GitHub issue #105: 173 ticked tasks, 6 lines reached, 0 true
positives, 4 false positives, trip words colliding with vocabulary the skills use
deliberately). Re-measured for the diff-side variant before choosing:

    git log -8 -p --format= --unified=0 | grep -cE '^\\+'
      -> 7280 added lines

    git log -8 -p --format= --unified=0 | grep -E '^\\+' \\
      | grep -icE 'measured|verified|counted|\\bzero\\b|no (violation|hit|match|instance|offender)s?\\b|[0-9]+ of [0-9]+|exactly (one|two|three|four|five|six|seven|eight|nine|ten|[0-9]+)\\b'
      -> 169 hits (2.3%)

A 21-line systematic sample of those 169 (every 8th hit) was dominated by test
function names, string literals inside assertions, spec scenario prose, and
claims that ALREADY named their command. That is issue #105's failure shape
again, so the mechanism is authored rather than discovered: you wrote the claims,
so finding them needs no scanner, and the artifact is what gets checked.

**What this guard can and cannot show.** It reads prose. It pins that the rule
is stated, at every commit chokepoint, with its wording intact — nothing more.
It does not check a single commit, and no gate does: a false trailer ships
silently, and the design's honest claim is narrower than enforcement. What it
buys is that the obligation sits in text read at the moment of committing rather
than in a file loaded at session start, and that its output is a durable artifact
a reviewer can falsify later. The adoption question — whether trailers are
actually being written — is answered by the ledger column in
`hooks/log-commit-provenance.py`, not here.

So the constants below are properties of the rule's WORDING. Each is a
clause a rewrite could drop while leaving something that still reads like the
rule:

- `_FORMAT` — the trailer's shape INCLUDING "runnable as written". Without that
  clause "Measured-by: the test suite" satisfies the rule and reproduces nothing.
- `_TWO_EXITS` — that a claim with no command is edited (run it, or delete it),
  never carried forward with the command owed.
- `_NO_NULL` — that a change asserting nothing writes no trailer, rather than a
  `Measured-by: none` line. A null certification is the ceremony failure this
  whole design is aimed at: it reads as evidence that a check happened.
- `_SAME_TREE` — that a pair asserting SAMENESS comes from one tree. A
  before/after delta is deliberately NOT caught: it is two trees by
  construction. Per-trailer verifiability does not reach the claim a pair
  makes: both commands can be real, both numbers true, and the sameness
  between them measured on nothing. Added for issue #208, whose example pairs
  4906 and 4894 from different trees and asserts "same pass/skip counts",
  citing a third run that appears nowhere.

The first three are `_MARKERS`, and the window below proves they are stated
TOGETHER as one rule. `_SAME_TREE` is checked on its own instead, by
`test_every_family_file_states_the_comparison_clause`: it has to be PRESENT,
which is a different property, and it was briefly a fourth marker — that took
window slack from 356 to 164 characters and pinned it no harder. Adjacency is a
budget; presence is not.

Two design decisions, each forced by something measured rather than assumed:

**The token is `Measured-by:`, not `Measured:`.** The shipped tree already uses
bare `Measured:` as ordinary narrative prose:

    git grep -l "Measured:" -- .claude/plugins/cla | wc -l      -> 4

Four tracked files, none of them a trailer. (`grep -rl` over the same directory
answers 5 — it opens a `__pycache__` `.pyc` too. Right count, wrong command; the
tracked-files form is the one that reproduces.) A bare token would make both the
drift tripwire below and `git log --grep='^Measured-by:'` collide with that
prose, so the hyphenated git-trailer form is load-bearing, not cosmetic.

**Adjacency is a tightest-WINDOW over the file, not a block test.** The rule is
written at two granularities: one long hoisted bullet in `spec-to-pr/SKILL.md`,
and three consecutive paragraphs (lead-in, fenced format, discharge rule) in the
other three files. A block test rejects the second shape outright.

The window is computed over every COMBINATION of marker occurrences. Today that
product is over singletons — each of the three markers occurs exactly once per
file (the `marker_occ` column below) — so the combinatorial form is defensive,
not currently load-bearing, and a plain min/max over first occurrences would
give the same answer. It is written this way because the thing that recurs is
`_TRAILER`, not a marker: `spec-to-pr/SKILL.md` names the trailer 5 times, first
in the message-style table and last in Ship, a spread of 38123 characters. The
moment any marker picks up a second occurrence — the likely way, since the
trailer token is embedded in two of them — first-occurrence min/max starts
reporting a window that spans the file.

Measured, first marker to last, and from the nearest preceding pre-commit check:

    file                             span   gap   marker_occ
    lite-pr/SKILL.md                  644  1430    1, 1, 1
    spec-to-pr/SKILL.md               487   760    1, 1, 1
    spec-to-pr/references/ship.md     644  2538    1, 1, 1
    spec-to-pr/references/revise.md   626   466    1, 1, 1

Command: `_best_window` and `_occurrences` below, over the four files `_FAMILY`
declares — and `test_the_measured_table_above_is_still_the_real_one` re-derives
every cell on each run, so this table cannot go stale without failing. The window
cap is 1000, clearing the widest real span (644) by 356 characters; the
chokepoint-gap bound is 2600, clearing the widest real gap (2538) by **62
characters**. Both literals live once, at their assignments below.

THAT GAP HEADROOM IS 2.4%, AND IT IS THE NUMBER TO READ BEFORE EDITING. One
added sentence at `ship.md` §2a's pre-commit stop will breach it. That is not a
reason to raise the bound — the bound is what makes the rule part of the stop
rather than advice filed near it. It is a reason to put new text at that stop
somewhere other than between `git_state.py` and the measurement rule, or to
trim while adding.

This table was stale once, which is why the test now derives it. The `[DEBUG-`
scan added to `ship.md` §2a moved two rows (`spec-to-pr/SKILL.md` 418→760,
`ship.md` 1952→2538) and the docstring still claimed the old figures and ~33%
headroom. Nothing failed: the guard checks the tree against its bounds, never
its own prose against the tree. A docstring stating a measurement is a fact with
no guard — the same defect this whole file exists to prevent in the plugin,
reproduced inside the file that prevents it.

Every looping test carries its own floor, in the same function. A floor in a
separate test function is coupled to nothing: a `-k`, a skip, or a collection
error leaves the real test silently green.

Spec: `openspec/specs/cla-plugin/spec.md`, "A measurement names the command that
produced it".
"""

from __future__ import annotations

import itertools
import re
import sys
from pathlib import Path

import pytest

_PLUGIN_ROOT = Path(__file__).resolve().parents[3] / ".claude" / "plugins" / "cla"
_SKILLS = _PLUGIN_ROOT / "skills"

_TRAILER = "measured-by:"
_FORMAT = (
    "measured-by: <the exact command, runnable as written> — <the claim it produced>"
)
_TWO_EXITS = "run the command now, or delete the claim"
_NO_NULL = "never `measured-by: none`"
_SAME_TREE = "must come from one tree"
_MARKERS = (_FORMAT, _TWO_EXITS, _NO_NULL)

_MAX_WINDOW = 1000

# The chokepoint anchor. The rule is only attached to the pre-commit stop if it
# is stated after it; stated earlier it is authoring-time advice again, which is
# the instrument that already failed.
_CHOKEPOINT = "git_state.py"

# How far past that check the rule may sit and still be part of it.
_MAX_CHOKEPOINT_GAP = 2600

# …and the far side of the sandwich. A bounded gap alone is not enough: three of
# these files mention the pre-commit check again in a trailing reference list
# (`lite-pr/SKILL.md` does so at the very end), so a rule block moved to EOF
# lands just after that mention and clears the gap test. Requiring a commit
# action AFTER the rule closes it — nothing commits after a reference index.
_COMMIT_ACTIONS = ("git commit", "commit-push-pr")

# Files carrying the rule, declared as a literal rather than derived. A derived
# key cannot fail when it stops matching something it never matched — the exact
# way the sibling turn-liveness guard's first revision excluded the skill the
# rule originated in.
_FAMILY = (
    "lite-pr/SKILL.md",
    "spec-to-pr/SKILL.md",
    "spec-to-pr/references/ship.md",
    "spec-to-pr/references/revise.md",
)

# Files that NAME the trailer without INSTRUCTING anyone to write one, keyed to
# the reason they are not family. The family test asks whether a file's copy of
# the rule kept its properties; a file that never states the rule has no copy to
# keep, and forcing it in would demand a pre-commit chokepoint it has no commit
# step to attach to.
#
# The distinction is producer versus consumer. `codify-retro` READS the ledger the
# trailer feeds and has to warn that rows written before 2026-09-06 understate the
# rate — the hook parsed the trailer with git, which sees only the last contiguous
# `Key: value` block, so a blank line before the attribution lines hid the
# measurements. It cannot give that warning without naming the field it is about.
#
# Each entry is verified below to still mention the trailer AND still not instruct
# writing one, so an exemption cannot outlive its reason or quietly cover a file
# that has since grown a commit step.
_NAMES_BUT_DOES_NOT_INSTRUCT = {
    "codify-retro/SKILL.md":
        "a retro that reads the ledger; it warns about historic rows, and has no "
        "commit step to hang the rule on",
}


def _path(rel: str) -> Path:
    return _SKILLS / Path(rel)


def _occurrences(text: str, needle: str) -> list[int]:
    out: list[int] = []
    i = text.find(needle)
    while i >= 0:
        out.append(i)
        i = text.find(needle, i + 1)
    return out


def _best_window(text: str) -> tuple[int, int] | None:
    """`(span, start)` for the tightest region carrying all three markers, over
    every combination of their occurrences — or None when a marker is absent."""
    occ = [_occurrences(text, m) for m in _MARKERS]
    if not all(occ):
        return None
    best: tuple[int, int] | None = None
    for combo in itertools.product(*occ):
        start = min(combo)
        span = max(p + len(m) for p, m in zip(combo, _MARKERS)) - start
        if best is None or span < best[0]:
            best = (span, start)
    return best


def _tightest_window(text: str) -> int | None:
    got = _best_window(text)
    return None if got is None else got[0]


def _why_not(text: str) -> str | None:
    """None when the rule is present, tight, and AT the chokepoint. Else why."""
    low = text.lower()
    got = _best_window(low)
    if got is None:
        absent = [m for m in _MARKERS if m not in low]
        return f"marker(s) absent from the file entirely: {absent}"
    window, start = got
    if window > _MAX_WINDOW:
        return (
            f"the three markers are present but their tightest window is {window} "
            f"chars (> {_MAX_WINDOW}) — they are scattered rather than stated "
            "together as one rule"
        )
    # NEAREST PRECEDING mention, and a bounded gap. "After the first mention of
    # the pre-commit check" was the original test and it is nearly free: a
    # reviewer moved the whole rule block to the very END of a file and it still
    # passed, because 40.8% of that file sits after the first mention. The
    # rule is only attached to the stop if it is stated AT it.
    preceding = [a for a in _occurrences(low, _CHOKEPOINT) if a <= start]
    if not preceding:
        if _CHOKEPOINT not in low:
            return (
                f"the file never mentions {_CHOKEPOINT!r}, so the rule is not "
                "anchored to a pre-commit stop at all"
            )
        return (
            "the rule is stated before every pre-commit check in the file, so it "
            "reads as authoring-time advice rather than a step at the chokepoint"
        )
    gap = start - max(preceding)
    if gap > _MAX_CHOKEPOINT_GAP:
        return (
            f"the rule sits {gap} chars past the nearest preceding "
            f"{_CHOKEPOINT!r} (> {_MAX_CHOKEPOINT_GAP}) — far enough downstream "
            "that it is no longer part of that stop"
        )
    end = start + window
    if not any(a > end for act in _COMMIT_ACTIONS for a in _occurrences(low, act)):
        return (
            "no commit action follows the rule, so it is not sitting between the "
            "pre-commit check and the commit — the position a trailing reference "
            "list also satisfies, which is why the gap alone is not enough"
        )
    return None


def test_the_declared_family_matches_the_tree():
    """Non-vacuity for the constants, plus the drift tripwire.

    Emptying `_MARKERS` would make `all(occ)` on an empty list vacuously True and
    `min()` over an empty product raise, so pin the constants before anything
    leans on them."""
    assert len(_MARKERS) == 3 and all(_MARKERS), (
        f"_MARKERS must hold three non-empty phrases, got {_MARKERS!r}"
    )
    # Pinned to its exact value, for the same reason `_TRAILER` is pinned above.
    # The presence check this feeds is a substring test over prose that talks
    # about trees constantly, so a weakened phrase — "tree", "same" — would be
    # satisfied by text that states no such rule, and the check would pass
    # vacuously while the clause was gone.
    assert _SAME_TREE == "must come from one tree", (
        f"_SAME_TREE is pinned to its exact phrase; got {_SAME_TREE!r}. Weakening "
        "it makes `test_every_family_file_states_the_comparison_clause` vacuous"
    )
    assert _MAX_WINDOW > 0 and _TRAILER and _CHOKEPOINT
    assert _TRAILER != "measured:", (
        "the token must stay hyphenated: bare `Measured:` is already ordinary "
        "narrative prose in the shipped tree, so it collides with both the "
        "tripwire below and `git log --grep`"
    )
    assert _SKILLS.is_dir(), f"{_SKILLS} is not a directory — the guard scans nothing"
    assert len(_FAMILY) >= 4, (
        f"_FAMILY declares {len(_FAMILY)} files; the four commit chokepoints are "
        "the floor — the two Ship steps plus Revise's fix-round commit and the "
        "Ship reference. Removing one silently shrinks every check below."
    )
    for rel in _FAMILY:
        assert _path(rel).is_file(), f"{rel} is declared in _FAMILY but does not exist"

    # The direction a declared literal cannot check on its own: a FOURTH file
    # picks the rule up (a new orchestrator, a copied reference) and drifts
    # unpoliced. Any shipped skill prose naming the trailer belongs here.
    mentioning = {
        p.relative_to(_SKILLS).as_posix()
        for p in _SKILLS.rglob("*.md")
        if _TRAILER in p.read_text(encoding="utf-8").lower()
    }
    assert mentioning, (
        f"no shipped skill prose mentions {_TRAILER!r} any more — the rule has "
        "left the plugin entirely and every check below is scanning nothing"
    )
    unaccounted = mentioning - set(_FAMILY) - set(_NAMES_BUT_DOES_NOT_INSTRUCT)
    assert not unaccounted, (
        f"{sorted(unaccounted)} state the measurement trailer but are neither in "
        "_FAMILY nor exempted, so nothing checks that their copy kept its "
        "properties. Add to _FAMILY if the file tells an author to WRITE a "
        "trailer; to _NAMES_BUT_DOES_NOT_INSTRUCT, with a reason, if it only "
        "names the field while reading it back"
    )


def test_every_exemption_still_earns_itself():
    """An exemption must not outlive its reason, nor quietly cover a file that has
    since grown a commit step. Both halves are checked, because either one going
    stale reopens the gap the family test exists to close."""
    for rel, reason in _NAMES_BUT_DOES_NOT_INSTRUCT.items():
        assert reason.strip(), f"{rel} is exempt with no reason given"
        path = _path(rel)
        assert path.is_file(), (
            f"{rel} is exempted but does not exist — delete the entry"
        )
        text = path.read_text(encoding="utf-8")
        assert _TRAILER in text.lower(), (
            f"{rel} no longer mentions {_TRAILER!r}, so the exemption covers "
            f"nothing — delete the entry"
        )
        assert rel not in _FAMILY, (
            f"{rel} is both declared family and exempted from it — the family "
            f"test would then never run on a file that claims to carry the rule"
        )


def test_every_family_file_states_the_whole_rule_at_the_chokepoint():
    seen = set()
    for rel in _FAMILY:
        why = _why_not(_path(rel).read_text(encoding="utf-8"))
        assert why is None, (
            f"{rel} does not carry the whole measurement rule at the pre-commit "
            f"stop — {why}. The rule is only load-bearing when the trailer's "
            "runnable-as-written format, the two edit-shaped exits, and the "
            "no-null-certification clause arrive together, after the stop."
        )
        seen.add(rel)
    # Floor INSIDE this test. `checked == len(_FAMILY)` is a tautology — the loop
    # has no break — so it passes with _FAMILY emptied, having read no file.
    assert seen == set(_FAMILY) and len(seen) >= 4, (
        f"checked {sorted(seen)}; expected all {len(_FAMILY)} declared files"
    )


def test_every_family_file_states_the_comparison_clause():
    """Issue #208: per-trailer verifiability does not reach the claim a PAIR makes.

    Two trailers can each name a real command and hold a true number while the
    pair asserts a third thing — that conditions matched — with nothing behind
    it. The issue's worked example pairs 4906 and 4894 from different trees,
    asserts "same pass/skip counts", and cites a comparison run that appears
    nowhere.

    Checked here rather than as a fourth `_MARKERS` entry. The window proves the
    core clauses are stated TOGETHER; this clause has to be PRESENT, which is a
    different property — and marking it charged the adjacency budget, taking
    window slack from 356 to 164 characters without pinning it any harder.

    What it does NOT forbid is a before/after delta, which is two trees by
    construction and is the normal way to state a speedup or a count change. The
    clause is about a pair asserting SAMENESS, so the assertion below is the
    sameness phrase, not the word "comparison".
    """
    missing = [
        rel for rel in _FAMILY
        if _SAME_TREE not in _path(rel).read_text(encoding="utf-8").lower()
    ]
    assert not missing, (
        f"{missing} state the measurement rule without the comparison clause "
        f"({_SAME_TREE!r}). A pair of numbers asserting sameness across two trees "
        "is the shape issue #208 reports: every trailer individually verifiable, "
        "and the claim between them measured on nothing."
    )
    assert len(_FAMILY) >= 4, (
        f"_FAMILY holds {len(_FAMILY)} files; the loop above checks nothing it "
        "does not declare, so the floor travels with it"
    )


# --------------------------------------------------------------------------- #
# The guard's own non-vacuity. Both floors below defend against a state the tree
# is not currently in, so a mutation over the real files cannot reach them —
# the case `_shared/references/test-quality.md` calls out, and it prefers this
# form: assert the check can still fire.
# --------------------------------------------------------------------------- #

_CONTENT_CHECKS = (
    test_the_declared_family_matches_the_tree,
    test_every_family_file_states_the_whole_rule_at_the_chokepoint,
)


def _surviving(checks) -> int:
    alive = 0
    for check in checks:
        try:
            check()
        except Exception:
            continue
        alive += 1
    return alive


def test_the_checks_all_pass_on_the_real_tree():
    """Baseline. Without it the tamper cases are satisfiable by a guard that
    fails on everything, including the truth."""
    assert _surviving(_CONTENT_CHECKS) == len(_CONTENT_CHECKS)


@pytest.mark.parametrize(
    "name,attribute,value",
    [
        ("the declared family is emptied", "_FAMILY", ()),
        ("the marker set is emptied", "_MARKERS", ()),
        (
            "a call site silently drops out of the family",
            "_FAMILY",
            ("spec-to-pr/SKILL.md", "spec-to-pr/references/ship.md"),
        ),
    ],
)
def test_the_guard_notices_when_its_own_state_is_gutted(
    name, attribute, value, monkeypatch
):
    monkeypatch.setattr(sys.modules[__name__], attribute, value)
    assert _surviving(_CONTENT_CHECKS) < len(_CONTENT_CHECKS), (
        f"every check still passed with {name} — the guard is vacuous under this "
        "tampering"
    )


def _measured_row(rel: str) -> tuple[int, int, tuple[int, ...]]:
    """`(span, gap, marker_occurrences)` for one family file, derived the same
    way `_why_not` derives them — lower-cased text, and the gap measured from the
    nearest PRECEDING chokepoint rather than the first one in the file."""
    low = _path(rel).read_text(encoding="utf-8").lower()
    span, start = _best_window(low)
    preceding = [i for i in _occurrences(low, _CHOKEPOINT.lower()) if i < start]
    gap = start - max(preceding)
    return span, gap, tuple(len(_occurrences(low, m)) for m in _MARKERS)


def test_the_measured_table_above_is_still_the_real_one():
    """This module's docstring states a span/gap per family file. Re-derive every
    cell and fail when one has moved.

    WHY THIS EXISTS. The table was stale for exactly one change: adding the
    `[DEBUG-` scan to `ship.md` §2a moved two gaps (418→760 and 1952→2538) and
    the docstring kept claiming the old pair plus ~33% headroom, while real
    headroom had fallen to 62 characters. Every test here passed throughout,
    because they all check the TREE against the bounds and none checks the
    PROSE against the tree.

    That is this file's own subject turned inward: a measurement written down
    without the command that reproduces it is a fact with no guard. The fix is
    the one the plugin is held to — derive it, or do not state it.

    The docstring stays rather than being deleted in favour of a bare command,
    because the gap figure is what a future editor needs BEFORE deciding where
    to put a new sentence, and a number nobody can see until they run something
    is a number nobody reads.
    """
    rows = re.findall(
        r"^\s{4}(\S+)\s+(\d+)\s+(\d+)\s+([\d, ]+)$", __doc__, re.M
    )
    assert len(rows) == len(_FAMILY), (
        f"the docstring table has {len(rows)} rows for {len(_FAMILY)} family "
        "files — a row was added, dropped, or reformatted out of this parse"
    )

    drifted = []
    for rel, span_s, gap_s, occ_s in rows:
        assert rel in _FAMILY, f"docstring table names {rel!r}, which is not family"
        span, gap, occ = _measured_row(rel)
        claimed_occ = tuple(int(n) for n in occ_s.replace(" ", "").split(","))
        if (span, gap, occ) != (int(span_s), int(gap_s), claimed_occ):
            drifted.append(
                f"  {rel}: docstring says span={span_s} gap={gap_s} "
                f"occ={claimed_occ}; measured span={span} gap={gap} occ={occ}"
            )
    assert not drifted, (
        "this module's docstring table no longer matches the tree:\n"
        + "\n".join(drifted)
        + "\n\nUpdate the table AND the headroom sentence below it."
    )


def test_the_stated_gap_headroom_is_the_real_one():
    """The docstring's headroom figure, checked the same way as the table.

    Separate from the table test on purpose: the headroom sentence is the part
    an editor actually acts on, and it is stated in two places (characters and a
    percentage). A reader who trusts a stale "~33%" adds a paragraph that a
    correct "2.4%" would have stopped.
    """
    widest = max(_measured_row(rel)[1] for rel in _FAMILY)
    slack = _MAX_CHOKEPOINT_GAP - widest
    assert f"widest real gap ({widest})" in __doc__, (
        f"the docstring no longer states the widest real gap as {widest}"
    )
    assert f"by **{slack}\ncharacters**" in __doc__ or f"by **{slack} characters**" in __doc__, (
        f"the docstring no longer states the gap slack as {slack} characters"
    )
    pct = f"{slack / widest * 100:.1f}%"
    assert pct in __doc__, (
        f"the docstring no longer states the gap headroom as {pct} "
        f"(slack {slack} over widest gap {widest})"
    )


def test_the_window_cap_is_load_bearing():
    """The cap, exercised the only way it can be: keep the real cap and feed it
    the bad input. Removing the cap AND supplying a wide region proves nothing,
    since the cap is the sole check that would catch it."""
    scattered = (
        _CHOKEPOINT
        + " "
        + _FORMAT
        + ("filler " * 200)
        + _TWO_EXITS
        + ("filler " * 40)
        + _NO_NULL
    )
    assert _tightest_window(scattered) > _MAX_WINDOW, (
        "the fixture must exceed the cap to test it"
    )
    why = _why_not(scattered)
    assert why is not None and "window" in why, (
        f"markers scattered beyond the cap were accepted as one rule; _why_not "
        f"returned {why!r}"
    )


def _tight_rule() -> str:
    return _FORMAT + " " + _TWO_EXITS + " " + _NO_NULL


def _sandwich(before: str = "", after: str = "") -> str:
    """The healthy shape: pre-commit check, then the rule, then a commit."""
    return f"{before}{_CHOKEPOINT} {_tight_rule()} {after}{_COMMIT_ACTIONS[0]} -m x"


def test_the_chokepoint_anchor_is_load_bearing():
    """The rule stated BEFORE the pre-commit check is authoring-time advice — the
    instrument that already failed — so it must be rejected even though all three
    markers are present and tight."""
    assert _tightest_window(_tight_rule()) <= _MAX_WINDOW, "fixture must clear the cap"
    assert _why_not(_sandwich()) is None, (
        "the healthy shape must be accepted, or every rejection below proves "
        "nothing but that the check rejects everything"
    )
    ahead = f"{_tight_rule()} ... later ... {_CHOKEPOINT} ... {_COMMIT_ACTIONS[0]}"
    assert _why_not(ahead) is not None, (
        "the rule stated ahead of the pre-commit stop was accepted"
    )


def test_a_rule_far_downstream_of_the_check_is_rejected():
    """The gap bound. Without it, ANY position after the first mention passed —
    measured on the real tree, 40.8% of `lite-pr/SKILL.md` (8409 of 20619
    characters sit after its first `git_state.py` mention)."""
    far = _sandwich(after="")
    far = far.replace(" " + _tight_rule(), " " + ("filler " * 500) + _tight_rule())
    assert _why_not(far) is not None, (
        "a rule thousands of characters downstream of the check was accepted as "
        "part of it"
    )


def test_the_rule_parked_after_a_trailing_reference_mention_is_rejected():
    """The reviewer's actual attack, as a regression test.

    `lite-pr/SKILL.md` names the pre-commit check a second time in its trailing
    file list, 220 characters from EOF, and everything after its FIRST mention
    is 8409 characters — 40.8% of the file — which is how much territory the
    original "after the check" test accepted. Moving the whole rule block to the
    end satisfies BOTH the window cap and the gap bound, because the nearest
    preceding mention is then that trailing one. Only the commit-action
    requirement rejects it: nothing commits after a reference index.

    Command: `_occurrences(low, _CHOKEPOINT)` over that file against `len(low)`
    — [12210, 20399] of 20619.
    """
    parked = f"{_CHOKEPOINT} ... {_COMMIT_ACTIONS[0]} -m x ... files: {_CHOKEPOINT} — reused for the pre-commit check. {_tight_rule()}"
    why = _why_not(parked)
    assert why is not None and "commit action" in why, (
        f"the rule parked after a trailing reference mention was accepted; "
        f"_why_not returned {why!r}"
    )
    # And the contrast that makes it a real discriminator rather than a check
    # that rejects everything with a mention near the end.
    assert _why_not(_sandwich(before=f"files: {_CHOKEPOINT} note. ")) is None


def test_the_format_marker_carries_the_runnability_clause():
    """`Measured-by: the test suite` satisfies a bare-token rule and reproduces
    nothing. The clause is what makes the trailer re-runnable, so it is asserted
    here rather than left to survive as an unexamined substring."""
    assert "runnable as written" in _FORMAT, (
        "the format marker lost its runnability clause — a trailer naming no "
        "real invocation is the failure mode the whole design exists to close"
    )
