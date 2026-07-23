"""Append one JSON line per /multi-pr chain run to the project's chain-runs log.

Called by /multi-pr's Phase 4 (Final cleanup) AFTER the chain's changes are all
shipped. Reads a JSON object from stdin (the chain record assembled by the
orchestrator from its in-context outcomes) and appends it as a single line to:

    <repo-root>/cla.io/retro/multi-pr-runs.jsonl

This is the deliberate sibling of `spec-to-pr/scripts/log_run.py` — same ledger
directory, same atomic-append discipline, same resolver — but for the
CHAIN-level facts a per-change ledger structurally can't see (whether the
discovered order held, gate/escalation outcomes, post-merge follow-ups,
inter-change breakage, per-change timing-by-complexity).

**Why a script and not a raw `printf >> file`.** The chain record is
hand-assembled JSON, and a raw shell append has three failure modes this script
removes: (1) no validation — a malformed line (an un-replaced `N`/`...`
placeholder, an apostrophe in a `side_quests` label breaking the single-quoted
string) is written verbatim and silently poisons the ledger a future aggregator
must parse; (2) `printf` exits 0 on a malformed-but-writable string, so the
"best-effort, non-fatal" posture the SKILL documents only ever covered I/O
failure, never the real silent-poison mode; (3) portability — on a
PowerShell-primary Windows box, `>>` writes a UTF-16LE-with-BOM redirect that
corrupts the JSONL. `json.loads`-validating on stdin and appending UTF-8 bytes
directly fixes all three.

Append is direct via `open("ab")`: POSIX guarantees writes smaller than
PIPE_BUF (typically 4 KiB, comfortably above a single counts-only chain record)
are atomic, so concurrent runs cannot interleave bytes within a line. Windows
offers the same effective guarantee for small writes to local files.

Exit codes:
  0 = appended successfully
  1 = JSON parse failure, oversize record, or write failure (stderr names which)

The orchestrator MUST not halt if this script fails — a missing log line is
infinitely preferable to a halted workflow at the very end of a successful
chain. Phase 4 ignores a non-zero exit and continues (see SKILL.md Phase 4).
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

    Resolved from the `git rev-parse --show-toplevel` repo root — kept
    byte-identical to `log_run.py._runs_dir()` so both ledgers land in the same
    directory and sync across machines via git. CLAUDE_RETRO_DIR (absolute path)
    overrides it, same as its sibling.
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
        print(f"log_chain_run: invalid JSON on stdin: {e}", file=sys.stderr)
        return 1
    if not isinstance(record, dict):
        print("log_chain_run: top-level JSON must be an object", file=sys.stderr)
        return 1

    try:
        log_path = _runs_dir() / "multi-pr-runs.jsonl"
    except (ValueError, RuntimeError) as e:
        print(f"log_chain_run: {e}", file=sys.stderr)
        return 1
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        print(f"log_chain_run: cannot create {log_path.parent}: {e}", file=sys.stderr)
        return 1

    line = json.dumps(record, separators=(",", ":"), ensure_ascii=False) + "\n"
    encoded = line.encode("utf-8")
    if len(encoded) >= 4096:
        # Above PIPE_BUF; concurrent appends could interleave. A counts-only
        # chain record is well under this — if it isn't, the producer is logging
        # prose (forbidden) or an unbounded per_change array.
        print(
            f"log_chain_run: record is {len(encoded)} bytes — exceeds 4 KiB atomic-write "
            f"ceiling. Producer is logging prose; trim to counts only.",
            file=sys.stderr,
        )
        return 1

    try:
        with log_path.open("ab") as fh:
            fh.write(encoded)
    except OSError as e:
        print(f"log_chain_run: write failed at {log_path}: {e}", file=sys.stderr)
        return 1

    print(str(log_path))
    return 0


if __name__ == "__main__":
    sys.exit(main())
