"""Mutation batch for test_guards_have_mutant_batches.py.

**THIS FILE WAS THE LAST `_EXEMPT` ENTRY, AND THE EXEMPTION COST SOMETHING.** The
stated reason was "meta-guard: mutating it only tests itself". That is true of
exactly ONE of its tests — `test_every_guard_file_has_a_mutant_batch_beside_its_
scope`, which would be asserting that the pairing checker checks pairing — and
false of the helpers, which are the part that actually broke.

`_area_test_dir`, `_guard_areas` and `_batch_areas` are all driven by planted
`tmp_path` trees through a monkeypatched `_DEV_TREE`. A mutant edits the helper
and the killing assertion comes from an observation of a FIXTURE, not of itself.
Nothing is circular. Same argument that took `test_mutate.py` and then
`test_guards_are_not_vacuous.py` off that list — and with this batch `_EXEMPT` is
empty, which is the end state the mechanism was aiming at.

**What the exemption cost, and what mutant 1 re-breaks.** `_area_test_dir`
short-circuited on `tests/<area>` before reaching its own ambiguity check. Areas
are LEAF NAMES, so a top-level `tests/<X>` and a nested `tests/skills/<X>` are the
same area — and the short-circuit resolved that collision silently to the
top-level directory. Measured by planting `tests/skills/lib/test_collide.py`
against the real tree: `unresolved` was empty, the collided guard was absent from
`_guard_files()`, `_guards_missing_a_batch()` was empty, and every assertion in
the file passed. A guard could ship with no batch, checked by the file whose
whole job is to notice that.

Worse, the docstring CLAIMED the ambiguity arm protected there. A widening that
reads as coverage is the same shape as the `_feeds` overreach on the parent
branch, and it earns the same evidence.

**Mutants 2-4 are the derivation itself**, which is what the parent PR changes:
where areas come from, how deep discovery goes, and whether a runtime artifact
can pose as an area. Each is killed by a planted tree rather than by the real
one, so none of them depends on the repo's current shape.

**DELIBERATELY NOT A MUTANT: raising `_PENDING_ADOPTION_CEILING`.** The assertion
is `len(_PENDING_ADOPTION) <= _PENDING_ADOPTION_CEILING`, so a HIGHER ceiling
passes by construction — nothing ever fails because a ceiling is too high. That
is the property that makes the number worth defending in review rather than in a
test, and it is why the batches were written before the derivation rather than
the ceiling being raised to absorb them.

Run: python3 plugin-tests/mutate.py plugin-tests/mutants/consistency/test_guards_have_mutant_batches.py
"""

from pathlib import Path

DEV = Path(__file__).resolve().parents[2]

GUARD = DEV / "tests" / "consistency" / "test_guards_have_mutant_batches.py"

# Scoped to the ONE guard file: every mutant below edits a helper defined in it,
# and every killing assertion is one of its own planted-tree tests.
TARGETS = [GUARD]

# Derived, not spelled: the checkout is CRLF, and mutant 1 INSERTS lines. A bare
# `\n` there would write LF into a CRLF file — harmless to the restore, which is
# byte-exact from a backup, but it leaves the mutated file in a state no editor
# in this repo would produce. Same derivation the annotate batches use.
_NL = "\r\n" if b"\r\n" in GUARD.read_bytes() else "\n"

MUTANTS = [
    (
        # THE FINDING, re-broken. Restoring the short-circuit puts the ambiguity
        # arm back out of reach for the one collision that actually occurs.
        "the `tests/<area>` short-circuit returns before the ambiguity check, so "
        "a top-level/nested leaf-name collision resolves silently instead of refusing",
        GUARD,
        "    nested = sorted(p for p in root.rglob(area) if p.is_dir())",
        "    direct = root / area" + _NL
        + "    if direct.is_dir():" + _NL
        + "        return direct" + _NL
        + "    nested = sorted(p for p in root.rglob(area) if p.is_dir())",
        TARGETS,
    ),
    (
        # The regression the parent PR exists to fix: areas read back out of
        # `mutants/`, so a directory with no batches stops being an area and its
        # guards become uncountable rather than merely unpoliced.
        "areas are derived from mutants/ again, so a directory with zero batches "
        "stops being an area and its guards drop out of every assertion",
        GUARD,
        '        sorted({p.parent.name for p in tests_root.rglob("test_*.py")})',
        '        sorted({p.name for p in (_DEV_TREE / "mutants").iterdir() if p.is_dir()})',
        TARGETS,
    ),
    (
        # Discovery stops descending. `tests/skills/<name>/` is one segment
        # deeper, so this silently drops every skill area — the same nesting
        # assumption `_area_test_dir` was fixed to abandon.
        "area discovery stops descending, so every nested skill area vanishes and "
        "only the top-level directories are policed",
        GUARD,
        '        sorted({p.parent.name for p in tests_root.rglob("test_*.py")})',
        '        sorted({p.parent.name for p in tests_root.glob("test_*.py")})',
        TARGETS,
    ),
    (
        # `__pycache__` appears under `mutants/` the moment anything runs, and
        # without the filter it poses as a batch area. Not hypothetical: leftover
        # cache directories from a branch switch are what made this exact shape
        # red a full-suite run during this change.
        "the dunder filter comes off the batch areas, so a __pycache__ directory "
        "poses as an area nothing is paired with",
        GUARD,
        '            if p.is_dir() and not p.name.startswith("__")',
        "            if p.is_dir()",
        TARGETS,
    ),
]
