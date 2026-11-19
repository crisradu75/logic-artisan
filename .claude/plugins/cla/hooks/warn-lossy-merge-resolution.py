#!/usr/bin/env python3
"""PreToolUse hook: WARN (never block) before a merge commit whose staged
result lacks lines the merged-in side added.

Why
---
`skills/_shared/references/conflict-resolution.md` §3 says to resolve hunk by
hunk and to take a whole side (`git checkout --ours <file>`) only when the
whole file is genuinely one side's. In one session an orchestrator resolving
merge conflicts broke that rule four times, each time dropping lines the other
side had added; the rule was prose, and prose did not stop it. This hook is the
mechanical half: before the merge is committed, it compares what is staged with
what the other side added, and names the lines that are missing.

When it runs
------------
On a Bash command holding a `git commit` (not `--dry-run`) or a
`git merge --continue`, found with `_shell_text.GitInvocation` in the command
and in each shell-wrapper body (`_shell_read.guard_parts`: `bash -c "..."`,
`eval`, ...). The dispatcher lists this hook in `_READS_COMMAND_ONLY` and the
hook reads the wrapper bodies itself, so its git calls happen once per
command, for each distinct directory a commit runs in, not once per part.
Silent unless a merge is in progress there: `MERGE_HEAD` resolves.

What it compares
----------------
The merge base is `git merge-base HEAD MERGE_HEAD`. The files checked are the
ones the other side changed since the base (`git diff --name-only base
MERGE_HEAD`) whose staged content differs from the other side's
(`git diff --cached --name-only MERGE_HEAD`): every file a resolution touched,
including one taken whole from our side, which differs from only one parent
and so would be missed by a "differs from both parents" test. A file the other
side changed and the merge took cleanly equals `MERGE_HEAD` and is skipped.

For each file, lines are compared as counts of identical text (trailing
whitespace ignored, blank lines skipped), read from one `git cat-file --batch`
call: the base, our side (`HEAD`), their side (`MERGE_HEAD`) and the result. A
line their side added (`theirs > base`) is lost when the result holds fewer
copies than their side does AND fewer than our side plus their additions
(`result < theirs` and `result < ours + theirs - base`). The first condition
keeps a line both sides added identically, which git merges into one copy;
the second keeps a line their side added where ours deleted a base copy.

The result is the staged content (index stage 0). For `git commit -a` it is the
working-tree file, which `-a` stages. For a path still unmerged when the hook
runs (a `git add` later in the same command will stage it) it is the
working-tree file too. A file still holding conflict markers holds both sides'
lines between them, so it reports nothing lost; the commit is refused or
commits the markers, which is not this hook's subject.

A line replaced on purpose is reported too. The hook cannot tell a deliberate
replacement from an accidental drop, and a warning costs one read; the
message says to state a deliberate drop in the commit message.

The warning names up to `MAX_FILES_SHOWN` files and up to `MAX_LINES_SHOWN`
lost lines each.

Limits
------
- It reads the repository as it stands when the command starts. A resolution
  made and committed in one command (`git checkout --ours f && git add f &&
  git commit`) is seen only as far as the working tree already holds it.
- It cannot see git commands run inside a wrapper script (`./merge.sh`), a git
  alias, or another program that runs git: only the command text and its shell
  wrapper bodies are read.
- Merges only. A rebase or cherry-pick has no `MERGE_HEAD`.
- Identical text is the unit, not position: a lost line whose text survives
  elsewhere in the file in enough copies is not reported.

Best-effort and advisory: unparseable input, no git, not a repository,
`--git-dir`/`--work-tree`/`GIT_DIR=` (the repository cannot be named), a git
error or timeout, or any exception exits 0 silently, as every warn hook does.
All git calls for one command share `GIT_BUDGET_SECONDS`
(`_dispatch_lib.HOOK_WORST_CASE_SECONDS` records the same figure), and the
files and bytes read are capped. Exit 0 always; the warning goes to stderr,
which the dispatcher turns into context.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

_HOOKS_DIR = str(Path(__file__).resolve().parent)
if _HOOKS_DIR not in sys.path:
    sys.path.insert(0, _HOOKS_DIR)

from _shell_text import GitInvocation, strip_quoted_spans  # noqa: E402
from _git_commit_args import (  # noqa: E402
    _GIT_ENV_REPO,
    ParseError,
    _heredoc_spans,
    command_words,
    directory_of,
    read_commit,
)

try:  # the wrapper bodies; without them the command alone is read
    from _shell_read import guard_parts as _guard_parts
except Exception:  # noqa: BLE001 -- a warn hook degrades, it does not fail
    _guard_parts = None

# Total wall time for every git call this hook makes on one command, shared.
GIT_BUDGET_SECONDS = 4.0
MAX_DIRECTORIES = 4
MAX_FILES = 100
MAX_TOTAL_BYTES = 8_000_000
MAX_FILES_SHOWN = 10
MAX_LINES_SHOWN = 5

_MATCHER = GitInvocation(r"(commit|merge)(?=$|[ \t\r\n;&|()<>])", capture_opts=True)
# `git cat-file --batch`'s header for an object it found: `<oid> <type> <size>`.
# Anything else (`<spec> missing`, `<spec> ambiguous`) is no object, and is told
# apart by shape, since a spec holds a path and a path can hold spaces.
_FOUND = re.compile(rb"[0-9a-f]{40,64} (\w+) (\d+)")


class _Clock:
    def __init__(self) -> None:
        self.deadline = time.monotonic() + GIT_BUDGET_SECONDS

    def left(self) -> float:
        return self.deadline - time.monotonic()


def _git(directory: str, args: list[str], clock: _Clock, stdin: bytes | None = None) -> bytes | None:
    """git's stdout as bytes, or None on any failure, a non-zero exit or no time left."""
    timeout = clock.left()
    if timeout <= 0:
        return None
    try:
        result = subprocess.run(
            ["git", "--no-optional-locks", "-C", directory, *args],
            input=stdin, capture_output=True, timeout=timeout,
        )
    except (OSError, subprocess.SubprocessError, ValueError):
        return None
    return result.stdout if result.returncode == 0 else None


def _directories(text: str, cwd: str) -> dict[str, bool]:
    """`{directory: takes the working tree (-a)}` for each `git commit` (not a
    dry run) and `git merge --continue` in `text`."""
    found: dict[str, bool] = {}
    base: str | None = None if _GIT_ENV_REPO.search(text) else cwd
    if base is None:
        return found
    bodies = _heredoc_spans(text)
    b = 0
    consumed = 0
    for match in _MATCHER.finditer(strip_quoted_spans(text)):
        if match.start() < consumed:
            continue
        while b < len(bodies) and bodies[b][1] <= match.start():
            b += 1
        if b < len(bodies) and bodies[b][0] <= match.start():
            continue  # text inside a heredoc body is data, not a command
        opts_text = text[match.start(1):match.end(1)]
        try:
            if match.group(2) == "commit":
                commit = read_commit(text, match.start(), match.end(), opts_text, base)
                consumed = commit.end
                if commit.refused or commit.dry_run or commit.directory is None:
                    continue
                directory, whole_tree = commit.directory, commit.all_files
            else:
                words, _bodies, consumed = command_words(text, match.end())
                if not any(w.text == "--continue" for w in words):
                    continue
                directory, whole_tree = directory_of(base, opts_text), False
                if directory is None:
                    continue
        except ParseError:
            break
        found[directory] = found.get(directory, False) or whole_tree
    return found


def _names(raw: bytes | None) -> list[str]:
    return [n for n in (raw or b"").decode("utf-8", errors="replace").split("\0") if n]


def _read_batch(directory: str, specs: list[str], clock: _Clock) -> list[bytes | None] | None:
    """The content of each `<rev>:<path>` spec, None for a missing one; None
    overall when git failed or the output could not be read."""
    out = _git(directory, ["cat-file", "--batch"], clock, ("\n".join(specs) + "\n").encode("utf-8"))
    if out is None:
        return None
    contents: list[bytes | None] = []
    pos = 0
    for _spec in specs:
        nl = out.find(b"\n", pos)
        if nl < 0:
            return None
        header = _FOUND.fullmatch(out[pos:nl])
        pos = nl + 1
        if header is None:
            contents.append(None)  # `<spec> missing`, or ambiguous: no object
            continue
        size = int(header.group(2))
        # Not a blob (a tree, a submodule's commit): nothing to compare.
        contents.append(out[pos:pos + size] if header.group(1) == b"blob" else None)
        pos += size + 1
    return contents


def _lines(blob: bytes | None) -> list[str]:
    if blob is None:
        return []
    text = blob.decode("utf-8", errors="replace")
    return [line.rstrip() for line in text.splitlines() if line.strip()]


def _lost(base: bytes | None, ours: bytes | None, theirs: bytes | None, result: bytes) -> list[str]:
    """The lines `theirs` added since `base` that `result` lacks, in `theirs`'s order."""
    b, o, r = Counter(_lines(base)), Counter(_lines(ours)), Counter(_lines(result))
    theirs_lines = _lines(theirs)
    t = Counter(theirs_lines)
    lost: list[str] = []
    for line in dict.fromkeys(theirs_lines):
        if t[line] > b[line] and r[line] < t[line] and r[line] < o[line] + t[line] - b[line]:
            lost.append(line)
    return lost


def _check(directory: str, whole_tree: bool, clock: _Clock) -> list[tuple[str, list[str]]]:
    """`(path, lost lines)` for each file in `directory`'s merge that lost any."""
    head = _git(directory, ["rev-parse", "--show-toplevel", "MERGE_HEAD"], clock)
    if head is None:
        return []  # no merge in progress, or not a repository
    root = head.decode("utf-8", errors="replace").splitlines()[0]
    base_out = _git(directory, ["merge-base", "HEAD", "MERGE_HEAD"], clock)
    if base_out is None:
        return []
    base = base_out.decode("ascii", errors="replace").strip()
    theirs_changed = _names(_git(
        directory, ["diff", "--name-only", "-z", "--no-renames", "--no-ext-diff", base, "MERGE_HEAD"], clock,
    ))
    if not theirs_changed:
        return []
    differs = set(_names(_git(
        directory, ["diff", "--cached", "--name-only", "-z", "--no-renames", "--no-ext-diff", "MERGE_HEAD"], clock,
    )))
    paths = [p for p in theirs_changed if p in differs and "\n" not in p][:MAX_FILES]
    if not paths:
        return []
    revs = (f"{base}:", "HEAD:", "MERGE_HEAD:", ":0:", ":2:", ":3:")
    contents = _read_batch(directory, [rev + p for p in paths for rev in revs], clock)
    if contents is None:
        return []
    found: list[tuple[str, list[str]]] = []
    budget = MAX_TOTAL_BYTES
    for k, path in enumerate(paths):
        base_blob, ours, theirs, staged, stage2, stage3 = contents[k * 6:k * 6 + 6]
        unmerged = staged is None and (stage2 is not None or stage3 is not None)
        if whole_tree or unmerged:
            try:
                with open(os.path.join(root, path), "rb") as handle:
                    result = handle.read(budget + 1)
            except OSError:
                result = None if unmerged else b""  # `-a` stages a deleted file's deletion
        else:
            result = staged if staged is not None else b""  # absent from the index: deleted
        if result is None:
            continue
        budget -= len(result) + sum(len(x or b"") for x in (base_blob, ours, theirs))
        if budget < 0:
            break
        if any(b"\0" in (x or b"") for x in (base_blob, ours, theirs, result)):
            continue  # binary: lines mean nothing
        lost = _lost(base_blob, ours, theirs, result)
        if lost:
            found.append((path, lost))
    return found


def _decide(stdin_text: str) -> str | None:
    payload = json.loads(stdin_text)
    if not isinstance(payload, dict):
        return None
    tool_input = payload.get("tool_input")
    command = tool_input.get("command") if isinstance(tool_input, dict) else None
    if not isinstance(command, str) or not re.search(r"commit|merge", command, re.IGNORECASE):
        return None
    cwd = payload.get("cwd")
    cwd = cwd if isinstance(cwd, str) and cwd else os.getcwd()
    texts = [command]
    if _guard_parts is not None:
        try:
            texts += list(_guard_parts(command)[0])
        except Exception:  # noqa: BLE001 -- the command alone is still read
            pass
    directories: dict[str, bool] = {}
    for text in texts:
        for directory, whole_tree in _directories(text, cwd).items():
            directories[directory] = directories.get(directory, False) or whole_tree
    clock = _Clock()
    lost: list[tuple[str, list[str]]] = []
    for directory, whole_tree in list(directories.items())[:MAX_DIRECTORIES]:
        if not os.path.isdir(directory) or clock.left() <= 0:
            continue
        lost += _check(directory, whole_tree, clock)
    return _message(lost) if lost else None


def _message(lost: list[tuple[str, list[str]]]) -> str:
    shown = []
    for path, lines in lost[:MAX_FILES_SHOWN]:
        quoted = "; ".join(repr(line.strip()[:100]) for line in lines[:MAX_LINES_SHOWN])
        more = f"; and {len(lines) - MAX_LINES_SHOWN} more" if len(lines) > MAX_LINES_SHOWN else ""
        shown.append(f"`{path[:200]}` ({len(lines)} line(s): {quoted}{more})")
    more_files = f"; and {len(lost) - MAX_FILES_SHOWN} more file(s)" if len(lost) > MAX_FILES_SHOWN else ""
    return (
        "[warn-lossy-merge-resolution] this commit concludes a merge, and the result lacks "
        "lines the merged-in side (MERGE_HEAD) added since the merge base: "
        + ", ".join(shown) + more_files + ". Taking one side whole (`git checkout --ours`) "
        "drops the other side's additions; resolve hunk by hunk and keep both intents "
        "(conflict-resolution.md section 3). Check each line: restore it and re-stage, or, if "
        "it was dropped or replaced on purpose, say so in the commit message."
    )


def main() -> int:
    try:
        message = _decide(sys.stdin.read())
    except Exception:  # noqa: BLE001 -- advisory: a failure to check is silence
        return 0
    if message:
        print(message, file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
