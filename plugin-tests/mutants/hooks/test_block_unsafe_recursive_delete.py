"""Mutant batch for `tests/hooks/test_block_unsafe_recursive_delete.py`.

Run: python3 plugin-tests/mutate.py plugin-tests/mutants/hooks/test_block_unsafe_recursive_delete.py

This is the blocking guard over recursive+forced deletion -- the hook whose
whole reason for existing is the 2026-07-19 incident described in its own
docstring, where a raw `rm -rf` recursed through an NTFS junction and
destroyed untracked files in the primary clone. A vacuous test here is the
most expensive kind: it reads green while the thing that stops the next
incident quietly does nothing.

Each entry re-breaks one real, distinct capability of the hook rather than a
variation on the same line: the ONE trigger condition (the delete target is
itself a link), the AND-of-two-flags logic that decides a delete is both
recursive and forced (bash and PowerShell are separate code paths, so both get
their own mutant), and the heredoc-stripping that keeps prose from being
misread as a real invocation.

FOUR ENTRIES WERE REMOVED WITH THE CODE THEY ANCHORED ON. The hook used to
carry two more triggers (a worktree-path rule, and a bounded walk looking for
a link inside the target) and an `ALLOW_UNSAFE_RM` escape hatch; all three are
gone, so their mutants could no longer find their anchors. They were deleted
rather than retargeted -- a mutant whose anchor is absent is refused by the
runner, and a batch carrying refusals trains the next reader to skip the list.
The removed behaviour is pinned in the test file instead, as explicit ALLOWs,
so re-adding it is a visible decision.

Mutations target the HOOK SOURCE, not the guard, so each kill is evidence
about the hook's behaviour rather than about the guard's own wording.

Paths resolve from this file's own location: a batch with an absolute
developer path works on one machine and leaks it into synced core.

PLATFORM NOTE, because a skip reads as a SURVIVED verdict. Entries here are
platform-conditional, and a reader who does not know that will read a
survivor as a finding about the code:

  * Every killer that needs a real link goes through `make_dir_alias`, which
    calls `pytest.skip` when neither alias kind can be created. The batch is
    robust to WHICH kind the machine permits, but not to a machine permitting
    NEITHER -- there it reports SURVIVED, a fact about the machine.
  * The ValueError-swallow mutant WAS Windows-only, when `_is_link_like` began
    with `os.path.islink` and returned at the `sys.platform` check before the
    `os.stat` that raises. That is no longer true: `os.lstat` is now the first
    statement and the platform check is downstream of it, so the raise is
    reachable on both platforms and the mutant dies on both. Left in this list
    as a record of a note that outlived its reason.
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
    "            verdict = _target_is_link(unresolved)",
    "            verdict = False and _target_is_link(unresolved)",
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
    "    except ValueError:  # an embedded null in the path",
    "    except ZeroDivisionError:  # an embedded null in the path",
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
    "        if exc.errno in _UNNAMEABLE_ERRNOS:",
    "        if True:",
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

MUTANTS.append((
    # The other direction of the same line, and the regression that made it
    # necessary. Treating an UNNAMEABLE string as undetermined blocked
    # `rm -rf dist/*` on Windows -- `os.lstat` raises OSError(EINVAL) for a `*`,
    # because it cannot name an NTFS file. 7 of 16 everyday commands began to
    # block, with a message asserting the target was a junction. This hook ships
    # to four repos under `--permission-mode auto`, where the hooks are the
    # safety layer.
    "an unnameable string (a glob, a redirection token) is treated as "
    "undetermined and blocks, instead of as a determinate not-a-link",
    HOOK,
    "        if exc.errno in _UNNAMEABLE_ERRNOS:",
    "        if False:",
    TARGETS,
))

# --------------------------------------------------------------------------- #
# The remedy the block message prescribes. With no escape hatch, a wrong remedy
# leaves a blocked caller with nowhere to go -- issue #220's pathology, which
# the first version of this shrink reintroduced.
# --------------------------------------------------------------------------- #

MUTANTS.append((
    # The exact defect a review found. Measured `-NonInteractive` against a real
    # junction, a bare `Remove-Item <junction>` FAILS under Windows PowerShell
    # 5.1 -- it prompts, and the PowerShell tool `hooks.json` wires to this
    # dispatcher runs non-interactive, so it removes nothing and reports
    # "Windows PowerShell is in NonInteractive mode".
    #
    # Restoring that wording is the most likely future regression here, because
    # it reads as the tidier, more symmetric sentence.
    "the Windows remedy reverts to a bare non-recursive Remove-Item, which "
    "fails under PowerShell 5.1 and leaves the caller with no way forward",
    HOOK,
    '"Remove the link itself instead: `Remove-Item -Recurse <link>` (WITHOUT "',
    '"Remove the link itself instead, with a plain non-recursive rm/Remove-Item "',
    TARGETS,
))

MUTANTS.append((
    # Drops the fallback that works on both PowerShell editions, leaving only
    # the counter-intuitive `-Recurse`-without-`-Force` form -- exactly the case
    # where a reader wants a second option they can trust.
    "the cmd /c rmdir fallback is dropped from the Windows remedy",
    HOOK,
    '"removes a junction without prompting), or `cmd /c rmdir <link>`. Both "',
    '"removes a junction without prompting). Both "',
    TARGETS,
))

# ---------------------------------------------------------------------------
# Issue #236: the remedy is chosen by the caller's TOOL, not by this process's
# platform. The four below break that routing in the four places it can break.
# They are about WHICH text a caller gets; the two above are about WHAT each
# text says. Both halves are needed -- right text to the wrong shell, or the
# right shell given wrong text, each leaves a blocked caller stuck, and with no
# escape hatch that sentence is all they have.
#
# ONE MUTANT IS DELIBERATELY ABSENT. Renaming `_POWERSHELL_TOOL`'s value so a
# PowerShell payload stops matching is UNKILLABLE on Windows: the payload then
# falls through to the `sys.platform` fallback, which yields the same
# PowerShell text, so no correct-tree input can tell the two apart. That is the
# "two candidate rules agree on every real input" case -- the mutant is left
# out rather than shipped as a permanent survivor.
# ---------------------------------------------------------------------------

MUTANTS.append((
    # The defect itself, restored at its root: stop reading `tool_name` and
    # every caller falls back to the platform, which is `win32` whichever tool
    # invoked the hook. That is exactly the pre-#236 behaviour -- a git-bash
    # caller told to run `Remove-Item`.
    "tool_name is never read, so every caller falls back to the platform remedy",
    HOOK,
    '    tool_name = payload.get("tool_name") if isinstance(payload, dict) else None',
    "    tool_name = None",
    TARGETS,
))

MUTANTS.append((
    # The Bash arm stops matching, so a `Bash` payload falls to the platform
    # fallback and a git-bash caller is handed a PowerShell cmdlet again. The
    # narrow version of the mutant above.
    "the Bash arm tests the wrong constant, so git-bash callers get the "
    "PowerShell remedy",
    HOOK,
    "    if tool_name == _BASH_TOOL:",
    "    if tool_name == _POWERSHELL_TOOL:",
    TARGETS,
))

MUTANTS.append((
    # The PowerShell arm hands back the Bash text. Worse than it looks: `rm` is
    # an alias for `Remove-Item` in PowerShell, so "use `rm <link>`" is the bare
    # `Remove-Item` that prompts and dies under `-NonInteractive` 5.1. Killed
    # only because the routing test names the tool explicitly -- the fallback
    # would otherwise mask it on Windows.
    "the PowerShell arm returns the Bash remedy, which aliases to the bare "
    "Remove-Item that fails under 5.1",
    HOOK,
    "        return _PS_REMEDY",
    "        return _RM_REMEDY",
    TARGETS,
))

MUTANTS.append((
    # The fallback inverts. An absent or unrecognised `tool_name` on Windows
    # then yields `rm <link>` -- which, if the caller really was in PowerShell,
    # is the bare `Remove-Item` that fails. The fallback's whole job is to be
    # no worse than the pre-#236 behaviour, and inverting it makes it worse.
    "the platform fallback picks the opposite shell's remedy",
    HOOK,
    '    return _PS_REMEDY if sys.platform == "win32" else _RM_REMEDY',
    '    return _RM_REMEDY if sys.platform == "win32" else _PS_REMEDY',
    TARGETS,
))
