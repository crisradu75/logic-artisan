"""Probe current workflow phase state for a given OpenSpec change name.

Emits JSON to stdout describing what the orchestrator sees in the workspace.
Read-only: never mutates anything.
"""

# Spec: spec-to-pr-orchestration#implicit-resume-via-artifact-probes
# Spec: spec-to-pr-orchestration#probe-state-includes-archived-flag

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path


def _repo_root() -> Path:
    """Repo root via git (location-independent — works from the plugin, unlike a
    fixed `parents[N]` depth). Falls back to cwd if git is unavailable; tests
    monkeypatch REPO_ROOT directly."""
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, timeout=10,
        )
        if out.returncode == 0 and out.stdout.strip():
            return Path(out.stdout.strip())
    except (OSError, subprocess.SubprocessError):
        pass
    return Path.cwd()


REPO_ROOT = _repo_root()


_TOOL_MISSING_RC = 127
_ENVIRONMENT_RC = 126

# Bounded so a hung child can't wedge the probe. Sized above the siblings'
# (`_repo_root` 10s, `_dispatch_lib._git` 5s) because the `gh` calls here are
# network round-trips and can legitimately sit on a credential prompt — which
# is exactly the case an unbounded `subprocess.run` never returns from.
_TIMEOUT_SECONDS = 30

# Track tools that resolved as missing during a single probe(...) call so the
# JSON output can surface "tool_missing" distinctly from "phase not done".
_missing_tools: list[str] = []

# Environment failures that are NOT a missing tool (unusable working directory,
# a timeout). Kept separate because reporting them as `tools_missing` points the
# reader at PATH for a problem PATH has nothing to do with.
_environment_errors: list[str] = []


def _run(cmd: list[str], cwd: Path | None = None, check: bool = False) -> subprocess.CompletedProcess[str]:
    """Run a child process, degrading to a synthetic non-zero result rather than
    raising. Nothing here may raise: the caller parses this script's stdout as
    JSON, so an uncaught exception yields NO output at all — strictly worse than
    a reported failure."""
    target_cwd = cwd if cwd is not None else REPO_ROOT
    try:
        return subprocess.run(cmd, cwd=target_cwd, check=check,
                              capture_output=True, text=True, timeout=_TIMEOUT_SECONDS)
    except (OSError, subprocess.SubprocessError) as exc:
        # `FileNotFoundError` alone was too narrow: `cwd=` also raises
        # `NotADirectoryError` / `PermissionError` (both `OSError`, neither
        # `FileNotFoundError`), which killed the script outright. And a bad cwd
        # that DOES raise `FileNotFoundError` was recorded as a missing tool —
        # a false diagnostic aimed at PATH. Distinguish by asking whether the
        # working directory is usable before blaming the executable.
        #
        # `Path.is_dir()` itself is not exception-proof here: it swallows
        # ENOENT/ENOTDIR/EBADF/ELOOP but re-raises anything else — EACCES
        # included — so a permission-denied `cwd` would otherwise escape this
        # `except` block entirely (a raise during exception handling), which
        # is the exact "no JSON at all" failure this function exists to
        # prevent. Catch broadly and treat "can't even stat it" as unusable.
        try:
            cwd_is_dir = Path(target_cwd).is_dir()
        except OSError:
            cwd_is_dir = False
        if not cwd_is_dir:
            reason = f"working directory unusable: {target_cwd} ({exc})"
            if reason not in _environment_errors:
                _environment_errors.append(reason)
            return subprocess.CompletedProcess(cmd, returncode=_ENVIRONMENT_RC,
                                               stdout="", stderr=reason)
        if isinstance(exc, FileNotFoundError):
            # Executable not on PATH (e.g. openspec.cmd on Windows).
            if cmd and cmd[0] not in _missing_tools:
                _missing_tools.append(cmd[0])
            return subprocess.CompletedProcess(cmd, returncode=_TOOL_MISSING_RC, stdout="",
                                               stderr=f"executable not found: {cmd[0]}")
        reason = f"{cmd[0] if cmd else 'command'} failed to run: {exc}"
        if reason not in _environment_errors:
            _environment_errors.append(reason)
        return subprocess.CompletedProcess(cmd, returncode=_ENVIRONMENT_RC,
                                           stdout="", stderr=reason)


_DATE_PREFIX = re.compile(r"^\d{4}-\d{2}-\d{2}-")


def _propose_done(change_name: str) -> bool:
    return (REPO_ROOT / "openspec" / "changes" / change_name / "proposal.md").is_file()


def _archived(change_name: str) -> bool:
    """Return True iff openspec/changes/archive/<YYYY-MM-DD>-<change_name>/proposal.md exists.
    Uses an anchored date-prefix match to avoid suffix collisions
    (e.g. change "bar" must not match "2026-05-03-add-foo-bar")."""
    archive_dir = REPO_ROOT / "openspec" / "changes" / "archive"
    if not archive_dir.is_dir():
        return False
    for p in archive_dir.iterdir():
        if not p.is_dir():
            continue
        m = _DATE_PREFIX.match(p.name)
        if m is None:
            continue
        if p.name[m.end():] == change_name and (p / "proposal.md").is_file():
            return True
    return False


def _implement_done(change_name: str) -> bool:
    res = _run(["openspec", "status", "--change", change_name, "--json"])
    if res.returncode != 0:
        # Surface stderr so the orchestrator can distinguish "not complete"
        # from "openspec.cmd error" / "unknown change name". Tool-missing case
        # is already separately tracked in `_missing_tools`.
        if res.returncode != _TOOL_MISSING_RC and res.stderr.strip():
            print(f"openspec status (rc={res.returncode}): {res.stderr.strip()}",
                  file=sys.stderr)
        return False
    try:
        data = json.loads(res.stdout)
    except json.JSONDecodeError as exc:
        print(f"openspec status emitted non-JSON output ({exc.msg}); treating as not-complete",
              file=sys.stderr)
        return False
    return bool(data.get("isComplete", False))


_base_branch_cache: str | None = None
_ORIGIN_HEAD_PREFIX = "refs/remotes/origin/"


def _base_branch() -> str:
    """Resolve this repo's base branch instead of assuming `master`.

    A repo whose default is `main` has no `master` ref at all, so the hardcoded
    `master..<branch>` ranges below used to fail outright with `unknown
    revision` — not merely return a wrong count. Mirrors the hooks'
    `_dispatch_lib.default_base_branch()`; kept as a local copy because each
    skill is its own isolated pytest scope and cannot import from `hooks/`.

    `refs/remotes/origin/HEAD` is verified before it is trusted: it is a
    clone-time cache git never auto-refreshes, and `symbolic-ref` exits 0 even
    when the symref dangles, so after an upstream `master`→`main` rename it
    names a ref that no longer exists — resurrecting the very `unknown
    revision` failure this function was written to prevent.
    """
    global _base_branch_cache
    if _base_branch_cache is not None:
        return _base_branch_cache
    head_ref = _run(["git", "symbolic-ref", "--quiet", "refs/remotes/origin/HEAD"])
    resolved = None
    if head_ref.returncode == 0 and head_ref.stdout.strip().startswith(_ORIGIN_HEAD_PREFIX):
        # Strip the known prefix rather than `rsplit("/", 1)`: a default branch
        # name containing its own slash (`release/main`) would otherwise lose
        # its leading segment, and `rev-parse --verify` on the FULL target
        # (below) succeeds regardless — so the truncated name passed every
        # check here and still resolved to a branch that doesn't exist.
        target = head_ref.stdout.strip()
        candidate = target[len(_ORIGIN_HEAD_PREFIX):] or None
        if candidate and candidate != "HEAD" and _run(
            ["git", "rev-parse", "--verify", "--quiet", target]
        ).returncode == 0:
            resolved = candidate
    if resolved is None:
        for candidate in ("main", "master"):
            for ref in (f"refs/heads/{candidate}", f"refs/remotes/origin/{candidate}"):
                if _run(["git", "rev-parse", "--verify", "--quiet", ref]).returncode == 0:
                    resolved = candidate
                    break
            if resolved:
                break
    if resolved is None:
        # Announce the guess. This arm cannot tell "this repo genuinely uses
        # master" from "git is unusable", and every range built on the result
        # below then fails as `unknown revision` — read by the callers as a
        # legitimate negative.
        print("could not resolve the base branch (no usable origin/HEAD, no main, "
              "no master); assuming 'master'", file=sys.stderr)
        resolved = "master"
    _base_branch_cache = resolved
    return _base_branch_cache


def _branch_state(change_name: str) -> bool:
    expected = f"feature/{change_name}"
    # `--quiet` matters here, not just cosmetically: without it, `rev-parse
    # --verify` prints `fatal: Needed a single revision` on the ordinary
    # "branch doesn't exist yet" path too, which would make a stderr-if-any-
    # output gate fire on the ordinary negative instead of only on a genuine
    # anomaly (ref-store corruption, an ambiguous name).
    res = _run(["git", "rev-parse", "--verify", "--quiet", expected])
    if res.returncode != 0:
        if res.returncode != _TOOL_MISSING_RC and res.stderr.strip():
            print(f"git rev-parse --verify {expected} (rc={res.returncode}): "
                  f"{res.stderr.strip()}", file=sys.stderr)
        return False
    base = _base_branch()
    ahead = _run(["git", "rev-list", "--count", f"{base}..{expected}"])
    if ahead.returncode != 0:
        # `False` here is read by the orchestrator as "no feature branch yet"
        # and it re-runs completed work. An `unknown revision` from a wrong
        # base branch produces exactly that, so say which range failed instead
        # of degrading silently — `_implement_done`/`_pr_state` already do.
        if ahead.returncode != _TOOL_MISSING_RC and ahead.stderr.strip():
            print(f"git rev-list {base}..{expected} (rc={ahead.returncode}): "
                  f"{ahead.stderr.strip()}", file=sys.stderr)
        return False
    try:
        return int(ahead.stdout.strip()) > 0
    except ValueError:
        return False


def _pr_state(change_name: str) -> dict:
    branch = f"feature/{change_name}"
    repo_res = _run(["gh", "repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner"])
    if repo_res.returncode != 0:
        # rc==127 here means gh is missing; already tracked in _missing_tools.
        # Other non-zero codes (auth expired, rate-limit, no remote) need to be
        # surfaced so the caller can distinguish "no PR exists" from "gh broken".
        if repo_res.returncode != _TOOL_MISSING_RC and repo_res.stderr.strip():
            print(f"gh repo view (rc={repo_res.returncode}): {repo_res.stderr.strip()}",
                  file=sys.stderr)
        return {"open": False, "url": None}
    owner_repo = repo_res.stdout.strip()
    if not owner_repo:
        return {"open": False, "url": None}
    res = _run(["gh", "pr", "view", branch, "--repo", owner_repo, "--json", "url,state"])
    if res.returncode != 0:
        # gh exits non-zero for "no PR for this branch" too, so don't shout — only
        # log when the stderr looks like a real error (auth/rate-limit/network).
        stderr = res.stderr.strip()
        if (res.returncode != _TOOL_MISSING_RC and stderr
                and "no pull requests found" not in stderr.lower()):
            print(f"gh pr view (rc={res.returncode}): {stderr}", file=sys.stderr)
        return {"open": False, "url": None}
    try:
        data = json.loads(res.stdout)
    except json.JSONDecodeError as exc:
        print(f"gh pr view emitted non-JSON output ({exc.msg}); treating as no PR",
              file=sys.stderr)
        return {"open": False, "url": None}
    return {
        "open": data.get("state", "").upper() == "OPEN",
        "url": data.get("url"),
    }


def _fix_rounds_applied(change_name: str) -> int:
    branch = f"feature/{change_name}"
    base = _base_branch()
    res = _run(["git", "log", "--format=%s", f"{base}..{branch}"])
    if res.returncode != 0:
        # Same hazard as `_branch_state`: `0` reads as "no fix rounds applied
        # yet" and the orchestrator re-loops an already-applied round.
        if res.returncode != _TOOL_MISSING_RC and res.stderr.strip():
            print(f"git log {base}..{branch} (rc={res.returncode}): "
                  f"{res.stderr.strip()}", file=sys.stderr)
        return 0
    pat = re.compile(r"^fix: review round (\d+)\b")
    rounds = {int(m.group(1)) for line in res.stdout.splitlines() for m in [pat.match(line)] if m}
    return len(rounds)


def probe(change_name: str) -> dict:
    global _base_branch_cache
    _missing_tools.clear()
    _environment_errors.clear()
    # Cleared alongside the other two: nothing calls `probe()` twice in one
    # process today, but leaving a stale cache in place would mean a future
    # second call reports `base_branch` resolved under the PREVIOUS call's
    # conditions with no re-warning — the exact stale-guess-read-as-fact
    # failure this file exists to eliminate.
    _base_branch_cache = None
    result = {
        "change_name": change_name,
        "propose": _propose_done(change_name),
        "implement": _implement_done(change_name),
        "branch": _branch_state(change_name),
        "pr": _pr_state(change_name),
        "fix_rounds_applied": _fix_rounds_applied(change_name),
        "archived": _archived(change_name),
        # Reported, not merely used: `branch` and `fix_rounds_applied` are both
        # computed from a `<base>..<branch>` range, so a wrongly-resolved base
        # turns them into plausible-looking negatives. Surfacing the resolved
        # value makes that visible instead of something the reader has to infer
        # from work being redone.
        "base_branch": _base_branch(),
    }
    if _missing_tools:
        result["tools_missing"] = list(_missing_tools)
    if _environment_errors:
        result["environment_errors"] = list(_environment_errors)
    return result


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print("usage: probe_state.py <change-name>", file=sys.stderr)
        return 2
    result = probe(argv[0])
    json.dump(result, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
