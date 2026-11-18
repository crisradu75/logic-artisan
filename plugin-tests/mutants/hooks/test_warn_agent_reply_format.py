"""Mutant batch for `tests/hooks/test_warn_agent_reply_format.py`.

Run: python3 plugin-tests/mutate.py plugin-tests/mutants/hooks/test_warn_agent_reply_format.py

Scope: every line of `hooks/warn-agent-reply-format.py` that decides whether a warning fires,
plus its `hooks.json` wiring (the matcher and the script name). One mutant per decision, each
anchor occurring once in its file. The check on a block's `type` is killed only by a non-text
block carrying text, which the tests build deliberately. Each mutant was checked by hand in a
scratch copy with bytecode writing off, not with mutate.py: every one fails a test.

Paths resolve from this file's own location, never an absolute developer path.
"""

from pathlib import Path

DEV = Path(__file__).resolve().parents[2]  # <repo>/plugin-tests
PLUGIN = DEV.parent / ".claude" / "plugins" / "cla"
HOOK = PLUGIN / "hooks" / "warn-agent-reply-format.py"
WIRING = PLUGIN / "hooks" / "hooks.json"
TARGETS = [DEV / "tests" / "hooks" / "test_warn_agent_reply_format.py"]

# The two Agent groups in hooks.json differ only in the script name, so the matcher's anchor runs
# from the matcher down to that name. Read from the file rather than copied, so it cannot drift.
_COMMAND_LINE = next(
    line for line in WIRING.read_text(encoding="utf-8").splitlines() if "/hooks/warn-agent-reply-format.py" in line
)
_MATCHER = '"matcher": "Agent",\n        "hooks": [\n          {\n            "type": "command",\n' + _COMMAND_LINE

MUTANTS = [
    (
        "the footer is matched only on the reply's first line",
        HOOK,
        '[*_`]*Scanned[*_`]*:",\n    re.MULTILINE | re.IGNORECASE,',
        '[*_`]*Scanned[*_`]*:",\n    re.IGNORECASE,',
        TARGETS,
    ),
    (
        'a footer in another case is missed',
        HOOK,
        '[*_`]*Scanned[*_`]*:",\n    re.MULTILINE | re.IGNORECASE,',
        '[*_`]*Scanned[*_`]*:",\n    re.MULTILINE,',
        TARGETS,
    ),
    (
        '`Scanned:` anywhere in a line counts as the footer',
        HOOK,
        'r"^[ \\t>]*(?:[-*+]',
        'r"(?:[-*+]',
        TARGETS,
    ),
    (
        'a footer behind a quote marker is missed',
        HOOK,
        'r"^[ \\t>]*(?:[-*+]',
        'r"^[ \\t]*(?:[-*+]',
        TARGETS,
    ),
    (
        'an indented footer is missed',
        HOOK,
        'r"^[ \\t>]*(?:[-*+]',
        'r"^[>]*(?:[-*+]',
        TARGETS,
    ),
    (
        'a footer in a list item is missed',
        HOOK,
        '(?:[-*+][ \\t]+|\\d+[.)][ \\t]+)?[*_`]*Scanned',
        '[*_`]*Scanned',
        TARGETS,
    ),
    (
        'a list marker becomes required',
        HOOK,
        '(?:[-*+][ \\t]+|\\d+[.)][ \\t]+)?[*_`]*Scanned',
        '(?:[-*+][ \\t]+|\\d+[.)][ \\t]+)[*_`]*Scanned',
        TARGETS,
    ),
    (
        'a `+` list item is missed',
        HOOK,
        '(?:[-*+][ \\t]+|',
        '(?:[-*][ \\t]+|',
        TARGETS,
    ),
    (
        'a `-` list item is missed',
        HOOK,
        '(?:[-*+][ \\t]+|',
        '(?:[*+][ \\t]+|',
        TARGETS,
    ),
    (
        'a bullet with no blank after it counts as a list item',
        HOOK,
        '(?:[-*+][ \\t]+|',
        '(?:[-*+][ \\t]*|',
        TARGETS,
    ),
    (
        'a multi-digit list number is missed',
        HOOK,
        '|\\d+[.)][ \\t]+)?',
        '|\\d[.)][ \\t]+)?',
        TARGETS,
    ),
    (
        'a `1)` list number is missed',
        HOOK,
        '|\\d+[.)][ \\t]+)?',
        '|\\d+[.][ \\t]+)?',
        TARGETS,
    ),
    (
        'a number with no blank after it counts as a list item',
        HOOK,
        '|\\d+[.)][ \\t]+)?',
        '|\\d+[.)][ \\t]*)?',
        TARGETS,
    ),
    (
        'a letter counts as a list number',
        HOOK,
        '|\\d+[.)][ \\t]+)?',
        '|\\w+[.)][ \\t]+)?',
        TARGETS,
    ),
    (
        "emphasis before the footer's name is missed",
        HOOK,
        ')?[*_`]*Scanned[*_`]*:"',
        ')?Scanned[*_`]*:"',
        TARGETS,
    ),
    (
        "emphasis before the footer's colon is missed",
        HOOK,
        ')?[*_`]*Scanned[*_`]*:"',
        ')?[*_`]*Scanned:"',
        TARGETS,
    ),
    (
        "the footer's colon is not required",
        HOOK,
        ')?[*_`]*Scanned[*_`]*:"',
        ')?[*_`]*Scanned[*_`]*"',
        TARGETS,
    ),
    (
        "the field's colon is not required",
        HOOK,
        'r"Fact corrections[*_`]*:|',
        'r"Fact corrections[*_`]*|',
        TARGETS,
    ),
    (
        'emphasis between the field name and its colon is missed',
        HOOK,
        'r"Fact corrections[*_`]*:|',
        'r"Fact corrections:|',
        TARGETS,
    ),
    (
        'a heading field is missed',
        HOOK,
        '|^[ \\t>]*#{1,6}[ \\t]+[*_`]*Fact corrections"',
        '"',
        TARGETS,
    ),
    (
        'a heading mid-line counts',
        HOOK,
        '|^[ \\t>]*#{1,6}[ \\t]+[*_`]*Fact corrections"',
        '|[ \\t>]*#{1,6}[ \\t]+[*_`]*Fact corrections"',
        TARGETS,
    ),
    (
        'a heading inside a quote is missed',
        HOOK,
        '|^[ \\t>]*#{1,6}[ \\t]+[*_`]*Fact corrections"',
        '|^[ \\t]*#{1,6}[ \\t]+[*_`]*Fact corrections"',
        TARGETS,
    ),
    (
        'seven hashes count as a heading',
        HOOK,
        '|^[ \\t>]*#{1,6}[ \\t]+[*_`]*Fact corrections"',
        '|^[ \\t>]*#+[ \\t]+[*_`]*Fact corrections"',
        TARGETS,
    ),
    (
        'a first-level heading is missed',
        HOOK,
        '|^[ \\t>]*#{1,6}[ \\t]+[*_`]*Fact corrections"',
        '|^[ \\t>]*#{2,6}[ \\t]+[*_`]*Fact corrections"',
        TARGETS,
    ),
    (
        'hashes with no blank after them count as a heading',
        HOOK,
        '|^[ \\t>]*#{1,6}[ \\t]+[*_`]*Fact corrections"',
        '|^[ \\t>]*#{1,6}[ \\t]*[*_`]*Fact corrections"',
        TARGETS,
    ),
    (
        'an emphasised heading is missed',
        HOOK,
        '|^[ \\t>]*#{1,6}[ \\t]+[*_`]*Fact corrections"',
        '|^[ \\t>]*#{1,6}[ \\t]+Fact corrections"',
        TARGETS,
    ),
    (
        "a heading below the reply's first line is missed",
        HOOK,
        'Fact corrections",\n    re.MULTILINE | re.IGNORECASE,',
        'Fact corrections",\n    re.IGNORECASE,',
        TARGETS,
    ),
    (
        'a field in another case is missed',
        HOOK,
        'Fact corrections",\n    re.MULTILINE | re.IGNORECASE,',
        'Fact corrections",\n    re.MULTILINE,',
        TARGETS,
    ),
    (
        'a brief naming the field without its colon arms the check',
        HOOK,
        '_FACT_FIELD_IN_PROMPT = "Fact corrections:"',
        '_FACT_FIELD_IN_PROMPT = "Fact corrections"',
        TARGETS,
    ),
    (
        'the hand-back caveat is dropped from every warning',
        HOOK,
        '_HANDBACK_NOTE = (\n    " If this agent',
        '_HANDBACK_NOTE = "" and (\n    " If this agent',
        TARGETS,
    ),
    (
        'the fact warning drops the hand-back caveat',
        HOOK,
        '"re-dispatch." + _HANDBACK_NOTE',
        '"re-dispatch."',
        TARGETS,
    ),
    (
        'a plugin-scoped sweeper name is missed',
        HOOK,
        'subagent_type.rsplit(":", 1)[-1] == "doc-sweeper"',
        'subagent_type == "doc-sweeper"',
        TARGETS,
    ),
    (
        'any name ending in doc-sweeper is a sweeper',
        HOOK,
        'subagent_type.rsplit(":", 1)[-1] == "doc-sweeper"',
        'subagent_type.endswith("doc-sweeper")',
        TARGETS,
    ),
    (
        'only the first scope is stripped from a sweeper name',
        HOOK,
        'subagent_type.rsplit(":", 1)[-1] == "doc-sweeper"',
        'subagent_type.split(":", 1)[-1] == "doc-sweeper"',
        TARGETS,
    ),
    (
        'a non-string agent type is read as a string',
        HOOK,
        'return isinstance(subagent_type, str) and subagent_type.rsplit',
        'return subagent_type.rsplit',
        TARGETS,
    ),
    (
        'a reply that is not completed is checked',
        HOOK,
        '    if tool_response.get("status") != "completed":\n        return None\n',
        '',
        TARGETS,
    ),
    (
        'a delivered hand-back report is ignored',
        HOOK,
        '    if isinstance(report, dict) and isinstance(report.get("text"), str):\n        return report["text"]\n',
        '',
        TARGETS,
    ),
    (
        'a hand-back report with no text is read',
        HOOK,
        'if isinstance(report, dict) and isinstance(report.get("text"), str):',
        'if isinstance(report, dict) and "text" in report:',
        TARGETS,
    ),
    (
        'a hand-back with no report in view is checked against the note',
        HOOK,
        '    if "handback" in tool_response:\n        return None\n',
        '',
        TARGETS,
    ),
    (
        'a string content is not read',
        HOOK,
        '    if isinstance(content, str):\n        return content\n',
        '',
        TARGETS,
    ),
    (
        'text blocks are joined with no line break',
        HOOK,
        '    return "\\n".join(',
        '    return "".join(',
        TARGETS,
    ),
    (
        'a non-text block is read',
        HOOK,
        'if isinstance(block, dict) and block.get("type") == "text" and isinstance',
        'if isinstance(block, dict) and isinstance',
        TARGETS,
    ),
    (
        'a block whose text is not a string is read',
        HOOK,
        'block.get("type") == "text" and isinstance(block.get("text"), str)',
        'block.get("type") == "text"',
        TARGETS,
    ),
    (
        'a non-dict block is read',
        HOOK,
        'if isinstance(block, dict) and block.get("type")',
        'if block.get("type")',
        TARGETS,
    ),
    (
        'the footer check fires when the footer is there',
        HOOK,
        'and not _SCANNED_LINE.search(reply):',
        'and _SCANNED_LINE.search(reply):',
        TARGETS,
    ),
    (
        'a non-string prompt arms the field check',
        HOOK,
        'if isinstance(prompt, str) and _FACT_FIELD_IN_PROMPT in prompt',
        'if _FACT_FIELD_IN_PROMPT in (prompt or "")',
        TARGETS,
    ),
    (
        'every brief arms the field check',
        HOOK,
        'if isinstance(prompt, str) and _FACT_FIELD_IN_PROMPT in prompt and',
        'if isinstance(prompt, str) and',
        TARGETS,
    ),
    (
        'the field check fires when the field is there',
        HOOK,
        'and not _FACT_FIELD.search(reply):',
        'and _FACT_FIELD.search(reply):',
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
        'a tool_response that is not an object is read',
        HOOK,
        'if not isinstance(tool_input, dict) or not isinstance(tool_response, dict):',
        'if not isinstance(tool_input, dict):',
        TARGETS,
    ),
    (
        'a tool_input that is not an object is read',
        HOOK,
        'if not isinstance(tool_input, dict) or not isinstance(tool_response, dict):',
        'if not isinstance(tool_response, dict):',
        TARGETS,
    ),
    (
        'a response with no reply is checked',
        HOOK,
        '    if reply is None:\n        return 0\n',
        '',
        TARGETS,
    ),
    (
        'undecodable stdin crashes the hook',
        HOOK,
        'except (ValueError, RecursionError):',
        'except (json.JSONDecodeError, RecursionError):',
        TARGETS,
    ),
    (
        'deeply nested input crashes the hook',
        HOOK,
        'except (ValueError, RecursionError):',
        'except ValueError:',
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
        '"hookEventName": "PostToolUse",',
        '"hookEventName": "PreToolUse",',
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
        '/hooks/warn-agent-reply-format.py\\"',
        '/hooks/warn-agent-reply-format-gone.py\\"',
        TARGETS + [DEV / "tests" / "hooks" / "test_hooks_wiring.py"],
    ),
]
