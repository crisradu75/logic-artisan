#!/usr/bin/env python3
"""Reads the arguments of every `git commit` and `git add` in a shell command.

Shared by the two commit-honesty guards, `block-dishonest-commit.py` (the
message and `--allow-empty`) and `ask-staged-debug-tag.py` (what the commit
would add). It is a library, not a hook: no dispatcher runs it.

Each guard finds its invocations with `_dispatch_lib.GitInvocation` over the
`strip_quoted_spans` text, then hands each match to `read_commit` or `read_add`
here, which read the ORIGINAL command from the match's end (the two texts have
the same offsets). Reading the original is the point: a commit message is a
quoted span, which the stripped text blanks.

The argument reader is a small shell-word reader, not a shell. It follows
single, double and `$'...'` quotes, backslashes, `$(...)` and backtick
substitutions (nested, a heredoc inside one included), redirections, and the
heredocs of the command itself, and it stops at an unquoted `;`, `&`, `|`,
newline, `)` or comment. A word's value has its quotes removed and keeps any
substitution as written, except that a word which is exactly
`"$(cat <<'WORD' ... WORD)"` takes the heredoc's body as its value: that is how
a multi-line message is usually written. Not followed: variables, aliases,
`eval`, a message piped in (`... | git commit -F -`), and a message file written
earlier in the same command (the file is read as it is when the hook runs).

Linear time: every character is read once. An invocation's arguments end where
its command ends, and a guard skips every match that starts inside the span an
earlier invocation consumed (`Commit.end`, `Add.end`), heredoc bodies included,
so no text is read twice. Nesting deeper than `_MAX_DEPTH` substitutions, an
unterminated quote and an unterminated substitution raise `ParseError`, and a
guard then treats that invocation as unreadable and stays silent about it.
"""

from __future__ import annotations

import os
import re

# A `git` sub-command word: the command name, then something that ends a word.
# For `GitInvocation`, which refuses a pattern that can match at whitespace.
COMMIT_OR_ADD = r"(commit|add)(?=$|[ \t\r\n;&|()<>])"

# `$(...)` nesting deeper than this is refused rather than recursed into.
_MAX_DEPTH = 32
# A message file larger than this is read only up to here.
MAX_MESSAGE_FILE_BYTES = 1_000_000

_BLANKS = " \t\r"
_WORD_END = frozenset(" \t\r\n;&|<>()")
_COMMAND_END = frozenset(";&|\n)(")
_HERESTRING = re.compile(r"\d*<<<")
_HEREDOC = re.compile(r"(\d*)<<(-?)")
_REDIRECT = re.compile(r"(?:\d+|&)?(?:>>|>&|>\||<&|<>|>|<)")
_HEREDOC_IN_SUBST = re.compile(
    r"<<(-?)[ \t]*(?:'([^'\n]*)'|\"([^\"\n]*)\"|\\?([^\s;&|<>()'\"`]+))"
)
_CAT_HEREDOC = re.compile(r"\$\([ \t]*cat[ \t]+<<")

# `git commit -h` (git 2.43), long names without their `--[no-]` prefix. git
# accepts an unambiguous prefix of any of them, and refuses an ambiguous one.
_COMMIT_LONG = (
    "quiet", "verbose", "file", "author", "date", "message", "reedit-message",
    "reuse-message", "fixup", "squash", "reset-author", "trailer", "signoff",
    "template", "edit", "cleanup", "status", "gpg-sign", "all", "include",
    "interactive", "patch", "only", "verify", "dry-run", "short", "branch",
    "ahead-behind", "porcelain", "long", "null", "amend", "post-rewrite",
    "untracked-files", "pathspec-from-file", "pathspec-file-nul", "allow-empty",
    "allow-empty-message",
)
# Long options whose value, when not given with `=`, is the next word.
_COMMIT_LONG_VALUED = frozenset({
    "file", "author", "date", "message", "reedit-message", "reuse-message",
    "fixup", "squash", "trailer", "template", "cleanup", "pathspec-from-file",
})
# Options that take the message from somewhere this reader cannot see.
_MESSAGE_ELSEWHERE = frozenset({"reedit-message", "reuse-message", "fixup", "squash", "template"})
_COMMIT_SHORT_FLAGS = frozenset("qvseaipnoz")
_COMMIT_SHORT_VALUED = frozenset("mFcCt")
_COMMIT_SHORT_OPTIONAL = frozenset("Su")  # value attached or absent

# `git add -h` (git 2.43); same conventions.
_ADD_LONG = (
    "dry-run", "verbose", "interactive", "patch", "edit", "force", "update",
    "renormalize", "intent-to-add", "all", "ignore-removal", "refresh",
    "ignore-errors", "ignore-missing", "sparse", "chmod", "pathspec-from-file",
    "pathspec-file-nul",
)
_ADD_LONG_VALUED = frozenset({"chmod", "pathspec-from-file"})
_ADD_SHORT = frozenset("nvipefuNA")
# Stages nothing, or asks the user what to stage.
_ADD_NOTHING_KNOWN = frozenset({"dry-run", "refresh", "interactive", "patch", "edit", "pathspec-from-file"})

# git global options that name the repository some other way than by directory.
_REPO_ELSEWHERE = ("--git-dir", "--work-tree")
_GIT_ENV_REPO = re.compile(r"(?:^|[\s;&|(])GIT_(?:DIR|WORK_TREE)=")


class ParseError(Exception):
    """The command could not be read; the caller stays silent about it."""


class Word:
    __slots__ = ("text", "heredoc")

    def __init__(self, text: str, heredoc: str | None) -> None:
        self.text = text
        self.heredoc = heredoc

    @property
    def message(self) -> str:
        return self.heredoc if self.heredoc is not None else self.text


# --------------------------------------------------------------------------- #
# The shell-word reader
# --------------------------------------------------------------------------- #


def _heredoc_body(text: str, pos: int, delim: str, strip_tabs: bool) -> tuple[str, int]:
    """The body starting at `pos` up to the line `delim`, and the index after it."""
    lines: list[str] = []
    n = len(text)
    while pos < n:
        nl = text.find("\n", pos)
        line_end = nl if nl >= 0 else n
        line = text[pos:line_end].rstrip("\r")
        if strip_tabs:
            line = line.lstrip("\t")
        if line == delim:
            return "\n".join(lines), min(line_end + 1, n)
        lines.append(line)
        pos = line_end + 1
    return "\n".join(lines), n


def _skip_backtick(text: str, i: int) -> int:
    """`text[i:]` follows an opening backtick; the index after the closing one."""
    n = len(text)
    while i < n:
        ch = text[i]
        if ch == "\\":
            i += 2
        elif ch == "`":
            return i + 1
        else:
            i += 1
    raise ParseError("unterminated backtick")


def _skip_dquote(text: str, i: int, depth: int, bodies: list[str]) -> int:
    """`text[i:]` follows an opening `"`; the index after the closing one."""
    n = len(text)
    while i < n:
        ch = text[i]
        if ch == "\\":
            i += 2
        elif ch == '"':
            return i + 1
        elif ch == "$" and text.startswith("$(", i):
            i = _skip_subst(text, i + 2, depth + 1, bodies)
        elif ch == "`":
            i = _skip_backtick(text, i + 1)
        else:
            i += 1
    raise ParseError("unterminated double quote")


def _skip_subst(text: str, i: int, depth: int, bodies: list[str]) -> int:
    """`text[i:]` follows `$(`; the index after the matching `)`.

    Appends to `bodies` the body of every heredoc met inside, in order."""
    if depth > _MAX_DEPTH:
        raise ParseError("substitutions nested too deeply")
    n = len(text)
    parens = 0
    pending: list[tuple[str, bool]] = []
    word_start = True
    while i < n:
        ch = text[i]
        if ch == "\n":
            i += 1
            for delim, strip_tabs in pending:
                body, i = _heredoc_body(text, i, delim, strip_tabs)
                bodies.append(body)
            pending.clear()
            word_start = True
            continue
        if ch == "\\":
            i += 2
        elif ch == "'":
            end = text.find("'", i + 1)
            if end < 0:
                raise ParseError("unterminated single quote")
            i = end + 1
        elif ch == '"':
            i = _skip_dquote(text, i + 1, depth, bodies)
        elif ch == "`":
            i = _skip_backtick(text, i + 1)
        elif ch == "$" and text.startswith("$(", i):
            i = _skip_subst(text, i + 2, depth + 1, bodies)
        elif ch == "#" and word_start:
            nl = text.find("\n", i)
            i = nl if nl >= 0 else n
            continue
        elif ch == "<" and text.startswith("<<", i) and not text.startswith("<<<", i):
            m = _HEREDOC_IN_SUBST.match(text, i)
            if m is None:
                i += 2
            else:
                delim = m.group(2) if m.group(2) is not None else (
                    m.group(3) if m.group(3) is not None else m.group(4))
                pending.append((delim, m.group(1) == "-"))
                i = m.end()
        elif ch == "(":
            parens += 1
            i += 1
        elif ch == ")":
            if parens == 0:
                return i + 1
            parens -= 1
            i += 1
        else:
            i += 1
        word_start = ch in " \t;&|("
    raise ParseError("unterminated substitution")


def _ansi_c(text: str, i: int) -> tuple[str, int]:
    """`text[i:]` follows `$'`; the decoded value and the index after the `'`."""
    out: list[str] = []
    escapes = {"n": "\n", "t": "\t", "r": "\r", "\\": "\\", "'": "'", '"': '"'}
    n = len(text)
    while i < n:
        ch = text[i]
        if ch == "\\" and i + 1 < n:
            out.append(escapes.get(text[i + 1], "\\" + text[i + 1]))
            i += 2
        elif ch == "'":
            return "".join(out), i + 1
        else:
            out.append(ch)
            i += 1
    raise ParseError("unterminated $'...'")


def read_word(text: str, i: int) -> tuple[Word, int]:
    """One shell word starting at `i`, and the index after it."""
    n = len(text)
    out: list[str] = []
    substs: list[tuple[str, list[str]]] = []

    def subst(start: int) -> int:
        bodies: list[str] = []
        end = _skip_subst(text, start + 2, 1, bodies)
        raw = text[start:end]
        out.append(raw)
        substs.append((raw, bodies))
        return end

    while i < n:
        ch = text[i]
        if ch in _WORD_END:
            break
        if ch == "\\":
            if i + 1 < n and text[i + 1] != "\n":
                out.append(text[i + 1])
            i += 2
        elif ch == "'":
            end = text.find("'", i + 1)
            if end < 0:
                raise ParseError("unterminated single quote")
            out.append(text[i + 1:end])
            i = end + 1
        elif ch == "$" and text.startswith("$'", i):
            value, i = _ansi_c(text, i + 2)
            out.append(value)
        elif ch == "$" and text.startswith("$(", i):
            i = subst(i)
        elif ch == "`":
            end = _skip_backtick(text, i + 1)
            out.append(text[i:end])
            i = end
        elif ch == '"':
            i += 1
            while True:
                if i >= n:
                    raise ParseError("unterminated double quote")
                c = text[i]
                if c == '"':
                    i += 1
                    break
                if c == "\\" and i + 1 < n:
                    nxt = text[i + 1]
                    if nxt in '$`"\\':
                        out.append(nxt)
                    elif nxt != "\n":
                        out.append(c + nxt)
                    i += 2
                elif c == "$" and text.startswith("$(", i):
                    i = subst(i)
                elif c == "`":
                    end = _skip_backtick(text, i + 1)
                    out.append(text[i:end])
                    i = end
                else:
                    out.append(c)
                    i += 1
        else:
            out.append(ch)
            i += 1
    value = "".join(out)
    heredoc = None
    if len(substs) == 1 and value == substs[0][0] and len(substs[0][1]) == 1 and _CAT_HEREDOC.match(value):
        heredoc = substs[0][1][0]
    return Word(value, heredoc), i


def _skip_blanks(text: str, i: int) -> int:
    n = len(text)
    while i < n:
        if text[i] in _BLANKS:
            i += 1
        elif text.startswith("\\\n", i):
            i += 2
        elif text.startswith("\\\r\n", i):
            i += 3
        else:
            break
    return i


def command_words(text: str, i: int) -> tuple[list[Word], list[tuple[str, str]], int]:
    """The words of the simple command starting at `i`.

    Returns the words (redirections and their targets left out), the body of
    each of the command's own heredocs as `(fd, body)` with `fd` the digits
    before `<<` (empty for stdin), and the index after everything the command
    consumed, its heredoc bodies included."""
    n = len(text)
    words: list[Word] = []
    pending: list[tuple[str, bool, str]] = []
    while True:
        i = _skip_blanks(text, i)
        if i >= n:
            break
        if _HERESTRING.match(text, i):
            i = _skip_blanks(text, _HERESTRING.match(text, i).end())
            _, i = read_word(text, i)
            continue
        heredoc = _HEREDOC.match(text, i)
        if heredoc:
            i = _skip_blanks(text, heredoc.end())
            delim, i = read_word(text, i)
            pending.append((delim.text, heredoc.group(2) == "-", heredoc.group(1)))
            continue
        redirect = _REDIRECT.match(text, i)
        if redirect:
            i = redirect.end()
            if redirect.group(0).endswith("&") and i < n and (text[i].isdigit() or text[i] == "-"):
                while i < n and (text[i].isdigit() or text[i] == "-"):
                    i += 1
                continue
            i = _skip_blanks(text, i)
            _, i = read_word(text, i)
            continue
        if text[i] in _COMMAND_END or text[i] == "#":
            break
        word, i = read_word(text, i)
        words.append(word)
    end = i
    bodies: list[tuple[str, str]] = []
    if pending:
        nl = text.find("\n", i)
        pos = nl + 1 if nl >= 0 else n
        for delim, strip_tabs, fd in pending:
            body, pos = _heredoc_body(text, pos, delim, strip_tabs)
            bodies.append((fd, body))
        end = max(end, pos)
    return words, bodies, end


# --------------------------------------------------------------------------- #
# Option parsing
# --------------------------------------------------------------------------- #


def _resolve(name: str, options: tuple[str, ...]) -> str | None:
    """The long option `name` resolves to, or None when git refuses it."""
    if name in options:
        return name
    hits = [opt for opt in options if opt.startswith(name)]
    return hits[0] if len(hits) == 1 and name else None


def _long(token: str, options: tuple[str, ...]) -> tuple[str, bool, str | None] | None:
    """`(option, negated, attached value or None)` for `--name[=value]`, or None."""
    name, eq, value = token[2:].partition("=")
    option = _resolve(name, options)
    if option is not None:
        return option, False, value if eq else None
    if name.startswith("no-"):
        option = _resolve(name[3:], options)
        if option is not None:
            return option, True, value if eq else None
    return None


def directory_of(cwd: str | None, opts_text: str) -> str | None:
    """The directory git runs in: `cwd` moved by each global `-C`, or None when
    `cwd` is None or the options name the repository another way
    (`--git-dir`, `--work-tree`)."""
    if cwd is None:
        return None
    words, _bodies, _end = command_words(opts_text, 0)
    directory = cwd
    k = 0
    while k < len(words):
        token = words[k].text
        if token.split("=", 1)[0] in _REPO_ELSEWHERE:
            return None
        if token == "-C" and k + 1 < len(words):
            value = os.path.expanduser(words[k + 1].text)
            directory = os.path.normpath(os.path.join(directory, value))
            k += 2
            continue
        k += 2 if token == "-c" else 1
    return directory


class Commit:
    """What one `git commit` would do, as far as its text says."""

    __slots__ = (
        "start", "end", "directory", "messages", "message_hidden", "trailers",
        "allow_empty", "dry_run", "all_files", "pathspecs", "pathspec_from_file", "refused",
    )

    def __init__(self, start: int, end: int, directory: str | None) -> None:
        self.start = start
        self.end = end
        self.directory = directory
        self.messages: list[str] = []      # each `-m`, `-F` file or stdin heredoc, in order
        self.message_hidden = False        # some part of the message is out of sight
        self.trailers: list[str] = []      # each `--trailer` value
        self.allow_empty = False
        self.dry_run = False
        self.all_files = False
        self.pathspecs: list[str] = []
        self.pathspec_from_file = False
        self.refused = False               # git would refuse this command line

    @property
    def subject(self) -> str | None:
        """The first non-blank message line, or None when it cannot be seen."""
        if self.message_hidden or not self.messages:
            return None
        for line in "\n".join(self.messages).splitlines():
            if line.strip():
                return line.strip()
        return None


def _refuse(invocation):
    invocation.refused = True
    return invocation


def _read_message_file(path: str, directory: str | None) -> str | None:
    if directory is None:
        return None
    try:
        full = os.path.join(directory, os.path.expanduser(path))
        if not os.path.isfile(full):  # a FIFO or device would block the read
            return None
        with open(full, "rb") as handle:
            data = handle.read(MAX_MESSAGE_FILE_BYTES)
    except (OSError, ValueError):
        return None
    return data.decode("utf-8", errors="replace")


def read_commit(command: str, match_start: int, match_end: int, opts_text: str, cwd: str | None) -> Commit:
    """The commit whose `git ... commit` spans `command[match_start:match_end]`.

    `refused` is set when git would refuse the command line (an unknown or
    ambiguous option). Raises `ParseError` when the text cannot be read."""
    words, bodies, end = command_words(command, match_end)
    commit = Commit(match_start, end, directory_of(cwd, opts_text))
    stdin_body = next((body for fd, body in bodies if fd in ("", "0")), None)
    message_given = False

    def message_from_file(value: str) -> None:
        if value in ("-", "/dev/stdin"):
            text = stdin_body
        else:
            text = _read_message_file(value, commit.directory)
        if text is None:
            commit.message_hidden = True
        else:
            commit.messages.append(text)

    k = 0
    after_dashdash = False
    while k < len(words):
        word = words[k]
        token = word.text
        k += 1
        if after_dashdash or not token.startswith("-") or token == "-":
            commit.pathspecs.append(token)
            continue
        if token == "--":
            after_dashdash = True
            continue
        if token.startswith("--"):
            parsed = _long(token, _COMMIT_LONG)
            if parsed is None:
                return _refuse(commit)
            option, negated, value_text = parsed
            value: Word | None = None
            if option in _COMMIT_LONG_VALUED and not negated:
                if value_text is not None:
                    value = Word(value_text, None)
                elif k < len(words):
                    value = words[k]
                    k += 1
                else:
                    return _refuse(commit)  # git: requires a value
            if option == "message" and value is not None:
                commit.messages.append(value.message)
                message_given = True
            elif option == "file" and value is not None:
                message_from_file(value.text)
                message_given = True
            elif option == "trailer" and value is not None:
                commit.trailers.append(value.message)
            elif option in _MESSAGE_ELSEWHERE and value is not None:
                commit.message_hidden = True
                message_given = message_given or option != "template"
            elif option == "allow-empty":
                commit.allow_empty = not negated
            elif option == "dry-run":
                commit.dry_run = not negated
            elif option == "all":
                commit.all_files = not negated
            elif option == "pathspec-from-file":
                commit.pathspec_from_file = not negated
            continue
        letters = token[1:]
        index = 0
        while index < len(letters):
            letter = letters[index]
            if letter in _COMMIT_SHORT_VALUED:
                rest = letters[index + 1:]
                if rest:
                    value = Word(rest, None)
                elif k < len(words):
                    value = words[k]
                    k += 1
                else:
                    return _refuse(commit)
                if letter == "m":
                    commit.messages.append(value.message)
                    message_given = True
                elif letter == "F":
                    message_from_file(value.text)
                    message_given = True
                else:
                    commit.message_hidden = True
                    message_given = message_given or letter != "t"
                break
            if letter in _COMMIT_SHORT_OPTIONAL:
                break
            if letter not in _COMMIT_SHORT_FLAGS:
                return _refuse(commit)
            if letter == "a":
                commit.all_files = True
            index += 1
    if not message_given:
        commit.message_hidden = True  # the editor, or the commit being amended
    return commit


class Add:
    """What one `git add` would stage, as far as its text says."""

    __slots__ = ("start", "end", "directory", "pathspecs", "whole_tree", "tracked_only", "refused")

    def __init__(self, start: int, end: int, directory: str | None) -> None:
        self.start = start
        self.end = end
        self.directory = directory
        self.pathspecs: list[str] = []
        self.whole_tree = False
        self.tracked_only = False
        self.refused = False               # stages nothing this reader can name


def read_add(command: str, match_start: int, match_end: int, opts_text: str, cwd: str | None) -> Add:
    """The `git add` whose `git ... add` spans `command[match_start:match_end]`.

    `refused` is set when it stages nothing this reader can name (a dry run,
    an interactive add, `--pathspec-from-file`, no pathspec and no `-A`/`-u`),
    or when git would refuse it. Raises `ParseError` when the text cannot be
    read."""
    words, _bodies, end = command_words(command, match_end)
    add = Add(match_start, end, directory_of(cwd, opts_text))
    all_flag = False
    k = 0
    after_dashdash = False
    while k < len(words):
        token = words[k].text
        k += 1
        if after_dashdash or not token.startswith("-") or token == "-":
            add.pathspecs.append(token)
            continue
        if token == "--":
            after_dashdash = True
            continue
        if token.startswith("--"):
            parsed = _long(token, _ADD_LONG)
            if parsed is None:
                return _refuse(add)
            option, negated, value_text = parsed
            if option in _ADD_LONG_VALUED and value_text is None and not negated:
                k += 1
            if option in _ADD_NOTHING_KNOWN and not negated:
                return _refuse(add)
            if option == "all":
                all_flag = not negated
            elif option == "ignore-removal":
                all_flag = negated
            elif option in ("update", "renormalize"):
                add.tracked_only = add.tracked_only or not negated
            continue
        letters = token[1:]
        if not set(letters) <= _ADD_SHORT:
            return _refuse(add)
        if set(letters) & set("nipe"):
            return _refuse(add)
        all_flag = all_flag or "A" in letters
        add.tracked_only = add.tracked_only or "u" in letters
    # An exclusion narrows nothing this reader merges, so it is dropped; one
    # with no positive pathspec beside it means "everything except".
    positive = [spec for spec in add.pathspecs if not spec.startswith((":!", ":^", ":(exclude"))]
    excluded = len(positive) != len(add.pathspecs)
    add.pathspecs = positive
    if not positive:
        if not (all_flag or add.tracked_only or excluded):
            return _refuse(add)  # `git add` with nothing: git stages nothing
        add.whole_tree = True
    return add


def _heredoc_spans(command: str) -> list[tuple[int, int]]:
    """The `(start, end)` of every heredoc body in `command`, in order. An
    operator inside an earlier body is skipped, which keeps this linear."""
    spans: list[tuple[int, int]] = []
    if "<<" not in command:
        return spans
    covered = 0
    for op in _HEREDOC_IN_SUBST.finditer(command):
        if op.start() < covered or command.startswith("<<<", op.start()):
            continue
        delim = next((g for g in op.groups()[1:] if g is not None), None)
        if not delim:
            continue
        nl = command.find("\n", op.end())
        if nl < 0:
            continue
        _body, end = _heredoc_body(command, nl + 1, delim, op.group(1) == "-")
        spans.append((nl + 1, end))
        covered = end
    return spans


def find_invocations(command: str, scanned: str, matcher, cwd: str) -> list:
    """Every readable `git commit` and `git add` in `command`, in order.

    `scanned` is `strip_quoted_spans(command)` and `matcher` a
    `GitInvocation(COMMIT_OR_ADD, capture_opts=True)`, both from the calling
    hook. `GIT_DIR=` or `GIT_WORK_TREE=` anywhere in the command leaves every
    invocation's `directory` None. A match inside text an earlier invocation consumed (its arguments
    or heredoc bodies) is skipped, which keeps the walk linear. Text that
    cannot be read ends the walk: the shell would refuse an unterminated
    quote too, and reading on from a guess could be quadratic."""
    found: list = []
    consumed = 0
    # Once per command, not per invocation: a scan of the whole text for each
    # of many invocations is quadratic.
    base: str | None = None if _GIT_ENV_REPO.search(command) else cwd
    bodies = _heredoc_spans(command)
    b = 0
    for match in matcher.finditer(scanned):
        if match.start() < consumed:
            continue
        while b < len(bodies) and bodies[b][1] <= match.start():
            b += 1
        if b < len(bodies) and bodies[b][0] <= match.start():
            continue  # text inside a heredoc body is data, not a command
        opts_text = command[match.start(1):match.end(1)]
        reader = read_commit if match.group(2) == "commit" else read_add
        try:
            invocation = reader(command, match.start(), match.end(), opts_text, base)
        except ParseError:
            break
        consumed = invocation.end
        if not invocation.refused:
            found.append(invocation)
    return found
