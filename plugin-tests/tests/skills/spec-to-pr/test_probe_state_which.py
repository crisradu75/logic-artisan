"""probe_state._run resolves the executable with shutil.which (issue #407).

Monkeypatched, so it passes on every platform: the Windows bug is that a bare
`openspec` cannot launch an npm `.cmd` shim, and `shutil.which` is what applies PATHEXT.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

import probe_state

SHIM = r"C:\Users\someone\AppData\Roaming\npm\openspec.CMD"


@pytest.fixture(autouse=True)
def _clean_state() -> None:
    probe_state._missing_tools.clear()
    probe_state._environment_errors.clear()
    yield
    probe_state._missing_tools.clear()
    probe_state._environment_errors.clear()


def test_run_passes_which_result_as_argv0(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[list[str]] = []

    def fake_run(argv, **kwargs):
        seen.append(list(argv))
        return subprocess.CompletedProcess(argv, 0, "{}", "")

    monkeypatch.setattr(probe_state.shutil, "which", lambda name: SHIM if name == "openspec" else None)
    monkeypatch.setattr(probe_state.subprocess, "run", fake_run)

    res = probe_state._run(["openspec", "status", "--json"], cwd=tmp_path)

    assert res.returncode == 0
    assert seen == [[SHIM, "status", "--json"]]
    assert probe_state._missing_tools == []


def test_genuinely_missing_tool_is_still_reported(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(argv, **kwargs):
        raise FileNotFoundError(2, "not found", argv[0])

    monkeypatch.setattr(probe_state.shutil, "which", lambda name: None)
    monkeypatch.setattr(probe_state.subprocess, "run", fake_run)

    res = probe_state._run(["no-such-tool-xyz", "x"], cwd=tmp_path)

    assert res.returncode == probe_state._TOOL_MISSING_RC
    assert probe_state._missing_tools == ["no-such-tool-xyz"]
