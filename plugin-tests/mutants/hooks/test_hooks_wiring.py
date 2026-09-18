"""Mutant batch for `tests/hooks/test_hooks_wiring.py`.

Run: python3 plugin-tests/mutate.py plugin-tests/mutants/hooks/test_hooks_wiring.py

WHAT IT COVERS. Two things, and the second is why the batch exists at all.

The new half is the top-level key set of `hooks.json` (issue #254). That file
carried a `_comment` array the plugin loader does not recognise, so every session
in every consuming repo printed `unknown key "_comment" ignored` — noise on the
hottest path, unfixable downstream because the install cache is read-only. The
guards all loaded, nothing broke, and nothing pinned the key set, which is how it
survived three releases. The mutants below re-create both ways it comes back: a
recognised key RENAMED to an unrecognised one, and an unrecognised key ADDED
beside a correct `description`. The second is the one that isolates the key-set
assertion, because the description guard still passes on it.

The old half is one entry re-breaking a regression this module's own docstring
records: `exit 1` deleted from ONE of the five otherwise-identical wiring
prologues. That survived a mutation run once, because the only executed test read
`hooks.PreToolUse[0]` and the only text test asserted a substring the other four
copies still satisfied.

WHAT IT DOES NOT COVER, stated because this file leaving `_PENDING_ADOPTION` must
not read as the area being finished. `tests/hooks/test_hooks_wiring.py` also
polices the handler-timeout budget, and its own comments say what that budget
cannot check: whether a `HOOK_WORST_CASE_SECONDS` entry matches the hook's REAL
cost. No mutant can close that — the table is the only statement of the cost
there is, so mutating it only proves the arithmetic reacts to its own inputs.
That gap is unchanged by this batch and is the reason the adoption note for this
file said "pin the gap rather than imply it is closed".

ANCHORS ARE SINGLE-LINE AND CARRY NO `\\n`. `hooks.json`'s five wiring prologues
are byte-identical by design (one test asserts exactly that), so every anchor
that touches a prologue has to reach past it to the dispatcher name to be unique.
`mutate.py` refuses an ambiguous anchor before touching anything, which is what
makes that constraint visible rather than silent.
"""

from pathlib import Path

DEV = Path(__file__).resolve().parents[2]
PLUGIN = DEV.parent / ".claude" / "plugins" / "cla"
HOOKS_JSON = PLUGIN / "hooks" / "hooks.json"
TARGETS = [DEV / "tests" / "hooks" / "test_hooks_wiring.py"]

MUTANTS = [
    (
        "the loader-recognised `description` is renamed back to `_comment`, "
        "which is the defect issue #254 fixed: the loader warns once per session "
        "in every consuming repo and drops the text entirely",
        HOOKS_JSON,
        '"description":',
        '"_comment":',
        TARGETS,
    ),
    (
        # Kills on the key-set assertion ALONE, and that is MEASURED rather than
        # reasoned: the same edit run with the target narrowed to
        # `test_hooks_wiring.py::test_the_hooks_json_description_points_at_the_
        # probe` reports SURVIVED, because `description` is still present and
        # still names the probe. Re-derive by copying this entry into a throwaway
        # batch with that `::`-qualified node as its only target. That is the
        # attribution the mutant above cannot give, since renaming the key fails
        # both guards at once — `mutate.py` runs `pytest -x` and reports one
        # verdict per mutant, so a batch can never say WHICH assertion fired.
        "a second unrecognised key appears beside a correct `description` — the "
        "same warning, from a key nobody removed",
        HOOKS_JSON,
        '"description": "Guard-hook',
        '"_pyexe": "stale", "description": "Guard-hook',
        TARGETS,
    ),
    (
        # Re-breaks the regression `test_every_wiring_is_byte_identical_up_to_
        # its_hook` was written for. Anchored through to the dispatcher name
        # because the prologue itself appears five times, identically.
        "ONE wiring loses `exit 1` from its postcondition clause, so an unusable "
        "probe lets that tool call proceed unguarded while the other four refuse",
        HOOKS_JSON,
        'exit 1; }; \\"$PYEXE\\" \\"${CLAUDE_PLUGIN_ROOT}/hooks/dispatch-edit-write-pretooluse.py\\"',
        '}; \\"$PYEXE\\" \\"${CLAUDE_PLUGIN_ROOT}/hooks/dispatch-edit-write-pretooluse.py\\"',
        TARGETS,
    ),
]
