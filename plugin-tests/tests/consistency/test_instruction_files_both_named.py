"""Shipped text that sends a model to a repo's `CLAUDE.md` must also name `AGENTS.md`.

Claude Code loads `AGENTS.md` by itself only when no `CLAUDE.md` exists, so a skill that says
"read the repo's CLAUDE.md" leaves AGENTS.md-only rules invisible. A file that names `CLAUDE.md`
passes when it also names `AGENTS.md` or the shared `instruction-files.md` reference.
"""

from __future__ import annotations

from pathlib import Path

_PLUGIN_ROOT = Path(__file__).resolve().parents[3] / ".claude" / "plugins" / "cla"

# Files that name CLAUDE.md on purpose, with the reason each is allowed to.
_EXCEPTIONS = {
    # Describes this source repo's own CLAUDE.md, not a client repo's.
    "skills/_shared/references/bash-discipline.md",
    # Quotes this source repo's own CLAUDE.md rule ("break the fix and confirm a test fails").
    "skills/_shared/references/test-quality-gates.md",
}

_SCANNED = ("skills", "agents", "com.github.copilot/agents")


def _shipped_prose():
    for top in _SCANNED:
        for path in sorted((_PLUGIN_ROOT / top).rglob("*.md")):
            if path.name.lower() != "readme.md":
                yield path


def test_shipped_text_naming_claude_md_also_names_agents_md():
    files = list(_shipped_prose())
    assert len(files) > 50, "the scan found too few files to mean anything"
    naming = [p for p in files if "CLAUDE.md" in p.read_text(encoding="utf-8")]
    assert len(naming) >= 10, "too few files name CLAUDE.md; the scan is looking elsewhere"
    bad = []
    for p in naming:
        rel = p.relative_to(_PLUGIN_ROOT).as_posix()
        text = p.read_text(encoding="utf-8")
        if rel in _EXCEPTIONS or "AGENTS.md" in text or "instruction-files.md" in text:
            continue
        bad.append(rel)
    assert not bad, (
        f"{bad} name CLAUDE.md as a rules source without AGENTS.md or instruction-files.md; "
        "see skills/_shared/references/instruction-files.md"
    )
    names = {p.relative_to(_PLUGIN_ROOT).as_posix() for p in naming}
    stale = [
        e for e in _EXCEPTIONS
        if e not in names
        or "AGENTS.md" in (_PLUGIN_ROOT / e).read_text(encoding="utf-8")
        or "instruction-files.md" in (_PLUGIN_ROOT / e).read_text(encoding="utf-8")
    ]
    assert not stale, f"exceptions that no longer need to be exceptions: {stale}"
