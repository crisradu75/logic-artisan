#!/usr/bin/env python3
"""Refuse a release when Copilot agent copies pin an account-specific model."""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[4]
_SCRIPTS = _REPO_ROOT / "plugin-tests" / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import sync_copilot_agents as sync

EXIT_OK = 0
EXIT_INVALID = 1
EXIT_CANNOT_CHECK = 2


def _declares_model(text: str) -> bool:
    frontmatter, _ = sync.split_frontmatter(text)
    return any(line.partition(":")[0].strip() == "model" for line in frontmatter)


def main() -> int:
    try:
        expected = sync.expected_copies(sync.CLAUDE_DIR)
    except (OSError, ValueError) as err:
        print(f"cannot check Copilot model inheritance: {err}", file=sys.stderr)
        return EXIT_CANNOT_CHECK
    if not expected:
        print("cannot check Copilot model inheritance: no source agents found", file=sys.stderr)
        return EXIT_CANNOT_CHECK

    errors = []
    for name, rendered in expected.items():
        target = sync.COPILOT_DIR / name
        try:
            current = target.read_text(encoding="utf-8")
        except OSError as err:
            errors.append(f"{name}: cannot read generated profile: {err}")
            continue
        if _declares_model(current):
            errors.append(f"{name}: explicit model pins an account-specific Copilot model")
        elif current != rendered:
            errors.append(f"{name}: generated profile is out of step; run sync_copilot_agents.py --write")

    orphans = sorted(
        path.name
        for path in sync.COPILOT_DIR.iterdir()
        if path.is_file() and path.name not in expected
    ) if sync.COPILOT_DIR.is_dir() else []
    errors.extend(f"{name}: no source agent" for name in orphans)
    if errors:
        for error in errors:
            print(f"INVALID {error}", file=sys.stderr)
        return EXIT_INVALID

    print(f"ok: all {len(expected)} Copilot profiles inherit the session model; source aliases are mapped")
    return EXIT_OK


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
