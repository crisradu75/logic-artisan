"""Tests for the shared log_run.py — atomic JSONL append into a run ledger.

Ported from the two per-skill copies this replaced (spec-to-pr's and
codify-learnings's `tests/test_log_run.py`, which were themselves near-identical),
plus the cases the new `<ledger>` argument introduces. The ledger dir is
redirected to a tmp dir via CLAUDE_RETRO_DIR; the tests that must exercise the
NO-override path instead run inside a throwaway git repo (`scratch_repo`), so
no test touches a real ledger.
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
         args: list[str] | None = None, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    env = {**os.environ}
    if retro_dir is None:
        env.pop("CLAUDE_RETRO_DIR", None)
    else:
        env["CLAUDE_RETRO_DIR"] = str(retro_dir)
    # Refuse the one combination that writes into a REAL ledger: no usable
    # override AND no cwd, which sends `git rev-parse --show-toplevel` at
    # whatever repo the suite happens to run in — this one. Enforced here rather
    # than asserted per-test, because the per-test assertion is exactly what a
    # future edit drops without any test noticing (measured: that mutant
    # survived).
    if not (retro_dir is not None and str(retro_dir).strip()) and cwd is None:
        raise AssertionError(
            "_run without a usable CLAUDE_RETRO_DIR must pass cwd=<scratch repo>; "
            "otherwise the append lands in this repo's own cla.io/retro/"
        )
    argv = args if args is not None else ([ledger] if ledger is not None else [])
    return subprocess.run(
        [sys.executable, str(SCRIPT), *argv],
        input=stdin, capture_output=True, text=True, encoding="utf-8", errors="replace", env=env,
        cwd=None if cwd is None else str(cwd), check=False,
    )


@pytest.fixture
def scratch_repo(tmp_path: Path) -> Path:
    """A throwaway git repo to run the script INSIDE.

    Required by every test that exercises the no-override path: with
    CLAUDE_RETRO_DIR unset the script resolves its ledger dir from `git
    rev-parse --show-toplevel`, which inherits the child's cwd. Run from the
    default cwd, that is THIS repo — and two such tests duly appended a junk
    record to `cla.io/retro/spec-to-pr-runs.jsonl` on every suite run, six of
    which reached a commit before anyone noticed. The docstring above claimed
    no test touches a real ledger; it does now.
    """
    repo = tmp_path / "scratch-repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True, capture_output=True)
    return repo


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


def test_runs_dir_default_is_cla_io_retro(scratch_repo: Path) -> None:
    # With no override, the dir comes from `git rev-parse --show-toplevel` —
    # hence `cwd`, so the write lands in the scratch repo, not this one.
    r = _run('{"a":1}', None, cwd=scratch_repo)
    assert r.returncode == 0, r.stderr
    written = Path(r.stdout.strip())
    assert written.parent.as_posix().endswith("cla.io/retro")
    assert written.is_relative_to(scratch_repo), f"escaped the scratch repo: {written}"


def test_blank_override_is_treated_as_unset(scratch_repo: Path) -> None:
    r = _run('{"a":1}', Path("   "), cwd=scratch_repo)
    assert r.returncode == 0, r.stderr
    written = Path(r.stdout.strip())
    assert written.parent.as_posix().endswith("cla.io/retro")
    assert written.is_relative_to(scratch_repo), f"escaped the scratch repo: {written}"


def test_relative_override_is_rejected_loudly(tmp_path: Path) -> None:
    # Silently guessing would make logged runs vanish from the retro, which
    # resolves the same path independently.
    r = _run('{"a":1}', Path("relative/retro"))
    assert r.returncode == 1
    assert "absolute path" in r.stderr
