"""`run_tests.py` must pin its OWN stdout, not just its children's.

Lives here rather than in a skill scope because `run_tests.py` sits at the
plugin root and belongs to no pytest scope — the same reason the subprocess
guard next door lives here.

WHY THIS EXISTS. Pinning the child decodes was the fix for one bug and the
cause of another: node's reporter emits `✔` and `ℹ`, and once the child was
read as UTF-8 those arrived as real characters instead of mojibake. Writing
them to a cp1252 stdout — the stock Windows default — raised
`UnicodeEncodeError` from `run_tests.py` itself, killing the aggregated run
after several scopes had already passed. Half a contract is worse than none:
before the child pin the bytes were merely wrong, after it the run died.

Nothing else can catch a regression here. The plugin's own suites all run
under pytest, which captures output through its own encoding, so the crash
only ever appears on a bare `python run_tests.py` — and the repo has no CI.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

_PLUGIN_ROOT = Path(__file__).resolve().parents[2]

# The exact characters node's test reporter emits. Both are undefined in cp1252.
_NODE_GLYPHS = "✔ ℹ"


def _print_glyphs_under_cp1252(preamble: str) -> subprocess.CompletedProcess:
    """Run a child whose stdout is cp1252, optionally importing `run_tests`
    first, and try to print node's glyphs to it."""
    code = f"{preamble}\nimport sys; sys.stdout.write({_NODE_GLYPHS!r})"
    env = dict(os.environ, PYTHONIOENCODING="cp1252", PYTHONPATH=str(_PLUGIN_ROOT))
    return subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        env=env, cwd=str(_PLUGIN_ROOT),
    )


def test_importing_the_runner_makes_node_glyphs_printable_on_a_cp1252_stdout():
    result = _print_glyphs_under_cp1252("import run_tests")
    assert result.returncode == 0, result.stderr
    assert "UnicodeEncodeError" not in result.stderr
    assert _NODE_GLYPHS in result.stdout


def test_without_the_runner_the_same_write_raises():
    """Non-vacuity partner. If this stops holding — a future Python defaulting
    stdout to UTF-8 regardless of PYTHONIOENCODING, say — the test above proves
    nothing and should be revisited rather than trusted."""
    result = _print_glyphs_under_cp1252("pass")
    assert result.returncode != 0
    assert "UnicodeEncodeError" in result.stderr


def test_the_pin_is_applied_at_import_time_not_left_to_a_caller():
    """`main()` is not the only entry point — anything that imports the module
    inherits its streams. Calling the pin from inside `main()` would leave that
    path unprotected, so it is asserted to run on import."""
    import ast

    tree = ast.parse((_PLUGIN_ROOT / "run_tests.py").read_text(encoding="utf-8"))
    module_level_calls = {
        node.value.func.id
        for node in tree.body
        if isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Call)
        and isinstance(node.value.func, ast.Name)
    }
    assert "_pin_streams_utf8" in module_level_calls


@pytest.mark.parametrize("stream_name", ["stdout", "stderr"])
def test_both_streams_are_pinned(stream_name):
    """stderr carries the near-miss warnings and the failure summary — the two
    things a reader most needs when a run goes wrong."""
    result = _print_glyphs_under_cp1252(
        f"import run_tests, sys; print(sys.{stream_name}.encoding)"
    )
    assert result.returncode == 0, result.stderr
    assert "utf-8" in result.stdout.lower()
