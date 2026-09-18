"""Every row in this repo's provenance ledger must be one the writer could emit.

`log-commit-provenance.py` shapes a record three ways before it reaches the file
— `_MAX_TRAILERS`, `_MAX_TRAILER_CHARS`, and a byte-shedding loop against
`_MAX_LINE_BYTES` — and `plugin-tests/tests/hooks/test_log_commit_provenance.py`
covers all three ON THE WRITER. Nothing covered the FILE.

The difference is not academic, and it is why this guard exists. The ledger is
edited by hand exactly once in its history: the 2026-09-18 backfill of the rows
the pre-`ab69d5e` trailer parser zeroed. That edit stored `_measured_by()`'s raw
return, which is the extraction and not the record — 20 values in a 3483-byte
line where the writer would have emitted 10 values in 1657 bytes. The full suite
stayed green, because every test that knows about the caps drives the writer and
the writer was never the thing that was wrong.

WHAT RESTS ON IT. `_already_recorded_fh` seeks to the last 4096 bytes and parses
`lines[-1]` alone; its docstring justifies that with "a row is capped at
`_MAX_LINE_BYTES`, so 4 KiB always contains a whole last line". A row past 4096
bytes at the TAIL therefore makes `json.loads` fail, `_already_recorded_fh`
return False, and the hook append a duplicate — silently, into the denominator
the ledger exists to supply. The bad rows sat mid-file, so nothing broke; the
invariant they violated is the one the dedupe is built on.

The caps and the tail size are READ FROM THE HOOK, never restated here. The 4096
is a literal inside `_already_recorded_fh` rather than a named constant, so it is
pulled out by AST from that one function — a mention in a docstring or another
function cannot answer for it.
"""

from __future__ import annotations

import ast
import importlib.util
import json
from pathlib import Path

import pytest

_DEV_TREE = Path(__file__).resolve().parents[2]
_REPO = _DEV_TREE.parent
_HOOK = _REPO / ".claude" / "plugins" / "cla" / "hooks" / "log-commit-provenance.py"
_LEDGER = _REPO / "cla.io" / "retro" / "commit-provenance.jsonl"


def _hook():
    spec = importlib.util.spec_from_file_location("log_commit_provenance_guard", _HOOK)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _dedupe_tail_bytes() -> int:
    """The window `_already_recorded_fh` reads, taken from that function only."""
    tree = ast.parse(_HOOK.read_text(encoding="utf-8"), filename=str(_HOOK))
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_already_recorded_fh":
            # The window is the literal subtracted from the file size — the
            # `size - N` in `fh.seek(max(0, size - N))`. Matched on that shape
            # rather than on "a positive int in this function", which also
            # catches the `-1` of `lines[-1]` and any index added later.
            sizes = [
                n.right.value for n in ast.walk(node)
                if isinstance(n, ast.BinOp) and isinstance(n.op, ast.Sub)
                and isinstance(n.left, ast.Name) and n.left.id == "size"
                and isinstance(n.right, ast.Constant) and isinstance(n.right.value, int)
            ]
            assert len(sizes) == 1, (
                f"expected exactly one `size - <literal>` in "
                f"`_already_recorded_fh` (the tail window), found {sizes}. If the "
                f"seek was rewritten, name the window as a constant and read it "
                f"here instead — a guard that picks the wrong literal is worse "
                f"than one that refuses."
            )
            return sizes[0]
    raise AssertionError("`_already_recorded_fh` not found in the hook")


def _rows() -> list[tuple[int, str, dict]]:
    with open(_LEDGER, encoding="utf-8", newline="") as fh:
        raw = fh.read()
    out = []
    for i, line in enumerate(raw.splitlines(), start=1):
        if line.strip():
            out.append((i, line, json.loads(line)))
    return out


def test_the_ledger_is_there_and_has_rows_to_check():
    """Non-vacuity. Every assertion below iterates the file, so an absent or
    empty ledger would turn this whole module green while checking nothing —
    and the ledger is opt-in by file presence, so absence is a real state."""
    assert _LEDGER.is_file(), f"no provenance ledger at {_LEDGER}"
    rows = _rows()
    assert rows, "the ledger is empty; every check in this file would be vacuous"
    # The value-shaped checks need at least one row that HAS values, for the
    # same reason: a ledger of bare `[]` satisfies both value caps trivially.
    assert any(r["measured_by"] for _, _, r in rows if "measured_by" in r), (
        "no row carries a `measured_by` value, so the per-value cap below is "
        "checked over nothing"
    )


def test_no_row_exceeds_the_caps_the_writer_enforces():
    mod = _hook()
    offenders = []
    for lineno, line, rec in _rows():
        values = rec.get("measured_by", [])
        nbytes = len((line.rstrip("\r\n") + "\n").encode("utf-8"))
        if len(values) > mod._MAX_TRAILERS:
            offenders.append(
                f"  line {lineno} ({rec.get('sha')}): {len(values)} values, "
                f"_MAX_TRAILERS is {mod._MAX_TRAILERS}"
            )
        long = [v for v in values if len(v) > mod._MAX_TRAILER_CHARS]
        if long:
            offenders.append(
                f"  line {lineno} ({rec.get('sha')}): {len(long)} value(s) longer "
                f"than _MAX_TRAILER_CHARS ({mod._MAX_TRAILER_CHARS}), longest "
                f"{max(len(v) for v in long)}"
            )
        if nbytes > mod._MAX_LINE_BYTES:
            offenders.append(
                f"  line {lineno} ({rec.get('sha')}): {nbytes} bytes, "
                f"_MAX_LINE_BYTES is {mod._MAX_LINE_BYTES}"
            )
    assert not offenders, (
        "row(s) in the provenance ledger are not rows the writer could have "
        "produced. Anything editing this file must apply `main()`'s shaping — "
        "the caps and the shedding loop — not just `_measured_by()`'s return:\n"
        + "\n".join(offenders)
    )


def test_the_dedupe_window_still_clears_a_maximal_row():
    """The margin `_already_recorded_fh`'s docstring claims, checked rather than
    asserted in prose. It reads a fixed tail and parses only the LAST line, so
    the window must hold a whole maximal row with room for the partial row above
    it — two maximal rows is the bound that guarantees that."""
    mod = _hook()
    tail = _dedupe_tail_bytes()
    assert tail >= 2 * mod._MAX_LINE_BYTES, (
        f"`_already_recorded_fh` reads a {tail}-byte tail while a row may be "
        f"{mod._MAX_LINE_BYTES} bytes. Its docstring relies on the tail always "
        f"containing a whole last line; at this ratio a maximal final row can be "
        f"truncated, `json.loads` fails, the dedupe reads 'not recorded' and the "
        f"hook appends a duplicate."
    )


def test_the_longest_row_on_disk_is_reported_against_both_bounds():
    """Not a bound of its own — it prints the live margin so a run that is one
    long commit message away from the cap says so, instead of passing silently
    until the row that trips it."""
    mod = _hook()
    rows = _rows()
    lineno, line, rec = max(
        rows, key=lambda r: len((r[1].rstrip("\r\n") + "\n").encode("utf-8"))
    )
    nbytes = len((line.rstrip("\r\n") + "\n").encode("utf-8"))
    print(
        f"longest row: line {lineno} ({rec.get('sha')}) at {nbytes} bytes — "
        f"{mod._MAX_LINE_BYTES - nbytes} under _MAX_LINE_BYTES, "
        f"{_dedupe_tail_bytes() - nbytes} under the dedupe tail"
    )
    assert nbytes <= mod._MAX_LINE_BYTES


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q", "-s"]))
