"""Mutant batch for `hooks/probe-python.sh`, the interpreter probe every
wiring in `hooks.json` sources, held by `tests/hooks/test_hooks_wiring.py`.

Run:
    python3 plugin-tests/mutate.py plugin-tests/mutants/hooks/test_probe_python.py

WHAT IT COVERS. The probe's four jobs: the interpreter search (stage order, the
`break`s that make the first working candidate win, the off-PATH stage 3), the
version check, the `$PYEXE` postcondition and refusal, and the `CLA_HOOK_T0`
start stamp the dispatchers' `Deadline` reads. `mutate.py` plants into any text
file by bytes, so a `.sh` subject needs nothing special. Each mutant was run
against the whole wiring test file; the killing test for each is named beside
it.

WHAT IT LEAVES OUT, named rather than implied:
- the cache WRITE (`mkdir`/`printf` into `$_cla_cache`): a probe that never
  writes the cache is slower, not wrong, and every test passes on a cold cache.
- stage 3's `[ -x "$_p" ] || continue`: the probe's own comment records that
  relaxing it survives, because `_cla_py_ok` is the real gate.
- the `[ -x "$_c_exe" ]` term of the cache hit: a cached path that no longer
  exists is caught one step later by the refusal's own `-x`.

Paths resolve from this file's own location, never an absolute developer path.
"""

from pathlib import Path

DEV = Path(__file__).resolve().parents[2]
PLUGIN = DEV.parent / ".claude" / "plugins" / "cla"
PROBE = PLUGIN / "hooks" / "probe-python.sh"
GUARD = DEV / "tests" / "hooks" / "test_hooks_wiring.py"
TARGETS = [GUARD]

MUTANTS = [
    # --- the start stamp -------------------------------------------------------
    # killed by test_the_probe_exports_a_fresh_start_stamp_or_an_empty_one
    ("the stamp keeps a value inherited from the environment",
     PROBE, "CLA_HOOK_T0=${EPOCHREALTIME:-}", "CLA_HOOK_T0=${CLA_HOOK_T0:-}", TARGETS),
    # killed by test_the_stamp_reaches_the_dispatcher_deadline
    ("the stamp is set but never exported to the hook",
     PROBE, "export CLA_HOOK_T0\n", ": CLA_HOOK_T0\n", TARGETS),
    # killed by test_the_probe_exports_a_fresh_start_stamp_or_an_empty_one
    ("the stamp is a fixed old time",
     PROBE, "CLA_HOOK_T0=${EPOCHREALTIME:-}", "CLA_HOOK_T0=1000.5", TARGETS),
    # --- the postcondition and refusal -------------------------------------------
    # killed by test_probe_rejects_a_stale_exported_pyexe
    ("the probe no longer clears an exported PYEXE",
     PROBE, "\nPYEXE=\n", "\n: PYEXE=\n", TARGETS),
    # killed by test_probe_announces_failure_and_exits_non_zero
    ("the refusal exits 0, so the tool call runs unguarded and silently",
     PROBE, "guard hooks are NOT running. Set CLA_PYTHON to your interpreter.\" >&2\n  exit 1",
     "guard hooks are NOT running. Set CLA_PYTHON to your interpreter.\" >&2\n  exit 0", TARGETS),
    # killed by test_probe_refuses_a_python_that_is_not_an_executable_file: a
    # `python3` shell function passes the version check, and only this `-x`
    # refuses its bare name (the wiring's own `-x` hides it, so that test
    # sources the probe directly)
    ("the refusal accepts a set but non-executable PYEXE",
     PROBE, 'if [ -z "$PYEXE" ] || [ ! -x "$PYEXE" ]; then', 'if [ -z "$PYEXE" ]; then', TARGETS),
    # killed by test_an_unusable_cla_python_refuses_loudly
    ("an unusable CLA_PYTHON falls through instead of refusing",
     PROBE, "fall back to the search.\" >&2\n    exit 1", "fall back to the search.\" >&2\n    :", TARGETS),
    # --- the version check -------------------------------------------------------
    # killed by test_probe_rejects_an_interpreter_that_exits_zero_for_everything
    ("the version check accepts any interpreter that exits 0",
     PROBE,
     """  [ "$("$1" -c 'import sys; sys.stdout.buffer.write(b"1" if sys.version_info >= (3,8) else b"0")' 2>/dev/null)" = 1 ]""",
     """  "$1" -c 'import sys' 2>/dev/null""", TARGETS),
    # killed by test_a_python_2_lookalike_that_prints_zero_is_rejected
    ("the version check accepts a printed 0",
     PROBE, '2>/dev/null)" = 1 ]', '2>/dev/null)" != "" ]', TARGETS),
    # --- the search ----------------------------------------------------------------
    # killed by test_probe_tries_the_candidate_names_in_the_same_order
    ("stage 2 tries python before python3",
     PROBE, "for _c in python3 py python; do", "for _c in python py python3; do", TARGETS),
    # killed by test_the_first_working_candidate_name_wins
    ("stage 2 keeps going after a working name, so the last one wins",
     PROBE, "if _cla_py_ok \"$_p\"; then PYEXE=$_p; break; fi", "if _cla_py_ok \"$_p\"; then PYEXE=$_p; fi", TARGETS),
    # killed by test_stage_three_stops_at_its_first_match
    ("stage 3 prints every match, concatenating the paths",
     PROBE, "then printf '%s' \"$_p\"; break; fi", "then printf '%s' \"$_p\"; fi", TARGETS),
    # killed by test_stage_three_finds_an_interpreter_that_is_not_on_path
    ("stage 3 never runs",
     PROBE, '  PYEXE=$(\n    if [ -n "${CLA_PY_SEARCH+set}" ]; then',
     '  PYEXE=$(exit 0\n    if [ -n "${CLA_PY_SEARCH+set}" ]; then', TARGETS),
    # killed by test_cla_python_overrides_a_working_path_interpreter
    ("CLA_PYTHON is ignored when stage 2 finds something",
     PROBE, 'if [ -z "$PYEXE" ] && [ -n "${CLA_PYTHON:-}" ]; then',
     'if false && [ -n "${CLA_PYTHON:-}" ]; then', TARGETS),
    # --- the cache key -------------------------------------------------------------
    # killed by test_a_warm_cache_does_not_survive_a_poisoned_path
    ("the cache hits under a different PATH",
     PROBE, 'if [ "$_c_path" = "$PATH" ] && [', 'if [ "$_c_path" = "$_c_path" ] && [', TARGETS),
]
