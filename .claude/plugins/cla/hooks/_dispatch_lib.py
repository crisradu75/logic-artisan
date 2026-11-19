#!/usr/bin/env python3
"""Shared helpers for the PreToolUse dispatcher scripts: the in-process hook
runner, the handler budget, and the output caps.

It runs several sibling hook scripts' `main()` in-process (one Python
interpreter instead of one per hook) by importing each as a standalone module —
the same technique the plugin's tests in `plugin-tests/tests/hooks/` use — and
temporarily redirecting stdin/stdout/stderr around each call. The sibling hook
files are never modified by this module; it only orchestrates them. It also
holds the budget the dispatchers spend (`HANDLER_TIMEOUT_SECONDS`,
`HOOK_WORST_CASE_SECONDS`, `Deadline`) and the bounded `run_git` the hooks with
git calls share, since a git timeout is a budget figure.

The shell-text helpers every git-matching guard imports (`strip_quoted_spans`,
`GitInvocation`, `GIT_CMD`, `GIT_SEP`) live in `_shell_text.py`, which imports
nothing from here. Some hooks still import from this module (`run_git`,
`clone_paths`, `Deadline`), so it loads them and they import from it: keep it
import-cheap and side-effect-free, because a failure here takes out the runner
and those hooks at once.

A hook that crashes (fails to load, or raises out of `main()`) is still
treated as fail-open — a guard must never wedge the workflow — but the
dispatcher must not go silent about it and must not let one broken sibling
take out the ones after it in the list. `run_hook_file()` isolates a load
failure to just that one hook, and callers MUST track `HookResult.errored`
across a run and surface it.

This docstring used to say callers should "exit non-zero-non-2" to fire Claude
Code's `<hook> hook error` transcript notice. Neither dispatcher does that, and
neither should: a non-zero exit makes Claude Code discard stdout, which
DOWNGRADES a pending `ask` to an allow and surfaces only the first line of
merged multi-hook stderr. The contract was stated one way and implemented
another, and the implementation was right.

What they do instead, and what a caller must match: exit 0, report an errored
ADVISORY hook as `additionalContext`, and escalate an errored ENFORCING hook to
`permissionDecision: "ask"`. That distinction is the load-bearing part — an
enforcing guard that failed to load did not run its check, and from the outside
that is indistinguishable from one that ran and allowed. stderr alone cannot
carry it, because stderr from an exit-0 hook reaches the debug log only, where
Claude never sees it.
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
# window `Deadline` can observe -- `Deadline` is constructed inside `main()`, so
# its clock starts after the shell wrapper has already run.
#
# Raised from 1.5 after measuring, because the run-each-candidate interpreter
# probe in `hooks.json` moved a full Python startup INTO that unobservable
# window and the reserve was never resized with it.
#
# MEASURED, and the spread is the point (Windows, Git Bash, `bash -c "<probe>
# true"` minus `bash -c true`):
#
#     quiet machine     net median 0.66-0.89s
#     loaded machine    net 5.5-7.1s, single samples to 10.8s
#
# So the honest position is that NO fixed constant covers this: the probe's cost
# swings ~70x with machine load, and 3.0 is a better guess than 1.5 rather than
# a proven ceiling. It comfortably covers the quiet case, which 1.5 did not.
#
# A threshold TEST on this number was written and then removed: it measured
# 4.01s under full-suite load while passing standalone, so it failed on exactly
# the machines that are busy. In a repo whose only gate is the local run, a
# flaky assertion is worse than none — it trains people to ignore the suite.
#
# THE MEASURED PATH, which replaces the guess where the shell allows it:
# `hooks/probe-python.sh` exports `CLA_HOOK_T0` from bash's `$EPOCHREALTIME` as
# its first act, and `Deadline` subtracts the REAL elapsed pre-`main()` cost
# (`_pre_main_seconds`) plus `_POST_HOOK_RESERVE_SECONDS` for the work after the
# last hook. `$EPOCHREALTIME` is a shell variable, so stamping spawns nothing on
# the probe's cache-hit path; `date +%s%3N`, the form first proposed here, would
# have spawned a process on every tool call. Git Bash on Windows is bash 5 and
# has it -- the platform this window was measured on. dash and macOS's bash 3.2
# do not, and leave the variable EMPTY, so this constant is the fallback there
# and whenever the value is unparseable, in the future, or older than the
# handler timeout (a stale value exported into the environment). The fallback
# is load-bearing, not decorative.
#
# The FALLBACK budget (12.0) is twice the enforcing sum each dispatcher carries
# (6.0: `ask-destructive-git.py` in the Bash one, `block-worktree-path-escape.py`
# in the Edit/Write one). The Bash sum was 12.0, the whole fallback, until that
# hook's probes moved onto one shared deadline. The 6s it freed is room for one
# more enforcing hook with git calls in the Edit/Write dispatcher, but in the
# Bash one only for a hook that reads the command alone and is listed in its
# `_READS_COMMAND_ONLY`: every other Bash hook runs once on the command and
# once per wrapper part, the part count has no cap, and an enforcing hook is
# never skipped, so a per-part enforcing hook must spawn nothing (0.0 below;
# `test_per_part_enforcing_hooks_spawn_nothing` holds it). Those sums are
# worst-case bounds assuming every git call times out, so real runs sit far
# below them -- and a hook added past the budget, or a timeout raised past it,
# fails `test_enforcing_hooks_fit_inside_the_handler_budget` immediately rather
# than silently overrunning. That test keeps using this constant: it is the
# worst case, the budget a run gets when nothing was measured. On a quiet
# machine the measured budget is larger (15 - ~0.7 - 1.0), which is what frees
# room for the advisory hooks after the enforcing ones; on a loaded one it is
# smaller, and is then the true figure rather than a guess that overran.
_BUDGET_RESERVE_SECONDS = 3.0

# Left after the last hook for the dispatcher's compose/print and exit, and for
# the few shell statements the wiring runs before the probe stamps the time.
# Used only when `CLA_HOOK_T0` was measured.
_POST_HOOK_RESERVE_SECONDS = 1.0

# Set by `hooks/probe-python.sh`: the wall-clock time the hook's shell began, in
# seconds (bash's `$EPOCHREALTIME`, whose decimal point follows the locale).
HOOK_T0_ENV = "CLA_HOOK_T0"


def _pre_main_seconds() -> float | None:
    """Seconds between the probe's stamp and now, or None when there is no
    usable stamp: unset, empty, not a plain decimal number, more than a second
    in the future, or as old as the handler timeout (a handler that old is
    already dead, so the value is stale, not this call's)."""
    raw = os.environ.get(HOOK_T0_ENV, "")
    if not re.fullmatch(r"\d+(?:[.,]\d+)?", raw):
        return None
    elapsed = time.time() - float(raw.replace(",", "."))
    if elapsed < -1.0 or elapsed >= HANDLER_TIMEOUT_SECONDS:
        return None
    return max(0.0, elapsed)

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
#     sum to no more than the budget, each counted once: that sum holds only
#     because the enforcing Bash hooks that run once per wrapper part all cost
#     0.0, which the same file asserts. Enforcing hooks are never skipped, so if
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
    "block-unsafe-recursive-delete.py": 0.0,
    "warn-comment-dates.py": 0.0,
    # Scans the command string for heredoc bodies carrying an eaten backslash
    # escape. Line-oriented regex over one string, no git and no filesystem.
    "warn-heredoc-escape-mangling.py": 0.0,
    # Resolves the write target and the plugins roots with `realpath`; no
    # subprocess, so it is enforcing in the Edit/Write dispatcher at no cost.
    "ask-plugin-cache-edit.py": 0.0,
    # Reads the command text and, at most, a `-F` message file; no subprocess,
    # so it is enforcing in the Bash dispatcher at no cost.
    "block-dishonest-commit.py": 0.0,
    # Reads the command text in one linear pass; its only I/O is looking for a
    # `.git` entry above the cwd once a `..` write target is found. No
    # subprocess, so it blocks and asks as an enforcing hook at no budget cost.
    "guard-bash-text.py": 0.0,
    # Regex scan of the new text of a write under `cla.io/<briefing dir>/`; no
    # subprocess and no file I/O, so it is enforcing in the Edit/Write dispatcher.
    "ask-secret-in-checkpoint.py": 0.0,
    # 2 x run_git(3s), as ONE deadline every git call of that hook shares
    # (`_PROBE_BUDGET_SECONDS` in `_destructive_git_probes.py`): each call gets
    # `min(3s, time left)` and none starts once it is gone, so this figure holds
    # however many call sites there are. Those are up to four fail-closed ones
    # (a `git status --porcelain` for the checkout/restore/switch paths, one for
    # the `git clean` paths, a memoised pathless fallback, a `rev-parse
    # --absolute-git-dir` for a saving `git stash`), then the fail-open history
    # checks (a rebase of pushed commits, `switch -C`/`checkout -B` over unique
    # commits, a merging switch over staged work), which spend what the first
    # four left. Before the deadline was shared this entry was 12.0 (4 x 3s).
    "ask-destructive-git.py": 6.0,
    # 2 x _run_git(3s): combined `rev-parse` + `--show-toplevel`.
    "block-worktree-path-escape.py": 6.0,
    # 1 x `git status --porcelain`(4s) — walks the working tree, so it gets more
    # than the `rev-parse` hooks.
    "warn-stray-scratch-artifact.py": 4.0,
    # `git status --porcelain --untracked-files=all` once per distinct broad
    # `git add` invocation, ALL of them sharing one 4s deadline
    # (`STATUS_BUDGET_SECONDS` in that hook), so the total is 4s however many
    # invocations the command chains. Best-effort, so skippable under budget
    # pressure (`_BEST_EFFORT_HOOKS` in the Bash dispatcher).
    "ask-broad-git-add.py": 4.0,
    # `git diff --cached`, plus a `git diff` and a `git ls-files --others` when
    # the commit takes files from the working tree, ALL sharing one 3s deadline
    # (`GIT_BUDGET_SECONDS` in that hook), however many commits the command
    # chains. Best-effort, so skippable under budget pressure.
    "ask-staged-debug-tag.py": 3.0,
    # Per directory a commit or `git merge --continue` runs in (at most
    # `MAX_DIRECTORIES`): a `rev-parse` for `MERGE_HEAD`, a `merge-base`, two
    # `diff --name-only` and one `cat-file --batch`, ALL sharing one 4s deadline
    # (`GIT_BUDGET_SECONDS` in that hook), so the total is 4s however many
    # directories or commits. It reads wrapper bodies itself and is listed in the
    # Bash dispatcher's `_READS_COMMAND_ONLY`, so it runs once per command, not
    # once per part. Advisory, so skippable under budget pressure.
    "warn-lossy-merge-resolution.py": 4.0,
    # 2 x _gh(4s): `pr view` then `pr list` on the explicit-PR-number path. The
    # only hook that leaves the machine, and the reason it stays advisory. Its
    # own docstring is the authority on the call count; the previous entry
    # described a different (cheaper) branch of the same function.
    "warn-stacked-pr-merge.py": 8.0,
}


class Deadline:
    """How much of the hooks.json handler timeout is left.

    Constructed at dispatcher entry, so `remaining()` already excludes the time
    spent in hooks that ran before the check. With no explicit budget, the time
    before construction is the measured `CLA_HOOK_T0` window when there is one,
    else the fixed `_BUDGET_RESERVE_SECONDS` guess.
    """

    __slots__ = ("_start", "_budget", "measured")

    def __init__(self, budget_seconds: float | None = None) -> None:
        self._start = time.monotonic()
        # True when the budget came from a real `CLA_HOOK_T0` measurement.
        self.measured = False
        if budget_seconds is None:
            before = _pre_main_seconds()
            self.measured = before is not None
            reserve = (
                _BUDGET_RESERVE_SECONDS if before is None
                else before + _POST_HOOK_RESERVE_SECONDS
            )
            budget_seconds = HANDLER_TIMEOUT_SECONDS - reserve
        self._budget = budget_seconds

    def remaining(self) -> float:
        return self._budget - (time.monotonic() - self._start)

    def expired(self) -> bool:
        return self.remaining() <= 0.0

    def has_room(self, cost_seconds: float) -> bool:
        """True when a hook whose worst case is `cost_seconds` can still finish.

        A zero-cost hook is admitted while any budget remains, down to and
        including `remaining() == 0.0` (where `expired()` is already True). Once
        the budget is OVERSPENT — `remaining()` negative — even a zero-cost hook
        is refused: the callers default an UNCOSTED hook to 0.0, which records
        absence of data rather than proof that it is free, and the handler is
        already late by then.

        The overspent case is the only one this wording changed. An earlier
        version promised admission "however little budget is left", which reads
        as covering negative remaining too; `>=` has never done that, and the
        body has not changed since it was introduced.
        """
        return self.remaining() >= cost_seconds


# --- Output size ------------------------------------------------------------
# Claude Code caps a hook's output at 10,000 characters; past that it writes
# the payload to a file and hands Claude a path plus a preview. For a warn hook
# that is a silent downgrade — the feedback these hooks exist to deliver stops
# being in front of Claude and becomes a file it may never open. Several leaf
# hooks truncate by ITEM count (`hits[:3]` in warn-comment-dates.py)
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

    THE SHRINK IS PROPORTIONAL, NOT SUBTRACTIVE. `overflow` counts SERIALIZED
    characters and `len(text)` counts unescaped ones, so the previous
    `clamp_output(text, len(text) - overflow)` over-corrected by the whole
    expansion factor. `json.dumps` defaults to `ensure_ascii=True`, so every
    non-ASCII character serializes as `\\uXXXX` at 6:1 — measured, a 20,000-char
    message that is 10% em-dashes clamped to the EMPTY string, and
    `clamp_output`'s `keep == 0` branch drops its own truncation notice, so the
    hook fired, produced output, and delivered nothing. Scaling by the measured
    ratio converges on the real budget instead:

        ascii  kept 9968 | 1% em-dash 8975 | 10% em-dash 0 -> now non-empty

    WHAT THIS FUNCTION CANNOT DO. It only shrinks `text`. When `build` closes
    over a fixed component — both dispatchers close over `reason` — and that
    component alone approaches `limit`, no choice of `text` fits and the loop
    returns something oversized. That is announced on stderr rather than
    returned quietly, because the caller's own budget is the only place it can
    be fixed: `reason` is `compose_output(asks)`, itself capped at exactly
    `limit`, so the envelope always pushes it over. Measured: a 9,990-char
    reason printed 10,077 characters.
    """
    out = json.dumps(build(text))
    for _ in range(4):
        if len(out) <= limit:
            return out
        if not text:
            break
        # `text`'s OWN serialized cost, which is the only part this function can
        # shrink. Everything else in `out` is the fixed component, so the room
        # left for text is `limit - fixed` in ESCAPED characters, converted back
        # to unescaped ones by text's own per-character expansion. Dividing the
        # whole payload by the text it contains would cancel to a tautology and
        # measure nothing.
        escaped = len(json.dumps(text))
        fixed = len(out) - escaped
        per_char = max(1.0, escaped / len(text))
        room = int((limit - fixed) / per_char)
        if room >= len(text):
            break
        text = clamp_output(text, max(0, room))
        out = json.dumps(build(text))
    if len(out) > limit:
        print(
            f"[dispatch] payload is {len(out)} characters against a {limit} cap "
            "and cannot be shrunk further — the part that overflows is not the "
            "hook text. Claude Code will write this to a file and show a "
            "preview instead of the whole message.",
            file=sys.stderr,
        )
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


def extract_ask(stdout_text: str) -> str | None:
    """Pull an `ask` escalation's reason out of a hook's stdout JSON.

    A hook that wants the user prompted (rather than blocked outright) exits 0
    and emits `permissionDecision: "ask"`. Only the dispatcher's stdout is read
    per PreToolUse call, so the decision has to be re-emitted there or it is
    silently downgraded to an allow. Shared by both dispatchers, which carried
    identical copies.
    """
    stdout_text = stdout_text.strip()
    if not stdout_text:
        return None
    try:
        payload = json.loads(stdout_text)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    nested = payload.get("hookSpecificOutput")
    if not isinstance(nested, dict) or nested.get("permissionDecision") != "ask":
        return None
    return str(nested.get("permissionDecisionReason") or "A guard requested confirmation.")


# --- Bounded git subprocess helpers -----------------------------------------
# Used by block-worktree-path-escape.py, which runs on every Edit/Write call
# and needs to answer "is cwd inside a linked worktree?" — resolved from its
# git-dir and git-common-dir. (These were shared with a second worktree hook
# until that hook was retired; the helpers stay here rather than being inlined,
# since a future worktree guard needs the same answer.)
# (`--show-toplevel` is NOT part of this; only
# block-worktree-path-escape.py wants the worktree root, and it keeps its own
# `_worktree_root` for that.)
#
# Each previously carried its own copy: the `_clone_paths` BODIES were
# identical, though their docstrings were not, and the two `_run_git` wrappers
# were NOT equivalent — one ran `["git", *args], cwd=cwd` while the other ran
# `git -C cwd`. Consolidating standardized on `-C`, so this was a behavior
# reconciliation, not a pure de-duplication. One definition, one fix site, same
# reasoning as `strip_quoted_spans`/`GIT_GLOBAL_OPTS` in `_shell_text.py`.
#
# 3s: the bound exists to catch a WEDGED git (an index lock held by a
# concurrent session), not to accommodate a slow one — `rev-parse` on a
# healthy repo answers in milliseconds. Worst case is (call sites) x (this
# timeout), charged against the 15s handler shared with every other hook on
# the same matcher; `HOOK_WORST_CASE_SECONDS` records the product per caller.
GIT_TIMEOUT_SECONDS = 3


def run_git(
    cwd: str, args: list[str], timeout: float | None = None
) -> subprocess.CompletedProcess | None:
    """Run `git -C cwd <args>`, bounded by `GIT_TIMEOUT_SECONDS`, fail-open.

    `timeout` is for a caller spending what is left of a shared deadline; it
    should never exceed `GIT_TIMEOUT_SECONDS`, which the budget table assumes."""
    try:
        return subprocess.run(
            ["git", "-C", cwd, *args],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=GIT_TIMEOUT_SECONDS if timeout is None else timeout,
        )
    except (OSError, subprocess.SubprocessError):
        return None


def clone_paths(cwd: str) -> tuple[str, str] | None:
    """Return (git_dir, git_common_dir) as realpaths, or None on failure.

    One `rev-parse` answering both questions, not two: it prints one line per
    requested option in argument order. Its only caller is the Edit/Write guard
    `block-worktree-path-escape.py`, which runs on every Edit/Write, so halving
    the process count here is a real saving against the shared handler budget.
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


def ensure_hooks_dir_importable() -> None:
    """Put the hooks dir on `sys.path` if it isn't already.

    Several hook files do `from _dispatch_lib import ...` or `from _shell_text
    import ...` at module level. That
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


def run_hook_file_each(filename: str, stdin_texts: list[str]):
    """`run_hook_file` over several inputs, loading the file once: yields one
    `HookResult` per text, in order, so the caller can stop early (on a block,
    or when the budget runs out) and nothing after that runs. A load failure
    yields its one errored result and stops, as `run_hook_file` reports it.

    The Bash dispatcher runs a guard on the command and then on each part
    `_shell_read.guard_parts` found in it; loading the file once per part would
    cost a module execution per part."""
    try:
        mod = load_hook(filename)
    except Exception:
        yield run_hook_file(filename, stdin_texts[0] if stdin_texts else "")
        return
    for text in stdin_texts:
        yield run_hook(mod, text)
