"""`warn-comment-dates`: warn (never block) when an Edit or Write adds a `#` comment line
carrying a bare YYYY-MM-DD date to a `.py` or `.sh` file.

The hook was reached only through the dispatcher tests, which check that it fires once and
that a `.md` file passes. This file pins its own allow/deny table.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

HOOK_PATH = Path(__file__).resolve().parents[3] / ".claude" / "plugins" / "cla" / "hooks" / "warn-comment-dates.py"


def _run(tool_input: dict) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input=json.dumps({"tool_input": tool_input}),
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )


def _warning(result: subprocess.CompletedProcess) -> str:
    assert result.returncode == 0, "the hook only ever warns"
    if not result.stdout.strip():
        return ""
    return json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]


# requirement: guard-warnings / A dated comment warns
@pytest.mark.parametrize(
    "tool_input",
    [
        {"file_path": "a.py", "new_string": "x = 1  # fixed 2026-10-30\n"},
        {"file_path": "a.py", "content": "# confirmed 2026-10-30 in review\nx = 1\n"},
        {"file_path": "run.sh", "new_string": "echo hi  # 2026-01-02 workaround\n"},
        {"file_path": "dir/b.py", "old_string": "x", "new_string": "    # since 2025-12-31\n"},
    ],
)
def test_a_dated_comment_in_python_or_shell_warns(tool_input):
    warning = _warning(_run(tool_input))
    assert "YYYY-MM-DD date" in warning
    assert "20" in warning, "the offending line is quoted back"


@pytest.mark.parametrize(
    "tool_input",
    [
        {"file_path": "notes.md", "content": "# Release 2026-10-30\n"},  # docs carry dates
        {"file_path": "a.py", "new_string": 'RELEASED = "2026-10-30"\n'},  # no comment
        {"file_path": "a.py", "new_string": "# a timeless reason, no date\n"},
        {"file_path": "a.py", "new_string": "# version 2026-1-3 is not a full date\n"},
        {"file_path": "a.py", "old_string": "# was 2026-10-30", "new_string": "x = 1\n"},  # only added text
        {"file_path": "a.txt", "content": "# 2026-10-30\n"},
    ],
)
def test_no_dated_comment_is_added_so_the_hook_is_silent(tool_input):
    """Non-vacuity partner: dates outside comments, outside .py/.sh, or only in removed text."""
    assert _warning(_run(tool_input)) == ""


def test_only_the_first_three_lines_are_quoted():
    added = "".join(f"# line {i} 2026-10-{10 + i}\n" for i in range(5))
    warning = _warning(_run({"file_path": "a.py", "content": added}))
    assert "line 2" in warning and "line 3" not in warning


def test_a_malformed_payload_is_ignored():
    result = subprocess.run(
        [sys.executable, str(HOOK_PATH)], input="not json",
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    assert result.returncode == 0 and result.stdout == ""


def test_a_payload_without_tool_input_is_ignored():
    result = subprocess.run(
        [sys.executable, str(HOOK_PATH)], input="{}",
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    assert result.returncode == 0 and result.stdout == ""


# requirement: guard-warnings / A dated comment warns
@pytest.mark.parametrize(
    "tool_input",
    [
        {"file_path": "a.py", "new_string": "#2026-10-30\n"},  # no space after the hash
        {"file_path": "a.py", "new_string": 'x = "#"  # 2026-10-30\n'},  # second hash on the line
        {"file_path": "a.py", "new_string": 'url = "a#b 2026-10-30"\n'},  # a hash inside a string still counts
        {"file_path": "a.py", "new_string": "# 2026-10-30 and 2026-11-01\n"},  # two dates on one line
        {"file_path": "a.py", "new_string": "x = 1\r\n# 2026-10-30\r\n"},  # CRLF line endings
        {"file_path": "a.py", "new_string": "", "content": "# 2026-10-30\n"},  # empty new_string falls through to content
        {"file_path": "C:\\repo\\a.py", "content": "# 2026-10-30\n"},  # Windows path
    ],
)
def test_other_shapes_of_a_dated_comment_warn(tool_input):
    assert "YYYY-MM-DD date" in _warning(_run(tool_input))


@pytest.mark.parametrize(
    "tool_input",
    [
        {"file_path": "a.py", "new_string": 'x = "2026-10-30"  # note\n'},  # date sits before the hash
        {"file_path": "a.py", "new_string": "# id 12026-10-30 is not a date\n"},  # digit glued on the left
        {"file_path": "a.py", "new_string": "# id 2026-10-301 is not a date\n"},  # digit glued on the right
        {"file_path": "a.py", "new_string": "# 26-10-30 is a short year\n"},
        {"file_path": "a.py", "new_string": "# 2026/10/30 uses slashes\n"},
        {"file_path": "a.py", "new_string": "# 2026-10 is year and month only\n"},
        {"file_path": "a.py", "new_string": "# in 2026 we did it\n"},  # year only
        {"file_path": "A.PY", "new_string": "# 2026-10-30\n"},  # the suffix check is case-sensitive
        {"file_path": "a.py", "new_string": ""},
        {"file_path": "a.py"},  # neither new_string nor content
        {"new_string": "# 2026-10-30\n"},  # no file_path
        {"file_path": "a.js", "new_string": "// 2026-10-30\n"},  # other comment syntax is out of scope
        {"file_path": "a.py", "new_string": "x = 1\n# fine\n    \n"},
    ],
)
def test_near_misses_of_the_date_pattern_stay_silent(tool_input):
    assert _warning(_run(tool_input)) == ""


def test_the_warning_quotes_the_dated_line_stripped():
    added = "x = 1\n    # old 2026-10-30   \ny = 2\n# clean\n"
    warning = _warning(_run({"file_path": "a.py", "content": added}))
    assert warning.endswith("Lines: # old 2026-10-30")


def test_a_line_with_two_dates_is_one_hit():
    warning = _warning(_run({"file_path": "a.py", "content": "# 2026-10-30 and 2026-11-01\n"}))
    assert " | " not in warning


def test_dated_lines_are_joined_with_a_pipe_and_clean_lines_skipped():
    added = "# a 2026-10-01\nx = 1\n# b 2026-10-02\n"
    warning = _warning(_run({"file_path": "a.py", "content": added}))
    assert warning.endswith("# a 2026-10-01 | # b 2026-10-02")


def test_an_edit_with_both_fields_reads_new_string_not_content():
    warning = _warning(_run({"file_path": "a.py", "new_string": "# new 2026-10-30\n", "content": "# other 2025-01-01\n"}))
    assert "2026-10-30" in warning and "2025-01-01" not in warning
