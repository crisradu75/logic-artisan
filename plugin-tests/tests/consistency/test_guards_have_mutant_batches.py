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
    """Every subdirectory actually present under `mutants/` — i.e. every area
    that holds at least one mutant batch.

    Was a fixed two-tuple, `("conformance", "consistency")`, mirroring the two
    `*-checks` scope directories that predated the dev-tree move. That shape
    could not address this PR's own new pairing, `mutants/release/` <->
    `tests/skills/release/` — a fixed tuple is silently unpoliced the moment a
    new area is added, which is exactly the kind of drop this file exists to
    catch elsewhere. Deriving the list from the filesystem means a future new
    area is discovered rather than requiring someone to remember to add it
    here."""
    mutants_root = _DEV_TREE / "mutants"
    if not mutants_root.is_dir():
        return ()
    # Dunder directories only. Taking EVERY subdirectory made `__pycache__` a
    # phantom area the moment anything ran under `mutants/`.
    #
    # A first cut also required `any(p.glob("test_*.py"))` — and that condition
    # was a fifth instance of the exact defect this whole change set exists to
    # fix. An area whose batches are deleted would stop BEING an area, so its
    # guards silently dropped out of every assertion here instead of failing.
    # Measured: with a `mutants/hooks/` area present, deleting its one batch took
    # `_guard_files()` from 30 to 17 and left all three assertions GREEN. The
    # `__pycache__` bug is fixed by the dunder half alone; the glob half only
    # bought silence. An emptied area now survives into the list and fails
    # `test_every_derived_area_resolves_to_a_tests_directory` loudly, which is
    # the whole point of this file.
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
    # This file and its sibling ARE the meta-guards; a mutant batch for them
    # would assert that the pairing checker checks pairing, which is circular.
    "tests/consistency/test_guards_have_mutant_batches.py":
        "meta-guard: mutating it only tests itself",
    "tests/conformance/test_guards_are_not_vacuous.py":
        "meta-guard: carries seeded-input tests of its own checker instead",

    # GRANDFATHERED, not excused. These guards predate the convention and have
    # never had a mutant written for them, so nobody has shown they can fail.
    # They are listed individually — rather than the rule being softened to
    # "new files only" — so the debt is countable and shrinks visibly. Delete a
    # line here the moment its batch lands. Tracked in issue #176.
    "tests/conformance/test_no_hardcoded_plugin_paths.py": "grandfathered",
    "tests/consistency/test_ledger_names_agree.py": "grandfathered",
    "tests/consistency/test_marketplace_manifest.py": "grandfathered",
    "tests/consistency/test_pre_push_is_installed.py": "grandfathered",
    "tests/consistency/test_subprocess_encoding.py": "grandfathered",
    "tests/consistency/test_token_list_is_curated_here.py": "grandfathered",
    "tests/consistency/test_mutate.py": "grandfathered",
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
# tree and committed nowhere, so it now exists nowhere.
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
}

# Re-derive on the commit that adopts an area, then only lower it. This is the
# one bound in the file allowed to move UP, and only there — see
# `test_adoption_debt_only_shrinks` for why that is stated as a number rather
# than trusted to the diff.
# Raised 0 -> 3 in the commit that adopts `annotate` as a mutants area, which is
# the one direction this number is allowed to move and only there. Three of the
# area's six guards got a batch in that commit; these are the other three.
_PENDING_ADOPTION_CEILING = 3


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
    assert grandfathered <= 7, (
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
    arbitrarily."""
    unresolved = [a for a in _guard_areas() if _area_test_dir(a) is None]
    assert not unresolved, (
        f"area(s) {unresolved} have mutant batches but no single matching "
        f"directory under tests/ — their guards are policed by nothing"
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


def test_the_area_filter_rejects_both_shapes_it_exists_for(tmp_path, monkeypatch):
    """Plant the two directories the filter must reject, rather than relying on
    one happening to be there.

    `_guard_areas()` filters `__pycache__`-style dunder dirs AND directories
    holding no batch. Its only witness in the real tree is `mutants/__pycache__`,
    which is GITIGNORED — a runtime artifact, not a fixture. On a fresh clone,
    before anything has run, it does not exist, and the cross-check in
    `test_the_scan_is_not_vacuous` then compares two sets that are trivially
    equal whether the filter is there or not. The second condition
    (a batch-less directory that is not a dunder) has no witness at all, ever.

    So both are planted here on a fake tree. This is the rule this repo's own
    `test-quality.md` states: prove a guard by planting what it must catch."""
    (tmp_path / "mutants" / "__pycache__").mkdir(parents=True)
    (tmp_path / "mutants" / "__pycache__" / "test_stale.py").write_text("x", encoding="utf-8")
    (tmp_path / "mutants" / "empty_area").mkdir()
    (tmp_path / "mutants" / "empty_area" / "notes.md").write_text("x", encoding="utf-8")
    (tmp_path / "mutants" / "real_area").mkdir()
    (tmp_path / "mutants" / "real_area" / "test_thing.py").write_text("x", encoding="utf-8")

    monkeypatch.setattr(sys.modules[__name__], "_DEV_TREE", tmp_path)
    areas = _guard_areas()

    assert "__pycache__" not in areas, (
        "a dunder directory is a runtime artifact, not an area — even when it "
        "holds a `test_*.py`, which a cached batch does"
    )
    # `empty_area` MUST survive. Filtering a batch-less directory out was the
    # tempting second condition, and it is the one that turns "this area lost its
    # batches" from a red run into silence. It stays in the list precisely so the
    # resolution check below can fail on it.
    assert "empty_area" in areas, (
        "a directory that lost its batches must remain an area and fail loudly; "
        "filtering it out is how an unpoliced area becomes invisible"
    )
    assert areas == ("empty_area", "real_area")
    assert _area_test_dir("empty_area") is None, (
        "the planted batch-less area must be the thing that fails resolution"
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
    # leaves `assert areas` above perfectly green while a whole area — the
    # `mutants/release/` this change adds — goes unpoliced by all four
    # assertions here. That is the same "still reports success, stopped
    # looking" shape this file exists to catch in other guards, so assert
    # against the filesystem rather than against truthiness.
    on_disk = {
        d.name
        for d in (_DEV_TREE / "mutants").iterdir()
        if d.is_dir() and not d.name.startswith("__") and any(d.glob("test_*.py"))
    }
    assert set(areas) == on_disk, (
        f"_guard_areas() returned {sorted(areas)} but mutants/ holds batches in "
        f"{sorted(on_disk)} — an area missing here is an area nothing checks"
    )

    # The comparison above is TAUTOLOGICAL on its own: both sides are derived
    # from `mutants/`, so deleting a whole area directory keeps them equal while
    # silently dropping that area's guards from every assertion in this file
    # (measured: removing `mutants/conformance/` takes `_guard_files()` from 15
    # to 10 and all four assertions still pass). Discovery cannot floor itself.
    # So the floor is stated here instead: these areas exist, and losing one is
    # a deletion someone must argue for, not a green run.
    required = {"conformance", "consistency", "release"}
    assert required <= set(areas), (
        f"area(s) {sorted(required - set(areas))} have no mutant batch directory "
        "any more — their guards just stopped being policed by this file. "
        "Removing an area is a deliberate change: delete it from `required` in "
        "the same commit, with a reason."
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
