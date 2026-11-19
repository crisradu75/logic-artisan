#!/usr/bin/env python3
r"""PreToolUse hook: three checks on the TEXT of a Bash or PowerShell command.

Why
---
The shipped skills state these rules in prose, and prose did not hold them:

- `_shared/references/plugin-root.md`: never pass a literal `${CLAUDE_PLUGIN_ROOT}`
  through to a shell (and `output-styles/COPILOT.md`: never run an unresolved
  placeholder).
- `_shared/references/bash-discipline.md`: never write to `..`, which in a
  consuming repo holds the user's other projects; no multi-line `--body`, no
  heredoc subshell for a commit message or PR body.
- `report-upstream/SKILL.md`: open the issue with a body file, never an inline
  multi-line string.

What it checks, and what each finding does
------------------------------------------
1. BLOCK: an unresolved plugin root. `${CLAUDE_PLUGIN_ROOT}` or
   `$CLAUDE_PLUGIN_ROOT`, directly followed by `/` or `\` (or by a closing `"`
   and then one), where the shell would expand it: unquoted, inside double
   quotes, or in the body of a heredoc whose delimiter is unquoted. Claude Code
   substitutes the placeholder into skill, command and agent text when it loads
   them, and exports it to hook and MCP processes, but "the variables aren't
   present in the environment of commands Claude runs through the Bash tool, in
   the main session or in a subagent" (Claude Code's plugins reference,
   "Where each variable resolves"). So in a command it expands to nothing and
   the command runs against `/skills/...`: a missing script, a check that
   "passes" because nothing ran, or a write at the filesystem root. Measured on
   Claude Code 2.1.42: `echo "[${CLAUDE_PLUGIN_ROOT-unset}]"` in the Bash tool
   printed `[unset]`. A literal reaches a command from a `references/` file,
   which `Read` returns raw (`plugin-root.md` records that half as measured).
   Blocked, not asked: with the variable unset the command is wrong every
   time, and the fix (substitute the absolute path) is always available, so a
   prompt would only let a broken command through. Silent: single-quoted text,
   a `\$` escape, a quoted-delimiter heredoc, a `#` comment, a bare
   `$CLAUDE_PLUGIN_ROOT` with no path after it (a diagnostic `echo`), the
   `${CLAUDE_PLUGIN_ROOT:-...}` forms, and any command that assigns the
   variable itself (`CLAUDE_PLUGIN_ROOT=...`, `export ...`, PowerShell's
   `$env:CLAUDE_PLUGIN_ROOT = ...`).

2. ASK: a write outside the checkout through `..`. The target of a write
   redirect (`>`, `>>`, `>|`, `&>`, `&>>`, `<>`, `>&<file>`), any file operand
   of `tee` or `mkdir`, or the destination of `cp` or `mv` (the last operand, or
   `-t`/`--target-directory`), when the path, normalised, starts with `..` and
   resolves (against the payload's `cwd`) outside the checkout that holds the
   cwd: the nearest directory upward with a `.git` entry, a linked worktree
   included, or the cwd itself when there is none. So `../x` from a
   subdirectory of the repo is silent. Asked, not blocked: a person can mean it
   ("copy this to ../other-repo"). Silent: `cd ..` (no write), a `..` path in an
   ordinary argument (`echo "see ../x"`, `git -C ../x status`), a source operand
   (`cp ../a b`), an absolute path, and a path starting with `$` or `~` (not
   knowable from the text).

3. WARN: a multi-line inline message. A `git commit` `-m`/`--message` value, or a
   `gh pr|issue create|edit|comment|review` `--body`/`-b` value, that holds a
   real newline (inside quotes, or a `$'...\n...'` string) or a `$(cat <<...)`
   heredoc. Warned, not blocked: the command does what its author meant, and
   the heredoc form is Claude Code's own default commit shape, so a block would
   fire on the most common commit in every repo that installs the plugin. The
   harm is friction: a multi-line command defeats permission-allowlist
   matching, so it prompts every time (bash-discipline.md, "Why these patterns
   matter"). Several single-line `-m` values are fine.

Not checked: a PR-body temp file written inside the repo (multi-spec's
`phases.md`: "in the system temp folder, never inside the repo"). Being inside
the repo is not the signal: spec-to-pr's handoff passes an in-repo, gitignored
`temp/` file to `--body-file` on purpose, and bash-discipline.md sanctions that
folder. The real signal (inside, untracked AND not ignored) needs
`git check-ignore`/`ls-files`, a subprocess that would make this hook
best-effort; and the file is usually written by the Write tool, so a Bash hook
sees it only after the fact. A stray body file is still caught at staging time
by `ask-broad-git-add`.

`ALLOW_DESTRUCTIVE_GIT` does not apply: none of these is a destructive git
command (its requirement covers "every prompt the guard hooks raise before a
destructive git command"), and the git half here only warns.

How the text is read
--------------------
One left-to-right pass with a stack of contexts (shell code, double quotes,
`$(...)`, backticks, `$((...))`), single quotes and `${...}` skipped with
`str.find`, heredoc bodies consumed line by line at the newline that starts
them. Every character is visited a bounded number of times, so the pass is
linear on hostile input. It yields simple commands (words and redirects); the
command name is found behind assignments, `env`, `command`, `sudo`, `nohup`,
`time`, `exec`, `builtin`, `!`, `{` and the compound keywords. `git` is matched
by `_shell_text.GIT_CMD` on the word's basename, and its global options are
walked as tokens (linear, as in `ask-broad-git-add.py`).

Bash quoting is used for PowerShell too. Its single quotes are literal and its
double quotes expand, as in bash; its backtick escape is not modelled, which
can only make a finding less likely (the scan gives up on the command).

Failure: unparseable input, a missing command, an unterminated quote or
substitution (the shell would refuse the command), or any exception: exit 0
silently. It runs no subprocess; its only I/O is looking for a `.git` entry
above the cwd when a `..` write target is found. If this file fails to load,
the Bash dispatcher counts it as an enforcing guard that did not run and asks.

Exit codes:
  0 -- allow, possibly with an ask (stdout JSON) and a warning (stderr)
  2 -- block, with the reason on stderr
"""

from __future__ import annotations

import json
import os
import posixpath
import re
import sys
from pathlib import Path

_HOOKS_DIR = str(Path(__file__).resolve().parent)
if _HOOKS_DIR not in sys.path:
    sys.path.insert(0, _HOOKS_DIR)

from _shell_text import GIT_CMD  # noqa: E402

_TAG = "(hook: guard-bash-text.py)"

# The placeholder as a path prefix: `${CLAUDE_PLUGIN_ROOT}/`, `$CLAUDE_PLUGIN_ROOT/`,
# and the quoted-variable form `"${CLAUDE_PLUGIN_ROOT}"/`. Matched only at a `$`
# the shell expands.
_PLACEHOLDER = re.compile(
    r"\$(?:\{CLAUDE_PLUGIN_ROOT\}|CLAUDE_PLUGIN_ROOT(?![A-Za-z0-9_]))\"?[/\\]"
)
# The command sets the variable itself, so the shell may well have it.
_ASSIGNS_ROOT = re.compile(
    r"(?:^|[\s;&|(])(?:export[ \t]+)?CLAUDE_PLUGIN_ROOT="
    r"|\$(?:env:)?CLAUDE_PLUGIN_ROOT[ \t]*=(?!=)"
)

# Bulk runs of characters with no meaning in their context.
_PLAIN_CODE = re.compile(r"[^\s\\'\"$`#()<>;&|]+")
_PLAIN_DOUBLE = re.compile(r"[^\"\\$`\n]+")

_WRITE_OPS = frozenset({">", ">>", ">|", "&>", "&>>", "<>", ">&"})
_ANGLE_OPS = (">>", ">|", ">&", "<>", "<&", ">", "<")

_ASSIGNMENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\+?=")
_PREFIX_WORDS = frozenset(
    {"{", "!", "if", "then", "elif", "else", "while", "until", "do", "time", "nohup", "exec", "builtin"}
)
_SUDO_VALUE_LETTERS = frozenset("ugChpDRTrtU")
_EXTENSIONS = frozenset({"exe", "cmd", "bat", "com", "ps1"})

_GIT_NAME = re.compile(GIT_CMD)
_GH_NAME = re.compile(r"(?i:gh)(?:\.(?i:exe|cmd|bat|com|ps1))?")
# git global options that take the NEXT token as their value.
_GIT_GLOBAL_VALUE_OPTS = frozenset({"-c", "-C", "--git-dir", "--work-tree", "--namespace", "--super-prefix"})
# `git commit` long options whose value may be the next token.
_COMMIT_VALUE_LONG = frozenset({
    "--file", "--reuse-message", "--reedit-message", "--fixup", "--squash", "--author",
    "--date", "--template", "--cleanup", "--trailer", "--pathspec-from-file",
})
_GH_MESSAGE_SUBCOMMANDS = frozenset({"create", "edit", "comment", "review"})

MAX_NAMED = 5


class _Word:
    __slots__ = ("chars", "quoted", "newline", "heredoc", "plain_prefix")

    def __init__(self) -> None:
        self.chars: list[str] = []
        self.quoted = False      # some part of it was quoted, escaped or substituted
        self.newline = False     # a quoted part holds a real newline
        self.heredoc = False     # a `$(...)` in it opens a heredoc
        self.plain_prefix: int | None = None  # length of the leading unquoted text

    def mark_quoted(self) -> None:
        if self.plain_prefix is None:
            self.plain_prefix = sum(len(c) for c in self.chars)
        self.quoted = True

    @property
    def value(self) -> str:
        return "".join(self.chars)


class _Redirect:
    __slots__ = ("op", "target")

    def __init__(self, op: str, target: _Word) -> None:
        self.op = op
        self.target = target


class _Frame:
    """`kind` "N" is shell code, "D" a double-quoted string (whose `word` is the
    enclosing code frame's current word)."""

    __slots__ = ("kind", "closer", "seg", "word", "pending", "parens", "arith", "heredoc")

    def __init__(self, kind: str, closer: str | None = None, arith: bool = False) -> None:
        self.kind = kind
        self.closer = closer
        self.seg: list = []
        self.word: _Word | None = None
        self.pending: str | None = None
        self.parens = 0
        self.arith = arith
        self.heredoc = False


class _Scan:
    """The simple commands of `cmd`, and where an unresolved plugin root sits."""

    def __init__(self, cmd: str) -> None:
        self.cmd = cmd
        self.segments: list[list] = []
        self.placeholders: list[int] = []
        self.heredocs: list[tuple[str, bool, bool]] = []
        self.complete = True
        self._run()

    # -- words and commands -------------------------------------------------
    @staticmethod
    def _word(f: _Frame) -> _Word:
        if f.word is None:
            f.word = _Word()
        return f.word

    @staticmethod
    def _end_word(f: _Frame) -> None:
        w = f.word
        if w is None:
            return
        f.word = None
        if f.pending is not None:
            f.seg.append(_Redirect(f.pending, w))
            f.pending = None
        else:
            f.seg.append(w)

    def _end_seg(self, f: _Frame) -> None:
        self._end_word(f)
        f.pending = None
        if f.seg:
            self.segments.append(f.seg)
            f.seg = []

    # -- the pass -------------------------------------------------------------
    def _run(self) -> None:
        cmd = self.cmd
        n = len(cmd)
        stack = [_Frame("N")]
        i = 0
        while i < n:
            f = stack[-1]
            if f.kind == "D":
                i = self._in_double(stack, f, i)
                continue
            c = cmd[i]
            if c == f.closer and (c == "`" or f.parens == 0):
                self._end_seg(f)
                stack.pop()
                parent = stack[-1]
                if parent.word is not None:
                    parent.word.heredoc = parent.word.heredoc or f.heredoc
                if parent.kind == "N":
                    parent.heredoc = parent.heredoc or f.heredoc
                i += 1
                continue
            plain = _PLAIN_CODE.match(cmd, i)
            if plain is not None:
                self._word(f).chars.append(plain.group())
                i = plain.end()
                continue
            if c == "\n":
                self._end_seg(f)
                i = self._read_heredocs(i + 1)
                continue
            if c.isspace():
                self._end_word(f)
                i += 1
                continue
            if c == "\\":
                if cmd.startswith("\\\n", i):
                    i += 2
                    continue
                w = self._word(f)
                w.mark_quoted()
                w.chars.append(cmd[i + 1 : i + 2])
                i += 2
                continue
            if c == "#" and f.word is None:
                j = cmd.find("\n", i)
                i = n if j < 0 else j
                continue
            if c == "'":
                w = self._word(f)
                w.mark_quoted()
                j = cmd.find("'", i + 1)
                if j < 0:
                    self.complete = False
                    return
                body = cmd[i + 1 : j]
                w.chars.append(body)
                w.newline = w.newline or "\n" in body
                i = j + 1
                continue
            if c == '"':
                self._word(f).mark_quoted()
                d = _Frame("D")
                d.word = f.word
                stack.append(d)
                i += 1
                continue
            if c == "$":
                i = self._dollar(stack, f, self._word(f), i)
                continue
            if c == "`":
                self._open_substitution(stack, self._word(f), "`")
                i += 1
                continue
            if f.arith:
                if c == "(":
                    f.parens += 1
                elif c == ")":
                    f.parens -= 1
                self._word(f).chars.append(c)
                i += 1
                continue
            if c == "(":
                if f.word is None and cmd.startswith("((", i):
                    frame = _Frame("N", ")", arith=True)
                    frame.parens = 1
                    stack.append(frame)
                    i += 2
                    continue
                self._end_seg(f)
                f.parens += 1
                i += 1
                continue
            if c == ")":
                self._end_seg(f)
                if f.parens > 0:
                    f.parens -= 1
                i += 1
                continue
            if c == "&" and cmd.startswith("&>", i):
                op = "&>>" if cmd.startswith("&>>", i) else "&>"
                self._end_word(f)
                f.pending = op
                i += len(op)
                continue
            if c in ";|&":
                self._end_seg(f)
                i += 1
                continue
            if c in "<>":
                i = self._angle(stack, f, i)
                continue
            self._word(f).chars.append(c)
            i += 1
        if len(stack) > 1:
            self.complete = False
            return
        self._end_seg(stack[0])

    def _open_substitution(self, stack: list, w: _Word, closer: str, arith: bool = False) -> None:
        # A `$` stands in for the substituted text, so a value that starts with
        # one reads as "not knowable from the text".
        w.mark_quoted()
        w.chars.append("$")
        frame = _Frame("N", closer, arith=arith)
        if arith:
            frame.parens = 1
        stack.append(frame)

    def _in_double(self, stack: list, d: _Frame, i: int) -> int:
        cmd = self.cmd
        w = d.word
        plain = _PLAIN_DOUBLE.match(cmd, i)
        if plain is not None:
            w.chars.append(plain.group())
            return plain.end()
        c = cmd[i]
        if c == '"':
            stack.pop()
            return i + 1
        if c == "\\":
            nxt = cmd[i + 1 : i + 2]
            if nxt == "\n":
                return i + 2
            if nxt and nxt in '$`"\\':
                w.chars.append(nxt)
                return i + 2
            w.chars.append(c)
            return i + 1
        if c == "$":
            return self._dollar(stack, d, w, i)
        if c == "`":
            self._open_substitution(stack, w, "`")
            return i + 1
        # c == "\n"
        w.newline = True
        w.chars.append(c)
        return i + 1

    def _dollar(self, stack: list, f: _Frame, w: _Word, i: int) -> int:
        cmd = self.cmd
        n = len(cmd)
        if _PLACEHOLDER.match(cmd, i):
            self.placeholders.append(i)
        nxt = cmd[i + 1 : i + 2]
        if nxt == "(":
            if cmd.startswith("$((", i):
                self._open_substitution(stack, w, ")", arith=True)
                return i + 3
            self._open_substitution(stack, w, ")")
            return i + 2
        if nxt == "{":
            j = cmd.find("}", i + 2)
            if j < 0:
                self.complete = False
                return n
            w.mark_quoted()
            w.chars.append(cmd[i : j + 1])
            return j + 1
        if nxt == "'" and f.kind == "N":
            # `$'...'`: backslash escapes are decoded, so `\n` is a real newline.
            w.mark_quoted()
            j = i + 2
            while j < n and cmd[j] != "'":
                if cmd[j] == "\\":
                    if cmd[j + 1 : j + 2] == "n":
                        w.newline = True
                    j += 2
                    continue
                if cmd[j] == "\n":
                    w.newline = True
                j += 1
            if j >= n:
                self.complete = False
                return n
            w.chars.append(cmd[i + 2 : j])
            return j + 1
        if nxt == '"' and f.kind == "N":
            return i + 1  # `$"..."` is a double-quoted string
        if nxt and (nxt.isalnum() or nxt in "_@*#?$!-"):
            w.mark_quoted()
        w.chars.append("$")
        return i + 1

    def _angle(self, stack: list, f: _Frame, i: int) -> int:
        cmd = self.cmd
        if cmd.startswith(("<(", ">("), i):
            self._open_substitution(stack, self._word(f), ")")
            return i + 2
        w = f.word
        if w is not None and not w.quoted and w.value.isdigit():
            f.word = None  # `2>`: the digits name a descriptor, not an argument
        else:
            self._end_word(f)
        if cmd.startswith("<<<", i):
            f.pending = "<<<"
            return i + 3
        if cmd.startswith("<<", i):
            return self._heredoc_op(f, i + 2)
        for op in _ANGLE_OPS:
            if cmd.startswith(op, i):
                f.pending = op
                return i + len(op)
        return i + 1  # unreachable: the caller saw `<` or `>`

    def _heredoc_op(self, f: _Frame, j: int) -> int:
        cmd = self.cmd
        n = len(cmd)
        strip = cmd.startswith("-", j)
        if strip:
            j += 1
        while j < n and cmd[j] in " \t":
            j += 1
        parts: list[str] = []
        quoted = False
        while j < n:
            ch = cmd[j]
            if ch in "'\"":
                k = cmd.find(ch, j + 1)
                if k < 0:
                    self.complete = False
                    return n
                parts.append(cmd[j + 1 : k])
                quoted = True
                j = k + 1
            elif ch == "\\" and j + 1 < n:
                parts.append(cmd[j + 1])
                quoted = True
                j += 2
            elif ch.isspace() or ch in ";&|<>()":
                break
            else:
                parts.append(ch)
                j += 1
        delim = "".join(parts)
        if delim:
            self.heredocs.append((delim, quoted, strip))
            f.heredoc = True
        return j

    def _read_heredocs(self, pos: int) -> int:
        """Consume the bodies of the heredocs opened on the line just ended."""
        if not self.heredocs:
            return pos
        cmd = self.cmd
        n = len(cmd)
        pending, self.heredocs = self.heredocs, []
        for delim, quoted, strip in pending:
            start = body_end = pos
            while True:
                if pos >= n:
                    body_end = n
                    break
                nl = cmd.find("\n", pos)
                end = n if nl < 0 else nl
                line = cmd[pos:end]
                if line.endswith("\r"):
                    line = line[:-1]
                if (line.lstrip("\t") if strip else line) == delim:
                    body_end = pos
                    pos = end + 1
                    break
                pos = end + 1
            if not quoted:
                self._scan_expanding(start, body_end)
        return min(pos, n)

    def _scan_expanding(self, a: int, b: int) -> None:
        cmd = self.cmd
        i = a
        while i < b:
            c = cmd[i]
            if c == "\\":
                i += 2
                continue
            if c == "$" and _PLACEHOLDER.match(cmd, i, b):
                self.placeholders.append(i)
            i += 1


# -- reading one simple command ---------------------------------------------

def _basename(value: str) -> str:
    return value.replace("\\", "/").rsplit("/", 1)[-1]


def _plain_name(value: str) -> str:
    """The command name, lowercased, without a directory or a Windows extension."""
    base = _basename(value).lower()
    stem, dot, ext = base.rpartition(".")
    return stem if dot and ext in _EXTENSIONS else base


def _is_assignment(w: _Word) -> bool:
    m = _ASSIGNMENT.match(w.value)
    return m is not None and (w.plain_prefix is None or m.end() <= w.plain_prefix)


def _command_start(words: list[_Word]) -> tuple[int, str] | None:
    """`(index, plain name)` of the word that names the command, behind
    prefixes and wrappers; None when there is none."""
    i = 0
    n = len(words)
    while i < n:
        w = words[i]
        if _is_assignment(w):
            i += 1
            continue
        name = _plain_name(w.value)
        if name in _PREFIX_WORDS:
            i += 1
        elif name == "env":
            i += 1
            while i < n:
                v = words[i].value
                if v in ("-u", "--unset", "-C", "--chdir"):
                    i += 2
                elif v.startswith("-") or _is_assignment(words[i]):
                    i += 1
                else:
                    break
        elif name == "sudo":
            i += 1
            while i < n and words[i].value.startswith("-"):
                v = words[i].value
                i += 1
                if v == "--":
                    break
                if len(v) == 2 and v[1] in _SUDO_VALUE_LETTERS:
                    i += 1
        elif name == "command":
            i += 1
            while i < n and words[i].value.startswith("-"):
                if words[i].value in ("-v", "-V"):
                    return None  # describes the command, does not run it
                i += 1
        else:
            return i, name
    return None


def _operands(args: list[_Word], value_short: str, value_long: frozenset) -> tuple[list[str], list[tuple[str, str]]]:
    """`(operands, [(option, value)])` for a GNU-style argument list."""
    operands: list[str] = []
    values: list[tuple[str, str]] = []
    i = 0
    n = len(args)
    after_dashdash = False
    while i < n:
        v = args[i].value
        i += 1
        if after_dashdash or v == "-" or not v.startswith("-"):
            operands.append(v)
            continue
        if v == "--":
            after_dashdash = True
            continue
        if v.startswith("--"):
            name, eq, rest = v.partition("=")
            if name in value_long:
                if eq:
                    values.append((name, rest))
                elif i < n:
                    values.append((name, args[i].value))
                    i += 1
            continue
        letters = v[1:]
        for k, ch in enumerate(letters):
            if ch in value_short:
                rest = letters[k + 1 :]
                if rest:
                    values.append(("-" + ch, rest))
                elif i < n:
                    values.append(("-" + ch, args[i].value))
                    i += 1
                break
    return operands, values


def _analyse(seg: list) -> tuple[list[str], list[str]]:
    """`(write targets, multi-line message labels)` of one simple command."""
    targets: list[str] = []
    words: list[_Word] = []
    for item in seg:
        if isinstance(item, _Redirect):
            if item.op not in _WRITE_OPS:
                continue
            value = item.target.value
            if item.op == ">&" and (value.isdigit() or value == "-"):
                continue  # `>&2`: a descriptor, not a file
            targets.append(value)
        else:
            words.append(item)
    start = _command_start(words)
    if start is None:
        return targets, []
    k, name = start
    targets += _command_targets(name, words[k + 1 :])
    return targets, _inline_messages(words[k], words[k + 1 :])


def _command_targets(name: str, args: list[_Word]) -> list[str]:
    """The files `tee` and `mkdir` write, and the destination of `cp` and `mv`."""
    if name == "tee":
        return _operands(args, "", frozenset())[0]
    if name == "mkdir":
        return _operands(args, "m", frozenset({"--mode"}))[0]
    if name in ("cp", "mv"):
        operands, values = _operands(args, "tS", frozenset({"--target-directory", "--suffix"}))
        named = [v for opt, v in values if opt in ("-t", "--target-directory")]
        if named:
            return named
        if len(operands) >= 2:
            return [operands[-1]]
    return []


def _commit_messages(args: list[_Word]) -> list[_Word]:
    found: list[_Word] = []
    i = 0
    n = len(args)
    while i < n:
        w = args[i]
        v = w.value
        i += 1
        if v == "--":
            break
        if v.startswith("--"):
            name, eq, _rest = v.partition("=")
            if name == "--message":
                if eq:
                    found.append(w)
                elif i < n:
                    found.append(args[i])
                    i += 1
            elif name in _COMMIT_VALUE_LONG and not eq:
                i += 1
            continue
        if not v.startswith("-") or v == "-":
            continue
        letters = v[1:]
        for k, ch in enumerate(letters):
            if ch in "mFCct":
                attached = bool(letters[k + 1 :])
                if ch == "m":
                    if attached:
                        found.append(w)
                    elif i < n:
                        found.append(args[i])
                if not attached:
                    i += 1
                break
            if ch in "Su":
                break  # the rest of the word is that option's optional value
    return found


def _gh_bodies(args: list[_Word]) -> list[_Word]:
    found: list[_Word] = []
    i = 0
    n = len(args)
    while i < n:
        w = args[i]
        v = w.value
        i += 1
        if v == "--":
            break
        if v in ("--body", "-b"):
            if i < n:
                found.append(args[i])
                i += 1
        elif v.startswith("--body="):
            found.append(w)
        elif v.startswith("-b") and not v.startswith("--"):
            found.append(w)
    return found


def _inline_messages(name_word: _Word, rest: list[_Word]) -> list[str]:
    """Labels of the multi-line inline messages this command passes."""
    name = _basename(name_word.value)
    if _GIT_NAME.fullmatch(name):
        j = 0
        while j < len(rest) and rest[j].value.startswith("-"):
            j += 2 if rest[j].value in _GIT_GLOBAL_VALUE_OPTS else 1
        if j < len(rest) and rest[j].value == "commit":
            if any(w.newline or w.heredoc for w in _commit_messages(rest[j + 1 :])):
                return ["`git commit -m`"]
        return []
    if _GH_NAME.fullmatch(name) and len(rest) >= 2:
        group, action = rest[0].value, rest[1].value
        if group in ("pr", "issue") and action in _GH_MESSAGE_SUBCOMMANDS:
            if any(w.newline or w.heredoc for w in _gh_bodies(rest[2:])):
                return [f"`gh {group} {action} --body`"]
    return []


# -- where `..` lands ----------------------------------------------------------

def _checkout_root(cwd: str) -> str | None:
    d = os.path.abspath(cwd)
    while True:
        if os.path.exists(os.path.join(d, ".git")):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            return None
        d = parent


def _is_inside(path: str, root: str) -> bool:
    try:
        common = os.path.commonpath([os.path.normcase(path), os.path.normcase(root)])
    except ValueError:  # different drives on Windows
        return False
    return common == os.path.normcase(root)


class _Boundary:
    """The checkout that holds `cwd`, found once, when first needed."""

    def __init__(self, cwd: str) -> None:
        self.cwd = cwd
        self._root: str | None = None

    def root(self) -> str:
        if self._root is None:
            self._root = _checkout_root(self.cwd) or os.path.abspath(self.cwd)
        return self._root

    def escapes(self, target: str) -> bool:
        path = target.replace("\\", "/")
        if not path or "://" in path or path.startswith(("/", "~", "$")):
            return False
        if re.match(r"[A-Za-z]:", path):
            return False  # a Windows drive path
        norm = posixpath.normpath(path)
        if norm != ".." and not norm.startswith("../"):
            return False
        resolved = os.path.normpath(os.path.join(os.path.abspath(self.cwd), *norm.split("/")))
        return not _is_inside(resolved, self.root())


# -- the decision ----------------------------------------------------------------

class _Findings:
    """Each finding once, in first-seen order (dicts, so a hostile command
    with thousands of them stays linear)."""

    __slots__ = ("placeholders", "outside", "messages")

    def __init__(self) -> None:
        self.placeholders: dict[str, None] = {}
        self.outside: dict[str, None] = {}
        self.messages: dict[str, None] = {}


def check(command: str, cwd: str) -> _Findings:
    found = _Findings()
    scan = _Scan(command)
    if not scan.complete:
        return found  # the shell would refuse it: nothing runs
    if scan.placeholders and not _ASSIGNS_ROOT.search(command):
        for at in scan.placeholders:
            found.placeholders[command[at : at + 120].split(None, 1)[0]] = None
    boundary = _Boundary(cwd)
    for seg in scan.segments:
        targets, labels = _analyse(seg)
        for target in targets:
            if boundary.escapes(target):
                found.outside[target] = None
        for label in labels:
            found.messages[label] = None
    return found


def _named(found: dict[str, None]) -> str:
    items = list(found)
    shown = ", ".join(f"`{item[:200]}`" for item in items[:MAX_NAMED])
    more = f", and {len(items) - MAX_NAMED} more" if len(items) > MAX_NAMED else ""
    return shown + more


def _block_reason(found: _Findings) -> str:
    root = os.environ.get("CLAUDE_PLUGIN_ROOT")
    hint = f" For a file of the cla plugin it is `{root}`." if root else ""
    return (
        f"blocked: this command holds an unresolved plugin-root placeholder ({_named(found.placeholders)}). "
        "The Bash tool's shell does not set CLAUDE_PLUGIN_ROOT (Claude Code substitutes it into "
        "skill text only, and a `references/` file read with Read keeps it literal), so it "
        "expands to nothing and the command would run against `/skills/...`. Replace it with "
        "the plugin's absolute path: the `Base directory for this skill:` line without its "
        "trailing `/skills/<skill>`, or a path you already read from the plugin cut after "
        f"`plugins/<plugin>`.{hint} {_TAG}"
    )


def _ask_reason(found: _Findings) -> str:
    return (
        f"this command writes outside the checkout through `..`: {_named(found.outside)}. In a "
        "repo that installs this plugin, `..` holds the user's other projects. Write logs, "
        "captured output and scratch copies to the session scratchpad, or to a gitignored "
        "folder inside the repo; confirm only if the user asked for this write. " + _TAG
    )


def _warning(found: _Findings) -> str:
    return (
        f"[guard-bash-text] {' and '.join(found.messages)} carries a multi-line inline message "
        "(a real newline, or a `$(cat <<...)` heredoc). Write the text to a file in the "
        "system temp folder or the session scratchpad and pass it with `git commit -F <file>` "
        "or `--body-file <file>`: a multi-line command defeats permission-allowlist matching, "
        "so it prompts every time. Single-line `-m` values are fine."
    )


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read())
        if not isinstance(payload, dict):
            return 0
        tool_input = payload.get("tool_input")
        command = tool_input.get("command") if isinstance(tool_input, dict) else None
        if not isinstance(command, str) or not command:
            return 0
        cwd = payload.get("cwd")
        if not isinstance(cwd, str) or not cwd:
            cwd = os.getcwd()
        found = check(command, cwd)
    except Exception:  # noqa: BLE001 -- fail open: a guard does not break normal work
        return 0

    if found.placeholders:
        parts = [_block_reason(found)]
        if found.outside:
            parts.append("Also: " + _ask_reason(found))
        if found.messages:
            parts.append(_warning(found))
        print("\n".join(parts), file=sys.stderr)
        return 2
    if found.messages:
        print(_warning(found), file=sys.stderr)
    if found.outside:
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "ask",
            "permissionDecisionReason": _ask_reason(found),
        }}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
