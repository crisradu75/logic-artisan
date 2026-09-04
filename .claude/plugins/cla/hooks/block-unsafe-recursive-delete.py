#!/usr/bin/env python3
"""PreToolUse hook: block an unsafe recursive+force delete (Bash `rm -rf` /
PowerShell `Remove-Item -Recurse -Force`) before it runs.

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

Three independent triggers, any one blocks
---------------------------------------------
0. **The target IS itself a symlink or junction.** Checked against the
   UNRESOLVED path, and first, because `Path.resolve()` follows the reparse
   point — after it, nothing downstream can tell the target was reached through
   a link. This trigger was missing until issue #215: `rm -rf <the junction>`
   was ALLOWED while `rm -rf <its parent>` was blocked, so the guard caught the
   distant shape and permitted the near one, which is the shape that deletes the
   far side.

1. **Worktree path, unconditionally.** The target resolves to a path under
   `.claude/worktrees/<name>` (anywhere in the path, any separator style).
   Tearing down a worktree must go through `git worktree remove`; if that
   fails, the fix is to diagnose what's actually locking the directory (a
   stray process holding a handle inside `node_modules` is the common case),
   not to bypass git's own removal logic with a raw filesystem delete.
2. **Symlink/junction found inside the target.** The target exists as a
   directory and a bounded walk finds a symlink or NTFS junction among its
   entries (at any depth within the scan budget). A recursive delete over a
   tree containing a link risks deleting whatever that link points at instead
   of (or in addition to) the tree itself.

Detection is best-effort, matching this repo's other Bash-command hooks
(block-cd-in-bash.py, block-worktree-path-escape.py): the command is split on
shell metacharacters into segments, each segment is checked for an `rm`
(recursive+force) or `Remove-Item`-family (with -Recurse and -Force)
invocation, and non-flag tokens are taken as candidate target paths. A
sufficiently adversarial command (piped input, a variable holding the path,
process substitution) can still slip past -- this is a backstop, not a
sandbox.

Escape hatch: set `ALLOW_UNSAFE_RM=1` for a deliberate exception.

Exit codes:
  0 - allow (no destructive-delete pattern detected, no candidate path trips
      any trigger, or any parse/FS error -- fail-open, a guard must never
      break normal work)
  2 - block with stderr explaining which trigger fired and how to proceed
"""

from __future__ import annotations

import json
import os
import re
import shlex
import stat
import sys
import time
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

_RM_ALIASES = {"rm", "remove-item", "ri", "del", "erase", "rd", "rmdir"}
_PS_PATH_PARAMS = {"-path", "-literalpath"}

_MAX_SCAN_ENTRIES = 5000
_MAX_SCAN_SECONDS = 4.0

# What to do when the far side of a link cannot be read at all. `True` blocks.
#
# Named rather than written inline because it is a POLICY — the same "an
# undetermined probe must not read as an approval" position the dispatcher takes
# for a guard that could not run — and a name says so where a bare `return True`
# in an except block does not. It is also a convenient single-line mutation
# anchor, though not the only one — and not the best one: `_MISSING_TARGET_ERRORS`
# below is the sharper target, since adding `OSError` to it undoes this policy
# entirely. Both are mutated.
#
# An earlier version of this comment claimed `return True` "occurs four times in
# this file" and that naming the constant was "the only way to anchor a mutant on
# it". Both were false, and the first was reachable only by counting the
# comment's own two lines — which is verbatim the defect CLAUDE.md records, where
# a comment's own text contained the token it declared absent.
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
# JSON on stdin, so a null is trivially reachable. Named because both probes
# use it and because dropping a member from it is one edit that silently
# converts an undetermined answer back into an approval.
_UNREADABLE_ERRORS = (OSError, ValueError)


class _Blocked(Exception):
    """A decided block, carrying its message, raised so the PRINT happens
    outside `main`'s `except OSError` swallow.

    The three block sites used to `print(...)` and `return 2` inside that
    swallow. A `BrokenPipeError` writing to stderr is an `OSError`, so it skipped
    the `return 2`, continued the loop, and fell through to `return 0` — a
    decided BLOCK becoming a clean ALLOW. Measured by injection: with the first
    gate having already judged the target dangerous, `main()` returned 0. A
    CLOSED stderr raises `ValueError` instead, which was not caught at all, so
    the two adjacent stderr failures produced a silent allow and a prompt, and
    neither was the block that had been computed.
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


def _is_worktree_path(resolved: Path) -> bool:
    # Normalize BOTH separators before splitting: a Windows-style path (backslashes)
    # must still be detected when this hook runs on POSIX, where pathlib treats "\"
    # as an ordinary character and would collapse the whole path into one segment.
    segments = [s for s in str(resolved).replace("\\", "/").lower().split("/") if s]
    for i in range(len(segments) - 1):
        if segments[i] == ".claude" and segments[i + 1] == "worktrees":
            return True
    return False


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
    the same answer on the guard's FIRST gate, and the second one silently
    ALLOWED. Measured on both platforms, against a junction and a symlink whose
    parent denies traverse: `_far_side_is_a_directory` answers True (block) for
    exactly that input and is never asked, because this function has already
    returned False and `_target_is_link` short-circuited. The hook exits 0 with
    empty stderr, which is byte-identical to having examined the command and
    approved it.

    A previous round tried to fix that one gate too far downstream, and left a
    comment claiming the conservative gate below handled it. It cannot: it sits
    downstream of this swallow. The undetermined state has to exist HERE, where
    the ambiguity arises.

    ONE `os.lstat` RATHER THAN `islink` THEN `stat`. `os.path.islink` swallows
    EACCES into False before the platform check is even reached, so the POSIX
    arm had the same hole and no amount of Windows-side care would close it.
    `os.lstat` raises instead, and carries `st_file_attributes` on Windows, so
    both platforms are answered from one call and one exception set.
    """
    try:
        st = os.lstat(path)
    except _MISSING_TARGET_ERRORS:
        # Determinate: nothing is there, so it is not a link. This is the
        # ordinary case -- `_tokenize_variants` double-parses every command and
        # feeds a mangled candidate here on every run.
        return False
    except _UNREADABLE_ERRORS:
        # ValueError is not padding: `os.lstat` raises it for an embedded null,
        # and the command arrives as JSON on stdin.
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
        # The path could not be read, so whether it is a link is unknown. This
        # is the gate the policy has to sit at: an unreadable junction is
        # indistinguishable from an ordinary directory here, and treating the
        # two alike is what let `rm -rf` through a link whose parent denied
        # traverse. Deciding it downstream cannot work — every downstream gate
        # is reached only by returning False from this one.
        return _UNDETERMINED_FAR_SIDE_BLOCKS
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


def _contains_symlink(resolved: Path) -> bool:
    """Whether anything INSIDE `resolved` is a link. The target's own link-ness
    is `main`'s business, checked there against the UNRESOLVED path.

    This used to read `if not resolved.is_dir() or _is_link_like(str(resolved))`.
    That second half was dead and wrong in the same breath. Dead, because the one
    call site always passes a `.resolve()`d path and `resolve()` has already
    followed the reparse point — nothing could reach it with a True result, and a
    dangling link short-circuits on `is_dir()` first. Wrong, because what it
    encoded was "the target is itself a link, so allow it", which is precisely
    the case that deletes the far side of a junction.

    Worth stating plainly, because the shape recurs: a test written to cover that
    clause as it stood would have pinned the defect and reported green. The fix
    was to delete it, not to test it.
    """
    if not resolved.is_dir():
        return False
    start = time.monotonic()
    scanned = 0
    try:
        for dirpath, dirnames, filenames in os.walk(resolved, followlinks=False):
            for name in (*dirnames, *filenames):
                scanned += 1
                # `is True`, deliberately, and NOT a truthiness test — the
                # sentinel is truthy, so a bare `if` would silently start
                # blocking here on any unreadable entry. That is the right
                # policy for the ONE target path, where the cost of being
                # conservative is one command; it is the wrong one for a walk
                # over up to `_MAX_SCAN_ENTRIES` entries, where a single
                # transient read error would block a legitimate delete of a
                # large tree. The walk already fails open when its budget runs
                # out, for the same reason.
                if _is_link_like(os.path.join(dirpath, name)) is True:
                    return True
                if scanned >= _MAX_SCAN_ENTRIES or (time.monotonic() - start) >= _MAX_SCAN_SECONDS:
                    return False  # inconclusive -- fail open rather than stall the hook
    except OSError:
        return False
    return False


def main() -> int:
    if os.environ.get("ALLOW_UNSAFE_RM") == "1":
        return 0
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
    # worktree — which is precisely the situation this hook guards, so getting
    # it from the process was wrong in exactly the case that matters: a relative
    # `rm -rf` would resolve against the wrong tree and miss the worktree check.
    # Falls back to the process cwd when the payload omits it (older payload
    # shapes, and the hook's own tests, which set the process cwd instead).
    cwd = payload.get("cwd") if isinstance(payload, dict) else None
    if not isinstance(cwd, str) or not cwd:
        cwd = os.getcwd()

    for raw_target in _extract_target_paths(command):
        try:
            unresolved = raw_target if os.path.isabs(raw_target) else os.path.join(cwd, raw_target)

            # CHECK THE TARGET'S OWN LINK-NESS BEFORE `resolve()` DESTROYS THE
            # EVIDENCE. `Path.resolve()` follows the reparse point, so by the
            # line below `resolved` names the directory on the OTHER SIDE of a
            # junction and nothing downstream can tell it was reached through
            # one. `_contains_symlink` then walks INSIDE that directory, which
            # is why the containing-directory case was caught and this one was
            # not.
            #
            # Measured before the fix: `rm -rf <the junction itself>` exited 0
            # while `rm -rf <its parent>` exited 2 — the guard blocked the
            # distant shape and allowed the near one. This is the shape closest
            # to the incident this whole hook exists for: `rm` from git-bash/MSYS
            # recurses THROUGH a junction as though it were an ordinary
            # directory, so the allowed command deletes the real contents on the
            # far side. The module docstring dates it.
            #
            # PLATFORM NOTE, and it is the half that could not be executed here.
            # The check itself is platform-independent: `_is_link_like` starts
            # with `os.path.islink`, which is true of a POSIX symlink as much as
            # of a Windows junction. What DIFFERS is the danger it guards. On
            # Windows, `rm` from git-bash recurses THROUGH a junction — that is
            # the incident. On POSIX, `rm -rf <a symlink>` unlinks the symlink
            # and leaves its target alone, so blocking there is conservative
            # rather than necessary.
            #
            # Blocking on both anyway, deliberately: `rm -rf` on a symlink is an
            # odd way to spell `rm <symlink>`, the remedy the message gives is
            # correct on either platform, and the trailing-slash spellings
            # (`rm -rf link/`) DO reach through on POSIX. The cost is a possible
            # false positive on a POSIX-only workflow that recursively deletes a
            # symlink on purpose; `ALLOW_UNSAFE_RM=1` is the exit.
            #
            # BOTH BRANCHES ARE NOW EXECUTED. This comment previously ended
            # "the POSIX branch is reasoned, not run", and that disclosure is
            # what got the branch run — it was wrong in a way only execution
            # found. Leaving it in place afterwards would re-arm the same trap
            # pointing the other way: a reader would either distrust a measured
            # branch, or notice it contradicts the coreutils measurement above
            # and trust neither. Windows: real `mklink /J` junctions, eight
            # spellings. POSIX: GNU coreutils 9.7 under WSL, correlating what
            # `rm` does to the far side with what this hook says about it.
            if _target_is_link(unresolved):
                points_at = Path(unresolved).resolve()
                # Only name the far side when it IS somewhere else. For a
                # self-referential link `resolve()` returns the path unchanged,
                # and printing "deletes what it points at -- here, <the same
                # path>" reads as a bug in the message.
                destination = (
                    f" -- here, '{points_at}' --" if points_at != Path(unresolved) else ""
                )
                # The recursing-through behaviour is REAL on Windows/git-bash and
                # is the incident. On POSIX it depends on the spelling: bare
                # `rm -rf link` unlinks the link, while `rm -rf link/` reaches
                # through. The message must not assert the Windows behaviour as
                # universal — on POSIX that tells a developer their safe command
                # caused the data loss and prescribes what they just typed.
                recursion = (
                    "`rm -rf` on it recurses THROUGH the link and deletes what it points at"
                    if sys.platform == "win32"
                    else "a recursive delete can reach THROUGH the link and delete what it "
                         "points at (a trailing slash, `rm -rf <link>/`, does exactly that here)"
                )
                raise _Blocked(
                    f"blocked: recursive+force delete targets '{unresolved}', which is itself a "
                    f"symlink or directory junction. {recursion}{destination} rather than "
                    "removing the link. Remove the link itself instead, with a plain "
                    "non-recursive rm/Remove-Item on just that entry (or `git worktree remove` if "
                    "it is a worktree). This is the shape that destroyed unrelated primary-clone "
                    "files in the incident this hook exists for (see memory "
                    "'feedback-worktree-rmrf-junction-risk'). Override for a deliberate exception "
                    "by setting ALLOW_UNSAFE_RM=1 in the environment. "
                    "(hook: block-unsafe-recursive-delete.py)",
                )

            resolved = Path(unresolved).resolve()

            if _is_worktree_path(resolved):
                raise _Blocked(
                    f"blocked: recursive+force delete targets a path under .claude/worktrees/ "
                    f"('{resolved}'). Never raw-delete a worktree directory -- use "
                    "`git worktree remove <path>` instead. If that fails (e.g. \"Directory not "
                    "empty\"), diagnose what's actually locking it (commonly a stray process "
                    "holding a handle inside node_modules) and clear that, then retry `git "
                    "worktree remove` -- do not bypass it with a raw rm/Remove-Item. See memory "
                    "'feedback-worktree-rmrf-junction-risk' for why: a worktree can contain "
                    "directory junctions/symlinks pointing back into the primary clone, and a "
                    "raw recursive delete can recurse through them and destroy real files "
                    "elsewhere in the repo. Override for a deliberate exception by setting "
                    "ALLOW_UNSAFE_RM=1 in the environment. (hook: block-unsafe-recursive-delete.py)",
                )

            if _contains_symlink(resolved):
                raise _Blocked(
                    f"blocked: recursive+force delete targets '{resolved}', which contains a "
                    "symlink or directory junction. Recursing through it can delete whatever it "
                    "points at instead of (or in addition to) this tree -- this is exactly how "
                    "unrelated primary-clone files were destroyed on 2026-07-19 (see memory "
                    "'feedback-worktree-rmrf-junction-risk'). Unlink the symlink/junction itself "
                    "first (a plain, non-recursive rm/Remove-Item on just that entry), or delete "
                    "only its non-linked subdirectories individually, or ask before proceeding. "
                    "Override for a deliberate exception by setting ALLOW_UNSAFE_RM=1 in the "
                    "environment. (hook: block-unsafe-recursive-delete.py)",
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
            # Measured by injection: with gate 0 having already decided the
            # target was dangerous, `main()` returned 0. A closed stderr raises
            # `ValueError` instead, which is not caught, so the two adjacent
            # stderr failures gave a silent allow and a prompt — neither of them
            # the block that had been computed.
            continue  # this one candidate couldn't be probed -- still check the rest
    return 0


if __name__ == "__main__":
    sys.exit(main())
