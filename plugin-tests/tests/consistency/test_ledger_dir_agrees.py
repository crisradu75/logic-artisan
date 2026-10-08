"""The ledger writer and its reader must resolve the same directory.

`lib/log_run.py` writes a run record, and `spec_to_pr_aggregate.py` reads one
back with its own copy of the directory resolver. If the copy disagrees with the
writer, the reader finds nothing and reports zero records, which reads as a cold
start. So this runs the writer and the reader as programs, the way a skill does,
and checks the reader sees the record the writer just appended. Both run from a
subdirectory of the repo, so a resolver that used the working directory instead
of the git root would miss. The filename half of the contract is
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

# (reader script, ledger it reads, extra CLI args, key holding the record count)
_READERS = {
    "spec_to_pr_aggregate": (
        _PLUGIN / "skills" / "spec-to-pr-retro" / "scripts" / "spec_to_pr_aggregate.py",
        "spec-to-pr-runs.jsonl", (), "runs_analyzed",
    ),
}


# A record the writer accepts, for each ledger a reader here reads.
_RECORDS = {
    "spec-to-pr-runs.jsonl": {
        "ts": "2026-10-08T00:00:00Z", "change": "probe", "mode": "description",
        "phases": [{"name": "Propose", "status": "ok"}],
    },
}


def _run(script: Path, cwd: Path, env: dict, *args: str, stdin: str = "") -> str:
    proc = subprocess.run(
        [sys.executable, str(script), *args], input=stdin, cwd=cwd, env=env,
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30,
    )
    assert proc.returncode == 0, f"{script.name} failed: {proc.stderr}"
    return proc.stdout


@pytest.mark.parametrize("reader", sorted(_READERS))
@pytest.mark.parametrize("override", [False, True], ids=["git-root", "CLAUDE_RETRO_DIR"])
def test_the_reader_finds_what_the_writer_wrote(tmp_path, monkeypatch, override, reader):
    script, ledger, args, count_key = _READERS[reader]
    repo = tmp_path / "repo"
    sub = repo / "sub"
    sub.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    monkeypatch.delenv("CLAUDE_RETRO_DIR", raising=False)
    if override:
        monkeypatch.setenv("CLAUDE_RETRO_DIR", str(tmp_path / "elsewhere"))
    env = dict(os.environ)

    record = json.dumps(_RECORDS[ledger])
    written = Path(_run(_WRITER, sub, env, ledger, stdin=record).strip())
    expected = (tmp_path / "elsewhere") if override else (repo / "cla.io" / "retro")
    assert written.parent.resolve() == expected.resolve(), (
        f"the writer appended to {written}, not under {expected}"
    )

    result = json.loads(_run(script, sub, env, *args))
    assert result[count_key] == 1, (
        f"{script.name} looked at {result.get('log_paths') or result.get('ledgers')} "
        f"and found no record; the writer appended to {written}"
    )
