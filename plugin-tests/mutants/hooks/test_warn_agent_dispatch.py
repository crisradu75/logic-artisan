"""Mutant batch for `tests/hooks/test_warn_agent_dispatch.py`.

Run: python3 plugin-tests/mutate.py plugin-tests/mutants/hooks/test_warn_agent_dispatch.py

Scope: every line of `hooks/warn-agent-dispatch.py` that decides whether a warning fires, plus
its `hooks.json` wiring (the matcher and the script name). One mutant per decision, each anchor
occurring once in its file. The size tests run real multi-megabyte prompts, so a mutant that
made a pattern quadratic would show as a slow kill; none here does. Each mutant was checked by
hand in a scratch copy with bytecode writing off, not with mutate.py: every one fails a test.

Paths resolve from this file's own location, never an absolute developer path.
"""

from pathlib import Path

DEV = Path(__file__).resolve().parents[2]  # <repo>/plugin-tests
PLUGIN = DEV.parent / ".claude" / "plugins" / "cla"
HOOK = PLUGIN / "hooks" / "warn-agent-dispatch.py"
WIRING = PLUGIN / "hooks" / "hooks.json"
TARGETS = [DEV / "tests" / "hooks" / "test_warn_agent_dispatch.py"]

# The two Agent groups in hooks.json differ only in the script name, so the matcher's anchor runs
# from the matcher down to that name. Read from the file rather than copied, so it cannot drift.
_COMMAND_LINE = next(
    line for line in WIRING.read_text(encoding="utf-8").splitlines() if "/hooks/warn-agent-dispatch.py" in line
)
_MATCHER = '"matcher": "Agent",\n        "hooks": [\n          {\n            "type": "command",\n' + _COMMAND_LINE

MUTANTS = [
    (
        'the diff header is matched only at the very start of the prompt',
        HOOK,
        'r"^[ \\t]*diff --git \\S", re.MULTILINE)',
        'r"^[ \\t]*diff --git \\S")',
        TARGETS,
    ),
    (
        'the diff header is matched anywhere in a line, so prose naming it warns',
        HOOK,
        'r"^[ \\t]*diff --git \\S"',
        'r"diff --git \\S"',
        TARGETS,
    ),
    (
        'an indented pasted diff is missed',
        HOOK,
        'r"^[ \\t]*diff --git \\S"',
        'r"^diff --git \\S"',
        TARGETS,
    ),
    (
        'a bare `diff --git` with no path after it counts as a diff',
        HOOK,
        'r"^[ \\t]*diff --git \\S"',
        'r"^[ \\t]*diff --git"',
        TARGETS,
    ),
    (
        'any `(none recorded)` warns, not only the protected-areas slot',
        HOOK,
        'r"protected areas? \\(\\s*`?\\(none recorded\\)`?\\s*\\)"',
        'r"\\(none recorded\\)"',
        TARGETS,
    ),
    (
        'the slot need not close after the placeholder',
        HOOK,
        'r"protected areas? \\(\\s*`?\\(none recorded\\)`?\\s*\\)"',
        'r"protected areas? \\(\\s*`?\\(none recorded\\)"',
        TARGETS,
    ),
    (
        'a backticked placeholder is missed',
        HOOK,
        'r"protected areas? \\(\\s*`?\\(none recorded\\)`?\\s*\\)"',
        'r"protected areas? \\(\\s*\\(none recorded\\)\\s*\\)"',
        TARGETS,
    ),
    (
        'the plural `protected areas` is missed',
        HOOK,
        'r"protected areas? \\(',
        'r"protected area \\(',
        TARGETS,
    ),
    (
        "a blank inside the slot's parentheses is missed",
        HOOK,
        'r"protected areas? \\(\\s*`?',
        'r"protected areas? \\(`?',
        TARGETS,
    ),
    (
        'a null model counts as named',
        HOOK,
        '    if model is None:\n        return True',
        '    if model is None:\n        return False',
        TARGETS,
    ),
    (
        'a blank model counts as named',
        HOOK,
        'return isinstance(model, str) and not model.strip()',
        'return False',
        TARGETS,
    ),
    (
        'a model of spaces counts as named',
        HOOK,
        'return isinstance(model, str) and not model.strip()',
        'return isinstance(model, str) and not model',
        TARGETS,
    ),
    (
        'a non-string model is read as a string',
        HOOK,
        'return isinstance(model, str) and not model.strip()',
        'return not model.strip()',
        TARGETS,
    ),
    (
        'the model warning fires when a model is named',
        HOOK,
        'if _missing_model(tool_input):',
        'if not _missing_model(tool_input):',
        TARGETS,
    ),
    (
        'a non-string prompt is searched',
        HOOK,
        'if isinstance(prompt, str):',
        'if prompt:',
        TARGETS,
    ),
    (
        'the diff header must be on the first line',
        HOOK,
        'if _DIFF_HEADER.search(prompt):',
        'if _DIFF_HEADER.match(prompt):',
        TARGETS,
    ),
    (
        'the slot must open the prompt',
        HOOK,
        'if _NONE_RECORDED_SLOT.search(prompt):',
        'if _NONE_RECORDED_SLOT.match(prompt):',
        TARGETS,
    ),
    (
        'a call to another tool is checked',
        HOOK,
        'if not isinstance(payload, dict) or payload.get("tool_name") != "Agent":',
        'if not isinstance(payload, dict):',
        TARGETS,
    ),
    (
        'a tool_input that is not an object is read',
        HOOK,
        '    if not isinstance(tool_input, dict):\n        return 0\n',
        '',
        TARGETS,
    ),
    (
        'undecodable stdin crashes the hook',
        HOOK,
        'except (json.JSONDecodeError, UnicodeDecodeError, ValueError):',
        'except json.JSONDecodeError:',
        TARGETS,
    ),
    (
        'output is printed when there is nothing to warn about',
        HOOK,
        '    if found:\n        print(',
        '    if True:\n        print(',
        TARGETS,
    ),
    (
        'the warning names the wrong event',
        HOOK,
        '"hookEventName": "PreToolUse",',
        '"hookEventName": "PostToolUse",',
        TARGETS,
    ),
    (
        'only the first warning is delivered',
        HOOK,
        '"additionalContext": "\\n\\n".join(found),',
        '"additionalContext": found[0],',
        TARGETS,
    ),
    (
        "the warning is wired on another tool's matcher",
        WIRING,
        _MATCHER,
        _MATCHER.replace('"matcher": "Agent"', '"matcher": "Task"', 1),
        TARGETS + [DEV / "tests" / "hooks" / "test_hooks_wiring.py"],
    ),
    (
        "the wiring names a script that does not exist",
        WIRING,
        '/hooks/warn-agent-dispatch.py\\"',
        '/hooks/warn-agent-dispatch-gone.py\\"',
        TARGETS + [DEV / "tests" / "hooks" / "test_hooks_wiring.py"],
    ),
]
