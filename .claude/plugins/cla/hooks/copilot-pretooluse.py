#!/usr/bin/env python3
"""Translate Copilot PreToolUse events and CLA dispatcher results."""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
import sys
from pathlib import Path
from types import ModuleType


_DISPATCHERS = {
    "Bash": "dispatch-bash-pretooluse.py",
    "PowerShell": "dispatch-bash-pretooluse.py",
    "Edit": "dispatch-edit-write-pretooluse.py",
    "Write": "dispatch-edit-write-pretooluse.py",
}
# The key that carries the new text of each Edit/Write tool the adapter accepts.
_TEXT_KEYS = {"Edit": "new_string", "Write": "content"}
# The dispatchers report "a guard did not run" as an `ask`, and set their module
# flag `GUARD_NOT_RUN` when they do (`dispatch-*-pretooluse.py`: the
# enforcing-guard escalation in main() and `_fail_closed`). Copilot cannot resolve
# that ask as a confirmation of a real action, and an unchecked call must never
# become an approval, so the adapter turns it into a deny. It reads the flag, not
# the reason's wording: a reworded message cannot turn a deny back into an ask. A
# dispatcher without the flag is an unknown contract and is denied as well. The
# one deliberate exception is the Bash dispatcher's oversize-command ask: that
# call is unchecked too, sets no flag, and stays an ask.
_FLAG = "GUARD_NOT_RUN"


def _plugin_root() -> Path:
    value = next(
        (
            os.environ[name]
            for name in ("COPILOT_PLUGIN_ROOT", "PLUGIN_ROOT", "CLAUDE_PLUGIN_ROOT")
            if os.environ.get(name)
        ),
        None,
    )
    if not value:
        raise RuntimeError("Copilot did not provide a plugin root")
    root = Path(value).resolve()
    if root != Path(__file__).resolve().parents[1]:
        raise RuntimeError("Copilot plugin root does not match the loaded CLA plugin")
    return root


def _deny(reason: str) -> int:
    reason = reason.strip() or "A CLA guard denied this tool call."
    print(json.dumps({
        "permissionDecision": "deny",
        "permissionDecisionReason": reason[:4000],
    }))
    return 0


def _load_dispatcher(path: Path) -> ModuleType:
    if not path.is_file():
        raise FileNotFoundError(f"CLA guard dispatcher is missing: {path.name}")
    hooks_dir = str(path.parent)
    if hooks_dir not in sys.path:
        sys.path.insert(0, hooks_dir)
    spec = importlib.util.spec_from_file_location("_cla_copilot_dispatcher", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load CLA guard dispatcher: {path.name}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _dispatch(path: Path, payload: dict) -> tuple[int, str, str, object]:
    module = _load_dispatcher(path)
    stdout = io.StringIO()
    stderr = io.StringIO()
    previous_stdin = sys.stdin
    try:
        sys.stdin = io.StringIO(json.dumps(payload))
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = module.main()
    finally:
        sys.stdin = previous_stdin
    if not isinstance(code, int):
        raise TypeError("CLA guard dispatcher returned a non-integer exit code")
    return code, stdout.getvalue(), stderr.getvalue(), getattr(module, _FLAG, None)


def _normalize(stdout_text: str, stderr_text: str, code: int, not_run: object) -> int:
    if code == 2:
        return _deny(stderr_text)
    if code != 0:
        return _deny(f"CLA guard dispatcher exited with status {code}; refusing an unchecked call.")
    if not isinstance(not_run, bool):
        return _deny(f"CLA guard dispatcher reports no `{_FLAG}` flag; refusing an unchecked call.")
    if not stdout_text.strip():
        return 0

    try:
        payload = json.loads(stdout_text)
    except json.JSONDecodeError:
        return _deny("CLA guard dispatcher returned malformed output; refusing an unchecked call.")
    if not isinstance(payload, dict):
        return _deny("CLA guard dispatcher returned invalid output; refusing an unchecked call.")

    nested = payload.get("hookSpecificOutput")
    if not isinstance(nested, dict):
        return _deny("CLA guard dispatcher returned an unknown decision; refusing an unchecked call.")
    if nested.get("hookEventName") not in (None, "PreToolUse"):
        return _deny("CLA guard dispatcher returned output for the wrong event; refusing the call.")

    decision = nested.get("permissionDecision")
    reason = nested.get("permissionDecisionReason")
    if not_run:
        return _deny(reason if isinstance(reason, str) else "A CLA guard could not run; refusing the call.")
    if decision == "ask":
        if not isinstance(reason, str) or not reason.strip():
            return _deny("CLA guard dispatcher requested confirmation without a reason; refusing the call.")
        print(json.dumps({
            "permissionDecision": "ask",
            "permissionDecisionReason": reason,
            **(
                {"additionalContext": nested["additionalContext"]}
                if isinstance(nested.get("additionalContext"), str)
                and nested["additionalContext"].strip()
                else {}
            ),
        }))
        return 0
    if decision == "deny":
        return _deny(reason if isinstance(reason, str) else "")
    if decision not in (None, "allow"):
        return _deny("CLA guard dispatcher returned an unsupported decision; refusing the call.")

    context = nested.get("additionalContext")
    if context is not None:
        if not isinstance(context, str):
            return _deny("CLA guard dispatcher returned invalid warning context; refusing the call.")
        if context.strip():
            print(json.dumps({"additionalContext": context}))
    return 0


def main() -> int:
    try:
        event = json.load(sys.stdin)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return _deny("CLA guard received malformed Copilot hook input; refusing the call.")
    if not isinstance(event, dict) or event.get("hook_event_name") != "PreToolUse":
        return _deny("CLA guard received an invalid Copilot PreToolUse event; refusing the call.")

    tool_name = event.get("tool_name")
    dispatcher_name = _DISPATCHERS.get(tool_name)
    if dispatcher_name is None:
        return _deny(f"CLA guard received an unsupported tool name: {tool_name!r}.")
    tool_input = event.get("tool_input")
    if not isinstance(tool_input, dict):
        return _deny("CLA guard received invalid tool arguments; refusing the call.")
    if tool_name in ("Bash", "PowerShell"):
        if not isinstance(tool_input.get("command"), str):
            return _deny("CLA guard received no shell command to check; refusing the call.")
    # UNVERIFIED ASSUMPTION: GitHub's hooks-configuration reference types
    # `tool_input` as `unknown` and names no per-tool argument keys, so
    # `file_path` (the Claude key the dispatchers read) is assumed. If Copilot
    # names it differently, every Edit/Write is denied (fail closed) rather than
    # passed unchecked; confirm against a live payload before relying on it.
    elif not isinstance(tool_input.get("file_path"), str) or not tool_input["file_path"]:
        return _deny("CLA guard received no file path to check; refusing the call.")
    # The same assumption for the new text: `content` on a Write, `new_string` on
    # an Edit, the keys the Edit/Write guards read (the secret scan among them).
    # The adapter passes `tool_input` through unchanged and maps no key, so a
    # Copilot payload that names the text differently is denied here rather than
    # scanned as empty and passed. An empty string is text, and is allowed.
    elif not isinstance(tool_input.get(_TEXT_KEYS[tool_name]), str):
        return _deny(
            f"CLA guard received no `{_TEXT_KEYS[tool_name]}` to check; refusing the call."
        )
    if not isinstance(event.get("cwd"), str) or not event["cwd"]:
        return _deny("CLA guard received no working directory; refusing the call.")

    try:
        root = _plugin_root()
        code, stdout_text, stderr_text, not_run = _dispatch(
            root / "hooks" / dispatcher_name,
            event,
        )
    except Exception as exc:
        print(f"cla: Copilot pre-tool guard failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return _deny("CLA guard could not run; refusing this tool call.")
    return _normalize(stdout_text, stderr_text, code, not_run)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"cla: Copilot pre-tool adapter failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        sys.exit(_deny("CLA guard adapter failed; refusing this tool call."))
