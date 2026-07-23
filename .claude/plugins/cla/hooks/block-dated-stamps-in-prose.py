#!/usr/bin/env python3
"""PreToolUse hook: block dated/PR-numbered stamps in surviving Markdown prose.

Convention: keep "today", PR numbers, dates, "post-PR-N", "as of PR-M",
"live since YYYY-MM-DD" out of code comments AND SKILL.md / README / docs
prose. The rotting context belongs in PR descriptions.

Pre-merge reviews tend to catch these stamps only after they are written; a
deterministic PreToolUse hook prevents the initial write instead.

The sibling hook `warn-comment-dates.py` covers `.py` / `.sh` code comments
(non-blocking warning). This hook covers `.md` surviving prose (blocking).
The two are complementary and intentionally split:
  - Code comments may legitimately mention dates inside docstring examples;
    warning lets the author confirm.
  - Surviving prose in SKILL.md / CLAUDE.md / README.md is read by future
    sessions out of context; dated stamps actively mislead, so blocking is
    appropriate.

Scope: `.md` files under any of:
  - `.claude/` (skills, commands, references, lessons-learned)
  - any path ending in `SKILL.md`, `CLAUDE.md`, `README.md`

Patterns blocked:
  - `(added YYYY-MM-DD)`
  - `post-PR-<digits>`
  - `as of PR-<digits>`
  - `live since YYYY-MM-DD`

Override: set `ALLOW_DATED_PROSE=1` in env when a legitimate case arises
(documenting changelog-writing style, citing a published date, etc.).

Exit codes:
  0 — allow
  2 — block with stderr explaining the rule
"""
from __future__ import annotations

import json
import os
import re
import sys


PATTERNS = [
    re.compile(r"\(added \d{4}-\d{2}-\d{2}\)"),
    re.compile(r"\bpost-PR-\d+\b"),
    re.compile(r"\bas of PR-?\d+\b"),
    re.compile(r"\blive since \d{4}-\d{2}-\d{2}\b"),
]


def _path_in_scope(path: str) -> bool:
    """Match `.md` files where surviving prose lives.

    Exclude:
      - lessons-learned*.md — intentionally dated session reports.
      - .claude/changes/**, openspec/changes/** — OpenSpec change directories
        whose proposal/design/tasks/spec files cite dates by design.
    """
    if not path.endswith(".md"):
        return False
    norm = path.replace("\\", "/")
    base = norm.rsplit("/", 1)[-1]
    if base.startswith("lessons-learned"):
        return False
    if "/openspec/" in norm or norm.startswith("openspec/"):
        return False
    if "/.claude/" in norm or norm.startswith(".claude/"):
        return True
    return base in {"SKILL.md", "CLAUDE.md", "README.md"}


def _find_hits(content: str) -> list[str]:
    hits = []
    for pat in PATTERNS:
        for m in pat.finditer(content):
            hits.append(m.group(0))
    return hits


def main() -> int:
    if os.environ.get("ALLOW_DATED_PROSE") == "1":
        return 0
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0
    tool_input = payload.get("tool_input", {}) if isinstance(payload, dict) else {}
    if not isinstance(tool_input, dict):
        return 0
    path = tool_input.get("file_path", "")
    if not isinstance(path, str) or not _path_in_scope(path):
        return 0
    # Edit supplies `new_string`; Write supplies `content`.
    added = tool_input.get("new_string") or tool_input.get("content") or ""
    if not isinstance(added, str):
        return 0
    hits = _find_hits(added)
    if not hits:
        return 0
    print(
        "blocked: dated/PR-numbered stamps in surviving prose. "
        f"Hits: {hits[:5]!r}. "
        "Move the rotting context to the PR description instead. "
        "(override with ALLOW_DATED_PROSE=1; hook: block-dated-stamps-in-prose.py)",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
