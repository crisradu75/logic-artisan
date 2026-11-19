"""The save-permissions skill states and performs what the permission-saving spec requires.

Spec: openspec/specs/permission-saving. The merge snippet in the skill is extracted and run on
temporary settings files, so what the user would paste is what is tested.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

_SKILL = Path(__file__).resolve().parents[4] / ".claude" / "plugins" / "cla" / "skills" / "save-permissions" / "SKILL.md"
_SETTINGS = Path(".claude") / "settings.local.json"


def _flat() -> str:
    return " ".join(_SKILL.read_text(encoding="utf-8").split())


def _fenced(lang: str) -> str:
    """The dedented body of the skill's first ```<lang> block."""
    text = _SKILL.read_text(encoding="utf-8").replace("\r\n", "\n")
    opener = f"   ```{lang}\n"
    start = text.index(opener) + len(opener)
    end = text.index("\n   ```\n", start)
    return textwrap.dedent(text[start:end])


def _python_body() -> str:
    """The Python between `python3 -c "` and the closing quote, exactly as the shell receives it."""
    block = _fenced("bash")
    opener = 'python3 -c "\n'
    assert block.startswith(opener) and block.endswith('\n"'), block[:40]
    return block[len(opener):-2]


def _with_entries(body: str, new_entries: list[str]) -> str:
    return "\n".join(f"new = {new_entries!r}" if line.startswith("new = ") else line for line in body.splitlines())


def _merge_script(new_entries: list[str]) -> str:
    """The skill's Python one-liner with its placeholder list replaced."""
    return _with_entries(_python_body(), new_entries)


def _run(cwd: Path, entries: list[str], prelude: str = "") -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-c", prelude + _merge_script(entries)],
        cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30,
    )


def _run_in_bash(cwd: Path, command: str) -> subprocess.CompletedProcess:
    bash = shutil.which("bash")
    if bash is None:
        pytest.skip("bash is not installed")
    python = Path(sys.executable).as_posix()
    return subprocess.run(
        [bash, "-c", command.replace("python3 ", f"'{python}' ", 1)],
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
@pytest.mark.parametrize(
    "content,reason",
    [
        ('{"permissions": {"allow": "Read"}, "hooks": {}}', "permissions.allow in"),
        ('{"permissions": ["Read"]}', "permissions in"),
        ('{"permissions": null}', "permissions in"),
        ('["Read"]', "does not hold a JSON object"),
    ],
)
def test_a_settings_file_of_the_wrong_shape_is_refused_and_left_exactly_as_it_was(tmp_path, content, reason):
    # Before the guard, an `allow` string went through set() and came back split into characters.
    path = _write_settings(tmp_path, content)
    before = path.read_bytes()
    result = _run(tmp_path, ["WebSearch"])
    assert result.returncode != 0
    assert "stopped, nothing written" in result.stderr and reason in result.stderr
    assert path.read_bytes() == before
    assert sorted(p.name for p in path.parent.iterdir()) == ["settings.local.json"]


# requirement: permission-saving / Saving keeps the rest of the settings file
def test_a_failed_replace_leaves_the_original_and_no_temporary_file(tmp_path):
    path = _write_settings(tmp_path, json.dumps({"permissions": {"allow": ["Read"]}}))
    before = path.read_bytes()
    prelude = (
        "import pathlib\n"
        "def _refuse(self, target):\n"
        "    raise OSError('simulated replace failure')\n"
        "pathlib.Path.replace = _refuse\n"
    )
    result = _run(tmp_path, ["WebSearch"], prelude=prelude)
    assert result.returncode != 0
    assert "simulated replace failure" in result.stderr
    assert path.read_bytes() == before
    assert sorted(p.name for p in path.parent.iterdir()) == ["settings.local.json"]


# requirement: permission-saving / Saving keeps the rest of the settings file
def test_a_missing_settings_file_is_created_with_the_new_entries(tmp_path):
    (tmp_path / ".claude").mkdir()
    result = _run(tmp_path, ["WebSearch", "Edit"])
    assert result.returncode == 0, result.stderr
    data = json.loads((tmp_path / _SETTINGS).read_text(encoding="utf-8"))
    assert data == {"permissions": {"allow": ["Edit", "WebSearch"]}}


# requirement: permission-saving / Saving keeps the rest of the settings file
def test_the_bash_form_and_its_heredoc_run_as_pasted(tmp_path):
    # The body has no double quote, `$` or backtick, so the shell hands it to Python unchanged
    # (an escaped quote inside an f-string is a SyntaxError before Python 3.12), and the same
    # body pasted into a quoted heredoc gives the same result.
    body = _python_body()
    assert not set(body) & {'"', "$", "`"}, "the -c body would be changed by the shell"
    one_liner = _with_entries(_fenced("bash"), ["WebSearch"])
    heredoc = "python3 - <<'PYEOF'\n" + _with_entries(body, ["WebSearch"]) + "\nPYEOF\n"
    for name, command in (("one-liner", one_liner), ("heredoc", heredoc)):
        cwd = tmp_path / name
        path = _write_settings(cwd, json.dumps({"permissions": {"allow": ["Read"]}}))
        result = _run_in_bash(cwd, command)
        assert result.returncode == 0, (name, result.stderr)
        assert json.loads(path.read_text(encoding="utf-8")) == {"permissions": {"allow": ["Read", "WebSearch"]}}
    assert "python3 - <<'PYEOF'" in _flat()


# requirement: permission-saving / Saving keeps the rest of the settings file
def test_the_powershell_form_carries_the_same_guards_as_the_python_form():
    # STATIC ONLY: PowerShell is not installed where these tests run, so this form is unexecuted.
    # It checks that the guards the Python form runs above are present and ordered before the write.
    ps = _fenced("powershell")
    assert ps.startswith("$ErrorActionPreference = 'Stop'\n")
    write = ps.index("WriteAllText($tmp")
    for guard in (
        "try { $data = $raw | ConvertFrom-Json } catch { throw",
        "-notmatch '^\\s*\\{') { throw",
        "Add-Member -NotePropertyName permissions",
        "$perms -isnot [System.Management.Automation.PSCustomObject]) { throw",
        "Add-Member -NotePropertyName allow",
        "$perms.allow -isnot [array]) { throw",
    ):
        assert guard in ps, guard
        assert ps.index(guard) < write, guard
    assert ps.index("Move-Item -LiteralPath $tmp -Destination $p -Force") > write
    assert "finally {\n  if (Test-Path -LiteralPath $tmp) { Remove-Item -LiteralPath $tmp -Force }" in ps
    assert "Set-Content" not in ps and "Out-File" not in ps
    # Both forms stop on the same cases, with the same messages.
    reasons = r"stopped, nothing written: [^\"')]*?(?=\(|$|'|\")"
    py = {m.strip() for m in re.findall(reasons, _python_body(), re.M)}
    pw = {m.strip() for m in re.findall(reasons, ps, re.M)}
    norm = lambda found: {m.replace("{p}", "P").replace("$p", "P") for m in found}
    assert norm(py) == norm(pw) and len(py) == 4, (py, pw)


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
