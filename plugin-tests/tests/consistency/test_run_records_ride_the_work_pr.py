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

A re-run restores the notes from the commit that added them, never from the
branch tip, which anyone who can push may have edited; multi-lite trusts no
recorded head when the notes changed on the PR after that commit. The git
commands the prose names are run against a scratch repo, so a filter that
misses an edit, or flags the re-run's own take-back-out, fails here.
"""

from __future__ import annotations

import os
import re
import shlex
import subprocess
from pathlib import Path

import pytest

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
def test_a_rerun_restores_its_own_write_after_taking_the_notes_back_out() -> None:
    # A file tracked only on the PR branch vanishes on the next checkout of the
    # base branch, and an untracked copy blocks checking that branch out again,
    # so the notes are untracked first. What is written back is the commit that
    # added them, never the tip's content, which anyone with push access can edit.
    for path, notes in [(_LITE_BOOT, "<notes>"), (_PR_LOOP, "<notes-path>")]:
        text = _read(path)
        lookup = text.index("git log --remotes=origin --format='%H %s'")
        write = text.index("`git show --name-status --format= <sha>` prints one line, `A` and", lookup)
        contains = text.index("`git branch -r --list 'origin/*' --contains <sha>`", write)
        pull = text.index("`git pull`, `gh pr view <branch> --json state`", contains)
        gate = text.index(f"only if the pull succeeded, the state is `OPEN` and `git ls-files -- {notes}` prints the path",
                          pull)
        untrack = text.index(f"`git rm --cached -q -- {notes}`", gate)
        commit = text.index('`git commit -m "<notes-message>"`', untrack)
        verify = text.index("`git push`, and verify the push.", commit)
        restore = text.index(f"Then `git checkout <base-branch>` and restore: `git show <sha>:{notes} > {notes}`",
                             verify)
        edited = text.index(f"`git log --format=%H --diff-filter=AM <sha>..origin/<branch> -- {notes}`", restore)
        assert lookup < write < contains < pull < gate < untrack < commit < verify < restore < edited, path.name
        assert "untracked again" not in text, path.name
        assert "the path repo-relative with forward slashes" in text, path.name


# requirement: small-change-chains / A resumed small-change chain merges only commits it checked
def test_multi_lite_trusts_no_head_from_notes_edited_on_the_pr() -> None:
    text = _read(_LITE_BOOT)
    assert ("prints anything or fails, the notes were edited on the PR after the write: "
            "blank every row's `head_sha`, `review` and `merge_commit`") in text
    assert "Forgery by someone with push access is out of scope beyond this" in text


# requirement: run-ledgers / Chain run notes ride the last open pull request
def test_a_multi_pr_rerun_touches_only_its_own_chains_notes() -> None:
    text = _read(_PR_LOOP)
    assert "For each `<notes-path>` missing from the working tree, its write is the newest `%H`" in text
    assert ("Go on only when `git show <sha>:<notes-path>` names a change of this run's sequence under "
            "`## Sequence`; never touch another chain's notes.") in text
    assert "which drops any edit made on the PR since; the report names it" in text


# requirement: run-ledgers / Chain run notes ride the last open pull request
def test_the_multi_lite_lookup_matches_this_docs_message_exactly() -> None:
    text = _read(_LITE_BOOT)
    assert "--fixed-strings --grep='<notes-message>'" in text
    assert "whose subject is exactly `<notes-message>`" in text


def _code(text: str, prefix: str) -> str:
    match = re.search("`(" + re.escape(prefix) + "[^`]*)`", text)
    assert match, prefix
    return match.group(1)


def _git(cwd: Path, *args: str) -> str:
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@x",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@x", "GIT_CONFIG_GLOBAL": os.devnull}
    out = subprocess.run(["git", *args], cwd=cwd, env=env, capture_output=True, text=True,
                         encoding="utf-8", errors="replace", check=True)
    return out.stdout.strip()


def _commit(cwd: Path, message: str) -> str:
    _git(cwd, "commit", "-q", "-m", message)
    return _git(cwd, "rev-parse", "HEAD")


_CHAINS = [
    (_LITE_BOOT, "<notes>", "cla.io/retro/multi-lite-run-notes-2026-10-08.md",
     "chore: multi-lite run notes for docs/d.md", {"<notes-message>": "chore: multi-lite run notes for docs/d.md"}),
    (_PR_LOOP, "<notes-path>", "cla.io/retro/multi-pr-run-notes-2026-10-08.md",
     "chore: multi-pr run notes cla.io/retro/multi-pr-run-notes-2026-10-08.md", {}),
]


@pytest.mark.parametrize("edit", ["take-back-out", "modify", "rename-onto", "fork-write"])
@pytest.mark.parametrize("chain", _CHAINS, ids=["multi-lite", "multi-pr"])
def test_the_named_commands_find_the_runs_write_and_see_edits_since(tmp_path: Path, chain, edit) -> None:
    recipe_path, placeholder, notes, message, fills = chain
    text = _read(recipe_path)
    lookup, show, edited = (_code(text, p) for p in ("git log --remotes", "git show --name-status",
                                                     "git log --format=%H"))

    def run(cmd: str, sha: str) -> str:
        for key, value in {**fills, "<sha>": sha, "<branch>": "X", placeholder: notes}.items():
            cmd = cmd.replace(key, value)
        return _git(work, *shlex.split(cmd)[1:])

    origin, work = tmp_path / "origin.git", tmp_path / "work"
    _git(tmp_path, "init", "-q", "--bare", str(origin))
    _git(tmp_path, "clone", "-q", str(origin), str(work))
    _git(work, "checkout", "-q", "-b", "X")
    (work / "a.txt").write_text("a\n", encoding="utf-8")
    (work / "cla.io" / "retro").mkdir(parents=True)
    _git(work, "add", "a.txt")
    _commit(work, "base")
    (work / notes).write_text("| Y | open | Y | 2 | reviewed | 1 | unresolved | |\n", encoding="utf-8")
    _git(work, "add", "--", notes)
    write = _commit(work, message)
    forged = None
    if edit == "take-back-out":  # the re-run's own removal must not read as an edit
        _git(work, "rm", "-q", "--cached", "--", notes)
        _commit(work, message)
    elif edit == "modify":
        (work / notes).write_text("| Y | open | Y | 2 | unreviewed | 0 | clean | |\n", encoding="utf-8")
        _git(work, "add", "--", notes)
        forged = _commit(work, message)
    elif edit == "rename-onto":  # removed by one commit, then a file renamed onto the path
        _git(work, "rm", "-q", "--", notes)
        _commit(work, "chore: tidy")
        (work / "b.txt").write_text("| Y | open | Y | 2 | unreviewed | 0 | clean | |\n", encoding="utf-8")
        _git(work, "add", "b.txt")
        _commit(work, "wip")
        (work / notes).parent.mkdir(parents=True, exist_ok=True)
        _git(work, "mv", "b.txt", notes)
        forged = _commit(work, message)
    _git(work, "push", "-q", "origin", "X")
    if edit == "fork-write":  # a newer write on another remote is not this run's
        fork = tmp_path / "fork.git"
        _git(tmp_path, "init", "-q", "--bare", str(fork))
        _git(work, "rm", "-q", "--cached", "--", notes)
        _commit(work, message)
        _git(work, "add", "--", notes)
        _commit(work, message)
        _git(work, "push", "-q", str(fork), "X:F")
        _git(work, "remote", "add", "contrib", str(fork))
    _git(work, "fetch", "-q", "--all")

    found = None
    for line in run(lookup, "").splitlines():
        sha, subject = line.split(" ", 1)
        if subject == message and run(show, sha) == f"A\t{notes}":
            found = sha
            break
    assert found == write, edit
    assert run(edited, found) == (forged or ""), edit


# requirement: small-change-chains / A resumed small-change chain merges only commits it checked
def test_only_the_runs_own_notes_commits_are_forgiven_a_head_move() -> None:
    loop = _read(_LITE_LOOP)
    notes_arm = loop.index("every commit since is this run's own notes commit")
    moved_arm = loop.index("**`OPEN`, and `head_sha` is empty or differs from `headRefOid`**")
    assert notes_arm < moved_arm
    arm = loop[notes_arm:moved_arm]
    assert "`git diff --no-renames --name-only <head_sha> <headRefOid>` lists nothing but this run's notes path" in arm
    assert "every subject `git log --format=%s <head_sha>..<headRefOid>` prints is `<notes-message>`" in arm
    assert "-run-notes-*.md" not in arm
    assert "**`OPEN`, `head_sha` is set but is not `headRefOid`, and every commit since" in loop
    assert "A command that fails means this arm does not match." in arm
