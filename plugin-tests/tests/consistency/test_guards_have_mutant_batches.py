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
    # line here the moment its batch lands. Tracked in TODO.md.
    "tests/conformance/test_no_hardcoded_plugin_paths.py": "grandfathered",
    "tests/consistency/test_check_script_drift.py": "grandfathered",
    "tests/consistency/test_ledger_names_agree.py": "grandfathered",
    "tests/consistency/test_marketplace_manifest.py": "grandfathered",
    "tests/consistency/test_pre_push_is_installed.py": "grandfathered",
    "tests/consistency/test_subprocess_encoding.py": "grandfathered",
    "tests/consistency/test_token_list_is_curated_here.py": "grandfathered",
    "tests/consistency/test_mutate.py": "grandfathered",
}


def test_the_grandfather_list_only_shrinks():
    """The pressure valve, bounded. A grandfathered guard is unproven debt; the
    list may lose entries but must never gain one, or the convention becomes
    opt-in and the whole check evaporates."""
    grandfathered = sum(1 for v in _EXEMPT.values() if v == "grandfathered")
    # RATCHET this down to the new real count whenever an entry is deleted. Left
    # at its original 12 while the real count fell to 8, it silently permitted
    # four new exemptions — a bound far above its population is the same
    # decorative-floor defect `test-quality.md` describes, applied to a ceiling.
    assert grandfathered <= 8, (
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


def test_every_guard_file_has_a_mutant_batch_beside_its_scope():
    missing = []
    for path in _guard_files():
        rel = _rel(path)
        if rel in _EXEMPT:
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
    assert not missing, (
        "guard(s) with no mutant batch — nobody has shown these can fail:\n"
        + "\n".join(missing)
        + "\n\nWrite one, then prove it: "
        "python3 plugin-tests/mutate.py plugin-tests/mutants/<area>/<name>.py"
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
    assert not problems, "mutant batch problems:\n" + "\n".join(problems)


def test_no_batch_hardcodes_an_absolute_path():
    """A batch resolving from an absolute developer path works on one machine and
    leaks a repo name into a directory the marketplace ships."""
    offenders = []
    for area in _guard_areas():
        for batch in sorted((_DEV_TREE / "mutants" / area).glob("*.py")):
            for lineno, line in enumerate(
                batch.read_text(encoding="utf-8").splitlines(), 1
            ):
                if ":\\" in line or line.lstrip().startswith("/home/"):
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


def test_the_scan_is_not_vacuous():
    files = _guard_files()
    # 17 today: `ls tests/{conformance,consistency,skills/release}/test_*.py | wc -l`.
    # Was `>= 6` against that same 17 — decorative, since a 65% collapse passed.
    # Re-derived here rather than left, per this repo's own `test-quality.md`:
    # a floor tracks its population or it is not a floor. Lower it to the new
    # real count when the population genuinely shrinks; never to survive a move.
    assert len(files) >= 15, f"guard discovery collapsed to {len(files)} files"
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
