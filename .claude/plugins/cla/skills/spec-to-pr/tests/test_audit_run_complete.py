"""audit_run_complete.py tests.

Covers the pure `audit()` discipline check and the --finalize / --check-prior
marker round-trip. The retro dir is redirected via CLAUDE_RETRO_DIR so no real
`cla.io/retro/` is touched; the git-backed committed-check (shipped=True) is
exercised only through `audit()` directly, not through a real git tree.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

import audit_run_complete as arc

_GOOD_LINE = json.dumps({"change": "x", "phases": []})


# --- pure audit() --------------------------------------------------------


def test_audit_clean_run_no_gaps_when_line_present_and_committed():
    assert arc.audit(_GOOD_LINE, log_dirty=False, shipped=True) == {"ok": True, "gaps": []}


def test_audit_missing_log_line_is_a_gap():
    assert arc.audit(None, log_dirty=None, shipped=False)["gaps"] == ["run-log-missing"]
    assert arc.audit("   ", log_dirty=None, shipped=False)["gaps"] == ["run-log-missing"]


def test_audit_non_object_last_line_is_missing():
    # A JSON array (not an object) does not count as a valid run record.
    assert arc.audit("[1,2,3]", log_dirty=False, shipped=True)["gaps"] == ["run-log-missing"]


def test_audit_uncommitted_only_flagged_when_shipped():
    # Dirty ledger + shipped → uncommitted gap.
    assert arc.audit(_GOOD_LINE, log_dirty=True, shipped=True)["gaps"] == ["run-log-uncommitted"]
    # Dirty ledger but NOT shipped → intentional (Ship skipped); no gap.
    assert arc.audit(_GOOD_LINE, log_dirty=True, shipped=False) == {"ok": True, "gaps": []}


def test_audit_unknown_git_state_is_not_a_gap():
    # git couldn't be consulted (None) → can't claim uncommitted.
    assert arc.audit(_GOOD_LINE, log_dirty=None, shipped=True) == {"ok": True, "gaps": []}


def test_audit_both_gaps_accumulate():
    assert arc.audit(None, log_dirty=True, shipped=True)["gaps"] == [
        "run-log-missing",
        "run-log-uncommitted",
    ]


# --- --finalize / --check-prior via CLAUDE_RETRO_DIR ---------------------


@pytest.fixture
def retro(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("CLAUDE_RETRO_DIR", str(tmp_path))
    return tmp_path


def _marker(retro: Path) -> Path:
    return retro / arc.MARKER_NAME


def test_finalize_missing_log_writes_marker(retro: Path, capsys):
    # No ledger file at all, not shipped → run-log-missing gap → marker written.
    rc = arc.main(["--finalize", "--change", "my-change"])
    assert rc == 0
    assert "DISCIPLINE GAP" in capsys.readouterr().out
    marker = json.loads(_marker(retro).read_text(encoding="utf-8"))
    assert marker["change"] == "my-change"
    assert marker["gaps"] == ["run-log-missing"]


def test_finalize_clean_clears_stale_marker(retro: Path, capsys):
    # A stale marker exists...
    _marker(retro).write_text(json.dumps({"gaps": ["run-log-missing"]}) + "\n", encoding="utf-8")
    # ...and this run logged its line cleanly (not shipped, so committed-check skipped).
    (retro / arc.LOG_NAME).write_text(_GOOD_LINE + "\n", encoding="utf-8")
    rc = arc.main(["--finalize"])
    assert rc == 0
    assert "ok" in capsys.readouterr().out
    assert not _marker(retro).exists()


def test_check_prior_surfaces_and_clears_marker(retro: Path, capsys):
    _marker(retro).write_text(
        json.dumps({"source": "spec-to-pr Handoff", "change": "abc", "gaps": ["run-log-uncommitted"]}) + "\n",
        encoding="utf-8",
    )
    rc = arc.main(["--check-prior"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "PRIOR-RUN DISCIPLINE GAP (abc)" in out
    assert "uncommitted" in out
    assert not _marker(retro).exists()  # surfaced once, then cleared


def test_check_prior_silent_when_no_marker(retro: Path, capsys):
    rc = arc.main(["--check-prior"])
    assert rc == 0
    assert capsys.readouterr().out == ""


def test_finalize_then_check_prior_roundtrip(retro: Path, capsys):
    arc.main(["--finalize", "--change", "roundtrip"])  # no log → marker written
    capsys.readouterr()
    arc.main(["--check-prior"])
    out = capsys.readouterr().out
    assert "roundtrip" in out
    assert not _marker(retro).exists()


def test_check_prior_malformed_marker_degrades(retro: Path, capsys):
    # A corrupt (non-JSON) marker must degrade gracefully, not crash, and still clear.
    _marker(retro).write_text("not json at all\n", encoding="utf-8")
    rc = arc.main(["--check-prior"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "PRIOR-RUN DISCIPLINE GAP" in out and "unspecified gap" in out
    assert not _marker(retro).exists()


# --- git-backed committed-check against a REAL repo (closes the _log_dirty gap) ---


def test_log_dirty_against_real_repo(tmp_repo: Path):
    log = tmp_repo / arc.LOG_NAME
    log.write_text(_GOOD_LINE + "\n", encoding="utf-8")
    # Untracked ledger → git reports it dirty.
    assert arc._log_dirty(tmp_repo, log) is True
    # Committed ledger → clean.
    subprocess.run(["git", "add", str(log)], cwd=tmp_repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "add log"], cwd=tmp_repo, check=True)
    assert arc._log_dirty(tmp_repo, log) is False
    # No repo root → unknown (None), never a fabricated verdict.
    assert arc._log_dirty(None, log) is None


def test_finalize_shipped_end_to_end(tmp_repo: Path, monkeypatch: pytest.MonkeyPatch, capsys):
    # Drive --finalize --shipped through main() against a real git tree, so the
    # actual `git status` subprocess (not just the pure audit()) is exercised.
    monkeypatch.setenv("CLAUDE_RETRO_DIR", str(tmp_repo))
    monkeypatch.setattr(arc, "_repo_root", lambda: tmp_repo)
    log = tmp_repo / arc.LOG_NAME

    # Uncommitted ledger line + shipped → run-log-uncommitted gap + marker.
    log.write_text(_GOOD_LINE + "\n", encoding="utf-8")
    assert arc.main(["--finalize", "--shipped", "--change", "ship-x"]) == 0
    assert "DISCIPLINE GAP" in capsys.readouterr().out
    marker = json.loads((tmp_repo / arc.MARKER_NAME).read_text(encoding="utf-8"))
    assert marker["gaps"] == ["run-log-uncommitted"]

    # Commit the ledger → clean → ok, and the stale marker is cleared.
    subprocess.run(["git", "add", str(log)], cwd=tmp_repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "log"], cwd=tmp_repo, check=True)
    assert arc.main(["--finalize", "--shipped", "--change", "ship-x"]) == 0
    out = capsys.readouterr().out
    assert "ok" in out and "committed" in out
    assert not (tmp_repo / arc.MARKER_NAME).exists()


# --- resolver edge cases (mirroring test_log_run.py; the two _runs_dir are twins) ---


def test_runs_dir_rejects_relative_override(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("CLAUDE_RETRO_DIR", "relative/path")
    with pytest.raises(ValueError):
        arc._runs_dir()


def test_runs_dir_blank_override_falls_back(monkeypatch: pytest.MonkeyPatch):
    # Whitespace-only override is treated as unset → walk to the cla.io ancestor.
    monkeypatch.setenv("CLAUDE_RETRO_DIR", "   ")
    resolved = arc._runs_dir()
    assert resolved.name == "retro" and resolved.parent.name == "cla.io"


def test_runs_dir_default_without_override(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("CLAUDE_RETRO_DIR", raising=False)
    resolved = arc._runs_dir()
    assert resolved.name == "retro" and resolved.parent.name == "cla.io"


# --- CLI arg contract ----------------------------------------------------


def test_main_requires_a_mode():
    with pytest.raises(SystemExit):
        arc.main([])


def test_main_modes_are_mutually_exclusive():
    with pytest.raises(SystemExit):
        arc.main(["--finalize", "--check-prior"])
