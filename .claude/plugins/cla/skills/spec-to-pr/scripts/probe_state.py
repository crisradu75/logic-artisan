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

# Track tools that resolved as missing during a single probe(...) call so the
# JSON output can surface "tool_missing" distinctly from "phase not done".
_missing_tools: list[str] = []


def _run(cmd: list[str], cwd: Path | None = None, check: bool = False) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(cmd, cwd=cwd if cwd is not None else REPO_ROOT,
                              check=check, capture_output=True, text=True)
    except FileNotFoundError:
        # Executable not on PATH (e.g. openspec.cmd on Windows). Degrade gracefully
        # and remember which tool was missing so probe() can report it.
        if cmd and cmd[0] not in _missing_tools:
            _missing_tools.append(cmd[0])
        return subprocess.CompletedProcess(cmd, returncode=_TOOL_MISSING_RC, stdout="",
                                            stderr=f"executable not found: {cmd[0]}")


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


def _branch_state(change_name: str) -> bool:
    expected = f"feature/{change_name}"
    res = _run(["git", "rev-parse", "--verify", expected])
    if res.returncode != 0:
        return False
    ahead = _run(["git", "rev-list", "--count", f"master..{expected}"])
    if ahead.returncode != 0:
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
    res = _run(["git", "log", "--format=%s", f"master..{branch}"])
    if res.returncode != 0:
        return 0
    pat = re.compile(r"^fix: review round (\d+)\b")
    rounds = {int(m.group(1)) for line in res.stdout.splitlines() for m in [pat.match(line)] if m}
    return len(rounds)


def probe(change_name: str) -> dict:
    _missing_tools.clear()
    result = {
        "change_name": change_name,
        "propose": _propose_done(change_name),
        "implement": _implement_done(change_name),
        "branch": _branch_state(change_name),
        "pr": _pr_state(change_name),
        "fix_rounds_applied": _fix_rounds_applied(change_name),
        "archived": _archived(change_name),
    }
    if _missing_tools:
        result["tools_missing"] = list(_missing_tools)
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
