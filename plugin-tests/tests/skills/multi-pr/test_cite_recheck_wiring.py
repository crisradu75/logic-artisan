"""multi-pr wires the cite recheck into the change loop (GitHub #272).

The script only helps if the loop runs it once, against the right commit, and
hands its results to the later change's review in a form that review can settle.
"""

from __future__ import annotations

import re
from pathlib import Path

_MULTI_PR = Path(__file__).resolve().parents[4] / ".claude" / "plugins" / "cla" / "skills" / "multi-pr"


def _read(rel: str) -> str:
    return (_MULTI_PR / rel).read_text(encoding="utf-8")


def _step(number: int) -> str:
    loop = _read("references/change-loop.md")
    heads = {2: "2. **Capture a real start timestamp**", 3: "3. **Record the head", 4: "4. **No-unresolved-issues"}
    return loop.split(heads[number], 1)[1].split("\n" + heads[number + 1], 1)[0]


def test_step_2_runs_the_script_against_the_chain_start_commit_after_re_positioning():
    step = _step(2)
    assert "check_cite_drift.py --since <sha> --ref origin/<base-branch> --fix openspec/changes/<name>" in step
    assert step.index("**Re-position HEAD first.**") < step.index("**Recheck cites, after re-positioning HEAD")


def test_the_recheck_never_runs_twice_on_one_change():
    """`--fix` leaves merged-tree numbers; a second run reads them as chain-start numbers."""
    step = _step(2)
    assert "**Never run it twice on one change.**" in step
    assert "reuse its rows for `--inherits` and do not run the script" in step
    loop = _read("references/change-loop.md")
    assert "never from a new run of the script" in loop.split("## Resume behavior", 1)[1]


def test_the_inherits_entry_has_no_semicolon_and_keys_on_the_path():
    """`<inherits>` splits on `;`: one inside the template turns each cite into two entries."""
    step = _step(2)
    template = re.search(r"one more `--inherits` entry: `([^`]+)`", step)
    assert template, "the entry template left step 2"
    assert ";" not in template.group(1)
    assert template.group(1).startswith("<path> — cite <cite> is <status>")
    assert "The token is the cited file's path" in step
    assert "plus the cites the recheck below hands on" in _read("references/change-loop.md")


def test_a_check_that_did_not_run_cleanly_is_recorded_and_never_rebased_on_today():
    step = _step(2)
    assert "**Exit 1 with no `gone` or `ambiguous` row, or exit 2:**" in step
    assert "`cite recheck: unchecked — no chain start`" in step
    assert "Never substitute today's `origin/<base-branch>`" in step


def test_step_3_confirms_each_handed_on_cite_is_gone():
    step = _step(3)
    assert "check_cite_drift.py --list <change-dir>" in step
    assert "still listed is a Tier B finding" in step


def test_the_chain_start_commit_is_keyed_by_change_and_kept_on_resume():
    gate = _read("references/discover-and-gate.md")
    assert "`<sha> — <change>, <change>, …`" in gate
    assert "a `## Chain start` line naming any change in this run" in gate
    assert "reuse that `<sha>` and write no new line" in gate


def test_skill_md_names_the_recheck():
    skill = _read("SKILL.md")
    assert "scripts/check_cite_drift.py" in skill
    assert "Never run the recheck twice on one change" in skill
