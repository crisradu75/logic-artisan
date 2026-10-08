"""Run records and chain run notes are committed on a work PR's branch, never on the base branch.

spec-to-pr commits its ledger line onto the feature branch it opened; multi-lite and
multi-pr commit their run notes onto the chain's last open PR, and leave them
uncommitted, saying so, when no PR is open. Each recipe is prose a model follows,
so these read the recipe: the commit is preceded by a checkout of the PR branch,
nothing in it checks out or pushes the base branch, and the direct-push escape
hatch is named only to forbid it.

The re-run half is checked too: multi-lite records each PR's head, and its own
notes commit moves that head, so the arm that forgives that move must sit before
the arm that stops a moved head, and must forgive nothing else: the diff ignores
renames, and every commit since must carry the run's own notes message. Each
chain defines that message once, and a re-run finds the commit by it rather than
by recency, since another doc's notes commit may be newer.
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


def _commits_on_the_pr_branch(recipe: str, notes: str) -> None:
    checkout = recipe.index("git checkout <branch>")
    state = recipe.index("gh pr view", checkout)
    add = recipe.index(f"git add -- {notes}")
    commit = recipe.index('git commit -m "<notes-message>"')
    push = recipe.index("git push", commit)
    assert checkout < state < add < commit < push
    assert "--expect-branch <branch>" in recipe[checkout:add]
    assert "-run-notes-*.md" not in recipe, "only this run's notes file is added"
    assert "never push, which would recreate a deleted branch" in recipe
    assert "git checkout <base-branch>" not in recipe
    assert "<base-branch>" not in re.sub(r"never `<base-branch>`|Never commit or push the notes to `<base-branch>`",
                                         "", recipe)


# requirement: run-ledgers / The spec-to-pr run record rides its pull request
def test_spec_to_pr_commits_its_record_on_the_feature_branch_only() -> None:
    step_6 = _between(_read(_HANDOFF), "## 6. Commit the run-log line", "Steps 5 and 6")
    assert "--expect-branch <branch>" in step_6
    assert "git add -- cla.io/retro/spec-to-pr-runs.jsonl" in step_6
    assert "Do this ONLY when Ship opened a PR" in step_6


# requirement: run-ledgers / Chain run notes ride the last open pull request
def test_multi_lite_commits_its_notes_on_the_last_open_pr() -> None:
    recipe = _between(_read(_LITE_PHASE4), "## Commit the run-notes file", None)
    _commits_on_the_pr_branch(recipe, "<notes>")
    assert "**None is open**" in recipe and "leave the file uncommitted and say so" in recipe
    assert "`ALLOW_PUSH_TO_MAIN=1`" in recipe and "Never commit or push" in recipe


# requirement: run-ledgers / Chain run notes ride the last open pull request
def test_multi_pr_commits_its_notes_on_the_last_open_pr() -> None:
    step_5 = _between(_read(_PR_CLEANUP), "5. **Commit the running notes", "Mark the")
    _commits_on_the_pr_branch(step_5, "<notes-path>")
    assert "leave the notes uncommitted and say so" in step_5


_LITE_MESSAGE = "`chore: multi-lite run notes for <source-doc-path>`"
_PR_MESSAGE = "`chore: multi-pr run notes <notes-path>`"


def test_each_chain_states_its_notes_message_once() -> None:
    lite = "".join(_read(p) for p in (_SKILLS / "multi-lite").rglob("*.md"))
    pr = "".join(_read(p) for p in (_SKILLS / "multi-pr").rglob("*.md"))
    assert lite.count("chore: multi-lite run notes") == 1
    assert f"**`<notes-message>`** is {_LITE_MESSAGE}" in _read(_LITE_BOOT)
    assert pr.count("chore: multi-pr run notes") == 2  # the definition, and the grep for it
    assert f"**`<notes-message>`** is {_PR_MESSAGE}" in _read(_PR_LOOP)


# requirement: run-ledgers / Chain run notes ride the last open pull request
def test_a_rerun_takes_committed_notes_back_out_before_it_needs_them() -> None:
    # A file tracked only on the PR branch vanishes on the next checkout of the
    # base branch, and an untracked copy blocks checking that branch out again:
    # untracking it is what keeps resume reading the notes from the working tree.
    for path, notes in [(_LITE_BOOT, "<notes>"), (_PR_LOOP, "<notes-path>")]:
        text = _read(path)
        lookup = text.index("git log --remotes --format='%H %s'")
        contains = text.index("`git branch -r --contains <sha>`", lookup)
        untrack = text.index(f"`git rm --cached -q -- {notes}`", contains)
        commit = text.index('`git commit -m "<notes-message>"`', untrack)
        back = text.index("verify the push, then `git checkout <base-branch>`", commit)
        assert lookup < contains < untrack < commit < back, path.name
    # multi-pr reads every notes file, so it looks each one up, not the newest.
    assert "For each `<notes-path>` missing from the working tree, take its newest `%H`" in _read(_PR_LOOP)


# requirement: run-ledgers / Chain run notes ride the last open pull request
def test_the_multi_lite_lookup_matches_this_docs_message_exactly() -> None:
    text = _read(_LITE_BOOT)
    assert "--fixed-strings --grep='<notes-message>'" in text
    assert "whose subject is exactly `<notes-message>`" in text


# requirement: small-change-chains / A resumed small-change chain merges only checked commits
def test_only_the_runs_own_notes_commits_are_forgiven_a_head_move() -> None:
    loop = _read(_LITE_LOOP)
    notes_arm = loop.index("every commit since is this run's own notes commit")
    moved_arm = loop.index("**`OPEN`, and `head_sha` is empty or differs from `headRefOid`**")
    assert notes_arm < moved_arm
    arm = loop[notes_arm:moved_arm]
    assert "`git diff --no-renames --name-only <head_sha> <headRefOid>` lists nothing but this run's notes path" in arm
    assert "every subject `git log --format=%s <head_sha>..<headRefOid>` prints is `<notes-message>`" in arm
    assert "-run-notes-*.md" not in arm
