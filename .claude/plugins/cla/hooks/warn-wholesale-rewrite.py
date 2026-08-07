#!/usr/bin/env python3
"""PostToolUse (Write): warn when a wholesale rewrite silently shrinks a file.

A `Write` to an existing tracked file replaces it entirely. That is the shape in
which content disappears without anyone deciding to remove it: the new version
reads well on its own, so nothing prompts a comparison against what it replaced.

The incident that added this hook: an output-style file was rewritten 121 -> 93
lines. Review found four separate rules dropped with no intent behind any of
them -- an anti-telegraphic-writing rule, a scope statement, and two exemptions
that a table depended on. Every one had survived the previous edit-based changes
to the same file. The same session had already shipped a rewritten guard whose
replacement lost six behaviours the original had.

So this fires on `Write`, never `Edit`. An `Edit` is surgical: whatever it does
not name, it keeps. A `Write` keeps only what the author remembered to carry
across, and remembering is exactly what fails.

It warns, never blocks. Deliberate shortening is common and legitimate -- this
hook cannot tell a good cut from a lost rule, and should not try. Its whole job
is to make the author say which one it was, at the moment they still remember.

Baseline is `git show HEAD:<path>`, so an untracked or brand-new file is silent
(nothing was replaced) and a shrink is measured against the last committed
state. Several small writes across one session therefore accumulate rather than
each resetting the baseline, which is the behaviour that matches the risk.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

# Below this, a "shrink" is noise -- reformatting a stub, trimming a short list.
MIN_BASELINE_LINES = 20

# Fraction of the committed file that must survive before this stays quiet.
# 0.85 flags the >=15% cuts. The incident above was a 23% cut.
KEEP_RATIO = 0.85

_GIT_TIMEOUT_SECONDS = 5


def _committed_line_count(repo: Path, rel_path: str) -> int | None:
    """Lines in `rel_path` at HEAD, or None when git cannot answer.

    None covers every "there is no baseline" case at once -- untracked file, new
    file, no commits yet, not a repo, git missing, binary. All of them mean the
    same thing here: nothing was replaced, so there is nothing to warn about.
    """
    try:
        result = subprocess.run(
            ["git", "-C", str(repo), "show", f"HEAD:{rel_path}"],
            capture_output=True,
            timeout=_GIT_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    try:
        text = result.stdout.decode("utf-8")
    except UnicodeDecodeError:
        return None
    return len(text.splitlines())


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0
    if not isinstance(payload, dict):
        return 0

    # Edit preserves what it does not name; only Write can drop content silently.
    if payload.get("tool_name") != "Write":
        return 0

    tool_input = payload.get("tool_input")
    raw_path = tool_input.get("file_path", "") if isinstance(tool_input, dict) else ""
    if not isinstance(raw_path, str) or not raw_path:
        return 0

    project_root = Path(os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())).resolve()
    file_path = Path(raw_path)
    file_path = (project_root / file_path) if not file_path.is_absolute() else file_path
    try:
        file_path = file_path.resolve()
    except OSError:
        return 0

    if not file_path.is_file():
        return 0

    try:
        rel = file_path.relative_to(project_root).as_posix()
    except ValueError:
        return 0  # outside the project; not ours to judge

    baseline = _committed_line_count(project_root, rel)
    if baseline is None or baseline < MIN_BASELINE_LINES:
        return 0

    try:
        new_lines = len(file_path.read_text(encoding="utf-8").splitlines())
    except (OSError, UnicodeDecodeError):
        return 0

    if new_lines >= baseline * KEEP_RATIO:
        return 0

    dropped = baseline - new_lines
    pct = round(100 * dropped / baseline)
    msg = (
        f"[warn-wholesale-rewrite] {rel}: replaced {baseline} committed lines "
        f"with {new_lines} ({pct}% shorter, {dropped} lines gone).\n"
        "A Write keeps only what you carried across. Before calling this done, "
        "diff it against the committed version and say what you dropped and why "
        "— naming the cuts is the check; a shorter file is not evidence that "
        "nothing was lost."
    )
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": msg,
        }
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
