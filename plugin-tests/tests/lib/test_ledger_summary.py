"""Tests for ledger_summary.py — the generic reader for ledgers nothing else reads.

Five ledgers (`multi-lite`, `multi-pr`, `multi-spec`, `project-review`,
`right-model`) held 22 rows across the fleet with no reader at all, and three
frequently-used skills wrote nothing. Bespoke aggregators for each was the plan
nobody was ever going to execute; this derives the shape from the records instead.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

SCRIPT = (Path(__file__).resolve().parents[3] / ".claude" / "plugins" / "cla"
          / "lib" / "ledger_summary.py")


def _write(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8")


def _run(*args: str) -> tuple[int, dict | None, str]:
    r = subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True,
                       text=True, encoding="utf-8", errors="replace", check=False)
    out = json.loads(r.stdout) if r.returncode == 0 and r.stdout.strip() else None
    return r.returncode, out, r.stderr


def test_a_bool_field_is_a_true_false_split_not_a_mean(tmp_path: Path) -> None:
    """bool IS an int in Python, so the naive path reports `mean: 0.67` for a
    field whose only useful reading is 2 true, 1 false."""
    log = tmp_path / "l.jsonl"
    _write(log, [{"halted": True}, {"halted": True}, {"halted": False}])
    rc, out, _ = _run("--log", str(log))
    assert rc == 0
    assert out["fields"]["halted"] == {"present": 3, "null": 0, "true": 2, "false": 1}


def test_numbers_get_min_mean_max(tmp_path: Path) -> None:
    log = tmp_path / "l.jsonl"
    _write(log, [{"n": 2}, {"n": 4}, {"n": 9}])
    rc, out, _ = _run("--log", str(log))
    f = out["fields"]["n"]
    assert (f["min"], f["mean"], f["max"]) == (2, 5.0, 9)


def test_strings_get_a_frequency_table(tmp_path: Path) -> None:
    log = tmp_path / "l.jsonl"
    _write(log, [{"mode": "a"}, {"mode": "a"}, {"mode": "b"}])
    f = _run("--log", str(log))[1]["fields"]["mode"]
    assert f["distinct"] == 2
    assert f["top"] == {"a": 2, "b": 1}


def test_lists_get_length_stats(tmp_path: Path) -> None:
    log = tmp_path / "l.jsonl"
    _write(log, [{"items": [1, 2]}, {"items": []}, {"items": [1, 2, 3, 4]}])
    f = _run("--log", str(log))[1]["fields"]["items"]
    assert (f["min_len"], f["max_len"], f["empty"]) == (0, 4, 1)


def test_one_level_of_nesting_is_flattened_with_dotted_keys(tmp_path: Path) -> None:
    log = tmp_path / "l.jsonl"
    _write(log, [{"counts": {"failed": 0, "ok": 3}}])
    fields = _run("--log", str(log))[1]["fields"]
    assert "counts.failed" in fields and "counts.ok" in fields
    assert fields["counts.ok"]["max"] == 3


def test_deeper_nesting_is_named_as_a_shape_not_exploded(tmp_path: Path) -> None:
    """Full recursion on a real spec-to-pr record makes hundreds of
    single-observation keys and buries the ones anybody reads."""
    log = tmp_path / "l.jsonl"
    _write(log, [{"a": {"b": {"c": 1}}}])
    f = _run("--log", str(log))[1]["fields"]["a.b"]
    assert f["top"] == {"<dict>": 1}


def test_a_field_whose_type_changes_is_named_as_mixed(tmp_path: Path) -> None:
    """Mixed types are the producer-drift signal the specific readers spend real
    code detecting; silently picking one branch would hide it."""
    log = tmp_path / "l.jsonl"
    _write(log, [{"v": 1}, {"v": "one"}])
    assert _run("--log", str(log))[1]["fields"]["v"]["mixed_types"] == ["int", "str"]


def test_present_counts_the_records_carrying_the_field_not_the_window(
        tmp_path: Path) -> None:
    """A schema that grew mid-history leaves fields in a third of the rows, and a
    mean over those reads exactly like one over the whole ledger."""
    log = tmp_path / "l.jsonl"
    _write(log, [{"old": 1}, {"old": 1, "new": 5}, {"old": 1}])
    fields = _run("--log", str(log))[1]["fields"]
    assert fields["old"]["present"] == 3
    assert fields["new"]["present"] == 1
    assert _run("--log", str(log))[1]["records"] == 3


def test_nulls_are_counted_separately_from_values(tmp_path: Path) -> None:
    log = tmp_path / "l.jsonl"
    _write(log, [{"x": None}, {"x": 4}])
    f = _run("--log", str(log))[1]["fields"]["x"]
    assert (f["present"], f["null"], f["max"]) == (2, 1, 4)


def test_a_malformed_line_is_skipped_and_counted(tmp_path: Path) -> None:
    log = tmp_path / "l.jsonl"
    log.write_text('{"a": 1}\nnot json\n[1,2]\n', encoding="utf-8")
    rc, out, err = _run("--log", str(log))
    assert rc == 0
    assert out["records"] == 1
    assert out["skipped_records"] == 2
    assert "not an object" in err


def test_a_missing_ledger_is_reported_as_found_false(tmp_path: Path) -> None:
    """The same rule the aggregators follow: a path that resolved to nothing must
    stay visible, so a 1-repo result cannot read as a 2-repo one."""
    good = tmp_path / "good.jsonl"
    _write(good, [{"a": 1}])
    out = _run("--log", str(good), str(tmp_path / "gone.jsonl"))[1]
    assert [row["found"] for row in out["ledgers"]] == [True, False]
    assert out["records"] == 1


def test_a_duplicate_path_does_not_double_the_counts(tmp_path: Path) -> None:
    log = tmp_path / "l.jsonl"
    _write(log, [{"a": 1}])
    rc, out, err = _run("--log", str(log), str(log))
    assert out["records"] == 1
    assert "more than once" in err


def test_an_empty_ledger_returns_zero_rather_than_crashing(tmp_path: Path) -> None:
    log = tmp_path / "l.jsonl"
    log.write_text("", encoding="utf-8")
    rc, out, _ = _run("--log", str(log))
    assert rc == 0 and out["records"] == 0 and out["fields"] == {}


def test_fleet_requires_a_ledger_name(tmp_path: Path) -> None:
    """A repo root names a directory, not which ledger inside it to read."""
    fleet = tmp_path / "fleet.local.md"
    fleet.write_text(f"- {tmp_path}\n", encoding="utf-8")
    rc, _, err = _run("--fleet", str(fleet))
    assert rc == 1
    assert "--fleet needs --ledger" in err


def test_fleet_reads_the_named_ledger_under_every_root(tmp_path: Path) -> None:
    roots = []
    for name in ("a", "b"):
        root = tmp_path / name
        _write(root / "cla.io" / "retro" / "lite-pr-runs.jsonl", [{"mode": name}])
        roots.append(root)
    fleet = tmp_path / "fleet.local.md"
    fleet.write_text("".join(f"- {r}\n" for r in roots), encoding="utf-8")
    out = _run("--fleet", str(fleet), "--ledger", "lite-pr-runs.jsonl")[1]
    assert out["records"] == 2
    assert out["fields"]["mode"]["top"] == {"a": 1, "b": 1}


def test_fleet_and_log_are_mutually_exclusive(tmp_path: Path) -> None:
    log = tmp_path / "l.jsonl"
    _write(log, [{"a": 1}])
    rc, _, err = _run("--fleet", str(tmp_path / "f.md"), "--log", str(log))
    assert rc == 1 and "mutually exclusive" in err


def test_no_arguments_at_all_refuses(tmp_path: Path) -> None:
    rc, _, err = _run()
    assert rc == 1
    assert "give --log" in err


def test_fields_are_ordered_by_how_many_records_carry_them(tmp_path: Path) -> None:
    """A long tail of once-seen keys is usually drift; the field in every row is
    usually the one worth reading."""
    log = tmp_path / "l.jsonl"
    _write(log, [{"common": 1}, {"common": 1}, {"common": 1, "rare": 1}])
    assert list(_run("--log", str(log))[1]["fields"])[0] == "common"


def test_the_empty_result_still_carries_window(tmp_path: Path) -> None:
    """A key on every populated result and absent from the empty one makes a
    consumer's `.get(...)` read a value where it should read "nothing measured" —
    the skeleton bug `codify_aggregate` records about its own empty return."""
    log = tmp_path / "l.jsonl"
    log.write_text("", encoding="utf-8")
    out = _run("--log", str(log))[1]
    assert out["records"] == 0
    assert out["window"] == {"first_ts": None, "last_ts": None}
