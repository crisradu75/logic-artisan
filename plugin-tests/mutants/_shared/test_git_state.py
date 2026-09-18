"""Mutation batch for test_git_state.py.

`git_state.py` is the one deterministic exit code for "an in-progress
rebase/cherry-pick/merge exists", checked at every commit boundary across four
skills. A guard that stopped noticing one of those states would let a skill
commit in the middle of a conflicted rebase, so the markers and the EXIT CODES
are what this batch pins.

**Exit 2 must supersede exit 3, and that ordering is the subtle one.** Mutant 2
narrows the in-progress branch so the wrong-branch report fires first. Both codes
are non-zero, so a caller that only checks truthiness sees no difference — the
harm is that the report names the wrong problem and hides the rebase that caused
it. Only one test passes a marker AND a mismatching `--expect-branch` at once,
which is what makes the kill attributable.

**Two obvious mutants are DELIBERATELY ABSENT, and both are findings about the
GUARD rather than about the script.** Neither is included, because neither can be
killed in a correct tree and a survivor nobody can act on trains the next reader
to skip the whole list.

  * `target = (repo_root / target).resolve()` -> `target.resolve()`. This is the
    mutant the guard looks built for — `test_worktree_relative_gitdir_resolves`'s
    docstring says the relative `gitdir:` pointer must resolve against the
    worktree root "not the script's cwd". It cannot fail: the `tmp_repo` fixture
    IS `tmp_path` and calls `monkeypatch.chdir(tmp_path)`, and `_run` starts the
    child with no `cwd=`, so the child's cwd already IS `repo_root` and the two
    expressions agree on every input the test supplies. The test asserts a
    property its own fixture removes. Fix is on the TEST side — run the child
    from a neutral directory — after which this becomes a good mutant.
  * Anything in `_git_dir`'s fail-closed region. All three fail-closed tests build
    their subject in a bare `tmp_path`, which is not a git repo, so even with
    `_git_dir` fully defeated `_current_branch` runs `git rev-parse` there, gets
    exit 128, and `main` exits 1 with the same payload the tests assert. The
    `git_dir is None` branch is SHADOWED by the branch branch and no test can
    tell them apart. Fix is again on the test side: `git init` the fixture and
    then break `.git`, or assert the specific error text.

Both were measured rather than reasoned: the second by running
`git rev-parse --abbrev-ref HEAD` in a non-repo directory and confirming exit 128.

Run: python3 plugin-tests/mutate.py plugin-tests/mutants/_shared/test_git_state.py
"""

from pathlib import Path

DEV = Path(__file__).resolve().parents[2]
PLUGIN = DEV.parent / ".claude" / "plugins" / "cla"

SCRIPT = PLUGIN / "skills" / "_shared" / "scripts" / "git_state.py"

# Scoped to the ONE guard file, never the area.
TARGETS = [DEV / "tests" / "skills" / "_shared" / "test_git_state.py"]

MUTANTS = [
    (
        "bisect drops out of the marker set, so a half-finished bisect reads as a "
        "clean commit boundary and a skill commits into it",
        SCRIPT,
        '        return "bisect"',
        "        return None",
        TARGETS,
    ),
    (
        # The precedence one. Both codes are non-zero, so this is invisible to a
        # caller checking truthiness — the harm is a report naming the wrong
        # problem.
        "an in-progress op stops superseding the branch check, so exit 3 fires "
        "first and the wrong-branch report hides the rebase that caused it",
        SCRIPT,
        "    if in_progress is not None:",
        "    if in_progress is not None and args.expect_branch is None:",
        TARGETS,
    ),
    (
        # The field renamed itself away from `clean` precisely so it could not
        # drift from the op it reports. This makes it lie again.
        "the no_in_progress_op field stops tracking the op it reports, so the "
        "JSON says true in the same breath as in_progress_op: cherry-pick",
        SCRIPT,
        '        "no_in_progress_op": in_progress is None,',
        '        "no_in_progress_op": True,',
        TARGETS,
    ),
    (
        "the branch-mismatch exit leaves no_in_progress_op true, so a consumer "
        "reading the field rather than the exit code proceeds on the wrong branch",
        SCRIPT,
        '        out["no_in_progress_op"] = False',
        '        out["no_in_progress_op"] = True',
        TARGETS,
    ),
    (
        # Re-breaks the decision `_current_branch`'s docstring spells out: a
        # detached HEAD is a valid state to REPORT, not a resolution failure.
        "detached HEAD is treated as a failure to resolve, so a detached checkout "
        "fails closed at exit 1 instead of being reported as the state it is",
        SCRIPT,
        "    if result.returncode != 0:",
        '    if result.returncode != 0 or (result.stdout or "").strip() == "HEAD":',
        TARGETS,
    ),
    (
        "revert stops being detected, so a conflicted `git revert` is invisible "
        "at a commit boundary",
        SCRIPT,
        '    if (git_dir / "REVERT_HEAD").exists():',
        "    if False:",
        TARGETS,
    ),
]
