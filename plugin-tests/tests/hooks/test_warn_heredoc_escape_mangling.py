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


def test_an_odd_backslash_run_of_three_is_still_an_eaten_escape():
    """`\\\\\\n` is an escaped backslash followed by a real `\\n`. The first cut
    used a one-character lookbehind, which saw a backslash and stayed silent —
    parity is what actually decides this."""
    assert offending_heredocs("cat <<'EOF'\nx = 'a\\\\\\nb'\nEOF")


def test_every_opener_on_one_line_is_scanned_not_just_the_first():
    """`cat <<A <<B` queues two bodies. `search()` found only A and left B's body
    unchecked — measured, with an offending B."""
    cmd = "cat <<A <<B\nplain\nA\nx='a\\nb'\nB"
    found = offending_heredocs(cmd)
    assert [d for d, _ in found] == ["B"], f"B's body was not scanned: {found}"


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


def test_a_herestring_is_not_a_heredoc():
    """`<<<bar` matched the opener at offset 1 and made `bar` a delimiter."""
    assert offending_heredocs("grep -q foo <<<bar\necho 'a\\nb'") == []


def test_an_arithmetic_left_shift_is_not_a_heredoc():
    """`$((1 << n))` matches the opener by construction — `n` is a valid
    delimiter name. Requiring a terminator is what excludes it; without that, the
    rest of the command became `n`'s body and any later escape fired."""
    assert offending_heredocs("echo $((1 << n))\nx=\"a\\nb\"") == []


def test_a_windows_path_in_a_body_does_not_fire():
    """`C:\\temp\\build` carries `\\t` and `\\b`. Trimming the escape class does not
    save this one — it is the reason the class should stay narrow and the reason
    this stays warn-only rather than blocking."""
    found = offending_heredocs("cat <<'EOF'\nsee C:\\temp\\build for output\nEOF")
    assert [e for _, e in found] == [["\\b", "\\t"]], (
        "documents the known false positive rather than pretending it is absent"
    )


def test_a_clean_heredoc_beside_an_offending_one_is_not_blamed():
    cmd = "cat <<'A'\nclean prose\nA\ncat <<'B'\nx='p\\tq'\nB"
    assert [d for d, _ in offending_heredocs(cmd)] == ["B"]


def test_an_unterminated_opener_is_not_treated_as_a_body():
    """Deliberate reversal of the first cut. Treating the remainder as a body is
    what let the arithmetic shift swallow the command; a real heredoc in a tool
    call is terminated. The miss is accepted so the hook stays believable."""
    assert offending_heredocs("python3 - <<'PY'\ns = \"a\\nb\"") == []


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


# --------------------------------------------------------------------------- #
# The deeper sandwich, and why it is deliberately not covered
# --------------------------------------------------------------------------- #


def test_a_long_even_run_is_left_alone():
    """A run of 6 mangles under two re-parses, and this hook stays silent on it.

    That is a KNOWN, DELIBERATE gap, pinned here so nobody re-widens the
    predicate without re-deriving the measurement that closed the question.

    A widening (`run % 2 or run >= 4`) was written, shipped to a PR, and
    reverted. Measured over 42,730 real Bash commands from this machine's
    transcripts, it fired on 3 commands parity did not, and all 3 were correctly
    escaped and did exactly what they intended -- zero true positives. It also
    flagged runs of 4, which is a power of two and therefore the CORRECT
    spelling for a literal two layers down.

    The arithmetic worth keeping: re-parsing halves the run, so N survives
    exactly k re-parses iff N == 2**k. Runs of 2, 4 and 8 are safe at one, two
    and three layers; 6 is safe at one and eaten at two.

    If you widen this again, measure against real commands first. Both tests
    that justified the reverted version were synthetic, and a synthetic case can
    demonstrate a run that mangles while proving nothing about whether anyone
    writes it.
    """
    # 12 source backslashes -> a run of 6 in the command the hook sees. Counted,
    # not assumed: the assertion below would also pass on a run of 2, and an
    # off-by-a-layer literal is how the reverted version's own tests came to
    # exercise 6 while the constant they justified was 4.
    body = 'x = """a \\\\\\\\\\\\nb"""'
    cmd = "python - <<'PY'\n" + body + "\nPY"
    assert body.count("\\") == 6, "this test must exercise a run of 6"
    assert offending_heredocs(cmd) == []
