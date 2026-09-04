"""Mutant batch for `tests/hooks/test_block_unsafe_recursive_delete.py`.

Run: python3 plugin-tests/mutate.py plugin-tests/mutants/hooks/test_block_unsafe_recursive_delete.py

This is the blocking guard over recursive+forced deletion -- the hook whose
whole reason for existing is the 2026-07-19 incident described in its own
docstring, where a raw `rm -rf` recursed through an NTFS junction and
destroyed untracked files in the primary clone. A vacuous test here is the
most expensive kind: it reads green while the thing that stops the next
incident quietly does nothing.

Each entry re-breaks one real, distinct capability of the hook rather than a
variation on the same line: the three independent trigger conditions (a link
AS the target, a worktree path anywhere in it, and a symlink/junction found
inside it), the AND-of-two-flags logic that decides a delete is both recursive and
forced (bash and PowerShell are separate code paths, so both get their own
mutant), the heredoc-stripping that keeps prose from being misread as a real
invocation, the escape-hatch env var's exact-match semantics, and a
false-positive/over-broad match that would block ordinary, legitimate work.

Mutations target the HOOK SOURCE, not the guard, so each kill is evidence
about the hook's behaviour rather than about the guard's own wording.

Paths resolve from this file's own location: a batch with an absolute
developer path works on one machine and leaks it into synced core.

PLATFORM NOTE, because a skip reads as a SURVIVED verdict. Three entries here
are platform-conditional, and a reader who does not know that will read a
survivor as a finding about the code:

  * The symlink/junction mutant's killer goes through `make_dir_alias`, which
    calls `pytest.skip` when neither alias kind can be created. The batch is
    robust to WHICH kind the machine permits, but not to a machine permitting
    NEITHER -- there it reports SURVIVED, a fact about the machine.
  * The ValueError-swallow mutant is killable on WINDOWS ONLY, by construction:
    `_is_link_like` returns at `sys.platform != "win32"` before it ever reaches
    the `os.stat` that raises, so on POSIX the edit is unobservable.
  * The trailing-separator mutant is the mirror image -- on Windows the strip is
    a NO-OP (`os.stat` reads a reparse point straight through a trailing
    separator), so no junction fixture can kill it there. It dies on the
    monkeypatched unit test, which stubs POSIX's slash-sensitive contract; on
    POSIX the end-to-end parametrize kills it too.
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
        "if _is_link_like(os.path.join(dirpath, name)) is True:",
        "if False and _is_link_like(os.path.join(dirpath, name)) is True:",
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

MUTANTS.append((
    # The check issue #215 added, and the one the guard was missing entirely.
    # `Path.resolve()` follows a reparse point, so the target's own link-ness has
    # to be read BEFORE resolution or it is gone. Disabling this line restores
    # the defect exactly: `rm -rf <a junction>` allowed, `rm -rf <its parent>`
    # blocked -- the guard blocking the distant shape and permitting the near
    # one, which is the shape that deletes the far side of the link.
    #
    # This entry is the reason the sibling mutant on `_contains_symlink`'s old
    # guard clause was NOT written. That clause was dead and encoded the opposite
    # intent, so a mutant for it was unkillable and a test for it would have
    # pinned the defect. It was deleted rather than covered; this is what covers
    # the behaviour instead.
    "the target's own link-ness is never checked, so rm -rf of a junction "
    "recurses through it and deletes the far side",
    HOOK,
    "            if _target_is_link(unresolved):",
    "            if False and _target_is_link(unresolved):",
    TARGETS,
))

MUTANTS.append((
    # The trailing-separator strip. Without it `os.path.islink('link/')` is
    # False on POSIX -- and `rm -rf link/` is the spelling that actually reaches
    # through there, while bare `rm -rf link` merely unlinks. The first version
    # of this fix omitted the strip and therefore blocked the safe spelling and
    # allowed the destructive one. Windows hides the bug (os.stat reads the
    # reparse point through a trailing separator), which is why it took a run
    # under WSL to find, and why the killing test is parametrized over spellings.
    "the trailing-separator strip is dropped, so rm -rf <link>/ stops being "
    "recognised as targeting the link",
    HOOK,
    '        if probe[-1:] in ("/", "\\\\") and os.path.dirname(probe) != probe:',
    '        if False and probe[-1:] in ("/", "\\\\") and os.path.dirname(probe) != probe:',
    TARGETS,
))

MUTANTS.append((
    # The must-resolve-to-a-directory requirement. Without it a dangling link
    # and a link to a FILE both block, and neither can produce the incident --
    # a dangling link points at nothing and a file link has no far side to
    # recurse into. On a guard that BLOCKS and ships to four repos those are
    # real false positives: `rm -rf ~/.config/nvim` on a dotfiles symlink, and
    # `rm -rf node_modules/<pkg>` in a workspace.
    "the directory requirement is dropped, so a dangling or file-targeted link "
    "blocks too",
    HOOK,
    "    return _far_side_is_a_directory(probe)",
    "    return True",
    TARGETS,
))

MUTANTS.append((
    # ValueError in the swallow tuple. `os.stat` raises it for an embedded null,
    # and the command arrives as JSON on stdin so a null is trivially reachable.
    # `os.path.islink` catches it internally, which is why this only became live
    # when the caller started passing an unresolved path straight in -- an
    # unconditional BLOCK on a worktree delete became an uncaught raise, which
    # the dispatcher fails open into an `ask`. Nobody is at the prompt in an
    # unattended run.
    "ValueError stops being swallowed, so an embedded null in the path crashes "
    "the hook instead of blocking",
    HOOK,
    "_UNREADABLE_ERRORS = (OSError, ValueError)",
    "_UNREADABLE_ERRORS = (OSError,)",
    TARGETS,
))

MUTANTS.append((
    # The `/.` strip branch had no mutant of its own -- the only thing
    # exercising it was one parameter of the monkeypatched test, so deleting the
    # branch would have been caught by a single parametrize cell and by nothing
    # else. CLAUDE.md check 4: the fix's own line earns evidence.
    #
    # Worth knowing what this spelling IS and is not. Measured with GNU
    # coreutils 9.7: `rm -rf link/.` is REFUSED by rm itself ("refusing to
    # remove '.' or '..' directory"), so it destroys nothing. Blocking it is
    # conservative, not necessary -- unlike `link/`, which does delete the far
    # side. The branch earns its place by keeping the two spellings consistent,
    # not by closing a hole.
    "the trailing /. strip is dropped, so rm -rf <link>/. stops being "
    "recognised as targeting the link",
    HOOK,
    '        elif probe.endswith(("/.", "\\\\.")) and len(probe) > 2:',
    '        elif False and probe.endswith(("/.", "\\\\.")) and len(probe) > 2:',
    TARGETS,
))

MUTANTS.append((
    # The conservative default on an unreadable far side. `os.path.isdir` was
    # the first spelling and it swallows every error into False, so "the far
    # side is a file" and "the far side could not be read" became the same
    # answer -- and the second silently ALLOWED. Measured by a reviewer: a
    # symlink to a directory under a mode-000 parent was BLOCKED before the
    # directory check existed and ALLOWED after it, a coverage regression
    # introduced by the check meant to reduce false positives.
    #
    # A junction into a clone whose far side cannot be stat'd is exactly the
    # shape this hook exists for, so an unreadable target must block.
    "an unreadable far side is treated as 'not a directory' and allowed, "
    "instead of blocking on an undetermined answer",
    HOOK,
    "_UNDETERMINED_FAR_SIDE_BLOCKS = True",
    "_UNDETERMINED_FAR_SIDE_BLOCKS = False",
    TARGETS,
))

MUTANTS.append((
    # The tri-state itself: collapse "could not read this path" back into
    # "not a link". That is the Critical round three found -- the conservative
    # policy existed but sat DOWNSTREAM of this swallow, so it could never fire
    # for the case it was written for. Measured on both platforms against a link
    # whose parent denies traverse: rc=0, empty stderr, byte-identical to an
    # examined approval.
    "an unreadable path is scored as 'not a link' instead of undetermined, so "
    "the conservative policy never runs",
    HOOK,
    "        return _LINK_UNDETERMINED",
    "        return False",
    TARGETS,
))

MUTANTS.append((
    # The routing half. Even with the sentinel produced, dropping the branch
    # that acts on it puts the behaviour back: `any(verdicts)` is True for a
    # truthy sentinel, so it would fall through to `_far_side_is_a_directory`
    # on a path it could not read -- a different wrong answer, not the same one.
    "the undetermined verdict stops being routed to the block policy",
    HOOK,
    "    if _LINK_UNDETERMINED in verdicts:",
    "    if False and _LINK_UNDETERMINED in verdicts:",
    TARGETS,
))

MUTANTS.append((
    # The error split inside `_far_side_is_a_directory`. Adding OSError here
    # sends every read failure down the allow arm and undoes the whole policy --
    # the single most likely future regression, and a better anchor than the
    # policy constant (round three's review made exactly this point).
    "an unreadable far side joins the missing-target arm and is allowed",
    HOOK,
    "_MISSING_TARGET_ERRORS = (FileNotFoundError, NotADirectoryError)",
    "_MISSING_TARGET_ERRORS = (FileNotFoundError, NotADirectoryError, OSError)",
    TARGETS,
))
