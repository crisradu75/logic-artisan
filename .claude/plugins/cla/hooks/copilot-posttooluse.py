#!/usr/bin/env python3
"""Translate Copilot PostToolUse events for CLA's wholesale-rewrite warning."""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
import sys
from pathlib import Path


def main() -> int:
    try:
        event = json.load(sys.stdin)
    except (json.JSONDecodeError, UnicodeDecodeError):
        print("cla: malformed Copilot PostToolUse input", file=sys.stderr)
        return 1
    if (
        not isinstance(event, dict)
        or event.get("hook_event_name") != "PostToolUse"
        or event.get("tool_name") != "Write"
        or not isinstance(event.get("tool_input"), dict)
        or not isinstance(event.get("cwd"), str)
        or not event["cwd"]
    ):
        print("cla: invalid Copilot PostToolUse event", file=sys.stderr)
        return 1

    root_value = next(
        (
            os.environ[name]
            for name in ("COPILOT_PLUGIN_ROOT", "PLUGIN_ROOT", "CLAUDE_PLUGIN_ROOT")
            if os.environ.get(name)
        ),
        None,
    )
    if not root_value:
        print("cla: Copilot did not provide a plugin root", file=sys.stderr)
        return 1
    root = Path(root_value).resolve()
    if root != Path(__file__).resolve().parents[1]:
        print("cla: Copilot plugin root does not match the loaded CLA plugin", file=sys.stderr)
        return 1

    warning_path = root / "hooks" / "warn-wholesale-rewrite.py"
    if not warning_path.is_file():
        print("cla: wholesale-rewrite warning hook is missing", file=sys.stderr)
        return 1
    spec = importlib.util.spec_from_file_location("_cla_copilot_rewrite_warning", warning_path)
    if spec is None or spec.loader is None:
        print("cla: cannot load wholesale-rewrite warning hook", file=sys.stderr)
        return 1
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
        stdout = io.StringIO()
        previous_stdin = sys.stdin
        previous_cwd = os.getcwd()
        try:
            sys.stdin = io.StringIO(json.dumps(event))
            os.chdir(event["cwd"])
            previous = os.environ.get("CLAUDE_PROJECT_DIR")
            os.environ["CLAUDE_PROJECT_DIR"] = event["cwd"]
            try:
                with contextlib.redirect_stdout(stdout):
                    code = module.main()
            finally:
                if previous is None:
                    os.environ.pop("CLAUDE_PROJECT_DIR", None)
                else:
                    os.environ["CLAUDE_PROJECT_DIR"] = previous
        finally:
            sys.stdin = previous_stdin
            os.chdir(previous_cwd)
    except Exception as exc:
        print(f"cla: wholesale-rewrite warning failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    if code != 0:
        print(f"cla: wholesale-rewrite warning exited with status {code}", file=sys.stderr)
        return 1

    output = stdout.getvalue().strip()
    if output:
        try:
            result = json.loads(output)
        except json.JSONDecodeError:
            print("cla: wholesale-rewrite warning returned malformed output", file=sys.stderr)
            return 1
        nested = result.get("hookSpecificOutput") if isinstance(result, dict) else None
        context = nested.get("additionalContext") if isinstance(nested, dict) else None
        if not isinstance(context, str):
            print("cla: wholesale-rewrite warning returned invalid context", file=sys.stderr)
            return 1
        print(json.dumps({"additionalContext": context}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
