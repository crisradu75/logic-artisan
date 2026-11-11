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


# requirement: copilot-cli / Copilot CLI enforces session guards
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


# requirement: copilot-cli / Copilot hook failures have an explicit policy
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
    extra_env: dict | None = None,
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
        **(extra_env or {}),
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


# requirement: copilot-cli / Copilot CLI enforces session guards
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


# requirement: copilot-cli / Copilot hook failures have an explicit policy
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


# ---------------------------------------------------------------------------
# Failure paths, launchers and wording drift. Everything writes under tmp_path.
# ---------------------------------------------------------------------------

_ROOT_VARS = ("COPILOT_PLUGIN_ROOT", "PLUGIN_ROOT", "CLAUDE_PLUGIN_ROOT")


def _run_no_root(script: Path, payload: dict | str, cwd: Path) -> subprocess.CompletedProcess:
    env = {k: v for k, v in os.environ.items() if k not in _ROOT_VARS}
    return subprocess.run(
        [sys.executable, str(script)],
        input=payload if isinstance(payload, str) else json.dumps(payload),
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=cwd, env=env,
    )


def _post_event(work: Path, **overrides) -> dict:
    cwd = work
    event = {
        "hook_event_name": "PostToolUse",
        "session_id": "test-session",
        "timestamp": "2026-11-04T00:00:00Z",
        "cwd": str(cwd),
        "tool_name": "Write",
        "tool_input": {"file_path": str(cwd / "x.md"), "content": "x\n"},
        "tool_result": {"result_type": "success", "text_result_for_llm": "ok"},
    }
    event.update(overrides)
    return event


def _fake_dispatcher(tmp_path: Path, body: str) -> tuple[Path, Path]:
    """A copied plugin tree whose Bash dispatcher is replaced by `body`."""
    root, adapter = _copy_adapter_tree(tmp_path)
    (root / "hooks" / "dispatch-bash-pretooluse.py").write_text(body, encoding="utf-8")
    return root, adapter


def _pre_with_fake(tmp_path: Path, body: str) -> subprocess.CompletedProcess:
    root, adapter = _fake_dispatcher(tmp_path, body)
    return _run_hook(adapter, _pre_event("Bash", {"command": "echo safe"}, tmp_path), tmp_path, root)


def _nested(**fields) -> str:
    return "import json\ndef main():\n    print(json.dumps({'hookSpecificOutput': %r}))\n    return 0\n" % (fields,)


def _denied(result, fragment: str) -> None:
    assert result.returncode == 0, result.stderr
    decision = json.loads(result.stdout)
    assert decision["permissionDecision"] == "deny"
    assert fragment in decision["permissionDecisionReason"], decision


# requirement: copilot-cli / Copilot hook failures have an explicit policy
def test_copilot_pretooluse_denies_when_the_plugin_root_is_missing(tmp_path):
    adapter = _PLUGIN / "hooks" / "copilot-pretooluse.py"
    result = _run_no_root(adapter, _pre_event("Bash", {"command": "echo safe"}, tmp_path), tmp_path)
    _denied(result, "could not run")
    assert "did not provide a plugin root" in result.stderr


def test_copilot_pretooluse_denies_when_the_plugin_root_does_not_match(tmp_path):
    other = tmp_path / "other-plugin"
    other.mkdir()
    adapter = _PLUGIN / "hooks" / "copilot-pretooluse.py"
    result = _run_hook(adapter, _pre_event("Bash", {"command": "echo safe"}, tmp_path), tmp_path, other)
    _denied(result, "could not run")
    assert "does not match" in result.stderr


def test_copilot_pretooluse_denies_the_wrong_event_name(tmp_path):
    adapter = _PLUGIN / "hooks" / "copilot-pretooluse.py"
    event = _pre_event("Bash", {"command": "echo safe"}, tmp_path)
    event["hook_event_name"] = "PostToolUse"
    _denied(_run_hook(adapter, event, tmp_path), "invalid Copilot PreToolUse event")


def test_copilot_pretooluse_denies_an_unsupported_tool_and_bad_arguments(tmp_path):
    adapter = _PLUGIN / "hooks" / "copilot-pretooluse.py"
    _denied(_run_hook(adapter, _pre_event("Read", {"file_path": "x"}, tmp_path), tmp_path),
            "unsupported tool name")
    _denied(_run_hook(adapter, _pre_event("Bash", "not-a-dict", tmp_path), tmp_path),
            "invalid tool arguments")
    _denied(_run_hook(adapter, _pre_event("Edit", {"new_string": "x"}, tmp_path), tmp_path),
            "no file path")
    event = _pre_event("Bash", {"command": "echo safe"}, tmp_path)
    event["cwd"] = ""
    _denied(_run_hook(adapter, event, tmp_path), "no working directory")


def test_copilot_pretooluse_denies_the_dispatcher_wrong_event_output(tmp_path):
    result = _pre_with_fake(tmp_path, _nested(hookEventName="PostToolUse", permissionDecision="allow"))
    _denied(result, "wrong event")


def test_copilot_pretooluse_denies_an_unsupported_decision(tmp_path):
    result = _pre_with_fake(tmp_path, _nested(hookEventName="PreToolUse", permissionDecision="defer"))
    _denied(result, "unsupported decision")


def test_copilot_pretooluse_denies_invalid_warning_context(tmp_path):
    result = _pre_with_fake(tmp_path, _nested(hookEventName="PreToolUse", additionalContext=5))
    _denied(result, "invalid warning context")


def test_copilot_pretooluse_denies_a_non_integer_exit_code(tmp_path):
    result = _pre_with_fake(tmp_path, "def main():\n    return 'ok'\n")
    _denied(result, "could not run")
    assert "non-integer exit code" in result.stderr


def test_copilot_pretooluse_denies_exit_status_two_with_the_stderr_reason(tmp_path):
    body = "import sys\ndef main():\n    print('blocked by test', file=sys.stderr)\n    return 2\n"
    _denied(_pre_with_fake(tmp_path, body), "blocked by test")


def test_copilot_pretooluse_denies_other_nonzero_exit_status(tmp_path):
    _denied(_pre_with_fake(tmp_path, "def main():\n    return 7\n"), "status 7")


def test_copilot_pretooluse_denies_unknown_and_non_object_output(tmp_path):
    _denied(_pre_with_fake(tmp_path, "import json\ndef main():\n    print(json.dumps({'x': 1}))\n    return 0\n"),
            "unknown decision")
    _denied(_pre_with_fake(tmp_path / "b", "def main():\n    print('[1]')\n    return 0\n"), "invalid output")


def test_copilot_pretooluse_denies_an_ask_without_a_reason(tmp_path):
    result = _pre_with_fake(tmp_path, _nested(hookEventName="PreToolUse", permissionDecision="ask"))
    _denied(result, "without a reason")


def test_copilot_pretooluse_turns_a_failure_ask_into_a_deny(tmp_path):
    reason = "an ENFORCING guard could not run on this call"
    result = _pre_with_fake(
        tmp_path, _nested(hookEventName="PreToolUse", permissionDecision="ask", permissionDecisionReason=reason))
    _denied(result, "could not run")


def test_copilot_pretooluse_passes_an_ask_with_context_and_a_dispatcher_deny(tmp_path):
    result = _pre_with_fake(tmp_path, _nested(
        hookEventName="PreToolUse", permissionDecision="ask",
        permissionDecisionReason="force-push needs confirmation", additionalContext="heads up"))
    decision = json.loads(result.stdout)
    assert decision == {
        "permissionDecision": "ask",
        "permissionDecisionReason": "force-push needs confirmation",
        "additionalContext": "heads up",
    }
    result = _pre_with_fake(tmp_path / "d", _nested(
        hookEventName="PreToolUse", permissionDecision="deny", permissionDecisionReason="no"))
    _denied(result, "no")


# The adapter treats a dispatcher `ask` as a failed guard by matching wording.
# These tests drive each dispatcher into each way it reports "a guard did not
# run" and require the adapter's marker list to still recognise the wording.
def _adapter_markers() -> tuple[str, ...]:
    spec = importlib.util.spec_from_file_location(
        "copilot_pretooluse_markers", _PLUGIN / "hooks" / "copilot-pretooluse.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.FAILURE_MARKERS


def _run_dispatcher(root: Path, name: str, payload: dict, cwd: Path) -> dict:
    result = _run_hook(root / "hooks" / name, payload, cwd, root)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)["hookSpecificOutput"]


def test_failure_wording_of_every_dispatcher_matches_the_adapter_markers(tmp_path):
    markers = _adapter_markers()
    bash_event = _pre_event("Bash", {"command": "echo safe"}, tmp_path)
    edit_event = _pre_event("Edit", {"file_path": str(tmp_path / "a.py"), "new_string": "x"}, tmp_path)
    cases = [
        ("dispatch-bash-pretooluse.py", bash_event, "block-cd-in-bash.py"),
        ("dispatch-edit-write-pretooluse.py", edit_event, "block-worktree-path-escape.py"),
    ]
    for index, (dispatcher, event, guard) in enumerate(cases):
        # An enforcing guard that is missing: the escalation inside main().
        root, _ = _copy_adapter_tree(tmp_path / f"guard{index}")
        (root / "hooks" / guard).unlink()
        reason = _run_dispatcher(root, dispatcher, event, tmp_path)["permissionDecisionReason"]
        assert any(m in reason.lower() for m in markers), (dispatcher, reason)
        # The shared library missing: the `_fail_closed` path.
        root, _ = _copy_adapter_tree(tmp_path / f"lib{index}")
        (root / "hooks" / "_dispatch_lib.py").unlink()
        reason = _run_dispatcher(root, dispatcher, event, tmp_path)["permissionDecisionReason"]
        assert any(m in reason.lower() for m in markers), (dispatcher, reason)


def test_the_adapter_denies_each_dispatcher_failure_ask_end_to_end(tmp_path):
    root, adapter = _copy_adapter_tree(tmp_path / "e")
    (root / "hooks" / "_dispatch_lib.py").unlink()
    _denied(_run_hook(adapter, _pre_event("Bash", {"command": "echo safe"}, tmp_path), tmp_path, root),
            "could not run")
    root, adapter = _copy_adapter_tree(tmp_path / "w")
    (root / "hooks" / "block-worktree-path-escape.py").unlink()
    event = _pre_event("Edit", {"file_path": str(tmp_path / "a.py"), "new_string": "x"}, tmp_path)
    _denied(_run_hook(adapter, event, tmp_path, root), "could not run")


# requirement: copilot-cli / Copilot hook failures have an explicit policy
def _post(tmp_path: Path, event: dict | str, root: Path | None = None, adapter: Path | None = None):
    if adapter is None:
        adapter, root = _PLUGIN / "hooks" / "copilot-posttooluse.py", _PLUGIN
    return _run_hook(adapter, event, tmp_path, root)


def _post_tree(tmp_path: Path, warn_body: str | None) -> tuple[Path, Path]:
    root, _ = _copy_adapter_tree(tmp_path)
    warn = root / "hooks" / "warn-wholesale-rewrite.py"
    if warn_body is None:
        warn.unlink()
    else:
        warn.write_text(warn_body, encoding="utf-8")
    return root, root / "hooks" / "copilot-posttooluse.py"


def test_copilot_posttooluse_fails_on_malformed_or_invalid_events(tmp_path):
    result = _post(tmp_path, "{")
    assert result.returncode == 1 and "malformed" in result.stderr
    for bad in (
        _post_event(tmp_path, hook_event_name="PreToolUse"),
        _post_event(tmp_path, tool_name="Edit"),
        _post_event(tmp_path, tool_input="x"),
        _post_event(tmp_path, cwd=""),
    ):
        result = _post(tmp_path, bad)
        assert result.returncode == 1 and "invalid Copilot PostToolUse event" in result.stderr, bad
        assert result.stdout.strip() == ""


def test_copilot_posttooluse_fails_when_the_plugin_root_is_missing_or_wrong(tmp_path):
    adapter = _PLUGIN / "hooks" / "copilot-posttooluse.py"
    result = _run_no_root(adapter, _post_event(tmp_path), tmp_path)
    assert result.returncode == 1 and "did not provide a plugin root" in result.stderr
    other = tmp_path / "other-plugin"
    other.mkdir()
    result = _post(tmp_path, _post_event(tmp_path), other, adapter)
    assert result.returncode == 1 and "does not match" in result.stderr


def test_copilot_posttooluse_fails_when_the_warning_hook_is_missing(tmp_path):
    root, adapter = _post_tree(tmp_path / "t", None)
    result = _post(tmp_path, _post_event(tmp_path), root, adapter)
    assert result.returncode == 1 and "hook is missing" in result.stderr


def test_copilot_posttooluse_fails_when_the_warning_hook_crashes_or_fails(tmp_path):
    root, adapter = _post_tree(tmp_path / "c", "def main():\n    raise RuntimeError('boom')\n")
    result = _post(tmp_path, _post_event(tmp_path), root, adapter)
    assert result.returncode == 1 and "boom" in result.stderr
    root, adapter = _post_tree(tmp_path / "n", "def main():\n    return 3\n")
    result = _post(tmp_path, _post_event(tmp_path), root, adapter)
    assert result.returncode == 1 and "exited with status 3" in result.stderr


def test_copilot_posttooluse_fails_on_malformed_or_invalid_warning_output(tmp_path):
    root, adapter = _post_tree(tmp_path / "m", "def main():\n    print('not json')\n    return 0\n")
    result = _post(tmp_path, _post_event(tmp_path), root, adapter)
    assert result.returncode == 1 and "malformed output" in result.stderr
    root, adapter = _post_tree(
        tmp_path / "i", "import json\ndef main():\n    print(json.dumps({'hookSpecificOutput': {}}))\n    return 0\n")
    result = _post(tmp_path, _post_event(tmp_path), root, adapter)
    assert result.returncode == 1 and "invalid context" in result.stderr


def test_copilot_posttooluse_stays_silent_when_nothing_is_warned(tmp_path):
    root, adapter = _post_tree(tmp_path / "s", "def main():\n    return 0\n")
    result = _post(tmp_path, _post_event(tmp_path), root, adapter)
    assert result.returncode == 0 and result.stdout.strip() == ""


# Launchers: run the exact command strings from hooks.json where the platform
# allows. A missing shell skips; a present shell that cannot launch fails.
def _launcher_commands(key: str) -> list[str]:
    return [hook[key]
            for groups in _config()["hooks"].values()
            for group in groups
            for hook in group["hooks"]]


def _run_launcher(argv: list[str], command: str, event: dict, cwd: Path, root: str | None,
                  extra_env: dict | None = None):
    env = {k: v for k, v in os.environ.items() if k not in _ROOT_VARS}
    env.update({"ALLOW_DESTRUCTIVE_GIT": "", "CLAUDE_PROJECT_DIR": str(cwd)})
    env.update(extra_env or {})
    if root is not None:
        env["COPILOT_PLUGIN_ROOT"] = root
    return subprocess.run(
        [*argv, command], input=json.dumps(event), capture_output=True, text=True,
        encoding="utf-8", errors="replace", cwd=cwd, env=env, timeout=60,
    )


def _shells() -> list[tuple[str, list[str], str]]:
    found = []
    if shutil.which("bash"):
        found.append(("bash", [shutil.which("bash"), "-c"], "bash"))
    ps = shutil.which("pwsh") or shutil.which("powershell")
    if ps:
        found.append(("powershell", [ps, "-NoProfile", "-NonInteractive", "-Command"], "powershell"))
    return found


def test_copilot_launchers_run_the_adapter_and_refuse_without_a_plugin_root(tmp_path):
    shells = _shells()
    if not shells:
        import pytest
        pytest.skip("neither bash nor PowerShell is available")
    pre_bash = _config()["hooks"]["PreToolUse"][0]
    root = str(_PLUGIN.resolve())
    clean = _pre_event("Bash", {"command": "git status --short"}, tmp_path)
    blocked = _pre_event("Bash", {"command": "cd /tmp && pwd"}, tmp_path)
    for name, argv, key in shells:
        command = pre_bash["hooks"][0][key]
        if name == "bash":
            root_arg = Path(root).as_posix()
        else:
            root_arg = root
        ok = _run_launcher(argv, command, clean, tmp_path, root_arg)
        assert ok.returncode == 0, (name, ok.stderr)
        assert ok.stdout.strip() == "", (name, ok.stdout)
        deny = _run_launcher(argv, command, blocked, tmp_path, root_arg)
        assert deny.returncode == 0, (name, deny.stderr)
        assert json.loads(deny.stdout)["permissionDecision"] == "deny", name
        missing = _run_launcher(argv, command, clean, tmp_path, None)
        assert missing.returncode != 0, name
        assert "guard hooks are NOT running" in (missing.stderr + missing.stdout), name


def test_powershell_probe_finds_python_and_honours_the_override(tmp_path):
    ps = shutil.which("pwsh") or shutil.which("powershell")
    if not ps:
        import pytest
        pytest.skip("PowerShell is not available")
    probe = _PLUGIN / "hooks" / "probe-python.ps1"
    script = f". '{probe}'; [Console]::Out.Write(\"$CLA_PYTHON_COMMAND|$($CLA_PYTHON_PREFIX -join ' ')\")"
    env = {k: v for k, v in os.environ.items() if k != "CLA_PYTHON"}
    found = subprocess.run([ps, "-NoProfile", "-NonInteractive", "-Command", script],
                           capture_output=True, text=True, encoding="utf-8", errors="replace",
                           env=env, cwd=tmp_path, timeout=60)
    assert found.returncode == 0, found.stderr
    command = found.stdout.split("|")[0]
    assert command, found.stderr
    env["CLA_PYTHON"] = "cla-no-such-python"
    missing = subprocess.run([ps, "-NoProfile", "-NonInteractive", "-Command", script],
                             capture_output=True, text=True, encoding="utf-8", errors="replace",
                           env=env, cwd=tmp_path, timeout=60)
    assert missing.stdout.split("|")[0] == ""
    assert "CLA_PYTHON=cla-no-such-python is not a working Python" in missing.stderr


# requirement: copilot-cli / Copilot hook failures have an explicit policy
def test_bash_launcher_refuses_loudly_when_cla_python_is_unusable(tmp_path):
    """Missing interpreter, bash probe: an unusable CLA_PYTHON must stop the
    launcher non-zero with a message, not fall through to another interpreter
    (which would run the guards) and not allow the call silently."""
    bash = shutil.which("bash")
    if not bash:
        import pytest
        pytest.skip("bash is not available")
    command = _config()["hooks"]["PreToolUse"][0]["hooks"][0]["bash"]
    clean = _pre_event("Bash", {"command": "git status --short"}, tmp_path)
    root = Path(_PLUGIN.resolve()).as_posix()
    result = _run_launcher(
        [bash, "-c"], command, clean, tmp_path, root,
        extra_env={"CLA_PYTHON": "cla-no-such-python", "CLA_PROBE_NO_CACHE": "1"})
    assert result.returncode != 0, result.stdout
    assert "CLA_PYTHON=cla-no-such-python is not a working Python" in result.stderr
    assert "guard hooks are NOT running" in result.stderr
    assert result.stdout.strip() == ""


# ---------------------------------------------------------------------------
# Every Bash and Edit/Write guard, through the Copilot adapter: one call it must
# leave alone and one it must stop or flag. Everything is built under tmp_path.
# ---------------------------------------------------------------------------

_ADAPTER = _PLUGIN / "hooks" / "copilot-pretooluse.py"


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def _make_repo(path: Path) -> Path:
    path.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(path)], check=True)
    _git(path, "config", "user.email", "test@example.com")
    _git(path, "config", "user.name", "Test")
    (path / "README.md").write_text("hello\n", encoding="utf-8")
    _git(path, "add", "README.md")
    _git(path, "-c", "commit.gpgsign=false", "commit", "-qm", "baseline")
    return path


def _bash(tmp_path: Path, command: str, cwd: Path | None = None, extra_env: dict | None = None):
    cwd = cwd or tmp_path
    return _run_hook(_ADAPTER, _pre_event("Bash", {"command": command}, cwd), cwd,
                     extra_env=extra_env)


def _silent(result) -> None:
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "", result.stdout


def _warned(result, fragment: str) -> None:
    assert result.returncode == 0, result.stderr
    decision = json.loads(result.stdout)
    assert "permissionDecision" not in decision, decision
    assert fragment in decision["additionalContext"], decision


# requirement: copilot-cli / Copilot CLI enforces session guards
def test_copilot_pretooluse_blocks_a_recursive_delete_of_a_symlink(tmp_path):
    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "link"
    try:
        os.symlink(real, link, target_is_directory=True)
    except (OSError, NotImplementedError):
        # Windows without symlink rights: an NTFS junction is the same hazard.
        made = os.name == "nt" and subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(link), str(real)],
            capture_output=True).returncode == 0
        if not made:
            import pytest
            pytest.skip("cannot create a symlink or junction on this machine")
    _denied(_bash(tmp_path, f"rm -rf {link.as_posix()}/"), "block-unsafe-recursive-delete.py")


def test_copilot_pretooluse_allows_a_recursive_delete_of_a_real_directory(tmp_path):
    real = tmp_path / "real"
    real.mkdir()
    _silent(_bash(tmp_path, f"rm -rf {real.as_posix()}"))


_FAKE_GH = '''\
import shutil, subprocess
_real_run, _real_which = subprocess.run, shutil.which
def _which(name, *a, **k):
    return "gh" if name == "gh" else _real_which(name, *a, **k)
def _run(args, *a, **k):
    if isinstance(args, list) and args and args[0] == "gh":
        if args[1:3] == ["pr", "view"]:
            out = "feature/base\\n"
        else:
            out = '[{"number": 9, "title": "child"}]'
        return subprocess.CompletedProcess(args, 0, out, "")
    return _real_run(args, *a, **k)
shutil.which, subprocess.run = _which, _run
'''


def test_copilot_pretooluse_warns_when_a_merge_would_orphan_a_stacked_pr(tmp_path):
    shim = tmp_path / "shim"
    shim.mkdir()
    (shim / "sitecustomize.py").write_text(_FAKE_GH, encoding="utf-8")
    # A PR merge always draws the destructive-git confirmation; ALLOW_PR_MERGE
    # lets the advisory warning be seen on its own.
    env = {"PYTHONPATH": str(shim), "ALLOW_PR_MERGE": "1"}
    result = _bash(tmp_path, "gh pr merge 7 --delete-branch", extra_env=env)
    _warned(result, "warn-stacked-pr-merge")
    assert "#9" in json.loads(result.stdout)["additionalContext"]


def test_copilot_pretooluse_stays_quiet_when_the_branch_is_kept(tmp_path):
    shim = tmp_path / "shim"
    shim.mkdir()
    (shim / "sitecustomize.py").write_text(_FAKE_GH, encoding="utf-8")
    # Same fake gh with a child PR present; only the missing --delete-branch differs.
    result = _bash(tmp_path, "gh pr merge 7 --merge",
                   extra_env={"PYTHONPATH": str(shim), "ALLOW_PR_MERGE": "1"})
    assert result.returncode == 0, result.stderr
    # The only output is the merge-confirmation-disabled note from another guard.
    assert "warn-stacked-pr-merge" not in result.stdout, result.stdout
    # The adapter exits 0 even when it denies, so rule a decision out explicitly.
    assert "permissionDecision" not in json.loads(result.stdout), result.stdout


def test_copilot_pretooluse_warns_about_a_stray_scratch_file_before_git_add(tmp_path):
    repo = _make_repo(tmp_path / "repo")
    (repo / "AppData_dump.txt").write_text("junk\n", encoding="utf-8")
    _warned(_bash(tmp_path, "git add .", cwd=repo), "AppData_dump.txt")


def test_copilot_pretooluse_allows_git_add_without_a_stray_file(tmp_path):
    repo = _make_repo(tmp_path / "repo")
    (repo / "notes.md").write_text("real work\n", encoding="utf-8")
    _silent(_bash(tmp_path, "git add .", cwd=repo))


def test_copilot_pretooluse_warns_when_a_heredoc_would_eat_an_escape(tmp_path):
    command = "python3 - <<'PY'\ns = \"anchor\\nnext\"\nprint(s)\nPY"
    _warned(_bash(tmp_path, command), "warn-heredoc-escape-mangling")


def test_copilot_pretooluse_allows_a_heredoc_without_escapes(tmp_path):
    _silent(_bash(tmp_path, "python3 - <<'PY'\ns = \"anchor next\"\nprint(s)\nPY"))


def _linked_worktree(tmp_path: Path) -> tuple[Path, Path]:
    primary = _make_repo(tmp_path / "primary")
    linked = tmp_path / "linked"
    _git(primary, "worktree", "add", "-q", str(linked), "-b", "side")
    return primary, linked


def _edit(cwd: Path, target: Path, extra_env: dict | None = None):
    return _run_hook(
        _ADAPTER,
        _pre_event("Edit", {"file_path": str(target), "new_string": "x = 1\n"}, cwd),
        cwd, extra_env=extra_env)


def test_copilot_pretooluse_denies_an_edit_that_escapes_the_linked_worktree(tmp_path):
    primary, linked = _linked_worktree(tmp_path)
    _denied(_edit(linked, primary / "README.md"), "block-worktree-path-escape.py")


def test_copilot_pretooluse_allows_an_edit_inside_the_linked_worktree(tmp_path):
    _, linked = _linked_worktree(tmp_path)
    _silent(_edit(linked, linked / "README.md"))


def test_copilot_pretooluse_allows_a_clean_edit_with_no_dates(tmp_path):
    result = _run_hook(
        _ADAPTER,
        _pre_event("Edit", {"file_path": str(tmp_path / "source.py"),
                            "new_string": "# fixed the parser\n"}, tmp_path),
        tmp_path)
    _silent(result)
