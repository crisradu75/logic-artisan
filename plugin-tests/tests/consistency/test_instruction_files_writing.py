"""Where a skill writes a rule or lesson: the shared instruction-files reference, and the skills
that write to a repo's instruction file point at it.

Spec: openspec/specs/instruction-files. The reading half is pinned by
test_instruction_files_both_named.py.
"""

from __future__ import annotations

import re
from pathlib import Path

_PLUGIN_ROOT = Path(__file__).resolve().parents[3] / ".claude" / "plugins" / "cla"
_REFERENCE = _PLUGIN_ROOT / "skills" / "_shared" / "references" / "instruction-files.md"
_WRITERS = ("codify-learnings", "lite-pr", "cla-setup")


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8").replace("\r\n", "\n")


def _writing() -> str:
    text = _text(_REFERENCE)
    start = text.index("## Writing")
    return " ".join(text[start:].split())


# requirement: instruction-files / A rule is written to the file the repo already uses
def test_the_reference_picks_the_file_by_the_repos_setup():
    section = _writing()
    assert "**Exactly one file exists at the root:** write to it" in section
    assert "`CLAUDE.md` imports or symlinks `AGENTS.md`:** write to `AGENTS.md`" in section
    assert "`@AGENTS.md`" in section
    assert "**Both exist and are not linked:** write to `CLAUDE.md`. Say in the report line which file and why" in section


# requirement: instruction-files / A rule is written to the file the repo already uses
def test_every_skill_that_writes_an_instruction_file_points_at_the_reference():
    for skill in _WRITERS:
        text = _text(_PLUGIN_ROOT / "skills" / skill / "SKILL.md")
        assert "instruction-files.md" in text, f"{skill} writes or reads the instruction file without the shared rule"


# requirement: instruction-files / An instruction file is never created silently
def test_the_reference_never_creates_an_instruction_file_without_asking():
    section = _writing()
    assert re.search(r"\*\*Neither exists:\*\* ask the user which one to create\. Never create one silently\.", section)


# requirement: instruction-files / Every instruction file is read
def test_the_reference_reads_both_files_when_both_exist():
    text = " ".join(_text(_REFERENCE).split())
    assert "Read every instruction file that exists: `CLAUDE.md` and `AGENTS.md`, at the root and nested for the affected area. When both exist, read both." in text
