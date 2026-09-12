"""Mutation batch for test_mutate.py — the suite for the mutation runner itself.

**Self-hosting, not circular, and that was measured before this batch was
written.** Running it means `mutate.py` edits `mutate.py` on disk while executing.
That works, and the mechanism is worth stating because it is not obvious: the
orchestrator has already imported itself into memory, so the on-disk edit cannot
affect the running process, while the child pytest imports the file fresh and
therefore sees the mutant. Probed with a single throwaway mutant before committing
to the approach — the child observed the change, the verdict came back, and
`git status` was clean afterwards, so the byte-exact restore holds under
self-mutation too.

This is the difference from the two meta-guards at `_EXEMPT`'s head. A batch for
`test_guards_have_mutant_batches.py` would assert that the pairing checker checks
pairing — the batch mechanism IS its subject, so there is nothing outside to
observe. Here the subject is an ordinary script that happens to be the runner;
`test_mutate.py` drives it as a SUBPROCESS against sandbox scopes in `tmp_path`,
so the observation is genuinely external. `test_mutate.py` therefore comes OFF the
grandfather list rather than being reclassified as a meta-guard.

**What these mutants target.** `mutate.py` exists to refuse to manufacture
confidence, and its docstring records four false-kill shapes a review found in the
first version. Mutants 1-4 re-break the refusals that close them. Mutants 5-7 hit
the mechanics the tool's correctness rests on rather than its verdicts — the
byte-exact restore, the bytecode drop, and the pinned child environment — each of
which has its own recorded incident in `mutate.py`.

**ONE MUTANT WAS WRITTEN, RUN, AND DELETED, and it is the most interesting result
here.** Weakening the kill verdict at its CALL SITE —
`if code == EXIT_TESTS_FAILED and _a_test_actually_ran(output):` ->
`if code == EXIT_TESTS_FAILED:` — SURVIVES the whole suite. The predicate
`_a_test_actually_ran` is thoroughly tested in isolation by a seven-case
parametrize, but nothing pins its USE. The reason is written in that test's own
docstring, honestly, before this batch existed: "every collection failure I could
construct exits 2 ... I could NOT reproduce an exit-1-with-zero-tests run, so this
predicate guards a path that may currently be unreachable." An unreachable branch
cannot be observed, so the mutant cannot be killed, and it is deleted rather than
shipped as a permanent survivor. Recorded here because the honest reading is not
"the guard is weak" but "the guard defends a path nothing can currently reach",
and a later reader deciding whether to delete that predicate should have this.

Anchors are single-line: `mutate.py` is CRLF, where a bare `\\n` matches nothing.

Run: python3 plugin-tests/mutate.py plugin-tests/mutants/consistency/test_mutate.py
"""

from pathlib import Path

DEV = Path(__file__).resolve().parents[2]

MUTATE = DEV / "mutate.py"
GUARD = DEV / "tests" / "consistency" / "test_mutate.py"
TARGET = [GUARD]

MUTANTS = [
    # ---- 1-4: the refusals that stop a false kill ----
    (
        "an ambiguous anchor is accepted instead of refused — only the first of "
        "several matches is mutated, so a kill can belong to a site nobody meant",
        MUTATE,
        "        elif hits > 1:",
        "        elif False:",
        TARGET,
    ),
    (
        "an empty MUTANTS list stops being refused, so a zero-mutant batch reports "
        "'All 0 mutant(s) killed' — confidence from a run that checked nothing",
        MUTATE,
        "    if not isinstance(mutants, list) or not mutants:",
        "    if not isinstance(mutants, list):",
        TARGET,
    ),
    (
        "a no-op mutant (old == new) stops being refused — it changes nothing and "
        "would report SURVIVED forever, reading as a real finding about the code",
        MUTATE,
        "        elif old == new:",
        "        elif False:",
        TARGET,
    ),
    (
        "pytest exit 0 is no longer reported as SURVIVED — the tool loses the "
        "ability to say NO, which is the half that makes a kill mean anything",
        MUTATE,
        "        elif code == EXIT_OK:",
        "        elif False:",
        TARGET,
    ),

    # ---- 5-7: the mechanics correctness rests on ----
    (
        "the restore writes text instead of bytes, so newline translation rewrites "
        "every line ending in an LF file — the defect that silently broke the "
        "eol=lf launchers, invisible to git diff",
        MUTATE,
        "            path.write_bytes(original)",
        '            path.write_text(original.decode("utf-8"))',
        TARGET,
    ),
    (
        "stale bytecode is left behind after the restore — a same-length mutant "
        "inside one second leaves the pyc holding the MUTANT while the source on "
        "disk is correct, which can leave a suite green over mutant code",
        MUTATE,
        "            _drop_bytecode(path)",
        "            pass",
        TARGET,
    ),
    (
        "the child environment stops being pinned to an allowlist — PYTEST_ADDOPTS, "
        "FORCE_COLOR and PYTHONOPTIMIZE reach the run and change what it measures",
        MUTATE,
        "    env = {k: v for k, v in os.environ.items() if k in _KEEP}",
        "    env = dict(os.environ)",
        TARGET,
    ),
]
