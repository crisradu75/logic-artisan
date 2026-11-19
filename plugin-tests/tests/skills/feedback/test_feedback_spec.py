"""The feedback skill states each outcome the session-records spec requires of it.

Spec: openspec/specs/session-records. The skill is prose, so these tests pin the text that carries
each outcome and the frontmatter that backs the read-only promise mechanically.
"""

from __future__ import annotations

from pathlib import Path

_SKILL = Path(__file__).resolve().parents[4] / ".claude" / "plugins" / "cla" / "skills" / "feedback" / "SKILL.md"


def _raw() -> str:
    return _SKILL.read_text(encoding="utf-8")


def _flat() -> str:
    return " ".join(_raw().split())


def _allowed_tools() -> list[str]:
    for line in _raw().splitlines():
        if line.startswith("allowed-tools:"):
            return [tool.strip() for tool in line.split(":", 1)[1].split(",")]
    raise AssertionError("feedback lost its allowed-tools line")


# requirement: session-records / Feedback notes are taken one at a time and read-only grounded
def test_notes_are_taken_one_at_a_time_and_grounded_without_editing_source():
    text = _flat()
    assert "One note per turn — don't batch" in text
    assert "do **not** invent a question" in text
    assert "`probable cause (unverified):`" in text
    assert "never edit or overwrite source files, never run the app" in text


# requirement: session-records / Feedback notes are taken one at a time and read-only grounded
def test_the_frontmatter_grants_no_tool_that_edits_source_or_runs_commands():
    tools = _allowed_tools()
    for forbidden in ("Edit", "Bash", "NotebookEdit"):
        assert forbidden not in tools


# requirement: session-records / Feedback writes a new file and never overwrites
def test_the_triage_file_is_created_first_suffixed_not_overwritten_and_the_inbox_is_untouched():
    text = _flat()
    assert "Create the deliverable file immediately" in text
    assert "append a numeric suffix (`-2`, `-3`, …) rather than overwriting an earlier run" in text
    assert "Don't silently ingest it" in text
    assert "does **not** own or rewrite it" in text
    assert "Clearing `notes.md` afterward is the user's explicit call, never automatic" in text


# requirement: session-records / Near-duplicate notes merge only on confirmation
def test_a_merge_is_proposed_and_made_only_on_confirmation():
    text = _flat()
    assert "Merge near-duplicates — but only with per-merge confirmation" in text
    assert "merge only on confirmation" in text
