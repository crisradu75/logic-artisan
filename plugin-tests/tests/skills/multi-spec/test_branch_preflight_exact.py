"""multi-spec's Phase 2 finds an existing `docs/propose-<slug>` branch by its exact name.

`git ls-remote --heads origin <name>` lists every branch whose name ENDS in `<name>`, so a longer
branch such as `old/docs/propose-x` read as "exists" and the run resumed onto the wrong branch.
Phase 2 asks `ship_check.py preflight`, which compares exact ref names (its own tests, in
`_shared/test_ship_check.py`, hold that), instead of a pattern match.
"""

from __future__ import annotations

import re
from pathlib import Path

_PHASES = (Path(__file__).resolve().parents[4]
           / ".claude" / "plugins" / "cla" / "skills" / "multi-spec" / "references" / "phases.md")


def _step_2() -> str:
    text = _PHASES.read_text(encoding="utf-8")
    match = re.search(r"^## Phase 2 .*?^2\. (.*?)$", text, re.S | re.M)
    assert match, "phases.md: no step 2 under Phase 2"
    return match.group(1)


def test_phase_2_asks_ship_check_for_the_branch():
    step = _step_2()
    assert "ship_check.py\" preflight --branch docs/propose-<batch-slug> --base <base-branch>" in step
    for code in ("Exit 0", "Exit 1", "Exit 2"):
        assert code in step, f"phase 2 step 2 does not say what {code} means"


def test_phase_2_no_longer_pattern_matches_the_remote():
    assert "ls-remote --exit-code --heads" not in _PHASES.read_text(encoding="utf-8")
