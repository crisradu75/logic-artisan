"""An obligation carried between changes has a producer and a consumer, and
nothing else reconciles them.

`multi-pr` records an obligation one change creates for a later one and hands it
to that change through the argument string of its `Skill(cla:spec-to-pr, args=…)`
call. `spec-to-pr` defines the flag, hands the entries to `review-change`'s
checklist, and re-runs the obligation step on a resume the phase probe would
otherwise skip. The checklist owns settling them, the report section and the
verdict effect. No file imports another; the only thing joining the three is that
they spell the same flag and describe the same hand-off. Every way that can drift
is silent:

- the flag is renamed on one side — the chain passes an argument nothing reads;
- the required output field is declared in the orchestrator rather than in the
  file that owns review behaviour — the dispatched-agent path then emits nothing
  and the verdict never moves;
- the verdict carve-out or the omit-empty exemption goes — a report pairs
  `NOT ADDRESSED` with `READY`, or drops the section for having no findings;
- the resume rule goes — a change resumed past Review answers nothing;
- the producer's write step (`4a`) or its read step (step 2) is deleted while the
  other survives. A row written and never read is the exact defect this change
  exists to fix.

Three kinds of check, deliberately:

**The flag parity check is DERIVED, not declared.** It extracts every `--flag`
`multi-pr` actually passes inside a `Skill(cla:spec-to-pr, args="…")` invocation
and requires each to be documented in `spec-to-pr/SKILL.md`. A declared list of
one flag could not fail when a second one drifted; deriving it also puts
`--pr-base` and the three cap flags under the same guard for free.

**The content checks are REGION-SCOPED, not file-wide.** The markers are ordinary
English these files use elsewhere for unrelated reasons, so a file-wide `in` test
would stay green with the guarded block deleted outright. Counted with
`text.lower().count(...)`: `critical` 11x in `spec-to-pr/SKILL.md` (a
74820-character file), `step 2` 6x and `carried obligations` 3x in
`change-loop.md`. Each check therefore slices its file between two anchors and
asserts inside that slice; a deleted anchor fails outright, and `_MAX_REGION`
stops a deleted END anchor from quietly widening a region back out to the rest of
the file.

**One check is an EXCLUSION.** `spec-to-pr/SKILL.md` states that
`review-change/references/checklist.md` is the single source of truth for review
behaviour and that review logic must not be added to the orchestrator. The first
revision of this change violated exactly that, putting the report template and
its position in the orchestrator, where the dispatched-agent path never reads it.
`test_the_report_template_lives_only_where_review_behaviour_does` pins the repair.

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
_CHECKLIST = _SKILLS / "review-change" / "references" / "checklist.md"

# The one flag this change adds. A constant only so the floors below can pin it;
# the parity check derives its flag set from the producer.
_CARRY_FLAG = "--inherits"

# The verdict template. It belongs in the file that owns the report shape and
# nowhere else — see the exclusion test.
_TEMPLATE = "HONOURED | VIOLATED | NOT ADDRESSED"

# A region wider than this means its END anchor was deleted and the slice ran on
# to the rest of the file. Measured over the nine real regions:
#   python -c "import test_chain_obligation_carry as g; \
#              print(sorted(len(g._region(n)) for n in g._REGIONS))"
# -> 367 / 407 / 659 / 1023 / 1353 / 1630 / 2021 / 2790 / 3562
# 5000 clears the widest (the `4a` write step, 3562) with ~1.4x headroom. It is
# well under what a deleted end anchor actually swallows, measured the same way
# (`len(text) - text.find(start)`): the `4a` region would run 13956 characters to
# the end of `change-loop.md`, and the Step 2b region 25945 to the end of
# `checklist.md`. The cap has ~3x of margin against the nearest real failure, so
# it is not a number the prose has to be written around.
_MAX_REGION = 5000

# region name -> (file, start anchor, end anchor, markers that must appear in it)
#
# Anchors are literal text from the files. A deleted anchor is a failure, not a
# skip: the anchor IS part of what is being guarded, since the rule lives in the
# block the anchor opens. Every anchor was confirmed to appear exactly once in
# its file (`text.count(anchor)`).
_REGIONS: dict[str, tuple[Path, str, str, tuple[str, ...]]] = {
    # ---- consumer: spec-to-pr owns the argument and the delivery, not the rules
    "spec-to-pr argument contract": (
        _SPEC_TO_PR,
        "**`<inherits>`**",
        "These rules apply across every phase.",
        (
            _CARRY_FLAG,
            # Derived from the prerequisite's actual state — issue #102.
            "not from the batch as proposed",
            # The token is what a grep matches, not a description of it.
            "literal string",
            # The separator is not legal inside an entry's prose half.
            "may not appear in the failure half",
            # The probe has no review state, so the flag outlives it.
            "not resumable-past",
        ),
    ),
    "spec-to-pr hands the entries to the checklist": (
        _SPEC_TO_PR,
        "**Inherited obligations — hand",
        "For each round:",
        # The destination is spelled out, not merely mentioned: the block's last
        # sentence also says "Step 2b", so a bare `step 2b` marker survived the
        # hand-off itself being rewritten to point nowhere. Measured — that
        # mutant SURVIVED this batch until the marker was tightened.
        (_CARRY_FLAG, "checklist's **step 2b**", "checklist"),
    ),
    "spec-to-pr answers on a resumed run": (
        _SPEC_TO_PR,
        "**A non-empty `<inherits>` survives the probe",
        "- **`--dry-run`:**",
        (
            # The probe genuinely has no review field; that is the whole reason.
            "no `review` field",
            "step 2b",
            # It runs ahead of whatever phase the probe picked. Anchored without
            # the leading "before", which the prose emphasises as `*before*`.
            "the first phase the probe selects",
        ),
    ),
    # ---- consumer: the checklist owns review behaviour
    "checklist settles the obligations": (
        _CHECKLIST,
        "### Step 2b: Inherited obligations",
        "## Step 3: Size gate",
        (
            "grep -rl",
            # Settled before the gate, so the answer cannot depend on the path.
            "both size-gate paths",
            "not addressed",
            # A pasted token is not a discharge.
            "tasks.md` subtask",
            "a missing line is a failed round",
        ),
    ),
    "checklist gives the obligations to the dispatched agents": (
        _CHECKLIST,
        "**Inherited-obligation rows in the context brief.**",
        "### Agent 1:",
        ("inherited obligation", "critical", "pasted into prose"),
    ),
    "checklist wires the verdict": (
        _CHECKLIST,
        "- **READY** — 0 Critical",
        "- **FIX FIRST**",
        ("step 2b", "honoured", "may never pair"),
    ),
    "checklist exempts the field from omit-empty": (
        _CHECKLIST,
        "- Omit any section with zero findings",
        "- Total report should fit",
        ("inherited obligations", "required output field"),
    ),
    # ---- producer: multi-pr writes the rows and reads them back
    "multi-pr reads the rows into the flag": (
        _CHANGE_LOOP,
        "**Inherited-obligation clause.**",
        "**Stacked clause**",
        (
            _CARRY_FLAG,
            "carried obligations",
            # Every dated notes file, not just this run's — the resume defect.
            "multi-pr-run-notes-*.md",
            "read every running-notes file",
        ),
    ),
    "multi-pr writes the rows": (
        _CHANGE_LOOP,
        "4a. **Record the obligations",
        "5-alt.",
        (
            "carried obligations",
            "owed by",
            # The empty carry is recorded as its derivation, not as a word.
            "never the bare word",
            "--name-only",
            # Derived from what the change became, not what it proposed.
            "not from what it proposed",
            # The third source: findings set aside as another change's problem.
            "out of scope for this change",
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

    Raises rather than returning a sentinel: a missing anchor is a real failure,
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
    nothing, so a floor parked in a separate test can be skipped or error out and
    leave the real check silently green.
    """
    for path in (_SPEC_TO_PR, _MULTI_PR, _CHANGE_LOOP, _CHECKLIST):
        assert path.is_file(), f"{path} does not exist — the guard reads nothing"
    assert len(_REGIONS) >= 9, (
        f"_REGIONS declares {len(_REGIONS)} regions; the nine sides of the "
        "hand-off are the floor. Dropping one silently stops checking that side."
    )
    assert all(markers for _, _, _, markers in _REGIONS.values()), (
        "a region with no markers passes vacuously — `all(m in text for m in ())`"
    )
    assert len(_HOISTED_MARKERS) == 3 and all(_HOISTED_MARKERS)
    assert _CARRY_FLAG.startswith("--") and _MAX_REGION > 0 and _TEMPLATE
    # Coverage is asserted per FILE, not per region name, so renaming a key is
    # harmless and DELETING one is not. The consumer side splits across two files
    # and the producer keeps a write step and a read step; losing any of those
    # leaves one end of the hand-off unchecked.
    covered = [path for path, _, _, _ in _REGIONS.values()]
    for path, sides in ((_SPEC_TO_PR, 3), (_CHECKLIST, 4), (_CHANGE_LOOP, 2)):
        assert covered.count(path) >= sides, (
            f"{path.name} is covered by {covered.count(path)} region(s); {sides} "
            "are required. A dropped region stops checking one side of the "
            "hand-off with every remaining assertion green."
        )


def test_every_flag_multi_pr_passes_is_documented_by_spec_to_pr():
    """The parity half. A flag renamed on one side only is otherwise silent: the
    chain passes an argument nothing reads and every suite stays green."""
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
            "its end anchor was probably deleted, so it now covers unrelated "
            f"prose in {path.name} where a marker may live by coincidence"
        )
        absent = [m for m in markers if m not in region]
        assert not absent, (
            f"the {name!r} region in {path.name} no longer states {absent}. "
            "Each marker is a property the hand-off needs; the block can read "
            "plausibly while having lost any one of them."
        )
        seen.add(name)
    assert seen == set(_REGIONS) and len(seen) >= 9, (
        f"checked {sorted(seen)}; expected all {len(_REGIONS)} declared regions"
    )


def test_the_report_template_lives_only_where_review_behaviour_does():
    """`spec-to-pr/SKILL.md` names the checklist as the single source of truth for
    the report shape and forbids adding review logic to the orchestrator. The
    first revision of this change did exactly that, which left the dispatched-
    agent path emitting no obligation lines at all."""
    assert _TEMPLATE in _read(_CHECKLIST), (
        f"{_CHECKLIST.name} no longer carries the {_TEMPLATE!r} template — the "
        "report shape has left the file that owns it"
    )
    assert _TEMPLATE not in _read(_SPEC_TO_PR), (
        f"{_SPEC_TO_PR.name} carries the {_TEMPLATE!r} template. That is review "
        "logic in the orchestrator, which this skill forbids: it prescribes a "
        "position in a template it does not own, and the three dispatched review "
        "agents never read it."
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
# The guard's own non-vacuity.
#
# Two floors here defend against states the tree is not currently in, so a
# mutation over the real files cannot reach them on its own. Rather than leave
# them unexercised, each has a tamper test that puts the tree INTO that state and
# asserts the floor is what fires — which also makes them mutable: relaxing
# either to `>= 0` now kills, and both mutants are in this guard's batch.
#
# An earlier revision claimed these two were "covered structurally" by the
# gutting cases below. They were not: each gutting case trips an earlier
# assertion and never reaches the floor. That claim was reasoned rather than run,
# and a reviewer measured it false — which is why the tamper tests below assert
# the SPECIFIC function raises, instead of counting survivors.
# --------------------------------------------------------------------------- #

_CONTENT_CHECKS = (
    test_the_guarded_files_and_regions_all_resolve,
    test_every_flag_multi_pr_passes_is_documented_by_spec_to_pr,
    test_every_region_carries_its_markers,
    test_the_report_template_lives_only_where_review_behaviour_does,
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
        ("the invocation matcher stops matching", "_INVOCATION", re.compile(r"(?!x)x")),
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


def test_the_parity_floor_is_reachable(monkeypatch):
    """Put the tree in the one state the floor exists for: the extraction still
    finds the carry flag, and everything it finds is documented, but it has
    stopped finding the other four. Only the floor can fail here."""
    monkeypatch.setattr(sys.modules[__name__], "_passed_flags", lambda: {_CARRY_FLAG})
    with pytest.raises(AssertionError, match="floor"):
        test_every_flag_multi_pr_passes_is_documented_by_spec_to_pr()


def test_the_coverage_floor_is_reachable(monkeypatch):
    """Keep all nine regions, all with real anchors and non-empty markers, but
    point every one at the same file. `len(_REGIONS) >= 9` and the marker floor
    both still pass; only the per-file coverage floor can catch it."""
    tampered = {
        name: (_CHANGE_LOOP, start, end, markers)
        for name, (_, start, end, markers) in _REGIONS.items()
    }
    monkeypatch.setattr(sys.modules[__name__], "_REGIONS", tampered)
    with pytest.raises(AssertionError, match="region"):
        test_the_guarded_files_and_regions_all_resolve()


def test_the_region_cap_is_load_bearing(monkeypatch):
    """The cap, exercised the only way it can be.

    Removing the cap AND feeding it a wide region proves nothing — the cap is the
    sole check that would catch it. Keep the real cap and feed it the bad input:
    a region that has run past its deleted end anchor and now contains every
    marker somewhere in a page of unrelated prose.
    """
    module = sys.modules[__name__]
    swallowed = (
        "**inherited obligations "
        + ("filler " * 900)
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
    monkeypatch.setattr(
        sys.modules[__name__],
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
