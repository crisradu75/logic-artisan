"""Mutant batch for `tests/test_no_project_tokens.py`.

Run: `python3 <plugin>/mutate.py <plugin>/conformance-checks/mutants/test_no_project_tokens.py`

The guard was promoted out of this scope into a program at
`skills/_shared/scripts/check_no_project_tokens.py`; the tests for it stayed
here. So the mutants break the PROGRAM and the tests in this scope are the
target.

Each entry breaks one branch where a wrong choice yields a SILENT CLEAN REPORT.
Two shapes:

  (i)  exit-code selection. `0` where the code returns `1`, and `1` where it
       returns `2`. A checker that answers "clean" when it found leaks, or
       "leaks found" when it could not look, is worse than no checker.
  (ii) violation accumulation across the FOUR checks. Short-circuiting after the
       first check that reports, or dropping check (d) — the readability check —
       entirely.

The check-(d) mutant is the one this batch most exists for. design.md D2 names
it as the check most likely to be dropped as "not really a check", and its
absence is invisible to every other assertion: an unreadable file returns "no
violations", which is exactly what a clean file returns.

The last two entries mutate what the promotion TOUCHED rather than what it
targeted — one carried-over heuristic in each of the two scanners — because a
promotion that quietly broke one of those would pass every CLI test above it.

Paths resolve from this file's own location: a batch with an absolute developer
path works on one machine and leaks a repo name into synced core.
"""

from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[2]
CHECKER = PLUGIN / "skills" / "_shared" / "scripts" / "check_no_project_tokens.py"
TARGETS = [PLUGIN / "conformance-checks" / "tests"]

MUTANTS = [
    (
        "violations are found but the program reports success",
        CHECKER,
        "    return EXIT_VIOLATIONS",
        "    return EXIT_CLEAN",
        TARGETS,
    ),
    (
        "a blocker with no violations is reported as violations found",
        CHECKER,
        "        return EXIT_CANNOT_RUN  # branch: could not run, and no violation to report",
        "        return EXIT_VIOLATIONS  # branch: could not run, and no violation to report",
        TARGETS,
    ),
    (
        # This is IMPORTANT-10's own fix: confirmed violations must win over a
        # coexisting blocker (exit 1, not 2). Mutating the gate back to `if
        # False:` reverts to the pre-fix behaviour where a blocker masks real
        # violations as "could not look" — silent from the caller's exit-code
        # perspective, since violations are still PRINTED either way.
        "confirmed violations no longer win over a coexisting blocker",
        CHECKER,
        "    if violations:",
        "    if False:",
        TARGETS,
    ),
    (
        "a bad --repo-root is reported as a violation rather than a broken run",
        CHECKER,
        "            return EXIT_CANNOT_RUN",
        "            return EXIT_VIOLATIONS",
        TARGETS,
    ),
    (
        "the run short-circuits after the first of the four checks that reports",
        CHECKER,
        "    for rel, kind, lineno, excerpt in find_absolute_path_leaks(plugin_root):",
        "    for rel, kind, lineno, excerpt in ([] if violations else find_absolute_path_leaks(plugin_root)):",
        TARGETS,
    ),
    (
        "check (d), the readability check, is dropped entirely",
        CHECKER,
        "    for rel, reason in find_unreadable_files(plugin_root):",
        "    for rel, reason in []:",
        TARGETS,
    ),
    (
        "a present-but-empty token list silently disables the guard",
        CHECKER,
        "            if not tokens:",
        "            if False:",
        TARGETS,
    ),
    (
        "the prose scanner stops excluding the tests/ and scripts/ subtrees",
        CHECKER,
        'EXCLUDED_SUBTREES = frozenset({"tests", "scripts"})',
        "EXCLUDED_SUBTREES = frozenset()",
        TARGETS,
    ),
    (
        "the absolute-path scanner stops exempting illustrative placeholder paths",
        CHECKER,
        'PLACEHOLDER_PATH_HINTS = ("<", "...")',
        "PLACEHOLDER_PATH_HINTS = ()",
        TARGETS,
    ),
    (
        # IMPORTANT-5's own fix: `_iter_scanned_source_files` silently `continue`s
        # past an absent scan root, so a whole missing root (heavy coverage loss)
        # was invisible before this function existed. Forcing it to always report
        # "nothing missing" reverts to that silent behaviour.
        "a missing expected source scan root is never reported",
        CHECKER,
        "    return [name for name in SOURCE_SCAN_ROOTS if not (plugin_root / name).is_dir()]",
        "    return []",
        TARGETS,
    ),
]
