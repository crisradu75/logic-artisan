"""The ledger writer and its reader must resolve the same directory.

`lib/log_run.py` writes a run record and `spec_to_pr_aggregate.py` reads it, each
with its own copy of the directory resolver. If the copies disagree the reader
finds nothing and reports `runs_analyzed: 0`, which reads as a cold start. So
this runs both as programs, the way a skill does, and checks the reader sees
the record the writer just appended. The filename half of the contract is
`test_ledger_names_agree.py`.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

_PLUGIN = Path(__file__).resolve().parents[3] / ".claude" / "plugins" / "cla"
_WRITER = _PLUGIN / "lib" / "log_run.py"
_READER = _PLUGIN / "skills" / "spec-to-pr-retro" / "scripts" / "spec_to_pr_aggregate.py"


def _run(script: Path, cwd: Path, env: dict, *args: str, stdin: str = "") -> str:
    proc = subprocess.run(
        [sys.executable, str(script), *args], input=stdin, cwd=cwd, env=env,
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30,
    )
    assert proc.returncode == 0, f"{script.name} failed: {proc.stderr}"
    return proc.stdout


@pytest.mark.parametrize("override", [False, True], ids=["git-root", "CLAUDE_RETRO_DIR"])
def test_the_reader_finds_what_the_writer_wrote(tmp_path, monkeypatch, override):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    monkeypatch.delenv("CLAUDE_RETRO_DIR", raising=False)
    if override:
        monkeypatch.setenv("CLAUDE_RETRO_DIR", str(tmp_path / "elsewhere"))
    env = dict(os.environ)

    record = json.dumps({"ts": "2026-10-08T00:00:00Z", "change": "probe"})
    written = Path(_run(_WRITER, repo, env, "spec-to-pr-runs.jsonl", stdin=record).strip())
    expected = (tmp_path / "elsewhere") if override else (repo / "cla.io" / "retro")
    assert written.parent.resolve() == expected.resolve()

    result = json.loads(_run(_READER, repo, env))
    assert result["runs_analyzed"] == 1, (
        f"the reader looked at {result.get('log_paths')} and found no record; the "
        f"writer appended to {written}"
    )
