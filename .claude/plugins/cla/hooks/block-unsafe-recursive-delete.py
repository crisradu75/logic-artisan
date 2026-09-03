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
      either trigger, or any parse/FS error -- fail-open, a guard must never
      break normal work)
  2 - block with stderr explaining which trigger fired and how to proceed
"""

from __future__ import annotations

import json
import os
import re
import shlex
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


def _is_link_like(path: str) -> bool:
    """True for a real symlink OR (Windows only) an NTFS junction/mount point.

    `os.path.islink()` alone only recognizes the symlink reparse tag -- an
    NTFS directory junction (created via `mklink /J`, needs no elevated
    privileges, and the most likely real mechanism behind the 2026-07-19
    incident this hook exists to prevent) uses a DIFFERENT reparse tag and is
    silently invisible to it. `st_file_attributes`'s reparse-point bit catches
    both.
    """
    if os.path.islink(path):
        return True
    if sys.platform != "win32":
        return False
    try:
        attrs = os.stat(path, follow_symlinks=False).st_file_attributes
    except (OSError, AttributeError):
        return False
    return bool(attrs & _FILE_ATTRIBUTE_REPARSE_POINT)


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
                if _is_link_like(os.path.join(dirpath, name)):
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
            resolved = Path(unresolved).resolve()

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
            # symlink on purpose; `ALLOW_UNSAFE_RM=1` is the exit. Verified by
            # execution on Windows with a real junction only — the POSIX branch
            # is reasoned, not run.
            if _is_link_like(unresolved):
                print(
                    f"blocked: recursive+force delete targets '{unresolved}', which is itself a "
                    "symlink or directory junction. `rm -rf` on it recurses THROUGH the link and "
                    "deletes what it points at -- here, "
                    f"'{resolved}' -- rather than removing the link. Unlink it instead with a "
                    "plain, non-recursive rm/Remove-Item on just that entry (or `git worktree "
                    "remove` if it is a worktree). This is the shape that destroyed unrelated "
                    "primary-clone files on 2026-07-19 (see memory "
                    "'feedback-worktree-rmrf-junction-risk'). Override for a deliberate exception "
                    "by setting ALLOW_UNSAFE_RM=1 in the environment. "
                    "(hook: block-unsafe-recursive-delete.py)",
                    file=sys.stderr,
                )
                return 2

            if _is_worktree_path(resolved):
                print(
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
                    file=sys.stderr,
                )
                return 2

            if _contains_symlink(resolved):
                print(
                    f"blocked: recursive+force delete targets '{resolved}', which contains a "
                    "symlink or directory junction. Recursing through it can delete whatever it "
                    "points at instead of (or in addition to) this tree -- this is exactly how "
                    "unrelated primary-clone files were destroyed on 2026-07-19 (see memory "
                    "'feedback-worktree-rmrf-junction-risk'). Unlink the symlink/junction itself "
                    "first (a plain, non-recursive rm/Remove-Item on just that entry), or delete "
                    "only its non-linked subdirectories individually, or ask before proceeding. "
                    "Override for a deliberate exception by setting ALLOW_UNSAFE_RM=1 in the "
                    "environment. (hook: block-unsafe-recursive-delete.py)",
                    file=sys.stderr,
                )
                return 2
        except OSError:
            continue  # this one candidate couldn't be resolved -- still check the rest
    return 0


if __name__ == "__main__":
    sys.exit(main())
