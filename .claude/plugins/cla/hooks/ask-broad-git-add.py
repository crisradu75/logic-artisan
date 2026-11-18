#!/usr/bin/env python3
r"""PreToolUse hook: ask before a broad `git add` that would stage untracked files.

Why
---
About nineteen shipped skill rules say the same thing: stage named paths, never
`git add -A`, never a broad `git add openspec/`. The harm is concrete: a broad
stage sweeps whatever untracked file happens to sit in the tree (scratch output,
a parallel session's change folder, a secret) into the next commit. Prose alone
did not hold: the rules exist because it happened. This hook is the mechanical
half of those rules.

Why ASK, and why only when untracked files exist
------------------------------------------------
A user's own broad add is legitimate, so a block would be wrong; the permission
prompt lets them say yes. And a broad add over a tree whose only changes are
tracked modifications stages nothing new, so the hook stays silent there: a
prompt that fires on harmless commands stops being read.

Detection
---------
A `git add` invocation anywhere in the command (behind global options such as
`git -C <dir>`, in any `&&` / `;` / `|` / newline / `(` / backtick segment, and
under the `git.exe` spellings `_dispatch_lib.GIT_CMD` accepts), after quoted
spans are blanked by `_dispatch_lib.strip_quoted_spans`, is BROAD when:

- it carries `-A`, `--all` or `--no-ignore-removal` (or any abbreviation git
  resolves) and names no positive pathspec, or only broad ones; or
- one of its pathspecs is broad: `.`, `./`, `*`, `:/`, `:(top)`, or a bare
  `openspec` / `openspec/` (each also with a `:/` or `:(top)` prefix, a `./`
  prefix, or a trailing `/`, `/.` or `/*`); or
- its only pathspecs are exclusions (`:!x`, `:^x`, `:(exclude)x`), which git
  reads as "everything except these".

`-A <path>` is scoped to `<path>`, so it is NOT broad. Not broad either, because
they stage no untracked file: `-u`/`--update` and `--renormalize` (tracked files
only), `-n`/`--dry-run` and `--refresh` (stage nothing), `-p`/`-i`/`-e`
(interactive), and an invocation git itself would refuse (an unknown or
ambiguous option). `--pathspec-from-file` is not read: its paths live in a file.

Decision
--------
For each broad invocation, `git status --porcelain -z --untracked-files=all`
runs in the invocation's effective directory (the payload cwd, moved by each
`-C`) with the invocation's broad and exclusion pathspecs, so git itself
resolves `.` against that directory and applies `.gitignore`. Untracked (`??`)
entries are what the add would sweep in; under `-f`/`--force` ignored (`!!`)
entries count too, since `-f` adds them. No such entry: silent. Otherwise: ask,
naming up to ten files and the total.

Best-effort, like the warn hooks. Unparseable input, no git, not a repository,
`--git-dir`/`--work-tree`/`GIT_DIR=` in the add's own command segment (the repository cannot be named), a
directory that does not exist, a git error or timeout, or any exception: exit 0
silently. The hook never blocks on its own failure, so the dispatcher may also
skip it when the handler budget is spent (`_BEST_EFFORT_HOOKS` there).

Linear time. The command is split into segments and whitespace tokens once, and
a `git` token's global options are walked once: scanning resumes AFTER them, so
a `git` that is the value of `-c` is never re-walked. (A regex over the shared
`GIT_GLOBAL_OPTS` blob re-walks that run from every `git` inside it, which is
quadratic on `git -c git -c git ...`.)

Exit codes:
  0 -- always. The decision travels as JSON on stdout.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

_HOOKS_DIR = str(Path(__file__).resolve().parent)
if _HOOKS_DIR not in sys.path:
    sys.path.insert(0, _HOOKS_DIR)

from _dispatch_lib import GIT_CMD  # noqa: E402
from _dispatch_lib import strip_quoted_spans  # noqa: E402

# Total wall time for every `git status` this hook runs on one call, shared
# across them. `status` walks the working tree, so it gets the 4 s that
# `warn-stray-scratch-artifact.py` gets rather than the 3 s of a `rev-parse`.
# `_dispatch_lib.HOOK_WORST_CASE_SECONDS` records the same figure.
STATUS_BUDGET_SECONDS = 4.0
MAX_NAMED = 10

# A whole token naming git: the shared spellings (`git.exe`, `GIT`), optionally
# behind a directory path.
_GIT_TOKEN = re.compile(r"(?:.*[/\\])?" + GIT_CMD)
# Global options that take the NEXT token as their value.
_GLOBAL_VALUE_OPTS = frozenset({"-c", "-C", "--git-dir", "--work-tree", "--namespace", "--super-prefix"})
# Any of these means the command names its repository some other way than by
# directory, which this hook does not follow.
_REPO_ELSEWHERE_OPTS = ("--git-dir", "--work-tree")
_GIT_ENV_REPO = re.compile(r"(?:^|[\s;&|(])GIT_(?:DIR|WORK_TREE)=")

# `git add -h` (git 2.43), long names without their `--[no-]` prefix. git
# accepts an unambiguous prefix of any of them, and refuses an ambiguous one.
_ADD_LONG_OPTS = (
    "dry-run", "verbose", "interactive", "patch", "edit", "force", "update",
    "renormalize", "intent-to-add", "all", "ignore-removal", "refresh",
    "ignore-errors", "ignore-missing", "sparse", "chmod", "pathspec-from-file",
    "pathspec-file-nul",
)
_ADD_SHORT_OPTS = frozenset("nvipefuNA")
# Long options whose value may be the next token.
_ADD_VALUE_OPTS = frozenset({"chmod", "pathspec-from-file"})
_NO_STAGING = frozenset({"dry-run", "refresh", "interactive", "patch", "edit"})
_SHORT_NO_STAGING = frozenset("nipe")

# Segment separators. A `\`-continued newline is blanked to spaces first, so it
# joins lines instead of ending one.
_SEGMENT = re.compile(r"[^&|;\n(){}`]+")
_CONTINUATION = re.compile(r"\\\r?\n")
_TOKEN = re.compile(r"[^ \t\r]+")
_REDIRECT = re.compile(r"\d*(?:[<>]|&>)")
_REDIRECT_ALONE = re.compile(r"\d*[<>]+&?")

def _unquote(token: str) -> str:
    if len(token) >= 2 and token[0] == token[-1] and token[0] in "\"'":
        return token[1:-1]
    return token.replace('"', "").replace("'", "")


def _is_git(token: str) -> bool:
    return _GIT_TOKEN.fullmatch(token) is not None


def _resolve_long(name: str) -> str | None:
    """The `git add` long option `name` resolves to, or None when git refuses it."""
    if name in _ADD_LONG_OPTS:
        return name
    hits = [opt for opt in _ADD_LONG_OPTS if opt.startswith(name)]
    return hits[0] if len(hits) == 1 and name else None


def _is_exclude(spec: str) -> bool:
    return spec.startswith((":!", ":^", ":(exclude"))


def _is_broad_pathspec(spec: str) -> bool:
    """True for `.`, `*`, `:/`, `:(top)` and a bare `openspec`, in their spellings."""
    rest = spec.replace("\\", "/")
    if rest.startswith(":/"):
        rest = rest[2:]
    elif rest.startswith(":(top)"):
        rest = rest[len(":(top)"):]
    elif rest.startswith(":"):
        return False  # other magic: narrow unless an exclusion, handled apart
    while rest.startswith("./"):
        rest = rest[2:]
    while rest.endswith(("/", "/.", "/*")) and len(rest) > 1:
        rest = rest[:-1] if rest.endswith("/") else rest[:-2]
    return rest in ("", ".", "*", "openspec")


class _Invocation:
    __slots__ = ("directory", "probe_specs", "force")

    def __init__(self, directory: str, probe_specs: list[str], force: bool) -> None:
        self.directory = directory
        self.probe_specs = probe_specs
        self.force = force


def _parse_add(args: list[str]) -> tuple[list[str], bool] | None:
    """`(probe pathspecs, force)` for a broad add, or None when it is not broad.

    An empty pathspec list means the whole tree.
    """
    all_flag = update = no_staging = force = from_file = False
    specs: list[str] = []
    after_dashdash = False
    skip_next = False
    for token in args:
        if skip_next:
            skip_next = False
            continue
        if after_dashdash or not token.startswith("-") or token == "-":
            specs.append(token)
            continue
        if token == "--":
            after_dashdash = True
            continue
        if token.startswith("--"):
            name, eq, _value = token[2:].partition("=")
            negated = name.startswith("no-") and _resolve_long(name) is None
            option = _resolve_long(name[3:] if negated else name)
            if option is None:
                return None  # git refuses the whole command
            if option in _ADD_VALUE_OPTS and not eq and not negated:
                skip_next = True
            if option == "all":
                all_flag = not negated
            elif option == "ignore-removal":
                all_flag = negated
            elif option in ("update", "renormalize"):
                update = update or not negated
            elif option in _NO_STAGING:
                no_staging = no_staging or not negated
            elif option == "force":
                force = not negated
            elif option == "pathspec-from-file":
                from_file = not negated
            continue
        letters = token[1:]
        if not set(letters) <= _ADD_SHORT_OPTS:
            return None
        if "A" in letters:
            all_flag = True
        if "u" in letters:
            update = True
        if "f" in letters:
            force = True
        if set(letters) & _SHORT_NO_STAGING:
            no_staging = True
    if update or no_staging or from_file:
        return None
    positive = [s for s in specs if not _is_exclude(s)]
    excludes = [s for s in specs if _is_exclude(s)]
    broad = [s for s in positive if _is_broad_pathspec(s)]
    if broad:
        if any(s.endswith("*/") for s in broad):
            # `*/` reaches git as a literal that matches nothing: probe the
            # whole effective directory instead.
            return excludes, force
        return broad + excludes, force
    if positive:
        return None  # named paths only, with or without -A
    if all_flag or excludes:
        return excludes, force
    return None  # `git add` with nothing: git stages nothing


def _segments(scanned: str):
    joined = _CONTINUATION.sub(lambda m: " " * len(m.group(0)), scanned)
    for seg in _SEGMENT.finditer(joined):
        yield [(m.start(), m.end()) for m in _TOKEN.finditer(joined, seg.start(), seg.end())]


def _broad_invocations(command: str, cwd: str) -> list[_Invocation]:
    scanned = strip_quoted_spans(command)
    if "git" not in scanned.lower():
        return []
    found: list[_Invocation] = []
    for spans in _segments(scanned):
        if spans and _GIT_ENV_REPO.search(scanned[spans[0][0]:spans[-1][1]]):
            continue  # this segment names its repository by environment
        tokens = [command[a:b] for a, b in spans]
        scanned_tokens = [scanned[a:b] for a, b in spans]
        i = 0
        while i < len(tokens):
            if not _is_git(scanned_tokens[i]):
                i += 1
                continue
            directory: str | None = cwd
            j = i + 1
            while j < len(tokens) and scanned_tokens[j].startswith("-"):
                flag = scanned_tokens[j].split("=", 1)[0]
                if flag in _REPO_ELSEWHERE_OPTS:
                    directory = None
                if scanned_tokens[j] in _GLOBAL_VALUE_OPTS:
                    if scanned_tokens[j] == "-C" and j + 1 < len(tokens) and directory is not None:
                        value = os.path.expanduser(_unquote(tokens[j + 1]))
                        directory = os.path.normpath(os.path.join(directory, value))
                    j += 2
                else:
                    j += 1
            if j < len(tokens) and scanned_tokens[j] == "add":
                args: list[str] = []
                k = j + 1
                while k < len(tokens):
                    raw = scanned_tokens[k]
                    if _REDIRECT.match(raw):
                        k += 2 if _REDIRECT_ALONE.fullmatch(raw) else 1
                        continue
                    args.append(_unquote(tokens[k]))
                    k += 1
                parsed = _parse_add(args) if directory is not None else None
                if parsed is not None:
                    found.append(_Invocation(directory, parsed[0], parsed[1]))
                break  # the add's arguments run to the end of the segment
            # Resume AFTER the global options: a `git` among them is an option
            # value, never a command, and re-walking it would be quadratic.
            i = max(j, i + 1)
    return found


def _status_entries(directory: str, specs: list[str], force: bool, timeout: float) -> list[str] | None:
    """Paths the add would newly stage, or None when git could not answer."""
    if timeout <= 0 or not os.path.isdir(directory):
        return None
    args = ["git", "--no-optional-locks", "-C", directory, "status", "--porcelain", "-z",
            "--untracked-files=all"]
    if force:
        args.append("--ignored")
    if specs:
        args += ["--", *specs]
    try:
        result = subprocess.run(
            args, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout,
        )
    except (OSError, subprocess.SubprocessError, ValueError):
        return None
    if result.returncode != 0:
        return None
    wanted = ("??", "!!") if force else ("??",)
    paths: list[str] = []
    fields = result.stdout.split("\0")
    index = 0
    while index < len(fields):
        entry = fields[index]
        index += 1
        if len(entry) < 4:
            continue
        code = entry[:2]
        if code[0] in "RC" or code[1] in "RC":
            index += 1  # a rename or copy carries its source path as the next field
        if code in wanted:
            paths.append(entry[3:])
    return paths


def _swept_files(invocations: list[_Invocation]) -> list[str]:
    """Every file the broad invocations would newly stage, in first-seen order.

    One probe per distinct (directory, force, pathspecs), never a merged one:
    an exclusion-only pathspec means "the whole tree except", and merging it
    with another invocation's positive pathspec would narrow it. All probes
    share one `STATUS_BUDGET_SECONDS` deadline; a probe with no time left is
    skipped, like any other probe that cannot answer.
    """
    deadline = time.monotonic() + STATUS_BUDGET_SECONDS
    probed: set[tuple[str, bool, tuple[str, ...]]] = set()
    swept: list[str] = []
    seen: set[str] = set()
    for inv in invocations:
        key = (inv.directory, inv.force, tuple(inv.probe_specs))
        if key in probed:
            continue
        probed.add(key)
        entries = _status_entries(inv.directory, inv.probe_specs, inv.force, deadline - time.monotonic())
        for path in entries or []:
            if path not in seen:
                seen.add(path)
                swept.append(path)
    return swept


def _quote_name(path: str) -> str:
    """A file name with whitespace and control characters escaped.

    The Copilot adapter turns an ask whose reason contains "did not run" or
    "could not run" into a deny; an escaped space (`\\x20`) keeps a file name
    from spelling either phrase.
    """
    escaped = path[:200].encode("unicode_escape").decode("ascii", "replace")
    return escaped.replace(" ", "\\x20")


def _ask_reason(swept: list[str]) -> str:
    shown = ", ".join(f"`{_quote_name(p)}`" for p in swept[:MAX_NAMED])
    more = f", and {len(swept) - MAX_NAMED} more" if len(swept) > MAX_NAMED else ""
    return (
        f"a broad `git add` that would stage {len(swept)} untracked file(s) that may not "
        f"belong in this commit: {shown}{more}. Stage named paths instead "
        "(`git add <path> ...`); confirm only if every one belongs in the commit. "
        "(hook: ask-broad-git-add.py)"
    )


def _decide(stdin_text: str) -> str | None:
    payload = json.loads(stdin_text)
    if not isinstance(payload, dict):
        return None
    tool_input = payload.get("tool_input")
    command = tool_input.get("command") if isinstance(tool_input, dict) else None
    if not isinstance(command, str) or not command:
        return None
    cwd = payload.get("cwd")
    cwd = cwd if isinstance(cwd, str) and cwd else os.getcwd()
    invocations = _broad_invocations(command, cwd)
    if not invocations:
        return None
    swept = _swept_files(invocations)
    return _ask_reason(swept) if swept else None


def main() -> int:
    try:
        reason = _decide(sys.stdin.read())
    except json.JSONDecodeError:
        return 0  # not our input to judge: stay silent
    except Exception as exc:  # noqa: BLE001 -- best-effort: a failure to check is silence
        print(f"ask-broad-git-add.py: skipped, {type(exc).__name__}", file=sys.stderr)
        return 0
    if reason:
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "ask",
                "permissionDecisionReason": reason,
            }
        }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
