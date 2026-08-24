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

This guard pins that the rule reaches every skill that owns a commit-creating
Ship step, and that it keeps the three properties that make it more than advice:

- `_FORMAT` — the trailer's shape INCLUDING "runnable as written". Without that
  clause "Measured-by: the test suite" satisfies the rule and reproduces nothing.
- `_TWO_EXITS` — that a claim with no command is edited (run it, or delete it),
  never carried forward with the command owed.
- `_NO_NULL` — that a change asserting nothing writes no trailer, rather than a
  `Measured-by: none` line. A null certification is the ceremony failure this
  whole design is aimed at: it reads as evidence that a check happened.

Two design decisions, each forced by something measured rather than assumed:

**The token is `Measured-by:`, not `Measured:`.** The shipped tree already uses
bare `Measured:` as ordinary narrative prose (`grep -rl "Measured:"
.claude/plugins/cla/ | wc -l` -> 4 files, none of them a trailer). A bare token would make
both the drift tripwire below and `git log --grep='^Measured-by:'` collide with
that prose, so the hyphenated git-trailer form is load-bearing, not cosmetic.

**Adjacency is a tightest-WINDOW over the file, not a block test.** The rule is
written at two granularities: one long hoisted bullet in `spec-to-pr/SKILL.md`,
and three consecutive paragraphs (lead-in, fenced format, discharge rule) in the
other two files. A block test rejects the second shape outright, and a plain
min/max over first occurrences is defeated by a file that legitimately mentions
the trailer twice — `spec-to-pr/SKILL.md` does, in the message-style table and
again in Ship, 37905 characters apart. The tightest window over all occurrence
combinations handles both. Measured spans of the real rule:

    lite-pr/SKILL.md                     644
    spec-to-pr/SKILL.md                  487
    spec-to-pr/references/ship.md        644

Command: `_tightest_window` below, over the same three files. 1000 clears the
widest real statement with ~55% headroom and rejects markers scattered across a
region half again as large.

Every looping test carries its own floor, in the same function. A floor in a
separate test function is coupled to nothing: a `-k`, a skip, or a collection
error leaves the real test silently green.

Spec: `openspec/specs/cla-plugin/spec.md`, "A measurement names the command that
produced it".
"""

from __future__ import annotations

import itertools
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
_MARKERS = (_FORMAT, _TWO_EXITS, _NO_NULL)

_MAX_WINDOW = 1000

# The chokepoint anchor. The rule is only attached to the pre-commit stop if it
# is stated after it; stated earlier it is authoring-time advice again, which is
# the instrument that already failed.
_CHOKEPOINT = "git_state.py"

# Files carrying the rule, declared as a literal rather than derived. A derived
# key cannot fail when it stops matching something it never matched — the exact
# way the sibling turn-liveness guard's first revision excluded the skill the
# rule originated in.
_FAMILY = (
    "lite-pr/SKILL.md",
    "spec-to-pr/SKILL.md",
    "spec-to-pr/references/ship.md",
)


def _path(rel: str) -> Path:
    return _SKILLS / Path(rel)


def _occurrences(text: str, needle: str) -> list[int]:
    out: list[int] = []
    i = text.find(needle)
    while i >= 0:
        out.append(i)
        i = text.find(needle, i + 1)
    return out


def _tightest_window(text: str) -> int | None:
    """Smallest span (first marker start to last marker end) over any combination
    of marker occurrences, or None when some marker is absent entirely."""
    occ = [_occurrences(text, m) for m in _MARKERS]
    if not all(occ):
        return None
    return min(
        max(p + len(m) for p, m in zip(combo, _MARKERS)) - min(combo)
        for combo in itertools.product(*occ)
    )


def _why_not(text: str) -> str | None:
    """None when the rule is present, tight, and after the chokepoint. Else why."""
    low = text.lower()
    window = _tightest_window(low)
    if window is None:
        absent = [m for m in _MARKERS if m not in low]
        return f"marker(s) absent from the file entirely: {absent}"
    if window > _MAX_WINDOW:
        return (
            f"the three markers are present but their tightest window is {window} "
            f"chars (> {_MAX_WINDOW}) — they are scattered rather than stated "
            "together as one rule"
        )
    anchor = low.find(_CHOKEPOINT)
    if anchor < 0:
        return (
            f"the file never mentions {_CHOKEPOINT!r}, so the rule is not anchored "
            "to the pre-commit stop"
        )
    # The window's own start, recomputed for the reported combination: any
    # occurrence of the earliest marker that participates in a valid window.
    earliest = min(min(_occurrences(low, m)) for m in _MARKERS)
    if earliest < anchor:
        return (
            "the rule is stated before the pre-commit check, so it reads as "
            "authoring-time advice rather than a step at the chokepoint"
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
    assert _MAX_WINDOW > 0 and _TRAILER and _CHOKEPOINT
    assert _TRAILER != "measured:", (
        "the token must stay hyphenated: bare `Measured:` is already ordinary "
        "narrative prose in the shipped tree, so it collides with both the "
        "tripwire below and `git log --grep`"
    )
    assert _SKILLS.is_dir(), f"{_SKILLS} is not a directory — the guard scans nothing"
    assert len(_FAMILY) >= 3, (
        f"_FAMILY declares {len(_FAMILY)} files; the three Ship-owning call sites "
        "are the floor. Removing one silently shrinks every check below."
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
    assert mentioning <= set(_FAMILY), (
        f"{sorted(mentioning - set(_FAMILY))} state the measurement trailer but "
        "are not in _FAMILY, so nothing checks that their copy kept its "
        "properties"
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
    assert seen == set(_FAMILY) and len(seen) >= 3, (
        f"checked {sorted(seen)}; expected all {len(_FAMILY)} declared files"
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


def test_the_chokepoint_anchor_is_load_bearing():
    """The rule stated BEFORE the pre-commit check is authoring-time advice — the
    instrument that already failed — so it must be rejected even though all three
    markers are present and tight."""
    tight = _FORMAT + " " + _TWO_EXITS + " " + _NO_NULL
    assert _tightest_window(tight) <= _MAX_WINDOW, "fixture must clear the cap"
    assert _why_not(tight + " ... later in the file ... " + _CHOKEPOINT) is not None, (
        "the rule stated ahead of the pre-commit stop was accepted"
    )
    assert _why_not(_CHOKEPOINT + " ... " + tight) is None, (
        "the same rule stated after the stop must be accepted, or the anchor "
        "check rejects everything and proves nothing"
    )


def test_the_format_marker_carries_the_runnability_clause():
    """`Measured-by: the test suite` satisfies a bare-token rule and reproduces
    nothing. The clause is what makes the trailer re-runnable, so it is asserted
    here rather than left to survive as an unexamined substring."""
    assert "runnable as written" in _FORMAT, (
        "the format marker lost its runnability clause — a trailer naming no "
        "real invocation is the failure mode the whole design exists to close"
    )
