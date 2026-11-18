#!/usr/bin/env python3
"""Check git state around a push: before a branch is made, after a push, and a commit's trailers.

The ship steps used to list git commands and leave the agent to compare their output by eye.
A comparison left to the reader is the step that fails: a branch that already exists gets
reused and its work lost, and a push or a trailer block that "worked" is reported when it did
not. This script makes each comparison and states the verdict in its exit code::

    python3 "${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/ship_check.py" preflight --branch <branch> --base <base-branch> [--pr-base <pr-base>]
    python3 "${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/ship_check.py" pushed --branch <branch>
    python3 "${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/ship_check.py" trailers [--rev HEAD]

It reads git state only. The one write is in ``preflight`` on a branch other than the base or
the target (the rename case): ``git fetch`` of the base into its remote-tracking ref, so the
commit count is taken against the remote's current base.

Every subcommand takes ``--root <dir>`` (default: the working directory) and checks the
checkout there, against the remote ``origin``.

OUTPUT. The first line is the verdict, and its first word is ``OK``, ``FAIL`` or ``UNCHECKED``.
Each later line is one finding: ``PROBLEM <kind>: <detail>`` (the reason for a ``FAIL``) or
``UNCHECKED <kind>: <detail>`` (a check that could not run). Callers read the exit code and the
first line; keep both stable.

EXIT CODES (the same for every subcommand):
  0 = every check ran and passed
  1 = a check found a problem (``PROBLEM`` lines say which); a found problem wins over a check
      that could not run, since it is certain
  2 = no problem found, but a check could not run (not a repository, git missing, the remote
      did not answer, a bad argument). Never a pass: the caller treats it as not verified.

preflight
  Run before a new branch is made. The mode, named on the first line, follows from the branch
  checked out (``--pr-base``, when given, stands in for ``--base`` everywhere):
    on-branch  already on ``--branch``: no collision check (it would find the branch you are on).
    create     on the base: ``refs/heads/<branch>``, ``refs/remotes/origin/<branch>`` and the
               remote's ``refs/heads/<branch>`` (``git ls-remote``, exact ref name) must all be absent.
    rename     on any other branch: the same three, plus ``git rev-list --count
               origin/<base>..HEAD`` must be 0 (no commits to lose) after fetching the base.
               A detached HEAD is a problem here: there is no branch to rename.
  With ``--pr-base``, in every mode: ``<pr-base>@{u}`` must resolve, its remote must be a real
  remote (not ``.``), and its branch must exist on that remote.

pushed
  Run after a push. The checked-out branch must be ``--branch`` (a detached HEAD fails), local
  ``HEAD`` must equal the remote's ``refs/heads/<branch>``, and ``@{u}`` must be set and equal
  ``HEAD``. Any failure prints ``push not verified`` on the first line.

trailers
  Run before a push. The count of message lines starting ``Measured-by:`` must equal the count of
  ``Measured-by`` trailers git parses. Git parses trailers only from the last paragraph, and only
  when every line in it is ``key: value``, so a blank line or a bare line in the block hides all
  of them. ``0`` and ``0`` passes.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import traceback
from pathlib import Path

REMOTE = "origin"
REMOTE_TIMEOUT = 60
TRAILER_KEY = "Measured-by"


class Unchecked(Exception):
    """A check that could not run. Carries (kind, detail)."""

    def __init__(self, kind: str, detail: str) -> None:
        super().__init__(f"{kind}: {detail}")
        self.kind = kind
        self.detail = detail


def _git(root: Path, *args: str, remote: bool = False) -> subprocess.CompletedProcess[str]:
    """Run git in ``root``. Raises Unchecked when git cannot be started or a remote call hangs."""
    env = dict(os.environ)
    if remote:
        # A remote that wants a password would wait on a prompt nobody answers.
        env["GIT_TERMINAL_PROMPT"] = "0"
    try:
        return subprocess.run(
            ["git", *args],
            cwd=root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
            timeout=REMOTE_TIMEOUT if remote else None,
        )
    except FileNotFoundError:
        raise Unchecked("git", "the git binary was not found") from None
    except subprocess.TimeoutExpired:
        raise Unchecked("remote", f"'git {' '.join(args)}' did not finish in {REMOTE_TIMEOUT}s") from None
    except OSError as exc:
        raise Unchecked("git", f"git could not be started: {exc}") from None


def _first_err(r: subprocess.CompletedProcess[str]) -> str:
    text = (r.stderr or r.stdout or "").strip().splitlines()
    return text[0] if text else f"exit {r.returncode}"


def _require_repo(root: Path) -> None:
    if not root.is_dir():
        raise Unchecked("repo", f"{root} is not a directory")
    r = _git(root, "rev-parse", "--git-dir")
    if r.returncode != 0:
        raise Unchecked("repo", f"{root} is not a git repository: {_first_err(r)}")


def _current_branch(root: Path) -> str | None:
    """The checked-out branch's short name, or None on a detached HEAD."""
    r = _git(root, "symbolic-ref", "--quiet", "HEAD")
    if r.returncode == 1:
        return None
    if r.returncode != 0:
        raise Unchecked("branch", f"git symbolic-ref HEAD failed: {_first_err(r)}")
    ref = r.stdout.strip()
    return ref[len("refs/heads/"):] if ref.startswith("refs/heads/") else ref


def _ref_exists(root: Path, ref: str) -> bool:
    r = _git(root, "rev-parse", "--verify", "--quiet", ref)
    return r.returncode == 0 and bool(r.stdout.strip())


def _remote_sha(root: Path, remote: str, ref: str) -> str | None:
    """The sha the remote holds for exactly ``ref``, or None when it has no such ref.

    ``git ls-remote`` matches its pattern against the tail of each ref name, so
    ``refs/heads/x`` alone could also list ``refs/heads/a/refs/heads/x``; only an exact name
    counts. A non-zero exit means the remote did not answer, which is Unchecked, never absent.
    """
    r = _git(root, "ls-remote", remote, ref, remote=True)
    if r.returncode != 0:
        raise Unchecked("remote", f"'git ls-remote {remote} {ref}' failed: {_first_err(r)}")
    for line in r.stdout.splitlines():
        parts = line.split("\t", 1)
        if len(parts) == 2 and parts[1].strip() == ref:
            return parts[0].strip()
    return None


def _rev(root: Path, rev: str) -> str | None:
    r = _git(root, "rev-parse", "--verify", "--quiet", f"{rev}^{{commit}}")
    return r.stdout.strip() if r.returncode == 0 and r.stdout.strip() else None


class Findings:
    """PROBLEM lines and UNCHECKED lines from one run. A check that cannot run is recorded and the
    others still run, so a problem found before or after it is not lost."""

    def __init__(self) -> None:
        self.problems: list[str] = []
        self.unchecked: list[str] = []

    def problem(self, kind: str, detail: str) -> None:
        self.problems.append(f"PROBLEM {kind}: {detail}")

    def attempt(self, check, *args):
        """Run ``check(*args)``; on Unchecked record it and return None."""
        try:
            return check(*args)
        except Unchecked as exc:
            self.unchecked.append(f"UNCHECKED {exc.kind}: {exc.detail}")
            return None


# ---------------------------------------------------------------- preflight


def _collisions(root: Path, branch: str, out: Findings) -> None:
    if _ref_exists(root, f"refs/heads/{branch}"):
        out.problem("local-branch", f"refs/heads/{branch} exists locally")
    if _ref_exists(root, f"refs/remotes/{REMOTE}/{branch}"):
        out.problem(
            "remote-tracking",
            f"refs/remotes/{REMOTE}/{branch} exists (a stale one goes with 'git fetch --prune {REMOTE}')",
        )
    found = out.attempt(_remote_sha, root, REMOTE, f"refs/heads/{branch}")
    if found:
        out.problem("remote-branch", f"{REMOTE} has refs/heads/{branch}")


def _upstream_on_remote(root: Path, pr_base: str, out: Findings) -> None:
    r = _git(root, "rev-parse", "--abbrev-ref", f"{pr_base}@{{u}}")
    if r.returncode != 0 or not r.stdout.strip():
        out.problem("no-upstream", f"{pr_base} has no upstream ({_first_err(r)}); push the parent first")
        return
    upstream = r.stdout.strip()
    r = _git(
        root, "for-each-ref", "--format=%(upstream:remotename)%00%(upstream:remoteref)",
        f"refs/heads/{pr_base}",
    )
    fields = r.stdout.strip().split("\x00") if r.returncode == 0 else []
    if len(fields) != 2 or not fields[0] or not fields[1]:
        raise Unchecked("upstream", f"could not read the remote and ref of {pr_base}'s upstream {upstream}")
    remote, ref = fields
    if remote == ".":
        out.problem("upstream-not-remote", f"{pr_base} tracks the local {ref}, not a branch on a remote")
        return
    if _remote_sha(root, remote, ref) is None:
        out.problem("upstream-missing", f"{pr_base}'s upstream {upstream} is not on {remote} ({ref} is absent)")


def _commits_to_lose(root: Path, base: str, out: Findings) -> None:
    fetch = _git(
        root, "fetch", "--quiet", REMOTE, f"+refs/heads/{base}:refs/remotes/{REMOTE}/{base}", remote=True,
    )
    if fetch.returncode != 0:
        raise Unchecked("remote", f"'git fetch {REMOTE} {base}' failed: {_first_err(fetch)}")
    count = _git(root, "rev-list", "--count", f"refs/remotes/{REMOTE}/{base}..HEAD")
    if count.returncode != 0 or not count.stdout.strip().isdigit():
        raise Unchecked("commits", f"'git rev-list --count {REMOTE}/{base}..HEAD' failed: {_first_err(count)}")
    n = int(count.stdout.strip())
    if n != 0:
        out.problem("commits-to-lose", f"HEAD has {n} commit(s) not on {REMOTE}/{base}")


def preflight(root: Path, branch: str, base: str, pr_base: str | None, out: Findings) -> str:
    """Run the checks for the mode the checked-out branch selects; return the mode."""
    base = pr_base or base
    if pr_base:
        out.attempt(_upstream_on_remote, root, pr_base, out)
    current = _current_branch(root)
    if current == branch:
        return "on-branch"
    _collisions(root, branch, out)
    if current == base:
        return "create"
    if current is None:
        out.problem("detached", "HEAD is detached, so there is no branch to rename")
    out.attempt(_commits_to_lose, root, base, out)
    return "rename"


# ---------------------------------------------------------------- pushed


def pushed(root: Path, branch: str, out: Findings) -> None:
    current = _current_branch(root)
    if current is None:
        out.problem("detached", f"HEAD is detached, expected branch {branch}")
    elif current != branch:
        out.problem("wrong-branch", f"on {current}, expected {branch}")
    head = _rev(root, "HEAD")
    if head is None:
        raise Unchecked("head", "HEAD names no commit")
    asked = len(out.unchecked)
    remote = out.attempt(_remote_sha, root, REMOTE, f"refs/heads/{branch}")
    if len(out.unchecked) == asked:  # the remote answered
        if remote is None:
            out.problem("remote-missing", f"{REMOTE} has no refs/heads/{branch}")
        elif remote != head:
            out.problem("remote-differs", f"HEAD is {head}, {REMOTE} refs/heads/{branch} is {remote}")
    upstream = _rev(root, "@{u}")
    if upstream is None:
        out.problem("no-upstream", "@{u} is not set for the checked-out branch")
    elif upstream != head:
        out.problem("upstream-differs", f"HEAD is {head}, @{{u}} is {upstream}")


# ---------------------------------------------------------------- trailers


def trailers(root: Path, rev: str) -> tuple[int, int]:
    """(lines written as ``Measured-by:``, trailers git parses with that key)."""
    if _rev(root, rev) is None:
        raise Unchecked("rev", f"{rev!r} names no commit")
    body = _git(root, "log", "-1", "--format=%B", rev, "--")
    parsed = _git(root, "log", "-1", f"--format=%(trailers:key={TRAILER_KEY},unfold=true)", rev, "--")
    for r in (body, parsed):
        if r.returncode != 0:
            raise Unchecked("log", f"git log failed: {_first_err(r)}")
    written = sum(1 for line in body.stdout.splitlines() if line.startswith(f"{TRAILER_KEY}:"))
    seen = sum(1 for line in parsed.stdout.splitlines() if line.strip())
    return written, seen


# ---------------------------------------------------------------- main


def _report(first: str, lines: list[str]) -> None:
    print(first)
    for line in lines:
        print(line)


def main(argv: list[str] | None = None) -> int:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--root", default=".", help="the checkout to check (default: the working directory)")
    ap = argparse.ArgumentParser(description="Check git state around a push. Exit 0 pass, 1 problem, 2 could not check.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("preflight", parents=[common], help="before a new branch is made")
    p.add_argument("--branch", required=True, help="the branch about to be made")
    p.add_argument("--base", help="the repo's default branch, resolved")
    p.add_argument("--pr-base", help="the branch this change is built on and opened against, when stacked")
    p = sub.add_parser("pushed", parents=[common], help="after a push")
    p.add_argument("--branch", required=True, help="the branch that was pushed")
    p = sub.add_parser("trailers", parents=[common], help="before a push: Measured-by lines against git's parse")
    p.add_argument("--rev", default="HEAD", help="the commit to read (default: HEAD)")
    args = ap.parse_args(argv)

    if args.cmd == "preflight" and not (args.base or args.pr_base):
        print("UNCHECKED preflight: pass --base <base-branch> (or --pr-base <pr-base>)")
        return 2

    root = Path(args.root).resolve()
    label = "push not verified: " if args.cmd == "pushed" else ""
    out = Findings()
    try:
        _require_repo(root)
        if args.cmd == "trailers":
            written, seen = trailers(root, args.rev)
            counts = f"{written} written as '{TRAILER_KEY}:', {seen} parsed by git"
            if written != seen:
                _report(
                    f"FAIL trailers: {counts}",
                    ["PROBLEM trailers: the trailer block is split; a blank line or a line that is not "
                     "'key: value' in the last paragraph hides the trailers. Fix with git commit --amend"],
                )
                return 1
            _report(f"OK trailers: {counts}", [])
            return 0
        if args.cmd == "preflight":
            mode = preflight(root, args.branch, args.base, args.pr_base, out)
            name, ok = f"preflight {mode}", f"OK preflight {mode}: {args.branch}"
        else:
            pushed(root, args.branch, out)
            name, ok = "push not verified", f"OK pushed: {args.branch} at {_rev(root, 'HEAD')}"
    except Unchecked as exc:
        out.unchecked.append(f"UNCHECKED {exc.kind}: {exc.detail}")
        if not out.problems:
            _report(f"UNCHECKED {label}{exc.kind}: {exc.detail}", [])
            return 2
        name = "push not verified" if args.cmd == "pushed" else "preflight"
    except Exception as exc:  # noqa: BLE001 - a crash must read as "could not check", never as a verdict
        _report(f"UNCHECKED {label}error: unexpected {type(exc).__name__}: {exc}", [])
        print(traceback.format_exc(), file=sys.stderr)
        return 2
    if out.problems:
        _report(f"FAIL {name}: {len(out.problems)} problem(s)", out.problems + out.unchecked)
        return 1
    if out.unchecked:
        first = out.unchecked[0][len("UNCHECKED "):]
        _report(f"UNCHECKED {label}{first}", out.unchecked[1:])
        return 2
    _report(ok, [])
    return 0


if __name__ == "__main__":
    sys.exit(main())
