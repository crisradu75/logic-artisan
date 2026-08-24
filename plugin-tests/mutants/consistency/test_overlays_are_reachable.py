"""Mutation batch for test_overlays_are_reachable.py.

The guard's whole claim is that it asks the READER where it looks. That claim
was false for one of its three readers: `_import_from` named a directory, put it
on `sys.path`, and then called a bare `__import__`, which resolves from
`sys.modules` first. After the dev-tree extraction deleted
`.claude/plugins/cla/conformance-checks/`, the directory it named stopped
existing and the guard kept passing in the full run, because collecting
`tests/conformance/` first had already put a module of that name in
`sys.modules`. Measured on `main`:

    $ python -m pytest plugin-tests/tests/consistency/ -q
    1 failed, 114 passed, 1 skipped
    $ python -m pytest plugin-tests/tests/conformance/ plugin-tests/tests/consistency/ -q
    238 passed, 1 skipped

That is the rare shape where the shipping gate is green and the edit loop is
red, which is why it survived a merge.

Mutants 1 and 2 are the same edit under two different targets, deliberately.
Alone, mutant 1 only shows that a dead path fails when nothing has preloaded the
module — the OLD code passed that too, so it is not the interesting evidence.
Mutant 2 runs `tests/conformance/` first in the same pytest process, which is
exactly the condition under which the old code SURVIVED. It is the mutant that
distinguishes a by-path load from an ambient one.

Mutant 3 keeps the pair honest: it proves the imported guard is actually
interrogated, not merely imported.

Run: python3 plugin-tests/mutate.py plugin-tests/mutants/consistency/test_overlays_are_reachable.py
"""

from pathlib import Path

DEV = Path(__file__).resolve().parents[2]
PLUGIN = DEV.parent / ".claude" / "plugins" / "cla"

GUARD = DEV / "tests" / "consistency" / "test_overlays_are_reachable.py"
CONFORMANCE = DEV / "tests" / "conformance"
CHECKER = PLUGIN / "skills" / "sync-context" / "scripts" / "check_fact_paths.py"

# Scoped to the ONE guard file, never to `tests/consistency/` as a whole: a
# target that is red for any other reason reports every mutant "killed" and
# proves nothing. `PRELOADED` widens that by exactly one directory, and only
# because populating `sys.modules` with a same-named module IS the condition
# under test. `tests/conformance/` is green today
# (`python -m pytest plugin-tests/tests/conformance/ -q` -> 123 passed), and
# pytest collects its arguments in the order given, so conformance is imported
# before the guard runs.
TARGETS = [GUARD]
PRELOADED = [CONFORMANCE, GUARD]

_LIVE_RESOLVER = '        _DEV_TREE / "tests" / "conformance", "test_project_facts_paths"'
_DEAD_RESOLVER = '        _DEV_TREE / "tests" / "conformance-checks", "test_project_facts_paths"'

MUTANTS = [
    (
        "the resolver names a directory that does not exist",
        GUARD,
        _LIVE_RESOLVER,
        _DEAD_RESOLVER,
        TARGETS,
    ),
    (
        "the resolver names a dead directory while a same-named module is "
        "already loaded (the regression that shipped)",
        GUARD,
        _LIVE_RESOLVER,
        _DEAD_RESOLVER,
        PRELOADED,
    ),
    (
        # Non-vacuity partner for the two above. Without this, a `_import_from`
        # that returned a correct-but-inert object would still satisfy them.
        #
        # It anchors on the LITERAL inside `_iter_scanned_files`, not on the
        # module-level `OVERLAY_GLOB` constant. Mutating the constant SURVIVED
        # the first run of this batch, which is how the constant turned out to be
        # dead: `grep -rn OVERLAY_GLOB .claude/plugins/cla plugin-tests` shows
        # its only reads are of `LEGACY_OVERLAY_GLOB`, while the overlay walk at
        # `check_fact_paths.py:436` spells `"*.md"` inline. Reported rather than
        # fixed here — this branch is not touching the shipped checker.
        "the staleness checker stops matching this repo's overlay files",
        CHECKER,
        '        for path in sorted(overlays_root.glob("*.md")):',
        '        for path in sorted(overlays_root.glob("*.markdown")):',
        TARGETS,
    ),
]

# NOT mutated, deliberately, so "the batch is all-green" does not imply coverage
# this batch lacks.
#
# **Deleting the `path.is_file()` assert.** It survives, and correctly: with the
# live path in place there is nothing for it to catch. What the assert buys is
# that mutant 2 fails LOUDLY instead of resolving from `sys.modules`, so it is
# proven by mutant 2's kill rather than by a mutant of its own.
#
# **The two `_git_common` readers.** They are on this scope's `pythonpath`, so
# they were ambiently importable regardless of the path named — the same latent
# defect, fixed by the same change to `_import_from`. Their own behaviour is
# covered by `tests/skills/spec-to-pr/test__git_common.py`.
