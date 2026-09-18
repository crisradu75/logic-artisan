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
it.

**MUTANT 4 REINTRODUCES A DEFECT THAT SHIPPED**, and it is the reason this batch
changed shape. `main()` used to force `no_in_progress_op` to False on the
branch-mismatch path, where `in_progress is None` — so the field reported an
operation that was not mid-flight. That is the same conflation that made the
field's old name a defect (`{"clean": true}` read with 47 files staged),
pointing the other way, and the module docstring's claim that the field "means
exactly what it says" was false on that one path.

The mutant re-adds the assignment. It is worth reading as the pair it forms with
mutant 3: mutant 3 breaks the field's agreement with the op on the SUCCESS path,
mutant 4 breaks it on the mismatch path, and
`test_the_field_tracks_the_op_on_every_exit_code` states the invariant both
violate rather than leaving three tests that happen to agree.

**MUTANT 7 WAS UNKILLABLE UNTIL THIS CHANGE FIXED THE FIXTURE.** It is the mutant
the guard looks built for — `test_worktree_relative_gitdir_resolves`'s docstring
says the relative `gitdir:` pointer must be evaluated "against the worktree root,
not the script's cwd" — and it could not fail, because the `tmp_repo` fixture
calls `monkeypatch.chdir(tmp_path)`, `tmp_repo IS tmp_path`, and `_run` started
the subprocess with no `cwd=`. The child's cwd therefore WAS `repo_root`, so
`(repo_root / target).resolve()` and `target.resolve()` agreed on every input the
test supplied. The test asserted a property its own fixture removed.

The fix was on the TEST side, as reported: `_run` now passes an explicit neutral
cwd. Nothing else in the script reads the process cwd — `_current_branch` passes
`cwd=repo_root` to git directly — so no other test changed behaviour.

**One obvious mutant is still DELIBERATELY ABSENT, and it is a finding about the
GUARD rather than about the script.** It is not included, because it cannot be
killed in a correct tree and a survivor nobody can act on trains the next reader
to skip the whole list.

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

# Derived, not spelled: mutant 4 INSERTS a line, and a bare `\n` would write LF
# into a CRLF checkout.
_NL = "\r\n" if b"\r\n" in SCRIPT.read_bytes() else "\n"

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
        # drift from the op it reports. This makes it lie again, on the success
        # path.
        "the no_in_progress_op field stops tracking the op it reports, so the "
        "JSON says true in the same breath as in_progress_op: cherry-pick",
        SCRIPT,
        '        "no_in_progress_op": in_progress is None,',
        '        "no_in_progress_op": True,',
        TARGETS,
    ),
    (
        # RE-BREAKS A DEFECT THAT SHIPPED. The assignment below is what this
        # change removed: on the branch-mismatch path `in_progress` is None, so
        # forcing the field False claimed an operation that was not mid-flight.
        # Re-adding it is a one-line edit that no exit code and no other field
        # would betray — which is exactly why it survived as long as it did.
        "the branch-mismatch path forces no_in_progress_op False again, so the "
        "field reports an in-progress operation that does not exist",
        SCRIPT,
        '        # "any non-zero exit halts", so no caller has to read the field to see it.',
        '        # "any non-zero exit halts", so no caller has to read the field to see it.'
        + _NL
        + '        out["no_in_progress_op"] = False',
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
    (
        # NEWLY KILLABLE. See the header: this mutant survived until `_run`
        # stopped starting the child in the repo under test. A `git worktree
        # add` writes a RELATIVE `gitdir:` pointer, so resolving it against the
        # process cwd instead of the worktree root makes `.exists()` False and
        # the script fails closed at exit 1 where it should have detected the
        # in-progress merge.
        "a relative `gitdir:` pointer is resolved against the process cwd rather "
        "than the worktree root, so a real worktree fails closed instead of "
        "reporting the op it is in",
        SCRIPT,
        "            target = (repo_root / target).resolve()",
        "            target = target.resolve()",
        TARGETS,
    ),
]
