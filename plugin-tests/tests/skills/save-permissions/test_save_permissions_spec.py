"""The save-permissions skill states and performs what the permission-saving spec requires.

Spec: openspec/specs/permission-saving. The skill's step 4 is one command that runs the bundled
`merge_permissions.py`; these tests run that script on temporary settings files, and run the
command exactly as the skill writes it, so what the agent would run is what is tested.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import stat
import subprocess
import sys
from pathlib import Path

import pytest

_SKILL_DIR = Path(__file__).resolve().parents[4] / ".claude" / "plugins" / "cla" / "skills" / "save-permissions"
_SKILL = _SKILL_DIR / "SKILL.md"
_SCRIPT = _SKILL_DIR / "scripts" / "merge_permissions.py"
_PLUGIN = _SKILL_DIR.parents[1]
_SETTINGS = Path(".claude") / "settings.local.json"


def _flat() -> str:
    return " ".join(_SKILL.read_text(encoding="utf-8").split())


def _run(cwd: Path, entries: list[str], prelude: str = "", stdin: str | None = None) -> subprocess.CompletedProcess:
    if prelude:
        code = prelude + f"import runpy, sys\nsys.argv = [{str(_SCRIPT)!r}, *{entries!r}]\nrunpy.run_path({str(_SCRIPT)!r}, run_name='__main__')\n"
        cmd = [sys.executable, "-c", code]
    else:
        cmd = [sys.executable, str(_SCRIPT), *entries]
    return subprocess.run(
        cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30,
        input=stdin if stdin is not None else "",
    )


def _write_settings(cwd: Path, content: str | bytes) -> Path:
    path = cwd / _SETTINGS
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content.encode("utf-8") if isinstance(content, str) else content)
    return path


def _left(path: Path) -> list[str]:
    return sorted(p.name for p in path.parent.iterdir())


# requirement: permission-saving / Only new permissions are listed
def test_the_skill_lists_only_new_entries_and_stops_when_there_are_none():
    text = _flat()
    assert "list the NEW permissions (the ones not already in the file)" in text
    assert "If there are none, say so and stop" in text
    assert "pass ONLY the new entries from step 3" in text


# requirement: permission-saving / Only new permissions are listed
def test_no_entry_is_a_usage_error_and_writes_nothing(tmp_path):
    path = _write_settings(tmp_path, '{"permissions": {"allow": ["Read"]}}')
    before = path.read_bytes()
    for entries, stdin in (([], ""), ([], "\n  \n"), ([""], None)):
        result = _run(tmp_path, entries, stdin=stdin)
        assert result.returncode == 2, (entries, stdin, result.stderr)
        assert "nothing written" in result.stderr
    assert path.read_bytes() == before


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
    assert _left(path) == ["settings.local.json"]
    assert result.stdout.strip() == "added 1 new permission(s); allowlist now has 3 entries"


# requirement: permission-saving / Saving keeps the rest of the settings file
def test_the_merge_is_sorted_by_code_point_and_written_with_two_space_indent(tmp_path):
    path = _write_settings(tmp_path, json.dumps({"permissions": {"allow": ["b", "Ä", "b"]}}))
    assert _run(tmp_path, ["B", "a", "Bash(git log *)"]).returncode == 0
    assert path.read_bytes() == (json.dumps({"permissions": {"allow": ["B", "Bash(git log *)", "a", "b", "Ä"]}},
                                            indent=2) + "\n").encode("utf-8")


# requirement: permission-saving / Saving keeps the rest of the settings file
def test_entries_can_come_one_per_line_on_stdin(tmp_path):
    path = _write_settings(tmp_path, "{}")
    result = _run(tmp_path, [], stdin="WebSearch\r\n\n  Bash(echo 'x' *)  \n")
    assert result.returncode == 0, result.stderr
    assert json.loads(path.read_text(encoding="utf-8")) == {"permissions": {"allow": ["Bash(echo 'x' *)", "WebSearch"]}}


# requirement: permission-saving / Saving keeps the rest of the settings file
def test_a_byte_order_mark_is_accepted(tmp_path):
    path = _write_settings(tmp_path, b"\xef\xbb\xbf" + json.dumps({"permissions": {"allow": ["Edit"]}}).encode())
    assert _run(tmp_path, ["Read"]).returncode == 0
    assert json.loads(path.read_bytes()) == {"permissions": {"allow": ["Edit", "Read"]}}


# requirement: permission-saving / Saving keeps the rest of the settings file
@pytest.mark.parametrize(
    "content,reason",
    [
        (b'{"permissions": {"allow": [', "is not valid JSON"),
        (b'{"permissions": {"allow": ["\xff"]}}', "is not valid JSON"),
    ],
    ids=["truncated", "not-utf-8"],
)
def test_a_file_that_is_not_json_is_left_exactly_as_it_was(tmp_path, content, reason):
    path = _write_settings(tmp_path, content)
    result = _run(tmp_path, ["WebSearch"])
    assert result.returncode == 1
    assert "stopped, nothing written" in result.stderr and reason in result.stderr
    assert path.read_bytes() == content
    assert _left(path) == ["settings.local.json"]


# requirement: permission-saving / Saving keeps the rest of the settings file
@pytest.mark.parametrize(
    "content,reason",
    [
        ('{"permissions": {"allow": "Read"}, "hooks": {}}', "permissions.allow in"),
        ('{"permissions": {"allow": ["Read", 1]}}', "permissions.allow in"),
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
    assert result.returncode == 1
    assert "stopped, nothing written" in result.stderr and reason in result.stderr
    assert path.read_bytes() == before
    assert _left(path) == ["settings.local.json"]


# requirement: permission-saving / Saving keeps the rest of the settings file
def test_a_failed_replace_leaves_the_original_and_no_temporary_file(tmp_path):
    path = _write_settings(tmp_path, json.dumps({"permissions": {"allow": ["Read"]}}))
    before = path.read_bytes()
    prelude = (
        "import os\n"
        "def _refuse(src, dst):\n"
        "    raise OSError('simulated replace failure')\n"
        "os.replace = _refuse\n"
    )
    result = _run(tmp_path, ["WebSearch"], prelude=prelude)
    assert result.returncode == 1
    assert "stopped, nothing written" in result.stderr and "simulated replace failure" in result.stderr
    assert path.read_bytes() == before
    assert _left(path) == ["settings.local.json"]


# requirement: permission-saving / Saving keeps the rest of the settings file
def test_the_temporary_file_has_a_unique_name_and_spares_a_file_of_the_old_fixed_name(tmp_path):
    path = _write_settings(tmp_path, "{}")
    stale = path.with_name("settings.local.json.tmp")
    stale.write_bytes(b"someone else's file\n")
    assert _run(tmp_path, ["Read"]).returncode == 0
    assert stale.read_bytes() == b"someone else's file\n"
    assert _left(path) == ["settings.local.json", "settings.local.json.tmp"]


# requirement: permission-saving / Saving keeps the rest of the settings file
@pytest.mark.skipif(os.name == "nt", reason="POSIX permission bits")
def test_a_replaced_file_keeps_its_permission_bits(tmp_path):
    path = _write_settings(tmp_path, "{}")
    path.chmod(0o640)  # not 0o600, which mkstemp gives a temp file anyway
    assert _run(tmp_path, ["Read"]).returncode == 0
    assert stat.S_IMODE(path.stat().st_mode) == 0o640


# requirement: permission-saving / Saving keeps the rest of the settings file
@pytest.mark.skipif(os.name == "nt", reason="a symlink needs a privilege on Windows")
def test_a_symlinked_settings_file_is_refused_and_its_target_left_alone(tmp_path):
    target = tmp_path / "elsewhere.json"
    target.write_bytes(b"{}")
    (tmp_path / ".claude").mkdir()
    (tmp_path / _SETTINGS).symlink_to(target)
    result = _run(tmp_path, ["Read"])
    assert result.returncode == 1 and "symbolic link" in result.stderr
    assert (tmp_path / _SETTINGS).is_symlink() and target.read_bytes() == b"{}"


# requirement: permission-saving / Saving keeps the rest of the settings file
def test_a_missing_settings_file_is_created_with_the_new_entries(tmp_path):
    for cwd in (tmp_path / "with-dir", tmp_path / "no-dir"):
        cwd.mkdir()
        if cwd.name == "with-dir":
            (cwd / ".claude").mkdir()
        result = _run(cwd, ["WebSearch", "Edit"])
        assert result.returncode == 0, result.stderr
        data = json.loads((cwd / _SETTINGS).read_text(encoding="utf-8"))
        assert data == {"permissions": {"allow": ["Edit", "WebSearch"]}}


def _command() -> str:
    text = _SKILL.read_text(encoding="utf-8").replace("\r\n", "\n")
    blocks = re.findall(r"   ```bash\n(.*?)\n   ```\n", text, re.S)
    assert len(blocks) == 1, f"step 4 should hold exactly one bash block, found {len(blocks)}"
    return blocks[0].strip()


# requirement: permission-saving / Saving keeps the rest of the settings file
def test_the_skill_command_runs_as_written(tmp_path):
    bash = shutil.which("bash")
    if bash is None:
        pytest.skip("bash is not installed")
    command = _command()
    assert command.startswith('python3 "${CLAUDE_PLUGIN_ROOT}/skills/save-permissions/scripts/merge_permissions.py" ')
    command = command.replace("${CLAUDE_PLUGIN_ROOT}", _PLUGIN.as_posix()).replace(
        "python3 ", f"'{Path(sys.executable).as_posix()}' ", 1)
    path = _write_settings(tmp_path, json.dumps({"permissions": {"allow": ["Read"]}}))
    result = subprocess.run([bash, "-c", command], cwd=tmp_path, capture_output=True, text=True,
                            encoding="utf-8", errors="replace", timeout=30)
    assert result.returncode == 0, result.stderr
    assert json.loads(path.read_text(encoding="utf-8")) == {
        "permissions": {"allow": ["Read", "Skill(...)", "WebFetch(domain:...)"]}}


# requirement: permission-saving / Saving keeps the rest of the settings file
def test_the_skill_carries_no_inline_merge_script():
    text = _SKILL.read_text(encoding="utf-8")
    assert "```powershell" not in text and "python3 -c" not in text and "json.loads" not in text


# requirement: permission-saving / Saving keeps the rest of the settings file
def test_the_skill_writes_only_the_local_settings_file_with_the_script_not_the_write_tool():
    text = _flat()
    assert "skills/save-permissions/scripts/merge_permissions.py" in text
    assert "Do NOT use the `Write` tool on `settings.local.json`" in text
    source = _SCRIPT.read_text(encoding="utf-8")
    assert 'SETTINGS = Path(".claude") / "settings.local.json"' in source
    assert "argparse" not in source, "the script must take no option that names another file"


# requirement: permission-saving / A wildcard permission needs the user's yes
def test_a_wildcard_entry_is_confirmed_and_never_retried_in_another_phrasing():
    text = _flat()
    assert "present it as a question and get explicit confirmation before writing it" in text
    assert "Do not self-classify a wildcard as \"narrow enough to skip asking\"" in text
    assert "retrying different wildcard phrasings after a block is itself a bad pattern" in text
    assert "This applies only to exact, non-wildcard entries" in text
