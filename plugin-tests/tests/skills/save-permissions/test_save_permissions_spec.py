"""The save-permissions skill states and performs what the permission-saving spec requires.

Spec: openspec/specs/permission-saving. The merge snippet in the skill is extracted and run on
temporary settings files, so what the user would paste is what is tested.
"""

from __future__ import annotations

import json
import subprocess
import sys
import textwrap
from pathlib import Path

_SKILL = Path(__file__).resolve().parents[4] / ".claude" / "plugins" / "cla" / "skills" / "save-permissions" / "SKILL.md"
_SETTINGS = Path(".claude") / "settings.local.json"


def _flat() -> str:
    return " ".join(_SKILL.read_text(encoding="utf-8").split())


def _merge_script(new_entries: list[str]) -> str:
    """The skill's Python one-liner, with its shell escapes undone and its placeholder list replaced."""
    text = _SKILL.read_text(encoding="utf-8").replace("\r\n", "\n")
    opener = 'python3 -c "\n'
    start = text.index(opener) + len(opener)
    end = text.index('\n   "\n', start)
    body = textwrap.dedent(text[start:end]).replace('\\"', '"')
    lines = [f"new = {new_entries!r}" if line.startswith("new = ") else line for line in body.splitlines()]
    return "\n".join(lines)


def _run(cwd: Path, entries: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-c", _merge_script(entries)],
        cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30,
    )


def _write_settings(cwd: Path, content: str) -> Path:
    path = cwd / _SETTINGS
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


# requirement: permission-saving / Only new permissions are listed
def test_the_skill_lists_only_new_entries_and_stops_when_there_are_none():
    text = _flat()
    assert "list the NEW permissions (the ones not already in the file)" in text
    assert "If there are none, say so and stop" in text
    assert "ONLY the new entries from step 3" in text


# requirement: permission-saving / Saving keeps the rest of the settings file
def test_an_allowlist_is_created_and_other_settings_survive(tmp_path):
    path = _write_settings(tmp_path, json.dumps({"hooks": {"Stop": []}}))
    result = _run(tmp_path, ["WebSearch"])
    assert result.returncode == 0, result.stderr
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data == {"hooks": {"Stop": []}, "permissions": {"allow": ["WebSearch"]}}


# requirement: permission-saving / Saving keeps the rest of the settings file
def test_new_entries_join_the_existing_ones_and_no_temporary_file_is_left(tmp_path):
    path = _write_settings(tmp_path, json.dumps({"permissions": {"allow": ["Read", "Edit"], "deny": ["X"]}}))
    result = _run(tmp_path, ["Edit", "Skill(foo)"])
    assert result.returncode == 0, result.stderr
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["permissions"] == {"allow": ["Edit", "Read", "Skill(foo)"], "deny": ["X"]}
    assert sorted(p.name for p in path.parent.iterdir()) == ["settings.local.json"]


# requirement: permission-saving / Saving keeps the rest of the settings file
def test_a_file_that_is_not_json_is_left_exactly_as_it_was(tmp_path):
    path = _write_settings(tmp_path, '{"permissions": {"allow": [')
    before = path.read_bytes()
    result = _run(tmp_path, ["WebSearch"])
    assert result.returncode != 0
    assert path.read_bytes() == before
    assert sorted(p.name for p in path.parent.iterdir()) == ["settings.local.json"]


# requirement: permission-saving / Saving keeps the rest of the settings file
def test_the_skill_writes_only_the_local_settings_file_with_the_script_not_the_write_tool():
    text = _flat()
    assert "Path('.claude/settings.local.json')" in text
    assert "Do NOT use the `Write` tool on `settings.local.json`" in text


# requirement: permission-saving / A wildcard permission needs the user's yes
def test_a_wildcard_entry_is_confirmed_and_never_retried_in_another_phrasing():
    text = _flat()
    assert "present it as a question and get explicit confirmation before writing it" in text
    assert "Do not self-classify a wildcard as \"narrow enough to skip asking\"" in text
    assert "retrying different wildcard phrasings after a block is itself a bad pattern" in text
    assert "This applies only to exact, non-wildcard entries" in text
