"""Append one JSON line per /codify-learnings run to the project's runs log.

Called by /codify-learnings's final step AFTER the rolling-log write, so the
loop can be reviewed in aggregate by /codify-retro. Reads a JSON object from
stdin (the run record assembled by conversation Claude from this run's
outcomes) and appends it as a single line to:

    <repo-root>/cla.io/retro/codify-runs.jsonl

The ledger lives INSIDE the repo (repo root resolved via `git rev-parse`, then
`<root>/cla.io/retro`) so it is version-controlled and syncs across machines
via git — not a machine-local `~/.claude/projects/<hash>/` that splits per
working-directory path. Override the directory with the CLAUDE_RETRO_DIR env
var (absolute path); used by tests and non-standard layouts. The companion
`.gitattributes` sets `merge=union` on `cla.io/retro/*.jsonl` so concurrent
appends from two machines auto-resolve by keeping both lines.

Append is direct via `open("ab")`: POSIX guarantees writes smaller than
PIPE_BUF (typically 4 KiB, comfortably above a counts-only run record) are
atomic, so concurrent runs from parallel sessions cannot interleave bytes
within a line. Windows offers the same effective guarantee for small writes to
local files. This avoids the read-modify-rewrite pattern, which is both O(N)
per append and silently race-unsafe.

The record is COUNTS-ONLY (no prose) — prose lives in lessons-learned.md and
transcripts. A record over 4 KiB means the producer is logging prose; that is
rejected so the atomic-append guarantee holds.

Exit codes:
  0 = appended successfully
  1 = JSON parse failure, prose-overflow, or write failure (stderr names which)

The orchestrator MUST not halt if this script fails — a missing log line is
infinitely preferable to a halted workflow at the very end of a successful
run. The /codify-learnings final step ignores non-zero exits and continues.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def _git_toplevel() -> Path | None:
    """Repo root via git (location-independent — works from the plugin, unlike a
    `.claude`-ancestor walk). None if git is unavailable."""
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, timeout=10,
        )
        if out.returncode == 0 and out.stdout.strip():
            return Path(out.stdout.strip())
    except (OSError, subprocess.SubprocessError):
        return None
    return None


def _runs_dir() -> Path:
    """The in-repo, git-synced ledger dir: <repo-root>/cla.io/retro/.

    Resolved from the `git rev-parse --show-toplevel` repo root, so the ledger
    sits alongside the skills and syncs across machines via git instead of a
    machine-local `~/.claude/projects/<hash>/`. CLAUDE_RETRO_DIR (absolute
    path) overrides it — used by tests and non-standard layouts.

    Raises on a non-absolute override or an unresolvable repo root rather
    than guessing a path: the consumer (`codify-retro/scripts/aggregate.py`)
    resolves independently with identical logic, so a silently-wrong path here
    would make logged runs vanish from the retro with no error. Keep the two
    resolvers byte-identical.
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


def main() -> int:
    raw = sys.stdin.read()
    try:
        record = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"log_run: invalid JSON on stdin: {e}", file=sys.stderr)
        return 1
    if not isinstance(record, dict):
        print("log_run: top-level JSON must be an object", file=sys.stderr)
        return 1

    try:
        log_path = _runs_dir() / "codify-runs.jsonl"
    except (ValueError, RuntimeError) as e:
        print(f"log_run: {e}", file=sys.stderr)
        return 1
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        print(f"log_run: cannot create {log_path.parent}: {e}", file=sys.stderr)
        return 1

    line = json.dumps(record, separators=(",", ":"), ensure_ascii=False) + "\n"
    encoded = line.encode("utf-8")
    if len(encoded) >= 4096:
        print(
            f"log_run: record is {len(encoded)} bytes — exceeds 4 KiB atomic-write "
            f"ceiling. Producer is logging prose; trim to counts only.",
            file=sys.stderr,
        )
        return 1

    try:
        with log_path.open("ab") as fh:
            fh.write(encoded)
    except OSError as e:
        print(f"log_run: write failed at {log_path}: {e}", file=sys.stderr)
        return 1

    print(str(log_path))
    return 0


if __name__ == "__main__":
    sys.exit(main())
