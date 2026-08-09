#!/usr/bin/env python3
"""PreToolUse hook: block direct `git push` to main/master.

Convention: no direct commits to the default branch — use feature branches.
A retroactive paperwork-PR after the fact is structurally impossible (GitHub
refuses no-diff PRs), so the only fix is
to prevent the push at the moment it would happen.

Detection: locate EVERY `git push` in the Bash command — including a `push`
reached via a git GLOBAL option between `git` and the subcommand (`-c`/`-C`/
`--work-tree`/etc., see `_dispatch_lib.GIT_GLOBAL_OPTS`) — and read each one's
own positional arguments, stopping at the shell separator that ends that
push's argument list. Scanning every match matters: `git push origin
feature/x && git push origin main` is exactly what a drifted session runs, and
inspecting only the first match let the second reach the remote unblocked. For
each push, the first positional is the remote and the rest are refspecs, each
normalized (surrounding quotes stripped, a leading `+` force-marker dropped, a
`refs/heads/` prefix removed) before EITHER side of a `src:dst` pair is
compared against main/master. Blocked shapes therefore include:
  - `git push <remote> main` / `git push <remote> master`
  - `git push <remote> HEAD:main` / `git push <remote> <branch>:main`
  - `git push <remote> main:<branch>` (pushing the main branch's content out)
  - `git push <remote> refs/heads/main` (fully-qualified destination)
  - `git push <remote> +main` (force refspec) and `git push <remote> :main`
    (deleting the remote default branch)
  - `git push <remote> "main"` / `'main'` (quoted destination)
  - Same with `--force` / `-f` / `--force-with-lease`
  - `git push` / `git push <remote>` with NO refspec, when HEAD is main/master
  - `git push <remote> HEAD` / `@` (or either side of a `HEAD:<dst>` pair) when
    HEAD is main/master. `HEAD` is a positional refspec, so the bare-push
    current-branch check never ran for it, and as a literal ref name it matches
    nothing protected — yet `git push origin HEAD` is what a script emits when
    it does not want to hardcode a branch name, and from main it pushes main.
  - Any of the above after a `&&`, `;`, `|`, or newline earlier in the command
  - `git push -o ci.skip <remote>` and friends from main — an option whose
    value is a separate token has that value consumed, so it cannot pose as a
    refspec and suppress the refspec-less current-branch check
  - `git push --all` / `--mirror` (with or without a remote) — these push EVERY
    local branch, so the default one goes with them and no refspec names it;
    `--mirror` additionally deletes remote refs the local repo lacks
  - `git push --repo <remote> main` — `--repo` supplies the remote as an option
    VALUE, so the positional that would normally be the remote is actually the
    refspec. `main` was read as the remote and the refspec check never ran
  - `git push <remote> heads/main` — git DWIMs `heads/main` to `refs/heads/main`,
    and only the fully-qualified prefix was being stripped

Which branch counts as "current" is resolved in the command's OWN directory:
`payload["cwd"]`, overridden by a `-C` / `--work-tree` value when the
invocation carries one (the same shape `guard-worktree-isolation.py` uses).
Resolving it in the hook process's cwd instead fails BOTH ways — a session in a
worktree while the primary clone sits on main allows a real direct push, and
the inverse blocks a legitimate one.

Resolution stays lazy: a literal refspec (`git push origin main`) is decided
with NO subprocess call at all, so the guard does not become dependent on git
being usable to catch its most common offense. Only a `HEAD`/`@` refspec or a
refspec-less push shells out.

Allow:
  - `git push -u origin feature/...` (any non-main destination)
  - Branch names that merely START with main/master — `main-refactor`,
    `master-list`, `main.old`, `maintenance` — are compared as whole refs, so
    they are NOT blocked. (A substring/word-boundary match got this wrong.)
  - `git push` with no refspec when the current branch is NOT main
  - Any push when the env var `ALLOW_PUSH_TO_MAIN=1` is set (escape hatch for
    the rare legitimate case — e.g. an admin restoring after force-push).

Exit codes:
  0 — allow
  2 — block with stderr explaining the rule

Best-effort, with the gaps named rather than implied. A `git push` invoked via
an alias, or one built by string interpolation, slips past; so does a
HERESTRING (`bash <<< '...'`), whose body IS quoted and so is blanked by
`strip_quoted_spans` before matching. That one is left open deliberately:
unlike `git.exe`, which PowerShell's tab-completion emits during ordinary
work, a herestring-wrapped push is evasion-shaped, and un-blanking quoted
spans after `<<<` adds parsing complexity to an ENFORCING guard for a
vector nobody reaches by accident. An uppercase `GIT` used to be out of
scope on that same reasoning; it no longer is, because unlike a herestring
it is reached by ordinary use on a case-insensitive filesystem — see
`GIT_CMD`'s comment for the measured trade. Also: so does a global
option shape outside `GIT_GLOBAL_OPTS`'s named, closed set (see that helper's
docstring). A `git push origin main` sitting in a HEREDOC BODY is matched and
blocked even though it is being written to a file rather than run — accepted,
per `strip_quoted_spans`'s stated scope. The common offense (`git push origin
main` from a session that drifted onto main, with or without a `-C`/
`--work-tree`/`-c` prefix) is caught.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

# The `_dispatch_lib` import below resolves through `sys.path`. `hooks.json`
# never invokes THIS file directly — it invokes the dispatcher
# (`dispatch-bash-pretooluse.py`), which loads this hook in-process via
# `_dispatch_lib.load_hook`; this file's own test suite loads it in-process
# too (`importlib.util.spec_from_file_location`), never as a standalone
# process. Neither shape puts the hooks dir at `sys.path[0]` for this file —
# the dispatcher relies on `_dispatch_lib.ensure_hooks_dir_importable()`,
# pytest on `hooks/pyproject.toml`'s `pythonpath = ["."]`. Insert it
# explicitly so this file's own import can never silently disable the guard,
# independent of either mechanism.
_HOOKS_DIR = str(Path(__file__).resolve().parent)
if _HOOKS_DIR not in sys.path:
    sys.path.insert(0, _HOOKS_DIR)

from _dispatch_lib import GIT_CMD as _GIT_CMD  # noqa: E402
from _dispatch_lib import GIT_GLOBAL_OPTS as _G  # noqa: E402
from _dispatch_lib import strip_quoted_spans as _strip_quoted_spans  # noqa: E402

# Group 1 captures the global-option blob between `git` and `push`, so a
# `-C`/`--work-tree` belonging to THIS invocation can be recovered per match
# rather than scanned for anywhere in the command line.
_GIT_PUSH = re.compile(_GIT_CMD + r"\s+(" + _G + r")push\b")

# Where the `git push` argument list ends: a shell separator starts a new
# command, so tokens past it are not this push's refspecs.
_SHELL_SEPARATOR = re.compile(r"[;&|)\n]")

# A repo-selecting global option's value, read out of one invocation's option
# blob. `--git-dir` is included because `GIT_GLOBAL_OPTS` already CONSUMES it:
# leaving it out here made `git --git-dir=/other/.git push origin HEAD` resolve
# HEAD in the session's directory instead of the repo the command names. Passing
# a `.git` dir to `git -C` is an approximation of git's own semantics, but a
# directed one — git recognizes being inside a git dir — and it beats silently
# answering from the wrong repo. Best-effort and first-match-wins: git applies
# repeated `-C` cumulatively, which this does not model; the shape worth
# resolving is the single `git -C <path> push …` a script emits.
_GIT_DIR_OPT = re.compile(
    r"(?:^|\s)(?:-C\s+(\S+)|--(?:work-tree|git-dir)(?:=|\s+)(\S+))"
)

# `git push` options whose value is a SEPARATE token. Dropping the flag alone
# leaves the value behind as a phantom positional, which makes the token after
# it read as a refspec and suppresses the refspec-less branch check — so
# `git push -o ci.skip origin` from main was allowed. A closed set, same posture
# as `_dispatch_lib._GIT_GLOBAL_VALUE_OPTS`: the `--opt=value` form is a single
# token and is already dropped by the leading-dash test.
_PUSH_VALUE_OPTS = ("-o", "--push-option", "--receive-pack", "--exec", "--repo")

_PROTECTED = ("main", "master")

# `--all` / `--mirror` push every local branch, so the default branch goes with
# them and NO refspec names it — the refspec check below cannot see them at all.
# `--mirror` additionally deletes remote refs the local repo lacks.
#
# No short form: `git push` has no `-a`, and matching one would fire on
# unrelated tools that do.
_ALL_BRANCHES_FLAG = re.compile(r"--(?:all|mirror)$")

# Positional refspecs that MEAN the current branch rather than naming a ref.
_HEAD_ALIASES = ("HEAD", "@")


def _normalize_ref(ref: str) -> str:
    """Reduce one side of a refspec to a bare branch name for comparison.

    Strips `heads/` as well as the fully-qualified `refs/heads/`: git DWIMs
    `git push origin heads/main` to `refs/heads/main`, so the short form is a
    real push to the default branch that the prefix-only check let through.
    """
    ref = ref.strip("'\"").lstrip("+")
    for prefix in ("refs/heads/", "heads/"):
        if ref.startswith(prefix):
            return ref[len(prefix) :]
    return ref


def _refspec_touches_main(
    refspec: str, work_tree: str | None = None, session_cwd: str | None = None
) -> bool:
    """True iff either side of `[+][src]:[dst]` (or a bare ref) is main/master.

    Both sides count: `<branch>:main` pushes TO the default branch, and
    `main:<branch>` pushes the default branch's content OUT — the convention
    this hook enforces treats both as a direct-to-main operation.

    `HEAD`/`@` on either side is not a ref NAME but a reference to whatever
    branch is checked out, so it is resolved through `_current_branch`. That
    resolution is deliberately reached only AFTER the literal comparison fails:
    the common offense (`git push origin main`) must stay decidable without
    git being usable at all.
    """
    ref = refspec.strip("'\"").lstrip("+")
    sides = ref.split(":") if ":" in ref else [ref]
    normalized = [_normalize_ref(side) for side in sides]
    if any(side in _PROTECTED for side in normalized):
        return True
    if any(side in _HEAD_ALIASES for side in normalized):
        return _branch_for(work_tree, session_cwd) in _PROTECTED
    return False


def _push_argument_lists(scanned: str, command: str) -> list[tuple[str | None, list[str]]]:
    """Return one window per `git push` in the command: its own `-C` /
    `--work-tree` override (or None) paired with the whitespace-delimited
    tokens following it, re-sliced from the ORIGINAL command so a quoted
    refspec keeps its real text.

    One window per match, not just the first: truncating at the first shell
    separator correctly ends ONE push's argument list, but a `.search()` then
    made every later push invisible, so `git push origin feature/x && git push
    origin main` reached the remote unblocked.

    `strip_quoted_spans` is length-preserving precisely so these offsets stay
    valid against `command`; matching on `scanned` is what keeps a `git push`
    inside an echoed string from being seen at all.
    """
    windows: list[tuple[str | None, list[str]]] = []
    for m in _GIT_PUSH.finditer(scanned):
        rest = scanned[m.end() :]
        stop = _SHELL_SEPARATOR.search(rest)
        if stop:
            rest = rest[: stop.start()]
        base = m.end()
        work_tree = _command_work_tree(m.group(1), command[m.start(1) : m.end(1)])
        windows.append((
            work_tree,
            [command[base + t.start() : base + t.end()] for t in re.finditer(r"\S+", rest)],
        ))
    return windows


def _command_work_tree(scanned_options: str, raw_options: str) -> str | None:
    """The `-C` / `--work-tree` path from ONE invocation's global-option blob,
    or None.

    Matched against the SCANNED text (so a quoted path containing a space is
    one `\\S+` token) and re-sliced from the RAW text at the same offsets (so
    the returned value is the real path, not the placeholder fill) — the same
    length-preserving contract `_push_argument_lists` relies on."""
    m = _GIT_DIR_OPT.search(scanned_options)
    if not m:
        return None
    idx = 1 if m.group(1) is not None else 2
    return raw_options[m.start(idx) : m.end(idx)].strip("'\"") or None


def _branch_for(work_tree: str | None, session_cwd: str | None) -> str | None:
    """Resolve the current branch for one push, preferring the directory the
    command itself names and falling back to the session's.

    Two things this does that a bare `work_tree or session_cwd` did not:

    - **A relative `-C` is composed against the session directory**, the way
      the shell would. Passed through raw it resolved against whatever cwd the
      hook PROCESS happens to have — reintroducing, for relative paths, the
      exact wrong-directory bug this hook was fixed for. Verified regression:
      from a session in `<repo>/sub`, `git -C .. push` (targeting a repo root
      sitting on main) resolved to `<repo>/..`, failed, and was ALLOWED.
    - **A failed command-derived path falls back to the session directory**
      rather than straight to "unknown". A scraped `-C` value is far likelier
      to be wrong than the payload's own cwd, and "unknown" means the guard
      stops guarding (see `_current_branch`'s tri-state note)."""
    candidates: list[str] = []
    if work_tree:
        if session_cwd and not os.path.isabs(work_tree):
            candidates.append(os.path.join(session_cwd, work_tree))
        else:
            candidates.append(work_tree)
    if session_cwd and session_cwd not in candidates:
        candidates.append(session_cwd)
    for candidate in candidates:
        branch = _current_branch(candidate)
        if branch is not None:
            return branch
    return _current_branch() if not candidates else None


def _positional_arguments(tokens: list[str]) -> list[str]:
    """Drop flags from one push's token list, INCLUDING the separate-token
    value of an option that takes one (`_PUSH_VALUE_OPTS`).

    Dropping the flag alone left its value behind as a positional, which then
    read as the remote and pushed the real remote into the refspec slot — so
    `git push -o ci.skip origin` from main looked like it carried a refspec
    (`origin`), skipped the refspec-less branch check, and was allowed."""
    positionals: list[str] = []
    skip_value = False
    for token in tokens:
        if skip_value:
            skip_value = False
            continue
        if token.startswith("-"):
            skip_value = token in _PUSH_VALUE_OPTS
            continue
        positionals.append(token)
    return positionals


_BRANCH_CACHE: dict[str | None, str | None] = {}


def _current_branch(cwd: str | None = None) -> str | None:
    """The checked-out branch in `cwd` (the session's own directory), NOT in
    whatever directory this hook process happens to be running from — those
    differ whenever the session works in a linked worktree, and getting it
    wrong fails open there.

    Tri-state on purpose: a branch name, or None for "could not determine".
    Callers collapse None to "not protected" (fail-open, per this hook's
    stated posture) — which is exactly why every None path here has to be
    audible on stderr rather than silent."""
    # Memoised per cwd. A command can carry several pushes and each one resolves
    # a branch, so without this the subprocess count is unbounded by the INPUT —
    # `git push a && git push b && ...` multiplies it — and no fixed entry in
    # `_dispatch_lib.HOOK_WORST_CASE_SECONDS` could be honest about the cost.
    # HEAD cannot move mid-hook, so caching is safe as well as cheap.
    if cwd in _BRANCH_CACHE:
        return _BRANCH_CACHE[cwd]
    try:
        result = subprocess.run(
            ["git", *(["-C", cwd] if cwd else []), "rev-parse", "--abbrev-ref", "HEAD"],
            # 3s bounds a WEDGED git, not a slow one; `rev-parse` is milliseconds.
            # Charged against the shared handler budget — see
            # `_dispatch_lib.HOOK_WORST_CASE_SECONDS`.
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=3,
        )
    except (OSError, subprocess.SubprocessError):
        # `SubprocessError` covers `TimeoutExpired`. Without the timeout a hung
        # `git rev-parse` (stale index.lock, network FS, credential prompt)
        # would burn the dispatcher's whole budget and take every other
        # guard down with it. Surface the degradation rather than allowing
        # silently — this is the one branch where the hook cannot tell whether
        # a bare push is safe.
        print(
            "[block-direct-push-to-main] warn: could not resolve HEAD (git "
            "unavailable or timed out) — bare-push detection is off for this call.",
            file=sys.stderr,
        )
        _BRANCH_CACHE[cwd] = None
        return None
    if result.returncode != 0:
        # git EXITS 128 here (bad directory, not a repo, dubious ownership,
        # unborn HEAD) far more often than it raises, so this — not the
        # exception branch above — is the common degradation now that the
        # directory is caller-supplied. Returning None silently made it
        # indistinguishable from "you are on a feature branch".
        print(
            f"[block-direct-push-to-main] warn: `git rev-parse` exited "
            f"{result.returncode} in {cwd or 'the hook process cwd'} — "
            "current-branch detection is off for this call.",
            file=sys.stderr,
        )
        _BRANCH_CACHE[cwd] = None
        return None
    branch = (result.stdout or "").strip() or None
    _BRANCH_CACHE[cwd] = branch
    return branch


def _is_direct_push_to_main(command: str, cwd: str | None = None) -> bool:
    """Return True iff ANY `git push` in the command pushes to main/master
    directly. `cwd` is the session's own directory (the hook payload's), used
    for branch resolution unless a push carries its own `-C`/`--work-tree`."""
    scanned = _strip_quoted_spans(command)
    for work_tree, tokens in _push_argument_lists(scanned, command):
        # First positional is the remote; anything after it is a refspec. Flags
        # are dropped — including `--force-with-lease=origin/main`, whose value
        # is not a push destination.
        # `--all` and `--mirror` push EVERY local branch, which necessarily
        # includes the default one, so there is no refspec to inspect and no
        # safe reading of them. `--mirror` additionally deletes remote refs the
        # local repo lacks. Checked before the refspec logic because these carry
        # no destination for it to examine.
        if any(_ALL_BRANCHES_FLAG.fullmatch(t) for t in tokens):
            return True

        positionals = _positional_arguments(tokens)
        # The first positional is ALWAYS the repository, including when `--repo`
        # is present -- git's own docs: `--repo` "is equivalent to the
        # <repository> argument. If both are specified, the command-line argument
        # takes precedence." A rule that treated the first positional as a
        # refspec when `--repo` appeared was added here and reverted, because
        # measuring it against real git showed all three of its premises wrong:
        #
        #   `git push --repo origin main`   git REFUSES: "'main' does not appear
        #                                    to be a git repository" -- so the
        #                                    shape it "closed" never pushed
        #                                    anything.
        #   `git push --repo origin origin` a REAL push of the default branch,
        #                                    which the rule turned from BLOCK
        #                                    into allow.
        #   `git push --repo origin main feature/x`
        #                                    `main` is the REMOTE here, so the
        #                                    rule blocked ordinary work in any
        #                                    repo with a remote so named.
        #
        # `--repo` stays in `_PUSH_VALUE_OPTS` so its value is consumed and
        # cannot pose as a refspec. That is the whole handling it needs.
        refspecs = positionals[1:]

        if refspecs:
            if any(_refspec_touches_main(r, work_tree, cwd) for r in refspecs):
                return True
            continue

        # No refspec (`git push`, `git push --force`, `git push origin`) → the
        # destination is the current branch's upstream.
        if _branch_for(work_tree, cwd) in _PROTECTED:
            return True
    return False


def main() -> int:
    if os.environ.get("ALLOW_PUSH_TO_MAIN") == "1":
        return 0
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        # ValueError also catches a UnicodeDecodeError on stdin. Matches the
        # sibling hooks, which already caught both.
        return 0
    tool_input = payload.get("tool_input", {}) if isinstance(payload, dict) else {}
    command = tool_input.get("command") if isinstance(tool_input, dict) else None
    if not isinstance(command, str):
        return 0
    cwd = payload.get("cwd") if isinstance(payload, dict) else None
    if not isinstance(cwd, str) or not cwd:
        cwd = None
    if not _is_direct_push_to_main(command, cwd):
        return 0
    print(
        # `<branch>`, not a hardcoded `feature/<name>`: this is synced core, and
        # an enforcing hook telling a repo whose convention is e.g.
        # `claude/fix/...` to create a `feature/` branch is instructing it to
        # break its own rules, with no way to correct that downstream.
        "blocked: `git push` targets main/master directly. No direct commits to "
        "the default branch — create a branch first, using this repo's own "
        "naming convention: `git checkout -b <branch>` -> commit -> push -> "
        "open a PR via `gh pr create`. Override for a genuine emergency by "
        "setting `ALLOW_PUSH_TO_MAIN=1` in the environment. "
        "(hook: block-direct-push-to-main.py)",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
