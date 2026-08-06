#!/usr/bin/env python3
r"""PreToolUse hook: block direct `git push` to main/master.

Convention: no direct commits to the default branch — use feature branches.
A retroactive paperwork-PR after the fact is structurally impossible (GitHub
refuses no-diff PRs), so the only fix is to prevent the push at the moment it
would happen.

Three verdicts, not two
-----------------------
This guard used to be binary: BLOCK, or allow. Every uncertainty — an alias, a
global-option shape outside the matcher's closed set, git being unusable so
HEAD could not be resolved — collapsed into *allow*, i.e. a SILENT BYPASS,
which for a guard is the worst available failure mode (indistinguishable from
"checked and found it safe").

It now returns one of three:

  BLOCK  the push provably targets a protected branch      -> exit 2
  ALLOW  no push to a protected branch found               -> exit 0
  ASK    a push was found but could NOT be fully resolved  -> exit 0 +
         `permissionDecision: "ask"` on stdout

ASK routes the uncertain cases to the user's own permission prompt (one
keystroke) instead of waving them through. That option only exists because the
dispatcher already understands the `ask` shape — see `ask-destructive-git.py`
and `dispatch-bash-pretooluse.py::_extract_ask`; it did not when this hook was
first written.

Parsing: two layers, both exact
-------------------------------
Previously one regex layer did double duty as a shell lexer AND a git argument
parser, coupled by an unchecked invariant (`strip_quoted_spans` had to be
length-preserving so match offsets could be re-sliced against the raw command).
Now:

  1. `shlex` tokenizes for real — quotes, and `&&`/`||`/`;`/`|` as genuine
     separators. Quote stripping comes free, so no placeholder-fill pass and no
     offset arithmetic.
  2. A table-driven walk consumes git's global options and finds the
     subcommand. An option shape outside the table no longer silently
     mis-parses the command.

This hook therefore imports nothing from `_dispatch_lib` any more — it is
stdlib-only, one fewer coupling point for a blocking guard.

`lexer.escape` is disabled deliberately: in POSIX mode shlex treats a backslash
as an escape character, so a Windows drive path passed to `-C` tokenized with
its separators silently stripped, and the current branch would then resolve in
the WRONG directory — the exact bug class `_branch_for` was fixed for. Windows
is this harness's primary platform, so a literal backslash matters far more
here than POSIX backslash-escaped spaces.

Blocked shapes
--------------
  - `git push <remote> main` / `master`, `HEAD:main`, `<branch>:main`,
    `main:<branch>` (pushing the default branch's content out)
  - `refs/heads/main` (fully qualified), `+main` (force refspec), `:main`
    (deleting the remote default branch), `"main"` / `'main'` (quoted)
  - the same with `--force` / `-f` / `--force-with-lease`
  - `git push` / `git push <remote>` with NO refspec, when HEAD is main/master
  - `git push <remote> HEAD` / `@` (either side of a pair) when HEAD is
    main/master
  - any of the above behind git global options (`-c`, `-C`, `--work-tree`,
    `--git-dir`, …), after a shell separator, or behind a `NAME=VALUE` env
    prefix (`GIT_DIR=/x git push origin main`)
  - `git push -o ci.skip <remote>` from main — a separate-token option value is
    consumed, so it cannot pose as a refspec and suppress the bare-push check

Asked (previously silent allows, except where noted)
----------------------------------------------------
  - an unrecognized subcommand near a protected branch name — i.e. a possible
    alias. Deliberately NOT resolved via `git config --get alias.<name>`: the
    Bash dispatcher's enforcing hooks already sum to 12.0s of a 13.5s budget
    (`_dispatch_lib.HOOK_WORST_CASE_SECONDS`), so a second subprocess would
    break `test_hooks_wiring.py`. Asking costs nothing and closes the gap.
  - a heredoc body containing a push to a protected branch. `cat <<EOF > f.sh`
    merely writes a file, but `bash <<EOF` EXECUTES it, and telling the two
    apart means parsing what consumes the heredoc. (This shape used to be a
    hard BLOCK — a false positive when the body was only being written out.)
  - a `HEAD` refspec, or a bare push, whose current branch could not be
    resolved (git missing, timed out, or exited non-zero)
  - a command `shlex` could not lex that still mentions a push and a protected
    branch name

Allowed
-------
  - `git push -u origin feature/...` (any non-protected destination)
  - branch names that merely START with main/master — `main-refactor`,
    `master-list`, `main.old`, `maintenance` — compared as whole refs
  - `git push` with no refspec when the current branch is not protected
  - anything when `ALLOW_PUSH_TO_MAIN=1` is set (escape hatch for the rare
    legitimate case, e.g. an admin restoring after a force-push)

Known remaining gap, stated rather than implied: a push whose target is built
by shell interpolation (`git push $REMOTE $BRANCH`) is allowed — the value is
not knowable without running the shell. Unchanged from the previous design.

Exit codes:
  0 — allow, or ask (the ask travels as stdout JSON)
  2 — block, with stderr explaining the rule
"""

from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import sys

BLOCK, ALLOW, ASK = "BLOCK", "ALLOW", "ASK"

_PROTECTED = ("main", "master")

# Positional refspecs that MEAN the current branch rather than naming a ref.
_HEAD_ALIASES = ("HEAD", "@")

# git GLOBAL options taking a SEPARATE-token value. A table, not a regex
# alternation: an entry here is a fact about git's CLI, and an unknown option
# now degrades to a miss rather than silently swallowing the subcommand token.
_GLOBAL_VALUE_OPTS = frozenset({
    "-c", "-C", "--git-dir", "--work-tree", "--namespace",
    "--super-prefix", "--exec-path",
})
# The subset of those that select which repository the command acts on.
_DIR_OPTS = frozenset({"-C", "--work-tree", "--git-dir"})

# `git push` options whose value is a SEPARATE token. Dropping the flag alone
# leaves its value behind as a phantom positional, which reads as a refspec and
# suppresses the refspec-less branch check — so `git push -o ci.skip origin`
# from main was allowed.
_PUSH_VALUE_OPTS = frozenset({
    "-o", "--push-option", "--receive-pack", "--exec", "--repo",
})

# Recognized git subcommands. Anything else sitting where a subcommand belongs
# may be a user alias — which could expand to a push. Not exhaustive by intent:
# a miss costs an ASK, never a silent allow.
_KNOWN_SUBCOMMANDS = frozenset({
    "push", "commit", "checkout", "switch", "status", "add", "log", "diff",
    "fetch", "pull", "merge", "rebase", "reset", "branch", "tag", "remote",
    "stash", "show", "config", "init", "clone", "rev-parse", "worktree",
    "cherry-pick", "restore", "describe", "ls-remote", "for-each-ref",
    "apply", "am", "bisect", "blame", "clean", "gc", "grep", "mv", "notes",
    "reflog", "revert", "rm", "shortlog", "submodule", "symbolic-ref",
})

_SEPARATORS = frozenset({"&&", "||", ";", "|", "&", "\n"})

_ENV_PREFIX = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
_PUSH_IN_BODY = re.compile(r"\bgit\b[^\n]*\bpush\b")
_HEREDOC_START = re.compile(r"<<-?\s*'?\"?(\w+)'?\"?")


def _strip_heredocs(command: str) -> tuple[str, bool]:
    """Remove heredoc bodies. Returns (stripped_command, body_has_protected_push).

    A heredoc body is not reliably inert: `cat <<EOF > f.sh` writes a file,
    `bash <<EOF` runs it. Rather than guess which, report whether the body
    contains a push to a protected branch and let the caller route that to ASK.
    """
    m = _HEREDOC_START.search(command)
    if not m:
        return command, False
    tag = m.group(1)
    rest = command[m.end():]
    end = re.search(rf"^\s*{re.escape(tag)}\s*$", rest, re.MULTILINE)
    body = rest[: end.start()] if end else rest
    risky = bool(_PUSH_IN_BODY.search(body)) and any(p in body for p in _PROTECTED)
    if end:
        return command[: m.start()] + command[m.end() + end.end():], risky
    return command[: m.start()], risky


def _segments(command: str) -> tuple[list[list[str]], bool]:
    """Split a command line into per-command token lists. Returns (segments, ok).

    `ok` is False when the text could not be lexed at all (an unbalanced quote),
    which the caller treats as uncertainty rather than absence.
    """
    try:
        lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
        lexer.whitespace_split = True
        lexer.escape = ""  # see module docstring: Windows paths, not POSIX escapes
        tokens = list(lexer)
    except ValueError:
        return [], False

    segments: list[list[str]] = []
    current: list[str] = []
    for token in tokens:
        if token in _SEPARATORS or (token and set(token) <= {"&", "|", ";"}):
            if current:
                segments.append(current)
            current = []
        else:
            current.append(token)
    if current:
        segments.append(current)
    return segments, True


def _parse_git(tokens: list[str]) -> tuple[str | None, str | None, list[str]] | None:
    """Return (subcommand, dir_override, remaining_args) for a git invocation.

    None when these tokens are not a git command at all. `dir_override` is the
    LAST `-C`/`--work-tree`/`--git-dir` value seen, so repeated options compose
    the way git applies them rather than first-match-wins.
    """
    start = 0
    # Leading `NAME=VALUE` env assignments are part of the shell invocation, not
    # the command — `GIT_DIR=/x git push origin main` is still a git push.
    while start < len(tokens) and _ENV_PREFIX.match(tokens[start]):
        start += 1
    tokens = tokens[start:]
    if not tokens or os.path.basename(tokens[0]) != "git":
        return None

    i = 1
    dir_override: str | None = None
    while i < len(tokens):
        token = tokens[i]
        if not token.startswith("-"):
            return token, dir_override, tokens[i + 1:]
        if "=" in token:
            name, _, value = token.partition("=")
            if name in _DIR_OPTS:
                dir_override = value
            i += 1
            continue
        if token in _GLOBAL_VALUE_OPTS:
            if i + 1 < len(tokens):
                if token in _DIR_OPTS:
                    dir_override = tokens[i + 1]
                i += 2
                continue
            return None, dir_override, []
        i += 1
    return None, dir_override, []


def _positional_arguments(tokens: list[str]) -> list[str]:
    """Drop flags from one push's token list, INCLUDING the separate-token value
    of an option that takes one (`_PUSH_VALUE_OPTS`)."""
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


def _normalize_ref(ref: str) -> str:
    """Reduce one side of a refspec to a bare branch name for comparison."""
    ref = ref.lstrip("+")
    if ref.startswith("refs/heads/"):
        ref = ref[len("refs/heads/"):]
    return ref


_BRANCH_CACHE: dict[str | None, str | None] = {}


def _current_branch(cwd: str | None = None) -> str | None:
    """The checked-out branch in `cwd` (the session's own directory), NOT in
    whatever directory this hook process happens to be running from — those
    differ whenever the session works in a linked worktree.

    Tri-state on purpose: a branch name, or None for "could not determine".
    None now routes to ASK rather than a silent allow, but every None path is
    still audible on stderr — a degraded guard should say so."""
    # Memoised per cwd. A command can carry several pushes and each one resolves
    # a branch, so without this the subprocess count is unbounded by the INPUT
    # and no fixed entry in `_dispatch_lib.HOOK_WORST_CASE_SECONDS` could be
    # honest. HEAD cannot move mid-hook, so caching is safe as well as cheap.
    if cwd in _BRANCH_CACHE:
        return _BRANCH_CACHE[cwd]
    try:
        result = subprocess.run(
            ["git", *(["-C", cwd] if cwd else []), "rev-parse", "--abbrev-ref", "HEAD"],
            # 3s bounds a WEDGED git, not a slow one; `rev-parse` is milliseconds.
            # Charged against the shared handler budget — see
            # `_dispatch_lib.HOOK_WORST_CASE_SECONDS`.
            capture_output=True, text=True, timeout=3,
        )
    except (OSError, subprocess.SubprocessError):
        # `SubprocessError` covers `TimeoutExpired`. Without the timeout a hung
        # `git rev-parse` (stale index.lock, network FS, credential prompt)
        # would burn the dispatcher's whole budget and take every other guard
        # down with it.
        print(
            "[block-direct-push-to-main] warn: could not resolve HEAD (git "
            "unavailable or timed out) — bare-push detection falls back to a prompt.",
            file=sys.stderr,
        )
        _BRANCH_CACHE[cwd] = None
        return None
    if result.returncode != 0:
        # git EXITS 128 here (bad directory, not a repo, dubious ownership,
        # unborn HEAD) far more often than it raises, so this — not the
        # exception branch above — is the common degradation now that the
        # directory is caller-supplied.
        print(
            f"[block-direct-push-to-main] warn: `git rev-parse` exited "
            f"{result.returncode} in {cwd or 'the hook process cwd'} — "
            "current-branch detection falls back to a prompt for this call.",
            file=sys.stderr,
        )
        _BRANCH_CACHE[cwd] = None
        return None
    branch = (result.stdout or "").strip() or None
    _BRANCH_CACHE[cwd] = branch
    return branch


def _branch_for(work_tree: str | None, session_cwd: str | None) -> str | None:
    """Resolve the current branch for one push, preferring the directory the
    command itself names and falling back to the session's.

    - **A relative `-C` is composed against the session directory**, the way the
      shell would. Passed through raw it resolved against whatever cwd the hook
      PROCESS happens to have — reintroducing, for relative paths, the exact
      wrong-directory bug this hook was fixed for.
    - **A failed command-derived path falls back to the session directory**
      rather than straight to "unknown". A scraped `-C` value is far likelier to
      be wrong than the payload's own cwd."""
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


def _push_verdict(command: str, cwd: str | None = None) -> tuple[str, str]:
    """Classify `command` as BLOCK / ALLOW / ASK, with a human reason.

    `cwd` is the session's own directory (the hook payload's), used for branch
    resolution unless a push carries its own `-C`/`--work-tree`/`--git-dir`.
    """
    stripped, heredoc_risky = _strip_heredocs(command)
    if heredoc_risky:
        return ASK, (
            "a heredoc body contains a `git push` to a protected branch. If it is "
            "being written to a file this is harmless; if it is piped to a shell "
            "(`bash <<EOF`) it would push to the default branch"
        )

    segments, lexed = _segments(stripped)
    if not lexed:
        if "push" in command and any(p in command for p in _PROTECTED):
            return ASK, (
                "this command could not be parsed (unbalanced quote?) and mentions "
                "both a push and a protected branch name"
            )
        return ALLOW, "unparseable, but no push to a protected branch is apparent"

    saw_unknown_subcommand = False
    for tokens in segments:
        parsed = _parse_git(tokens)
        if parsed is None:
            continue
        subcommand, dir_override, args = parsed
        if subcommand is None:
            continue
        if subcommand != "push":
            if subcommand not in _KNOWN_SUBCOMMANDS:
                saw_unknown_subcommand = True
            continue

        # First positional is the remote; anything after it is a refspec.
        refspecs = _positional_arguments(args)[1:]

        if refspecs:
            for spec in refspecs:
                sides = spec.split(":") if ":" in spec else [spec]
                normalized = [_normalize_ref(s) for s in sides]
                # The literal comparison runs FIRST and needs no subprocess, so
                # the common offense (`git push origin main`) stays decidable
                # even when git itself is unusable.
                if any(side in _PROTECTED for side in normalized):
                    return BLOCK, f"refspec {spec!r} targets the default branch"
                if any(side in _HEAD_ALIASES for side in normalized):
                    branch = _branch_for(dir_override, cwd)
                    if branch is None:
                        return ASK, (
                            f"refspec {spec!r} refers to HEAD, and the current branch "
                            "could not be resolved to check whether it is protected"
                        )
                    if branch in _PROTECTED:
                        return BLOCK, f"HEAD resolves to {branch!r}"
            continue

        # No refspec (`git push`, `git push --force`, `git push origin`) → the
        # destination is the current branch's upstream.
        branch = _branch_for(dir_override, cwd)
        if branch is None:
            return ASK, (
                "this is a bare `git push` and the current branch could not be "
                "resolved to check whether it is protected"
            )
        if branch in _PROTECTED:
            return BLOCK, f"a bare push from {branch!r} targets the default branch"

    if saw_unknown_subcommand and any(p in command for p in _PROTECTED):
        return ASK, (
            "this command uses an unrecognized git subcommand — possibly an alias "
            "that expands to a push — and mentions a protected branch name"
        )
    return ALLOW, "no push to a protected branch found"


def _is_direct_push_to_main(command: str, cwd: str | None = None) -> bool:
    """True iff `command` provably pushes to a protected branch.

    Compatibility surface kept for the existing test suite, which is this
    hook's specification. It is LOSSY by construction — it cannot express ASK,
    and collapses it to False — so production code calls `_push_verdict`.
    """
    return _push_verdict(command, cwd)[0] == BLOCK


def main() -> int:
    if os.environ.get("ALLOW_PUSH_TO_MAIN") == "1":
        return 0
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        # ValueError also catches a UnicodeDecodeError on stdin.
        return 0
    tool_input = payload.get("tool_input", {}) if isinstance(payload, dict) else {}
    command = tool_input.get("command") if isinstance(tool_input, dict) else None
    if not isinstance(command, str):
        return 0
    cwd = payload.get("cwd") if isinstance(payload, dict) else None
    if not isinstance(cwd, str) or not cwd:
        cwd = None

    verdict, reason = _push_verdict(command, cwd)

    if verdict == BLOCK:
        print(
            f"blocked: {reason}. No direct commits to the default branch — "
            "create a feature branch first: `git checkout -b feature/<name>` -> "
            "commit -> push -> open a PR via `gh pr create`. Override for a "
            "genuine emergency by setting `ALLOW_PUSH_TO_MAIN=1` in the "
            "environment. (hook: block-direct-push-to-main.py)",
            file=sys.stderr,
        )
        return 2

    if verdict == ASK:
        # Exit 0 + stdout JSON: the dispatcher re-emits this as the call's
        # permission decision (see `dispatch-bash-pretooluse.py::_extract_ask`).
        # A non-zero exit would discard stdout and lose the escalation.
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "ask",
                "permissionDecisionReason": (
                    f"Possible direct push to the default branch: {reason}. "
                    "Confirm this is what you intend. (Set ALLOW_PUSH_TO_MAIN=1 to "
                    "skip this prompt; hook: block-direct-push-to-main.py)"
                ),
            }
        }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
