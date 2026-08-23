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

_REPO_ROOT = Path(__file__).resolve().parents[3]
_PLUGIN_ROOT = _REPO_ROOT / ".claude" / "plugins" / "cla"

# THREE trees, not one. This guard's subject is "every `.py` this repo owns
# that could spawn a subprocess", and `extract-dev-tree-from-plugin` split
# that population across the published plugin, the dev tree, and the
# repo-local skills tree. Leaving the scan pointed at the plugin alone would
# have dropped it from 84 files to 27 — and the floor below would then have
# had to be lowered, which is exactly the false relaxation this file's own
# comment forbids.
_SCAN_ROOTS = (
    _PLUGIN_ROOT,
    _REPO_ROOT / "plugin-tests",
    _REPO_ROOT / ".claude" / "skills",
)

# Bytes UNDEFINED in cp1252. Decoding them with that codec raises; with utf-8 +
# errors="replace" they become U+FFFD. This is Cyrillic `ст` (U+0441 U+0442),
# i.e. an ordinary branch name in a Russian-language repo, not a contrived value.
_UNDECODABLE_IN_CP1252 = "ст".encode("utf-8")


# Scanning a vendored `.venv` or `node_modules` would fail this suite on
# third-party code nobody here can fix.
_EXCLUDE_PARTS = {"__pycache__", ".pytest_cache", ".git", ".venv", "node_modules"}

# The spawners, and the module names they are reached through in this tree.
# Checking the CALLEE is what lets the `encoding=`-alone rule below exist: an
# unqualified "any call with encoding=" would flag every `open(p,
# encoding="utf-8")` in the plugin, and a guard that cries wolf gets deleted.
_SPAWNERS = {"run", "Popen", "call", "check_call", "check_output"}
_SPAWN_MODULES = {"subprocess", "_sp", "sp"}


def _scanned_files() -> list[Path]:
    """Every `.py` this repo owns that could spawn a subprocess.

    Stated as "everything under each root, minus a named exclusion" rather
    than as a positive allow-list of globs. The allow-list version silently
    missed the root-level runner, `skills/*/tests/conftest.py`, and every
    `tests/` directory — 47 swept sites that no guard could see. An
    under-scanning guard is the same defect class this file exists to prevent,
    which is also why the root list is three trees and not just the plugin.
    """
    out = []
    for root in _SCAN_ROOTS:
        if not root.is_dir():
            continue
        out.extend(
            p for p in root.rglob("*.py")
            if not set(p.parts) & _EXCLUDE_PARTS
        )
    return sorted(set(out))


def _is_spawn(func: ast.expr) -> bool:
    """True for `subprocess.run(...)` and the aliased spellings used here."""
    return (
        isinstance(func, ast.Attribute)
        and func.attr in _SPAWNERS
        and isinstance(func.value, ast.Name)
        and func.value.id in _SPAWN_MODULES
    )


def _unpinned_calls(tree: ast.AST) -> list[tuple[int, str]]:
    """`(lineno, reason)` for every text-mode subprocess call lacking a pin.

    Reads the parsed call, so it is immune to line splitting and to an
    `encoding=` appearing in a comment.

    THREE ways into text mode, not one. `text=True` is the obvious spelling;
    `universal_newlines=True` is CPython's exact alias for it; and `encoding=`
    ALONE puts the pipes in text mode too — so `subprocess.run(cmd,
    capture_output=True, encoding="utf-8")`, the natural shorthand and a STRICT
    decode, raises in the reader thread just the same. Checking only `text=True`
    left two one-token ways to silence a guard built to be unevadable.
    """
    problems: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not _is_spawn(node.func):
            continue
        kwargs = {k.arg: k.value for k in node.keywords if k.arg}
        if any(k.arg is None for k in node.keywords):
            # `subprocess.run(cmd, **opts)` — text mode is decided at runtime and
            # cannot be read here. Reported rather than skipped: a silent pass on
            # the one shape the checker cannot see is how the class comes back.
            problems.append((node.lineno, "**kwargs splat — text mode is unreadable"))
            continue
        text_mode = "encoding" in kwargs or any(
            isinstance(kwargs.get(name), ast.Constant) and kwargs[name].value is True
            for name in ("text", "universal_newlines")
        )
        if not text_mode:
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
            offenders.append(f"{f.relative_to(_REPO_ROOT).as_posix()}:{lineno} ({why})")
    assert not offenders, (
        'subprocess text decode left to the ambient locale — add encoding="utf-8", '
        'errors="replace":\n  ' + "\n  ".join(offenders)
    )


def test_the_scan_reaches_the_places_the_first_version_missed():
    """Non-vacuity partner, naming the exact files an allow-list glob excluded.
    A guard that scans nothing passes forever, and this one already did once."""
    names = {p.relative_to(_REPO_ROOT).as_posix() for p in _scanned_files()}
    # Tracks the real count rather than sitting well below it, where a collapse
    # that halved the scan set would still pass. RE-DERIVED, not adjusted:
    # `extract-dev-tree-from-plugin` moved the tests out of the plugin, so the
    # plugin alone now holds 27 `.py` files. Scanning only the plugin would
    # have forced this floor down to ~25 — a check certifying what it had
    # stopped checking. Scanning all three trees the repo actually owns keeps
    # the population at 80 (84 in the plugin alone before the move, less the 4
    # `.py` files this change deletes), so the floor stays where it was. The
    # named anchors below are the stronger half of this pair — they span four
    # subtrees, so an exclusion that drops any one of them fails here even if
    # the count survives.
    #
    # A DELIBERATE deletion is expected to trip this and get the floor lowered
    # with it; that is the check working. Lower it to the new real count, never
    # to a number chosen to be safe from future deletions.
    assert len(names) >= 55, f"scan set collapsed to {len(names)} files"
    for expected in (
        # `run_tests.py` stood at the head of this list as "plugin root".
        # It was deleted with the twelve-scope split; `plugin-tests/mutate.py`
        # takes its place as the dev tree's root-level runner.
        "plugin-tests/mutate.py",                          # a dev-tree root script
        "plugin-tests/tests/hooks/test_dispatch.py",       # a tests/ dir
        "plugin-tests/tests/skills/spec-to-pr/conftest.py", # a conftest
        ".claude/plugins/cla/skills/spec-to-pr/scripts/probe_state.py", # a skill script
        ".claude/plugins/cla/hooks/_dispatch_lib.py",      # enforcing code
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


@pytest.mark.parametrize("source", [
    # CPython's exact alias for `text=True`.
    "subprocess.run(cmd, universal_newlines=True)",
    "subprocess.run(cmd, universal_newlines=True, encoding='utf-8')",
    # `encoding=` ALONE enables text mode. Measured: this exact call decodes in
    # the reader thread and comes back returncode 0 / stdout None.
    "subprocess.run(cmd, capture_output=True, encoding='cp1252')",
    # Runtime-decided kwargs: unreadable, so reported rather than waved through.
    "subprocess.run(cmd, **opts)",
    "_sp.run(cmd, text=True)",
    "subprocess.Popen(cmd, text=True)",
    "subprocess.check_output(cmd, text=True)",
])
def test_the_alternate_spellings_are_not_an_escape_hatch(source):
    """Each of these reaches text mode without the word `text=True`, and each
    was invisible to the first AST version — a one-token way to silence a guard
    whose whole purpose is to be unevadable."""
    assert _unpinned_calls(ast.parse(source)), source


@pytest.mark.parametrize("source", [
    # The reason the checker inspects the CALLEE. `open` is the common case; an
    # unqualified "any call with encoding=" would flag every one in the plugin.
    "open(path, encoding='utf-8')",
    "path.read_text(encoding='utf-8')",
    # A non-subprocess callee that happens to take `text=`.
    "widget.Label(master, text=True)",
    "parser.add_argument('--x', text=True)",
    # Correctly pinned, in every spelling.
    "subprocess.run(cmd, text=True, encoding='utf-8', errors='replace')",
    "subprocess.run(cmd, universal_newlines=True, encoding='utf-8', errors='replace')",
    # No text mode at all: bytes in, bytes out, nothing to decode.
    "subprocess.run(cmd, capture_output=True)",
])
def test_the_checker_does_not_cry_wolf(source):
    assert not _unpinned_calls(ast.parse(source)), source


def test_no_module_reaches_a_spawner_by_a_bare_name():
    """Pins the assumption `_is_spawn` rests on.

    It matches `<module>.<spawner>`, so a `from subprocess import run` followed
    by a bare `run(cmd, text=True)` would slip past. No file does that today;
    this fails the moment one starts, rather than letting the checker quietly
    stop covering it."""
    offenders = []
    for f in _scanned_files():
        for node in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
            if isinstance(node, ast.ImportFrom) and node.module == "subprocess":
                names = ", ".join(a.name for a in node.names)
                offenders.append(f"{f.relative_to(_REPO_ROOT).as_posix()}:{node.lineno} ({names})")
    assert not offenders, (
        "`from subprocess import ...` bypasses the callee check — import the "
        "module instead:\n  " + "\n  ".join(offenders)
    )


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
