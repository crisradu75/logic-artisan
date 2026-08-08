#!/usr/bin/env python3
"""Shared helpers for the PreToolUse dispatcher scripts, and the hooks package's
shared git-command-matching library.

TWO responsibilities, deliberately in one file. (1) It runs several sibling hook
scripts' `main()` in-process (one Python interpreter instead of one per hook) by
importing each as a standalone module — the same technique
.claude/plugins/cla/hooks/tests/ already uses — and temporarily redirecting
stdin/stdout/stderr around each call. The sibling hook files are never
modified by this module; it only orchestrates them. (2) It also HOSTS
`strip_quoted_spans` / `GIT_GLOBAL_OPTS`, which six leaf git hooks import.
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
the debug log — exit 0 keeps stderr out of the transcript entirely (it reaches
the debug log only, where Claude never sees it) per the documented PreToolUse
hook contract, which would otherwise make a crash in a hook like
guard-worktree-isolation.py or block-worktree-path-escape.py invisible.
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
import re
import subprocess
import sys
import time
import traceback
from pathlib import Path
from types import ModuleType

_HOOKS_DIR = Path(__file__).resolve().parent


# --- Handler budget ---------------------------------------------------------
# Claude Code kills a hook handler at the `timeout` declared for it in
# hooks.json, and a killed handler is enforcement that did not run — the worst
# possible outcome, because from the outside it is indistinguishable from a
# guard that ran and allowed the call.
#
# Two things keep the dispatchers inside that ceiling:
#   1. `HOOK_WORST_CASE_SECONDS` below, which states what each hook can spend
#      in subprocesses and is asserted in aggregate by the wiring test.
#   2. `Deadline` below, which the dispatchers consult before starting each
#      ADVISORY hook. When too little budget is left for THAT hook's worst
#      case, it is skipped and SAID SO rather than being silently lost to a
#      kill mid-run.
#
# Only advisory hooks are ever skipped. An enforcing hook always runs, even
# past the budget — a late block still blocks, whereas a dropped block is a
# silent failure. Losing a warning is the acceptable half of that trade.
#
# HANDLER_TIMEOUT_SECONDS mirrors the `timeout` in hooks.json; the wiring test
# asserts the two agree, so raising one without the other fails the suite.
#
# 15s, not 10s. The ceiling has to be derived from what the guards actually need,
# not picked first and the guards starved to fit it. Squeezing the rev-parse calls to
# 2s did make the sum fit 10s — and made a BLOCKING guard fail open under load,
# because a `rev-parse` on a busy Windows machine can genuinely exceed 2s once
# process-spawn cost is counted. A guard that silently allows the thing it exists
# to block is far worse than a rare slow handler: the ceiling only costs anything
# in the pathological case (a wedged git), and 15s buys correctness there that
# 10s did not.
HANDLER_TIMEOUT_SECONDS = 15.0

# Left for the dispatcher's own compose/print work after the last hook returns,
# plus interpreter startup before the first one begins. Both fall outside the
# window `Deadline` can observe.
_BUDGET_RESERVE_SECONDS = 1.5

# Worst-case wall time each dispatched hook can spend in subprocesses, as
# (call sites on the hot path) x (that hook's own timeout constant). A hook that
# spawns nothing is 0.0.
#
# Two things consume this table:
#   - the dispatchers, which admit an ADVISORY hook only when this much budget
#     is still left. Gating on `expired()` alone was not enough: it let a hook
#     with a 9s worst case start with 0.1s remaining, so the handler was killed
#     anyway — the budget check has to be sized against the hook about to run,
#     not merely against zero.
#   - `test_hooks_wiring.py`, which asserts each dispatcher's ENFORCING hooks
#     sum to no more than the budget. Enforcing hooks are never skipped, so if
#     their sum alone exceeds the ceiling then no admission policy can rescue
#     them; the only fixes are fewer calls or shorter timeouts. Keeping the
#     numbers here rather than deriving them means a hook that gains a call site
#     must update this table, and the test fails until the sum still fits.
# The arithmetic is stated PER ENTRY, not per group. Grouped comments ("one
# local git call each") drifted silently as hooks gained call sites, and the
# tests only check presence and the sum — never an individual figure — so a
# wrong entry made the budget test look rigorous while proving nothing.
HOOK_WORST_CASE_SECONDS: dict[str, float] = {
    # Pure text inspection — no subprocess at all.
    "block-cd-in-bash.py": 0.0,
    "ask-destructive-git.py": 0.0,
    "block-unsafe-recursive-delete.py": 0.0,
    "warn-comment-dates.py": 0.0,
    "block-dated-stamps-in-prose.py": 0.0,
    "warn-smoke-test-drift.py": 0.0,
    # 1 x _current_branch(3s) for the shapes that actually occur. Memoised per
    # cwd, which bounds the common case: several pushes sharing one directory
    # resolve the branch once.
    #
    # KNOWN GAP, stated rather than implied: the cache key IS the cwd, and each
    # push may carry its own `-C`/`--work-tree`, so distinct directories are
    # distinct keys. `git -C /a push origin HEAD && git -C /b push origin HEAD
    # && git -C /c push origin HEAD` really does spawn three `rev-parse` calls
    # (verified) — 9s, not 3.0. `_branch_for` can also try two candidates for a
    # single push (composed relative path, then session cwd), doubling again.
    # So this entry is the realistic bound, not a proven ceiling.
    #
    # Left at 3.0 deliberately: raising it to a true worst case would put the
    # enforcing sum over the budget and fail `test_hooks_wiring.py`, and the fix
    # for that is to make the hook cheaper (resolve at most one branch per
    # command), not to raise the handler timeout. Tracked here so the next
    # person to touch this hook sees the constraint instead of rediscovering it.
    "block-direct-push-to-main.py": 3.0,
    # 1 x _git_email(3s).
    "ask-git-identity.py": 3.0,
    # 2 x _run_git(3s): combined `rev-parse` + one conditional checkout lookup.
    "guard-worktree-isolation.py": 6.0,
    # 2 x _run_git(3s): combined `rev-parse` + `--show-toplevel`.
    "block-worktree-path-escape.py": 6.0,
    # 1 x `git status --porcelain`(4s) — walks the working tree, so it gets more
    # than the `rev-parse` hooks.
    "warn-stray-scratch-artifact.py": 4.0,
    # 1 x `rev-parse`(3s) + default_base_branch(), which is up to 3 spawns at 2s.
    # This hook cannot avoid resolving the base branch — comparing against it is
    # the hook's entire job — so unlike the two hooks that only wanted the name
    # for a MESSAGE, the cost is charged rather than removed.
    "warn-branch-base.py": 9.0,
    # 2 x _gh(4s): `pr view` then `pr list` on the explicit-PR-number path. The
    # only hook that leaves the machine, and the reason it stays advisory. Its
    # own docstring is the authority on the call count; the previous entry
    # described a different (cheaper) branch of the same function.
    "warn-stacked-pr-merge.py": 8.0,
}


class Deadline:
    """How much of the hooks.json handler timeout is left.

    Constructed at dispatcher entry, so `remaining()` already excludes the time
    spent in hooks that ran before the check.
    """

    __slots__ = ("_start", "_budget")

    def __init__(self, budget_seconds: float | None = None) -> None:
        self._start = time.monotonic()
        if budget_seconds is None:
            budget_seconds = HANDLER_TIMEOUT_SECONDS - _BUDGET_RESERVE_SECONDS
        self._budget = budget_seconds

    def remaining(self) -> float:
        return self._budget - (time.monotonic() - self._start)

    def expired(self) -> bool:
        return self.remaining() <= 0.0

    def has_room(self, cost_seconds: float) -> bool:
        """True when a hook whose worst case is `cost_seconds` can still finish.

        A zero-cost hook always has room: it spawns nothing, so it cannot
        overrun the handler however little budget is left.
        """
        return self.remaining() >= cost_seconds


# --- Output size ------------------------------------------------------------
# Claude Code caps a hook's output at 10,000 characters; past that it writes
# the payload to a file and hands Claude a path plus a preview. For a warn hook
# that is a silent downgrade — the feedback these hooks exist to deliver stops
# being in front of Claude and becomes a file it may never open. Several leaf
# hooks truncate by ITEM count (`hits[:5]` in block-dated-stamps-in-prose.py)
# but no item is bounded in LENGTH, and the dispatchers then concatenate every
# hook's output, so the only place the total can be enforced is here at the join.

HOOK_OUTPUT_CHAR_LIMIT = 10_000


def clamp_output(text: str, limit: int = HOOK_OUTPUT_CHAR_LIMIT) -> str:
    """Truncate `text` to `limit` characters, saying so in the space it keeps.

    The notice is part of the retained budget, not added on top of it, so the
    return value is always <= `limit`. When `limit` is too small to hold even
    the notice, the text is truncated bare rather than overshooting — the size
    guarantee is the one thing this function must not break.
    """
    limit = max(0, limit)
    if len(text) <= limit:
        return text
    notice = (
        f"\n[dispatch] … truncated: {len(text)} characters of hook output "
        f"exceeded the {limit}-character cap Claude Code applies. Re-run the "
        f"specific check directly to see the rest.\n"
    )
    keep = max(0, limit - len(notice))
    if keep == 0:
        # Pathological `limit`; a bare truncation still beats overshooting.
        return text[:limit]
    return text[:keep] + notice


def fit_json_payload(build, text: str, limit: int = HOOK_OUTPUT_CHAR_LIMIT) -> str:
    """Serialize `build(text)` so the WHOLE payload fits in `limit` characters.

    The cap applies to what the process prints, envelope included — and JSON
    escaping can expand a string past a naive pre-clamp — so the size is measured
    on the serialized result and `text` re-clamped by however much it overshot.

    `build` takes the (possibly shortened) text and returns the payload dict.
    Both dispatchers need this: one wraps an `additionalContext`, the other a
    `permissionDecisionReason`, and clamping only the inner string left the
    printed total over the cap in both cases.

    Converges in one or two passes. The loop is bounded so it always returns; if
    it somehow has not converged by then, the last attempt is returned rather
    than looping — an oversized payload is a degraded outcome, a hung hook is a
    dead one.
    """
    for _ in range(4):
        out = json.dumps(build(text))
        overflow = len(out) - limit
        if overflow <= 0:
            return out
        text = clamp_output(text, len(text) - overflow)
    return out


def compose_output(
    sections: list[str],
    must_keep: str = "",
    limit: int = HOOK_OUTPUT_CHAR_LIMIT,
) -> str:
    """Join `sections`, prioritising `must_keep` over the advisory preamble.

    `must_keep` is the blocking hook's reason — the one part Claude has to act
    on, and the part that arrives LAST in the stream, so a naive tail-truncation
    would drop precisely it. It is budgeted first and the advisory preamble
    absorbs the loss instead.

    It survives intact whenever it fits. A `must_keep` that is itself at or over
    `limit` is clamped like anything else and the preamble is dropped entirely —
    the size cap wins, because overshooting it sends the whole payload to a file
    Claude may never open, which loses the block reason completely rather than
    partially.
    """
    must_keep = must_keep or ""
    if len(must_keep) >= limit:
        # The block reason alone fills the budget. Advisory context is dropped
        # entirely rather than competing with it.
        return clamp_output(must_keep, limit)

    body = "\n".join(s for s in sections if s)
    if not body:
        return must_keep
    if not must_keep:
        return clamp_output(body, limit)

    budget = limit - len(must_keep) - 1  # -1 for the joining newline
    if budget <= 0:
        return must_keep
    return clamp_output(body, budget) + "\n" + must_keep


# --- Bounded git subprocess helpers -----------------------------------------
# Shared by block-worktree-path-escape.py and guard-worktree-isolation.py,
# which both run on every Edit/Write/Bash call and both need the SAME answer —
# "is cwd inside a linked worktree?" — resolved from its git-dir and
# git-common-dir. (`--show-toplevel` is NOT part of this; only
# block-worktree-path-escape.py wants the worktree root, and it keeps its own
# `_worktree_root` for that.)
#
# Each previously carried its own copy: the `_clone_paths` BODIES were
# identical, though their docstrings were not, and the two `_run_git` wrappers
# were NOT equivalent — one ran `["git", *args], cwd=cwd` while the other ran
# `git -C cwd`. Consolidating standardized on `-C`, so this was a behavior
# reconciliation, not a pure de-duplication. One definition, one fix site, same
# reasoning as `strip_quoted_spans`/`GIT_GLOBAL_OPTS` below.
#
# 3s: the bound exists to catch a WEDGED git (an index lock held by a
# concurrent session), not to accommodate a slow one — `rev-parse` on a
# healthy repo answers in milliseconds. Worst case is (call sites) x (this
# timeout), charged against the 15s handler shared with every other hook on
# the same matcher; `HOOK_WORST_CASE_SECONDS` records the product per caller.
GIT_TIMEOUT_SECONDS = 3


def run_git(cwd: str, args: list[str]) -> subprocess.CompletedProcess | None:
    """Run `git -C cwd <args>`, bounded by `GIT_TIMEOUT_SECONDS`, fail-open."""
    try:
        return subprocess.run(
            ["git", "-C", cwd, *args],
            capture_output=True, text=True, timeout=GIT_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.SubprocessError):
        return None


def clone_paths(cwd: str) -> tuple[str, str] | None:
    """Return (git_dir, git_common_dir) as realpaths, or None on failure.

    One `rev-parse` answering both questions, not two: it prints one line per
    requested option in argument order. This runs on every Bash call and on
    every Edit/Write via --heartbeat, so halving the process count here is a
    real saving against the shared handler budget.
    """
    r = run_git(cwd, ["rev-parse", "--absolute-git-dir", "--git-common-dir"])
    if not r or r.returncode != 0:
        return None
    lines = r.stdout.strip().splitlines()
    if len(lines) < 2:
        return None
    git_dir = os.path.realpath(lines[0].strip())
    common = lines[1].strip()
    if not os.path.isabs(common):
        common = os.path.join(cwd, common)
    return git_dir, os.path.realpath(common)


# --- Git command-line matching helpers --------------------------------------
# Shared by block-direct-push-to-main.py, warn-branch-base.py,
# warn-stray-scratch-artifact.py, guard-worktree-isolation.py,
# ask-destructive-git.py, and ask-git-identity.py. Previously
# each of those four files carried its own literal copy of this pattern (three
# linked only by a "mirrors guard-worktree-isolation.py" comment) — a bug fixed
# in one copy could silently persist in the other three, and did: a long
# global option with a space-separated (non-`=`) value (`git --work-tree
# <path> push origin main`) bypassed all of them, and a quoted `-c`/`-C` value
# containing a space (`git -C "/path with space" checkout -b x`) bypassed the
# two hooks that didn't call `strip_quoted_spans` before matching. One
# definition, one fix site closes both classes at once and keeps them closed.


# The git executable token, including the Windows extension forms.
#
# `\bgit\s+` cannot match `git.exe` -- `\s` does not match `.` -- so every git
# guard in this plugin silently allowed the extension spellings. Measured before
# this constant existed: `git push origin main` blocked (exit 2) while
# `git.exe push origin main` and `git.cmd push origin main` both exited 0. That
# was the whole guard set at once: the push-to-main block, both `ask-*`
# confirmations, worktree isolation, and two warns.
#
# Reachable by ordinary use rather than by evasion -- PowerShell is a primary
# shell for this harness and its tab-completion emits `git.exe`.
#
# `ask-destructive-git._GH_PR_MERGE` already spelled the sibling tool as
# `\bgh(?:\.(?i:exe|cmd|bat|com|ps1))?`, with a comment saying it exists
# "because Windows is the primary platform". The identical reasoning was never
# applied to `git`. This constant exists so the fix lands once instead of in six
# separate regexes -- the same rationale as `GIT_GLOBAL_OPTS` above.
#
# The command NAME stays case-sensitive, matching the `gh` precedent (whose
# docstring names `GH pr merge` as out of scope). `GIT push` therefore still
# slips through. That is a KNOWN, DOCUMENTED non-coverage, pinned by a contract
# test -- widening it is a behaviour change and belongs in its own commit, not
# bundled into a bypass fix.
GIT_CMD = r"\bgit(?:\.(?i:exe|cmd|bat|com|ps1))?"


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
_ORIGIN_HEAD_PREFIX = "refs/remotes/origin/"


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
                capture_output=True, text=True, timeout=2,
            )
        except (OSError, subprocess.SubprocessError):
            return None
        return (r.stdout or "").strip() if r.returncode == 0 else None

    resolved = None
    head_ref = _git(["symbolic-ref", "--quiet", "refs/remotes/origin/HEAD"])
    if head_ref and head_ref.startswith(_ORIGIN_HEAD_PREFIX):
        # Strip the known prefix rather than `rsplit("/", 1)`: a default branch
        # name containing its own slash (`release/main`) would otherwise lose
        # its leading segment, and `rev-parse --verify` on the FULL `head_ref`
        # (below) succeeds regardless — so the truncated name passed every
        # check here and still resolved to a branch that doesn't exist.
        candidate = head_ref[len(_ORIGIN_HEAD_PREFIX):] or None
        # `HEAD` as the remainder means the symref points at itself or at
        # something unusable — never a branch name.
        if candidate and candidate != "HEAD" and _git(
            ["rev-parse", "--verify", "--quiet", head_ref]
        ):
            resolved = candidate
    if resolved is None:
        # ONE `for-each-ref` for all four candidates, not four `rev-parse`
        # probes. The probes were up to 4 subprocesses, which put this
        # function's worst case at 6 spawns — and it is called while composing
        # an ENFORCING hook's block message, so that cost lands inside the
        # handler budget and was large enough to get the handler killed before
        # the block was emitted. `for-each-ref` takes many patterns and prints
        # only those that exist, answering the same question in one spawn.
        listed = _git([
            "for-each-ref", "--format=%(refname)",
            "refs/heads/main", "refs/remotes/origin/main",
            "refs/heads/master", "refs/remotes/origin/master",
        ])
        existing = set((listed or "").split())
        # `main` first: a repo carrying BOTH is nearly always one that renamed
        # to `main` and kept `master` as a stale leftover.
        for candidate in ("main", "master"):
            if {f"refs/heads/{candidate}", f"refs/remotes/origin/{candidate}"} & existing:
                resolved = candidate
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
