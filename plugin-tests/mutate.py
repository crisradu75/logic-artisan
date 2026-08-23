#!/usr/bin/env python3
"""Mutation-check a batch of fixes: break each one, confirm a test fails, restore.

WHAT IT PROVES, AND WHAT IT DOES NOT. A green suite proves the tests pass, not
that they would catch the defect coming back. This tool closes that gap for the
mutants you write — and ONLY for those. Two commits on one branch in this repo
each said "three mutations checked, all caught" and each shipped a critical the
next review found, because the mutants covered the branch the author was thinking
about and not the branch they got wrong. A clean run here is evidence about the
mutants you thought of. It is not a safety certificate, and it does not replace a
review.

WHY IT FAILS LOUD. An earlier version of this file read any non-zero pytest exit
as "killed". pytest exits non-zero for a missing target, an empty target, a
collection error, a usage error, and an absent pytest — so a batch pointing at a
typo'd path reported every mutant killed and exited 0. A verification tool that
resolves ambiguity into confidence is worse than no tool, so every verdict here
is now driven by evidence of an actual test FAILURE, and anything else is
INCONCLUSIVE and fails the run.

WHY IT WRITES BYTES. The same earlier version paired `read_text` with
`write_text`, whose newline translation rewrote every line ending in an LF file
to CRLF on Windows. This repo pins `cla` to `eol=lf` precisely because
a CRLF shebang (`#!/usr/bin/env bash\\r`) breaks the POSIX launchers — and
`git diff` shows nothing for that change, because the `eol=lf` attribute
normalizes on read. Restores are byte-exact and asserted.

USAGE. Write a batch file — a Python module defining `MUTANTS`, a list of
`(name, path, old, new, targets)`. Batches live in `plugin-tests/mutants/<area>/`,
mirroring `plugin-tests/tests/`. The subject usually stays in the published
plugin while its tests live here, so a batch commonly needs both roots:

    from pathlib import Path
    DEV = Path(__file__).resolve().parents[2]        # <repo>/plugin-tests
    PLUGIN = DEV.parent / ".claude" / "plugins" / "cla"
    HOOKS = PLUGIN / "hooks"
    MUTANTS = [
        ("the git matcher stops case-folding the command name",
         HOOKS / "_dispatch_lib.py",
         r'GIT_CMD = r"\\b(?i:git)(?:\\.(?i:exe|cmd|bat|com|ps1))?"',
         r'GIT_CMD = r"\\bgit(?:\\.(?i:exe|cmd|bat|com|ps1))?"',
         [DEV / "tests" / "hooks"]),
    ]

then run it:

    python3 plugin-tests/mutate.py <batch.py>

`old` must appear EXACTLY ONCE in the file. A missing anchor means that mutant
silently stopped checking anything; an ambiguous one silently mutates a site you
did not mean, and a kill on the wrong site reads exactly like a kill on the right
one. Both are refused before any file is touched.

KEEP `\\n` OUT OF AN ANCHOR. Anchors are matched against the file's raw bytes
(see WHY IT WRITES BYTES above), so on a CRLF checkout — every file in this repo
except the `eol=lf` launchers — a `\\n` in `old` matches nothing and the mutant is
refused as "anchor not found" even though the line is plainly there. Anchor
within a single line, or spell the separator `\\r\\n` and accept that the batch
then only runs on one platform.

VERDICTS. `killed` (pytest exit 1 — a test actually failed), `SURVIVED` (exit 0 —
no test noticed), `INCONCLUSIVE` (any other exit — the run proves nothing, and
the captured pytest output is printed). Exit 0 only when every mutant was killed.

TARGETS. Passed straight to pytest, so a scope dir, a test file, or a
`::`-qualified node all work; pytest finds the scope's `pyproject.toml` by
walking up from the argument. Prefer the narrowest target that could plausibly
catch the mutation — one pytest runs per mutant.
"""

from __future__ import annotations

import importlib.util
import re
import subprocess
import sys
from pathlib import Path

# pytest's exit codes. Only ONE of them is evidence that a test caught the
# mutant; conflating the rest with it is what made the first version of this file
# report success for batches that never ran a test.
EXIT_OK = 0
EXIT_TESTS_FAILED = 1
_PYTEST_EXIT_MEANING = {
    2: "interrupted (often a collection or syntax error — the mutant may have "
       "broken the parse rather than the behaviour)",
    3: "internal error",
    4: "usage error (commonly a target path that does not exist)",
    5: "no tests were collected",
}

_BACKUP_SUFFIX = ".mutate-backup"

# Pin this process's own streams: a batch name or a traceback can carry anything,
# and a run that dies writing its own output to a cp1252 console reports nothing.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except (OSError, ValueError):
            pass


def load_batch(path: Path) -> list[tuple]:
    """Import `path` as a module and return its validated `MUTANTS` list.

    Validation happens HERE, before any file is touched. Unpacking inside the run
    loop meant a malformed entry at position N crashed only after entries 1..N-1
    had already mutated and restored, with no summary and a traceback for output.
    """
    spec = importlib.util.spec_from_file_location("mutation_batch", path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"error: cannot import a batch from {path}")
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except OSError as exc:
        raise SystemExit(f"error: cannot read the batch {path}: {exc}") from exc
    except Exception as exc:  # a syntax error, a bad import, anything the batch does
        raise SystemExit(f"error: the batch {path} failed to load: {exc!r}") from exc

    mutants = getattr(module, "MUTANTS", None)
    if not isinstance(mutants, list) or not mutants:
        raise SystemExit(f"error: {path} defines no non-empty MUTANTS list")

    problems: list[str] = []
    for i, entry in enumerate(mutants):
        if not isinstance(entry, (tuple, list)) or len(entry) != 5:
            problems.append(f"MUTANTS[{i}]: expected a 5-tuple "
                            f"(name, path, old, new, targets), got {entry!r:.80}")
            continue
        name, target_path, old, new, targets = entry
        if not isinstance(old, str) or not isinstance(new, str):
            problems.append(f"MUTANTS[{i}] ({name}): `old` and `new` must be strings")
        elif old == new:
            problems.append(f"MUTANTS[{i}] ({name}): `old` == `new` — this mutant "
                            "changes nothing and would report SURVIVED forever")
        if isinstance(targets, (str, Path)):
            # `[Path(t) for t in targets]` iterates a string CHARACTER by
            # character, producing garbage paths and a pytest usage error, which
            # the old exit-code mapping then reported as a kill.
            problems.append(f"MUTANTS[{i}] ({name}): `targets` must be a LIST of "
                            "paths, not a single path")
        elif not targets:
            problems.append(f"MUTANTS[{i}] ({name}): `targets` is empty")
    if problems:
        raise SystemExit("error: malformed batch:\n  " + "\n  ".join(problems))
    return mutants


def preflight(mutants: list[tuple]) -> None:
    """Refuse to start unless every mutant could actually prove something.

    Every check here exists because its absence produced a FALSE KILL: no pytest
    at all, a target that does not exist, an anchor that no longer matches, an
    anchor that matches twice. Each of those makes pytest exit non-zero for a
    reason unrelated to the mutation.
    """
    problems: list[str] = []

    if importlib.util.find_spec("pytest") is None:
        problems.append(f"pytest is not available under {sys.executable} — every "
                        "run would exit non-zero for that reason alone")

    stale = sorted({
        str(Path(str(p)) .with_name(Path(str(p)).name + _BACKUP_SUFFIX))
        for _, p, _, _, _ in mutants
        if Path(str(p)).with_name(Path(str(p)).name + _BACKUP_SUFFIX).exists()
    })
    if stale:
        problems.append(
            "a previous run did not finish — these backups still exist, and the "
            "source beside them may still be mutated. Restore each by hand "
            "(`mv <f>" + _BACKUP_SUFFIX + " <f>`) before re-running:\n    "
            + "\n    ".join(stale))

    for name, path, old, _new, targets in mutants:
        path = Path(str(path))
        if not path.is_file():
            problems.append(f"{name}: no such file: {path}")
            continue
        try:
            text = path.read_bytes().decode("utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            problems.append(f"{name}: cannot read {path} as UTF-8: {exc}")
            continue
        hits = text.count(old)
        if hits == 0:
            problems.append(f"{name}: anchor not found in {path.name} — this "
                            "mutant checks nothing")
        elif hits > 1:
            problems.append(f"{name}: anchor appears {hits}x in {path.name} — only "
                            "the first would be mutated, so a kill might belong to "
                            "a site you did not mean. Anchor on something unique.")
        for target in targets:
            # A `::`-qualified node id is not a path; check the file part only.
            probe = Path(str(target).split("::")[0])
            if not probe.exists():
                problems.append(f"{name}: target does not exist: {target}")

    if problems:
        raise SystemExit("error: preflight failed, nothing was mutated:\n  "
                         + "\n  ".join(problems))


def uncommitted(paths: list[Path]) -> list[str]:
    """Which of `paths` git reports as dirty. Empty list when git is unusable.

    A crash or a hard kill mid-run leaves the mutant on disk (the `finally` below
    cannot run for a SIGKILL). If the file also held uncommitted work, that work
    is unrecoverable — `git checkout` restores the committed version, not yours.
    Advisory rather than blocking: a dirty tree is the normal state mid-change,
    and this tool's whole purpose is checking a fix you have not committed yet.
    """
    try:
        proc = subprocess.run(
            ["git", "status", "--porcelain", "--", *[str(p) for p in paths]],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    if proc.returncode != 0:
        return []
    return [line[3:] for line in proc.stdout.splitlines() if line.strip()]


_RAN_RE = re.compile(r"^\s*\d+\s+(?:passed|failed)\b", re.MULTILINE)
# A per-TEST error line carries a `::<nodeid>` suffix — the test was selected and
# its setup ran. A COLLECTION error names only the file. That suffix is the whole
# discriminator; the word "error" alone is not.
_TEST_LEVEL_ERROR_RE = re.compile(r"^ERROR\s+.*::", re.MULTILINE)


def _a_test_actually_ran(output: str) -> bool:
    """True when at least one test was selected and executed.

    `killed` must mean "a test failed", not "pytest exited 1". With `-x`, a
    collection error exits 1 having run nothing — pytest's own exit-2 meaning is
    lost — so the exit code alone cannot tell a real kill from a broken target
    list. Measured: two scopes shipping same-named modules collect nothing and
    summarise as `1 error`.

    But `1 error` is ALSO what a fixture blowing up during setup prints, at exit
    1, having genuinely run a test — and a mutation that breaks module
    construction lands there constantly. A first version of this predicate keyed
    on the count line alone and so reported those real kills as INCONCLUSIVE:
    correcting the false-`killed` path had opened a false-`INCONCLUSIVE` one, the
    second branch of exactly the shape CLAUDE.md warns a fix always has.

    So discriminate on WHERE the error is attributed, not on the word: a
    per-test error carries a `::<nodeid>` suffix, a collection error names only
    the file. That single check is the whole discriminator.

    An earlier version also looked for pytest's `Interrupted: N error(s) during
    collection` banner. That is gone: whether the banner is printed varies with
    how the target is spelled, so it could never be relied on — and mutation
    showed it was doing nothing, surviving as dead weight while the `::` check
    handled every case. A redundant guard whose docstring calls itself
    load-bearing is worse than no guard, because it draws attention away from
    the one that is.
    """
    if _RAN_RE.search(output):
        return True
    return bool(_TEST_LEVEL_ERROR_RE.search(output))


def run_pytest(targets: list[Path]) -> tuple[int, str]:
    """Run pytest over `targets`. Returns `(exit code, combined output)`.

    `-x` because the batch only needs to know WHETHER the mutant was caught; the
    first failure answers that, and a mutant that breaks fifty tests should not
    cost fifty tests' worth of runtime.

    The output is returned rather than discarded: it is the only thing that can
    explain an INCONCLUSIVE verdict, and throwing it away is what made the first
    version's false kills invisible.

    No `cwd=` is set. pytest resolves rootdir and the ini-file by walking UP from
    its arguments, not from the working directory, so a scope's `pyproject.toml`
    applies either way — an earlier version set a derived cwd and justified it
    with a mechanism that measurement did not support, while breaking relative
    targets.
    """
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-x", *[str(t) for t in targets]],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    return proc.returncode, proc.stdout + proc.stderr


def check(mutants: list[tuple]) -> int:
    dirty = uncommitted([Path(str(p)) for _, p, _, _, _ in mutants])
    if dirty:
        print("note: these target files have uncommitted changes. An interrupted "
              "run cannot restore them:", flush=True)
        for d in dirty:
            print(f"  {d}", flush=True)

    failures: list[str] = []
    for i, (name, path, old, new, targets) in enumerate(mutants, 1):
        path = Path(str(path))
        print(f"[{i}/{len(mutants)}] {name}", flush=True)
        original = path.read_bytes()
        backup = path.with_name(path.name + _BACKUP_SUFFIX)
        # On disk, not just in memory: if this process is hard-killed, the
        # original still exists and preflight will refuse to run again until it
        # has been put back.
        backup.write_bytes(original)
        try:
            mutated = original.decode("utf-8").replace(old, new, 1)
            path.write_bytes(mutated.encode("utf-8"))
            code, output = run_pytest([Path(str(t)) for t in targets])
        finally:
            path.write_bytes(original)

        if path.read_bytes() != original:
            # Never observed, but a restore that cannot prove it restored is the
            # same defect class as a check that cannot prove it checked.
            print(f"  RESTORE FAILED — {path} does NOT match its original. "
                  f"Recover from {backup}", flush=True)
            return 1
        backup.unlink()

        if code == EXIT_TESTS_FAILED and _a_test_actually_ran(output):
            print("  killed", flush=True)
        elif code == EXIT_TESTS_FAILED:
            # Exit 1 with nothing collected. `-x` turns a collection ERROR into a
            # "failure", so a target list that cannot even be imported — say two
            # same-named modules that shadow each other — reads as exit 1 and
            # would otherwise be reported `killed`. That is this tool manufacturing the confidence
            # it exists to supply.
            print("  INCONCLUSIVE — pytest exited 1 but no test ran "
                  "(collection error, or every test deselected)", flush=True)
            for line in output.strip().splitlines()[-12:]:
                print(f"      {line}", flush=True)
            failures.append(f"INCONCLUSIVE (nothing collected): {name}")
        elif code == EXIT_OK:
            print("  SURVIVED — no test noticed this change", flush=True)
            failures.append(f"SURVIVED: {name}")
        else:
            why = _PYTEST_EXIT_MEANING.get(code, "unrecognized pytest exit")
            print(f"  INCONCLUSIVE — pytest exited {code}: {why}", flush=True)
            for line in output.strip().splitlines()[-12:]:
                print(f"      {line}", flush=True)
            failures.append(f"INCONCLUSIVE (pytest exit {code}): {name}")

    print()
    if failures:
        print(f"{len(failures)} of {len(mutants)} mutant(s) did not produce a test "
              f"failure:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print(f"All {len(mutants)} mutant(s) killed.")
    return 0


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(f"usage: {Path(argv[0]).name} <batch.py>", file=sys.stderr)
        print("  A batch is a Python module defining MUTANTS, a list of\n"
              "  (name, path, old, new, targets). See this file's docstring.",
              file=sys.stderr)
        return 2
    mutants = load_batch(Path(argv[1]).resolve())
    preflight(mutants)
    return check(mutants)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
