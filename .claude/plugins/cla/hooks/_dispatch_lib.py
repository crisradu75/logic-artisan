#!/usr/bin/env python3
"""Shared helpers for the PreToolUse dispatcher scripts, and the hooks package's
shared git-command-matching library.

TWO responsibilities, deliberately in one file. (1) It runs several sibling hook
scripts' `main()` in-process (one Python interpreter instead of one per hook) by
importing each as a standalone module — the same technique
.claude/plugins/cla/hooks/tests/ already uses — and temporarily redirecting
stdin/stdout/stderr around each call. The sibling hook files are never
modified by this module; it only orchestrates them. (2) It also HOSTS
`strip_quoted_spans` / `GIT_GLOBAL_OPTS`, which four leaf git hooks import.
So the relationship with those hooks is bidirectional: this module loads them,
and they import from it. Consequence worth holding onto: keep this module
import-cheap and side-effect-free, because a failure here takes out both roles
at once.

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
import re
import subprocess
import sys
import traceback
from pathlib import Path
from types import ModuleType

_HOOKS_DIR = Path(__file__).resolve().parent


# --- Git command-line matching helpers --------------------------------------
# Shared by block-direct-push-to-main.py, warn-branch-base.py,
# warn-stray-scratch-artifact.py, and guard-worktree-isolation.py. Previously
# each of those four files carried its own literal copy of this pattern (three
# linked only by a "mirrors guard-worktree-isolation.py" comment) — a bug fixed
# in one copy could silently persist in the other three, and did: a long
# global option with a space-separated (non-`=`) value (`git --work-tree
# <path> push origin main`) bypassed all of them, and a quoted `-c`/`-C` value
# containing a space (`git -C "/path with space" checkout -b x`) bypassed the
# two hooks that didn't call `strip_quoted_spans` before matching. One
# definition, one fix site closes both classes at once and keeps them closed.


def strip_quoted_spans(cmd: str) -> str:
    """Replaces the contents of every quoted/backtick span with same-length,
    non-whitespace placeholder characters (the quote delimiters themselves are
    left in place), so a matcher below doesn't trip on a `git commit` mentioned
    inside an echoed string or a commit message, AND so a global option's quoted
    value (`-C "/path with space"`) becomes a single whitespace-free token
    before `GIT_GLOBAL_OPTS` tries to match it — the value-consuming
    alternatives below all use `\\S+`, which cannot span an un-stripped
    internal space on its own.

    Length-preserving is deliberate, not incidental: it's what lets a caller
    that captures a match GROUP against the scanned string (e.g. a branch
    name) re-slice the SAME start/end offsets out of the original, unscanned
    command to recover the real text — a naive collapse-to-`''` would shift
    every later offset and silently return the placeholder instead of the
    real value for anything captured after the first quoted span. Note the
    re-sliced text still carries its surrounding quote characters, so callers
    strip them (`.strip("'\\"")`) before use.

    Scope, stated precisely so nobody assumes more than it does:

    - NOT handled — heredoc bodies. Those are unquoted text, so a script
      written via `cat <<'EOF' … git push origin main … EOF` still matches and
      a block hook will fire on it. This is the most likely real-world false
      positive of the git hooks; it is accepted, not solved.
    - NOT handled — escaped or nested quotes (`\\'`, `"a 'b' c"` interactions).
    - INTENTIONALLY matches shell semantics for a mid-word apostrophe:
      `echo don't && git push origin main && echo won't` collapses the span
      between the two apostrophes, so the `git push` disappears from the
      scanned string and the hook allows it. That is CORRECT — bash reads the
      same span as one single-quoted literal and never runs the push. Do not
      "fix" this by requiring quotes to sit at token boundaries; that would
      make the hooks fire on commands the shell would not execute."""

    def _placeholder(match: re.Match[str]) -> str:
        span = match.group(0)
        return span[0] + "#" * (len(span) - 2) + span[-1]

    stripped = re.sub(r"'[^']*'", _placeholder, cmd)
    stripped = re.sub(r'"[^"]*"', _placeholder, stripped)
    stripped = re.sub(r"`[^`]*`", _placeholder, stripped)
    return stripped


# git GLOBAL options that may sit between `git` and the subcommand — consumed
# so `git -c core.x=y commit`, `git -C /path checkout`, `git --work-tree /path
# push origin main` are not a bypass. `-c KEY=VAL` / `-C PATH` take a
# following value token (bare, or — once `strip_quoted_spans` has run — a
# same-length `#`-filled quoted token such as `"################"`, which is
# whitespace-free and so matches `\S+` as one token). A NAMED, closed set of long options that also
# take their value as a separate space-delimited token (`--git-dir`,
# `--work-tree`, `--namespace`, `--super-prefix`) get the same optional
# space-value treatment; every other short/long flag is a single token
# (`--long[=val]` only, no bare-space form). The named-option list is
# deliberately closed rather than "any --long-opt may take a following
# value" — a blanket rule risks the matcher swallowing the real subcommand
# token whenever a value-less flag (`--bare`, `--no-pager`, `--paginate`) is
# immediately followed by it. Best-effort, not an exhaustive git-argument
# parser: an option shape outside this list, or one this hasn't been tested
# against, can still slip through — see each hook's own docstring for its
# specific detection scope.
_GIT_GLOBAL_VALUE_OPTS = r"(?:git-dir|work-tree|namespace|super-prefix)"
GIT_GLOBAL_OPTS = (
    r"(?:"  # outer repetition group — zero or more options, each followed by whitespace
    r"(?:"  # inner alternation — exactly one option-shape per repetition
    r"(?:-[cC]\s+\S+)"
    r"|(?:--" + _GIT_GLOBAL_VALUE_OPTS + r"\b(?:=\S+|\s+\S+)?)"
    r"|(?:-[A-Za-z])"
    r"|(?:--[A-Za-z][\w-]*(?:=\S+)?)"
    r")"
    r"\s+"
    r")*"
)


_BASE_BRANCH_CACHE: dict[str | None, str] = {}
_BASE_BRANCH_FALLBACK = "master"


def default_base_branch(cwd: str | None = None) -> str:
    """Resolve THIS repo's base branch instead of assuming one.

    The harness previously hardcoded `master` throughout. That is not portable —
    and it is not even correct for every repo that ships the harness: a repo
    whose default is `main` has no `master` ref at all, so a hardcoded
    `git rev-list master..HEAD` fails with `unknown revision` rather than
    producing a wrong answer quietly.

    Resolution order, most authoritative first:
      1. `refs/remotes/origin/HEAD` — what the remote itself reports as default
         — but only once its target is VERIFIED to exist. That ref is a
         clone-time cache git never auto-refreshes, and `symbolic-ref` exits 0
         on a dangling symref, so after an upstream `master`→`main` rename it
         happily names a ref that is gone. Trusting it unverified reintroduced
         exactly the failure described above: in a `main`-default repo it
         returned `master`, and the caller's `git rev-list master..HEAD` then
         died with `unknown revision`.
      2. An existing local or remote `main`, then `master`. `main` is probed
         first because a repo carrying BOTH is nearly always one that renamed
         to `main` and kept `master` as a stale leftover.
      3. `master`, preserving the harness's historical assumption for a repo
         with no remote and no conventional branch yet — announced on stderr,
         because this arm cannot tell "this repo genuinely uses master" apart
         from "git is unusable and I guessed", and the sibling hooks all say so
         when they degrade.

    Cached per cwd: hook processes are short-lived, but several call sites may
    ask within one run and this shells out to git.
    """
    if cwd in _BASE_BRANCH_CACHE:
        return _BASE_BRANCH_CACHE[cwd]

    def _git(args: list[str]) -> str | None:
        try:
            r = subprocess.run(
                ["git", *(["-C", cwd] if cwd else []), *args],
                capture_output=True, text=True, timeout=5,
            )
        except (OSError, subprocess.SubprocessError):
            return None
        return (r.stdout or "").strip() if r.returncode == 0 else None

    resolved = None
    head_ref = _git(["symbolic-ref", "--quiet", "refs/remotes/origin/HEAD"])
    if head_ref and "/" in head_ref:
        candidate = head_ref.rsplit("/", 1)[-1] or None
        # `HEAD` as the last segment means the symref points at itself or at
        # something unusable — never a branch name.
        if candidate and candidate != "HEAD" and _git(
            ["rev-parse", "--verify", "--quiet", head_ref]
        ):
            resolved = candidate
    if resolved is None:
        for candidate in ("main", "master"):
            for ref in (f"refs/heads/{candidate}", f"refs/remotes/origin/{candidate}"):
                if _git(["rev-parse", "--verify", "--quiet", ref]):
                    resolved = candidate
                    break
            if resolved:
                break

    if resolved is None:
        print(
            f"[cla] warn: could not resolve this repo's base branch (no usable "
            f"origin/HEAD, no main, no master) — falling back to "
            f"'{_BASE_BRANCH_FALLBACK}'. A command built on it may fail with "
            f"'unknown revision'.",
            file=sys.stderr,
        )
        resolved = _BASE_BRANCH_FALLBACK
    _BASE_BRANCH_CACHE[cwd] = resolved
    return resolved


def ensure_hooks_dir_importable() -> None:
    """Put the hooks dir on `sys.path` if it isn't already.

    Several hook files do `from _dispatch_lib import ...` at module level. That
    import resolves through `sys.path` — `spec_from_file_location` locates the
    HOOK by path but does nothing for the hook's OWN imports. Without this, the
    hooks work only by accident: `hooks.json` happens to invoke the dispatcher
    as a standalone script living in this dir, so CPython sets `sys.path[0]` to
    it. That is a property of how the dispatcher is launched, not an invariant —
    it evaporates under `PYTHONSAFEPATH=1` / `python -I` / `python -P`, or under
    any future caller that imports `load_hook` from a differently-launched
    process. Making it explicit here means the guarantee holds by construction
    rather than by luck, which matters because the failure mode is a guard that
    silently doesn't run."""
    hooks_dir = str(_HOOKS_DIR)
    if hooks_dir not in sys.path:
        sys.path.insert(0, hooks_dir)


def load_hook(filename: str) -> ModuleType:
    """Load a sibling hook file as a fresh module (not cached in sys.modules)."""
    ensure_hooks_dir_importable()
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
