"""Contract tests for the Copilot CLI hook adapter and wiring."""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

_PLUGIN = Path(__file__).resolve().parents[3] / ".claude" / "plugins" / "cla"
_COPILOT_HOOKS = _PLUGIN / "com.github.copilot" / "hooks" / "hooks.json"
_CLAUDE_HOOKS = _PLUGIN / "hooks" / "hooks.json"


def _config() -> dict:
    return json.loads(_COPILOT_HOOKS.read_text(encoding="utf-8"))


# requirement: guard-hooks / Copilot CLI enforces session guards
def test_copilot_plugin_wires_matching_pre_and_post_tool_hooks():
    config = _config()
    assert config["version"] == 1
    hooks = config["hooks"]
    pre = hooks["PreToolUse"]
    assert {group["matcher"] for group in pre} == {"Bash|PowerShell", "Edit|Write"}
    assert [(group["matcher"], hook["timeoutSec"])
            for group in pre for hook in group["hooks"]] == [
                ("Bash|PowerShell", 30),
                ("Edit|Write", 30),
            ]
    assert len(hooks["PostToolUse"]) == 1
    post = hooks["PostToolUse"][0]
    assert post["matcher"] == "Write"
    assert post["hooks"][0]["timeoutSec"] == 30
    for group in [*pre, *hooks["PostToolUse"]]:
        for hook in group["hooks"]:
            assert hook["type"] == "command"
            assert "COPILOT_PLUGIN_ROOT" in hook["bash"]
            assert "COPILOT_PLUGIN_ROOT" in hook["powershell"]


def test_copilot_hook_commands_resolve_and_keep_platform_launchers():
    config = _config()
    root = _PLUGIN.resolve()
    expected = {
        "hooks/copilot-pretooluse.py",
        "hooks/copilot-posttooluse.py",
        "hooks/probe-python.sh",
        "hooks/probe-python.ps1",
    }
    assert all((root / path).is_file() for path in expected)
    commands = [
        command
        for groups in config["hooks"].values()
        for group in groups
        for hook in group["hooks"]
        for command in (hook["bash"], hook["powershell"])
    ]
    assert all("probe-python.sh" in command or "probe-python.ps1" in command
               for command in commands)


def test_claude_hook_wiring_remains_separate():
    claude = json.loads(_CLAUDE_HOOKS.read_text(encoding="utf-8"))
    assert "PreToolUse" in claude["hooks"]
    assert "PostToolUse" in claude["hooks"]
    assert all("COPILOT_PLUGIN_ROOT" not in hook.get("command", "")
               for groups in claude["hooks"].values()
               for group in groups
               for hook in group["hooks"])


# requirement: guard-hooks / Copilot hook failures have an explicit policy
def test_copilot_timeout_covers_the_dispatcher_budget():
    spec = importlib.util.spec_from_file_location(
        "copilot_wiring_dispatch_lib",
        _PLUGIN / "hooks" / "_dispatch_lib.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    timeouts = {
        hook["timeoutSec"]
        for groups in _config()["hooks"].values()
        for group in groups
        for hook in group["hooks"]
    }
    assert timeouts == {30}
    assert min(timeouts) >= module.HANDLER_TIMEOUT_SECONDS + module._BUDGET_RESERVE_SECONDS


def _run_hook(
    script: Path,
    payload: dict | str,
    cwd: Path,
    plugin_root: Path = _PLUGIN,
) -> subprocess.CompletedProcess:
    env = {
        **os.environ,
        "COPILOT_PLUGIN_ROOT": str(plugin_root),
        "ALLOW_DESTRUCTIVE_GIT": "",
        "ALLOW_PR_MERGE": "",
        "ALLOW_WORKTREE_PATH_ESCAPE": "",
        "ALLOW_SHARED_CLONE_MUTATION": "",
        "ALLOW_GIT_IDENTITY_MISMATCH": "",
        "CLA_EXPECTED_GIT_EMAIL": "",
        "CLAUDE_PROJECT_DIR": str(cwd),
    }
    return subprocess.run(
        [sys.executable, str(script)],
        input=payload if isinstance(payload, str) else json.dumps(payload),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=cwd,
        env=env,
    )


def _pre_event(tool_name: str, tool_input: dict, cwd: Path) -> dict:
    return {
        "hook_event_name": "PreToolUse",
        "session_id": "test-session",
        "timestamp": "2026-11-04T00:00:00Z",
        "cwd": str(cwd),
        "tool_name": tool_name,
        "tool_input": tool_input,
    }


# requirement: guard-hooks / Copilot CLI enforces session guards
def test_copilot_pretooluse_leaves_a_clean_call_to_normal_permission_flow(tmp_path):
    adapter = _PLUGIN / "hooks" / "copilot-pretooluse.py"
    result = _run_hook(
        adapter,
        _pre_event("Bash", {"command": "git status --short"}, tmp_path),
        tmp_path,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == ""


def test_copilot_pretooluse_denies_a_blocked_call_with_a_reason(tmp_path):
    adapter = _PLUGIN / "hooks" / "copilot-pretooluse.py"
    result = _run_hook(
        adapter,
        _pre_event("Bash", {"command": "cd /tmp && pwd"}, tmp_path),
        tmp_path,
    )
    assert result.returncode == 0, result.stderr
    decision = json.loads(result.stdout)
    assert decision["permissionDecision"] == "deny"
    assert "block-cd-in-bash.py" in decision["permissionDecisionReason"]


def test_copilot_pretooluse_preserves_a_destructive_git_confirmation(tmp_path):
    adapter = _PLUGIN / "hooks" / "copilot-pretooluse.py"
    result = _run_hook(
        adapter,
        _pre_event(
            "Bash",
            {"command": "git push --force origin feature/x"},
            tmp_path,
        ),
        tmp_path,
    )
    assert result.returncode == 0, result.stderr
    decision = json.loads(result.stdout)
    assert decision["permissionDecision"] == "ask"
    assert "force-push" in decision["permissionDecisionReason"]


def test_copilot_pretooluse_translates_an_advisory_warning(tmp_path):
    adapter = _PLUGIN / "hooks" / "copilot-pretooluse.py"
    result = _run_hook(
        adapter,
        _pre_event(
            "Edit",
            {
                "file_path": str(tmp_path / "source.py"),
                "new_string": "# fixed on 2026-11-04\n",
            },
            tmp_path,
        ),
        tmp_path,
    )
    assert result.returncode == 0, result.stderr
    decision = json.loads(result.stdout)
    assert "additionalContext" in decision
    assert "YYYY-MM-DD" in decision["additionalContext"]


def test_copilot_posttooluse_translates_rewrite_warning(tmp_path):
    repo = tmp_path
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run(
        ["git", "-C", str(repo), "config", "user.email", "test@example.com"],
        check=True,
    )
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "Test"], check=True)
    target = repo / "long.md"
    target.write_text(("content " * 200) + "\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "long.md"], check=True)
    subprocess.run(
        ["git", "-C", str(repo), "commit", "-qm", "baseline"],
        check=True,
    )

    adapter = _PLUGIN / "hooks" / "copilot-posttooluse.py"
    event = {
        "hook_event_name": "PostToolUse",
        "session_id": "test-session",
        "timestamp": "2026-11-04T00:00:00Z",
        "cwd": str(repo),
        "tool_name": "Write",
        "tool_input": {"file_path": str(target), "content": "short\n"},
        "tool_result": {"result_type": "success", "text_result_for_llm": "written"},
    }
    target.write_text("short\n", encoding="utf-8")
    result = _run_hook(adapter, event, repo)
    assert result.returncode == 0, result.stderr
    output = json.loads(result.stdout)
    assert "additionalContext" in output
    assert "words gone" in output["additionalContext"]


def _copy_adapter_tree(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "plugin"
    hooks = root / "hooks"
    hooks.mkdir(parents=True)
    for source in (_PLUGIN / "hooks").glob("*.py"):
        shutil.copy2(source, hooks / source.name)
    return root, hooks / "copilot-pretooluse.py"


# requirement: guard-hooks / Copilot hook failures have an explicit policy
def test_copilot_pretooluse_denies_malformed_input(tmp_path):
    adapter = _PLUGIN / "hooks" / "copilot-pretooluse.py"
    result = _run_hook(adapter, "{", tmp_path)
    assert result.returncode == 0, result.stderr
    decision = json.loads(result.stdout)
    assert decision["permissionDecision"] == "deny"
    assert "malformed Copilot hook input" in decision["permissionDecisionReason"]


def test_copilot_pretooluse_denies_when_required_arguments_are_missing(tmp_path):
    adapter = _PLUGIN / "hooks" / "copilot-pretooluse.py"
    result = _run_hook(adapter, _pre_event("Bash", {}, tmp_path), tmp_path)
    assert result.returncode == 0, result.stderr
    decision = json.loads(result.stdout)
    assert decision["permissionDecision"] == "deny"
    assert "no shell command" in decision["permissionDecisionReason"]


def test_copilot_pretooluse_denies_when_dispatcher_is_missing(tmp_path):
    root, adapter = _copy_adapter_tree(tmp_path)
    (root / "hooks" / "dispatch-bash-pretooluse.py").unlink()
    result = _run_hook(
        adapter,
        _pre_event("Bash", {"command": "echo safe"}, tmp_path),
        tmp_path,
        root,
    )
    assert result.returncode == 0, result.stderr
    decision = json.loads(result.stdout)
    assert decision["permissionDecision"] == "deny"
    assert "could not run" in decision["permissionDecisionReason"]


def test_copilot_pretooluse_denies_when_a_required_guard_is_missing(tmp_path):
    root, adapter = _copy_adapter_tree(tmp_path)
    (root / "hooks" / "block-cd-in-bash.py").unlink()
    result = _run_hook(
        adapter,
        _pre_event("Bash", {"command": "cd /tmp && pwd"}, tmp_path),
        tmp_path,
        root,
    )
    assert result.returncode == 0, result.stderr
    decision = json.loads(result.stdout)
    assert decision["permissionDecision"] == "deny"
    assert "could not run" in decision["permissionDecisionReason"]


def test_copilot_pretooluse_denies_when_dispatcher_returns_malformed_output(tmp_path):
    root, adapter = _copy_adapter_tree(tmp_path)
    (root / "hooks" / "dispatch-bash-pretooluse.py").write_text(
        "def main():\n    print('not json')\n    return 0\n",
        encoding="utf-8",
    )
    result = _run_hook(
        adapter,
        _pre_event("Bash", {"command": "echo safe"}, tmp_path),
        tmp_path,
        root,
    )
    assert result.returncode == 0, result.stderr
    decision = json.loads(result.stdout)
    assert decision["permissionDecision"] == "deny"
    assert "malformed output" in decision["permissionDecisionReason"]


def test_copilot_pretooluse_denies_when_dispatcher_crashes(tmp_path):
    root, adapter = _copy_adapter_tree(tmp_path)
    (root / "hooks" / "dispatch-bash-pretooluse.py").write_text(
        "def main():\n    raise RuntimeError('dispatcher crash')\n",
        encoding="utf-8",
    )
    result = _run_hook(
        adapter,
        _pre_event("Bash", {"command": "echo safe"}, tmp_path),
        tmp_path,
        root,
    )
    assert result.returncode == 0, result.stderr
    decision = json.loads(result.stdout)
    assert decision["permissionDecision"] == "deny"
    assert "could not run" in decision["permissionDecisionReason"]
    assert "dispatcher crash" in result.stderr
