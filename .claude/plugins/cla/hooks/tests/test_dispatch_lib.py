"""Unit tests for `_dispatch_lib.py` — the module the two dispatcher scripts
share to run sibling hooks in-process. These target the load-isolation and
loud-fail-open behavior added after a code review found both were previously
silent: an unhandled exception discarded all its diagnostic output on exit 0
(stderr is dropped entirely on a non-blocking exit per the documented
PreToolUse hook contract), and a hook that failed to LOAD could crash the
whole dispatcher, taking out every hook positioned after it in the list.
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path
from types import ModuleType

import pytest

_HOOKS_DIR = Path(__file__).resolve().parent.parent
_LIB_PATH = _HOOKS_DIR / "_dispatch_lib.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("dispatch_lib_under_test", _LIB_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


lib = _load_module()


def _stub_module(name: str, main_body: str) -> ModuleType:
    mod = ModuleType(name)
    exec(compile(main_body, f"<stub:{name}>", "exec"), mod.__dict__)
    return mod


# --------------------------------------------------------------------------- #
# run_hook: exception / SystemExit handling
# --------------------------------------------------------------------------- #

def test_run_hook_raising_main_is_loud_fail_open():
    mod = _stub_module("stub_raises", "def main():\n    raise RuntimeError('boom')\n")
    result = lib.run_hook(mod, "{}")
    assert result.code == 0
    assert result.errored is True
    assert "boom" in result.stderr
    assert "RuntimeError" in result.stderr


def test_run_hook_clean_main_is_not_flagged_errored():
    mod = _stub_module("stub_clean", "def main():\n    return 0\n")
    result = lib.run_hook(mod, "{}")
    assert result.code == 0
    assert result.errored is False


def test_run_hook_system_exit_int_code_preserved_and_not_errored():
    mod = _stub_module("stub_exit_2", "import sys\ndef main():\n    sys.exit(2)\n")
    result = lib.run_hook(mod, "{}")
    assert result.code == 2
    assert result.errored is False


def test_run_hook_bare_system_exit_is_not_errored():
    # A bare `sys.exit()` (no args) is a normal, intentional success exit —
    # must NOT be misclassified as an error (regression: e.code is None was
    # once treated the same as a non-int code).
    mod = _stub_module("stub_bare_exit", "import sys\ndef main():\n    sys.exit()\n")
    result = lib.run_hook(mod, "{}")
    assert result.code == 0
    assert result.errored is False


def test_run_hook_system_exit_non_int_code_is_loud_fail_open():
    mod = _stub_module("stub_exit_str", "import sys\ndef main():\n    sys.exit('bad happened')\n")
    result = lib.run_hook(mod, "{}")
    assert result.code == 0
    assert result.errored is True
    assert "bad happened" in result.stderr


# --------------------------------------------------------------------------- #
# run_hook_file: load-failure isolation
# --------------------------------------------------------------------------- #

def test_run_hook_file_isolates_load_failure():
    result = lib.run_hook_file("this-file-does-not-exist.py", "{}")
    assert result.code == 0
    assert result.errored is True
    assert "this-file-does-not-exist.py" in result.stderr


def test_run_hook_file_loads_and_runs_a_real_sibling():
    # Sanity check the happy path still works end-to-end through run_hook_file.
    result = lib.run_hook_file("warn-branch-base.py", '{"tool_input": {"command": "ls"}}')
    assert result.errored is False
    assert result.code == 0


# --------------------------------------------------------------------------- #
# GIT_GLOBAL_OPTS / strip_quoted_spans — shared by every git-matching hook.
# Tested once here at the source rather than duplicated per hook: a fix (or a
# regression) in the shared pattern shows up in exactly one place.
# --------------------------------------------------------------------------- #

def _git_push_pattern():
    return re.compile(r"\bgit\s+" + lib.GIT_GLOBAL_OPTS + r"push\b")


def _branch_create_pattern():
    return re.compile(
        r"\bgit\s+" + lib.GIT_GLOBAL_OPTS + r"(?:checkout\s+-b|switch\s+(?:-c|--create))\s+(\S+)"
    )


@pytest.mark.parametrize(
    "command",
    [
        "git push origin main",
        "git -c core.x=y push origin main",
        "git -C /some/path push origin main",
        "git --work-tree /some/path push origin main",
        "git --git-dir /some/path push origin main",
        "git --git-dir=/some/path push origin main",
        "git --namespace ns push origin main",
        "git --no-pager push origin main",
        "git --bare push origin main",
        "git -c core.x=y -C /some/path --work-tree /other push origin main",
    ],
)
def test_git_global_opts_recognizes_every_documented_prefix_shape(command):
    assert _git_push_pattern().search(command), f"expected a match for: {command!r}"


def test_git_global_opts_documented_gap_is_a_known_no_match_not_a_crash():
    # --exec-path is deliberately NOT in the named space-value-taking list
    # (see GIT_GLOBAL_OPTS's own docstring) — confirms the accepted gap fails
    # SAFE (simply no match) rather than something worse (a garbled partial
    # match, or the pattern eating into the real subcommand token).
    assert not _git_push_pattern().search("git --exec-path /x push origin main")


def test_git_global_opts_does_not_false_positive_on_a_plain_non_main_push():
    # Push-shape detection itself is separate from the main/master-target
    # check a caller layers on top — just confirming the shared pattern
    # doesn't refuse to match a legitimate, unrelated push.
    assert _git_push_pattern().search("git push origin feature/x")


@pytest.mark.parametrize(
    "quoted_value",
    [
        '"/some/checkout path/with a space"',
        "'/some path/with a space'",
    ],
)
def test_strip_quoted_spans_lets_a_quoted_c_or_capital_c_value_with_a_space_match(quoted_value):
    # Before this fix, `-C "/path with space"` broke the mandatory trailing
    # `\s+` in GIT_GLOBAL_OPTS because `\S+` stopped at the space INSIDE the
    # still-quoted value — a real, not exotic, shape (e.g. a checkout under
    # something like "Documents/My Project" on macOS/Windows).
    command = f"git -C {quoted_value} push origin main"
    scanned = lib.strip_quoted_spans(command)
    assert _git_push_pattern().search(scanned), f"expected a match after stripping: {scanned!r}"


def test_strip_quoted_spans_is_length_preserving():
    # Length-preservation is load-bearing, not cosmetic: it's what lets a
    # caller capture a match GROUP against the scanned string (e.g. a branch
    # name) and re-slice the same offsets out of the ORIGINAL command to
    # recover real text a naive collapse-to-`''` would have destroyed.
    command = "git checkout -b 'feature/foo'"
    scanned = lib.strip_quoted_spans(command)
    assert len(scanned) == len(command)

    m = _branch_create_pattern().search(scanned)
    assert m is not None
    real_branch = command[m.start(1) : m.end(1)].strip("'\"")
    assert real_branch == "feature/foo"


def test_strip_quoted_spans_still_hides_a_git_command_mentioned_in_quoted_prose():
    # The original, pre-existing purpose of this function: a `git commit`
    # substring inside a quoted commit message / echoed string must not
    # itself look like a real invocation to a caller matching on `scanned`.
    command = 'echo "run git commit -m foo later" && ls'
    scanned = lib.strip_quoted_spans(command)
    assert "git commit" not in scanned
    assert "git" not in scanned or not re.search(r"\bgit\s+commit\b", scanned)
