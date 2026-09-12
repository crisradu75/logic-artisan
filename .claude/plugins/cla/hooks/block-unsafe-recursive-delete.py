#!/usr/bin/env python3
"""PreToolUse hook: block a recursive+force delete (Bash `rm -rf` / PowerShell
`Remove-Item -Recurse -Force`) whose TARGET is itself a symlink or junction.

Why this exists
----------------
On 2026-07-19, `git worktree remove --force` failed with "Directory not
empty" (a lingering `node_modules`). The fallback was a raw `rm -rf` on the
worktree directory. That worktree contained sibling openspec change folders
and `.claude/decisions/` as untracked paths that were very likely NTFS
directory junctions/symlinks pointing back into the PRIMARY clone (set up
earlier in the session so a sub-agent could read sibling proposals for
context), not real copies. `rm` from git-bash/MSYS is known to recurse
through NTFS junctions as if they were ordinary directories rather than
treating them as a leaf link, so the "cleanup" silently deleted the real
target files in the primary clone. Everything lost was untracked, so git had
no history to recover from -- permanent data loss. See memory
'feedback-worktree-rmrf-junction-risk' for the full incident.

ONE trigger, and why it is one
------------------------------
**The target IS itself a symlink or junction**, checked against the
UNRESOLVED path -- `Path.resolve()` follows the reparse point, and after it
nothing downstream can tell the target was reached through a link.

This hook used to carry two more triggers (a worktree-path rule, and a
bounded walk looking for a link INSIDE the target) plus an `ALLOW_UNSAFE_RM`
escape hatch. All three are gone, deliberately, and the reasoning is worth
keeping because it applies to the next guard as much as to this one.

Two reviews executed the shipped hook across roughly 140 command spellings on
real POSIX symlinks and real NTFS junctions. They found about twenty shapes
that exited 0 and destroyed the far side -- unexpanded `~` and `$HOME`, globs
and braces, a shell metacharacter inside a link's own name, `bash -c`, a bind
mount, PowerShell parameter abbreviation, and a scan budget that failed open
on a large tree (issues #218 and #221, closed with their findings intact).
A later attempt to repair the escape hatch (PR #231, closed) added five NEW
destructive-allow paths of its own, two of them critical -- including one
where a PowerShell user following the block message's own advice disarmed the
guard AND executed the delete.

Both of those arrived with a green test suite and a clean mutation run. The
surface was the defect, not any single patch of it: three triggers and an
override are more behaviour than this guard's evidence supports. Block events
across every session transcript, counted 2026-09-12 by real absolute path,
were 86 in this repo -- which builds and tests the hook, so dominated by its
own test runs -- and 2 in the one consuming repo.

AND THE REMOVED WALK WAS GUARDING A SHAPE `rm` DOES NOT FOLLOW. Measured on
GNU coreutils 9.7 and on real NTFS junctions: `rm -rf <a directory containing
a junction>` leaves the far side intact, with or without a trailing slash.
Only the link AS the target destroys anything, and only then via the trailing
slash. So trigger 2 cost a scan budget, a fail-open exhaustion path and a
bind-mount blind spot to defend against something that did not reproduce as
destructive, while the trigger kept here defends the one shape that does.

That measurement does not reconcile with the 2026-07-19 incident, and this
docstring does not pretend it does. `rm` from git-bash/MSYS is a different
binary from coreutils 9.7 and is the likely explanation; it was not
re-measured, and the question is left open rather than settled in either
direction.

So this file now does one thing, on the shape the incident actually had.
A narrow guard that is right is worth more than a broad one that is not.

There is no escape hatch. What replaces it is a block message that names a
remedy which actually runs on the platform the caller is on -- and that is a
sharper requirement than it sounds, because with no override a wrong remedy
leaves the caller with nowhere to go.

The first version of this shrink got it wrong in exactly that way. It
prescribed "a plain non-recursive rm/Remove-Item", which is right for `rm` and
wrong for Windows PowerShell 5.1, where a bare `Remove-Item <junction>` prompts
and the `-NonInteractive` PowerShell tool therefore fails with "Windows
PowerShell is in NonInteractive mode" having removed nothing. See the `remedy`
branch in `main` for the measured table and for why `-Recurse` WITHOUT `-Force`
is the PowerShell answer. Anyone editing that message must re-measure it;
`test_the_block_message_names_a_remedy_that_works` pins the requirement but
cannot prove a new wording runs.

`git worktree remove` is no longer recommended by any message here, which also
retires the orphaned-worktree dead end of issue #220: this hook no longer fires
on a worktree path merely for being one.

Detection is best-effort, matching this repo's other Bash-command hooks
(block-cd-in-bash.py, block-worktree-path-escape.py): the command is split on
shell metacharacters into segments, each segment is checked for an `rm`
(recursive+force) or `Remove-Item`-family (with -Recurse and -Force)
invocation, and non-flag tokens are taken as candidate target paths. Many
command spellings still slip past -- a variable holding the path, process
substitution, `bash -c`, an unexpanded `~` or glob, a metacharacter inside a
filename. This is a backstop against one known accident, not a sandbox, and
the issues above enumerate the gaps for anyone who needs them.

Exit codes:
  0 - allow (no destructive-delete pattern detected, no candidate path is a
      link, or a PARSE error -- fail-open, a guard must never break normal
      work)
  2 - block with stderr explaining what was found and how to proceed,
      INCLUDING the case where a candidate path could not be read at all.
      That last one is deliberate and is not fail-open: an unreadable probe
      and an approved one are indistinguishable from the outside, so an
      undetermined answer blocks and says so in its own words. A string that
      cannot NAME a file (a glob, a redirection token) is not undetermined --
      it is a determinate not-a-link, and allows.
"""

from __future__ import annotations

import errno
import json
import os
import re
import shlex
import stat
import sys
from pathlib import Path

# A heredoc body (`<<'EOF' ... EOF`, the convention this repo's own
# commit-message commands use) -- see `_strip_non_command_text` below.
_HEREDOC_BODY = re.compile(r"<<-?\s*['\"]?(\w+)['\"]?\r?\n.*?\r?\n\s*\1\b", re.DOTALL)

_SEGMENT_SPLIT = re.compile(r"&&|\|\||[;|\n]")


def _strip_non_command_text(command: str) -> str:
    """Blank out heredoc bodies so PROSE (e.g. a multi-line commit message
    that happens to mention "rm -rf" or split "Remove-Item -Recurse" /
    "-Force" across a line break as an English sentence, not an actual
    invocation) is never scanned as a real command. This repo's own commit
    convention wraps multi-line messages in `git commit -m "$(cat <<'EOF'
    ... EOF)"` -- a heredoc body is never itself parsed as a shell command by
    the outer shell, so it's always safe to blank out.

    Deliberately does NOT strip ordinary single/double-quoted spans: shlex
    already keeps a genuinely quoted argument (e.g. `rm -rf "some path"`) as
    ONE atomic token, so a real destructive command inside quotes is still
    correctly detected. Blind quote-stripping would defeat exactly that case.
    """
    return _HEREDOC_BODY.sub("HEREDOC", command)


# The PowerShell spellings stay. `hooks/hooks.json` wires a PowerShell matcher
# to `dispatch-bash-pretooluse.py`, so this hook is live on PowerShell commands.
# Dropping the PowerShell arm would leave that wiring running a detector that
# cannot match anything it is handed -- coverage removed silently rather than
# deliberately. Unwiring the matcher instead was not an option either: it
# carries six leaf hooks, and only this one was under review.
#
# SAID PLAINLY, BECAUSE "KEPT" OVERSTATES IT: the PowerShell detector misses
# most spellings PowerShell actually binds. `_is_powershell_recursive_force`
# uses `re.fullmatch` on the canonical parameter names, and PowerShell binds
# any unambiguous prefix -- `-Rec -For`, `-r -Force` and friends all ALLOW.
# Measured against a real junction, and pre-existing rather than introduced
# here (#221 lists the family). A prefix match would close it. It is left
# alone because this change only narrows, and widening a detector is the kind
# of edit that earned this hook two bad reviews; keeping the arm is a decision
# not to remove coverage, not a claim that the coverage is good.
_RM_ALIASES = {"rm", "remove-item", "ri", "del", "erase", "rd", "rmdir"}
_PS_PATH_PARAMS = {"-path", "-literalpath"}

# What to do when the far side of a link cannot be read at all. `True` blocks.
#
# Named rather than written inline because it is a POLICY — the same "an
# undetermined probe must not read as an approval" position the dispatcher takes
# for a guard that could not run — and a name says so where a bare `return True`
# in an except block does not. It is also a convenient single-line mutation
# anchor, though not the only one — and not the best one: `_MISSING_TARGET_ERRORS`
# below is the sharper target, since adding `OSError` to it undoes this policy
# entirely. Both are mutated.
_UNDETERMINED_FAR_SIDE_BLOCKS = True

# Returned by `_is_link_like` when a path could not be read at all. Distinct
# from False, which means "read it, not a link" -- conflating the two is what
# let an unreadable junction through.
_LINK_UNDETERMINED = object()

# The errors that mean "there is genuinely nothing at this path" -- as opposed
# to "I could not read it". The distinction is the whole of this hook's
# fail-closed policy, and adding OSError to this tuple would undo it silently,
# which is why it is named and mutated rather than spelled inline twice.
_MISSING_TARGET_ERRORS = (FileNotFoundError, NotADirectoryError)

# The errors that mean "I could not read this path at all". ValueError is not
# padding: os.lstat raises it for an embedded null, and the command arrives as
# JSON on stdin, so a null is trivially reachable. Used by
# `_far_side_is_a_directory`, where the path has ALREADY been confirmed
# link-like, so any read failure there is a genuine unknown.
#
# `_is_link_like` deliberately does NOT use this tuple — see `_UNNAMEABLE_ERRNOS`.
_UNREADABLE_ERRORS = (OSError, ValueError)

# The errno values that mean "this string cannot name a file", as distinct from
# "I could not read the file it names". EINVAL is what Windows raises for a path
# containing `*`, `?`, `<` or `>`; ENAMETOOLONG is the over-long case on both
# platforms.
#
# This distinction only binds in `_is_link_like`, which sees RAW candidate
# tokens straight off the command line — globs, redirection operators, anything
# the tokenizer could not resolve. Treating those as undetermined blocked
# `rm -rf dist/*`. `_far_side_is_a_directory` must NOT copy it: by the time it
# runs, the path has been confirmed link-like, so it IS a real filename and a
# read failure there really is an unknown. Same words, opposite correct answer,
# which is why the two probes have different tuples rather than a shared one.
_UNNAMEABLE_ERRNOS = frozenset({errno.EINVAL, errno.ENAMETOOLONG})


class _Blocked(Exception):
    """A decided block, carrying its message, raised so the PRINT happens
    outside `main`'s `except OSError` swallow.

    The block site used to `print(...)` and `return 2` inside that swallow. A
    `BrokenPipeError` writing to stderr is an `OSError`, so it skipped the
    `return 2`, continued the loop, and fell through to `return 0` — a decided
    BLOCK becoming a clean ALLOW. Measured by injection: with the gate having
    already judged the target dangerous, `main()` returned 0. A CLOSED stderr
    raises `ValueError` instead, which was not caught at all, so the two
    adjacent stderr failures produced a silent allow and a prompt, and neither
    was the block that had been computed.
    """


_SHORT_FLAG_CHARS = set("rRfFidvIu")


def _tokenize_variants(segment: str) -> list[list[str]]:
    """Tokenize `segment` both ways and return whichever variants parse.

    posix=False preserves a literal Windows backslash path (`C:\\Code\\...`,
    the PowerShell tool's native convention) -- POSIX mode treats '\' as an
    escape character and silently eats every separator. posix=True is still
    needed for the equally common POSIX convention of escaping a space in a
    path (`rm -rf /Users/me/My\\ Docs`), which posix=False does NOT collapse
    back into one token. Running both and merging candidate paths (see
    `_extract_target_paths`) covers both platforms without needing to guess
    which shell dialect produced the command.
    """
    variants = []
    for posix in (False, True):
        try:
            tokens = shlex.split(segment, posix=posix)
        except ValueError:
            continue  # unbalanced quote etc. -- best-effort, skip this variant
        cleaned = []
        for t in tokens:
            if len(t) >= 2 and t[0] == t[-1] and t[0] in ("'", '"'):
                t = t[1:-1]
            cleaned.append(t)
        variants.append(cleaned)
    return variants


def _rm_command_index(tokens: list[str]) -> int | None:
    for i, tok in enumerate(tokens):
        base = tok.replace("\\", "/").rsplit("/", 1)[-1].lower()
        if base in _RM_ALIASES:
            return i
    return None


def _is_short_flag_cluster(t: str) -> bool:
    # Only a genuine short-option cluster (e.g. "-rf", "-Rf") counts -- a long
    # PowerShell-style flag like "-Force"/"-Recurse" must NOT be misread as a
    # cluster just because the word happens to contain the letter 'r' or 'f'.
    return t.startswith("-") and not t.startswith("--") and len(t) > 1 and all(
        c in _SHORT_FLAG_CHARS for c in t[1:]
    )


def _is_bash_recursive_force(flag_tokens: list[str]) -> bool:
    has_r = any(
        t in ("-r", "-R", "--recursive") or (_is_short_flag_cluster(t) and "r" in t[1:].lower())
        for t in flag_tokens
    )
    has_f = any(
        t in ("-f", "--force") or (_is_short_flag_cluster(t) and "f" in t[1:].lower())
        for t in flag_tokens
    )
    return has_r and has_f


def _is_powershell_recursive_force(flag_tokens: list[str]) -> bool:
    has_recurse = any(re.fullmatch(r"-recurse(:\$true)?", t, re.IGNORECASE) for t in flag_tokens)
    has_force = any(re.fullmatch(r"-force(:\$true)?", t, re.IGNORECASE) for t in flag_tokens)
    return has_recurse and has_force


def _candidate_paths(tokens: list[str], start: int) -> list[str]:
    paths: list[str] = []
    i = start
    while i < len(tokens):
        tok = tokens[i]
        if tok.lower() in _PS_PATH_PARAMS and i + 1 < len(tokens):
            paths.append(tokens[i + 1])
            i += 2
            continue
        if not tok.startswith("-"):
            paths.append(tok)
        i += 1
    return paths


def _extract_target_paths(command: str) -> list[str]:
    targets: list[str] = []
    seen: set[str] = set()
    for segment in _SEGMENT_SPLIT.split(_strip_non_command_text(command)):
        for tokens in _tokenize_variants(segment):
            idx = _rm_command_index(tokens)
            if idx is None:
                continue
            rest = tokens[idx + 1 :]
            if not (_is_bash_recursive_force(rest) or _is_powershell_recursive_force(rest)):
                continue
            for p in _candidate_paths(tokens, idx + 1):
                if p not in seen:
                    seen.add(p)
                    targets.append(p)
    return targets


_FILE_ATTRIBUTE_REPARSE_POINT = 0x400


def _is_link_like(path: str):
    """Three states, not two: True / False / `_LINK_UNDETERMINED`.

    True for a real symlink OR (Windows) an NTFS junction. `os.path.islink`
    alone only recognizes the symlink reparse tag -- a junction (`mklink /J`,
    no elevated privileges, and the likely mechanism behind the incident this
    hook exists to prevent) uses a DIFFERENT tag and is invisible to it.
    `st_file_attributes`'s reparse-point bit catches both.

    WHY THREE STATES. This returned a plain bool, swallowing every probe error
    into False -- so "this is not a link" and "I could not read this path" were
    the same answer, and the hook silently ALLOWED. Measured on both platforms,
    against a junction and a symlink whose parent denies traverse:
    `_far_side_is_a_directory` answers True (block) for exactly that input and
    is never asked, because this function has already returned False and
    `_target_is_link` short-circuited. The hook exits 0 with empty stderr,
    which is byte-identical to having examined the command and approved it.

    ONE `os.lstat` RATHER THAN `islink` THEN `stat`. `os.path.islink` swallows
    EACCES into False before the platform check is even reached, so the POSIX
    arm had the same hole and no amount of Windows-side care would close it.
    `os.lstat` raises instead, and carries `st_file_attributes` on Windows, so
    both platforms are answered from one call.

    THREE OUTCOMES NEED THREE ERROR CLASSES, NOT TWO. The first version of this
    split them as "missing" versus "everything else is undetermined", and on
    Windows that second class is dominated by ordinary commands rather than by
    unreadable links: `os.lstat` on `dist\\*` raises `OSError(EINVAL)`, because
    `*` cannot name an NTFS file. Measured: `rm -rf dist/*`,
    `rm -rf node_modules/*`, `rm -rf build/*.log` and
    `Remove-Item -Recurse -Force .\\dist\\*` all began to BLOCK — 7 of 16
    everyday commands — with a message asserting the target was a junction. This
    hook ships to every consuming repo, and the launcher runs
    `--permission-mode auto` where the hooks ARE the safety layer, so that made
    `rm -rf dist/*` unrunnable.

    A string that CANNOT NAME A FILE is a determinate "not a link", not an
    unknown. Only a read failure on a path that could be named is undetermined.
    """
    try:
        st = os.lstat(path)
    except _MISSING_TARGET_ERRORS:
        # Determinate: nothing is there, so it is not a link. This is the
        # ordinary case -- `_tokenize_variants` double-parses every command and
        # feeds a mangled candidate here on every run.
        return False
    except OSError as exc:
        if exc.errno in _UNNAMEABLE_ERRNOS:
            # A glob, a redirection token, an over-long path: not a filename at
            # all, so it is determinately not a link. Blocking here is a pure
            # false positive on a guard that blocks.
            return False
        return _LINK_UNDETERMINED
    except ValueError:  # an embedded null in the path
        # The command arrives as JSON on stdin, so a null is reachable, and it
        # IS a genuine unknown -- the string names something the filesystem
        # refuses to discuss rather than something absent.
        #
        # The trailing comment is load-bearing, not decoration: `_tokenize_variants`
        # has its own `except ValueError:` at a deeper indent, and `mutate.py`
        # matches anchors as SUBSTRINGS, so the four-space form is contained in
        # the eight-space one and a mutant on it is refused as ambiguous.
        return _LINK_UNDETERMINED
    if stat.S_ISLNK(st.st_mode):
        return True
    if sys.platform != "win32":
        return False
    return bool(getattr(st, "st_file_attributes", 0) & _FILE_ATTRIBUTE_REPARSE_POINT)


def _target_is_link(unresolved: str) -> bool:
    """Whether the delete TARGET is itself a link we must not recurse through.

    Two things this gets right that a bare `_is_link_like(unresolved)` does not.

    TRAILING SEPARATORS. POSIX `lstat` resolves through a trailing slash, so
    `os.path.islink('link/')` is False while `os.path.islink('link')` is True —
    and `rm -rf link/` is the spelling that actually reaches through on POSIX.
    Measured on GNU coreutils: `rm -rf link` unlinks the link and the far side
    survives, while `rm -rf link/` leaves the link and DELETES the far side's
    contents. So the unstripped check blocked the safe spelling and allowed the
    destructive one — a precise inversion, on the platform this fix could not
    execute on. Stripped by hand rather than with `os.path.normpath`, which also
    collapses `..` and would rewrite `link/..` into the parent, losing the very
    thing being asked about. Windows is unaffected either way: `os.stat` reads
    the reparse point through a trailing separator.

    IT MUST RESOLVE TO A DIRECTORY. A dangling link points at nothing and a link
    to a FILE has no far side to recurse into, so neither can produce the
    incident, and blocking them is a pure false positive on a guard that ships
    and blocks.

    THAT IS ALL IT BUYS, AND AN EARLIER VERSION OF THIS COMMENT CLAIMED MORE. It
    offered `rm -rf ~/.config/nvim` on a dotfiles symlink and
    `rm -rf node_modules/<pkg>` in a workspace as the false positives being
    fixed. Both are symlinks to DIRECTORIES, so both still block, before and
    after — measured against both commits. Those are real false positives and
    this check does not address them; if they matter, they need their own
    decision, not a sentence in a docstring that reads as though they were
    handled.
    """
    probe = unresolved
    # ONE loop over both rules, alternating until neither applies. They used to
    # run in sequence — the `/.` strip once, then the separator loop — so any
    # spelling with a separator AFTER the dot escaped: `link/.` was recognised
    # and `link/./` was not, which is the inconsistency the `/.` rule exists to
    # remove. Measured on POSIX: `link/.` blocked, `link/./` allowed, `link/./.`
    # allowed. No data is at risk in those cases (`rm` refuses any `.` component,
    # measured), but a rule that fires on one spelling and not its neighbour is
    # worse than no rule — it reads as coverage.
    #
    # Terminate on the ROOT rather than on a length. `len(probe) > 3` was
    # `len("C:\\")` — Windows-shaped, and POSIX's root is one character, so it
    # refused to strip `/a/` and left `/a//` carrying a separator. A symlink at
    # a short absolute path spelled `rm -rf /a/` then went unrecognised, which
    # is precisely the spelling this function exists for. `dirname` of a root is
    # itself, on every platform and for UNC paths, so this needs no magic number.
    while True:
        if probe[-1:] in ("/", "\\") and os.path.dirname(probe) != probe:
            stripped = probe[:-1]
            if not stripped or stripped == os.path.dirname(stripped):
                break
            probe = stripped
        elif probe.endswith(("/.", "\\.")) and len(probe) > 2:
            probe = probe[:-2]
        else:
            break
    verdicts = (_is_link_like(unresolved), _is_link_like(probe))
    if _LINK_UNDETERMINED in verdicts:
        # Propagate the sentinel rather than collapsing it to True, so `main`
        # can say WHICH thing it found. Returning True here made an unreadable
        # path share the confirmed-link message, asserting something the code
        # never determined.
        #
        # An earlier comment here said "every downstream gate is reached only by
        # returning False from this one". That was true before the sentinel
        # existed and false after it: `_far_side_is_a_directory` is downstream and
        # is reached only when this returns a decided TRUE.
        return _LINK_UNDETERMINED if _UNDETERMINED_FAR_SIDE_BLOCKS else False
    if not any(verdicts):
        return False
    return _far_side_is_a_directory(probe)


def _far_side_is_a_directory(probe: str) -> bool:
    """Whether the link's target is a directory — and BLOCK when that cannot be
    determined, rather than allowing.

    `os.path.isdir` was the first spelling of this and it is wrong here for one
    reason: it swallows every error and returns False, so "the far side is a
    file" and "the far side could not be read" become the same answer, and the
    second one silently ALLOWS. Measured: a symlink to a directory under a
    mode-000 parent was blocked before this check existed and allowed after it —
    a coverage regression introduced by the check meant to reduce false
    positives. A junction into a clone whose far side cannot be stat'd is
    exactly the shape the hook exists for.

    That is the same argument `_is_link_like`'s own swallow makes one gate up,
    and it applies identically here. Only a genuinely MISSING target is treated
    as "nothing to recurse into"; anything else unreadable is treated as a
    directory and blocks.
    """
    try:
        return stat.S_ISDIR(os.stat(probe).st_mode)
    except _MISSING_TARGET_ERRORS:
        # The link points at nothing. A dangling link cannot destroy a far side
        # that does not exist, so this is a real allow rather than an unknown.
        return False
    except _UNREADABLE_ERRORS:
        return _UNDETERMINED_FAR_SIDE_BLOCKS


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0
    tool_input = payload.get("tool_input", {}) if isinstance(payload, dict) else {}
    command = tool_input.get("command") if isinstance(tool_input, dict) else None
    if not isinstance(command, str) or not command.strip():
        return 0

    # Resolve a relative delete target against the SESSION's directory, not this
    # hook process's. The two differ whenever the session is in a linked
    # worktree, where a relative `rm -rf` would otherwise resolve against the
    # wrong tree and probe the wrong path. Falls back to the process cwd when
    # the payload omits it (older payload shapes, and the hook's own tests,
    # which set the process cwd instead).
    cwd = payload.get("cwd") if isinstance(payload, dict) else None
    if not isinstance(cwd, str) or not cwd:
        cwd = os.getcwd()

    for raw_target in _extract_target_paths(command):
        try:
            unresolved = raw_target if os.path.isabs(raw_target) else os.path.join(cwd, raw_target)

            # CHECK THE TARGET'S OWN LINK-NESS AGAINST THE UNRESOLVED PATH.
            # `Path.resolve()` would follow the reparse point, and after it
            # nothing can tell the target was reached through one.
            #
            # Measured before this trigger existed: `rm -rf <the junction
            # itself>` exited 0 while `rm -rf <its parent>` exited 2 — the guard
            # blocked the distant shape and allowed the near one. This is the
            # shape closest to the incident this whole hook exists for: `rm`
            # from git-bash/MSYS recurses THROUGH a junction as though it were
            # an ordinary directory, so the allowed command deletes the real
            # contents on the far side.
            #
            # PLATFORM NOTE. The check itself is platform-independent:
            # `_is_link_like` reads one `os.lstat`, whose symlink bit is true of
            # a POSIX symlink and whose reparse bit is true of a Windows
            # junction. What DIFFERS is the danger it guards. On Windows, `rm`
            # from git-bash recurses THROUGH a junction — that is the incident.
            # On POSIX, `rm -rf <a symlink>` unlinks the symlink and leaves its
            # target alone, so blocking there is conservative rather than
            # necessary.
            #
            # Blocking on both anyway, deliberately: `rm -rf` on a symlink is an
            # odd way to spell `rm <symlink>`, the remedy the message gives is
            # correct on either platform, and the trailing-slash spellings
            # (`rm -rf link/`) DO reach through on POSIX.
            #
            # BOTH BRANCHES ARE EXECUTED. This comment previously ended "the
            # POSIX branch is reasoned, not run", and that disclosure is what got
            # the branch run — it was wrong in a way only execution found.
            # Windows: real `mklink /J` junctions, eight spellings. POSIX: GNU
            # coreutils 9.7 under WSL, correlating what `rm` does to the far side
            # with what this hook says about it.
            verdict = _target_is_link(unresolved)
            if verdict is _LINK_UNDETERMINED:
                # ITS OWN MESSAGE. The confirmed-link text was reused here, so a
                # path the hook could not READ was told it "is itself a symlink
                # or directory junction" and to "remove the link itself
                # instead" — an assertion the code had not made and advice that
                # cannot be followed. A correct fail-closed policy explained
                # wrongly is how a real block gets dismissed as a known-bogus
                # one, which costs exactly what the policy buys.
                raise _Blocked(
                    f"blocked: recursive+force delete targets '{unresolved}', which this guard "
                    "could not examine -- reading it failed, so whether it is a symlink or "
                    "directory junction is UNKNOWN. Blocking rather than allowing, because an "
                    "unreadable probe and an approved one are indistinguishable from the "
                    "outside. Check the path exists and is readable, then retry. "
                    "(hook: block-unsafe-recursive-delete.py)"
                )
            if verdict:
                # Computed INSIDE its own try, not on the way to the raise. The
                # decision was already hoisted out of the `except OSError`
                # swallow, but this line was left in front of it — and it is the
                # line that touches the filesystem. `Path.resolve()` raises
                # `ValueError` on an embedded null, which neither handler
                # catches, so a DECIDED block became an uncaught raise: the
                # dispatcher then told the user "this guard could not run",
                # which is the opposite of what happened.
                try:
                    points_at = Path(unresolved).resolve()
                except (OSError, ValueError):
                    points_at = Path(unresolved)
                # Only name the far side when it IS somewhere else. For a
                # self-referential link `resolve()` returns the path unchanged,
                # and printing "deletes what it points at -- here, <the same
                # path>" reads as a bug in the message.
                destination = (
                    f" -- here, '{points_at}' --" if points_at != Path(unresolved) else ""
                )
                # THE TRAILING SLASH IS THE DISCRIMINATOR, NOT THE PLATFORM.
                # This branched on `sys.platform` and asserted that Windows
                # recurses through unconditionally while POSIX only does so with
                # a trailing slash. Measured on GNU coreutils 9.7 and on real
                # NTFS junctions, the two behave the same way: `rm -rf <link>`
                # unlinks the link and the far side survives; `rm -rf <link>/`
                # destroys the far side. So the spelling decides it on both.
                #
                # UNRESOLVED, and stated rather than papered over: that does not
                # reconcile with the 2026-07-19 incident, which did happen. `rm`
                # from git-bash/MSYS is not the same binary as coreutils 9.7 and
                # is the likely explanation, but it was not re-measured here.
                # The hook blocks both spellings either way, so the ambiguity
                # costs nothing operationally -- it only means the message must
                # not tell a developer which of their two spellings was safe.
                recursion = (
                    "A recursive delete can reach THROUGH the link and delete what it points at "
                    "(a trailing slash -- `rm -rf <link>/` -- does exactly that; the bare "
                    "spelling unlinks the link instead, and this guard blocks both rather than "
                    "relying on which one you typed)"
                )
                # THE REMEDY IS PLATFORM-SPECIFIC, AND GETTING IT WRONG HERE IS
                # THE WHOLE COST OF HAVING NO ESCAPE HATCH. This message once
                # prescribed "a plain non-recursive rm/Remove-Item". The `rm`
                # half is right. The `Remove-Item` half is WRONG on Windows
                # PowerShell 5.1: a bare `Remove-Item <junction>` prompts, and
                # Claude Code's PowerShell tool runs `-NonInteractive`, so it
                # dies with "Windows PowerShell is in NonInteractive mode" and
                # removes nothing. `hooks.json` wires that tool to this
                # dispatcher, so it is a live path, and a blocked caller
                # following this text got an error instead of a way forward --
                # the same pathology as issue #220, reintroduced by the change
                # that claimed to retire it.
                #
                # Measured, `-NonInteractive`, against a real junction:
                #
                #   remedy                      WinPS 5.1   pwsh 7
                #   Remove-Item <j>             FAILS       works
                #   Remove-Item -Force <j>      FAILS       works
                #   Remove-Item -Recurse <j>    works       works
                #   cmd /c rmdir <j>            works       works
                #
                # The far side survived in every one of those, including the
                # `-Recurse` forms -- removing the link is not recursing through
                # it. So `-Recurse` WITHOUT `-Force` is the remedy, on a hook
                # whose trigger is `-Recurse` WITH `-Force`. That reads like a
                # contradiction and is not: this guard fires on the recursive
                # FORCED delete, and the unforced one is what PowerShell needs
                # to drop a junction without prompting.
                #
                # Named per-platform rather than listing both, because a message
                # offering a menu is one the reader has to test.
                remedy = (
                    "Remove the link itself instead: `Remove-Item -Recurse <link>` (WITHOUT "
                    "-Force -- that is this guard's trigger, and the unforced form is what "
                    "removes a junction without prompting), or `cmd /c rmdir <link>`. Both "
                    "leave the far side untouched."
                    if sys.platform == "win32"
                    else "Remove the link itself instead, with a plain non-recursive `rm "
                         "<link>` on just that entry."
                )
                raise _Blocked(
                    f"blocked: recursive+force delete targets '{unresolved}', which is itself a "
                    f"symlink or directory junction. {recursion}{destination} rather than "
                    f"removing the link. {remedy} This is the shape that "
                    "destroyed unrelated primary-clone files in the incident this hook exists "
                    "for (see memory 'feedback-worktree-rmrf-junction-risk'). "
                    "(hook: block-unsafe-recursive-delete.py)",
                )
        except _Blocked as blocked:
            # OUTSIDE the OSError swallow below, which is the whole point: a
            # failure writing this message can no longer erase the decision that
            # produced it. If the write itself raises, that propagates out of
            # `main` and the dispatcher escalates to a prompt — never a silent
            # allow.
            print(blocked.args[0], file=sys.stderr)
            return 2
        except OSError:
            # ONLY the filesystem probing above is inside this swallow. Every
            # `print(...)` + `return 2` was once inside it too, and that is a
            # decided BLOCK sitting under `except OSError: continue` — a
            # `BrokenPipeError` writing the message (an OSError) skipped the
            # `return 2`, continued the loop, and fell through to `return 0`.
            # Measured by injection: with the gate having already decided the
            # target was dangerous, `main()` returned 0. A closed stderr raises
            # `ValueError` instead, which is not caught, so the two adjacent
            # stderr failures gave a silent allow and a prompt — neither of them
            # the block that had been computed.
            continue  # this one candidate couldn't be probed -- still check the rest
    return 0


if __name__ == "__main__":
    sys.exit(main())
