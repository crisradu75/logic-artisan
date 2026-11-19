#!/usr/bin/env python3
"""The git probes of `ask-destructive-git.py`, and the one deadline they share.

Each conditional rule there asks only when something is at stake, so each runs
git first: `git status --porcelain` for the working-tree discards and `git
clean`, `rev-parse --absolute-git-dir` for a stash during a merge, and the
rev-parse, rev-list, merge-base, config and status calls of the history checks
(a rebase of pushed commits, a branch reset that orphans commits, a merging
switch over staged work).

ONE DEADLINE FOR ALL OF THEM. `_reasons` builds one `_Probes` per command and
every call below goes through its `git()`, which gives each call at most
`GIT_TIMEOUT_SECONDS` and never more than is left of `_PROBE_BUDGET_SECONDS`
(`HOOK_WORST_CASE_SECONDS["ask-destructive-git.py"]`), and starts none once it
is gone. So that table entry is the deadline itself, however many call sites
there are. What a call that is never started returns is `None`, the "could not
run" answer each caller already handles: the discard, clean and stash checks
ask (fail closed), the history checks stay silent and say so on stderr (fail
open; the section comment above `_REBASE` in `_destructive_git_rules.py` says
why). Each identical call runs once per command.

Split out of `ask-destructive-git.py`, which imports only the names its decision
calls. A test reaches the rest here, and one that replaces `_run_git`, `time` or
a helper patches it HERE: these functions look those names up in this module.
"""

from __future__ import annotations

import os
import re
import sys
import time  # the deadline's clock (a test replaces this module's `time`)
from pathlib import Path

# Loaded by path, like every hook: the `_dispatch_lib` import below is made
# explicit rather than left to how the process happened to start.
_HOOKS_DIR = str(Path(__file__).resolve().parent)
if _HOOKS_DIR not in sys.path:
    sys.path.insert(0, _HOOKS_DIR)

from _dispatch_lib import Deadline  # noqa: E402
from _dispatch_lib import GIT_TIMEOUT_SECONDS  # noqa: E402
from _dispatch_lib import HOOK_WORST_CASE_SECONDS  # noqa: E402
from _dispatch_lib import run_git as _run_git  # noqa: E402
from _destructive_git_rules import (  # noqa: E402
    _BRANCH_CHANGE,
    _NOT_REBASE,
    _OPERATION_MARKERS,
    _PULL,
    _REBASE,
    BRANCH_RESET_REASON,
    MERGE_SWITCH_REASON,
    REBASE_REASON,
    _config_key,
    _config_overrides,
    _invocation_dir,
    _line_kind,
    _merges_on_switch,
    _pull_rebase,
    _pull_upstream,
    _rebase_range,
    _reset_target,
    _words,
)

# Every git call this hook makes shares one deadline this long, counted from
# the start of `_reasons`: 2 x `GIT_TIMEOUT_SECONDS` (3s), room for two calls
# that each run to their own timeout, which is what a wedged git costs before
# the rest are refused. It was 12s (four fail-closed call sites x 3s, with the
# history calls spending whatever those left); one deadline for every call
# keeps the worst case at this figure however many call sites there are, and
# frees 6s of the handler for another enforcing guard. The cost, named: on a
# git slow enough to spend the deadline, a later fail-closed probe is never
# started and its check asks as unchecked rather than running late.
_PROBE_BUDGET_SECONDS = HOOK_WORST_CASE_SECONDS["ask-destructive-git.py"]


class _Probes:
    """Every git call one command's checks make: one shared deadline, each
    identical call run once, and every revision from the command resolved to
    a SHA before it goes anywhere else. `missed` is True once a call could not
    run (no git, a timeout, or the deadline spent)."""

    def __init__(self, started: float) -> None:
        # Also no later than the handler's own deadline, when the probe measured
        # it (`CLA_HOOK_T0`): a handler killed mid-probe would drop every reason
        # already found with it. Without a measurement the handler's figure
        # is a guess, and the hook's own budget alone applies. Counted from
        # `started`, which is earlier than now, so the bound errs early.
        handler = Deadline()
        budget = _PROBE_BUDGET_SECONDS
        if handler.measured:
            budget = min(budget, handler.remaining())
        self.deadline = started + budget
        self.asked: dict = {}
        self.missed = False

    def git(self, directory: str, args: list[str]):
        key = (directory, tuple(args))
        if key not in self.asked:
            left = self.deadline - time.monotonic()
            self.asked[key] = (
                _run_git(directory, args, timeout=min(GIT_TIMEOUT_SECONDS, left))
                if left > 0 else None
            )
            self.missed = self.missed or self.asked[key] is None
        return self.asked[key]

    def commit(self, directory: str, rev: str) -> str | None:
        """`rev` as a full commit SHA, or None. `--end-of-options` keeps a
        `--output=<file>` from being read as an option; a leading `-` is
        refused outright."""
        if not rev or rev.startswith("-"):
            return None
        # `:/<text>` names the youngest commit whose message matches, so it is
        # a commit already; a `^{commit}` suffix would join the search text.
        peeled = rev if rev.startswith(":/") else rev + "^{commit}"
        out = self.git(directory, ["rev-parse", "--verify", "--quiet", "--end-of-options", peeled])
        sha = out.stdout.strip() if out is not None and out.returncode == 0 else ""
        return sha if re.fullmatch(r"[0-9a-f]{40,64}", sha) else None

    def ref(self, directory: str, rev: str) -> str | None:
        """The full ref name `rev` spells (`refs/remotes/origin/main`), or None
        for a revision that is not a ref. git prints it; the command never
        reaches `merge-base` itself."""
        if rev.startswith("-"):
            return None
        out = self.git(directory, [
            "rev-parse", "--verify", "--quiet", "--symbolic-full-name", "--end-of-options", rev,
        ])
        name = out.stdout.strip() if out is not None and out.returncode == 0 else ""
        return name if re.fullmatch(r"refs/[^\s]+", name) else None

    def setting(self, directory: str, key: str, overrides: dict[str, str]) -> str | None:
        """A config value: a `-c` override from the command first, else the
        repository's own, else None when unset."""
        if _config_key(key) in overrides:
            return overrides[_config_key(key)]
        out = self.git(directory, ["config", "--get", key])
        return out.stdout.strip() if out is not None and out.returncode == 0 else None


def _status_lines(cwd: str, paths: list[str], ignored: bool, probes: _Probes | None = None):
    """Porcelain lines for `paths`, or a sentinel saying why there are none.

    Tri-state on purpose, because the two ways of getting no answer must not be
    treated alike:

    - `None` — the probe could NOT RUN: no git on PATH, or a git that hung past
      `GIT_TIMEOUT_SECONDS`. The check did not happen, and a guard that allows
      because it failed to look is indistinguishable from one that looked and
      approved, which is the worst outcome this layer has.
    - `False` — the probe ran and git REFUSED (non-zero): a pathspec outside the
      repository, an unknown pathspec magic, not a repository at all.

    An empty `paths` asks about the whole tree. `probes` is the command's
    shared `_Probes`; a direct call without one gets its own.

    (An earlier revision of this docstring named "a wedged git holding an index
    lock" as a `None` trigger. Measured: with `.git/index.lock` present,
    `git status --porcelain` returns 0 and correct output — it takes the lock
    non-fatally — so a held lock produces neither sentinel. The claim was
    reasoned rather than run, which is the failure CLAUDE.md's check 3 names.)
    """
    args = ["status", "--porcelain"] + (["--ignored"] if ignored else [])
    if paths:
        args += ["--", *paths]
    result = (probes or _Probes(time.monotonic())).git(cwd, args)
    if result is None:
        return None
    if result.returncode != 0:
        return False
    return [line for line in result.stdout.splitlines() if line.strip()]


def _holds_work(cwd, paths, wanted, ignored, whole_tree, probes: _Probes | None = None) -> bool:
    """True when the matched commands would destroy something of kind `wanted`.

    `whole_tree` is a zero-argument callable returning the pathless probe's
    lines, memoised by the caller so it costs at most one extra subprocess per
    hook run however many times this is asked.

    A REFUSAL is silence only when a single path was probed — there, "git is
    about to reject the real command the same way" is exactly true. It is NOT
    true of a batch: this hook merges the operands of every matching invocation
    into one probe to keep the subprocess count at two, and git rejects the
    whole call for one bad pathspec. So

        git checkout -- ../outside && git checkout -- tracked.txt

    refused the merged probe, returned silence, and the shell then ran the
    second command and destroyed `tracked.txt`. A refused BATCH therefore falls
    back to the whole tree rather than to silence — over-prompting on a command
    that half-fails, which is the right side to err on.
    """
    lines = _status_lines(cwd, paths, ignored, probes)
    if lines is None:
        return True
    if lines is False:
        if len(paths) <= 1:
            return False
        lines = whole_tree()
        if lines is None:
            return True
        if lines is False:
            return False
    return any(_line_kind(line) in wanted for line in lines)


def _operation_in_progress(directory: str, probes: _Probes | None = None) -> bool | None:
    """True when a merge, cherry-pick or revert is in progress in `directory`.

    `None` means the probe could not run (no git, or a hang past the timeout),
    the same sentinel `_status_lines` uses. A refusal (not a repository) is
    False: git is about to reject the stash the same way. But a directory that
    does not exist is NOT a refusal we can trust: it may be a path the shell
    would have translated (`/c/...` under Git Bash), so that is "could not check".
    """
    result = (probes or _Probes(time.monotonic())).git(directory, ["rev-parse", "--absolute-git-dir"])
    if result is None:
        return None
    if result.returncode != 0:
        return False if os.path.isdir(directory) else None
    git_dir = result.stdout.strip()
    return any(os.path.exists(os.path.join(git_dir, n)) for n in _OPERATION_MARKERS)


def _rewrites_published(
    directory: str, branch: str, upstream: str | None, rewrites: bool,
    fork_point: bool, probes: _Probes,
) -> bool:
    """True when the commits the rebase rewrites include one already reachable
    from a remote-tracking branch: two counts over the same range, the second
    leaving out everything `--remotes` reaches. Any remote counts, not only the
    upstream, because a branch pushed without `-u` is published all the same.

    A branch already up to date with its upstream (the upstream is an ancestor
    of it) replays nothing, unless `rewrites` says an option may force it, or
    fork-point finds an older point in the upstream's reflog: there git drops
    the commits the upstream has since lost and replays the rest.
    """
    tip = probes.commit(directory, branch)
    if tip is None:
        return False
    span = [tip]
    if upstream is not None:
        base = probes.commit(directory, upstream)
        if base is None:
            return False
        if not rewrites and _replays_nothing(directory, upstream, base, tip, fork_point, probes):
            return False
        span.append("^" + base)
    every = probes.git(directory, ["rev-list", "--count", *span, "--"])
    if every is None or every.returncode != 0:
        return False
    local = probes.git(directory, ["rev-list", "--count", *span, "--not", "--remotes", "--"])
    if local is None or local.returncode != 0:
        return False
    return int(every.stdout) > int(local.stdout)


def _replays_nothing(
    directory: str, upstream: str, base: str, tip: str, fork_point: bool, probes: _Probes
) -> bool:
    """True when git would report the branch up to date: `base` is an ancestor
    of `tip` and, under fork-point, the fork point is `base` or there is none.
    A probe that cannot run counts as up to date, so the check fails open."""
    ancestor = probes.git(directory, ["merge-base", "--is-ancestor", base, tip])
    if ancestor is None:
        return True
    if ancestor.returncode != 0:
        return False
    ref = probes.ref(directory, upstream) if fork_point else None
    if ref is None:
        return True
    out = probes.git(directory, ["merge-base", "--fork-point", "--end-of-options", ref, tip])
    if out is None:
        return True
    found = out.stdout.strip() if out.returncode == 0 else ""
    return found in ("", base)


def _pull_rebases(
    directory: str, rebase: bool | None, overrides: dict[str, str], probes: _Probes
) -> bool:
    """Whether a `git pull` rebases: the command's own flag, else
    `branch.<current>.rebase`, else `pull.rebase`, each from a `-c` override
    before the repository's config. The branch name comes from git's own
    output, never from the command."""
    if rebase is not None:
        return rebase
    head = probes.git(directory, ["symbolic-ref", "--quiet", "--short", "HEAD"])
    keys = ["pull.rebase"]
    if head is not None and head.stdout.strip():
        keys.insert(0, "branch." + head.stdout.strip() + ".rebase")
    for key in keys:
        value = probes.setting(directory, key, overrides)
        if value is not None:
            return _is_true(value)
    return False


def _is_true(value: str) -> bool:
    """A config value as git's `--rebase`/`forkPoint` reading takes it."""
    return value.strip().lower() not in _NOT_REBASE and value.strip() != ""


def _orphans_commits(directory: str, name: str, start: str, probes: _Probes) -> bool:
    """True when branch `name` exists and holds commits on no other branch, tag
    or remote-tracking branch, nor in `start` — what the reset would orphan.
    A branch that does not exist yet does not resolve: silence, since creating
    it loses nothing."""
    if name.startswith("-"):
        return False
    tip = probes.commit(directory, "refs/heads/" + name)
    target = probes.commit(directory, start)
    if tip is None or target is None:
        return False
    out = probes.git(directory, [
        "rev-list", "--count", tip, "--not",
        "--exclude=" + name, "--branches", "--tags", "--remotes", target, "--",
    ])
    return out is not None and out.returncode == 0 and int(out.stdout) > 0


def _holds_staged_work(directory: str, probes: _Probes) -> bool:
    """True when the index differs from HEAD anywhere: porcelain column X is not
    blank. `--untracked-files=no` keeps `??` lines, whose X is `?`, out."""
    out = probes.git(directory, ["status", "--porcelain", "--untracked-files=no"])
    if out is None or out.returncode != 0:
        return False
    return any(line[:1].strip() for line in out.stdout.splitlines())


def _history_reasons(command: str, scanned: str, cwd: str, probes: _Probes) -> list[str]:
    """The rebase, branch-reset and merging-switch reasons in `command`, probed
    on `probes`, the command's shared deadline; `missed` is counted from here,
    so a working-tree probe refused earlier does not read as a history one."""
    probes.missed = False
    found: list[str] = []
    for m in _REBASE.finditer(scanned):
        directory = _invocation_dir(command[m.start(1):m.end(1)], scanned, cwd)
        target = _rebase_range(_words(m.group(2), command[m.start(2):m.end(2)]))
        if directory and target and REBASE_REASON not in found:
            branch, upstream, rewrites, fork_point = target
            if fork_point is None:
                overrides = _config_overrides(command[m.start(1):m.end(1)])
                setting = probes.setting(directory, "rebase.forkPoint", overrides)
                fork_point = setting is None or _is_true(setting)
            if _rewrites_published(directory, branch, upstream, rewrites, fork_point, probes):
                found.append(REBASE_REASON)
    for m in _PULL.finditer(scanned):
        directory = _invocation_dir(command[m.start(1):m.end(1)], scanned, cwd)
        rebase, operands = _pull_rebase(_words(m.group(2), command[m.start(2):m.end(2)]))
        upstream = _pull_upstream(operands)
        if directory and upstream and REBASE_REASON not in found:
            # Always `rewrites`: the fetch can move the upstream past HEAD, so
            # "up to date" before it says nothing about after.
            overrides = _config_overrides(command[m.start(1):m.end(1)])
            if _pull_rebases(directory, rebase, overrides, probes) and _rewrites_published(
                directory, "HEAD", upstream, True, False, probes
            ):
                found.append(REBASE_REASON)
    for m in _BRANCH_CHANGE.finditer(scanned):
        directory = _invocation_dir(command[m.start(1):m.end(1)], scanned, cwd)
        if directory is None:
            continue
        words = _words(m.group(3), command[m.start(3):m.end(3)])
        target = _reset_target(words, m.group(2))
        if target and BRANCH_RESET_REASON not in found:
            if _orphans_commits(directory, *target, probes):
                found.append(BRANCH_RESET_REASON)
        if _merges_on_switch(words, m.group(2)) and MERGE_SWITCH_REASON not in found:
            if _holds_staged_work(directory, probes):
                found.append(MERGE_SWITCH_REASON)
    if probes.missed:
        print(
            "[ask-destructive-git] a rebase or branch-change probe did not run "
            "(git missing, a timeout, or the hook's time budget spent) — not "
            "asking about it. (hook: ask-destructive-git.py)",
            file=sys.stderr,
        )
    return found
