#!/usr/bin/env python3
"""Shared helpers for the PreToolUse dispatcher scripts.

Runs several sibling hook scripts' `main()` in-process (one Python interpreter
instead of one per hook) by importing each as a standalone module — the same
technique .claude/plugins/cla/hooks/tests/ already uses — and temporarily redirecting
stdin/stdout/stderr around each call. The sibling hook files are never
modified by this module; it only orchestrates them.

A hook that crashes (fails to load, or raises out of `main()`) is still
treated as fail-open — a guard must never wedge the workflow — but the
dispatcher must not go silent about it and must not let one broken sibling
take out the ones after it in the list. `run_hook_file()` isolates a load
failure to just that one hook, and callers should track `HookResult.errored`
across a run and exit non-zero-non-2 if any hook errored, so Claude Code's
`<hook> hook error` transcript notice fires and the full diagnostic reaches
the debug log — exit 0 discards stderr entirely per the documented PreToolUse
hook contract, which would otherwise make a crash in a hook like
guard-worktree-isolation.py or block-worktree-path-escape.py invisible.
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import sys
import traceback
from pathlib import Path
from types import ModuleType

_HOOKS_DIR = Path(__file__).resolve().parent


def load_hook(filename: str) -> ModuleType:
    """Load a sibling hook file as a fresh module (not cached in sys.modules)."""
    path = _HOOKS_DIR / filename
    module_name = path.stem.replace("-", "_")
    spec = importlib.util.spec_from_file_location(module_name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class HookResult:
    __slots__ = ("code", "stdout", "stderr", "errored")

    def __init__(self, code: int, stdout: str, stderr: str, errored: bool = False) -> None:
        self.code = code
        self.stdout = stdout
        self.stderr = stderr
        # True iff this hook failed to load or run as intended (as opposed to
        # legitimately deciding to allow/warn) — see module docstring for why
        # dispatchers must surface this loudly rather than swallowing it.
        self.errored = errored


def run_hook(mod: ModuleType, stdin_text: str, argv: list[str] | None = None) -> HookResult:
    """Call `mod.main()` (or `mod.main(argv)` when argv is not None) with stdin
    set to `stdin_text`, capturing stdout/stderr. A hook that raises is treated
    as fail-open (code 0) but flagged `errored=True` with a full traceback in
    stderr, so the caller can make the failure visible instead of silently
    discarding it.
    """
    out, err = io.StringIO(), io.StringIO()
    errored = False
    old_stdin = sys.stdin
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            sys.stdin = io.StringIO(stdin_text)
            try:
                code = mod.main() if argv is None else mod.main(argv)
            except SystemExit as e:
                if e.code is None or isinstance(e.code, int):
                    # `sys.exit()` (bare) or `sys.exit(<int>)` — both intentional,
                    # not an error. `None` conventionally means success (code 0).
                    code = e.code if isinstance(e.code, int) else 0
                else:
                    code = 0
                    errored = True
                    print(f"[dispatch] {mod.__name__} called sys.exit({e.code!r}) — non-int exit, treating as fail-open", file=err)
            except Exception:  # noqa: BLE001 - fail open, but loudly (see module docstring)
                print(f"[dispatch] {mod.__name__} raised an unexpected exception — failing open:", file=err)
                traceback.print_exc(file=err)
                code, errored = 0, True
    finally:
        sys.stdin = old_stdin
    return HookResult(code or 0, out.getvalue(), err.getvalue(), errored=errored)


def run_hook_file(filename: str, stdin_text: str, argv: list[str] | None = None) -> HookResult:
    """Load a sibling hook file and run it, isolating a LOAD failure (bad edit,
    syntax error, file lock) to just this one hook — so it can't prevent the
    dispatcher from still evaluating the rest of the hooks in its list, the
    way an independent per-hook process always could."""
    try:
        mod = load_hook(filename)
    except Exception:
        err = io.StringIO()
        print(f"[dispatch] failed to load {filename} — skipping this hook, continuing with the rest:", file=err)
        traceback.print_exc(file=err)
        return HookResult(0, "", err.getvalue(), errored=True)
    return run_hook(mod, stdin_text, argv=argv)
