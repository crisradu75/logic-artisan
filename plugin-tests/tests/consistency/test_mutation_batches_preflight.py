"""Every mutation batch passes `mutate.py`'s preflight, checked by the PR gate.

WHY. A batch's anchors are exact text in the files it mutates, so any edit to
those files can leave a mutant pointing at text that no longer exists. Nothing
noticed until someone next ran the batch: on 2026-11-19, refactors had left 11
batches and 32 mutants failing preflight, and the gate was green throughout,
because the gate runs pytest and pytest never runs a batch. Mutation runs are
opt-in (CLAUDE.md), so "someone will run it soon" is not a check either.

WHAT EACH CASE DOES. It loads the batch the way `mutate.py`'s `main` does
(`load_batch` on the resolved path, with `plugin-tests` on `sys.path`, which is
`sys.path[0]` when `mutate.py` runs as a script), then calls `preflight` on its
`MUTANTS`. Preflight reports its problems by raising `SystemExit`; the case fails
with that message. Nothing is planted and nothing is written: preflight only
reads the target files, and the batch module is loaded with bytecode writing
off, so no `__pycache__` appears under `mutants/`.

PARALLEL-SAFE. `mutate.py` stays serial (CLAUDE.md), because it reads pytest's
exit code; this test calls only `load_batch` and `preflight`, which read, so it
runs under `-n 4 --dist loadfile` like any other.

A LEFTOVER `.mutate-backup` FAILS THE CASE; IT DOES NOT SKIP. Preflight refuses a
batch whose target has a `<file>.mutate-backup` beside it. Two things leave one:
a `mutate.py` run in flight on this tree, or a run that was killed before it
restored. In the first, other tests in this same run are reading mutated
source, which CLAUDE.md forbids ("never run `mutate.py` while a review agent
reads the same tree") and which makes the whole run's result worthless; in the
second, the source beside the backup may still hold the mutant. A skip would
turn either into a green gate. Failing with preflight's own message, which names
each backup and the `mv` that restores it, is the useful outcome.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_DEV = Path(__file__).resolve().parents[2]  # <repo>/plugin-tests
_MUTANTS_DIR = _DEV / "mutants"
_MUTATE = _DEV / "mutate.py"

# 74 batches when this test was added; the floor sits well under that so a
# deleted batch does not trip it, and far above zero so a moved directory or a
# broken glob does.
_MIN_BATCHES = 60


def _load_mutate():
    """`mutate.py` belongs to no package, so it is loaded by path, as
    `test_mutate.py` does."""
    spec = importlib.util.spec_from_file_location("_mutate_for_preflight", _MUTATE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


mutate = _load_mutate()

BATCHES = sorted(
    p for p in _MUTANTS_DIR.rglob("*.py") if "__pycache__" not in p.parts
)


def _preflight_problem(batch: Path, monkeypatch) -> str | None:
    """Preflight's refusal for `batch`, or None when it would run."""
    monkeypatch.setattr(sys, "dont_write_bytecode", True)
    monkeypatch.syspath_prepend(str(_DEV))
    try:
        mutate.preflight(mutate.load_batch(batch.resolve()))
    except SystemExit as exc:
        return str(exc)
    return None


def test_the_batch_set_is_not_vacuous():
    assert len(BATCHES) > _MIN_BATCHES, (
        f"found {len(BATCHES)} mutation batches under {_MUTANTS_DIR}, expected more "
        f"than {_MIN_BATCHES}: the glob or the directory moved, and the cases below "
        "check almost nothing"
    )


@pytest.mark.parametrize(
    "batch", BATCHES, ids=[p.relative_to(_MUTANTS_DIR).as_posix() for p in BATCHES]
)
def test_every_batch_passes_preflight(batch, monkeypatch):
    problem = _preflight_problem(batch, monkeypatch)
    if problem is not None:
        pytest.fail(
            f"{batch.relative_to(_DEV).as_posix()} fails mutate.py's preflight, so "
            f"`python3 plugin-tests/mutate.py` would refuse it:\n{problem}",
            pytrace=False,
        )


def _seed(tmp_path: Path, anchor: str) -> Path:
    """A one-mutant batch over a file in `tmp_path`, targeting a real path."""
    source = tmp_path / "subject.py"
    source.write_text("def verdict():\n    return 'ON'\n", encoding="utf-8")
    batch = tmp_path / "batch.py"
    batch.write_text(
        "from pathlib import Path\n"
        "HERE = Path(__file__).resolve().parent\n"
        "MUTANTS = [\n"
        f"    ('flip', HERE / 'subject.py', {anchor!r}, \"return 'OFF'\", [HERE]),\n"
        "]\n",
        encoding="utf-8",
    )
    return batch


def test_a_batch_with_a_missing_anchor_fails(tmp_path, monkeypatch):
    """The must-fail case: the helper every real case uses reports a stale anchor."""
    problem = _preflight_problem(_seed(tmp_path, "return 'GONE'"), monkeypatch)
    assert problem is not None and "anchor not found" in problem, problem


def test_a_seeded_batch_with_a_live_anchor_passes(tmp_path, monkeypatch):
    """The control for the case above: the same batch with a real anchor runs."""
    assert _preflight_problem(_seed(tmp_path, "return 'ON'"), monkeypatch) is None


def test_a_leftover_backup_fails_rather_than_skips(tmp_path, monkeypatch):
    """The docstring's decision, held: a `.mutate-backup` beside a target fails."""
    batch = _seed(tmp_path, "return 'ON'")
    (tmp_path / "subject.py.mutate-backup").write_bytes(b"")
    problem = _preflight_problem(batch, monkeypatch)
    assert problem is not None and "did not finish" in problem, problem
