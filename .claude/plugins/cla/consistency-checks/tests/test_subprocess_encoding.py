"""Every `subprocess.run(..., text=True)` in synced core must pin its decode.

Lives in `consistency-checks/` because the rule spans hooks, five skills'
scripts, every test scope, and the plugin-root runner — no single pytest scope
can see the whole set.

WHY THIS CLASS IS WORSE THAN AN ORDINARY ENCODING BUG. `text=True` with no
`encoding=` decodes with the ambient locale (cp1252 on a stock Windows box), and
the failure escapes the caller's error handling entirely:

  1. The decode happens in `subprocess`'s READER THREAD, so it dumps an
     unhandled traceback rather than raising where the caller can see it.
  2. `returncode` is still 0 — the call looks successful.
  3. `stdout` is None, so the next `.stdout.strip()` raises `AttributeError`,
     which `except (OSError, subprocess.SubprocessError)` cannot catch.
     `UnicodeDecodeError` is a `ValueError`, and it never propagates anyway.

`block-worktree-path-escape.py` is an ENFORCING guard, and
`_git_common.repo_root()` is bound at import time by five scripts — so the
script dies before emitting any JSON. Trigger: a checkout path or branch name
outside the ANSI code page (Cyrillic, much CJK), or `warn-stacked-pr-merge`'s
`gh pr list --json number,title`, which pulls arbitrary user text.

The whole class was structurally invisible to the existing suites: every case
feeds `str` / `io.StringIO`, so nothing ever crossed the byte boundary. The
behavioural test below does.

WHY THIS CHECK IS AST-BASED. The first version matched text per line and was
defeated three separate ways, each proven by a surviving mutation:
  - a call splitting `text=True` and `encoding=` across lines read as unpinned;
  - any `encoding=` elsewhere on the line — a trailing comment — read as pinned;
  - it never checked `errors=` at all, which is the load-bearing half: a strict
    decode still raises in the reader thread.
Parsing removes all three, and the scan set below is stated as
everything-minus-exclusions so an under-scan is visible rather than assumed.
"""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

import pytest

_PLUGIN_ROOT = Path(__file__).resolve().parents[2]

# Bytes UNDEFINED in cp1252. Decoding them with that codec raises; with utf-8 +
# errors="replace" they become U+FFFD. This is Cyrillic `ст` (U+0441 U+0442),
# i.e. an ordinary branch name in a Russian-language repo, not a contrived value.
_UNDECODABLE_IN_CP1252 = "ст".encode("utf-8")


def _scanned_files() -> list[Path]:
    """Every `.py` under the plugin that could spawn a subprocess.

    Stated as "everything, minus a named exclusion" rather than as a positive
    allow-list of two globs. The allow-list version silently missed
    `run_tests.py` at the plugin root, `skills/*/tests/conftest.py`, and every
    `tests/` directory — 47 swept sites that no guard could see. An
    under-scanning guard is the same defect class this file exists to prevent.
    """
    return sorted(
        p for p in _PLUGIN_ROOT.rglob("*.py")
        if "__pycache__" not in p.parts and ".pytest_cache" not in p.parts
    )


def _unpinned_calls(tree: ast.AST) -> list[tuple[int, str]]:
    """`(lineno, reason)` for every `subprocess.run(text=True)` lacking a pin.

    Reads the parsed call, so it is immune to line splitting and to an
    `encoding=` appearing in a comment.
    """
    problems: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        kwargs = {k.arg: k.value for k in node.keywords if k.arg}
        text = kwargs.get("text")
        if not (isinstance(text, ast.Constant) and text.value is True):
            continue
        if "encoding" not in kwargs:
            problems.append((node.lineno, "no encoding="))
        elif "errors" not in kwargs:
            # The load-bearing half. A strict decode still raises in the reader
            # thread; `errors="replace"` is what lets a guard degrade to a
            # mojibake'd path it can still reason about instead of to None.
            problems.append((node.lineno, "encoding= without errors="))
    return problems


def test_every_subprocess_text_call_pins_encoding_and_errors():
    offenders = []
    for f in _scanned_files():
        try:
            tree = ast.parse(f.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError) as exc:  # pragma: no cover
            pytest.fail(f"{f}: {exc}")
        for lineno, why in _unpinned_calls(tree):
            offenders.append(f"{f.relative_to(_PLUGIN_ROOT).as_posix()}:{lineno} ({why})")
    assert not offenders, (
        'subprocess text decode left to the ambient locale — add encoding="utf-8", '
        'errors="replace":\n  ' + "\n  ".join(offenders)
    )


def test_the_scan_reaches_the_places_the_first_version_missed():
    """Non-vacuity partner, naming the exact files an allow-list glob excluded.
    A guard that scans nothing passes forever, and this one already did once."""
    names = {p.relative_to(_PLUGIN_ROOT).as_posix() for p in _scanned_files()}
    assert len(names) > 60, f"scan set collapsed to {len(names)} files"
    for expected in (
        "run_tests.py",                             # plugin root
        "hooks/tests/test_dispatch.py",             # a tests/ dir
        "skills/spec-to-pr/tests/conftest.py",      # a conftest
        "skills/spec-to-pr/scripts/probe_state.py", # a skill script
        "hooks/_dispatch_lib.py",                   # enforcing code
    ):
        assert expected in names, f"{expected} is not scanned"


def test_the_checker_flags_each_shape_it_is_meant_to_catch():
    """The three ways the line-based version was defeated, as parsed snippets."""
    unpinned = ast.parse("subprocess.run(cmd, capture_output=True, text=True)")
    assert _unpinned_calls(unpinned)

    split_across_lines = ast.parse(
        "subprocess.run(\n    cmd,\n    text=True,\n    encoding='utf-8',\n"
        "    errors='replace',\n)"
    )
    assert not _unpinned_calls(split_across_lines), "a multi-line pinned call must pass"

    comment_only = ast.parse("subprocess.run(cmd, text=True)  # encoding=utf-8 honest")
    assert _unpinned_calls(comment_only), "a comment must not satisfy the check"

    strict = ast.parse("subprocess.run(cmd, text=True, encoding='utf-8')")
    assert _unpinned_calls(strict) == [(1, "encoding= without errors=")]


@pytest.mark.parametrize("errors", ["replace", "surrogateescape"])
def test_utf8_with_a_fallback_survives_bytes_that_break_the_ambient_locale(errors):
    """The behavioural half, crossing the byte boundary the suites could not."""
    r = subprocess.run(
        [sys.executable, "-c",
         "import sys; sys.stdout.buffer.write(%r); sys.stdout.buffer.flush()"
         % _UNDECODABLE_IN_CP1252],
        capture_output=True, text=True, encoding="utf-8", errors=errors,
    )
    assert r.returncode == 0
    assert r.stdout is not None, "the failure mode: stdout comes back None"
    assert isinstance(r.stdout, str)


def test_the_unpinned_form_really_does_fail_on_those_bytes():
    """Non-vacuity partner for the test above, and the reproduction for the whole
    finding: the same bytes raise under cp1252. If this stops holding, the test
    above proves nothing."""
    with pytest.raises(UnicodeDecodeError):
        _UNDECODABLE_IN_CP1252.decode("cp1252")


def test_a_guard_degrades_to_a_readable_path_not_to_none():
    """`errors="replace"` rather than strict is the load-bearing choice: a guard
    handed a mojibake'd path can still compare prefixes and detect a worktree
    escape. One handed None crashes on the next attribute access, inside an
    `except` clause that cannot catch it."""
    decoded = _UNDECODABLE_IN_CP1252.decode("utf-8", errors="replace")
    assert decoded and decoded.strip()
