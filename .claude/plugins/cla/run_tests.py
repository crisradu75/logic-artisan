#!/usr/bin/env python3
"""Top-level test runner for the cla plugin.

Each skill *that ships tests* (and the guard-hooks dir) is its own isolated
pytest scope with its own ``pyproject.toml`` (``[tool.pytest.ini_options]`` —
``pythonpath = ["scripts"]`` / ``testpaths = ["tests"]``) and a sibling
``tests/`` dir. They CANNOT share one
pytest process: multiple scopes ship a top-level ``scripts/aggregate.py`` and
``scripts/log_run.py``, and Python refuses to import two different modules under
the same name in one interpreter. A root ``conftest.py``/``pyproject.toml``
therefore can't collect the whole plugin — running ``pytest`` from the plugin
root fails collection by design.

This runner instead discovers every isolated scope and runs ``pytest`` once per
scope as a separate subprocess, with that scope as the working dir so its own
``pyproject.toml`` is the rootdir — exactly the invocation that passes today
per-skill — then aggregates the results into one pass/fail summary and exit code.

Because a false green is the worst outcome for a CI gate, discovery is defensive:
a **scope** is a dir with BOTH a pytest-configured ``pyproject.toml`` AND a
``tests/`` subdir; a dir with exactly one of those signals is a **near-miss** (a
half-removed or misconfigured scope — e.g. someone renamed ``tests/`` or dropped
the ``pyproject.toml``) and **fails the run** rather than silently vanishing. On a
bare full run (no forwarded args) a discovered scope that collects zero tests
(pytest exit 5) also fails, since a scope only exists because it has a ``tests/``
dir — "no tests collected" there means the tests were renamed/misnamed out of
collection. When args ARE forwarded (e.g. ``-k foo``), exit 5 is expected filtering
and stays benign. (Residual limit: a scope whose ``pyproject.toml`` AND ``tests/``
are BOTH removed leaves no signal to detect — that's a deliberate teardown, not a
regression this heuristic can catch.)

Stdlib-only, no third-party deps (matches every other cla-plugin script). Uses
``sys.executable -m pytest`` so it runs under whatever interpreter launched it.

Usage (from anywhere):
    python3 .claude/plugins/cla/run_tests.py            # run every scope
    python3 .claude/plugins/cla/run_tests.py -q         # forward args to pytest
    python3 .claude/plugins/cla/run_tests.py -k branch  # e.g. filter by name

Any argument after the script name is forwarded verbatim to every per-scope
``pytest`` invocation. Exit code is 0 only when every scope passes, no near-miss
is found, and (on a bare full run) no discovered scope collects zero tests;
non-zero otherwise.
"""

from __future__ import annotations

import importlib.util
import re
import subprocess
import sys
from pathlib import Path


def _pin_streams_utf8() -> None:
    """Force UTF-8 on this process's own stdout/stderr.

    Load-bearing since the child decodes were pinned. Node's reporter emits
    `✔` and `ℹ`; with the child pinned to UTF-8 those now arrive as real
    characters, and writing them to a cp1252 stdout raises UnicodeEncodeError
    mid-run — killing the aggregated suite after several scopes had already
    passed. Pinning the input and not the output is half a contract, which is
    the same lesson the ledger scripts and `orchestrate.py` already carry.
    """
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except (OSError, ValueError):
                pass


_pin_streams_utf8()


PLUGIN_ROOT = Path(__file__).resolve().parent

# Dirs we never descend into when discovering scopes (caches, VCS, vendored deps).
EXCLUDE_PARTS = {"__pycache__", ".pytest_cache", ".git", ".venv", "node_modules"}

# The marker that distinguishes a pytest-scope pyproject from an unrelated one
# (e.g. a lint/format-only config that happens to sit in some dir).
PYTEST_CONFIG_MARKER = "[tool.pytest.ini_options]"

# pytest exit codes we treat specially; everything else is a failure.
EXIT_OK = 0
EXIT_NO_TESTS = 5


def _excluded(path: Path) -> bool:
    return any(part in EXCLUDE_PARTS for part in path.parts)


def discover(root: Path) -> tuple[list[Path], list[tuple[Path, str]]]:
    """Return ``(scopes, near_misses)``.

    A *scope* is a dir with both a pytest-configured ``pyproject.toml`` and a
    ``tests/`` subdir. A *near-miss* is a dir with exactly one of those signals,
    paired with a human reason — a likely half-removed/misconfigured scope that
    must be surfaced (and fail the run) rather than silently ignored.
    """
    pytest_dirs: set[Path] = set()
    for pyproject in root.rglob("pyproject.toml"):
        if _excluded(pyproject):
            continue
        try:
            text = pyproject.read_text(encoding="utf-8")
        except OSError:
            # Unreadable pyproject: don't count it as a pytest scope. If it has a
            # sibling tests/ it will surface below as a near-miss (fail loud),
            # never silently drop.
            continue
        if PYTEST_CONFIG_MARKER in text:
            pytest_dirs.add(pyproject.parent)

    tests_dirs: set[Path] = {
        d.parent for d in root.rglob("tests") if d.is_dir() and not _excluded(d)
    }

    scopes = sorted(pytest_dirs & tests_dirs)
    near_misses: list[tuple[Path, str]] = []
    for d in sorted(pytest_dirs - tests_dirs):
        near_misses.append((d, "pytest-configured pyproject.toml but no tests/ dir"))
    for d in sorted(tests_dirs - pytest_dirs):
        near_misses.append((d, "tests/ dir but no pytest-configured pyproject.toml"))
    return scopes, near_misses


def _rel(path: Path) -> Path:
    base = PLUGIN_ROOT.parent
    return path.relative_to(base) if path.is_relative_to(base) else path


_SKIP_COUNT = re.compile(r"(\d+) skipped")


def run_scope(scope: Path, pytest_args: list[str]) -> tuple[int, int]:
    """Run ``pytest`` in ``scope`` as a subprocess. Returns (exit code, skips).

    Output is teed rather than inherited so the skip count can be read back.
    Skips matter here beyond the usual: several of this plugin's guards are
    conditional on an overlay file that does not exist in the source repo, so
    they `pytest.skip` and the summary said PASS — a guard that never executed
    was indistinguishable from one that passed.
    """
    print(f"\n{'=' * 70}\n>>> {_rel(scope)}\n{'=' * 70}", flush=True)
    # Streamed line-by-line rather than captured and printed at the end. The
    # scopes that build real git worktrees run for minutes, and buffering until
    # completion makes a slow suite indistinguishable from a hung one — which is
    # exactly what a developer watching it needs to be able to tell.
    proc = subprocess.Popen(
        [sys.executable, "-m", "pytest", *pytest_args],
        cwd=scope, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding="utf-8", errors="replace", bufsize=1,
    )
    skipped = 0
    for line in proc.stdout:
        sys.stdout.write(line)
        sys.stdout.flush()
        match = _SKIP_COUNT.search(line)
        if match:
            skipped = int(match.group(1))
    proc.stdout.close()
    return proc.wait(), skipped


# Node's own skip line is `ℹ skipped N`. Do NOT anchor this with `\W`: `ℹ`
# (U+2139) has Unicode category `Ll` — it IS a word character to `re`, so
# `^\W*skipped` misses every real summary line while still matching the plain
# `# skipped` form a fixture would use, i.e. it passes its own tests and fails
# in production.
_NODE_SKIP_COUNT = re.compile(r"^[^a-zA-Z]*skipped\s+(\d+)\s*$", re.MULTILINE)


def discover_node_tests() -> list[Path]:
    """Every `*.test.mjs` under the plugin.

    These ran under NOTHING before this: not the pytest aggregator (it looks for
    a dir with both a pytest-configured pyproject.toml and a tests/ subdir, so a
    `.test.mjs` is not even a near-miss), and not a consuming repo's package
    manager either, since the plugin is not a workspace member. CLAUDE.md told
    the reader to run them by hand, which nobody does.
    """
    return sorted(
        p for p in PLUGIN_ROOT.rglob("*.test.mjs")
        if not _excluded(p)
    )


def node_near_misses() -> list[tuple[Path, str]]:
    """A near-miss when `.mjs` SOURCE exists but no `*.test.mjs` does at all.

    The pytest half fails the run on a half-configured scope; the node half had
    no equivalent, so renaming the single `*.test.mjs` made the glob return
    nothing, dropped the scope out of `results` entirely, and the run still
    printed "All N scope(s) passed" and exited 0. With no CI anywhere in this
    repo that local run is the only gate there is.

    Deliberately narrow: it fires only when EVERY node test has disappeared, not
    per-untested-script, so adding an `.mjs` helper does not manufacture a
    failure.
    """
    scripts = [
        p for p in PLUGIN_ROOT.rglob("*.mjs")
        if not _excluded(p) and not p.name.endswith(".test.mjs")
    ]
    if scripts and not discover_node_tests():
        return [(PLUGIN_ROOT, f"{len(scripts)} .mjs script(s) but no *.test.mjs anywhere")]
    return []


def run_node_tests(files: list[Path]) -> tuple[int, int]:
    """Run every `*.test.mjs` as one `node --test` scope. Returns (exit, skips).

    A MISSING `node` is a FAILURE, not a skip. Files that exist but could not run
    must not look like files that passed — the same rule the pytest half already
    applies to a near-miss scope.
    """
    print(f"\n{'=' * 70}\n>>> node --test ({len(files)} file(s))\n{'=' * 70}", flush=True)
    try:
        proc = subprocess.Popen(
            ["node", "--test", *[str(f) for f in files]],
            cwd=PLUGIN_ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace", bufsize=1,
        )
    except (OSError, ValueError) as exc:
        print(
            f"node is not runnable ({exc}) — {len(files)} .test.mjs file(s) did NOT run",
            file=sys.stderr,
        )
        return 1, 0
    out = []
    for line in proc.stdout:
        sys.stdout.write(line)
        sys.stdout.flush()
        out.append(line)
    proc.stdout.close()
    match = _NODE_SKIP_COUNT.search("".join(out))
    return proc.wait(), int(match.group(1)) if match else 0


def main(argv: list[str]) -> int:
    pytest_args = argv[1:]

    if importlib.util.find_spec("pytest") is None:
        print(
            f"error: pytest is not available under {sys.executable}; "
            "install it (e.g. `python3 -m pip install pytest`) before running the suite.",
            file=sys.stderr,
        )
        return 1

    scopes, near_misses = discover(PLUGIN_ROOT)
    near_misses += node_near_misses()

    # A near-miss is a likely broken/half-removed scope — surface it loudly and
    # fail the run; never let a scope silently disappear into a false green.
    for scope, reason in near_misses:
        print(f"WARNING: {_rel(scope)} looks like a test scope but won't run — {reason}", file=sys.stderr)

    node_test_files = discover_node_tests()

    if not scopes and not node_test_files:
        print("No test scopes found under", PLUGIN_ROOT, file=sys.stderr)
        return 1

    # On a bare full run (no forwarded args) every discovered scope MUST collect
    # tests — it only exists because it has a tests/ dir. Zero collected (exit 5)
    # then means tests were renamed/misnamed out of collection: fail. When args
    # are forwarded (e.g. `-k foo`), exit 5 is expected filtering and stays benign.
    strict_no_tests = not pytest_args

    results: list[tuple[Path, int, int]] = [
        (s, *run_scope(s, pytest_args)) for s in scopes
    ]

    # Forwarded args are pytest's, not node's, so the node scope is skipped when
    # any are present rather than passed arguments it would reject.
    if node_test_files and not pytest_args:
        results.append((PLUGIN_ROOT / "node --test", *run_node_tests(node_test_files)))
    elif node_test_files:
        print(
            f"\nNOTE: {len(node_test_files)} .test.mjs file(s) not run — forwarded "
            "args are pytest-only. Re-run without args to include them.",
            file=sys.stderr,
        )

    # Relaxing the zero-scope guard above to `not scopes and not node_test_files`
    # opens a false green: with pytest discovering nothing AND node skipped for
    # forwarded args, the summary loop never runs, `failed` stays 0, and the run
    # prints "All 0 scope(s) passed" and exits 0. Guard it explicitly.
    if not results:
        print("No scopes ran.", file=sys.stderr)
        return 1

    print(f"\n{'=' * 70}\nSUMMARY ({len(results)} scopes)\n{'=' * 70}", flush=True)
    failed = 0
    total_skipped = 0
    for scope, code, skipped in results:
        total_skipped += skipped
        if code == EXIT_OK:
            label = "PASS"
        elif code == EXIT_NO_TESTS and not strict_no_tests:
            label = "no tests (filtered)"
        elif code == EXIT_NO_TESTS:
            label = "NO TESTS COLLECTED"
            failed += 1
        else:
            label = f"FAIL (exit {code})"
            failed += 1
        # The skip count rides on the same line as the verdict: a reader
        # scanning for "PASS" should not be able to miss that part of the scope
        # opted out of running.
        suffix = f"  ({skipped} skipped)" if skipped else ""
        print(f"  {label:<20} {_rel(scope)}{suffix}")

    problems = failed + len(near_misses)
    if problems:
        parts = []
        if failed:
            parts.append(f"{failed} of {len(results)} scope(s) failed")
        if near_misses:
            parts.append(f"{len(near_misses)} near-miss scope(s) not run")
        print("\n" + "; ".join(parts) + ".", file=sys.stderr)
        return 1
    if total_skipped:
        print(
            f"\nAll {len(results)} scope(s) passed, with {total_skipped} test(s) "
            "SKIPPED — a skipped guard has not run. Check the list above."
        )
    else:
        print(f"\nAll {len(results)} scope(s) passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
