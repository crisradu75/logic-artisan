"""Mutant batch for `tests/hooks/test_block_unsafe_recursive_delete.py`.

Run: python3 plugin-tests/mutate.py plugin-tests/mutants/hooks/test_block_unsafe_recursive_delete.py

This is the blocking guard over recursive+forced deletion -- the hook whose
whole reason for existing is the 2026-07-19 incident described in its own
docstring, where a raw `rm -rf` recursed through an NTFS junction and
destroyed untracked files in the primary clone. A vacuous test here is the
most expensive kind: it reads green while the thing that stops the next
incident quietly does nothing.

Each entry re-breaks one real, distinct capability of the hook rather than a
variation on the same line: the two independent trigger conditions (a
worktree path anywhere in the target, and a symlink/junction found inside
it), the AND-of-two-flags logic that decides a delete is both recursive and
forced (bash and PowerShell are separate code paths, so both get their own
mutant), the heredoc-stripping that keeps prose from being misread as a real
invocation, the escape-hatch env var's exact-match semantics, and a
false-positive/over-broad match that would block ordinary, legitimate work.

Mutations target the HOOK SOURCE, not the guard, so each kill is evidence
about the hook's behaviour rather than about the guard's own wording.

Paths resolve from this file's own location: a batch with an absolute
developer path works on one machine and leaks it into synced core.
"""

from pathlib import Path

DEV = Path(__file__).resolve().parents[2]
PLUGIN = DEV.parent / ".claude" / "plugins" / "cla"
HOOK = PLUGIN / "hooks" / "block-unsafe-recursive-delete.py"
TARGETS = [DEV / "tests" / "hooks" / "test_block_unsafe_recursive_delete.py"]

MUTANTS = [
    (
        # Trigger 1 (worktree path): the docstring's own claim is "anywhere in
        # the path, any separator style". Narrowing the scan to only the first
        # segment pair breaks that -- a worktree path buried under a tmp_path
        # prefix (which is exactly what every test fixture produces) would no
        # longer be recognized at all. Caught by
        # test_worktree_path_detected_regardless_of_separator and by the
        # end-to-end test_blocks_worktree_path_delete.
        "worktree-path detection stops scanning past the first path segment",
        HOOK,
        "for i in range(len(segments) - 1):",
        "for i in [0]:",
        TARGETS,
    ),
    (
        # Trigger 2 (symlink/junction inside target): disables the one call
        # that actually flags a link found during the walk, independent of
        # whether the test environment can create a real symlink or has to
        # fall back to an NTFS junction -- both paths funnel through this same
        # call, so the mutant's killability does not depend on which alias
        # kind the test machine happens to permit. Caught by
        # test_blocks_directory_containing_a_symlink.
        "symlink/junction detection inside the delete target is disabled",
        HOOK,
        "if _is_link_like(os.path.join(dirpath, name)):",
        "if False and _is_link_like(os.path.join(dirpath, name)):",
        TARGETS,
    ),
    (
        # Flag parsing (bash): the hook must require BOTH recursive and
        # force, not either alone -- `rm -r` (no force) and `rm -f` (no
        # recurse) are both real, common, non-destructive-in-this-sense
        # commands that must not be flagged. AND-to-OR turns either into a
        # false trigger. Caught by test_does_not_detect_non_matching_commands
        # ("rm -r some/dir", "rm -f some/file").
        "bash recursive+force flag check becomes recursive-OR-force",
        HOOK,
        "return has_r and has_f",
        "return has_r or has_f",
        TARGETS,
    ),
    (
        # Flag parsing (PowerShell): the same AND-not-OR requirement, but this
        # is a separate function/code path (`-Recurse` alone or `-Force`
        # alone must not trigger). Caught by
        # test_does_not_detect_non_matching_commands ("Remove-Item -Recurse
        # some/dir", "Remove-Item -Force some/file").
        "PowerShell recursive+force flag check becomes recursive-OR-force",
        HOOK,
        "return has_recurse and has_force",
        "return has_recurse or has_force",
        TARGETS,
    ),
    (
        # Deliberately-allowed safe case: a heredoc-wrapped commit message
        # that merely MENTIONS "rm -rf" / "Remove-Item -Recurse" / "-Force" as
        # English prose must not be read as a real invocation -- this is the
        # exact regression the hook's own docstring records tripping against
        # itself. Skipping the strip lets the segment splitter (which also
        # splits on bare newlines) see "rm -rf" inside the prose and block a
        # legitimate commit. Caught by
        # test_allows_a_commit_message_mentioning_rm_rf_as_prose.
        "heredoc-body stripping is skipped, so prose is scanned as a real command",
        HOOK,
        'return _HEREDOC_BODY.sub("HEREDOC", command)',
        "return command",
        TARGETS,
    ),
    (
        # Escape hatch: must require the env var to be exactly "1", not
        # merely present. Every test that goes through the `_run` helper sets
        # `ALLOW_UNSAFE_RM=""` in the subprocess environment (to guarantee the
        # hatch is closed by default) -- loosening the check to "present at
        # all" makes that empty string count as an opt-out, silently
        # disarming the hook for every blocking test. Caught by
        # test_blocks_worktree_path_delete and the other end-to-end block
        # assertions.
        "escape hatch fires on ALLOW_UNSAFE_RM merely being set, not set to 1",
        HOOK,
        'if os.environ.get("ALLOW_UNSAFE_RM") == "1":',
        'if os.environ.get("ALLOW_UNSAFE_RM") is not None:',
        TARGETS,
    ),
    (
        # Negative case: a genuinely scoped, ordinary recursive delete (no
        # worktree path, no symlink) must NOT be blocked. Turning the
        # worktree-path condition into a tautology makes _is_worktree_path
        # true for essentially any multi-segment path, over-blocking
        # legitimate work. Caught by test_allows_a_clean_recursive_delete
        # (expects returncode 0, would get 2) and by
        # test_non_worktree_path_not_flagged.
        "worktree-path match becomes a tautology, blocking ordinary deletes too",
        HOOK,
        'segments[i] == ".claude" and segments[i + 1] == "worktrees"',
        "segments[i] == segments[i]",
        TARGETS,
    ),
]
