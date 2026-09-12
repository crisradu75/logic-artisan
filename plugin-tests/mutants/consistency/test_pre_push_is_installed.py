"""Mutation batch for test_pre_push_is_installed.py.

The guard claims the push-to-main hook is really installed in THIS clone, is
executable, and has not drifted from its source. The failure it exists for is
that absence looks exactly like compliance: no error, no warning, and the first
sign is a push to `main` that succeeds.

**Nothing here touches `.git/hooks/pre-push`, deliberately.** That file is the
guard's real subject, and mutating it would be the most direct probe — but git
shares `.git/hooks` across every worktree of a repository, so a mutant there
edits the hook protecting the primary checkout and every sibling worktree for the
duration of a pytest run. `mutate.py` restores byte-exactly, but the window is
real and the thing inside it is the push guard. The four mutants below reach the
same assertions through the plugin's own copy and the guard's own path
resolution, both of which live inside this worktree.

**One consequence of that choice, stated rather than implied:** no mutant here
exercises the *installed* file being wrong on its own terms. Mutant 1 proves the
drift comparison reads both sides by moving the source; it does not prove the
comparison would notice the installed copy moving instead.

An earlier version of this paragraph called such a mutant "unkillable by
construction", which is wrong: `installed == source` is symmetric, so mutating
the other operand would be KILLED — just redundantly, by the same assertion.
The real reason it is absent is the one at the top of this docstring, and it is
a safety argument rather than an information one: from a worktree,
`git rev-parse --git-path hooks` resolves to the **primary** clone's
`.git/hooks`, so that mutant would disarm the push guard for the primary
checkout and every sibling worktree for the duration of a pytest run.

**`test_the_installed_guard_is_executable` has no mutant.** It is skipped on
Windows (`sys.platform == "win32"`), which is where this batch is run and where
this repo has no CI, so any mutant against it would report killed or survived on
the strength of a skip. That is a platform gap in the evidence, not a gap in the
batch, and it is named here so nobody reads 4/4 as covering the chmod case.

Run: python3 plugin-tests/mutate.py plugin-tests/mutants/consistency/test_pre_push_is_installed.py
"""

from pathlib import Path

DEV = Path(__file__).resolve().parents[2]
PLUGIN = DEV.parent / ".claude" / "plugins" / "cla"

GUARD = DEV / "tests" / "consistency" / "test_pre_push_is_installed.py"
SOURCE = PLUGIN / "hooks" / "git" / "pre-push"

# Scoped to the ONE guard file: a target red for any other reason reports every
# mutant "killed" and proves nothing.
TARGETS = [GUARD]

MUTANTS = [
    (
        # THE QUIET FAILURE the guard names: a copy that exists, so the
        # installation check passes, while missing whatever the source learned
        # since it was copied. Moving the source is the reachable half of that
        # comparison — see the docstring for why the installed half is left
        # alone.
        "the source hook gains a line the installed copy does not have",
        SOURCE,
        "# CLA guard: refuse a push that targets the default branch directly.",
        "# CLA guard: refuse a push that targets the default branch directly. (revised)",
        TARGETS,
    ),
    (
        # NON-VACUITY for the whole file. `_SOURCE` is what every assertion
        # compares against; point it at a name that does not exist and
        # `test_the_source_hook_still_exists` fires. Without that test the other
        # three would compare against nothing and pass by accident, which is the
        # shape its own docstring claims to prevent — this is the evidence.
        "the source path names a hook file that does not exist",
        GUARD,
        '_SOURCE = _PLUGIN_ROOT / "hooks" / "git" / "pre-push"',
        '_SOURCE = _PLUGIN_ROOT / "hooks" / "git" / "pre-push-disabled"',
        TARGETS,
    ),
    (
        # THE `core.hooksPath` CASE, which is the reason this helper asks git
        # instead of hardcoding `<gitdir>/hooks`. Husky, pre-commit and lefthook
        # all set that config, often `--global`, and with it set git ignores
        # `.git/hooks` entirely — so a check looking there passes on a file git
        # will never execute. Asking git for the wrong path name simulates
        # resolving to a directory git does not use.
        "the hooks directory is resolved to a path git does not execute from",
        GUARD,
        '["git", "-C", str(_REPO_ROOT), "rev-parse", "--git-path", "hooks"],',
        '["git", "-C", str(_REPO_ROOT), "rev-parse", "--git-path", "hooks-unused"],',
        TARGETS,
    ),
    (
        # THE OTHER NON-VACUITY PARTNER, and the one whose failure is silent.
        # `_REPO_ROOT` is a fixed `parents[N]` hop; wrong, git answers about a
        # different tree or not at all, `_hooks_dir()` returns None, and every
        # remaining test SKIPS — green, with nothing checked. That is precisely
        # what `test_the_repo_root_resolved_correctly` exists to catch, and this
        # is the evidence it does.
        "the repo-root hop lands somewhere that is not this clone",
        GUARD,
        "_REPO_ROOT = _PLUGIN_ROOT.parents[2]",
        "_REPO_ROOT = _PLUGIN_ROOT.parents[1]",
        TARGETS,
    ),
]
