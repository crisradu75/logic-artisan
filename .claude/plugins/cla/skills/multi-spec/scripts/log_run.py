"""Append one JSON line per /multi-spec batch run to the project's runs log.

Called by /multi-spec's Report phase, after the terminal report is printed and
the PR is open. Reads a JSON object from stdin (the batch record assembled by
the orchestrator from its in-context outcomes) and appends it as a single line
to:

    <repo-root>/cla.io/retro/multi-spec-runs.jsonl

This is the deliberate sibling of `spec-to-pr/scripts/log_run.py` and
`multi-pr/scripts/log_chain_run.py` — same ledger directory, same
atomic-append discipline, same repo-root resolver — sized for the facts a
proposal-authoring batch produces (sequencing source, per-change review
findings, whether a prior interrupted run was resumed), which neither
sibling's schema captures.

**Log-only, deliberately.** There is no `multi-spec-retro` analyzer skill yet
— per this repo's own established convention (`codify-retro`, `spec-to-pr-retro`,
and `multi-pr`'s own "wait until enough chains accumulate" note), a handful of
runs is noise, not a pattern. This script exists so the data is there when a
future `multi-spec-retro` is justified, not to feed one yet. (See SKILL.md's
"Log the run" for the concrete revisit threshold.)

**Why a script and not a raw shell append.** Same three failure modes as
`log_chain_run.py`: (1) no validation, so a malformed line silently poisons a
ledger a future aggregator must parse; (2) `printf`/`>>` exits 0 on a
malformed-but-writable string, defeating the "best-effort, non-fatal" posture;
(3) on a PowerShell-primary Windows box, `>>` writes a UTF-16LE-with-BOM
redirect that corrupts JSONL. `json.loads`-validating on stdin and appending
UTF-8 bytes directly fixes all three.

Append is direct via `open("ab")`: POSIX (and Windows, for small local-file
writes) guarantees writes smaller than PIPE_BUF (typically 4 KiB) are atomic,
so concurrent runs cannot interleave bytes within a line.

Exit codes:
  0 = appended successfully
  1 = JSON parse failure, oversize record, or write failure (stderr names which)

The orchestrator MUST NOT halt if this script fails — a missing log line is
infinitely preferable to a halted run at the very end of a successful batch.
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
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10,
        )
        if out.returncode == 0 and out.stdout.strip():
            return Path(out.stdout.strip())
    except (OSError, subprocess.SubprocessError):
        return None
    return None


def _runs_dir() -> Path:
    """The in-repo, git-synced ledger dir: <repo-root>/cla.io/retro/.

    Resolved from the `git rev-parse --show-toplevel` repo root — logic-identical
    to `spec-to-pr/scripts/log_run.py._runs_dir()` and
    `multi-pr/scripts/log_chain_run.py._runs_dir()` (the executable code matches;
    only comments/strings here use ASCII glyphs where the siblings use Unicode,
    to stay safe on a cp1252 Windows console) so every skill's ledger lands in
    the same directory and syncs across machines via git. CLAUDE_RETRO_DIR
    (absolute path) overrides it, same as its siblings.
    """
    override = os.environ.get("CLAUDE_RETRO_DIR")
    if override and override.strip():  # set-but-blank/whitespace -> treat as unset
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
    """Force UTF-8 on stdout/stderr regardless of the ambient locale.

    JSON is UTF-8 by specification (RFC 8259) and the write path below already
    re-encodes with `.encode("utf-8")`. Reading stdin through the ambient
    encoding -- cp1252 on a stock Windows box -- silently double-encoded every
    non-ASCII value: a scope of "cafe-fix" with an accent was appended as
    mojibake, exit 0, success path taken, ledger path echoed, and the retro
    skills then aggregated the corrupted record.

    Worse, a UTF-8 byte in cp1252's undefined set (0x81/0x8D/0x8F/0x90/0x9D --
    e.g. the second byte of Cyrillic U+0441) decodes to a lone surrogate, and
    the later `.encode("utf-8")` raises UnicodeEncodeError OUTSIDE every `try`,
    replacing this module's documented exit-code contract with a bare traceback.

    Fixing only stdin is half a contract: these scripts `print()` diagnostics
    containing non-ASCII (the oversize message carries an em-dash), and
    `print(..., file=sys.stderr)` encodes with the ambient locale too. Pinning
    one and not the other just moves the failure.

    `reconfigure` is guarded because a wrapped stream -- pytest capture, a pipe
    shim -- may not expose it. `update-cla/scripts/orchestrate.py` already
    carried this pattern for exactly this reason; it simply was not applied here.
    """
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")


def main() -> int:
    _pin_streams_utf8()
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
        log_path = _runs_dir() / "multi-spec-runs.jsonl"
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
        # batch record is well under this — if it isn't, the producer is
        # logging prose or an unbounded per-change array; trim to counts only.
        print(
            f"log_run: record is {len(encoded)} bytes -- exceeds 4 KiB atomic-write "
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
