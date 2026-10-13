"""multi-pr wires the cite recheck into the change loop (GitHub #272).

The script only helps if the loop runs it against the right commit and hands its
results to the later change's review in a form that review can settle.
"""

from __future__ import annotations

from pathlib import Path

_MULTI_PR = Path(__file__).resolve().parents[4] / ".claude" / "plugins" / "cla" / "skills" / "multi-pr"


def _read(rel: str) -> str:
    return (_MULTI_PR / rel).read_text(encoding="utf-8")


def _step2() -> str:
    loop = _read("references/change-loop.md")
    return loop.split("2. **Capture a real start timestamp**", 1)[1].split("\n3. **Record the head", 1)[0]


def test_step_2_runs_the_script_against_the_chain_start_commit_and_fixes_in_place():
    step = _step2()
    assert "check_cite_drift.py --since <chain_start_sha> --ref origin/<base-branch> --fix openspec/changes/<name>" in step
    assert step.index("**Re-position HEAD first.**") < step.index("**Recheck cites, after re-positioning HEAD.**")


def test_a_gone_or_ambiguous_cite_becomes_an_inherits_entry_keyed_on_its_path():
    """Step 2b greps the token; a corrected cite drops the old line number, so a cite token
    would read NOT ADDRESSED after a correct fix."""
    step = _step2()
    assert "each `gone` or `ambiguous` row becomes one more `--inherits` entry" in step
    assert "The token is the cited file's path, not the cite" in step
    assert "plus the cites the recheck below hands on" in step


def test_a_check_that_cannot_run_is_recorded_and_never_rebased_on_today():
    step = _step2()
    assert "`cite drift unchecked: <its stderr>`" in step
    assert "Never substitute today's `origin/<base-branch>`" in step


def test_the_chain_start_commit_is_recorded_once_and_kept_on_resume():
    gate = _read("references/discover-and-gate.md")
    assert "a `## Chain start` line holding `git rev-parse origin/<base-branch>`" in gate
    assert "never records a new one" in gate


def test_skill_md_names_the_recheck():
    assert "scripts/check_cite_drift.py" in _read("SKILL.md")
