"""The heredoc-escape hook: it must fire on the shape that actually bit, and stay
quiet on the far more common legitimate heredoc.

A warn hook that fires on every heredoc is muted within a day, at which point it
protects nothing — so the quiet cases below are as load-bearing as the loud ones.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

_DEV_TREE = Path(__file__).resolve().parents[2]
_PLUGIN = _DEV_TREE.parent / ".claude" / "plugins" / "cla"
HOOK = _PLUGIN / "hooks" / "warn-heredoc-escape-mangling.py"


def _load():
    spec = importlib.util.spec_from_file_location("_ut_heredoc_hook", HOOK)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_hook = _load()
offending_heredocs = _hook.offending_heredocs


def _run(cmd: str):
    payload = json.dumps({"tool_input": {"command": cmd}, "cwd": str(_DEV_TREE)})
    return subprocess.run(
        [sys.executable, str(HOOK)],
        input=payload, capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=30,
    )


# --------------------------------------------------------------------------- #
# Fires — the real shape, taken verbatim from the session that motivated it
# --------------------------------------------------------------------------- #


def test_a_python_heredoc_writing_a_backslash_n_is_flagged():
    cmd = "python3 - <<'PY'\ns = \"anchor\\nnext\"\nprint(s)\nPY"
    assert offending_heredocs(cmd), "the exact shape that mangled twice was not caught"
    r = _run(cmd)
    assert r.returncode == 0, "a warn hook must never block"
    assert "warn-heredoc-escape-mangling" in r.stderr
    assert "\\n" in r.stderr


def test_the_escape_is_named_in_the_warning():
    """Naming which escape was seen is what makes the warning actionable — the
    author has to find it in the body."""
    _, escapes = offending_heredocs("cat <<'EOF'\nx = \"a\\tb\"\nEOF")[0]
    assert escapes == ["\\t"]


def test_more_than_one_heredoc_in_one_command_is_all_reported():
    cmd = "cat <<'A'\nx\\ny\nA\ncat <<'B'\np\\tq\nB"
    found = offending_heredocs(cmd)
    assert [d for d, _ in found] == ["A", "B"]


def test_an_unterminated_heredoc_still_has_its_body_scanned():
    """Conservative reading: the text after the opener IS the body. Bailing out
    here would make a truncated command the way to slip past the hook."""
    assert offending_heredocs("python3 - <<'PY'\ns = \"a\\nb\"")


# --------------------------------------------------------------------------- #
# Stays quiet — the cases that decide whether anyone leaves it enabled
# --------------------------------------------------------------------------- #


def test_an_ordinary_multi_line_heredoc_is_not_flagged():
    cmd = "cat <<'EOF'\njust some prose\nover two lines\nEOF"
    assert offending_heredocs(cmd) == []
    assert _run(cmd).stderr == ""


def test_a_command_with_no_heredoc_at_all_is_not_flagged():
    assert offending_heredocs('echo "a\\nb"') == []


def test_a_doubled_backslash_is_left_alone():
    """An author writing `\\\\n` has already thought about the layering; flagging
    it would be the false positive that gets the hook muted."""
    assert offending_heredocs("cat <<'EOF'\nx = \"a\\\\nb\"\nEOF") == []


def test_text_after_the_terminator_is_not_part_of_the_body():
    cmd = "cat <<'EOF'\nclean prose\nEOF\necho \"tail \\n here\""
    assert offending_heredocs(cmd) == []


# --------------------------------------------------------------------------- #
# Non-vacuity — the scan must actually be looking at something
# --------------------------------------------------------------------------- #


def test_the_hook_file_exists_and_is_wired_into_the_bash_dispatcher():
    assert HOOK.is_file(), f"{HOOK} is missing; the dispatcher would skip it silently"
    dispatcher = (_PLUGIN / "hooks" / "dispatch-bash-pretooluse.py").read_text(
        encoding="utf-8"
    )
    assert "warn-heredoc-escape-mangling.py" in dispatcher, (
        "the hook exists but nothing runs it — a hook file alone is inert"
    )
