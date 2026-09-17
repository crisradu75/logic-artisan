"""A guard without a killed mutant is a guard nobody has proven.

The sibling `conformance-checks/tests/test_guards_are_not_vacuous.py` catches one
concrete shape statically — a collection asserted empty that nothing fills. It
cannot catch the other shape this repo has actually shipped: an assertion that is
reachable but checks the wrong thing (greping for a function's name rather than
calling it). Only a mutant catches that, and only if someone writes one.

`mutate.py` is invoked by hand, so "write a mutant" was advice, and advice is
what gets skipped at the end of a long session. This makes the pairing checkable:
every guard test file in a checks scope has a same-named batch under `mutants/`,
and every batch names a target that exists — found by basename, not by assuming
the batch's area also names its guard's immediate parent under `tests/`, which
is false for `mutants/release/` (see `_find_guard_for_batch`).

It deliberately does NOT run the mutants — a mutation run edits real files and
takes minutes, which does not belong in the ordinary gate. It asserts only that
the evidence CAN be produced and points at the command that produces it.
"""

from __future__ import annotations

import ast
import importlib.util
import sys
from pathlib import Path

_DEV_TREE = Path(__file__).resolve().parents[2]


def _guard_areas() -> tuple[str, ...]:
    """Every area that holds GUARDS — i.e. every directory under `tests/` with
    at least one test file, named by its last path segment.

    DERIVED FROM `tests/`, NOT FROM `mutants/`, and that is the whole point of
    this function's latest revision. It was a fixed two-tuple once
    (`("conformance", "consistency")`, the two `*-checks` scopes that predated
    the dev-tree move), which could not see `mutants/release/` arriving. Deriving
    it from `mutants/` fixed that and introduced a subtler version of the same
    defect: a directory with ZERO batches was not an AREA, so its guards were not
    merely unpoliced, they were uncountable — absent from `_EXEMPT`, absent from
    `_PENDING_ADOPTION`, and absent from the ceiling that bounds them.

    Measured before the change: 9 guards across 7 directories — `launcher`,
    `lib`, `skills/_shared`, `skills/codify-retro`, `skills/new-worktree`,
    `skills/spec-to-pr`, `skills/spec-to-pr-retro` — sat outside the pairing
    check entirely. An area list read out of `mutants/` can only ever enumerate
    the areas that already complied, which is a census of the converted.

    `tests/` is the right source because the POPULATION this file polices is
    guards, not batches. `mutants/` is now the other side of the comparison
    rather than the definition of the universe — see `_batch_areas`.

    `rglob`, not `iterdir`: `tests/skills/<name>/` sits one segment deeper, the
    same nesting `_area_test_dir` was fixed to stop assuming.
    """
    tests_root = _DEV_TREE / "tests"
    if not tests_root.is_dir():
        return ()
    # `__pycache__` can hold no `test_*.py`, so the dunder filter the previous
    # revision needed is now implied by the population itself rather than
    # written out — one fewer condition that could be wrong.
    return tuple(
        sorted({p.parent.name for p in tests_root.rglob("test_*.py")})
    )


def _batch_areas() -> tuple[str, ...]:
    """Every subdirectory under `mutants/`, dunder directories excluded.

    What `_guard_areas` used to be. It is still needed, but as the OTHER side of
    a comparison rather than as the definition of an area: a batch directory that
    matches no tests directory is a batch nothing is paired with, which is the
    mirror of the check this file is mainly about.

    The dunder filter stays here because this one really does read raw
    subdirectories, and `__pycache__` appears the moment anything runs.
    """
    mutants_root = _DEV_TREE / "mutants"
    if not mutants_root.is_dir():
        return ()
    return tuple(
        sorted(
            p.name
            for p in mutants_root.iterdir()
            if p.is_dir() and not p.name.startswith("__")
        )
    )

# Guard files exempt from needing a batch, each for a stated reason. Keep this
# list short and justified — it is the pressure valve that could quietly empty
# this test if it grew without argument.
_EXEMPT = {
    # THIS file is the meta-guard; a mutant batch for it would assert that the
    # pairing checker checks pairing, which is circular.
    "tests/consistency/test_guards_have_mutant_batches.py":
        "meta-guard: mutating it only tests itself",

    # `tests/conformance/test_guards_are_not_vacuous.py` USED TO BE EXEMPT HERE,
    # on the reasoning that it "carries seeded-input tests of its own checker
    # instead". That reasoning was wrong on its own terms and it cost something.
    #
    # It was never circular. Its checker — `_feeds`, `_empty_asserted_names` —
    # lives INSIDE the guard file, so a mutant edits the checker and the killing
    # assertion comes from that same file's seeded inputs. That is precisely the
    # shape `mutants/consistency/test_subprocess_encoding.py` already has, and
    # the same argument that took `test_mutate.py` off this list: the observation
    # is external to the thing observed.
    #
    # What the exemption cost: a widening to `_feeds` treated a collection passed
    # to ANY call as "fed", including inside the assertion's own failure message
    # — so `assert not problems, "\n".join(problems)`, the standard guard shape
    # in this repo, could never be reported again. 29 of 68 policed assertions
    # were immunised, and no mutant existed to notice, because the file that
    # polices vacuousness was itself the one thing nothing mutated.
    #
    # It now has a batch. A guard whose subject is "guards that stopped checking"
    # is the last file that should be trusted on its own say-so.

    # GRANDFATHERED: NONE LEFT. All seven guards that predated the convention
    # now ship a batch (issue #176, groups A and B), so the debt this section
    # counted is paid and the bound below is 0. The heading stays, empty, so the
    # next reader sees that "grandfathered" is a closed category rather than an
    # available one — `test_the_grandfather_list_only_shrinks` now reads
    # `<= 0`, which turns the ratchet into "no grandfathered exemption may ever
    # be added again". A new guard needs a batch, not a line here.
}


# Guards in an area whose adoption is UNDERWAY — the area already has at least
# one batch, and these are the guards still waiting for theirs. Keyed by the same
# `tests/<...>/<file>.py` relative path as `_EXEMPT`, one line each, with a
# reason.
#
# The problem this solves. `_guard_areas()` derives areas from the directories
# present under `mutants/`, so creating `mutants/hooks/` for ONE guard made
# `hooks` an area and `test_every_guard_file_has_a_mutant_batch_beside_its_scope`
# demanded a batch for the 12 other guards in `tests/hooks/` at once — none of
# them exemptable, because the grandfather list above only shrinks. The rational
# response was to write no batch, so the check discouraged exactly the behaviour
# it exists to encourage. It already cost one: the batch proving
# `ask-destructive-git`'s `git branch -D` detection was run from outside the repo
# tree and committed nowhere, so it existed nowhere.
#
# `hooks` HAS SINCE BEEN ADOPTED, which is what this mechanism was built for and
# its first actual use (issue #207). Six guards got a batch in that commit; the
# other seven are listed below. The `git branch -D` batch exists again.
#
# The line was drawn on SEVERITY rather than on count. What matters is what gets
# through when a guard is vacuous: a broken block or ask lets a destructive git
# operation, an unsafe recursive delete, a cross-worktree write, or a push to the
# default branch proceed. That covers five of the six — the three blocks,
# `ask_destructive_git`, and `pre_push`.
#
# `log_commit_provenance` is the EXCEPTION and does not fit the scale at all: its
# own docstring says it never blocks, never warns, and prints nothing on the
# happy path. It earned a batch for a different reason — PR #204 added two gates
# to it that were verified by hand and by nothing else.
#
# A broken warn prints nothing, and warn output never reaches a transcript, so a
# warn's batch is the only evidence it fires at all. That is an argument for
# covering the warns eventually, not ahead of the blocks.
#
# Why PER-FILE and not per-area. The first design here was per-area — an area
# mapped to the set of guards adopted so far, and any guard not in that set was
# skipped. Three reviews measured the same hole from three directions, and all of
# them come from the branch being keyed on the area rather than the file:
#
#   * A guard added to a listed area LATER is silently exempt forever. It cannot
#     be in an "adopted" set written before it existed, so it is skipped — an
#     open-ended exemption, which is the opposite of countable debt.
#   * `{"hooks": frozenset()}` — a one-token slip while landing the first batch —
#     unpoliced all 13 guards in the area with every test in this file green.
#   * The decisive one: mutating the skip to `if adopted is not None:`, which
#     turns the mechanism into a blanket area exemption, passed all five tests
#     written for it. A branch no test can distinguish from its own opposite is
#     not a mechanism.
#
# Keyed per file, none of those exist: there is no area-level branch to mutate,
# an unlisted guard is demanded whenever it appears, and the debt is countable
# and bounded by `test_adoption_debt_only_shrinks` the way `_EXEMPT` is. Adopting
# an area is then a list edit measured in lines rather than a demand for a dozen
# mutation batches in one commit — which was the actual cost #138 named.
#
# Three properties are enforced rather than asked for, in
# `test_pending_adoption_entries_are_live`: an entry must name a guard that
# EXISTS, must sit in an area that already has at least one batch (otherwise it
# is an exemption wearing adoption's name), and must NOT already have a batch
# (a stale entry is an exemption that outlived its reason).
_PENDING_ADOPTION: dict[str, str] = {
    # `annotate` was adopted as an area by the change that put the annotations in
    # the page's right-hand margin. That change touched three of the six guards
    # in the area and wrote a batch for each; these are the other three, which it
    # did not touch. Listed rather than exempted, so the debt is countable — and
    # the batch to write first is the store's, since the corpus is the one thing
    # on disk that outlives every page.
    "tests/skills/annotate/test_annotations_store.py":
        "adoption debt: untouched by the margin change; the corpus format is the "
        "highest-value batch still owed here",
    "tests/skills/annotate/test_openspec_change.py":
        "adoption debt: untouched by the margin change; its thresholds are "
        "measured by sweep_changes.py rather than asserted, so a batch has to "
        "mutate the detector rather than a constant",
    "tests/skills/annotate/test_review_findings.py":
        "adoption debt: untouched by the margin change",

    # `hooks`, adopted by issue #207. Six guards got a batch in that commit; these
    # are the seven that did not, each a warn or a dispatch-layer guard rather
    # than one that stops a destructive action. Ordered by what a batch would buy.
    "tests/hooks/test_warn_wholesale_rewrite.py":
        "adoption debt: highest-value of the seven. It is wired DIRECTLY on "
        "PostToolUse rather than through a dispatcher, so nothing else exercises "
        "its wiring, and its output never reaches a transcript — a batch is the "
        "only evidence it fires at all",
    "tests/hooks/test_warn_stray_scratch_artifact.py":
        "adoption debt: warn-severity. Its subject is a filename SHAPE — a "
        "mangled scratchpad path collapsed into one long separator-free name — "
        "so a batch has to mutate the shape predicate, and getting a mutant that "
        "is neither trivially killed nor a false positive on real filenames is "
        "the work here",
    "tests/hooks/test_warn_stacked_pr_merge.py":
        "adoption debt: warn-severity. Guards a merge ordering whose failure "
        "closed a dependent PR once (recorded in the codify-learnings overlay), "
        "so the warn matters even though it blocks nothing",
    "tests/hooks/test_warn_heredoc_escape_mangling.py":
        "adoption debt: warn-severity, and it fired correctly twice during the "
        "session that adopted this area — evidence it works, but not a batch",
    "tests/hooks/test_dispatch.py":
        "adoption debt: the dispatcher, not a guard. A mutant here breaks every "
        "leaf hook at once, so the batch wants designing around what a leaf's own "
        "batch does NOT already cover rather than duplicating it",
    "tests/hooks/test_dispatch_lib.py":
        "adoption debt: shared helpers behind both dispatchers. Same caveat as "
        "test_dispatch.py — a mutant here is caught by whichever leaf batch "
        "happens to exercise the helper, which makes attribution the hard part",
    "tests/hooks/test_hooks_wiring.py":
        "adoption debt: asserts hooks.json matches the leaf hooks and that the "
        "timeout budget fits. Its own docstring records what it does NOT verify "
        "(that a HOOK_WORST_CASE_SECONDS entry matches that hook's real cost), so "
        "a batch should pin the gap rather than imply it is closed",
}

# Re-derive on the commit that adopts an area, then only lower it. This is the
# one bound in the file allowed to move UP, and only there — see
# `test_adoption_debt_only_shrinks` for why that is stated as a number rather
# than trusted to the diff.
# Raised 0 -> 3 in the commit that adopts `annotate` as a mutants area, which is
# the one direction this number is allowed to move and only there. Three of the
# area's six guards got a batch in that commit; these are the other three.
#
# Raised 3 -> 10 in the commit that adopts `hooks` (issue #207): six of its
# thirteen guards got a batch, seven did not.
#
# THE BOUND IS GLOBAL, NOT PER AREA. `_PENDING_ADOPTION` is one flat map and the
# assertion below reads `len()` of the whole thing, so the ceiling is 3 annotate
# + 7 hooks = 10, not 7. The decisions doc behind #207 said 3 -> 7, reasoning as
# though each area carried its own bound; it does not. Recorded because that doc
# is what a later reader reaches for first, and the code is the authority.
#
# Ten is a large standing debt, deliberately. It is bounded and visible, which is
# the whole trade this mechanism makes against the alternative that produced it:
# thirteen batches in one commit, which nobody wrote, so the area had none at all.
#
# IT DID NOT MOVE WHEN AREAS STARTED BEING DERIVED FROM `tests/`, and that is the
# most load-bearing fact about this number. That change made 9 previously
# uncountable guards countable, across 7 directories that held no batch at all.
# Absorbing them into this map would have meant a ceiling of 19 — and a ceiling
# that large stops being a budget and becomes a record of a backlog, which is the
# opposite of what it is for. All 9 got a REAL BATCH in the commit before the
# derivation instead, so the debt this number bounds is unchanged at 10 while the
# policed population went from 45 guards to 54.
#
# The ordering was the point: batches first, derivation second. Landing the
# derivation first would have forced exactly the ceiling raise that the batches
# made unnecessary, and a raised ceiling is far harder to walk back than an
# unraised one — nothing ever fails because a ceiling is too high.
_PENDING_ADOPTION_CEILING = 10


def test_adoption_debt_only_shrinks():
    """The same bounded-debt shape `_EXEMPT` uses, for a different lifetime.

    `_EXEMPT`'s grandfathered entries predate the convention; these are guards in
    an area being taken on right now. Both are debt, and debt that is not counted
    is the pressure valve quietly emptying the check."""
    assert len(_PENDING_ADOPTION) <= _PENDING_ADOPTION_CEILING, (
        f"{len(_PENDING_ADOPTION)} guards pending adoption against a ceiling of "
        f"{_PENDING_ADOPTION_CEILING}. Raising the ceiling is legitimate only in "
        "the commit that adopts a new area, and is a deliberate edit reviewed as "
        "such; every other direction is down."
    )


def _stale_pending_entries(dev_tree: Path, pending: dict[str, str], areas):
    """Pending entries that have stopped being adoption debt, with the reason.

    A pure function over explicit inputs so every branch can be planted. It takes
    `dev_tree`, `pending` AND `areas` as parameters and reads no module global —
    a helper that quietly reads a global instead of its own argument is the exact
    bug this repo's `test-quality.md` names, and an earlier draft of this file
    reintroduced it."""
    problems = []
    for rel, reason in sorted(pending.items()):
        guard = dev_tree / rel
        name = Path(rel).name
        if not guard.is_file():
            problems.append(f"  {rel}: names no guard that exists")
            continue
        if not reason.strip():
            problems.append(f"  {rel}: carries no reason")
        batches = [a for a in areas if (dev_tree / "mutants" / a / name).is_file()]
        if batches:
            problems.append(
                f"  {rel}: already has a batch ({batches[0]}) — delete this entry "
                "and lower the ceiling in the same commit"
            )
        area_dir = dev_tree / "mutants" / _pending_area_of(dev_tree, rel)
        if not any(area_dir.glob("test_*.py")):
            problems.append(
                f"  {rel}: its area holds no batch at all, so nothing is being "
                "adopted — this is an exemption, and belongs in _EXEMPT with an "
                "argument for it"
            )
    return problems


def _pending_area_of(dev_tree: Path, rel: str) -> str:
    """The mutants-area a pending guard belongs to, by matching `_area_test_dir`
    in reverse: the last path segment of its directory."""
    return Path(rel).parent.name


def test_the_policed_population_has_its_own_floor():
    """`test_the_scan_is_not_vacuous` floors guards DISCOVERED. Nothing floored
    guards actually POLICED, and the two now diverge.

    Adopting an area moves them in opposite directions: bringing `mutants/hooks/`
    in adds 13 files to discovery while adding one guard to policing, so the
    discovery floor gains 13 files of slack for one guard's worth of coverage.
    That is the decorative-floor defect the comment in `test_the_scan_is_not_
    vacuous` describes, reached through a new door — so the population that
    matters gets a floor of its own."""
    policed = [
        p
        for p in _guard_files()
        if _rel(p) not in _EXEMPT and _rel(p) not in _PENDING_ADOPTION
    ]
    # PER-AREA again, and for the same reason as its sibling above: this was
    # `>= 10`, then `>= 13`, and each move was a hand re-derivation asserted as
    # a fact. The property it protects is that exemptions and pending entries
    # have not eaten the check — and the shape that failure actually takes is an
    # area every one of whose guards is excused, which reads as fully policed
    # while policing nothing. A global count cannot see that: an area going
    # wholly unpoliced is invisible as long as the other areas are large enough
    # to hold the total up. `_PENDING_ADOPTION`'s own docstring records this
    # exact hole being found three times from three directions.
    unpoliced = _areas_policing_nothing(_guard_areas(), _EXEMPT, _PENDING_ADOPTION)
    assert unpoliced == [], (
        f"every guard in these areas is exempt or pending: {unpoliced}. The area "
        "has batches, so it reads as adopted, and not one of its guards is "
        "actually policed for one."
    )
    assert policed, "no guard anywhere is policed for a batch"


def test_pending_adoption_entries_are_live():
    """A pending entry is a promise with a deadline. Left after its batch lands,
    or written for an area nobody is actually adopting, it is an uncounted
    exemption — and this file exists because uncounted exemptions are invisible."""
    problems = _stale_pending_entries(_DEV_TREE, _PENDING_ADOPTION, _guard_areas())
    assert not problems, "pending-adoption entries that are no longer live:\n" + (
        "\n".join(problems)
    )


def test_the_grandfather_list_only_shrinks():
    """The pressure valve, bounded. A grandfathered guard is unproven debt; the
    list may lose entries but must never gain one, or the convention becomes
    opt-in and the whole check evaporates."""
    grandfathered = sum(1 for v in _EXEMPT.values() if v == "grandfathered")
    # RATCHET this down to the new real count whenever an entry is deleted. Left
    # at its original 12 while the real count fell to 8, it silently permitted
    # four new exemptions — a bound far above its population is the same
    # decorative-floor defect `test-quality.md` describes, applied to a ceiling.
    #
    # 7 -> 4 with the batches for `test_subprocess_encoding.py`,
    # `test_token_list_is_curated_here.py` and `test_mutate.py` (issue #176).
    # `test_mutate.py` came off the list rather than being reclassified as a
    # meta-guard: its batch mutates `mutate.py` and observes the result through
    # a subprocess run against a sandbox scope, so the observation is external
    # and the pairing is not circular. Its batch header records the probe.
    #
    # 4 -> 0 with the batches for `test_no_hardcoded_plugin_paths.py`,
    # `test_ledger_names_agree.py`, `test_marketplace_manifest.py` and
    # `test_pre_push_is_installed.py` (issue #176, group A). The debt is paid.
    #
    # ZERO IS A MEANINGFUL BOUND, NOT A DEGENERATE ONE. `0 <= 0` passes; a
    # single new entry makes it `1 <= 0` and fails. So the ratchet's meaning
    # changes at this point from "the list only shrinks" to "no grandfathered
    # exemption may ever be added again", which is the end state this mechanism
    # was aiming at rather than an accident of arithmetic.
    assert grandfathered <= 0, (
        f"{grandfathered} grandfathered guards; the bound is the real count at "
        "the last deletion and is only allowed to shrink. A NEW guard needs a "
        "mutant batch, not an exemption — and deleting an entry means lowering "
        "this number in the same commit."
    )


def _area_test_dir(area: str) -> Path | None:
    """The `tests/` directory belonging to `area`, wherever it sits.

    NOT `tests/<area>` — that is the same two-segment assumption
    `_find_guard_for_batch` was fixed to abandon, and it is false for exactly
    the area this change adds: `mutants/release/`'s guards live at
    `tests/skills/release/`, one segment deeper. Left as `tests/<area>`, the
    derived `release` area contributed ZERO files and `Path.glob` on a missing
    directory returns empty SILENTLY — so the area looked policed, the file
    count was byte-identical to the old hardcoded pair, and nothing said so.
    Generalising only the batch->guard direction fixed the half that does not
    catch a guard shipped without a batch."""
    root = _DEV_TREE / "tests"
    direct = root / area
    if direct.is_dir():
        return direct
    nested = sorted(p for p in root.rglob(area) if p.is_dir())
    if len(nested) == 1:
        return nested[0]
    return None


def test_every_derived_area_resolves_to_a_tests_directory():
    """An area whose tests directory cannot be located contributes nothing, and
    contributing nothing is indistinguishable from being clean. Fail loudly
    instead — including on an ambiguous match, which would otherwise pick one
    arbitrarily.

    NOW MOSTLY A TAUTOLOGY, AND KEPT ANYWAY FOR THE HALF THAT IS NOT. Areas are
    derived from `tests/`, so every area has a tests directory by construction —
    that half can no longer fail. What CAN still fail is `_area_test_dir`'s
    AMBIGUITY arm: it returns None when `rglob` matches the area name in more
    than one place, which happens the moment two skills' test directories share a
    leaf name. That is a real and silent collapse — the area resolves to nothing
    and reads as clean — and it is not covered anywhere else, so the assertion
    stays. Its message is corrected: these areas hold GUARDS, which is what they
    are derived from now."""
    unresolved = [a for a in _guard_areas() if _area_test_dir(a) is None]
    assert not unresolved, (
        f"area(s) {unresolved} name more than one directory under tests/, so "
        f"`_area_test_dir` refuses to pick — their guards are policed by nothing. "
        f"Two test directories sharing a leaf name is the usual cause."
    )


def test_every_batch_area_is_a_guard_area():
    """The mirror, and the direction that became possible only by deriving areas
    from `tests/`.

    A directory under `mutants/` that matches no area holds batches paired with
    nothing. Under the old derivation this could not be expressed at all: the
    batch directory WAS the area, so the question answered itself. Now the two
    sides are independent and the comparison means something.

    It is the same shape as the guard-without-a-batch check one level up, and it
    catches the case that one cannot: a batch whose guard was deleted or moved to
    a differently-named directory, which otherwise sits there being counted as
    coverage of nothing."""
    orphans = sorted(set(_batch_areas()) - set(_guard_areas()))
    assert not orphans, (
        f"mutants area(s) {orphans} match no directory under tests/ — their "
        "batches are paired with nothing. Either the guards moved and the batch "
        "directory should move with them, or the guards were deleted and so "
        "should the batches."
    )


def _areas_discovering_nothing(areas) -> list[str]:
    """Areas that contribute no guard files at all.

    The collapse a global `len(files) >= N` floor was standing in for, asserted
    where it actually happens. `_area_test_dir` returning None and `Path.glob`
    over a missing directory both yield empty rather than raising, so an area can
    stop contributing in total silence.

    `areas` is a parameter rather than a read of `_guard_areas()` so a planted
    list can redden this — the same rule `_stale_pending_entries` follows, and
    for the reason stated there."""
    out = []
    for area in areas:
        d = _area_test_dir(area)
        if d is None or not list(d.glob("test_*.py")):
            out.append(area)
    return sorted(out)


def _areas_policing_nothing(areas, exempt, pending) -> list[str]:
    """Areas in which every discovered guard is exempt or pending.

    Such an area holds batches, so it reads as adopted, while not one of its
    guards is actually demanded to have one. A global count of policed files
    cannot see it: the other areas hold the total up.

    All three inputs are parameters, so each branch can be planted."""
    by_area: dict[str, list[str]] = {}
    for area in areas:
        d = _area_test_dir(area)
        if d is None:
            continue
        by_area[area] = [_rel(p) for p in sorted(d.glob("test_*.py"))]
    return sorted(
        area
        for area, rels in by_area.items()
        if rels and not [r for r in rels if r not in exempt and r not in pending]
    )


def _guard_files():
    out = []
    for area in _guard_areas():
        d = _area_test_dir(area)
        if d is not None:
            out.extend(sorted(d.glob("test_*.py")))
    return out


def _rel(p: Path) -> str:
    return p.relative_to(_DEV_TREE).as_posix()


def _find_guard_for_batch(batch: Path) -> list[Path]:
    """Every file under `tests/` sharing the batch's basename.

    NOT `tests/<area>/<name>` — that two-segment substitution assumes a batch's
    area name is also its guard's immediate parent directory under `tests/`,
    which `mutants/release/test_check_shipped_tree.py` breaks: its guard lives
    at `tests/skills/release/test_check_shipped_tree.py`, two segments deeper.
    A basename search finds it regardless of nesting. `conftest.py` is the only
    basename this repo's own tests tree duplicates (measured in
    `plugin-tests/pyproject.toml`'s own comment), and no batch is ever named
    `conftest.py`, so a search here stays unambiguous in practice."""
    return sorted(p for p in (_DEV_TREE / "tests").rglob(batch.name) if p.is_file())


def _guards_missing_a_batch(exempt=None, pending=None):
    """Guards that owe a batch and do not have one, as report lines.

    `exempt`/`pending` are parameters rather than reads of the module globals so
    a planted tree can exercise both skips. They default to the real maps, which
    is what the test over the real tree wants."""
    exempt = _EXEMPT if exempt is None else exempt
    pending = _PENDING_ADOPTION if pending is None else pending
    missing = []
    for path in _guard_files():
        rel = _rel(path)
        if rel in exempt:
            continue
        if rel in pending:
            # This guard's area is being adopted and its batch has not landed
            # yet. Same per-file shape as `_EXEMPT` directly above, deliberately:
            # a guard NOT named here is demanded the moment it appears, so the
            # list cannot absorb a file written after it.
            continue
        # Search every area rather than assuming the guard's immediate parent
        # directory names its batch's area — false for `tests/skills/release/`,
        # whose batches live under `mutants/release/`. This is the mirror of
        # `_find_guard_for_batch`; fixing only that direction left the one that
        # actually catches a guard shipped without a batch still broken.
        found = [
            b
            for area in _guard_areas()
            for b in [_DEV_TREE / "mutants" / area / path.name]
            if b.is_file()
        ]
        if not found:
            missing.append(f"  {rel} -> no batch named {path.name} under mutants/")
    return missing


def test_every_guard_file_has_a_mutant_batch_beside_its_scope():
    missing = _guards_missing_a_batch()
    assert not missing, (
        "guard(s) with no mutant batch — nobody has shown these can fail:\n"
        + "\n".join(missing)
        + "\n\nWrite one, then prove it:"
        "\n  python3 plugin-tests/mutate.py plugin-tests/mutants/<area>/<name>.py"
        "\n\nADOPTING A NEW AREA? Creating mutants/<area>/ makes <area> an area, "
        "which demands a batch for every guard in it at once — and the rational "
        "answer to that is to write no batch, which is the opposite of what this "
        "check wants. It already cost one batch that now exists nowhere. So the "
        "first batch is all you owe: add the area's OTHER guards to "
        "_PENDING_ADOPTION with a one-line reason each, and raise "
        "_PENDING_ADOPTION_CEILING to match in the same commit. Both lists only "
        "shrink after that. No other number in this file needs re-deriving."
    )


def test_every_batch_is_loadable_and_declares_real_targets():
    """A batch that cannot load, or that points at a file that no longer exists,
    reports every mutant as an anchor error — which reads like a tooling problem
    and gets ignored, so the guard it covers quietly stops being proven."""
    problems = []
    for area in _guard_areas():
        for batch in sorted((_DEV_TREE / "mutants" / area).glob("test_*.py")):
            rel = _rel(batch)
            try:
                tree = ast.parse(batch.read_text(encoding="utf-8"), filename=str(batch))
            except (OSError, SyntaxError) as exc:
                problems.append(f"  {rel}: does not parse ({exc.__class__.__name__})")
                continue
            names = {
                t.id
                for node in ast.walk(tree)
                if isinstance(node, ast.Assign)
                for t in node.targets
                if isinstance(t, ast.Name)
            }
            if "MUTANTS" not in names:
                problems.append(f"  {rel}: defines no MUTANTS list")
            guarded = _find_guard_for_batch(batch)
            if not guarded:
                problems.append(
                    f"  {rel}: guards no file named {batch.name} anywhere under "
                    "tests/"
                )
            problems.extend(f"  {rel}: {p}" for p in _unresolvable_anchors(batch))
    assert not problems, "mutant batch problems:\n" + "\n".join(problems)


def _unresolvable_anchors(batch):
    """Every mutant's `old` string must appear EXACTLY ONCE in its target file.

    This is the condition `mutate.py` refuses on, and refusing is a preflight
    abort: it reports "anchor not found" and runs NO mutant in the batch, so a
    batch of twenty checks reports nothing rather than failing. Nothing in the
    suite went red for it, because a batch is not a test.

    Measured twice on one branch. An edit to `checklist.md` killed
    `test_chain_obligation_carry`'s anchor and its 21 mutants stopped running for
    three review rounds; separately, renumbering a check from `0k` to `0l` killed
    two anchors in `test_check_labels_agree` and took its 5 down. Both times the
    full suite was green. The guard above already says a batch that "reports every
    mutant as an anchor error ... quietly stops being proven" — it just never
    opened the target to check.

    Anchors are prose fragments in markdown by design, so they WILL be broken by
    ordinary edits. The point is not to prevent that; it is to make it loud.
    """
    problems = []
    try:
        tree = ast.parse(batch.read_text(encoding="utf-8"), filename=str(batch))
    except (OSError, SyntaxError):
        return problems  # already reported by the caller

    # Every batch resolves its target paths from `__file__`, so the namespace has
    # to carry it — without it each batch dies on a NameError and this guard
    # reports a tooling problem instead of the anchors it exists to check.
    namespace = {"__file__": str(batch), "__name__": batch.stem}
    try:
        exec(compile(tree, str(batch), "exec"), namespace)  # noqa: S102 - our own file
    except Exception as exc:  # a batch that cannot evaluate is reported, not skipped
        return [f"could not evaluate to read its anchors ({exc.__class__.__name__}: {exc})"]

    for mutant in namespace.get("MUTANTS", []):
        try:
            name, target, old, _new, _targets = mutant
        except (TypeError, ValueError):
            problems.append("has a MUTANTS entry that is not a 5-tuple")
            continue
        try:
            # `read_bytes().decode()`, not `read_text()`, because that is exactly
            # what mutate.py does and the difference is not cosmetic: `read_text`
            # translates line endings, so an anchor built with a literal `\r\n`
            # on a CRLF checkout — which several batches do deliberately — reads
            # as absent and this guard reports a healthy batch as broken. Caught
            # by running the two batches it accused; both ran fine.
            text = Path(target).read_bytes().decode("utf-8")
        except OSError:
            problems.append(f"mutant {name!r} targets a missing file: {target}")
            continue
        found = text.count(old)
        if found != 1:
            problems.append(
                f"mutant {name!r} anchors on a string appearing {found} times in "
                f"{Path(target).name} (needs exactly 1) — mutate.py aborts the WHOLE "
                "batch in preflight, so none of its mutants run"
            )
    return problems


# The absolute-path detector is BORROWED, not written here.
#
# `skills/_shared/scripts/check_no_project_tokens.py` already ships
# `WIN_ABS_PATH`, `HOME_ABS_PATH` and `MANGLED_WIN_PATH`, whose own comments
# record that they were "tuned against the real tree rather than synthetic cases
# only". It does not reach `plugin-tests/mutants/` — its `SCANNED_ROOTS` are the
# five shipped directories — which is why this guard exists at all; but the
# PREDICATE is the same question, and this file has no business answering it
# differently.
#
# The first fix for #139 did write a fourth predicate here, and review measured
# it strictly worse than the shipped three in BOTH directions:
#
#   caught by shipped, missed by mine:  BASE = "/home/alice/code"
#                                       BASE = "/Users/alice/code"
#                                       P = "C:UsersaliceAppData"   (mangled)
#   ignored by shipped, flagged by mine: ("with open(p) as f:\n", "x")
#                                        ("except OSError as e:\n", "raise")
#                                        print("a:\tb")
#                                        re.compile(r"(?i:\s+)")
#
# That false-positive column is the point. `MUTANTS` entries are pairs of Python
# source fragments, so a single-letter name before a colon at the end of a quoted
# `\n`-terminated line is the most common shape in a batch, and `f:\` reads as
# drive `F:` to any rule that keys on one character. `WIN_ABS_PATH` kills the
# whole class by requiring TWO separators — a path SHAPE — instead of guessing
# from the character before the colon. Its comment names `except OSError as e:\n`
# verbatim as the reason.
#
# Known gap, shared with the shipped detector and stated rather than hidden: an
# escape immediately before the drive letter (`X = "\tC:\\Users\\alice"`) is
# missed by all three patterns, and the old `":\\" in line` test did catch it.
# Measured — both the old predicate and the shipped set were run against it. It
# needs an escape abutting a drive letter inside a quoted string, which no batch
# in the corpus does; fixing it belongs in the shipped detector, where every
# caller gets it, not in a local divergence that reintroduces the fourth scanner.
_CHECKER = (
    Path(__file__).resolve().parents[3]
    / ".claude/plugins/cla/skills/_shared/scripts/check_no_project_tokens.py"
)
_spec = importlib.util.spec_from_file_location("_cla_token_checker", _CHECKER)
_token_checker = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_token_checker)

_ABS_PATH_PATTERNS = (
    _token_checker.WIN_ABS_PATH,
    _token_checker.HOME_ABS_PATH,
    _token_checker.MANGLED_WIN_PATH,
)


def _looks_like_absolute_path(line: str) -> bool:
    """Whether `line` carries an absolute developer path.

    A predicate rather than an inline condition so both directions can be pinned
    by fixtures: the real corpus holds zero drive paths, so the catching half has
    no live witness and would otherwise be asserted by nothing."""
    if _token_checker.ABS_PATH_EXEMPT_MARKER in line:
        return False
    return any(p.search(line) for p in _ABS_PATH_PATTERNS)


def test_no_batch_hardcodes_an_absolute_path():
    """A batch resolving from an absolute developer path works on one machine and
    leaks a repo name into a directory the marketplace ships."""
    offenders = []
    for area in _guard_areas():
        for batch in sorted((_DEV_TREE / "mutants" / area).glob("*.py")):
            for lineno, line in enumerate(
                batch.read_text(encoding="utf-8").splitlines(), 1
            ):
                if _looks_like_absolute_path(line):
                    offenders.append(f"  {_rel(batch)}:{lineno}  {line.strip()[:80]}")
    assert not offenders, (
        "mutant batch(es) with an absolute path — resolve from `Path(__file__)` "
        "instead:\n" + "\n".join(offenders)
    )


def test_a_directory_with_no_batches_is_still_an_area(tmp_path, monkeypatch):
    """THE PROPERTY THE `tests/`-DERIVED LIST EXISTS FOR, planted.

    Deriving areas from `mutants/` meant a directory with zero batches was not an
    area at all, so its guards were not merely unpoliced — they were UNCOUNTABLE.
    Not in `_EXEMPT`, not in `_PENDING_ADOPTION`, and so not charged against
    `_PENDING_ADOPTION_CEILING` either. An area list read out of `mutants/` can
    only ever enumerate the areas that already complied.

    Measured before the change: 9 guards across 7 directories sat outside the
    pairing check entirely. This is the direction that could not be tested at
    all under the old derivation, because the thing to observe did not exist as
    an area to observe it on.

    Planted on a fake tree rather than asserted against the real one, which is
    clean by construction now that those 7 directories all carry batches."""
    guards = tmp_path / "tests" / "lonely"
    guards.mkdir(parents=True)
    (guards / "test_unpoliced.py").write_text("def test_a(): pass\n", encoding="utf-8")
    # A nested area too — `tests/skills/<name>/` is one segment deeper, and an
    # `iterdir` here would silently miss every skill area.
    nested = tmp_path / "tests" / "skills" / "deep"
    nested.mkdir(parents=True)
    (nested / "test_nested.py").write_text("def test_b(): pass\n", encoding="utf-8")
    # `mutants/` holds nothing at all, which under the old derivation meant
    # "there are no areas" and therefore "nothing is unpoliced".
    (tmp_path / "mutants").mkdir()

    monkeypatch.setattr(sys.modules[__name__], "_DEV_TREE", tmp_path)
    assert _guard_areas() == ("deep", "lonely"), (
        "a directory holding guards is an area whether or not anything has "
        "written it a batch — that is the whole change"
    )
    assert _batch_areas() == (), "the planted mutants/ tree is empty"
    # And the consequence: the guard is DEMANDED rather than invisible.
    missing = _guards_missing_a_batch(exempt={}, pending={})
    assert sorted(m.split(" ->")[0].strip() for m in missing) == [
        "tests/lonely/test_unpoliced.py",
        "tests/skills/deep/test_nested.py",
    ], missing


def test_the_batch_area_filter_still_rejects_the_dunder_shape(tmp_path, monkeypatch):
    """The half of the old area filter that survives, now on `_batch_areas`.

    Its only witness in the real tree is `mutants/__pycache__`, which is
    GITIGNORED — a runtime artifact, not a fixture. On a fresh clone, before
    anything has run, it does not exist, so the comparison it feeds is trivially
    equal whether the filter is there or not. Planted here for that reason, which
    is the rule this repo's own `test-quality.md` states: prove a guard by
    planting what it must catch.

    An `empty_area` is planted alongside and MUST survive into the list. A batch
    directory holding no batches is a directory nothing is paired with, and
    filtering it out here would hide it from
    `test_every_batch_area_is_a_guard_area` exactly the way the old
    `any(glob(...))` condition hid an emptied area."""
    (tmp_path / "mutants" / "__pycache__").mkdir(parents=True)
    (tmp_path / "mutants" / "__pycache__" / "test_stale.py").write_text("x", encoding="utf-8")
    (tmp_path / "mutants" / "empty_area").mkdir()
    (tmp_path / "mutants" / "empty_area" / "notes.md").write_text("x", encoding="utf-8")
    (tmp_path / "mutants" / "real_area").mkdir()
    (tmp_path / "mutants" / "real_area" / "test_thing.py").write_text("x", encoding="utf-8")

    monkeypatch.setattr(sys.modules[__name__], "_DEV_TREE", tmp_path)
    areas = _batch_areas()

    assert "__pycache__" not in areas, (
        "a dunder directory is a runtime artifact, not an area — even when it "
        "holds a `test_*.py`, which a cached batch does"
    )
    assert areas == ("empty_area", "real_area"), (
        "a batch directory that lost its batches must stay visible; filtering it "
        "out is how an unpaired batch directory becomes invisible"
    )


def _plant_adopting_area(tmp_path):
    """An area mid-adoption: two guards, one batch.

    `test_covered` has a batch; `test_uncovered` does not and is the one a
    pending entry may excuse. Both tests below run against this same tree and
    differ only in the `pending` map, so the map is the only variable."""
    (tmp_path / "mutants" / "partial").mkdir(parents=True)
    (tmp_path / "mutants" / "partial" / "test_covered.py").write_text(
        "MUTANTS = []\n", encoding="utf-8"
    )
    guards = tmp_path / "tests" / "partial"
    guards.mkdir(parents=True)
    (guards / "test_covered.py").write_text("def test_a(): pass\n", encoding="utf-8")
    (guards / "test_uncovered.py").write_text("def test_b(): pass\n", encoding="utf-8")
    (guards / "test_later.py").write_text("def test_c(): pass\n", encoding="utf-8")


def test_a_pending_entry_excuses_exactly_one_guard(tmp_path, monkeypatch):
    """The defect #138 names: the FIRST batch in a new area demanded a batch for
    every other guard in it at once — 12 of them, measured, none exemptable — so
    the affordable move was to write no batch at all.

    The assertion is a POSITIVE value, not `== []`. `test_later.py` is planted
    precisely so this test cannot pass by relaxing everything: an entry excuses
    the one file it names and nothing else. An earlier per-area design failed
    here — mutating the skip to ignore the guard's own name passed every test
    written for it, because they only ever asserted emptiness."""
    _plant_adopting_area(tmp_path)
    monkeypatch.setattr(sys.modules[__name__], "_DEV_TREE", tmp_path)

    missing = _guards_missing_a_batch(
        exempt={}, pending={"tests/partial/test_uncovered.py": "hooks adoption"}
    )
    assert missing == [
        "  tests/partial/test_later.py -> no batch named test_later.py under mutants/"
    ], f"a pending entry must excuse its own file and no other; got {missing}"


def test_a_guard_added_after_the_entry_is_still_demanded(tmp_path, monkeypatch):
    """The hole that killed the per-area design, kept as a standing test.

    Keyed by area, an "adopted names" set could not contain a guard written after
    it, so every future guard in that area was silently exempt forever. Keyed per
    file there is nothing to absorb it: `test_later.py` appears in the report
    whether or not its neighbours are pending."""
    _plant_adopting_area(tmp_path)
    monkeypatch.setattr(sys.modules[__name__], "_DEV_TREE", tmp_path)

    pending = {
        "tests/partial/test_uncovered.py": "hooks adoption",
        # Both of the area's other guards excused; the newcomer must not be.
        "tests/partial/test_covered.py": "hooks adoption",
    }
    missing = _guards_missing_a_batch(exempt={}, pending=pending)
    assert any("test_later.py" in m for m in missing), (
        "a guard that appears after the pending list was written must still be "
        f"demanded — that is the whole reason this is keyed per file; got {missing}"
    )


def test_a_stale_or_bogus_pending_entry_is_caught(tmp_path):
    """A pending entry is a promise with a deadline. Each branch is planted; the
    helper takes every input as a parameter, so none of this reads a global."""
    _plant_adopting_area(tmp_path)
    areas = ("partial",)

    live = {"tests/partial/test_uncovered.py": "hooks adoption"}
    assert _stale_pending_entries(tmp_path, live, areas) == [], (
        "a live entry — real guard, area being adopted, batch not yet written — "
        "must not be reported"
    )

    stale = {"tests/partial/test_covered.py": "hooks adoption"}
    assert any("already has a batch" in p
               for p in _stale_pending_entries(tmp_path, stale, areas)), (
        "an entry whose batch has landed is an exemption that outlived its reason"
    )

    ghost = {"tests/partial/test_absent.py": "hooks adoption"}
    assert any("names no guard that exists" in p
               for p in _stale_pending_entries(tmp_path, ghost, areas)), (
        "an entry naming no real guard is dead config that reads as coverage"
    )

    unreasoned = {"tests/partial/test_uncovered.py": "   "}
    assert any("carries no reason" in p
               for p in _stale_pending_entries(tmp_path, unreasoned, areas)), (
        "debt without a stated reason is what the grandfather list refuses too"
    )

    # An area with NO batch at all is not being adopted; excusing a guard there
    # is a plain exemption, and belongs in `_EXEMPT` where it is counted.
    for b in (tmp_path / "mutants" / "partial").glob("*.py"):
        b.unlink()
    assert any("its area holds no batch at all" in p
               for p in _stale_pending_entries(tmp_path, live, areas)), (
        "adoption requires an area that is actually being adopted"
    )


def test_the_absolute_path_check_pins_both_directions():
    """The real corpus holds ZERO drive paths, so neither direction of this
    predicate has a live witness and both are asserted here instead.

    Both corpora were widened after review measured the first pair as fitted to
    the implementation: the sole `caught` fixture was the one shape the old
    `/home/` arm could match (a bare line, which is a SyntaxError as Python and
    cannot occur in a batch), and the `ignored` list held only the three `(?:`
    anchors observed in #139 while the far more common `f:\\n` shape was flagged."""
    caught = [
        r'BASE = "C:\Users\alice\code"',  # path-fixture-ok
        r"root = 'd:/work/example-repo/x'",  # path-fixture-ok
        'BASE = "/home/alice/code/thing"',  # path-fixture-ok
        'BASE = "/Users/alice/code/thing"',  # path-fixture-ok
        'P = "C:UsersaliceAppDataLocalTemp"',  # path-fixture-ok
        "    /home/alice/src/thing.py",  # path-fixture-ok
    ]
    ignored = [
        # The three measured in #139 — regex anchors, not paths.
        r'_CLUSTER = re.compile(r"(?:^|\s)-[A-Za-z]*D[A-Za-z]*(?:\s|$)")',
        r'PAT = r"(?:\S+)"',
        r'PAT = r"(?:\d+)"',
        # Scoped inline-flag groups: the flag letter IS a drive letter to any
        # rule keying on one character. This repo already writes `(?i:` in two
        # hooks, including the one whose batch motivated #138.
        r'PAT = re.compile(r"(?i:\s+)")',
        r'PAT = re.compile(r"(?m:/x)")',
        # The highest-frequency shape in a mutant batch: `MUTANTS` entries are
        # pairs of `\n`-terminated Python source fragments, and a single-letter
        # name before a colon at the end of one reads as a drive.
        r'MUTANTS = [("    with open(p) as f:\n", "    pass")]',
        r'("    except OSError as e:\n", "    raise")',
        r'print("a:\tb")',
        # A URL and a file URI, which a drive-letter rule without a shape
        # requirement also swallows.
        "    # see https://github.com/example/repo",
        '    URI = "file:///tmp/x"',
    ]
    # Both directions are collected and asserted ONCE, rather than as two loops
    # that each raise. Written as a caught-loop followed by an ignored-loop, the
    # first failure short-circuits the second — and reverting to the old
    # `":\\" in line` test made exactly that happen: the run failed on a
    # forward-slash drive path the old check never caught, never reaching the
    # regex-anchor lines that are the defect (#139) being fixed. A plant that
    # fails for the wrong reason reads as proof and is not.
    failures = [f"should be caught, was not: {ln!r}" for ln in caught
                if not _looks_like_absolute_path(ln)]
    failures += [f"should be ignored, was flagged: {ln!r}" for ln in ignored
                 if _looks_like_absolute_path(ln)]
    assert not failures, "\n".join(failures)


def test_the_scan_is_not_vacuous():
    files = _guard_files()
    # PER-AREA, not a global count. This was `len(files) >= N` for four
    # successive values of N — 6, 15, 18, 24 — and the history of that line is
    # the argument against it: it was decorative at 6 (a 65% collapse passed),
    # its comment said 17 while the assertion said 15 and the truth was 20, and
    # every area added since has forced a hand re-derivation that is itself a
    # measurement nobody re-runs.
    #
    # What the number was ever guarding is COLLAPSE — discovery quietly finding
    # less than it used to. An area contributing zero files is what that looks
    # like, and it is exactly what `_area_test_dir` returning None produces,
    # silently, because `Path.glob` on a missing directory is empty rather than
    # an error. Asserting it per area catches the same failure, catches it in the
    # area where it happened, and needs no maintenance when an area is added.
    empty = _areas_discovering_nothing(_guard_areas())
    assert empty == [], (
        f"these mutants areas contribute no guard files at all: {empty}. An area "
        "that discovers nothing is indistinguishable from an area that is clean."
    )
    assert files, "guard discovery found no files in any area"
    areas = _guard_areas()
    assert areas, "no area directories found under mutants/ at all"
    batches = [
        b
        for area in areas
        for b in (_DEV_TREE / "mutants" / area).glob("test_*.py")
    ]
    assert batches, "no mutant batches found at all; the convention has evaporated"

    # Non-EMPTY is not the same as COMPLETE, and only the second one is the
    # property this file needs. `_guard_areas()` used to be the fixed tuple
    # `("conformance", "consistency")`; reverting it to any hardcoded tuple
    # leaves `assert areas` above perfectly green while a whole area goes
    # unpoliced by every assertion here. That is the same "still reports success,
    # stopped looking" shape this file exists to catch in other guards, so assert
    # against the filesystem rather than against truthiness.
    #
    # THE OLD `set(areas) == on_disk` COMPARISON IS GONE, and it is worth saying
    # why rather than just deleting it. It compared `_guard_areas()` against the
    # directories under `mutants/` — and when both sides were derived from
    # `mutants/` it was tautological, which its own comment admitted. Now that
    # areas come from `tests/` the two sides ARE independent, but the comparison
    # is the wrong one in a new way: equality demands that every guard area own a
    # batch DIRECTORY, which is a weaker restatement of
    # `test_every_guard_file_has_a_mutant_batch_beside_its_scope` with a worse
    # message, and it would go red for a legitimately-pending area. The
    # containment it was reaching for is now
    # `test_every_batch_area_is_a_guard_area`, asserted in the direction that
    # actually carries information.
    #
    # The floor below is what the tautology was standing in for, and it does not
    # change: these areas exist, and losing one is a deletion someone must argue
    # for, not a green run. It is an INDEPENDENT list on purpose — deriving it
    # from the filesystem would re-create the tautology exactly — the same
    # argument `REQUIRED_SUFFIXES` makes next door in
    # `test_no_hardcoded_plugin_paths.py`.
    #
    # Widened from three to all twelve in the commit that derived areas from
    # `tests/`: the seven directories that had no batches are now areas, and an
    # area absent from this list is an area whose disappearance nothing would
    # report.
    required = {
        "conformance", "consistency", "release", "annotate", "hooks",
        "_shared", "codify-retro", "launcher", "lib", "new-worktree",
        "spec-to-pr", "spec-to-pr-retro",
    }
    assert required <= set(areas), (
        f"area(s) {sorted(required - set(areas))} hold no guards any more — the "
        "directory was renamed, moved, or emptied, and its guards stopped being "
        "policed by this file. Removing an area is a deliberate change: delete "
        "it from `required` in the same commit, with a reason."
    )


# ---------------------------------------------------------------- the two collapse checks
#
# Both replaced a hand-maintained integer floor. A floor that has been re-derived
# four times (6, 15, 18, 24) is a measurement someone has to re-run on every
# move, and this file's own history records it drifting out of step with its
# comment twice. These two need no maintenance — but that is worth nothing
# unless they can still go red, so both are planted here.


def test_an_area_that_discovers_nothing_is_named(tmp_path, monkeypatch):
    """`_area_test_dir` returns None for an area whose tests directory cannot be
    located, and `Path.glob` over a missing directory is empty rather than an
    error — so the area contributes zero files and looks exactly like an area
    with nothing wrong."""
    assert _areas_discovering_nothing(_guard_areas()) == []      # the real tree
    assert _areas_discovering_nothing(("no-such-area",)) == ["no-such-area"]

    # And an area that RESOLVES but holds no guard files, which is the other way
    # to contribute nothing.
    (tmp_path / "tests" / "hollow").mkdir(parents=True)
    monkeypatch.setattr(sys.modules[__name__], "_DEV_TREE", tmp_path)
    assert _areas_discovering_nothing(("hollow",)) == ["hollow"]


def test_an_area_whose_every_guard_is_excused_is_named():
    """The failure a global policed-count cannot see: an area holding batches,
    reading as adopted, with not one guard actually demanded to have one. The
    other areas keep the total up."""
    areas = _guard_areas()
    assert _areas_policing_nothing(areas, _EXEMPT, _PENDING_ADOPTION) == []

    # Excuse every guard in one area and it must be named. Built from the tree
    # rather than hardcoded, so this keeps working as areas come and go.
    victim = "annotate"
    assert victim in areas, "the planted area no longer exists; pick another"
    rels = [_rel(p) for p in sorted(_area_test_dir(victim).glob("test_*.py"))]
    assert rels, "the planted area discovers nothing, so this proves nothing"
    swollen = dict(_PENDING_ADOPTION, **{r: "planted" for r in rels})
    assert _areas_policing_nothing(areas, _EXEMPT, swollen) == [victim]

    # Via _EXEMPT too — the other half of the disjunction.
    swollen2 = dict(_EXEMPT, **{r: "planted" for r in rels})
    assert _areas_policing_nothing(areas, swollen2, _PENDING_ADOPTION) == [victim]
