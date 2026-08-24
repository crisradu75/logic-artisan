"""An obligation carried between changes has a producer and a consumer, and
nothing else reconciles them.

`multi-pr` records an obligation one change creates for a later one and then
hands it to that change through the argument string of its
`Skill(cla:spec-to-pr, args="…")` call. `spec-to-pr` defines the flag and turns
it into a required Review output field. Neither file imports the other; the only
thing joining them is that both spell the same flag and both describe the same
two-step hand-off. Every way that can drift is silent:

- the flag is renamed on one side — the chain then passes an argument nothing
  reads, and every test in the repo stays green;
- the Review required-field block is deleted while the producer keeps building
  the argument — the obligation is delivered and answered by nobody;
- the producer's write step (`4a`) or its read step (step 2) is deleted while the
  other survives — a row written and never read, or a read of rows nobody
  writes. The first is the exact defect this change exists to fix: a carry list
  written and then not fed anywhere is indistinguishable from never having
  written it.

Two kinds of check, deliberately:

**The flag parity check is DERIVED, not declared.** It extracts every `--flag`
token `multi-pr` actually passes inside a `Skill(cla:spec-to-pr, args="…")`
invocation and requires each to be documented in `spec-to-pr/SKILL.md`. A
declared list of one flag could not fail when a second one drifted; deriving it
also puts `--pr-base` and the three cap flags under the same guard for free.

**The content checks are REGION-SCOPED, not file-wide.** The markers are ordinary
English that these files use elsewhere for unrelated reasons, so a file-wide `in`
test would stay green with the guarded block deleted outright. Counted over the
two files (`text.lower().count(...)`): `critical` 11 times in
`spec-to-pr/SKILL.md` — a 74820-character file — `step 2` 6 times and
`carried obligations` 3 times in `change-loop.md`. Each check therefore slices
the file between two anchors and asserts inside that slice; a deleted anchor
fails outright, and `_MAX_REGION` stops a deleted END anchor from quietly
widening a region back out to the rest of the file.

Spec: `openspec/specs/cla-plugin/spec.md`, "Cross-change obligation carry".
Issues: #98, #100, #102.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

_PLUGIN_ROOT = Path(__file__).resolve().parents[3] / ".claude" / "plugins" / "cla"
_SKILLS = _PLUGIN_ROOT / "skills"

_SPEC_TO_PR = _SKILLS / "spec-to-pr" / "SKILL.md"
_MULTI_PR = _SKILLS / "multi-pr" / "SKILL.md"
_CHANGE_LOOP = _SKILLS / "multi-pr" / "references" / "change-loop.md"

# The one flag this change adds. Present as a constant only so the floors below
# can pin it; the parity check itself derives its flag set from the producer.
_CARRY_FLAG = "--inherits"

# A region wider than this means its END anchor was deleted and the slice ran on
# to the rest of the file. Measured over the four real regions:
# 1438 / 1517 / 1065 / 2345 characters.
#   python -c "import test_chain_obligation_carry as g; \
#              print([len(g._region(n)) for n in g._REGIONS])"
# 4000 clears the widest (the `4a` write step) with ~1.7x headroom, and rejects a
# region that has run on into a neighbouring phase — `spec-to-pr/SKILL.md`'s
# Review section alone is 8212 characters:
#   python -c "t=open('.../spec-to-pr/SKILL.md',encoding='utf-8').read(); \
#              print(t.find('### Implement') - t.find('### Review'))"
_MAX_REGION = 4000

# region name -> (file, start anchor, end anchor, markers that must appear in it)
#
# Anchors are literal text from the files. A deleted anchor is a failure, not a
# skip: the anchor IS part of what is being guarded, since the rule lives in the
# block the anchor opens.
_REGIONS: dict[str, tuple[Path, str, str, tuple[str, ...]]] = {
    "spec-to-pr argument contract": (
        _SPEC_TO_PR,
        "**`<inherits>`**",
        "These rules apply across every phase.",
        (
            _CARRY_FLAG,
            # The obligation is derived from the prerequisite's actual state,
            # which is issue #102's whole point.
            "not from the batch as proposed",
            # The token is what Review greps for, not a description of it.
            "literal string",
        ),
    ),
    "spec-to-pr review required field": (
        _SPEC_TO_PR,
        "**Inherited obligations",
        "For each round:",
        (
            _CARRY_FLAG,
            "honoured",
            "violated",
            "not addressed",
            # Settled mechanically, not by judgement.
            "grep -rl",
            # A non-honoured verdict has to bite.
            "critical",
            # And the field is required, so an omitted line is not a pass.
            "a missing line is a failed round",
        ),
    ),
    "multi-pr reads the rows into the flag": (
        _CHANGE_LOOP,
        "**Inherited-obligation clause.**",
        "**Stacked clause.**",
        (
            _CARRY_FLAG,
            "carried obligations",
            # Names the step that writes what it reads.
            "step 4a",
        ),
    ),
    "multi-pr writes the rows": (
        _CHANGE_LOOP,
        "4a. **Record the obligations",
        "5-alt.",
        (
            "carried obligations",
            "owed by",
            # The empty carry is written down, so a resume can tell "nothing was
            # owed" from "nobody looked". Anchored on the RULE, not on the token
            # `none` — that token also appears in the step's done-when line, so a
            # marker of `` `none` `` survives the rule being deleted.
            "zero obligations is a real answer",
            # Derived from what the change became, not what it proposed.
            "not from what it proposed",
            # Names the step that reads what it writes.
            "step 2",
        ),
    ),
}

# The hoisted invariant in multi-pr/SKILL.md is one bullet — a single long line —
# so it is checked at line granularity rather than by region slicing.
_HOISTED_MARKERS = (
    _CARRY_FLAG,
    "carried obligations",
    "indistinguishable from never having written it",
)

_INVOCATION = re.compile(r'Skill\(cla:spec-to-pr,\s*args="([^"]*)"')
_FLAG = re.compile(r"--[a-z][a-z0-9-]*")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _region(name: str) -> str:
    """The slice a region's two anchors bound, lowercased.

    Raises rather than returning a sentinel: a missing anchor is a real failure
    and a caller that forgot to check a sentinel would report a pass.
    """
    path, start, end, _ = _REGIONS[name]
    text = _read(path)
    lo = text.find(start)
    if lo < 0:
        raise AssertionError(
            f"{path.name} no longer contains {start!r}, the anchor opening the "
            f"{name!r} region — the rule it guards has been renamed or deleted"
        )
    hi = text.find(end, lo + len(start))
    if hi < 0:
        raise AssertionError(
            f"{path.name} has no {end!r} after {start!r}, so the {name!r} "
            "region is unbounded"
        )
    return text[lo:hi].lower()


def _passed_flags() -> set[str]:
    """Every `--flag` multi-pr actually passes to spec-to-pr, derived from its
    own invocation strings rather than declared here."""
    flags: set[str] = set()
    for path in (_MULTI_PR, _CHANGE_LOOP):
        for args in _INVOCATION.findall(_read(path)):
            flags.update(_FLAG.findall(args))
    return flags


def test_the_guarded_files_and_regions_all_resolve():
    """Non-vacuity for the constants, before anything relies on them.

    Every looping assertion below carries its own floor too: pytest couples
    nothing, so a floor parked in a separate test can be skipped or error out
    and leave the real check silently green.
    """
    for path in (_SPEC_TO_PR, _MULTI_PR, _CHANGE_LOOP):
        assert path.is_file(), f"{path} does not exist — the guard reads nothing"
    assert len(_REGIONS) >= 4, (
        f"_REGIONS declares {len(_REGIONS)} regions; the two producer steps and "
        "the two consumer blocks are the floor. Dropping one silently stops "
        "checking that side of the hand-off."
    )
    assert all(markers for _, _, _, markers in _REGIONS.values()), (
        "a region with no markers passes vacuously — `all(m in text for m in ())`"
    )
    # Coverage is asserted per FILE-AND-SIDE rather than per region name, so
    # renaming a key is harmless and DELETING one is not. Both producer steps
    # (write, read) and both consumer blocks (contract, required field) must
    # survive; losing either side of a hand-off is how it drifts unnoticed.
    covered = [path for path, _, _, _ in _REGIONS.values()]
    for path, sides in ((_CHANGE_LOOP, 2), (_SPEC_TO_PR, 2)):
        assert covered.count(path) >= sides, (
            f"{path.name} is covered by {covered.count(path)} region(s); {sides} "
            "are required. A dropped region stops checking one side of the "
            "hand-off with every remaining assertion green."
        )
    assert len(_HOISTED_MARKERS) == 3 and all(_HOISTED_MARKERS)
    assert _CARRY_FLAG.startswith("--") and _MAX_REGION > 0


def test_every_flag_multi_pr_passes_is_documented_by_spec_to_pr():
    """The parity half. A flag renamed on one side only is otherwise silent:
    the chain passes an argument nothing reads and every suite stays green."""
    flags = _passed_flags()
    assert _CARRY_FLAG in flags, (
        f"multi-pr no longer passes {_CARRY_FLAG} in any "
        'Skill(cla:spec-to-pr, args="…") invocation — the carry is recorded and '
        "then delivered nowhere, which is the defect this guard exists for"
    )
    assert len(flags) >= 5, (
        f"derived only {sorted(flags)} from multi-pr's invocations; the four "
        "pre-existing flags plus the carry flag are the floor. A shrinking set "
        "means the extraction stopped matching, not that the flags went away."
    )
    consumer = _read(_SPEC_TO_PR)
    undocumented = sorted(f for f in flags if f not in consumer)
    assert not undocumented, (
        f"multi-pr passes {undocumented} to /cla:spec-to-pr, which documents no "
        "such argument. The invocation is the only contract between the two "
        "files; an undocumented flag is read by nothing."
    )


def test_every_region_carries_its_markers():
    seen = set()
    for name, (path, _, _, markers) in _REGIONS.items():
        region = _region(name)
        assert len(region) <= _MAX_REGION, (
            f"the {name!r} region spans {len(region)} chars (> {_MAX_REGION}) — "
            f"its end anchor was probably deleted, so it now covers unrelated "
            f"prose in {path.name} where a marker may live by coincidence"
        )
        absent = [m for m in markers if m not in region]
        assert not absent, (
            f"the {name!r} region in {path.name} no longer states {absent}. "
            "Each marker is a property the hand-off needs; the block can read "
            "plausibly while having lost any one of them."
        )
        seen.add(name)
    assert seen == set(_REGIONS) and len(seen) >= 4, (
        f"checked {sorted(seen)}; expected all {len(_REGIONS)} declared regions"
    )


def test_multi_pr_hoists_the_record_and_carry_invariant():
    """The invariant must survive `SKILL.md` being the only file in front of the
    reader — Phase 3's reference is read on demand, and the seam where an
    obligation is created is reached with it closed."""
    lines = [" ".join(l.split()) for l in _read(_MULTI_PR).lower().splitlines()]
    carrying = [l for l in lines if all(m in l for m in _HOISTED_MARKERS)]
    assert carrying, (
        "no single bullet in multi-pr/SKILL.md states the carry invariant with "
        f"all of {list(_HOISTED_MARKERS)} together. Split across bullets it can "
        "be dismantled one bullet at a time with the words still in the file."
    )


# --------------------------------------------------------------------------- #
# The guard's own non-vacuity, checked structurally rather than by mutation.
#
# The floors below defend against states the tree is not currently in, so a
# mutation over the real files cannot reach them. Measured with a throwaway batch
# through `plugin-tests/mutate.py`: relaxing `len(flags) >= 5` and
# `covered.count(path) >= sides` to `>= 0` gave 2 of 2 SURVIVED. That is the case
# `_shared/references/test-quality.md` calls out, and it prefers this form —
# assert the check can still fire, which keeps holding after a later refactor
# quietly turns it into a no-op.
# --------------------------------------------------------------------------- #

_CONTENT_CHECKS = (
    test_the_guarded_files_and_regions_all_resolve,
    test_every_flag_multi_pr_passes_is_documented_by_spec_to_pr,
    test_every_region_carries_its_markers,
    test_multi_pr_hoists_the_record_and_carry_invariant,
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
        ("the region set is emptied", "_REGIONS", {}),
        ("the hoisted markers are emptied", "_HOISTED_MARKERS", ()),
        # The parity check derives its input; a matcher that stops matching
        # would otherwise leave it asserting over an empty set.
        ("the invocation matcher stops matching", "_INVOCATION", re.compile(r"(?!x)x")),
        # One region deleted rather than all four — the realistic drift, and the
        # case a bare `len(_REGIONS) >= 4` floor would have missed once a fifth
        # region was added.
        (
            "one side of the hand-off drops out",
            "_REGIONS",
            {k: v for k, v in _REGIONS.items() if k != "multi-pr writes the rows"},
        ),
    ],
)
def test_the_guard_notices_when_its_own_state_is_gutted(
    name, attribute, value, monkeypatch
):
    monkeypatch.setattr(sys.modules[__name__], attribute, value)
    assert _surviving(_CONTENT_CHECKS) < len(_CONTENT_CHECKS), (
        f"every check still passed with {name} — the guard is vacuous under "
        "this tampering"
    )


def test_the_region_cap_is_load_bearing(monkeypatch):
    """The cap, exercised the only way it can be.

    Removing the cap AND feeding it a wide region proves nothing — the cap is
    the sole check that would catch it. Keep the real cap and feed it the bad
    input: a region that has run past its deleted end anchor and now contains
    every marker somewhere in a page of unrelated prose.
    """
    module = sys.modules[__name__]
    swallowed = (
        "**inherited obligations "
        + ("filler " * 700)
        + "--inherits honoured violated not addressed grep -rl critical "
        "a missing line is a failed round"
    )
    assert len(swallowed) > _MAX_REGION, "the fixture must exceed the cap"
    monkeypatch.setattr(module, "_region", lambda name: swallowed)
    with pytest.raises(AssertionError, match="end anchor"):
        test_every_region_carries_its_markers()


def test_a_missing_anchor_fails_rather_than_skips(monkeypatch):
    """A region whose START anchor is gone must fail. Returning a sentinel and
    letting the marker loop run over an empty string would report a pass for a
    rule that has been deleted outright."""
    module = sys.modules[__name__]
    monkeypatch.setattr(
        module,
        "_REGIONS",
        {
            "fabricated": (
                _SPEC_TO_PR,
                "a phrase this file does not contain",
                "For each round:",
                ("anything",),
            )
        },
    )
    with pytest.raises(AssertionError, match="anchor"):
        test_every_region_carries_its_markers()
