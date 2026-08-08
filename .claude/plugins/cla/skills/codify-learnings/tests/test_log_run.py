"""Tests for log_run.py — atomic JSONL append into the in-repo codify-runs ledger.

The ledger default is `<repo>/cla.io/retro/codify-runs.jsonl`; tests redirect
it to a tmp dir via the CLAUDE_RETRO_DIR override so they never touch the real
ledger.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "log_run.py"


def _run(stdin: str, retro_dir: Path) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "CLAUDE_RETRO_DIR": str(retro_dir)}
    return subprocess.run(
        [sys.executable, str(SCRIPT)],
        input=stdin, capture_output=True, text=True, encoding="utf-8", errors="replace", env=env,
        check=False,
    )


def test_appends_one_line_per_call(tmp_path: Path) -> None:
    retro = tmp_path / "retro"

    r1 = _run('{"ts":"2026-06-24","scope":"a"}', retro)
    r2 = _run('{"ts":"2026-06-25","scope":"b"}', retro)

    assert r1.returncode == 0, r1.stderr
    assert r2.returncode == 0, r2.stderr

    log_path = Path(r1.stdout.strip())
    assert log_path == retro / "codify-runs.jsonl"
    lines = log_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["scope"] == "a"
    assert json.loads(lines[1])["scope"] == "b"


def test_invalid_json_exits_1_and_writes_nothing(tmp_path: Path) -> None:
    retro = tmp_path / "retro"
    r = _run("not json", retro)
    assert r.returncode == 1
    assert "invalid JSON" in r.stderr
    assert not list(tmp_path.glob("**/codify-runs.jsonl"))


def test_non_object_top_level_rejected(tmp_path: Path) -> None:
    r = _run("[1, 2, 3]", tmp_path / "retro")
    assert r.returncode == 1
    assert "must be an object" in r.stderr


def test_prose_overflow_rejected(tmp_path: Path) -> None:
    big = json.dumps({"ts": "2026-06-24", "blob": "x" * 5000})
    r = _run(big, tmp_path / "retro")
    assert r.returncode == 1
    assert "exceeds 4 KiB" in r.stderr


def test_non_ascii_round_trips_utf8(tmp_path: Path) -> None:
    # ensure_ascii=False must persist UTF-8 bytes, not \uXXXX escapes.
    r = _run('{"ts":"2026-06-24","scope":"café"}', tmp_path / "retro")
    assert r.returncode == 0, r.stderr
    raw = Path(r.stdout.strip()).read_bytes()
    assert "café".encode("utf-8") in raw
    assert b"\\u00e9" not in raw


def _import_resolver():
    # Load by explicit path under a unique module name so the two skills'
    # identically-named `log_run.py` modules never collide in sys.modules.
    import importlib.util
    spec = importlib.util.spec_from_file_location("_ut_codify_log_run", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod._runs_dir


def test_runs_dir_env_override(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("CLAUDE_RETRO_DIR", str(tmp_path))
    assert _import_resolver()() == tmp_path


def test_runs_dir_default_is_claude_retro(monkeypatch) -> None:
    # With no override, the ledger resolves to the repo's `cla.io/retro/`.
    monkeypatch.delenv("CLAUDE_RETRO_DIR", raising=False)
    d = _import_resolver()()
    assert d.name == "retro"
    assert d.parent.name == "cla.io"


def test_runs_dir_blank_override_treated_as_unset(monkeypatch) -> None:
    # A whitespace-only override must NOT become a relative `Path(" ")` under CWD.
    monkeypatch.setenv("CLAUDE_RETRO_DIR", "   ")
    d = _import_resolver()()
    assert d.name == "retro" and d.parent.name == "cla.io"


def test_relative_override_rejected_loudly(tmp_path: Path) -> None:
    # End-to-end: a relative override must exit 1 with a clear stderr message,
    # not silently scatter a ledger under the CWD.
    r = _run('{"ts":"2026-06-24"}', Path("relative/dir"))
    assert r.returncode == 1
    assert "absolute path" in r.stderr
    assert not list(tmp_path.glob("**/codify-runs.jsonl"))
