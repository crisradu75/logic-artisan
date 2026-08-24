"""Mutant batch for `tests/test_project_facts_paths.py`.

Run: python3 plugin-tests/mutate.py plugin-tests/mutants/conformance/test_project_facts_paths.py

The guard was promoted out of this scope into a program at
`skills/sync-context/scripts/check_fact_paths.py`; the tests for it stayed here.
So the mutants break the PROGRAM and the tests in this scope are the target.

Each entry breaks one branch where a wrong choice yields a SILENT CLEAN REPORT —
the failure this promotion could plausibly introduce and no green suite would
show. Two shapes:

  (i)  exit-code selection. `0` where the code returns `1`, and `1` where it
       returns `2`. A checker that answers "clean" when it found stale paths, or
       "stale paths found" when it could not look, is worse than no checker: a
       caller scripting the exit code acts on the wrong answer with confidence.
  (ii) violation accumulation. Stopping after the first stale path, or letting
       the trivial-pass branch swallow a repo that DOES have something to scan.

The last entry mutates what the promotion TOUCHED rather than what it targeted —
a carried-over extraction heuristic — because a promotion that quietly broke one
of those would pass every CLI test above it.

Paths resolve from this file's own location: a batch with an absolute developer
path works on one machine and leaks a repo name into synced core.
"""

from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[3] / ".claude" / "plugins" / "cla"
DEV = Path(__file__).resolve().parents[2]
CHECKER = PLUGIN / "skills" / "sync-context" / "scripts" / "check_fact_paths.py"
TARGETS = [DEV / "tests" / "conformance"]

MUTANTS = [
    (
        "stale paths are found but the program reports success",
        CHECKER,
        "    return EXIT_STALE",
        "    return EXIT_CLEAN",
        TARGETS,
    ),
    (
        "'I could not look' is reported as 'I found stale paths'",
        CHECKER,
        "            return EXIT_CANNOT_RUN",
        "            return EXIT_STALE",
        TARGETS,
    ),
    (
        "a broken extraction (zero candidates, facts file present) reads as clean",
        CHECKER,
        "        return EXIT_CANNOT_RUN  # branch: extraction yielded nothing",
        "        return EXIT_CLEAN  # branch: extraction yielded nothing",
        TARGETS,
    ),
    (
        "an unreadable input is reported as a staleness rather than a broken run",
        CHECKER,
        "        return EXIT_CANNOT_RUN  # branch: unreadable input",
        "        return EXIT_STALE  # branch: unreadable input",
        TARGETS,
    ),
    (
        "reporting stops at the first stale path instead of naming them all",
        CHECKER,
        '        print(f"{rel}:{lineno}  stale path {candidate!r}")',
        '        print(f"{rel}:{lineno}  stale path {candidate!r}"); break',
        TARGETS,
    ),
    (
        "the trivial-pass branch swallows a repo that DOES have files to scan",
        CHECKER,
        "    if not scanned_files:",
        "    if True:",
        TARGETS,
    ),
    (
        # IMPORTANT-2's own fix: the zero-candidates blocker used to be gated on
        # `facts_file.is_file()`, so an overlay-only repo (no facts file) that
        # extracted zero candidates exited 0 clean instead of 2. Restoring that
        # gate (using the module-level `PROJECT_FACTS_RELPATH` since the local
        # `facts_file` variable no longer exists) reverts the fix.
        "the zero-candidates blocker is re-gated on the facts file specifically",
        CHECKER,
        "    if checked == 0:",
        "    if (repo_root / PROJECT_FACTS_RELPATH).is_file() and checked == 0:",
        TARGETS,
    ),
    (
        # Anchored on the function body rather than on the regex literal. The
        # sibling guard `test_no_batch_hardcodes_an_absolute_path` USED TO read a
        # colon followed by a backslash as a Windows drive path, and the
        # line-suffix pattern contains exactly that pair before its digit class —
        # so quoting the pattern here tripped the guard rather than mutating the
        # code. That constraint is gone: the guard now requires a drive-letter
        # shape, so a regex literal is safe to quote. This anchor is left as-is
        # because it works, not because it is still forced.
        "the carried-over `:line[:col]` strip stops removing the suffix",
        CHECKER,
        "    return _TRAILING_LINE_COL_RE.sub(\"\", token)",
        "    return token",
        TARGETS,
    ),
    (
        # Round 2: the diagnostic the test is NAMED for was never asserted — the
        # branch returns EXIT_CLEAN whether or not it prints, so deleting the
        # whole `if` survived. The test now captures stdout; this mutant is what
        # proves that.
        "the live iterdir-fallback diagnostic stops being printed",
        CHECKER,
        '    if _tracked_top_level_names(repo_root) is None and (repo_root / ".git").exists():',
        "    if False:",
        TARGETS,
    ),
    (
        # Round 2: one unreadable input used to raise out of `scan()`, discarding
        # every stale path found before it and returning 2 — a blocker outranking
        # confirmed violations. Collapsing the per-file guard back into a bare
        # read restores that inversion.
        "an unreadable input again discards the stale paths already found",
        CHECKER,
        "            unreadable.append((rel, f\"{type(exc).__name__}: {exc}\"))",
        "            raise",
        TARGETS,
    ),
]
