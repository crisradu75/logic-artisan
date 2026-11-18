"""The autonomy gate's no-pause default must defer to its own exceptions.

`spec-to-pr/SKILL.md` runs Propose to Handoff without pausing, except where the "Autonomy gate"
section lists an exception: `--gate-on-push` and `--interactive` pause before push and PR open, a
gate the user asked for on their own git state. A rewording of the default once said "no flag
authorizes the pause", which told the agent to ignore those flags (review of checklist item 4i).
"""
from __future__ import annotations

import re
from pathlib import Path

_SKILL = (Path(__file__).resolve().parents[4]
          / ".claude" / "plugins" / "cla" / "skills" / "spec-to-pr" / "SKILL.md")


def _gate_section() -> str:
    text = _SKILL.read_text(encoding="utf-8")
    match = re.search(r"^### Autonomy gate\n(.*?)(?=^#{2,3} )", text, re.S | re.M)
    assert match, "spec-to-pr/SKILL.md has no '### Autonomy gate' section"
    return match.group(1)


def test_the_pausing_flags_are_listed_as_exceptions():
    section = _gate_section()
    for flag in ("--gate-on-push", "--interactive"):
        assert flag in section, f"{flag} is not among the autonomy gate's exceptions"


def test_the_no_pause_default_defers_to_the_exceptions():
    default = _gate_section().strip().split("\n\n")[0]
    assert "exceptions" in default, "the no-pause default does not point at its exceptions"
    assert not re.search(r"\bno flag\b", default, re.I), (
        "the no-pause default denies that any flag pauses the run, but "
        "--gate-on-push and --interactive do")
