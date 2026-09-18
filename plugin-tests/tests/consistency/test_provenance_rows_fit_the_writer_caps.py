"""No row in this repo's provenance ledger exceeds the caps the writer enforces.

`log-commit-provenance.py` shapes a record three ways before it reaches the file
— `_MAX_TRAILERS`, `_MAX_TRAILER_CHARS`, and a byte-shedding loop against
`_MAX_LINE_BYTES` — and `plugin-tests/tests/hooks/test_log_commit_provenance.py`
covers all three ON THE WRITER. Nothing covered the FILE.

The difference is not academic. The ledger has been edited by hand exactly once:
the backfill of the rows the old trailer parser zeroed, recorded in
`cla.io/retro/commit-provenance-corrections.md`. The first attempt stored
`_measured_by()`'s raw return, which is the extraction and not the record — 20
values in one 3484-byte line, terminator included, where the writer emits 10 in
1657. The full suite stayed green, because every test that knows about the caps
drives the writer and the writer was never the thing that was wrong.

THE CLAIM HERE IS THE CAPS, NOT "a row the writer could emit". Those are
different, and the wider one is false of this file. 161 of its rows use compact JSON separators
that today's writer does not produce, because an earlier version of the hook
did. The total moves with every commit, so count both forms rather than quoting
a ratio:

    grep -c '{"ts":"'  cla.io/retro/commit-provenance.jsonl   # compact, legacy
    grep -c '{"ts": "' cla.io/retro/commit-provenance.jsonl   # spaced, current

That is also why a row can measure 1635 bytes on disk while the writer's own
serialisation of the same record measures 1657. A serialisation check would red immediately on legacy rows
and would be checking house style rather than an invariant anything depends on.

WHAT DOES DEPEND ON A CAP. `_already_recorded_fh` reads a fixed tail and parses
`lines[-1]` alone. The file always ends in a newline, so that last line is whole
whenever the window is at least one maximal row — which is what
`test_the_dedupe_window_clears_a_maximal_row` pins, and no more than that. The
partial row above it is discarded unparsed, so the window does NOT need room for
two. A row past the WINDOW (not past `_MAX_LINE_BYTES`) at the END of the file is
what breaks the dedupe: `json.loads` fails, the call returns False, and the next
commit is appended a second time. `_MAX_LINE_BYTES` at half the window is the
margin that keeps that from being reachable, and checking rows against it is
checking the margin rather than the failure.

BYTE COUNTS HERE INCLUDE THE LINE TERMINATOR, the way `main()` counts them: it
sheds against `json.dumps(record) + "\\n"`. A `\\r` is stripped before counting,
so a CRLF checkout reports the same number the writer budgeted against rather
than one more — which is the number the caps are about. The dedupe's own read is
of raw bytes, so a CRLF checkout does give it one extra byte per row; at the
margins this file runs, that is noise, and normalising to the writer's own
accounting is worth more than tracking a checkout setting.
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


def _dedupe_window_bytes() -> int:
    """The window `_already_recorded_fh` reads, taken from that function only.

    It is a literal rather than a named constant, so this matches the shape it
    appears in — the `size - N` of `fh.seek(max(0, size - N))` — rather than "a
    positive int somewhere in the function", which also catches the `-1` of
    `lines[-1]` and any index added later.
    """
    tree = ast.parse(_HOOK.read_text(encoding="utf-8"), filename=str(_HOOK))
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_already_recorded_fh":
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


def _rows() -> tuple[list[tuple[int, int, dict]], list[int]]:
    """`(lineno, bytes-with-terminator, record)` per row, plus unparsable linenos.

    SPLIT ON BYTES, like the writer and like `_already_recorded_fh`. `str`
    splitting also breaks on `\\x0b`, `\\x0c`, `\\x85`, `\\u2028` and `\\u2029`,
    which `json.dumps(..., ensure_ascii=False)` writes raw — so a trailer value
    carrying one of those would split a row in two here, and nowhere else, and
    shift every byte count with it.

    A LINE THAT DOES NOT PARSE IS SKIPPED AND TALLIED, not raised on, which is
    what `codify_aggregate.py` does with the same file and for the same reason:
    the producer can emit one. `_already_recorded`'s docstring says two processes
    appending can both write, and a torn line there must not red the repo's only
    gate with a bare `JSONDecodeError` naming neither the file nor the line.
    """
    raw = _LEDGER.read_bytes()
    rows: list[tuple[int, int, dict]] = []
    unparsable: list[int] = []
    for lineno, chunk in enumerate(raw.split(b"\n"), start=1):
        body = chunk.rstrip(b"\r")
        if not body.strip():
            continue
        try:
            rec = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            unparsable.append(lineno)
            continue
        if not isinstance(rec, dict):
            unparsable.append(lineno)
            continue
        rows.append((lineno, len(body) + 1, rec))
    return rows, unparsable


def _cap_violations(rows, maxt: int, maxc: int, maxb: int) -> list[str]:
    """One line per violated cap, per row. Empty means every row fits."""
    out: list[str] = []
    for lineno, nbytes, rec in rows:
        values = rec.get("measured_by", [])
        if len(values) > maxt:
            out.append(f"  line {lineno} ({rec.get('sha')}): {len(values)} values, "
                       f"_MAX_TRAILERS is {maxt}")
        long = [v for v in values if len(v) > maxc]
        if long:
            out.append(f"  line {lineno} ({rec.get('sha')}): {len(long)} value(s) past "
                       f"_MAX_TRAILER_CHARS ({maxc}), longest {max(len(v) for v in long)}")
        if nbytes > maxb:
            out.append(f"  line {lineno} ({rec.get('sha')}): {nbytes} bytes, "
                       f"_MAX_LINE_BYTES is {maxb}")
    return out


def test_the_ledger_is_there_and_has_rows_to_check():
    """Non-vacuity. The real-file check below iterates `_rows()`, so an absent or
    empty ledger would turn it green while checking nothing — and the ledger is
    opt-in by file presence, so absence is a real state, not a broken checkout."""
    assert _LEDGER.is_file(), f"no provenance ledger at {_LEDGER}"
    rows, unparsable = _rows()
    assert rows, "the ledger is empty; the cap check over it would be vacuous"
    assert any(r.get("measured_by") for _, _, r in rows), (
        "no row carries a `measured_by` value, so the per-value cap would be "
        "checked over nothing"
    )
    if unparsable:
        print(f"note: {len(unparsable)} unparsable line(s) skipped, at {unparsable}")


def test_no_row_exceeds_the_caps_the_writer_enforces():
    mod = _hook()
    rows, _ = _rows()
    offenders = _cap_violations(
        rows, mod._MAX_TRAILERS, mod._MAX_TRAILER_CHARS, mod._MAX_LINE_BYTES
    )
    assert not offenders, (
        "row(s) in the provenance ledger exceed a cap the writer enforces. "
        "Anything editing this file must apply `main()`'s shaping — the two "
        "caps and the shedding loop — not just `_measured_by()`'s return:\n"
        + "\n".join(offenders)
    )


@pytest.mark.parametrize("cap, row", [
    ("_MAX_TRAILERS", {"sha": "aaa1111", "measured_by": [c for c in "abcdefghijk"]}),
    ("_MAX_TRAILER_CHARS", {"sha": "bbb2222", "measured_by": ["x" * 161]}),
    ("_MAX_LINE_BYTES", {"sha": "ccc3333", "measured_by": ["x" * 100]}),
])
def test_each_cap_is_actually_checked(cap, row):
    """The discriminating half, and the reason it is written against synthetic
    rows rather than by mutating the ledger.

    In a correct tree no row violates any cap, so a comparison that is right and
    one that is merely satisfied both produce an empty list — the unkillable
    class CLAUDE.md names. The usual answer is to mutate the input, but the input
    here is a LIVE file the harness appends to on every commit, and a mutation
    run that snapshots and restores it destroys any row written meanwhile while
    reporting success. Feeding the checker a row it has never seen discriminates
    just as well and touches nothing.

    Each case violates exactly ONE cap: eleven one-character values, one
    161-character value, and a row whose line is long only because the byte
    budget passed in is tiny.
    """
    nbytes = len((json.dumps(row, ensure_ascii=False) + "\n").encode("utf-8"))
    # ONE BYTE OVER, not comfortably over. A budget the row clears by a wide
    # margin is satisfied by a loosened comparison too, so the case would stop
    # discriminating — measured: with a budget of 40 against a ~130-byte row, a
    # `> maxb * 2` mutant survived, because 130 is over 80 as well.
    maxb = nbytes - 1 if cap == "_MAX_LINE_BYTES" else 4096
    offenders = _cap_violations([(1, nbytes, row)], 10, 160, maxb)
    assert len(offenders) == 1, (
        f"the {cap} case should trip exactly one cap, got: {offenders}"
    )
    assert cap in offenders[0], f"tripped the wrong cap: {offenders[0]}"
    # The partner that makes the above mean something: the same row under the
    # real budgets, minus the one property under test, is NOT flagged.
    assert not _cap_violations([(1, 200, {"sha": "ddd4444", "measured_by": ["ok"]})],
                               10, 160, 4096)


def test_the_dedupe_window_clears_a_maximal_row():
    """`_already_recorded_fh` reads a fixed tail and parses only the LAST line.
    The file always ends in a newline, so that line is whole whenever the window
    holds one maximal row. It does NOT need room for the partial row above —
    that one is discarded unparsed — so this is the bound, and anything stricter
    would red the gate on a `_MAX_LINE_BYTES` change that breaks nothing."""
    mod = _hook()
    window = _dedupe_window_bytes()
    assert window >= mod._MAX_LINE_BYTES, (
        f"`_already_recorded_fh` reads a {window}-byte tail while a row may be "
        f"{mod._MAX_LINE_BYTES} bytes. A maximal row at the end of the file is "
        f"then truncated, `json.loads` fails, the dedupe reads 'not recorded', "
        f"and the next commit is appended a second time."
    )


def test_the_longest_row_on_disk_is_reported_against_both_bounds():
    """Not a bound of its own — it prints the live margin, so a run one long
    commit message away from the cap says so instead of passing silently until
    the row that trips it."""
    mod = _hook()
    rows, _ = _rows()
    lineno, nbytes, rec = max(rows, key=lambda r: r[1])
    print(
        f"longest row: line {lineno} ({rec.get('sha')}) at {nbytes} bytes — "
        f"{mod._MAX_LINE_BYTES - nbytes} under _MAX_LINE_BYTES, "
        f"{_dedupe_window_bytes() - nbytes} under the dedupe window"
    )
    assert nbytes <= mod._MAX_LINE_BYTES


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q", "-s"]))
