#!/usr/bin/env python3
"""Append one JSON line to a project run-ledger under `cla.io/retro/`.

ONE writer, shared by every skill that keeps a ledger, invoked with the ledger
filename as an argument:

    python .claude/plugins/cla/lib/log_run.py spec-to-pr-runs.jsonl < record.json

There used to be five near-identical copies of this file (one per skill), kept
in step by a dedicated drift check in `consistency-checks/`. The copies existed
because `run_tests.py` runs each scope as its own pytest process — same-named
modules in one interpreter collide — so a skill could not import a sibling's
helper. Living at the plugin root instead of under `skills/<name>/scripts/`
sidesteps that entirely: nothing imports it, the skills invoke it as a program.

Three of those five ledgers had no reader at all (`multi-pr`, `multi-spec`,
`multi-lite`) and were deleted rather than migrated. Only `spec-to-pr-runs`
(132 records) and `codify-runs` (43) are consumed, by their respective retro
skills.

Reads a JSON object from stdin (the run record the caller assembled from its
own outcomes) and appends it as a single line to:

    <repo-root>/cla.io/retro/<ledger>

The repo root comes from `git rev-parse --show-toplevel`, so the ledger sits
alongside the skills and syncs across machines via git rather than living in a
machine-local `~/.claude/projects/<hash>/`. CLAUDE_RETRO_DIR overrides it
(absolute path); used by tests and non-standard layouts. The companion
`.gitattributes` sets `merge=union` on `cla.io/retro/*.jsonl` so concurrent
appends from two machines auto-resolve by keeping both lines.

Appends are a single `write()` of one line in "ab" mode. POSIX writes below
PIPE_BUF (typically 4 KiB, comfortably above a counts-only run record) are
atomic, so concurrent runs from parallel sessions cannot interleave bytes
within a line. Windows offers the same effective guarantee for small writes to
local files. This avoids the read-modify-rewrite pattern, which is both O(N)
per append and silently race-unsafe (two readers see the same N, both rewrite,
one append is lost).

The record is COUNTS-ONLY (no prose) — prose lives in the skill's own report.
The 4 KiB ceiling below is what enforces that in practice.

A caller MUST NOT halt if this script fails — a missing log line is infinitely
preferable to a halted workflow at the end of a successful run. Callers ignore
a non-zero exit and continue.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

# A ledger name is a bare filename, never a path. Without this an argument like
# `../../etc/thing.jsonl` would write outside the ledger dir — the caller is a
# model assembling a command line, so the check is not hypothetical.
_LEDGER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*\.jsonl$")


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

    Raises on a non-absolute override or an unresolvable repo root rather than
    guessing a path: the consumers (the retro skills' `aggregate.py`) resolve
    independently with identical logic, so a silently-wrong path here would make
    logged runs vanish from the retro with no error.
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


def _pin_streams_utf8() -> None:
    """Force UTF-8 on stdout/stderr regardless of the ambient locale."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    _pin_streams_utf8()
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        print("log_run: usage: log_run.py <ledger-name>.jsonl < record.json", file=sys.stderr)
        return 1
    ledger = args[0]
    if not _LEDGER_RE.match(ledger):
        print(
            f"log_run: {ledger!r} is not a bare `<name>.jsonl` filename; a ledger "
            "argument must not contain a path separator",
            file=sys.stderr,
        )
        return 1

    # Read BYTES and decode explicitly, rather than letting the text wrapper
    # apply the platform locale.
    try:
        raw = sys.stdin.buffer.read().decode("utf-8")
    except UnicodeDecodeError as e:
        print(f"log_run: stdin is not valid UTF-8: {e}", file=sys.stderr)
        return 1
    try:
        record = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"log_run: invalid JSON on stdin: {e}", file=sys.stderr)
        return 1
    if not isinstance(record, dict):
        print("log_run: top-level JSON must be an object", file=sys.stderr)
        return 1

    try:
        log_path = _runs_dir() / ledger
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
        # Above PIPE_BUF; concurrent appends could interleave. A counts-only
        # record is well under this threshold — if it isn't, the producer is
        # logging prose (forbidden).
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
