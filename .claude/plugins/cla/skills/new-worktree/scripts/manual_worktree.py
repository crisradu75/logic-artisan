#!/usr/bin/env python3
"""Create an isolation worktree with plain git, bypassing the `EnterWorktree` tool.

Why this exists
---------------
On Windows, `EnterWorktree` can refuse to run with:

    Refusing to use <path> as an isolation worktree: git resolves its working
    tree to <same path, different letter case> ...

The two paths name the SAME directory. The harness compares the session's
launch-time project path against git's own resolution of it as literal strings,
and on a case-insensitive filesystem those can differ purely in casing — a repo
whose real directory name is capitalised, reached through an all-lowercase path,
produces one spelling of each. `core.ignorecase` being correctly `true` does not
help: the comparison never asks git.

Nothing in the repo can fix that; it is harness-side. But plain `git worktree`
is entirely unaffected — git resolves the paths properly — so the fallback is to
do the same work directly, which is what this script does.

What it does NOT do
-------------------
Dependency installs, env-file copying, and any other per-repo setup are
deliberately absent. Those differ per repo and belong in the calling skill plus
its `cla.io/overlays/new-worktree.md` overlay, not in portable core.

The isolation guarantee is different too, and the caller must know it: a session
that entered via `EnterWorktree` has its file operations redirected into the
worktree automatically. A manually created worktree gets none of that — the
session is still rooted in the primary clone, so every subsequent path must
target the worktree explicitly. `block-worktree-path-escape.py` cannot help
either: it only fires for a session whose cwd IS the worktree.

Exit codes: 0 on success, 1 on failure. Output is JSON on stdout either way —
the created worktree's details on success, an `error` object on failure.
"""

from __future__ import annotations

import argparse
import errno
import json
import os
import subprocess
import sys
from pathlib import Path

# Bounded like every other subprocess in this plugin. `git worktree add` copies a
# checkout, so it gets materially longer than the `rev-parse` calls elsewhere.
GIT_TIMEOUT_SECONDS = 120
DEFAULT_WORKTREE_DIR = ".claude/worktrees"
DEFAULT_BRANCH_PREFIX = "worktree-"


class GitError(RuntimeError):
    """A git operation could not be completed.

    Usually a failed invocation, in which case the message carries git's own
    stderr. Also raised for a precondition this script checks itself (an
    existing branch, a dirty worktree) — those carry an explanation and the
    command that resolves them instead.
    """


def run_git(repo: Path, args: list[str], check: bool = True) -> subprocess.CompletedProcess:
    try:
        proc = subprocess.run(
            ["git", "-C", str(repo), *args],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=GIT_TIMEOUT_SECONDS,
        )
    except OSError as exc:
        # Every OSError, not just FileNotFoundError: a PermissionError or
        # NotADirectoryError from the spawn would otherwise escape main()'s
        # `except GitError` as a traceback, breaking this module's documented
        # promise of JSON-on-stdout and leaving the calling skill with output it
        # cannot parse. FileNotFoundError is itself an OSError, so the
        # git-is-missing wording stays available for the case that means it.
        if isinstance(exc, FileNotFoundError):
            raise GitError(f"git is not available: {exc}") from exc
        raise GitError(f"could not run git in {repo}: {exc}") from exc
    except subprocess.SubprocessError as exc:  # includes TimeoutExpired
        raise GitError(f"git {' '.join(args)} did not complete: {exc}") from exc
    if check and proc.returncode != 0:
        raise GitError(
            f"git {' '.join(args)} failed ({proc.returncode}): "
            f"{(proc.stderr or proc.stdout).strip()}"
        )
    return proc


def casing_mismatch(repo: Path) -> dict | None:
    """Classify how `repo` as given differs from its real on-disk path.

    Returns None only when they are identical. Otherwise a dict with a `kind`:

    - ``case_only`` — the same directory spelled with different letter case.
      This is the shape that makes `EnterWorktree` refuse.
    - ``path_indirection`` — resolves somewhere else entirely (a symlink,
      junction, or `subst` drive). NOT the casing bug, but reported rather than
      discarded: it is a plausible cause of the same class of refusal, and a
      diagnostic that answers `null` while holding proof the paths differ is
      worse than useless — the reader concludes their paths are clean.

    This detects the mismatch as a PROXY, comparing `abspath` against
    `realpath`, rather than performing the harness's own comparison (which we
    cannot see). A caller that passes the true-cased path gets None even though
    the harness's stored session path may still be lowercase.

    Platform limit worth stating: `os.path.realpath` canonicalises letter case
    only on Windows. On a case-insensitive POSIX filesystem (macOS APFS by
    default) it resolves symlinks and leaves case alone, so `case_only` cannot
    be detected there even though the underlying refusal can still occur.
    """
    as_given = os.path.abspath(str(repo))
    resolved = os.path.realpath(str(repo))
    if as_given == resolved:
        return None
    if as_given.lower() != resolved.lower():
        return {
            "kind": "path_indirection",
            "as_given": as_given,
            "on_disk": resolved,
            "explanation": (
                "This path resolves to a different location (symlink, junction, "
                "or substituted drive). That is not the letter-case bug, but it "
                "can produce a similar refusal — worth knowing before you dig."
            ),
        }
    return {
        "kind": "case_only",
        "as_given": as_given,
        "on_disk": resolved,
        "explanation": (
            "These name the same directory but differ in letter case. "
            "EnterWorktree compares such paths as literal strings, so it refuses. "
            "Plain `git worktree` is unaffected; this script uses it directly."
        ),
    }


def validate_name(name: str) -> str:
    """Reject a name that would place the worktree outside the intended dir.

    `--name ../../elsewhere` would otherwise resolve out of `.claude/worktrees`,
    and `clean_stale_worktree` would then be pointed at a directory nobody meant
    to touch. A worktree name is a single path segment; anything else is a bug
    or an attack, and neither deserves the benefit of the doubt.
    """
    if not name or name in (".", ".."):
        raise GitError("--name must be a non-empty directory name")
    if os.path.sep in name or (os.path.altsep and os.path.altsep in name):
        raise GitError(f"--name must be a single path segment, not {name!r}")
    if os.path.isabs(name) or os.path.splitdrive(name)[0]:
        raise GitError(f"--name must be relative, not {name!r}")
    return name


def validate_worktree_dir(worktree_dir: str, pathmod=os.path) -> str:
    """The same containment rule as `validate_name`, for the sibling argument.

    `create_worktree` builds `repo / worktree_dir / name`, and `Path` join
    discards everything to the left of an absolute component, so the repo prefix
    is gone. `--name` was hardened against exactly this and the argument beside
    it was not, so a traversing value simply moved one flag over.

    Three checks, because on Windows each catches a shape the others miss —
    measured on CPython 3.13.12, with the resulting join shown:

        '/rooted/path'      isabs False  drive ''    joined -> \\rooted\\path
        'D:/elsewhere/tmp'  isabs True   drive 'D:'  joined -> the drive root   # path-fixture-ok
        'D:elsewhere/tmp'   isabs False  drive 'D:'  joined -> drive-relative   # path-fixture-ok

    So `isabs` alone misses both the slash-rooted and the drive-RELATIVE forms
    (3.13 stopped calling a bare leading slash absolute), and `splitdrive` alone
    misses the slash-rooted one. `D:elsewhere/tmp` is the shape only
    `splitdrive` catches, and it still discards the repo at the join.

    `pathmod` EXISTS FOR THE TESTS, and is not decoration. These rules are
    genuinely platform-divergent — `posixpath.splitdrive` is `return p[:0], p`,
    so it reports no drive for anything, and a drive-prefixed value is an
    ordinary relative directory name on POSIX rather than an escape. No CI here,
    so whichever platform the author is not on never runs. Injecting the path
    module lets both platforms' behaviour be pinned from either machine.

    Unlike `--name` this one may contain separators — `.claude/worktrees` is the
    default and is two segments — so only the escaping shapes are rejected.

    THIS CHECK IS LEXICAL, AND CANNOT SEE A FILESYSTEM-LEVEL ESCAPE. Do not read
    a pass here as "the worktree is contained". Accepted today, verified by
    running it: `'.'` (the worktree lands at `<repo>/<name>`, not under
    `.claude/worktrees`), `'.git'` (inside the git directory), `'   '` (Windows
    strips the component, so it resolves to `<repo>/<name>`), and `'a//b'`.
    None of those leave the repo, which is why they are allowed — but a
    directory-alias segment DOES: `clean_stale_worktree` calls
    `os.path.realpath`, so cleanup operates on the resolved target, which a
    junction or symlink can place anywhere. Containing that needs a post-resolve
    check against the repo root, which this function deliberately does not do.

    The backslash in the leading-separator check also refuses a backslash-rooted
    name, legal on POSIX. Deliberate: such a value is an escape on the
    platform this harness primarily runs on, and a leading backslash in a
    worktree directory name is not worth the ambiguity anywhere else.
    """
    if not worktree_dir:
        raise GitError("--worktree-dir must be a non-empty relative path")
    rooted = worktree_dir.startswith(("/", "\\"))
    if rooted or pathmod.isabs(worktree_dir) or pathmod.splitdrive(worktree_dir)[0]:
        raise GitError(f"--worktree-dir must be relative, not {worktree_dir!r}")
    seps = [pathmod.sep] + ([pathmod.altsep] if pathmod.altsep else [])
    segments = [worktree_dir]
    for sep in seps:
        segments = [part for seg in segments for part in seg.split(sep)]
    if ".." in segments:
        raise GitError(
            f"--worktree-dir must stay inside the repo; {worktree_dir!r} traverses out"
        )
    return worktree_dir


def _registered_worktrees(repo: Path) -> set[str]:
    """Absolute paths git currently has registered, realpath-normalised.

    Normalised because the whole point here is that the same directory can be
    spelled two ways; comparing raw strings would reintroduce the bug this
    script exists to route around.
    """
    out = run_git(repo, ["worktree", "list", "--porcelain"]).stdout
    found: set[str] = set()
    for line in out.splitlines():
        if line.startswith("worktree "):
            found.add(os.path.realpath(line[len("worktree "):].strip()))
    return found


def clean_stale_worktree(repo: Path, path: Path) -> bool:
    """Remove a half-created worktree at `path`. Returns True if anything went.

    Observed behaviour this works around: a failed `EnterWorktree` appears to
    register the worktree with git BEFORE its safety check refuses, leaving a
    registered — often locked — entry that blocks the next attempt at the same
    path. That ordering is a claim about closed harness internals which this
    repo cannot verify; the cleanup below is written to be correct either way.

    Two different safety postures, deliberately:
    - A registered worktree is removed only when `git status` says it is CLEAN.
      A dirty one raises instead, because `remove --force` would delete
      uncommitted work and `unlock` first is what lets it.
    - An UNREGISTERED leftover directory is removed only when empty.

    Unlock/remove/prune are each best-effort: any legitimately fails when the
    corresponding state is absent, which is not an error. A failure that is NOT
    that is reported on stderr rather than swallowed.
    """
    target = os.path.realpath(str(path))
    cleaned = False
    failures: list[str] = []

    if target in _registered_worktrees(repo):
        # Refuse to touch a worktree that has work in it. `remove --force`
        # deletes modified tracked files and untracked files alike, and
        # `unlock` first is exactly what makes that succeed on an entry
        # somebody deliberately locked. "It is at the path I want" is not
        # evidence that a worktree is stale — a live one from a concurrent
        # session looks identical. A dirty worktree is somebody's work, and
        # the same reasoning that protects a non-empty untracked directory
        # below applies with more force here, because git would actually
        # succeed in destroying it.
        # Only when the directory is still THERE. A registration whose directory
        # has already been deleted is the prunable half of the half-created
        # state, and it holds nothing that could be destroyed — reading a failed
        # `git status` there as "dirty, refuse" would block the exact cleanup
        # this function exists for.
        if path.exists():
            status = run_git(path, ["status", "--porcelain"], check=False)
            if status.returncode != 0 or (status.stdout or "").strip():
                raise GitError(
                    f"a worktree already exists at {path} and it has uncommitted "
                    "changes (or its state could not be read), so it was left "
                    "untouched. Inspect it, then remove it yourself with "
                    f"`git worktree remove {path}` if it really is finished with."
                )
            run_git(repo, ["worktree", "unlock", str(path)], check=False)
            rm = run_git(repo, ["worktree", "remove", "--force", str(path)], check=False)
            cleaned = rm.returncode == 0
            if rm.returncode != 0:
                # Keep git's own reason. Without it the caller sees only the
                # downstream `worktree add` failing with "already exists" and has
                # no way to tell that cleanup ran at all, let alone why it failed.
                failures.append((rm.stderr or rm.stdout or "").strip())

    # Prunes entries whose directory is already gone — the other half of the
    # half-created state, which `remove` cannot address. Its effect is measured
    # rather than assumed: `prune` exits 0 whether or not it dropped anything,
    # so comparing registrations is the only way to know, and without that a run
    # that genuinely cleaned something reported `False`.
    before = target in _registered_worktrees(repo)
    run_git(repo, ["worktree", "prune"], check=False)
    if before and target not in _registered_worktrees(repo):
        cleaned = True

    # A leftover directory that git no longer knows about still blocks
    # `worktree add`. Only remove it when EMPTY: a non-empty unregistered
    # directory is somebody's work, and deleting it to make room would be the
    # exact "destroyed to fix a mistake" failure the skill warns about.
    if path.exists():
        try:
            path.rmdir()
            cleaned = True
        except OSError as exc:
            # ENOTEMPTY is the protective case above and needs no report: the
            # `worktree add` that follows fails loudly and names the path.
            # Anything else (a permission denial, an antivirus or editor handle
            # — the ordinary Windows failures this whole script exists around)
            # is the environment refusing, not us protecting, and saying so is
            # the difference between a one-line diagnosis and reading source.
            if exc.errno not in (errno.ENOTEMPTY, errno.EEXIST):
                failures.append(f"could not remove {path}: {exc}")

    if failures:
        print(
            "[manual_worktree] cleanup did not fully succeed: "
            + "; ".join(f for f in failures if f),
            file=sys.stderr,
        )
    return cleaned


def branch_exists(repo: Path, branch: str) -> bool:
    return run_git(
        repo, ["rev-parse", "--verify", "--quiet", f"refs/heads/{branch}"], check=False
    ).returncode == 0


def create_worktree(
    repo: Path,
    name: str,
    base: str,
    worktree_dir: str = DEFAULT_WORKTREE_DIR,
    branch_prefix: str = DEFAULT_BRANCH_PREFIX,
    casing: dict | None = None,
) -> dict:
    """Create `<repo>/<worktree_dir>/<name>` on a new branch off `base`.

    `casing` is the `casing_mismatch()` verdict for the path as the USER spelled
    it, passed in because `repo` has already been resolved by the time it gets
    here and the mismatch is only visible before that.

    Validates its own arguments rather than trusting `main` to have done it.
    This is the function that owns the invariant — it builds the join and hands
    the result to `clean_stale_worktree` — and it is public, so an importing
    caller (this skill's own tests among them) reached the join with neither
    validator run. The `main` calls are kept as earlier, cheaper rejection.
    """
    validate_name(name)
    validate_worktree_dir(worktree_dir)
    rel = f"{worktree_dir}/{name}"
    path = repo / worktree_dir / name
    branch = f"{branch_prefix}{name}"

    if branch_exists(repo, branch):
        raise GitError(
            f"branch '{branch}' already exists. Pick another name, or delete it "
            f"with `git branch -D {branch}` if it is finished with."
        )

    cleaned = clean_stale_worktree(repo, path)
    run_git(repo, ["worktree", "add", rel, "-b", branch, base])

    # Resolved from git rather than rebuilt by string-joining, so the caller gets
    # the canonical spelling instead of whichever casing happened to be typed.
    resolved = os.path.realpath(str(path))

    # The worktree EXISTS from here on. A failure resolving these extras must not
    # be reported as a failed creation: the caller would retry with the same
    # name, hit `branch_exists`, and be told "pick another name" — actionable-
    # sounding advice for a situation where the right move is to use the worktree
    # that is already there. Degrade to a partial result with a warning instead.
    main_checkout, warning = None, None
    try:
        common = run_git(path, ["rev-parse", "--git-common-dir"]).stdout.strip()
        main_checkout = os.path.dirname(
            os.path.realpath(os.path.join(str(path), common))
        )
    except GitError as exc:
        warning = (
            f"worktree created, but the main checkout could not be resolved "
            f"({exc}). Any step needing it (copying gitignored env files) has to "
            "locate it another way."
        )

    return {
        "worktree_path": resolved,
        "relative_path": rel,
        "branch": branch,
        "base": base,
        "main_checkout": main_checkout,
        "cleaned_stale_entry": cleaned,
        # Declared here so one function owns the whole key set the skill and the
        # tests depend on. The VALUE has to come from the caller: detecting the
        # mismatch requires the path as originally spelled, and `repo` here is
        # already resolved — computing it from `repo` would always answer None
        # and silently disable the diagnosis.
        "casing_mismatch": casing,
        "warning": warning,
    }


def default_base(repo: Path) -> str:
    """`origin/<default>` when a remote HEAD is known, else the current branch.

    Matches what a harness-created worktree does (branch from the remote's
    default), while still working in a repo with no remote at all.

    The final `HEAD` arm cannot tell "this repo genuinely has no remote" from
    "origin/HEAD is dangling after an upstream rename, and I guessed", so it
    says which it did — the same posture as `_dispatch_lib.default_base_branch`.
    Silently branching off whatever happens to be checked out is how a day's
    work ends up rooted in an unrelated half-finished change, and the skill's
    own step 1 insists the base be reported.
    """
    head = run_git(repo, ["symbolic-ref", "--quiet", "refs/remotes/origin/HEAD"], check=False)
    if head.returncode == 0 and head.stdout.strip():
        return head.stdout.strip().removeprefix("refs/remotes/")
    for candidate in ("origin/main", "origin/master"):
        if run_git(repo, ["rev-parse", "--verify", "--quiet", candidate],
                   check=False).returncode == 0:
            return candidate
    print(
        "[manual_worktree] warn: could not resolve a remote default branch "
        "(no usable origin/HEAD, no origin/main, no origin/master) — branching "
        "from the currently checked-out HEAD instead. Confirm that is the base "
        "you wanted.",
        file=sys.stderr,
    )
    return "HEAD"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--name", help="worktree name (also the branch suffix)")
    parser.add_argument("--base", help="base ref; defaults to the remote's default branch")
    parser.add_argument("--repo", default=".", help="repo root (default: cwd)")
    parser.add_argument("--worktree-dir", default=DEFAULT_WORKTREE_DIR)
    parser.add_argument("--branch-prefix", default=DEFAULT_BRANCH_PREFIX)
    parser.add_argument(
        "--diagnose", action="store_true",
        help="only report whether this repo is exposed to the path-casing refusal",
    )
    args = parser.parse_args(argv)

    repo = Path(args.repo).resolve()
    try:
        # The RAW argument, deliberately — `repo` above is `.resolve()`d, which
        # canonicalises casing on Windows and would erase the very mismatch this
        # is meant to detect. Do not "tidy" this to use `repo`.
        mismatch = casing_mismatch(Path(args.repo))
        if args.diagnose:
            print(json.dumps({"casing_mismatch": mismatch}, indent=2))
            return 0
        if not args.name:
            # Not `parser.error`: that exits 2 with plain text on stderr, and
            # this module's documented contract is JSON on stdout with exit 1.
            # A caller parsing stdout would get nothing to read.
            raise GitError("--name is required unless --diagnose is given")
        validate_name(args.name)
        validate_worktree_dir(args.worktree_dir)

        result = create_worktree(
            repo, args.name, args.base or default_base(repo),
            worktree_dir=args.worktree_dir, branch_prefix=args.branch_prefix,
            casing=mismatch,
        )
        print(json.dumps(result, indent=2))
        return 0
    except GitError as exc:
        print(json.dumps({"error": str(exc)}, indent=2))
        return 1


if __name__ == "__main__":
    sys.exit(main())
