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
different, and the wider one is false of this file. 161 of its rows use compact
JSON separators that today's writer does not produce, because an earlier version
of the hook did. The total moves with every commit, so count both forms rather
than quoting a ratio:

    grep -c '{"ts":"'  cla.io/retro/commit-provenance.jsonl   # compact, legacy
    grep -c '{"ts": "' cla.io/retro/commit-provenance.jsonl   # spaced, current

That is also why a row can measure 1635 bytes on disk while the writer's own
serialisation of the same record measures 1657. A serialisation check would red
immediately on legacy rows and would be checking house style rather than an
invariant anything depends on.

WHAT DOES DEPEND ON A CAP. `_already_recorded_fh` seeks to the last N bytes and
parses `lines[-1]` alone; the partial row above it is discarded unparsed. So the
last line is whole exactly when the window is at least as large as one maximal
row AS IT SITS ON DISK — and those are two different numbers, which is the whole
of `test_the_dedupe_window_clears_a_maximal_row`. `_MAX_LINE_BYTES` budgets
`json.dumps(record) + "\\n"`, one byte of terminator, while a CRLF checkout
stores two. This repo has `core.autocrlf=true` and no `.gitattributes` rule for
`.jsonl` (`git check-attr text eol -- cla.io/retro/commit-provenance.jsonl`
answers `unspecified` for both), so a fresh Windows clone gets CRLF and every row
occupies one byte more than the cap budgeted. At `window == _MAX_LINE_BYTES` a
maximal row is then one byte short of fitting: `json.loads` fails, the dedupe
reads "not recorded", and a re-presented HEAD is appended twice. `_window_shortfall`
carries that byte, and `test_the_window_check_accounts_for_a_crlf_checkout` is
what stops it being dropped.

THERE IS NO SECOND MARGIN BEYOND THAT, and this file does not claim one. The
current values happen to sit at half the window, which is comfortable but is not
an invariant: nothing here would fail if `_MAX_LINE_BYTES` rose to 4095, and that
is deliberate — a guard asserting a margin nobody chose reds the gate on a
legitimate change.

BYTE COUNTS HERE INCLUDE THE LINE TERMINATOR, the way `main()` counts them, and
are normalised to its single `\\n` so they compare directly with
`_MAX_LINE_BYTES`. Where the on-disk size is what matters — the dedupe window —
the terminator width is passed in explicitly rather than assumed.
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

# The widest line terminator the ledger can be stored with. `\r\n` on a Windows
# checkout under `core.autocrlf=true`, which is this repo's setting and the case
# the window has to survive; a POSIX checkout stores one byte and has more room.
_WIDEST_TERMINATOR_BYTES = 2


def _hook():
    spec = importlib.util.spec_from_file_location("log_commit_provenance_guard", _HOOK)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _dedupe_window_bytes(source: str) -> int:
    """The window `_already_recorded_fh` reads, from that function only.

    Takes the SOURCE rather than reading the hook itself, so
    `test_the_window_is_read_out_of_the_hook_rather_than_assumed` can prove the
    extraction on a string whose literal is not 4096 — otherwise a version that
    ignored its input and returned a constant would pass identically.

    The window is a literal rather than a named constant, so this matches the
    shape it appears in — the `size - N` of `fh.seek(max(0, size - N))` — rather
    than "a positive int somewhere in the function", which also catches the `-1`
    of `lines[-1]` and any index added later.
    """
    tree = ast.parse(source)
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
    raise AssertionError("`_already_recorded_fh` not found in the hook source")


def _window_shortfall(window: int, max_line: int, terminator_bytes: int) -> int:
    """Bytes by which the dedupe window falls short of a maximal row on disk.

    `max_line` is `_MAX_LINE_BYTES`, which budgets the record plus ONE byte of
    terminator. On disk the terminator may be wider, so the row occupies
    `max_line - 1 + terminator_bytes`. Zero or less means the window holds a
    whole maximal row and `lines[-1]` always parses.
    """
    return (max_line - 1 + terminator_bytes) - window


def _rows(raw: bytes) -> tuple[list[tuple[int, int, dict]], list[int]]:
    """`(lineno, bytes-with-terminator, record)` per row, plus unparsable linenos.

    Takes the BYTES rather than reading the ledger, for the same reason
    `_dedupe_window_bytes` takes source: the callers that want the real file read
    it through `_ledger_rows()`, which fails with an actionable message when it
    is absent, and the discriminating tests can hand this synthetic input.

    SPLIT ON BYTES, like the writer and like `_already_recorded_fh`. `str`
    splitting also breaks on `\\x0b`, `\\x0c`, `\\x85`, `\\u2028` and `\\u2029`,
    which `json.dumps(..., ensure_ascii=False)` writes raw — so a trailer value
    carrying one of those would split a row in two here, and nowhere else, and
    shift every byte count with it.

    A LINE THAT DOES NOT PARSE IS SKIPPED AND TALLIED, not raised on, which is
    what `codify_aggregate.py` does with the same file and for the same reason:
    the producer can emit one. `_already_recorded`'s docstring says two processes
    appending can both write, and a torn line must not red the repo's only gate
    with a bare `JSONDecodeError` naming neither the file nor the line.

    Byte counts are normalised to one terminator byte, so they compare with
    `_MAX_LINE_BYTES` on a CRLF checkout as well as a POSIX one.
    """
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


def _ledger_rows() -> tuple[list[tuple[int, int, dict]], list[int]]:
    """The real file's rows, or an actionable failure.

    Every test that reads the ledger goes through here, so an absent or empty
    one fails the same way everywhere. It used to be checked in ONE test while
    two others read the file directly, which meant deleting the ledger — the
    documented way to turn the hook OFF, so a real state rather than a broken
    checkout — produced a bare `FileNotFoundError` from one and
    `ValueError: max() arg is an empty sequence` from another.
    """
    assert _LEDGER.is_file(), (
        f"no provenance ledger at {_LEDGER}. Its existence is the hook's opt-in, "
        f"so this is a legitimate state — but every check in this file is about "
        f"that file's contents, and there are none to check."
    )
    rows, unparsable = _rows(_LEDGER.read_bytes())
    assert rows, (
        f"{_LEDGER} holds no parsable row; every check in this file would be "
        f"vacuous. Unparsable lines: {unparsable or 'none'}"
    )
    return rows, unparsable


def _cap_violations(rows, maxt: int, maxc: int, maxb: int) -> list[str]:
    """One line per violated cap, per row. Empty means every row fits.

    A FIELD OF THE WRONG SHAPE IS REPORTED, NOT RAISED ON. `_rows()` takes care
    not to die on a torn line; dying instead on `"measured_by": null`, or on a
    list holding a number, would reintroduce exactly that failure one layer up —
    a bare `TypeError` naming neither the file nor the line. `codify_aggregate.py`
    reads the same rows and type-guards every field it touches
    (`_coerce_int`, `isinstance(skill, str)`), and its `coerced_fields` bucket is
    the precedent: producer drift is counted, not glossed and not fatal. A
    wrong-shaped field is also, on its own terms, a row the writer could not have
    written — so it belongs in this list rather than beside it.
    """
    out: list[str] = []
    for lineno, nbytes, rec in rows:
        where = f"  line {lineno} ({rec.get('sha')})"
        values = rec.get("measured_by", [])
        if not isinstance(values, list):
            out.append(f"{where}: `measured_by` is {type(values).__name__}, not a list")
            values = []
        elif not all(isinstance(v, str) for v in values):
            kinds = sorted({type(v).__name__ for v in values if not isinstance(v, str)})
            out.append(f"{where}: `measured_by` holds non-string value(s): {kinds}")
            values = [v for v in values if isinstance(v, str)]
        if len(values) > maxt:
            out.append(f"{where}: {len(values)} values, _MAX_TRAILERS is {maxt}")
        long = [v for v in values if len(v) > maxc]
        if long:
            out.append(f"{where}: {len(long)} value(s) past _MAX_TRAILER_CHARS "
                       f"({maxc}), longest {max(len(v) for v in long)}")
        if nbytes > maxb:
            out.append(f"{where}: {nbytes} bytes, _MAX_LINE_BYTES is {maxb}")
    return out


def test_the_ledger_is_there_and_has_rows_to_check():
    """Non-vacuity. The real-file check iterates `_ledger_rows()`, so an absent
    or empty ledger would turn it green while checking nothing."""
    rows, unparsable = _ledger_rows()
    assert any(r.get("measured_by") for _, _, r in rows), (
        "no row carries a `measured_by` value, so the per-value cap would be "
        "checked over nothing"
    )
    if unparsable:
        print(f"note: {len(unparsable)} unparsable line(s) skipped, at {unparsable}")


def test_no_row_exceeds_the_caps_the_writer_enforces():
    mod = _hook()
    rows, _ = _ledger_rows()
    offenders = _cap_violations(
        rows, mod._MAX_TRAILERS, mod._MAX_TRAILER_CHARS, mod._MAX_LINE_BYTES
    )
    assert not offenders, (
        "row(s) in the provenance ledger exceed a cap the writer enforces, or "
        "carry a field it could not have written. Anything editing this file "
        "must apply `main()`'s shaping — the two caps and the shedding loop — "
        "not just `_measured_by()`'s return:\n" + "\n".join(offenders)
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
    # The partner that makes the above mean something: a well-formed row under
    # the real budgets is NOT flagged.
    assert not _cap_violations([(1, 200, {"sha": "ddd4444", "measured_by": ["ok"]})],
                               10, 160, 4096)


@pytest.mark.parametrize("field, expected", [
    ({"sha": "eee5555", "measured_by": None}, "not a list"),
    ({"sha": "fff6666", "measured_by": "one string"}, "not a list"),
    ({"sha": "ggg7777", "measured_by": ["ok", 7]}, "non-string value"),
])
def test_a_wrong_shaped_field_is_reported_rather_than_raised_on(field, expected):
    """The type-guard partner. A hand edit writing `null`, a bare string, or a
    list holding a number parses as JSON and reaches the checker; reporting it
    keeps the failure actionable where a `len()` on it would be a bare
    `TypeError` naming neither the file nor the line."""
    offenders = _cap_violations([(1, 200, field)], 10, 160, 4096)
    assert offenders, "a wrong-shaped `measured_by` must be reported"
    assert expected in offenders[0], offenders[0]


def test_the_dedupe_window_clears_a_maximal_row():
    """`_already_recorded_fh` reads a fixed tail and parses only the LAST line,
    so the window must hold one maximal row AS STORED. It does not need room for
    the partial row above — that one is discarded unparsed — and nothing here
    asks for a margin beyond the one row."""
    mod = _hook()
    window = _dedupe_window_bytes(_HOOK.read_text(encoding="utf-8"))
    short = _window_shortfall(window, mod._MAX_LINE_BYTES, _WIDEST_TERMINATOR_BYTES)
    assert short <= 0, (
        f"`_already_recorded_fh` reads a {window}-byte tail while a maximal row "
        f"occupies {window + short} bytes on a CRLF checkout "
        f"(_MAX_LINE_BYTES {mod._MAX_LINE_BYTES} budgets one terminator byte, "
        f"the checkout stores {_WIDEST_TERMINATOR_BYTES}) — {short} byte(s) "
        f"short. The last line is then truncated, `json.loads` fails, the dedupe "
        f"reads 'not recorded', and a re-presented HEAD is appended twice."
    )


def test_the_window_check_accounts_for_a_crlf_checkout():
    """The byte that is easy to drop, pinned on its own.

    `_MAX_LINE_BYTES` budgets one terminator byte and a CRLF checkout stores two,
    so a window EQUAL to the cap is one byte short rather than exactly enough.
    Without this, `_window_shortfall` could assume `\\n` and the real check would
    still pass at today's values — and would bless a `_MAX_LINE_BYTES` of 4096
    against the 4096 window, which double-records on any Windows clone.
    """
    assert _window_shortfall(4096, 4096, 2) == 1, "CRLF: a maximal row is 4097 on disk"
    assert _window_shortfall(4096, 4096, 1) == 0, "LF: a maximal row fits exactly"
    assert _window_shortfall(4096, 4095, 2) == 0, "the largest CRLF-safe cap"
    assert _window_shortfall(4096, 2048, 2) < 0, "today's values, with room to spare"


def test_the_window_is_read_out_of_the_hook_rather_than_assumed():
    """That the extractor reads its input, proved on an input whose literal is
    not the real one — an implementation returning a constant passes the check
    above identically, and the two hook-mutating mutants that used to prove this
    were withdrawn: this repo loads the plugin from the working tree, so
    mutating the live hook lets a concurrent commit write a row the real writer
    would never have produced, which `mutate.py` cannot restore."""
    source = (
        "def _already_recorded_fh(fh, sha):\n"
        "    size = fh.tell()\n"
        "    fh.seek(max(0, size - 777))\n"
        "    return fh.read().splitlines()[-1]\n"
    )
    assert _dedupe_window_bytes(source) == 777
    # And that it reads the REAL hook without raising, which is the other half:
    # a wrong function name or a rewritten seek must refuse rather than guess.
    assert _dedupe_window_bytes(_HOOK.read_text(encoding="utf-8")) > 0


def test_the_longest_row_on_disk_is_reported_against_both_bounds():
    """Not a bound of its own — it prints the live margin, so a run one long
    commit message away from the cap says so instead of passing silently until
    the row that trips it."""
    mod = _hook()
    rows, _ = _ledger_rows()
    lineno, nbytes, rec = max(rows, key=lambda r: r[1])
    window = _dedupe_window_bytes(_HOOK.read_text(encoding="utf-8"))
    print(
        f"longest row: line {lineno} ({rec.get('sha')}) at {nbytes} bytes — "
        f"{mod._MAX_LINE_BYTES - nbytes} under _MAX_LINE_BYTES, "
        f"{window - (nbytes - 1 + _WIDEST_TERMINATOR_BYTES)} under the dedupe "
        f"window once a CRLF terminator is counted"
    )
    assert nbytes <= mod._MAX_LINE_BYTES


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q", "-s"]))
