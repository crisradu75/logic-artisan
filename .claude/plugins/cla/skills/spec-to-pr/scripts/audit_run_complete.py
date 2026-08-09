"""Audit that a /spec-to-pr run finalized its discipline metadata — and surface
any gap to the NEXT run.

Deterministic and hook-independent by design: a hook can silently fail to fire
(and a Stop hook would fire on every stop, not just /spec-to-pr), so this
discipline audit is an in-skill script the orchestrator calls directly, not a
hook.

Two discipline invariants are checked against the repo's retro log:
  (1) the run appended a per-run line to `spec-to-pr-runs.jsonl` — Handoff step 5
      actually ran (the log exists and its last line parses as a JSON object); and
  (2) that line is committed, not left dangling — Handoff step 6 ran (the log
      file is clean in `git status --porcelain`). A written-but-uncommitted line
      is exactly the "metadata uncommitted" gap a deferred-audit check catches.
      Only checked when the run actually opened a PR (`--shipped`): when Ship was
      skipped the line is *intentionally* left uncommitted (SKILL.md Handoff
      step 6's feature-branch-only guard), so checking it there would false-flag.

Modes:
  --finalize [--shipped] [--change NAME]
      Run at the end of Handoff. Checks the invariants for the CURRENT run. On a
      gap, writes a local marker file the next run's Precheck surfaces; on a clean
      run, clears any stale marker. Always exits 0 (advisory — never halts a run).
  --check-prior
      Run at the start of Precheck. If the marker exists, prints a one-line
      warning describing the PRIOR run's gap (for the orchestrator to surface),
      then deletes it (a gap is surfaced once). Silent + exit 0 when no marker.

The marker (`<retro-dir>/.spec-to-pr-incomplete`) is LOCAL-only — never committed
(the orchestrator's path-scoped `git add` never names it) — a transient cross-run
signal, cleared once surfaced. Retro dir resolution matches `log_run.py` exactly
(repo root via `git rev-parse`, then `cla.io/retro`; CLAUDE_RETRO_DIR absolute
override) so the marker lands beside the ledger it audits.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


LOG_NAME = "spec-to-pr-runs.jsonl"
MARKER_NAME = ".spec-to-pr-incomplete"

# Human-readable text for each gap slug, shown by --check-prior.
_GAP_TEXT = {
    "run-log-missing": "the run did not append its per-run line to "
    f"{LOG_NAME} (Handoff step 5 was skipped or failed)",
    "run-log-uncommitted": f"the {LOG_NAME} line was written but left "
    "uncommitted (Handoff step 6 was skipped or failed) - it will not ship with the PR",
}


def _git_toplevel() -> Path | None:
    """Repo root via git (location-independent — works from the plugin, unlike a
    `.claude`-ancestor walk). None if git is unavailable."""
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10,
        )
        if out.returncode == 0 and out.stdout.strip():
            return Path(out.stdout.strip())
    except (OSError, subprocess.SubprocessError):
        return None
    return None


def _runs_dir() -> Path:
    """The in-repo, git-synced ledger dir: <repo-root>/cla.io/retro/.

    Same resolution as `log_run.py`'s `_runs_dir()` so the marker lands beside the
    ledger. CLAUDE_RETRO_DIR (absolute) overrides; a non-absolute override or an
    unresolvable repo root raises rather than guessing.
    """
    override = os.environ.get("CLAUDE_RETRO_DIR")
    if override and override.strip():  # set-but-blank/whitespace → treat as unset
        path = Path(override)
        if not path.is_absolute():
            raise ValueError(f"CLAUDE_RETRO_DIR must be an absolute path, got {override!r}")
        return path
    root = _git_toplevel()
    if root is None:
        raise RuntimeError(
            "could not resolve the repo root via `git rev-parse --show-toplevel`; "
            "set CLAUDE_RETRO_DIR to an absolute path"
        )
    return root / "cla.io" / "retro"


def audit(log_last_line: str | None, log_dirty: bool | None, shipped: bool) -> dict:
    """Pure discipline check. `log_last_line` is the final line of the ledger (or
    None if the file is absent/empty); `log_dirty` is whether git reports the
    ledger modified/untracked (None = git couldn't be consulted); `shipped` is
    whether the run opened a PR. Returns {"ok": bool, "gaps": [slug, ...]}."""
    gaps: list[str] = []

    parsed_ok = False
    if log_last_line and log_last_line.strip():
        try:
            parsed_ok = isinstance(json.loads(log_last_line), dict)
        except json.JSONDecodeError:
            parsed_ok = False
    if not parsed_ok:
        gaps.append("run-log-missing")

    # Only meaningful when the run shipped a PR (else the line is intentionally
    # uncommitted) AND git could actually be consulted (dirty is not None).
    if shipped and log_dirty is True:
        gaps.append("run-log-uncommitted")

    return {"ok": not gaps, "gaps": gaps}


def _last_line(path: Path) -> str | None:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    lines = [ln for ln in text.splitlines() if ln.strip()]
    return lines[-1] if lines else None


def _log_dirty(repo_root: Path | None, log_path: Path) -> bool | None:
    """True/False if git could report the ledger's cleanliness, None if git was
    unavailable or errored (unknown — the audit then skips the committed check)."""
    if repo_root is None:
        return None
    try:
        out = subprocess.run(
            ["git", "status", "--porcelain", "--", str(log_path)],
            cwd=str(repo_root),
            capture_output=True,
            text=True, encoding="utf-8", errors="replace",
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    return bool(out.stdout.strip())


def _repo_root() -> Path | None:
    return _git_toplevel()


def _finalize(shipped: bool, change: str | None) -> int:
    try:
        retro = _runs_dir()
    except (ValueError, RuntimeError) as e:
        print(f"audit_run_complete: {e}", file=sys.stderr)
        return 0  # advisory — never fail the run
    log_path = retro / LOG_NAME
    marker_path = retro / MARKER_NAME

    result = audit(
        _last_line(log_path),
        _log_dirty(_repo_root(), log_path) if shipped else None,
        shipped,
    )

    if result["ok"]:
        try:
            marker_path.unlink(missing_ok=True)  # absent marker is the normal case
        except OSError as e:
            # A real error (e.g. permission) — NOT the absent-file case (missing_ok
            # handles that). Surface it: a marker left behind would resurface a
            # now-resolved gap at the next run's Precheck. Still advisory (exit 0).
            print(f"audit_run_complete: could not clear stale marker: {e}", file=sys.stderr)
        print("audit: ok (run-log present" + (" + committed" if shipped else "") + ")")
        return 0

    marker = {"source": "spec-to-pr Handoff", "change": change or "unknown", "gaps": result["gaps"]}
    try:
        marker_path.parent.mkdir(parents=True, exist_ok=True)
        marker_path.write_text(json.dumps(marker) + "\n", encoding="utf-8")
    except OSError as e:
        print(f"audit_run_complete: could not write marker: {e}", file=sys.stderr)
    print("audit: DISCIPLINE GAP: " + ", ".join(result["gaps"]))
    return 0


def _check_prior() -> int:
    try:
        marker_path = _runs_dir() / MARKER_NAME
    except (ValueError, RuntimeError):
        return 0
    line = _last_line(marker_path)  # marker is a single JSON line
    if not line:
        # No marker, or an empty/whitespace one (can't arise via _finalize, but be
        # robust): clean up an empty file so it doesn't linger, and report nothing.
        try:
            marker_path.unlink(missing_ok=True)
        except OSError:
            pass
        return 0
    try:
        marker = json.loads(line)
    except json.JSONDecodeError:
        marker = {}
    change = marker.get("change", "unknown") if isinstance(marker, dict) else "unknown"
    gaps = marker.get("gaps", []) if isinstance(marker, dict) else []
    detail = "; ".join(_GAP_TEXT.get(g, g) for g in gaps) or "unspecified gap"
    print(f"PRIOR-RUN DISCIPLINE GAP ({change}): {detail}")
    try:
        marker_path.unlink()  # surface once, then clear
    except OSError:
        pass
    return 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="audit_run_complete.py")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--finalize", action="store_true")
    mode.add_argument("--check-prior", action="store_true")
    parser.add_argument("--shipped", action="store_true")
    parser.add_argument("--change", default=None)
    args = parser.parse_args(argv)
    if args.finalize:
        return _finalize(args.shipped, args.change)
    return _check_prior()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
