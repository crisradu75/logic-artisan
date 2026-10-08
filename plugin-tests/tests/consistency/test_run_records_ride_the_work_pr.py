"""Run records and chain run notes are committed on a work PR's branch, never on the base branch.

spec-to-pr commits its ledger line onto the feature branch it opened; multi-lite and
multi-pr commit their run notes onto the chain's last open PR, and leave them
uncommitted, saying so, when no PR is open. Each recipe is prose a model follows,
so these read the recipe: the commit is preceded by a checkout of the PR branch,
nothing in it checks out or pushes the base branch, and the direct-push escape
hatch is named only to forbid it.

The re-run half is checked too: multi-lite records each PR's head, and its own
notes commit moves that head, so the arm that forgives a notes-only move must sit
before the arm that stops a moved head.
"""

from __future__ import annotations

import re
from pathlib import Path

_SKILLS = Path(__file__).resolve().parents[3] / ".claude" / "plugins" / "cla" / "skills"
_HANDOFF = _SKILLS / "spec-to-pr" / "references" / "handoff.md"
_LITE_PHASE4 = _SKILLS / "multi-lite" / "references" / "phase4-and-log.md"
_LITE_BOOT = _SKILLS / "multi-lite" / "references" / "bootstrap-and-tracking.md"
_LITE_LOOP = _SKILLS / "multi-lite" / "references" / "candidate-loop.md"
_PR_CLEANUP = _SKILLS / "multi-pr" / "references" / "cleanup.md"
_PR_LOOP = _SKILLS / "multi-pr" / "references" / "change-loop.md"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _between(text: str, start: str, end: str | None) -> str:
    i = text.index(start)
    j = text.index(end, i) if end else len(text)
    return text[i:j]


def _commits_on_the_pr_branch(recipe: str, notes_glob: str, message: str) -> None:
    checkout = recipe.index("git checkout <branch>")
    add = recipe.index(f"git add -- {notes_glob}")
    commit = recipe.index(f'git commit -m "{message}"')
    push = recipe.index("git push", commit)
    assert checkout < add < commit < push
    assert "--expect-branch <branch>" in recipe[checkout:add]
    assert "git checkout <base-branch>" not in recipe
    assert "<base-branch>" not in re.sub(r"never `<base-branch>`|Never commit or push the notes to `<base-branch>`",
                                         "", recipe)


# requirement: run-ledgers / Run records ride the work's pull request
def test_spec_to_pr_commits_its_record_on_the_feature_branch_only() -> None:
    step_6 = _between(_read(_HANDOFF), "## 6. Commit the run-log line", "Steps 5 and 6")
    assert "--expect-branch <branch>" in step_6
    assert "git add -- cla.io/retro/spec-to-pr-runs.jsonl" in step_6
    assert "Do this ONLY when Ship opened a PR" in step_6


# requirement: run-ledgers / Run records ride the work's pull request
def test_multi_lite_commits_its_notes_on_the_last_open_pr() -> None:
    recipe = _between(_read(_LITE_PHASE4), "## Commit the run-notes file", None)
    _commits_on_the_pr_branch(recipe, "cla.io/retro/multi-lite-run-notes-*.md",
                              "chore: multi-lite run notes")
    assert "**None is open**" in recipe and "leave the file uncommitted and say so" in recipe
    assert "`ALLOW_PUSH_TO_MAIN=1`" in recipe and "Never commit or push" in recipe


# requirement: run-ledgers / Run records ride the work's pull request
def test_multi_pr_commits_its_notes_on_the_last_open_pr() -> None:
    step_5 = _between(_read(_PR_CLEANUP), "5. **Commit the running notes", "Mark the")
    _commits_on_the_pr_branch(step_5, "cla.io/retro/multi-pr-run-notes-*.md",
                              "chore: multi-pr run notes")
    assert "leave the notes uncommitted and say so" in step_5


def test_a_rerun_takes_committed_notes_back_out_before_it_needs_them() -> None:
    # A file tracked only on the PR branch vanishes on the next checkout of the
    # base branch, and an untracked copy blocks checking that branch out again:
    # untracking it is what keeps resume reading the notes from the working tree.
    for path, message in [(_LITE_BOOT, "chore: multi-lite run notes"),
                          (_PR_LOOP, "chore: multi-pr run notes")]:
        text = _read(path)
        assert f"--grep='^{message}$'" in text, path.name
        assert "git rm --cached -q -- <notes>" in text, path.name
        assert f'git commit -m "{message} back to the working tree"' in text, path.name


def test_a_notes_only_head_move_is_forgiven_before_a_moved_head_stops_the_row() -> None:
    loop = _read(_LITE_LOOP)
    notes_arm = loop.index("touch only the run notes")
    moved_arm = loop.index("**`OPEN`, and `head_sha` is empty or differs from `headRefOid`**")
    assert notes_arm < moved_arm
    arm = loop[notes_arm:moved_arm]
    assert "git diff --name-only <head_sha> <headRefOid>" in arm
    assert "`cla.io/retro/multi-lite-run-notes-*.md`" in arm
