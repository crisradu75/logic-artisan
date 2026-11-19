#!/usr/bin/env python3
"""Add permission entries to the project's ``.claude/settings.local.json`` allowlist.

    python3 "${CLAUDE_PLUGIN_ROOT}/skills/save-permissions/scripts/merge_permissions.py" '<entry>' ['<entry>' ...]
    python3 "${CLAUDE_PLUGIN_ROOT}/skills/save-permissions/scripts/merge_permissions.py" < entries.txt

Run from the project root: the file is ``.claude/settings.local.json`` under the working
directory, and no other path can be named. The entries are the arguments, or, with no argument,
one entry per line on stdin (surrounding whitespace and blank lines are dropped).

WHAT IT DOES, in this order:
  1. Load the file. A missing file counts as ``{}``; a UTF-8 byte order mark is accepted.
  2. Create a missing ``permissions`` object and a missing ``allow`` list.
  3. Set-union ``allow`` with the new entries and sort by code point.
  4. Write the JSON (2-space indent, ASCII escapes, one trailing newline) to a new temporary file
     beside the original, then replace the original with it in one step (``os.replace``). The
     temporary file is removed if anything fails, so the original is either whole or replaced.
     A replaced file keeps the original's permission bits.

It stops, writing nothing and leaving the file byte-identical, when the file is not UTF-8 or not
valid JSON, the top level is not an object, ``permissions`` is not an object, ``allow`` is not a
list or holds anything but strings, the path is a symbolic link or not a regular file, or the
write fails. Every such message starts ``stopped, nothing written:``. Every other setting in the
file is kept; the whole file is re-serialised, so its spacing may change.

This replaced two inline merge snippets (a Python one and a PowerShell one) that the skill told
the agent to copy; prose that must be copied exactly is fragile, and the guards lived twice.

EXIT CODES:
  0 = written (stdout: how many entries were new, and the allowlist's size)
  1 = stopped, nothing written (stderr says why)
  2 = usage: no entry given, an empty entry, or stdin unreadable as UTF-8; nothing written
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

SETTINGS = Path(".claude") / "settings.local.json"
STOPPED = "stopped, nothing written"


class Stop(Exception):
    """A refusal: nothing was written."""


def _entries(argv: list[str]) -> list[str]:
    if argv:
        if any(not a.strip() for a in argv):
            raise ValueError("an entry is empty")
        return list(argv)
    if sys.stdin is None or sys.stdin.isatty():
        raise ValueError("give the new entries as arguments, or one per line on stdin")
    raw = sys.stdin.buffer.read()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError(f"stdin is not UTF-8 ({exc})") from None
    entries = [line.strip() for line in text.splitlines() if line.strip()]
    if not entries:
        raise ValueError("no entry on stdin")
    return entries


def _load(p: Path) -> dict:
    if p.is_symlink():
        raise Stop(f"{p} is a symbolic link")
    if not p.exists():
        return {}
    if not p.is_file():
        raise Stop(f"{p} is not a regular file")
    try:
        data = json.loads(p.read_bytes().decode("utf-8-sig"))
    except ValueError as exc:  # UnicodeDecodeError and JSONDecodeError both
        raise Stop(f"{p} is not valid JSON ({exc})") from None
    if not isinstance(data, dict):
        raise Stop(f"{p} does not hold a JSON object")
    return data


def merge(data: dict, new: list[str], p: Path) -> tuple[list[str], int]:
    """Return (the merged allowlist, how many entries were new). Mutates ``data``."""
    perms = data.setdefault("permissions", {})
    if not isinstance(perms, dict):
        raise Stop(f"permissions in {p} is not an object")
    allow = perms.setdefault("allow", [])
    if not isinstance(allow, list):
        raise Stop(f"permissions.allow in {p} is not a list")
    if not all(isinstance(e, str) for e in allow):
        raise Stop(f"permissions.allow in {p} holds an entry that is not a string")
    merged = sorted(set(allow) | set(new))
    perms["allow"] = merged
    return merged, len(set(new) - set(allow))


def _mode_for(p: Path) -> int:
    try:
        return p.stat().st_mode & 0o7777
    except FileNotFoundError:
        umask = os.umask(0)
        os.umask(umask)
        return 0o666 & ~umask


def write_atomic(p: Path, text: str) -> None:
    mode = _mode_for(p)
    fd, tmp = tempfile.mkstemp(dir=str(p.parent), prefix="." + p.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(text.encode("utf-8"))
        os.chmod(tmp, mode)
        os.replace(tmp, str(p))
    except BaseException:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass
        raise


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] in (["-h"], ["--help"]):
        print(__doc__)
        return 0
    try:
        new = _entries(argv)
    except ValueError as exc:
        print(f"usage error, nothing written: {exc}", file=sys.stderr)
        return 2
    p = SETTINGS
    try:
        if p.parent.is_symlink() or (p.parent.exists() and not p.parent.is_dir()):
            raise Stop(f"{p.parent} is not a directory")
        data = _load(p)
        merged, added = merge(data, new, p)
        p.parent.mkdir(exist_ok=True)
        try:
            write_atomic(p, json.dumps(data, indent=2) + "\n")
        except OSError as exc:
            raise Stop(f"could not write {p} ({exc})") from None
    except Stop as exc:
        print(f"{STOPPED}: {exc}", file=sys.stderr)
        return 1
    print(f"added {added} new permission(s); allowlist now has {len(merged)} entries")
    return 0


if __name__ == "__main__":
    sys.exit(main())
