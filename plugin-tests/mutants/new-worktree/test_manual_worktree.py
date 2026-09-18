"""Mutation batch for test_manual_worktree.py.

CLAUDE.md's script table justifies this script in one line: it "routes around the
Windows path-casing refusal, and refuses to remove a worktree holding uncommitted
work — where a model slip destroys work". The second half is the reason this
batch exists at all, and mutant 1 is the whole argument: it is the edit that
turns the refusal into a deletion, and nothing else in the suite is pointed at
it.

**The refusal is covered on every platform, which is what makes mutant 1 worth
writing.** `test_a_registered_worktree_with_uncommitted_work_is_never_force_
removed` carries no `skipif` and drives a real `git worktree add` plus a real
dirty tree. The skips in that file are elsewhere — the three directory-alias
tests, and the Windows-only end-to-end casing test, each of which has an
everywhere-partner. So the highest-value behaviour in the script is guarded on
this machine and on a POSIX one alike.

**Mutants 1 and 2 are a PAIR, deliberately, and neither is worth much alone.**
Mutant 1 proves the refusal exists; mutant 2 proves the refusal has not eaten the
feature it guards, by removing the `unlock` that lets a legitimate cleanup
succeed. A script that refused everything would pass mutant 1 and fail nothing —
which is the "simpler form of the code is also correct" trap CLAUDE.md warns
about, where the test defends the defect. Read them together.

**`make_dir_alias` IS NOT MUTATED HERE**, though it lives in this guard. It is
group 4 of `check_script_drift.py`'s sibling groups, so editing it reddens the
drift guard too and the kill would not attribute itself to this guard. Same rule
the aggregator batches follow for their shared resolvers.

**DELIBERATELY NOT A MUTANT: `resolved = os.path.realpath(str(path))` ->
`str(path)`.** It is the obvious mutant for the casing half of the script, and it
is not reliably killable. `test_the_returned_path_is_canonical_not_the_spelling_
we_passed` asserts against `realpath(str(repo / ...))`, so where the fixture's
`tmp_path` is ALREADY canonical the mutated and original expressions agree on
every input the test supplies — CLAUDE.md's named unkillable class. The alias
test does discriminate, but it skips wherever neither a symlink nor a junction
can be created, so a kill there is a fact about the machine rather than about the
guard. Recorded rather than included, because a survivor nobody can act on trains
the next reader to skip the whole list.

That leaves a REAL COVERAGE FINDING, stated here rather than hidden: the
canonicalisation is pinned only where the alias tests run. A batch entry cannot
fix that; a fixture whose path needs normalising would.

Run: python3 plugin-tests/mutate.py plugin-tests/mutants/new-worktree/test_manual_worktree.py
"""

from pathlib import Path

DEV = Path(__file__).resolve().parents[2]
PLUGIN = DEV.parent / ".claude" / "plugins" / "cla"

SCRIPT = PLUGIN / "skills" / "new-worktree" / "scripts" / "manual_worktree.py"

# Scoped to the ONE guard file. Pointing at the area would report every mutant
# killed the moment anything else there went red, which proves nothing.
TARGETS = [DEV / "tests" / "skills" / "new-worktree" / "test_manual_worktree.py"]

MUTANTS = [
    (
        # THE ONE THAT MATTERS. `git status` exits 0 on a dirty tree — being
        # dirty is not an error — so reading only the returncode drops the
        # uncommitted-work check entirely while still looking like a check.
        # The script then unlocks and `remove --force`s a worktree holding the
        # user's unsaved work.
        "the dirty check reads only git status's EXIT CODE, so a worktree full of "
        "uncommitted work is force-removed",
        SCRIPT,
        '            if status.returncode != 0 or (status.stdout or "").strip():',
        "            if status.returncode != 0:",
        TARGETS,
    ),
    (
        # The other half of the pair. Without this the refusal above could be
        # replaced by "refuse always" and mutant 1 would still die.
        "cleanup stops unlocking, so the half-created locked entry a crashed run "
        "leaves behind can never be cleared and creation stays wedged",
        SCRIPT,
        '            run_git(repo, ["worktree", "unlock", str(path)], check=False)',
        "            pass  # leave the lock in place",
        TARGETS,
    ),
    (
        # Not a refusal but a DIAGNOSIS: the two kinds send the reader at two
        # different bugs, and swapping them is silent because both are truthy
        # strings. Killed by the monkeypatched sibling that runs everywhere,
        # not by the Windows-only end-to-end test.
        "the casing classifier's two kinds are swapped, so a symlinked repo is "
        "reported as a letter-case difference and vice versa",
        SCRIPT,
        "    if as_given.lower() != resolved.lower():",
        "    if as_given.lower() == resolved.lower():",
        TARGETS,
    ),
    (
        # `pathmod` is injected, so this fails on POSIX too — no platform
        # escape. `D:elsewhere/tmp` is drive-RELATIVE: `isabs` is False and
        # there is no leading separator, so only `splitdrive` refuses it, and
        # the `Path` join then discards the repo prefix.
        "the drive-relative rule is dropped, so `--worktree-dir D:elsewhere/tmp` "
        "is accepted and the repo prefix is silently discarded by the join",
        SCRIPT,
        "    if rooted or pathmod.isabs(worktree_dir) or pathmod.splitdrive(worktree_dir)[0]:",
        "    if rooted or pathmod.isabs(worktree_dir):",
        TARGETS,
    ),
    (
        # The call `main` also makes, which is exactly why this is worth
        # mutating: an importing caller reaches the join with the traversal
        # check unrun, and the CLI path stays green throughout.
        "create_worktree stops validating its own worktree_dir, so only the CLI "
        "is guarded and an importing caller escapes the repo",
        SCRIPT,
        "    validate_worktree_dir(worktree_dir)",
        "    pass  # trust main to have validated",
        TARGETS,
    ),
    (
        # Every other creation test is blind to this; the killing test advances
        # `main` past `origin/main` first precisely so the two commits differ.
        "the requested base is dropped from the `worktree add` argv, so the "
        "worktree branches from whatever HEAD happens to be",
        SCRIPT,
        '    run_git(repo, ["worktree", "add", rel, "-b", branch, base])',
        '    run_git(repo, ["worktree", "add", rel, "-b", branch])',
        TARGETS,
    ),
]
