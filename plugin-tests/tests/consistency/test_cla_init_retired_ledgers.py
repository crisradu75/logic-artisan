"""cla-init lists the retired run ledgers a repo still holds, and deletes nothing itself.

A ledger is retired when no skill writes it and nothing reads it. Repos onboarded
earlier still hold the files, and no install removes them, so `cla-init` item 7
carries the list and prints the ones present; the deletion the user may then agree
to is the model's own `rm` and is not run here.

The list is pinned two ways: it holds exactly the names the retirement decided,
and it never names a ledger `lib/log_run.py` still accepts — offering to delete a
live ledger would destroy run history on a careless yes.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

import log_run

_REPO = Path(__file__).resolve().parents[3]
_SKILL = _REPO / ".claude" / "plugins" / "cla" / "skills" / "cla-init" / "SKILL.md"
_BASH = shutil.which("bash")

RETIRED = ("codify-runs", "commit-provenance", "right-model-runs", "multi-pr-runs", "multi-spec-runs",
           "multi-lite-runs", "project-review-runs", "lite-pr-runs", "shape-decision-runs",
           "feedback-runs")


def _script() -> str:
    text = _SKILL.read_text(encoding="utf-8")
    match = re.search(r"```bash\n(: \"\$\{ROOT:\?[^`]*?retired ledger: [^`]*?)```", text)
    assert match, "cla-init/SKILL.md: no retired-ledger block found"
    return match.group(1)


def _listed() -> tuple[str, ...]:
    match = re.search(r"for f in (.*?); do", _script(), re.DOTALL)
    assert match, "the retired-ledger block has no `for f in ...; do` list"
    return tuple(match.group(1).replace("\\\n", " ").split())


def _run(root: Path) -> list[str]:
    out = subprocess.run(
        [_BASH, "-c", _script()],
        # Forward slashes: a POSIX shell reads `C:\...` backslashes as escapes.
        env={**os.environ, "ROOT": str(root).replace("\\", "/")},
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30,
    )
    assert out.returncode == 0, out.stderr
    return out.stdout.splitlines()


_needs_bash = pytest.mark.skipif(_BASH is None, reason="bash is not installed")


# requirement: repo-context / Reporting retired ledgers
def test_the_list_is_the_retired_ledgers_and_no_live_one() -> None:
    live = {name.removesuffix(".jsonl") for name in log_run.SHAPES}
    assert not live & set(_listed()), "cla-init offers to delete a ledger log_run.py still writes"
    assert _listed() == RETIRED


# requirement: repo-context / Reporting retired ledgers
@_needs_bash
def test_only_the_retired_ledgers_present_are_listed_and_none_is_deleted(tmp_path: Path) -> None:
    retro = tmp_path / "cla.io" / "retro"
    retro.mkdir(parents=True)
    present = ["spec-to-pr-runs.jsonl", "codify-runs.jsonl", "lite-pr-runs.jsonl",
               "commit-provenance.jsonl", "multi-lite-run-notes-2026-10-08.md",
               "lite-pr-runs.jsonl.bak", "other-runs.jsonl"]
    for name in present:
        (retro / name).write_text('{"a": 1}\n', encoding="utf-8")
    # In the list's order, not the directory's.
    assert _run(tmp_path) == ["retired ledger: cla.io/retro/codify-runs.jsonl",
                              "retired ledger: cla.io/retro/commit-provenance.jsonl",
                              "retired ledger: cla.io/retro/lite-pr-runs.jsonl"]
    assert sorted(p.name for p in retro.iterdir()) == sorted(present)


# requirement: repo-context / Reporting retired ledgers
@_needs_bash
def test_nothing_is_listed_when_none_is_present(tmp_path: Path) -> None:
    assert _run(tmp_path) == []  # no cla.io/retro/ at all
    retro = tmp_path / "cla.io" / "retro"
    retro.mkdir(parents=True)
    (retro / "spec-to-pr-runs.jsonl").write_text("", encoding="utf-8")
    assert _run(tmp_path) == []
