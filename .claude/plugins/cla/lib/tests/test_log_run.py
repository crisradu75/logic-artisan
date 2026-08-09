"""Tests for the shared log_run.py — atomic JSONL append into a run ledger.

Ported from the two per-skill copies this replaced (spec-to-pr's and
codify-learnings's `tests/test_log_run.py`, which were themselves near-identical),
plus the cases the new `<ledger>` argument introduces. The ledger dir is
redirected to a tmp dir via CLAUDE_RETRO_DIR so no test touches a real ledger.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "log_run.py"

LEDGER = "spec-to-pr-runs.jsonl"


def _run(stdin: str, retro_dir: Path | None, ledger: str | None = LEDGER,
         args: list[str] | None = None) -> subprocess.CompletedProcess[str]:
    env = {**os.environ}
    if retro_dir is None:
        env.pop("CLAUDE_RETRO_DIR", None)
    else:
        env["CLAUDE_RETRO_DIR"] = str(retro_dir)
    argv = args if args is not None else ([ledger] if ledger is not None else [])
    return subprocess.run(
        [sys.executable, str(SCRIPT), *argv],
        input=stdin, capture_output=True, text=True, encoding="utf-8", errors="replace", env=env,
        check=False,
    )


# --------------------------------------------------------------------------- #
# Appending
# --------------------------------------------------------------------------- #

def test_appends_one_line_per_call(tmp_path: Path) -> None:
    retro = tmp_path / "retro"

    r1 = _run('{"change":"a","phases":[]}', retro)
    r2 = _run('{"change":"b","phases":[]}', retro)

    assert r1.returncode == 0, r1.stderr
    assert r2.returncode == 0, r2.stderr

    log_path = Path(r1.stdout.strip())
    assert log_path == retro / LEDGER
    lines = log_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["change"] == "a"
    assert json.loads(lines[1])["change"] == "b"


def test_two_ledgers_stay_separate(tmp_path: Path) -> None:
    # The whole point of the `<ledger>` argument: one writer, several ledgers.
    # If the argument were ignored, both records would land in one file.
    retro = tmp_path / "retro"
    _run('{"a":1}', retro, ledger="spec-to-pr-runs.jsonl")
    _run('{"b":2}', retro, ledger="codify-runs.jsonl")

    assert json.loads((retro / "spec-to-pr-runs.jsonl").read_text(encoding="utf-8")) == {"a": 1}
    assert json.loads((retro / "codify-runs.jsonl").read_text(encoding="utf-8")) == {"b": 2}


def test_creates_deeply_missing_parent_dirs(tmp_path: Path) -> None:
    retro = tmp_path / "nested" / "deep" / "retro"
    r = _run('{"change":"x","phases":[]}', retro)
    assert r.returncode == 0, r.stderr
    assert Path(r.stdout.strip()).exists()


def test_preserves_unicode(tmp_path: Path) -> None:
    retro = tmp_path / "retro"
    r = _run('{"note":"café — ✓"}', retro)
    assert r.returncode == 0, r.stderr
    written = Path(r.stdout.strip()).read_text(encoding="utf-8")
    assert "café — ✓" in written, "record must not be escaped to ASCII"


# --------------------------------------------------------------------------- #
# Rejected input
# --------------------------------------------------------------------------- #

def test_rejects_non_object_json(tmp_path: Path) -> None:
    r = _run('["not","an","object"]', tmp_path / "retro")
    assert r.returncode == 1
    assert "must be an object" in r.stderr


def test_rejects_malformed_json(tmp_path: Path) -> None:
    r = _run("{not json", tmp_path / "retro")
    assert r.returncode == 1
    assert "invalid JSON" in r.stderr


def test_rejects_oversize_record(tmp_path: Path) -> None:
    r = _run(json.dumps({"prose": "x" * 5000}), tmp_path / "retro")
    assert r.returncode == 1
    assert "4 KiB" in r.stderr


def test_nothing_is_written_when_the_record_is_rejected(tmp_path: Path) -> None:
    # A rejected record must not leave a partial line behind for the retro to
    # trip over — the ledger is append-only and nothing repairs it.
    retro = tmp_path / "retro"
    _run("{not json", retro)
    assert not (retro / LEDGER).exists()


# --------------------------------------------------------------------------- #
# The ledger argument
# --------------------------------------------------------------------------- #

def test_missing_ledger_argument_is_refused(tmp_path: Path) -> None:
    r = _run('{"a":1}', tmp_path / "retro", args=[])
    assert r.returncode == 1
    assert "usage" in r.stderr


def test_extra_arguments_are_refused(tmp_path: Path) -> None:
    r = _run('{"a":1}', tmp_path / "retro", args=[LEDGER, "extra.jsonl"])
    assert r.returncode == 1


@pytest.mark.parametrize("bad", [
    "../escape.jsonl",
    "sub/dir.jsonl",
    "sub\\dir.jsonl",
    "runs.txt",
    ".hidden.jsonl",
    "",
])
def test_a_ledger_name_that_is_not_a_bare_filename_is_refused(tmp_path: Path, bad: str) -> None:
    # The caller is a model assembling a command line, so a path-shaped argument
    # writing outside the ledger dir is a real shape, not a hypothetical one.
    r = _run('{"a":1}', tmp_path / "retro", ledger=bad)
    assert r.returncode == 1, f"{bad!r} was accepted"
    assert not (tmp_path / "escape.jsonl").exists()


# --------------------------------------------------------------------------- #
# Resolving the ledger dir
# --------------------------------------------------------------------------- #

def test_runs_dir_env_override(tmp_path: Path) -> None:
    retro = tmp_path / "elsewhere"
    r = _run('{"a":1}', retro)
    assert Path(r.stdout.strip()).parent == retro


def test_runs_dir_default_is_cla_io_retro(tmp_path: Path) -> None:
    # With no override, the dir comes from `git rev-parse --show-toplevel`.
    r = _run('{"a":1}', None)
    assert r.returncode == 0, r.stderr
    assert Path(r.stdout.strip()).parent.as_posix().endswith("cla.io/retro")


def test_blank_override_is_treated_as_unset(tmp_path: Path) -> None:
    r = _run('{"a":1}', Path("   "))
    assert r.returncode == 0, r.stderr
    assert Path(r.stdout.strip()).parent.as_posix().endswith("cla.io/retro")


def test_relative_override_is_rejected_loudly(tmp_path: Path) -> None:
    # Silently guessing would make logged runs vanish from the retro, which
    # resolves the same path independently.
    r = _run('{"a":1}', Path("relative/retro"))
    assert r.returncode == 1
    assert "absolute path" in r.stderr
