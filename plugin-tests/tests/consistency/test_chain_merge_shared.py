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

_ROOT = Path(__file__).resolve().parents[3]
_SKILLS = _ROOT / ".claude" / "plugins" / "cla" / "skills"
_README = _ROOT / ".claude" / "plugins" / "cla" / "README.md"
_GUIDE = _ROOT / "DEVELOPER-GUIDE.md"
_SHARED = _SKILLS / "_shared" / "references" / "chain-merge.md"
_LITE = _SKILLS / "multi-lite"
_PR = _SKILLS / "multi-pr"
_LITE_LOOP = _LITE / "references" / "candidate-loop.md"
_PR_LOOP = _PR / "references" / "change-loop.md"
_POINTER = "skills/_shared/references/chain-merge.md"
# Words naming a deleted multi-pr policy. `stack(ed|ing)` but not the hook's own
# name, `warn-stacked-pr-merge`, which the scan strips first.
_DELETED_POLICY = re.compile(r"stack(?:ed|ing)|open all|open-all|5-alt|--pr-base", re.I)
_HOOK_NAME = "warn-stacked-pr-merge"
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
    assert "neither is one with no recorded `head_sha`" in step_1
    # A resumed, not-yet-archived change compares its head before spec-to-pr runs again.
    assert "`head moved since review`" in step_1


# requirement: change-chains / An OpenSpec change chain merges only a later change's prerequisite, on the head it checked
def test_multi_pr_step_4_checks_its_commit_and_records_the_head() -> None:
    """A fix multi-pr commits, and a spec-to-pr re-run, both move the head. Step 4
    must prove the commit and record the head again, or the merge refuses it."""
    step_4 = _between(_read(_PR_LOOP), "4. **No-unresolved-issues enforcement", "4a. **Record the obligations")
    assert 'chain-merge.md` "Record the head"' in step_4
    assert "which make it the new `head_sha`" in step_4
    failed = next(line for line in step_4.splitlines() if "A failed check leaves the finding unresolved" in line)
    assert "`fix not committed`" in failed and "`push not verified`" in failed
    assert "Tier A halt" in failed and "left open" in failed
    step_3 = _between(_read(_PR_LOOP), "3. **Record the head", "4. **No-unresolved-issues enforcement")
    assert "Record the head again after every later `/cla:spec-to-pr` call" in step_3
    shared = _between(_read(_SHARED), "## Record the head", "## Pre-merge checks (every merge)")
    assert "Whenever the skill the chain runs hands back an open PR" in shared


# requirement: change-chains / Running a batch of OpenSpec changes in dependency order
def test_a_multi_pr_resume_merges_only_an_enforced_change() -> None:
    """A session that died between step 3 and step 4b recorded a head but never
    fixed its findings. A resume must not merge that head."""
    loop = _read(_PR_LOOP)
    step_1 = _between(loop, "1. **Resume check.**", "2. **Capture a real start timestamp**")
    assert "**but only when its row's `status` is `enforced`**" in step_1
    assert "**Never infer them fixed.**" in step_1
    assert "The reason is `findings lost on resume`: a change a later one needs merged is a Tier A halt" in step_1
    step_4b = _between(loop, "4b. **Validate the live spec set", "5. **Merge")
    assert "**Passing → write `status: enforced` to this change's row.**" in step_4b
    assert "`enforced` (step 4b passed)" in _read(_PR / "SKILL.md")


# requirement: change-chains / An OpenSpec change chain merges only a later change's prerequisite, on the head it checked
def test_multi_pr_halts_when_a_needed_merge_fails() -> None:
    step_5 = _between(_read(_PR_LOOP), "5. **Merge", "6. **Capture a real end timestamp**")
    halt = next(line for line in step_5.splitlines() if "**Any other reason, or a host refusal**" in line)
    assert "**Tier A halt**" in halt and "start no later change" in halt
    neither = next(line for line in step_5.splitlines() if "Neither edge" in line)
    assert "leave its PR open" in neither


def _deleted_policy_words(text: str) -> list[str]:
    return sorted({m.group(0).lower() for m in _DELETED_POLICY.finditer(text.replace(_HOOK_NAME, ""))})


def test_multi_pr_keeps_no_stacked_or_open_all_policy() -> None:
    """P7a deleted both. A leftover mention reads as a live option to the
    orchestrator, or as a promise to the user in the README or the guide."""
    texts = {f"{p.relative_to(_SKILLS)}": _read(p) for p in sorted(_PR.rglob("*.md"))}
    assert len(texts) >= 4
    texts["README.md"] = _read(_README)
    texts["DEVELOPER-GUIDE.md §6"] = _between(_read(_GUIDE), "## 6. Batches:", "## 7. Parallel and safe:")
    leftovers = {name: words for name, text in texts.items() if (words := _deleted_policy_words(text))}
    assert not leftovers, f"multi-pr still names a deleted policy: {leftovers}"


def test_the_deleted_policy_scanner_is_not_vacuous() -> None:
    assert _deleted_policy_words("or stacking PRs on their parents") == ["stacking"]
    assert _deleted_policy_words("under `multi-pr`'s stacked policy") == ["stacked"]
    assert _deleted_policy_words("`warn-stacked-pr-merge` warns") == []


def test_the_shared_file_keeps_the_rules_the_move_dropped() -> None:
    """Rules each chain carried before the move, which a review found missing."""
    shared = _read(_SHARED)
    bootstrap = _between(shared, "## Bootstrap (once, before the chain starts)", "**Primary clone by default.**")
    assert "A failed pull halts" in bootstrap
    landed = _between(shared, "## Merge, then confirm it landed", "## A fix needed after a merge")
    assert "**a pull that fails there halts the run**" in landed
    assert "confirm `git log --oneline -1` shows `merge_commit`" in landed
    assert "`ALLOW_PR_MERGE=1` does not cover `branch -D`" in landed
    checks = _between(shared, "## Pre-merge checks (every merge)", "## Merge, then confirm it landed")
    behind = next(line for line in checks.splitlines() if "`BEHIND` → proceed" in line)
    assert "reports `BLOCKED` instead" in behind and "the skill's final report" in behind
    assert "runs it again on the resolved tree" in checks
    dirty = next(line for line in checks.splitlines() if "`DIRTY` →" in line)
    assert "Never rebase or force-push" in dirty


def test_multi_pr_reports_every_note_and_open_reason() -> None:
    report = _read(_PR / "references" / "cleanup.md").split("\n5. ", 1)[1]
    for note in ("`behind base: merged tree not tested`", "`gate skipped: no source-affecting paths`",
                 "`base not updated`", "`queued: merges later outside this run`",
                 "`conflicts resolved, not re-reviewed`", "`findings lost on resume`", "**Left open**"):
        assert note in report, f"cleanup step 5 does not report {note}"
    conflicts = next(line for line in _read(_PR_LOOP).splitlines() if "**The reason is `conflicts`**" in line)
    assert "gated but not re-reviewed" in conflicts and "`conflicts resolved, not re-reviewed`" in conflicts
    row = "`change | branch | pr_number | head_sha | status | merge_commit | notes`"
    assert row in _read(_PR / "SKILL.md")


def test_landing_a_hand_built_stack_lives_in_spec_to_pr() -> None:
    refs = _SKILLS / "spec-to-pr" / "references"
    landing = _read(refs / "branch-and-pr-base.md").split("## Landing a stack", 1)[1]
    assert "`gh pr edit <child> --base <base-branch>` — retarget the child FIRST" in landing
    assert "GitHub CLOSED the dependent PR" in landing
    assert "`git rebase --onto origin/<base-branch> <parent-tip-sha> <child-branch>`" in landing
    assert "`git push --force-with-lease`" in landing
    assert '`branch-and-pr-base.md`, "Landing a stack"' in _read(refs / "handoff.md")
