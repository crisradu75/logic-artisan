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
from pathlib import Path
from types import ModuleType

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
