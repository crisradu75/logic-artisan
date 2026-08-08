#!/usr/bin/env python3
"""Mutation-check a batch of fixes: break each one, confirm a test fails, restore.

WHY THIS EXISTS. A green suite proves the tests pass, not that they would catch
the defect coming back. The gap is invisible and this repo has hit it repeatedly:
a helper nobody called, a parse test whose setup never reached the defective
block, a fixture that rounded its own argument, a corpus that never exercised the
branch its rule lived on. Each looked tested. Each survived deletion of the thing
it was supposed to test.

It also exists because the batch was hand-written three separate times in one
session's scratchpad — the same apply/run/restore loop, retyped, with the restore
step re-derived each time. A restore that runs only on the happy path leaves the
tree mutated, which is a far worse outcome than not checking at all; here it is in
a `finally`, once.

USAGE. Write a batch file — a Python module defining `MUTANTS`, a list of
`(name, path, old, new, targets)`:

    from pathlib import Path
    HOOKS = Path("C:/code/logic-artisan/.claude/plugins/cla/hooks")
    MUTANTS = [
        ("the args fallback comes back",
         HOOKS / "warn-lint-on-edit.py",
         "if not raw_exts or not binary or not args:",
         "if not raw_exts or not binary:",
         [HOOKS / "tests"]),
    ]

then run it:

    python3 .claude/plugins/cla/mutate.py batch.py

`old` must appear in the file (a missing anchor is reported as a failure, never
skipped silently — a batch whose anchors have drifted is a batch that checks
nothing). Only the FIRST occurrence is replaced, so anchor on something unique.

EXIT CODE. 0 when every mutant was killed; 1 when any survived or any anchor was
missing. A survivor names a fix that no test would catch the regression of.

TARGETS. Each entry's `targets` is a list of paths passed straight to pytest, so
a scope dir, a single test file, or a `::`-qualified node all work. Prefer the
narrowest target that could plausibly catch the mutation — the batch runs one
pytest per mutant, so a whole-repo target multiplies wall-clock by the batch size
for no extra signal.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

# Pin this process's own streams: a mutated test's output can carry anything, and
# a run that dies writing a traceback to a cp1252 console reports nothing at all.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except (OSError, ValueError):
            pass


def load_batch(path: Path) -> list[tuple]:
    """Import `path` as a module and return its `MUTANTS` list."""
    spec = importlib.util.spec_from_file_location("mutation_batch", path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"error: cannot import a batch from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    mutants = getattr(module, "MUTANTS", None)
    if not isinstance(mutants, list) or not mutants:
        raise SystemExit(f"error: {path} defines no non-empty MUTANTS list")
    return mutants


def run_pytest(targets: list[Path]) -> int:
    """Run pytest over `targets`, quiet and fail-fast.

    `-x` because the batch only needs to know WHETHER the mutant was caught; the
    first failure answers that, and a mutant that breaks fifty tests should not
    cost fifty tests' worth of runtime.

    cwd is the scope root (the target's own dir, or its parent for a file) so the
    scope's `pyproject.toml` — its `pythonpath`, its `testpaths` — actually
    applies. Running from elsewhere silently collects nothing in a repo whose
    scopes are deliberately isolated.
    """
    first = targets[0]
    cwd = first.parent.parent if first.is_file() else first.parent
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-x", *[str(t) for t in targets]],
        cwd=str(cwd), capture_output=True,
        text=True, encoding="utf-8", errors="replace",
    )
    return proc.returncode


def check(mutants: list[tuple]) -> int:
    survivors: list[str] = []
    for name, path, old, new, targets in mutants:
        path = Path(path)
        original = path.read_text(encoding="utf-8")
        if old not in original:
            # NOT a skip. An anchor that no longer matches means this mutant
            # silently stopped checking anything, which is the exact failure
            # shape the tool exists to surface.
            print(f"  ANCHOR MISSING  {name}", flush=True)
            survivors.append(f"{name} (anchor missing in {path.name})")
            continue
        path.write_text(original.replace(old, new, 1), encoding="utf-8")
        try:
            code = run_pytest([Path(t) for t in targets])
        finally:
            # Unconditional. A batch that leaves the tree mutated after a crash
            # or a Ctrl-C is worse than one that never ran.
            path.write_text(original, encoding="utf-8")
        if code == 0:
            print(f"  SURVIVED        {name}", flush=True)
            survivors.append(name)
        else:
            print(f"  killed          {name}", flush=True)

    print()
    if survivors:
        print(f"{len(survivors)} of {len(mutants)} mutant(s) SURVIVED — no test catches:")
        for s in survivors:
            print(f"  - {s}")
        return 1
    print(f"All {len(mutants)} mutant(s) killed.")
    return 0


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(f"usage: {Path(argv[0]).name} <batch.py>", file=sys.stderr)
        print(__doc__.split("USAGE.")[1].split("EXIT CODE.")[0].strip(), file=sys.stderr)
        return 2
    return check(load_batch(Path(argv[1]).resolve()))


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
