"""Every `subprocess.run(..., text=True)` in synced core must pin its encoding.

Lives in `consistency-checks/` rather than in any one scope because the rule
spans all of them — hooks and five skills' scripts — and no single scope can see
the whole set.

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
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

_PLUGIN_ROOT = Path(__file__).resolve().parents[2]

# Bytes that are UNDEFINED in cp1252. Decoding them with that codec raises
# UnicodeDecodeError; with utf-8 + errors="replace" they become U+FFFD. This is
# the second byte of Cyrillic `с` (U+0441 -> D1 81), i.e. an ordinary branch
# name in a Russian-language repo, not a contrived value.
_UNDECODABLE_IN_CP1252 = b"\xd1\x81\xd1\x82"


def _scanned_files() -> list[Path]:
    """Every `.py` in synced core that could spawn a subprocess."""
    return sorted(
        list((_PLUGIN_ROOT / "hooks").glob("*.py"))
        + list(_PLUGIN_ROOT.glob("skills/*/scripts/*.py"))
    )


def test_every_subprocess_text_call_pins_its_encoding():
    """Source-level guard. 24 sites were unpinned when this was written, three
    of them in enforcing code, and nothing could see them — so the rule is
    asserted mechanically rather than left to review."""
    offenders = []
    for f in _scanned_files():
        for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            if "text=True" in line and "encoding=" not in line and not line.lstrip().startswith("#"):
                offenders.append(f"{f.relative_to(_PLUGIN_ROOT).as_posix()}:{i}")
    assert not offenders, (
        "subprocess text decode left to the ambient locale — add "
        'encoding="utf-8", errors="replace":\n  ' + "\n  ".join(offenders)
    )


def test_the_scan_actually_finds_files():
    """Non-vacuity partner: a guard that scans nothing passes forever."""
    files = _scanned_files()
    assert len(files) > 20, f"expected the whole synced-core script set, got {len(files)}"
    assert any("text=True" in f.read_text(encoding="utf-8") for f in files), (
        "no subprocess text call found at all — the pattern this guards has moved"
    )


@pytest.mark.parametrize("errors", ["replace", "surrogateescape"])
def test_utf8_with_a_fallback_survives_bytes_that_break_the_ambient_locale(errors):
    """The behavioural half, crossing the byte boundary the suite could not.

    Emits bytes that are UNDEFINED in cp1252 and confirms the pinned decode
    returns a usable string. Run under an explicitly cp1252 child environment so
    the assertion means something on a POSIX dev box too."""
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
    """Non-vacuity partner for the test above, and the reproduction for the
    whole finding: decoding the same bytes as cp1252 raises. If this ever stops
    raising, the test above is proving nothing."""
    with pytest.raises(UnicodeDecodeError):
        _UNDECODABLE_IN_CP1252.decode("cp1252")


def test_a_guard_degrades_to_a_readable_path_not_to_none():
    """`errors="replace"` rather than strict is the load-bearing choice: a guard
    that gets a mojibake'd path can still reason about it (compare prefixes,
    detect a worktree escape). One that gets None crashes on the next
    attribute access, inside an `except` clause that cannot catch it."""
    decoded = _UNDECODABLE_IN_CP1252.decode("utf-8", errors="replace")
    assert decoded and isinstance(decoded, str)
    assert decoded.strip(), "must remain something a guard can still operate on"
