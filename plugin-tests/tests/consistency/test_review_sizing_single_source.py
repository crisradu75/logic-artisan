"""The review-sizing table lives once, and the skills cite it.

`skills/_shared/references/model-routing.md` holds the one table that says which reviewers
a pull request gets, by risk. Every skill that reviews cites that section by name and carries
no row of its own, so the rows cannot drift. Round 2 runs only after a fixed Critical, and the
PR body carries one `Risk:` line. The orchestration cost rules live once in
`orchestration-economy.md`, and all three chain skills cite it.
"""

from __future__ import annotations

import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
_SKILLS = _ROOT / ".claude" / "plugins" / "cla" / "skills"
_ROUTING = _SKILLS / "_shared" / "references" / "model-routing.md"
_ECONOMY = _SKILLS / "_shared" / "references" / "orchestration-economy.md"
_REVISE = _SKILLS / "spec-to-pr" / "references" / "revise.md"
_SHIP = _SKILLS / "spec-to-pr" / "references" / "ship.md"
_S2P = _SKILLS / "spec-to-pr" / "SKILL.md"
_LITE_PR = _SKILLS / "lite-pr" / "SKILL.md"
_CHAINS = {
    "multi-lite": _SKILLS / "multi-lite" / "SKILL.md",
    "multi-pr": _SKILLS / "multi-pr" / "SKILL.md",
    "multi-spec": _SKILLS / "multi-spec" / "SKILL.md",
}
_SECTION = "Review sizing by risk"
_ECONOMY_POINTER = "skills/_shared/references/orchestration-economy.md"
_RISK_LINE = "Risk: <level> — <reason>; reviewers: <list>."
# A sizing-table row: a risk level in the first cell, then a reviewer name.
_TABLE_ROW = re.compile(r"^\|\s*(?:low risk|high risk)[^|]*\|[^|]*(?:code-reviewer|comment-analyzer|silent-failure-hunter)", re.I | re.M)
_OLD_ROUND_2 = re.compile(r"whenever round 1 committed fixes|runs after every fix commit", re.I)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _between(text: str, start: str, end: str) -> str:
    """The text from `start` to `end`; each must occur exactly once."""
    for marker in (start, end):
        assert text.count(marker) == 1, f"{marker!r} occurs {text.count(marker)} times"
    return text.split(start, 1)[1].split(end, 1)[0]


def _revise_stub() -> str:
    return _read(_S2P).split("### Revise — PR-review loop", 1)[1].split("\n### ", 1)[0]


def _flags_row() -> str:
    return next(line for line in _read(_S2P).splitlines() if line.startswith("| `--pr-rounds N`"))


# requirement: change-workflow / A change becomes a risk-reviewed pull request
def test_round_2_runs_only_after_a_fixed_critical() -> None:
    """The cap sentence, the Flags row, the Revise stub and the exit gate all name a
    fixed Critical as the one round-2 trigger. The old trigger, any round-1 fix commit, is gone."""
    revise = _read(_REVISE)
    cap = next(line for line in revise.splitlines() if line.startswith("Cap: `--pr-rounds N`"))
    assert "only after round 1 fixed a Critical" in cap
    gate = next(line for line in revise.splitlines() if "**Both 0**" in line)
    assert "unless this round fixed a Critical and the cap allows another round" in gate
    assert "only after round 1 fixed a Critical" in _flags_row()
    assert "only after round 1 fixed a Critical" in _revise_stub()
    for name, text in (("revise.md", revise), ("SKILL.md Flags row", _flags_row()), ("SKILL.md Revise stub", _revise_stub())):
        assert not _OLD_ROUND_2.search(text), f"{name} still says round 2 follows any fix commit"


# requirement: change-workflow / A change becomes a risk-reviewed pull request
def test_the_pr_body_carries_the_risk_line_on_one_line() -> None:
    """Ship's two `gh pr create` examples and the message-style table show the `Risk:` line.
    The line sits inside the one-line body, so no example may add a newline."""
    commands = [line for line in _read(_SHIP).splitlines() if line.startswith("gh pr create")]
    assert len(commands) == 2, f"ship.md holds {len(commands)} gh pr create examples, expected plain and stacked"
    for command in commands:
        assert _RISK_LINE in command, f"a gh pr create example lacks the Risk line: {command}"
        assert "\\n" not in command
    row = next(line for line in _read(_S2P).splitlines() if line.startswith("| PR body (Ship)"))
    assert _RISK_LINE in row
    assert "Risk: <level>" in _read(_LITE_PR)


def test_model_routing_holds_the_one_sizing_table() -> None:
    text = _read(_ROUTING)
    assert text.count(f"## {_SECTION}") == 1
    section = text.split(f"## {_SECTION}", 1)[1].split("\n## ", 1)[0]
    rows = _TABLE_ROW.findall(section)
    assert len(rows) == 3, f"the sizing section holds {len(rows)} reviewer rows, expected 3"
    assert "Unsure means high" in section
    assert "only after round 1 fixed a Critical" in section


def test_other_skills_cite_the_table_and_carry_no_row() -> None:
    """Each reviewing skill names the section; none holds a risk-level row of its own."""
    citing = {
        "spec-to-pr/SKILL.md": _S2P,
        "spec-to-pr/references/revise.md": _REVISE,
        "spec-to-pr/references/ship.md": _SHIP,
        "lite-pr/SKILL.md": _LITE_PR,
        **{f"{name}/SKILL.md": path for name, path in _CHAINS.items()},
    }
    for name, path in citing.items():
        text = _read(path)
        assert _SECTION in text, f"{name} does not cite the section {_SECTION!r}"
        assert not _TABLE_ROW.search(text), f"{name} carries a sizing-table row of its own"
    selection = _between(_read(_REVISE), "## Round 1 — agent selection + routing", "## Round 1 — Workflow fan-out")
    assert _SECTION in selection, "revise.md round 1 does not dispatch per the sizing section"
    assert "Risk:" in selection, "revise.md round 1 does not read the PR-body Risk line"


def test_the_row_scanner_is_not_vacuous() -> None:
    assert _TABLE_ROW.search("| Low risk, code | `code-reviewer` | Sonnet |")
    assert _TABLE_ROW.search("| High risk | `code-reviewer` + `silent-failure-hunter` | Opus |")
    assert not _TABLE_ROW.search("| logic / behavior code | `code-reviewer` | per the review-sizing table |")
    assert _OLD_ROUND_2.search("Round 2 runs whenever round 1 committed fixes")


def test_the_orchestration_rules_live_once_and_all_three_chains_cite_them() -> None:
    assert _ECONOMY.is_file()
    economy = _read(_ECONOMY)
    assert "git status --porcelain --ignored --untracked-files=all" in economy
    assert "explicit `model:`" in economy
    for name, path in _CHAINS.items():
        text = _read(path)
        assert _ECONOMY_POINTER in text, f"{name}/SKILL.md does not cite {_ECONOMY_POINTER}"
        assert "full suite once" not in text, f"{name}/SKILL.md copies a rule from {_ECONOMY.name}"
