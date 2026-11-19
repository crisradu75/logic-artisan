"""The new-worktree skill states each outcome the worktree-setup spec requires.

Spec: openspec/specs/worktree-setup. The plain-git fallback's behaviour is proven by
test_manual_worktree.py; this file pins what the skill's own text promises.
"""

from __future__ import annotations

from pathlib import Path

_PLUGIN = Path(__file__).resolve().parents[4] / ".claude" / "plugins" / "cla"
_SKILL = _PLUGIN / "skills" / "new-worktree" / "SKILL.md"
_CASING = _PLUGIN / "skills" / "new-worktree" / "references" / "path-casing.md"


def _flat(path: Path) -> str:
    return " ".join(path.read_text(encoding="utf-8").split())


# requirement: worktree-setup / A new worktree is ready to work in
def test_the_skill_enters_installs_copies_env_files_and_reports():
    text = _flat(_SKILL)
    assert "Call `EnterWorktree`" in text
    assert "dependency-install command" in text
    assert "gitignored env file(s)" in text
    assert "worktree path, branch name, and whether the install and the `.env` copy succeeded" in text
    assert "Surface the base branch in step 3" in text


# requirement: worktree-setup / A new worktree is ready to work in
def test_a_missing_env_file_is_skipped_and_reported_not_fatal():
    text = _flat(_SKILL)
    assert "— skipping" in text
    assert "note that in the final report — don't fail the whole flow" in text


# requirement: worktree-setup / Inside a worktree only setup runs
def test_inside_a_worktree_the_skill_runs_setup_only_and_says_so():
    text = _flat(_SKILL)
    assert "ALREADY inside a worktree, that is the setup-only case" in text
    assert "Do NOT try to create a second worktree" in text
    assert '"worktree already existed; ran setup only"' in text


# requirement: worktree-setup / Work stays inside the worktree
def test_every_later_path_targets_the_worktree_and_a_manual_one_is_flagged():
    text = _flat(_SKILL)
    assert "must use a path relative to the worktree cwd" in text
    assert "never a hardcoded primary-clone path" in text
    casing = _flat(_CASING)
    assert "every** subsequent path must target the worktree explicitly" in casing
    assert "it must go in the final report" in casing


# requirement: worktree-setup / A casing refusal falls back without deleting anyone's files
def test_a_casing_refusal_is_never_fixed_by_renaming_the_repo():
    casing = _flat(_CASING)
    assert 'Do not "fix" it by renaming the repo directory' in casing
    assert "A non-empty directory git no longer tracks is never deleted" in casing
    assert "Don't retry `EnterWorktree`" in _flat(_SKILL)


# requirement: worktree-setup / Removing a worktree lists what it would delete
def test_removal_lists_untracked_and_ignored_files_first():
    text = _flat(_SKILL)
    assert "list its untracked and gitignored files first" in text
    assert "removal deletes gitignored files silently" in text
    cleanup = _flat(_PLUGIN / "skills" / "multi-pr" / "references" / "cleanup.md")
    assert "Before any removal, list what would be lost" in cleanup
