"""Both chains merge through one shared file, and multi-pr has only one merge policy.

`multi-lite` and `multi-pr` used to carry their own merge steps. Only
`multi-lite`'s checked the PR's checks, the recorded head and
`--match-head-commit` before merging, so `multi-pr` could merge a head nobody had
reviewed or tested. The steps now live once, in
`skills/_shared/references/chain-merge.md`, and both chains point at it.

These tests keep that true: each chain's merge step names the shared file, no
chain file carries a merge command of its own, the shared merge command passes
the checked head, and `multi-pr`'s deleted `stacked` and `open all` policies stay
deleted.
"""

from __future__ import annotations

import re
from pathlib import Path

_SKILLS = Path(__file__).resolve().parents[3] / ".claude" / "plugins" / "cla" / "skills"
_SHARED = _SKILLS / "_shared" / "references" / "chain-merge.md"
_LITE = _SKILLS / "multi-lite"
_PR = _SKILLS / "multi-pr"
_LITE_LOOP = _LITE / "references" / "candidate-loop.md"
_PR_LOOP = _PR / "references" / "change-loop.md"
_POINTER = "skills/_shared/references/chain-merge.md"
# A real merge command, not prose naming one: the env prefix and the subcommand.
_MERGE_COMMAND = re.compile(r"ALLOW_PR_MERGE=1 gh pr merge\b")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _between(text: str, start: str, end: str) -> str:
    """The text from `start` to `end`; each must occur exactly once."""
    for marker in (start, end):
        assert text.count(marker) == 1, f"{marker!r} occurs {text.count(marker)} times"
    return text.split(start, 1)[1].split(end, 1)[0]


def _chain_files() -> list[Path]:
    files = sorted([*_LITE.rglob("*.md"), *_PR.rglob("*.md")])
    assert len(files) >= 9, f"found only {len(files)} chain files"
    return files


def test_both_chains_point_at_the_shared_file() -> None:
    assert _SHARED.is_file()
    for skill in (_LITE / "SKILL.md", _PR / "SKILL.md"):
        assert _POINTER in _read(skill), f"{skill.parent.name}/SKILL.md does not name {_POINTER}"
    step_8 = _between(_read(_LITE_LOOP), "**8b. Pre-merge checks", "Move to the next candidate")
    step_5 = _between(_read(_PR_LOOP), "5. **Merge", "6. **Capture a real end timestamp**")
    for name, step in (("multi-lite step 8b", step_8), ("multi-pr step 5", step_5)):
        assert _POINTER in step, f"{name} does not send the merge through {_POINTER}"
        assert '"Pre-merge checks" through "If `gh pr merge` exits non-zero"' in step, name


def test_the_merge_command_lives_only_in_the_shared_file() -> None:
    """A chain carrying its own copy of the merge command can drift off the checks."""
    own = [f"{p.relative_to(_SKILLS)}" for p in _chain_files() if _MERGE_COMMAND.search(_read(p))]
    assert not own, f"a chain file carries its own merge command: {own}"
    commands = _MERGE_COMMAND.findall(_read(_SHARED))
    assert len(commands) == 1, f"chain-merge.md holds {len(commands)} merge commands, expected one"


def test_the_merge_command_scanner_is_not_vacuous() -> None:
    assert _MERGE_COMMAND.search("ALLOW_PR_MERGE=1 gh pr merge 12 --squash")
    assert not _MERGE_COMMAND.search("ALLOW_PR_MERGE=1 alone, or `gh pr merge` named in prose")


# requirement: change-chains / An OpenSpec change chain merges only a later change's prerequisite, on the head it checked
def test_multi_pr_merges_only_the_checked_head() -> None:
    """The guards multi-pr adopted: the head is recorded when the PR opens, the
    checks read the remote checks and the head, and the merge passes that head."""
    shared = _read(_SHARED)
    command = next(line for line in shared.splitlines() if _MERGE_COMMAND.search(line))
    assert "--match-head-commit <head_sha>" in command
    checks = _between(shared, "## Pre-merge checks (every merge)", "## Merge, then confirm it landed")
    assert "gh pr checks <pr>" in checks
    assert "`headRefOid` must equal `head_sha`" in checks
    assert "the reason is `head moved`" in checks
    loop = _read(_PR_LOOP)
    step_3 = _between(loop, "3. **Record the head", "Two failure tiers")
    assert "`head_sha`" in step_3 and 'chain-merge.md` "Record the head"' in step_3
    step_1 = _between(loop, "1. **Resume check.**", "2. **Capture a real start timestamp**")
    assert "a moved head is never merged" in step_1


# requirement: change-chains / An OpenSpec change chain merges only a later change's prerequisite, on the head it checked
def test_multi_pr_halts_when_a_needed_merge_fails() -> None:
    step_5 = _between(_read(_PR_LOOP), "5. **Merge", "6. **Capture a real end timestamp**")
    halt = next(line for line in step_5.splitlines() if "**Any other reason, or a host refusal**" in line)
    assert "**Tier A halt**" in halt and "start no later change" in halt
    neither = next(line for line in step_5.splitlines() if "Neither edge" in line)
    assert "leave its PR open" in neither


def test_multi_pr_keeps_no_stacked_or_open_all_policy() -> None:
    """P7a deleted both. A leftover mention reads as a live option to the orchestrator."""
    leftovers = {
        f"{p.relative_to(_SKILLS)}": sorted({m.group(0).lower() for m in
                                             re.finditer(r"stacked|open all|open-all|5-alt|--pr-base", _read(p), re.I)})
        for p in sorted(_PR.rglob("*.md"))
    }
    leftovers = {k: v for k, v in leftovers.items() if v}
    assert not leftovers, f"multi-pr still names a deleted policy: {leftovers}"
    assert len(list(_PR.rglob("*.md"))) >= 4
