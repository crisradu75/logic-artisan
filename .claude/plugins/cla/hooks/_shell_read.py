#!/usr/bin/env python3
r"""Shared shell reading for the Bash guards: what a command runs once its
shell wrappers are opened and its git expansions are filled in.

Every guard reads the command's quote-stripped text, so a command that hands
its real work to another shell inside quotes (`bash -c "..."`, `sh -c`,
`eval "..."`, `pwsh -Command`, `Invoke-Expression`, `cmd /c`) was blanked and
allowed by every guard but one, and so was a git whose subcommand the shell
fills in (`X=commit; git $X ...`). `expand()` returns the command as a list of
parts: the command itself, then each wrapper body that holds git and each
rewritten git line, each a command a guard can read as if it had been typed
bare. `guard_parts()` is the other guards' reading: every wrapper body,
whatever it runs, and no rewritten git line.

Two readers use it, once per call:
  - `dispatch-bash-pretooluse.py` calls `guard_parts()` before any guard runs,
    and runs each Bash guard that reads parts (all but `block-cd-in-bash.py`
    and `ask-destructive-git.py`) on every part as well as on the command;
  - `ask-destructive-git.py` reads `expand()`'s cached result through `_scan`,
    and alone turns its unresolved and depth-cap reasons into an ask.

It lived inside `ask-destructive-git.py` until the other guards needed it.
Stdlib only, import-cheap and side-effect-free, like `_dispatch_lib`.

The reading is linear in the command's length: the readers spend from one work
cap (`_WORK_FACTOR`), appended text is capped at the command's own length plus
`_EXPAND_SLACK`, and a command past either cap asks (`UNRESOLVED_REASON`) rather
than being read partly; `guard_parts()` stops at the same caps and returns what
it found. The section comments above `_WRAP_DEPTH` and `_HEREDOC_START` hold
the rules and the named misses.
"""

from __future__ import annotations

import base64
import bisect
import functools
import itertools
import re
import sys
from pathlib import Path

# Loaded by path from the dispatcher and from pytest, neither of which puts
# the hooks dir first on `sys.path`, so the `_dispatch_lib` import below is
# made explicit. The same bootstrap every hook carries.
_HOOKS_DIR = str(Path(__file__).resolve().parent)
if _HOOKS_DIR not in sys.path:
    sys.path.insert(0, _HOOKS_DIR)

from _dispatch_lib import GitInvocation  # noqa: E402
from _dispatch_lib import GIT_SEP as _GIT_SEP  # noqa: E402
from _dispatch_lib import strip_quoted_spans as _strip_quoted_spans  # noqa: E402

# Horizontal whitespace, or a backslash line continuation. A continuation is a
# JOINED line, not a new command, so it separates tokens; a bare newline ends
# the command and must not. The matchers here and in `_destructive_git_rules.py`
# (`_GH_PR_MERGE` among them) share this —
# four review rounds each found the same bug one construct over, every time
# because one position used a plain `\s` or excluded the newline outright.
# Imported rather than defined here: `GIT_GLOBAL_OPTS` needs the same thing, and
# the two drifting is exactly how `git -C . \`+newline+`push --force` stayed a
# silent bypass after every OTHER separator position had been fixed.
_SEP = _GIT_SEP

# The trailing tail stops at a shell separator so the flags of a LATER command
# are never attributed to this one. A NEWLINE is such a separator: a multi-line
# Bash command is ordinary here, and without `\n` excluded, a plain `git push`
# on one line was flagged because of an `-f` on the next.
#
# But a CONTINUED newline is not a command boundary, and excluding `\n` flatly
# made `git push \`+newline+`--force origin feat` — an ordinary multi-line
# invocation — a silent bypass of the force-push guard. The tail therefore
# admits a continuation while still stopping at a bare newline, and the
# `git`→subcommand gap uses `_SEP` for the same reason.
_TAIL = r"((?:\\\r?\n|[^&|;\n])*)"
# Each is `GIT_CMD`, `_SEP`, the global options, then the subcommand and tail,
# matched by `GitInvocation` in linear time: the regex it replaced took 25 s on
# a 28 KB `git -c git -c git ... status`, past the hook timeout.
_PUSH = GitInvocation(r"push\b" + _TAIL)
_RESET = GitInvocation(r"reset\b" + _TAIL)
_BRANCH = GitInvocation(r"branch\b" + _TAIL)


def _abbrev(word: str, floor: int) -> str:
    """Regex for any prefix of `word` at least `floor` characters long.

    git accepts any UNAMBIGUOUS long-option abbreviation, so a matcher that
    spells an option out in full is a silent bypass for every shorter spelling
    git still resolves. `floor` is that command's shortest resolving prefix and
    must be read off THAT command's own option set — it differs per command, and
    guessing it wrong fails in both directions (too low over-matches a prefix git
    refuses; too high misses one it accepts).

    Generated rather than hand-written. The nesting is fine at four characters
    and stops being fine at fifteen: a hand-written `--discard-changes` form
    shipped here with unbalanced parentheses, and the whole module then failed to
    import — which the dispatcher reports as a hook that did not run, i.e. every
    check in this file silently off.
    """
    out = ""
    for char in reversed(word[floor:]):
        out = "(?:" + re.escape(char) + out + ")?"
    return re.escape(word[:floor]) + out


# One segment of a shell word each: `$'...'`, `'...'`, `"..."` or `$"..."`, a
# backslash escape, or plain text; a closing quote may be missing.
_QUOTED = re.compile(
    r"""\$'((?:[^'\\]|\\.)*)'?|'([^']*)'?|\$?"((?:[^"\\]|\\.)*)"?|\\(.)|([^'"\\$]+|.)""", re.S
)
_ANSI_ESCAPE = re.compile(r"\\(x[0-9a-fA-F]{1,2}|[0-7]{1,3}|.)", re.S)
# Inside double quotes a backslash escapes only these.
_DOUBLE_ESCAPE = re.compile(r'\\([\\"$`])')
_ANSI_C = {
    "n": "\n", "t": "\t", "r": "\r", "a": "\a", "b": "\b", "f": "\f", "v": "\v",
    "e": "\x1b", "E": "\x1b", "\\": "\\", "'": "'", '"': '"', "?": "?",
}


def _unquote(word: str) -> str:
    """One shell word as the command receives it: `'...'`, `"..."`, `$'...'`
    (ANSI-C escapes), `$"..."` and backslashes, at any point in the word, so
    `ma"in"`, `$'main'` and `--rebase="false"` read as `main` and `--rebase=false`.
    An unterminated quote runs to the end of the word."""
    if "'" not in word and '"' not in word and "\\" not in word:
        return word  # every piece would be plain text
    out: list[str] = []
    for m in _QUOTED.finditer(word):
        ansi, single, double, escaped, plain = m.groups()
        if ansi is not None:
            out.append(_ANSI_ESCAPE.sub(_ansi_char, ansi))
        elif double is not None:
            out.append(_DOUBLE_ESCAPE.sub(r"\1", double))
        else:
            out.append(next(g for g in (single, escaped, plain) if g is not None))
    return "".join(out)


def _ansi_char(m: re.Match) -> str:
    """One `$'...'` escape: hex `x` plus digits, octal digits, or a named one (`t`)."""
    code = m.group(1)
    if code[0] == "x" and len(code) > 1:
        return chr(int(code[1:], 16))
    if code[0] in "01234567":
        return chr(int(code, 8))
    return _ANSI_C.get(code, "\\" + code)


# --- Shell wrappers and expansions --------------------------------------------
# Every git matcher reads the command's quote-stripped text, so a command that
# hands git to another shell inside quotes (`bash -c "git push -f origin x"`,
# `sh -c '...'`, `eval "..."`, `pwsh -Command '...'`, `Invoke-Expression`,
# `cmd /c`) was blanked and allowed, and so was a git whose subcommand or flag
# the shell fills in (`X=push; git $X -f origin x`). `_expand` closes both:
#
# - A WRAPPER's argument words are read, unquoted, joined and appended to the
#   command as a line of their own, and wrappers inside that line are read the
#   same way, `_WRAP_DEPTH` levels deep; a wrapper deeper than that asks
#   (`WRAP_DEPTH_REASON`). A body is appended only when it holds `git` or `gh`,
#   so `eval "$(ssh-agent)"` costs nothing. A wrapper word is found outside
#   quotes wherever it sits, so `echo bash -c 'git push -f'` asks too: one extra
#   prompt on a command that names a destructive one, rather than a list of
#   every prefix that can run a command. A wrapper among the words of the
#   wrapper before it is read at the next depth, not again at this one.
# - A git at a command's start whose SUBCOMMAND word holds a quote, a `$` or a
#   backtick anywhere (`git "push"`, `git $X`, `git pu$X"sh"`) is rewritten
#   with the word's value: quotes are removed, and each `$NAME` assigned a
#   literal in the same command (`NAME=v`, `export`, PowerShell `$NAME = 'v'`)
#   is tried with each value it is given. Anything else (an unassigned,
#   computed or positional name, `$(...)`) asks: `UNRESOLVED_REASON`.
# - The same for the words of `git push`, `git reset` and `git branch`, whose
#   flags alone decide a prompt. A quoted or escaped word whose value starts
#   with `-` or `+` (`"-f"`, `'+main'`) is read unquoted. A word with an
#   expansion is resolved the same way; when it cannot be, its literal start
#   decides: `+` is a forced refspec whatever follows, `--name=` names the flag
#   whatever follows, any other `-` (`--force$X`, `-D$X`) asks. A word that
#   starts with the expansion asks only when it is an unquoted `$NAME` before
#   any plain operand (`git push $F origin x`); after one
#   (`git push origin $BRANCH`, the common shape) it is left alone. A quoted
#   `"$NAME"` is one word, the way a value is passed (`git branch "$NAME"`),
#   and a `$(...)` is a computed value; neither asks. Known misses, named: a
#   flag from a whole-word expansion after an operand or in double quotes, a
#   refspec from one (`git push origin $REF` holding `+main`), a command name
#   from one (`$CMD push -f`), a quoted or escaped `git` (`'git' push -f`), a
#   subcommand word that starts with a backslash (`git \push -f`), a prefix
#   command that takes a value (`timeout 60 git $X`), which hides the
#   command's start, and a backtick span that opens on an earlier line (or
#   across a `\`-newline) and closes on git's line: a substituted flag later
#   on that line is not read, and a git word glued to that closing backtick
#   asks (`_span_close`).
#
# Appended text goes after a blank line, so no line continuation or tail joins
# it to the line before, and each part is quote-stripped on its own, so an odd
# quote in one part cannot pair with one in the next. The result is the command
# itself whenever nothing was appended, so every other command reads exactly as
# before. Appended text is capped at the command's own length plus
# `_EXPAND_SLACK`, and the characters the readers walk at `_WORK_FACTOR` times
# that; past either, the command asks rather than being read partly.
_WRAP_DEPTH = 3
_EXPAND_ROUNDS = 4
_EXPAND_SLACK = 4096
_EXPAND_MAX_LINES = 64
# Every reader below is linear in what it is handed. This bounds a shape that
# makes them walk the same text again and again: the first version walked the
# rest of the command once per `eval` in `eval eval eval ...`, and per `X=$(`
# in `X=$(X=$(...`, and a 20 kB command took longer than the 15 s the handler
# is given, which Claude Code then ALLOWS. A command that needs these readers
# walks its text about three times (wrapper words, assignments, rewrites) over
# at most twice its length, so 8 leaves room for every real one.
_WORK_FACTOR = 8
_PART_SEP = "\n\n"
# Where a command word may start: after a path separator inside the word, or
# after whitespace, an operator or the start of the text.
_WORD_START = r"(?:(?<=[/\\])|(?<![^\s;&|(){}`!]))"
_WRAPPER = re.compile(
    _WORD_START
    + r"(?i:bash|sh|zsh|dash|ksh|mksh|ash|fish|csh|tcsh|su|pwsh|powershell|cmd"
    r"|eval|iex|invoke-expression)(?i:\.exe)?(?=[ \t]|\\\r?\n)"
)
# `-EncodedCommand` and its PowerShell spellings: `-e`, `-ec`, `-en` onward.
_PS_ENCODED = re.compile(r"(?i)-(?:ec|" + _abbrev("encodedcommand", 1) + ")")
_HAS_GIT = re.compile(r"(?i)git|gh")
# The depth cap asks only when the body it will not read names git or gh as a word.
# `_HAS_GIT` is a cheap substring test that decides which bodies are worth reading
# ("through" holds `gh`); a prompt needs the stronger test, or prose that lists
# wrapper names before such a word asks for a command nobody wrote.
_NAMES_GIT = re.compile(r"(?i)(?<![\w-])(?:git|gh)(?![\w-])")
# A `$NAME` or `${NAME}`, optionally inside double quotes: the whole-word
# expansion shape that asks while it comes before an operand.
_SINGLE_VAR = re.compile(r'"?\$(?:([A-Za-z_]\w*)|\{([A-Za-z_]\w*)\})"?')
# The name after a `$`, bare or braced.
_VAR_NAME = re.compile(r"[A-Za-z_]\w*")
_VAR_BRACED = re.compile(r"\{([A-Za-z_]\w*)\}")
# A shell assignment word (`X=`, `export X=`), and a PowerShell one (`$X =`).
_ASSIGN = re.compile(
    r"(?:^|(?<=[\s;&|(){}`]))(?:(?:export|local|declare|readonly|typeset)[ \t]+"
    r"(?:-\w+[ \t]+)*)?([A-Za-z_]\w*)="
)
_PS_ASSIGN = re.compile(r"(?:^|(?<=[\s;&|(){}]))\$([A-Za-z_]\w*)[ \t]*=(?!=)[ \t]*")
# A value is taken as literal only when it is plain text a shell would not
# expand or a PowerShell expression would not compute.
_LITERAL_VALUE = re.compile(r"[\w ./:+=,@%~^-]*")
# A word that is a prefix to the command after it, not the command.
_COMMAND_PREFIXES = frozenset(
    "sudo env command exec time nohup nice xargs builtin then do else elif if while until".split()
)
# A subcommand word holding a quote, a `$` or a backtick anywhere. When `git`
# sits inside a backtick span (`_span_close`), the word ends where the span
# closes: in `` run `git status` `` that backtick closes a span opened before
# `git`, and reading it as an expansion asked on every heredoc that quotes a
# git command. The word does not start with `-`, which is an option the matcher did not take as one
# (`--git-dir="$D"`), or with a backslash, where `GitInvocation` refuses a
# pattern that matches.
_GIT_SUBCOMMAND_EXPANDED = GitInvocation(r"(?!-)(?=[^\s;&|<>()\\]*?[$`\"'])", capture_opts=True)
# Global options that take the next word as their value. The matcher may read
# one as a bare flag, which makes its value look like the subcommand.
_GIT_VALUE_OPT = re.compile(r"-[cC]|--(?:git-dir|work-tree|namespace|super-prefix)")
_TAIL_RE = re.compile(_TAIL)
_STOP = frozenset(" \t\r\n;&|<>()")
# A run of characters `_word_end` steps over one at a time, matched at once.
_PLAIN_RUN = re.compile(r"[^\\'\"`$ \t\r\n;&|<>()]+")


class _OverBudget(Exception):
    """The readers walked more than `_WORK_FACTOR` allows for this command."""


# Characters the readers may still walk; set by `_expand` for each command and
# unlimited outside it.
_WORK_LEFT = [float("inf")]


def _spend(chars: int) -> None:
    _WORK_LEFT[0] -= chars
    if _WORK_LEFT[0] < 0:
        raise _OverBudget


@functools.lru_cache(maxsize=128)
def _stripped(part: str) -> str:
    """`part` quote-stripped. Several readers below strip the same part; one
    pass serves them all."""
    return _strip_quoted_spans(part)


@functools.lru_cache(maxsize=16)
def _paren_close(text: str) -> dict[int, int]:
    """The offset of the `)` that closes each `(` in `text`, counted by depth
    alone, as `_word_end` reads a `$(...)`; an unclosed `(` is absent. One pass
    per text, so a run of unclosed `$(` is not walked to the end once each."""
    close: dict[int, int] = {}
    stack: list[int] = []
    for m in re.finditer(r"[()]", text):
        if m.group() == "(":
            stack.append(m.start())
        elif stack:
            close[stack.pop()] = m.start()
    return close


UNRESOLVED_REASON = (
    "a git command whose subcommand or flags come from a shell expansion this "
    "guard cannot resolve (`git $X ...`, `git push $F ...`), so it cannot tell "
    "whether this force-pushes, hard-resets or force-deletes a branch"
)

WRAP_DEPTH_REASON = (
    f"a shell wrapper nested more than {_WRAP_DEPTH} deep (`bash -c \"eval '...'\"`), "
    "whose innermost command this guard does not read, so it cannot tell whether "
    "it force-pushes, hard-resets or force-deletes a branch"
)


def _word_end(text: str, i: int, limit: int | None = None) -> int:
    """End of the shell word that starts at `i`, reading no further than
    `limit` (the end of `text` when None): quotes, backslash escapes, `$(...)`
    and backtick spans are part of the word; unquoted whitespace or an operator
    ends it. An unterminated quote runs to the limit."""
    n = len(text) if limit is None else limit
    start = i
    while i < n:
        ch = text[i]
        if ch == "\\":
            i += 2
        elif ch == "'":
            j = text.find("'", i + 1, n)
            i = n if j < 0 else j + 1
        elif ch == '"':
            j = i + 1
            while j < n and text[j] != '"':
                j += 2 if text[j] == "\\" else 1
            i = j + 1
        elif ch == "`":
            j = text.find("`", i + 1, n)
            i = n if j < 0 else j + 1
        elif text.startswith("$(", i):
            i = _paren_close(text).get(i + 1, n) + 1
        elif ch in _STOP:
            break
        else:
            plain = _PLAIN_RUN.match(text, i, n)
            i = plain.end() if plain else i + 1
    end = min(i, n)
    _spend(end - start)
    return end


def _command_words(text: str, i: int, limit: int | None = None) -> list[tuple[int, int]]:
    """The `(start, end)` of each word from `i` to the end of its simple
    command, or to `limit`. A redirection operator is skipped (its target stays
    a word); a line continuation is not an end."""
    spans: list[tuple[int, int]] = []
    n = len(text) if limit is None else limit
    while i < n:
        ch = text[i]
        if ch in " \t":
            i += 1
        elif ch == "\\" and text.startswith("\n", i + 1, n):
            i += 2
        elif ch == "\\" and text.startswith("\r\n", i + 1, n):
            i += 3
        elif ch in "<>":
            i += 1
            while i < n and text[i] in "<>&|":
                i += 1
        elif ch in _STOP:
            break
        else:
            end = _word_end(text, i, n)
            spans.append((i, end))
            i = end
    return spans


def _expansions(word: str) -> tuple[int, list[tuple[int, int, str]] | None]:
    """Where the shell substitutes into `word`: the offset of the first
    expansion (-1 when there is none), and the `(start, end, NAME)` of each
    `$NAME` or `${NAME}` in it, or None when one is of any other kind (`$(...)`,
    a backtick, `$1`, `${X:-y}`). An expansion is a `$` that starts a parameter
    or command substitution, or a backtick, outside single quotes. `$'...'` is
    a literal: the `'` after its `$` starts no expansion, and the single-quote
    rule then skips its text."""
    first = -1
    names: list[tuple[int, int, str]] = []
    i, n, double = 0, len(word), False
    while i < n:
        ch = word[i]
        if ch == "\\":
            i += 2
            continue
        if ch == "'" and not double:
            j = word.find("'", i + 1)
            i = n if j < 0 else j + 1
            continue
        if ch == '"':
            double = not double
        elif ch == "`":
            return (i if first < 0 else first), None
        elif ch == "$" and i + 1 < n and (word[i + 1].isalnum() or word[i + 1] in "_{(@*#?!$-"):
            if first < 0:
                first = i
            bare = _VAR_NAME.match(word, i + 1)
            braced = bare is None and _VAR_BRACED.match(word, i + 1)
            if not bare and not braced:
                return first, None
            names.append((i, (bare or braced).end(), bare.group() if bare else braced.group(1)))
            i = (bare or braced).end()
            continue
        i += 1
    return first, names


@functools.lru_cache(maxsize=16)
def _live_ticks(scanned: str) -> tuple[list[int], list[int]]:
    """The offsets of the backticks in quote-stripped `scanned` that open or
    close a span, and the offset each line starts at. A backtick is escaped
    only by an odd run of backslashes right before it (`\\\\`` is an escaped
    backslash, then a live backtick); quoted ones are blanked there already.
    One pass per text."""
    ticks = [m.end() - 1 for m in re.finditer(r"(\\*)`", scanned) if len(m.group(1)) % 2 == 0]
    starts = [0] + [m.end() for m in re.finditer(r"\n", scanned)]
    return ticks, starts


def _span_close(scanned: str, at: int) -> int | None:
    """When `at` is inside a backtick span, the offset of the backtick that
    closes it (the end of the text when none does); None when it is not.
    Pairing, not position: an odd number of live backticks before `at` on its
    own line opened a span that `at` sits in, as `git` does in prose quoting
    `` `git status` ``, while a backtick after an even number opens a
    substitution, as in `git push -`echo f``. Only `at`'s line counts: a
    backtick in a comment or a heredoc body on an earlier line is no shell
    syntax, and one would flip the count. A backtick right before `at` opens a
    span too: the count goes wrong in prose, where an apostrophe (`user's`)
    pairs with a later one and blanks the backticks between them.

    A named miss: a backtick span that opens on an earlier line (or across a
    `\\`-newline) and closes on git's line. Its closing backtick counts as an
    opening one there, so a substituted flag later on that line is not read,
    and a git word glued to that closing backtick asks."""
    ticks, starts = _live_ticks(scanned)
    line = starts[bisect.bisect_right(starts, at) - 1]
    k = bisect.bisect_left(ticks, at)
    count = k - bisect.bisect_left(ticks, line)
    if count % 2 == 0 and not (count and ticks[k - 1] == at - 1):
        return None
    return ticks[k] if k < len(ticks) else len(scanned)


def _has_expansion(word: str) -> bool:
    """True when the shell substitutes part of `word` (see `_expansions`)."""
    return _expansions(word)[0] >= 0


def _at_command_start(scanned: str, start: int) -> bool:
    """True when the word holding position `start` is where a command starts:
    `git` is the whole word or its last path element, and only operators,
    assignments, options and prefix words (`sudo`, `env`, ...) come before it
    in its simple command."""
    i = start
    if i > 0 and scanned[i - 1] not in " \t\n;&|(){}`!/\\":
        return False
    while i > 0 and scanned[i - 1] not in " \t\n;&|(){}`!":
        i -= 1
    while True:
        while i > 0 and scanned[i - 1] in " \t":
            i -= 1
        if i == 0 or scanned[i - 1] in "\n;&|(){}`!":
            _spend(start - i)
            return True
        end = i
        while i > 0 and scanned[i - 1] not in " \t\n;&|(){}`!":
            i -= 1
        word = scanned[i:end]
        if not (
            word.lower() in _COMMAND_PREFIXES
            or word.startswith("-")
            or re.fullmatch(r"[A-Za-z_]\w*=\S*", word)
        ):
            _spend(start - i)
            return False


def _assignments(parts: list[str]) -> dict[str, list[str | None]]:
    """Every value each name is assigned in the command, in any part; None for
    a value that is not a plain literal."""
    found: dict[str, list[str | None]] = {}
    for part in parts:
        scanned = _stripped(part)
        for pattern in (_ASSIGN, _PS_ASSIGN):
            read_to = -1
            for m in pattern.finditer(scanned):
                if m.start() < read_to:
                    # Inside the value before it (`X=$(Y=v)`), which is not a
                    # literal: its names are not read, and in `X=$(X=$(...`
                    # each would run to the end of the text.
                    continue
                end = read_to = _word_end(part, m.end())
                raw = part[m.end():end]
                value: str | None = None
                # A bare word after PowerShell's `=` is a command it runs
                # (`$X = Get-Verb`), so only a quoted string is a literal there.
                bare_ps = pattern is _PS_ASSIGN and not raw.startswith(("'", '"'))
                if not bare_ps and not _has_expansion(raw) and not part.startswith("(", end):
                    value = _unquote(raw)
                    if not _LITERAL_VALUE.fullmatch(value):
                        value = None
                found.setdefault(m.group(1), []).append(value)
    return found


def _wrapper_bodies(part: str, every: bool = False) -> list[str]:
    """The text each shell wrapper in `part` hands to a shell: its words after
    the wrapper, unquoted and joined, plus a decoded `-EncodedCommand`. Only
    the bodies that hold `git` or `gh`, unless `every`, the reading for the
    other guards (`_every_body`), which also skips quoted-heredoc data and
    carries the wrapper's assignment prefix."""
    bodies: list[str] = []
    read_to = -1
    scanned = _stripped(part)
    data = _quoted_heredoc_bodies(part, scanned) if every else []
    starts = [a for a, _ in data]
    for m in _WRAPPER.finditer(scanned):
        if m.start() < read_to:
            # Among the words of the wrapper before it, so in that body, where
            # the next depth finds it. Reading it here too walked the rest of
            # the command once per wrapper.
            continue
        k = bisect.bisect_right(starts, m.start()) - 1
        if k >= 0 and m.start() < data[k][1]:
            continue  # heredoc data, not a command
        spans = _command_words(part, m.end())
        read_to = spans[-1][1] if spans else m.end()
        words = [_unquote(part[a:b]) for a, b in spans]
        prefix = _env_prefix(part, scanned, m.start()) if every else ""
        bodies.append(prefix + " ".join(words))
        for flag, value in zip(words, words[1:]):
            if _PS_ENCODED.fullmatch(flag):
                try:
                    bodies.append(prefix + base64.b64decode(value).decode("utf-16-le"))
                except (ValueError, UnicodeDecodeError):
                    pass
    if every:
        return bodies
    return [b for b in bodies if _HAS_GIT.search(b)]


def _resolve(raw: str, names: dict[str, list[str | None]]) -> list[str] | None:
    """The values word `raw` can take, unquoted, at most `_EXPAND_MAX_LINES + 1`
    of them; None when one cannot be known: an expansion other than `$NAME`, or
    a name with no value or one that is not a plain literal."""
    first, spans = _expansions(raw)
    if first < 0:
        return [_unquote(raw)]
    if spans is None:
        return None
    choices: list[list[str]] = []
    for _, _, name in spans:
        values = names.get(name)
        if not values or any(v is None for v in values):
            return None
        choices.append(list(dict.fromkeys(values)))
    readings: list[str] = []
    for combo in itertools.islice(itertools.product(*choices), _EXPAND_MAX_LINES + 1):
        pieces, at = [], 0
        for (a, b, _), value in zip(spans, combo):
            pieces += [raw[at:a], value]
            at = b
        pieces.append(raw[at:])
        readings.append(_unquote("".join(pieces)))
    return list(dict.fromkeys(readings))


def _rewrites(part: str, names: dict[str, list[str | None]]) -> tuple[list[str], bool]:
    """Lines `part` can stand for once one expansion or quoted flag in a git
    command is filled in, and whether some expansion could not be resolved."""
    scanned = _stripped(part)
    lines: list[str] = []
    unresolved = False

    def tail_end(at: int) -> int:
        stop = _TAIL_RE.match(scanned, at).end()
        _spend(stop - at)
        return stop

    for m in _GIT_SUBCOMMAND_EXPANDED.finditer(scanned):
        opts = scanned[m.start(1):m.end(1)].split()
        if not _at_command_start(scanned, m.start()) or (
            opts and _GIT_VALUE_OPT.fullmatch(opts[-1])
        ):
            continue
        sub = m.end()
        # Inside a backtick span, the git command ends where the span closes.
        close = _span_close(scanned, m.start())
        end = _word_end(part, sub, close)
        raw = part[sub:end]
        if not _has_expansion(raw) and _unquote(raw) == raw:
            continue  # cut at the span's close, it is a plain word
        values = _resolve(raw, names)
        if values is None:
            unresolved = True
            continue
        stop = tail_end(end) if close is None else min(tail_end(end), close)
        lines += [part[m.start():sub] + v + part[end:stop] for v in values]
        if len(lines) > _EXPAND_MAX_LINES:
            return lines, True
    for pattern in (_PUSH, _RESET, _BRANCH):
        for m in pattern.finditer(scanned):
            if not _at_command_start(scanned, m.start()):
                continue
            operand = False
            close = _span_close(scanned, m.start())
            limit = m.end(1) if close is None else min(m.end(1), close)
            for a, b in _command_words(part, m.start(1), limit):
                raw = part[a:b]
                first, _ = _expansions(raw)
                if first < 0:
                    value = _unquote(raw)
                    if value == raw or not value.startswith(("-", "+")):
                        operand = operand or not value.startswith("-")
                        continue
                    values = [value]  # a quoted or escaped flag or refspec
                else:
                    values = _resolve(raw, names)
                if values is None:
                    lead = _unquote(raw[:first])
                    if lead.startswith("+"):
                        values = [lead + "x"]  # a forced refspec, whatever follows
                    elif lead.startswith("-") and "=" in lead:
                        values = [lead[: lead.index("=") + 1] + "x"]  # the flag is named
                    elif lead.startswith("-"):
                        unresolved = True
                        continue
                    else:
                        unresolved = unresolved or (
                            not operand and raw.startswith("$") and _SINGLE_VAR.fullmatch(raw) is not None
                        )
                        continue
                lines += [part[m.start():a] + v + part[b:limit] for v in values]
                if len(lines) > _EXPAND_MAX_LINES:
                    return lines, True
                break  # the rewritten line is read again for the next one
    return lines, unresolved


def _expand(command: str) -> tuple[list[str], str | None]:
    """`command` as a list of parts to read: the command itself, then each
    wrapper body and each rewritten git line; and the reason to ask when it
    could not be read in full (an expansion it could not resolve, a cap it
    reached), else None."""
    parts = [command]
    _WORK_LEFT[0] = _WORK_FACTOR * (len(command) + _EXPAND_SLACK)
    try:
        return _expand_into(parts)
    except _OverBudget:
        return parts, UNRESOLVED_REASON
    finally:
        _WORK_LEFT[0] = float("inf")


def _expand_into(parts: list[str]) -> tuple[list[str], str | None]:
    """`_expand`'s reading, adding to `parts` (which holds the command) as it
    goes, so a reading cut short by `_OverBudget` keeps what it found."""
    command = parts[0]
    budget = len(command) + _EXPAND_SLACK
    frontier = [command]
    for _ in range(_WRAP_DEPTH):
        frontier = [b for p in frontier for b in _wrapper_bodies(p)]
        if not frontier:
            break
        parts += frontier
        budget -= sum(len(b) for b in frontier)
        if budget < 0:
            return parts, UNRESOLVED_REASON
    else:
        if any(_NAMES_GIT.search(b) for p in frontier for b in _wrapper_bodies(p)):
            return parts, WRAP_DEPTH_REASON
    names = _assignments(parts)
    unresolved = False
    seen = set(parts)
    frontier = list(parts)
    for _ in range(_EXPAND_ROUNDS):
        new: list[str] = []
        for part in frontier:
            lines, missed = _rewrites(part, names)
            unresolved = unresolved or missed
            for line in lines:
                if line not in seen:
                    seen.add(line)
                    new.append(line)
        if not new:
            return parts, UNRESOLVED_REASON if unresolved else None
        parts += new
        budget -= sum(len(line) for line in new)
        if budget < 0 or len(parts) > _EXPAND_MAX_LINES:
            return parts, UNRESOLVED_REASON
        frontier = new
    return parts, UNRESOLVED_REASON




@functools.lru_cache(maxsize=4)
def expand(command: str) -> tuple[tuple[str, ...], str | None]:
    """`_expand`, cached and frozen: `ask-destructive-git`'s `_scan` reads it,
    and its `ALLOW_DESTRUCTIVE_GIT` note path and `main` read the same entry
    rather than reading the command again. An exception is not cached, so a
    reading that raises makes that enforcing hook ask as one that could not
    run, exactly as it did when the reading lived there."""
    parts, unread = _expand(command)
    return tuple(parts), unread



# --- The parts the other guards read ----------------------------------------
# `expand` reads only what can hold a git command, and its verdicts must not
# move, so the bodies every other guard needs (`bash -c "echo hi > ../x"`) are a
# second reading: `_every_body`, under the same caps, with `_wrapper_bodies`'
# `every`. That differs from `expand`'s reading in three ways, each because a
# guard reads the part as a command typed bare:
#   - every body, whatever it runs;
#   - a wrapper inside the body of a heredoc with a QUOTED delimiter
#     (`<<'EOF'`, `<<"EOF"`, `<<\EOF`) is data and is skipped: a commit message
#     that names `bash -c` in prose is no command, and a guard that knows the
#     body is literal (`${CLAUDE_PLUGIN_ROOT}` in it is text) would read the
#     part bare and block. `strip_quoted_spans` leaves most bodies visible, so
#     this reading finds them itself. An unquoted delimiter's body is read: its
#     `$(...)` and backticks run;
#   - assignment words right before the wrapper (`X=1 bash -c '...'`) are put
#     in front of the body as `export X=1;`, since they are set in the shell
#     that runs it. Named miss: an assignment or `export` earlier in the
#     command (`export X=1; bash -c '...'`) is not carried, so a guard that
#     reads variables sees the body without it.
# Past a cap it returns what it found; the asks for what was not read stay
# with `ask-destructive-git`, for a body that names git.
_HEREDOC_START = re.compile(r"<<(-?)[ \t]*(?=['\"\\])")
_HEREDOC_DELIM = re.compile(r"""'([A-Za-z0-9_]+)'|"([A-Za-z0-9_]+)"|\\([A-Za-z0-9_]+)""")
_ENV_WORD = re.compile(r"[A-Za-z_]\w*=\S*")
_ENV_STOP = " \t\n;&|(){}`!"


def _quoted_heredoc_bodies(part: str, scanned: str) -> list[tuple[int, int]]:
    """The `(start, end)` of each body in `part` whose heredoc delimiter is
    quoted, in order. The operator is found on the quote-stripped text, so a
    `<<'EOF'` inside a string is none, and its delimiter read from the raw
    text at the same offset. A body runs to the line that is its delimiter
    (after tabs, for `<<-`), or to the end. An operator inside an earlier body
    is text and is skipped, so each character is searched once."""
    spans: list[tuple[int, int]] = []
    done = 0
    for m in _HEREDOC_START.finditer(scanned):
        if m.start() < done:
            continue
        d = _HEREDOC_DELIM.match(part, m.end())
        nl = part.find("\n", m.end())
        if d is None or nl < 0:
            continue
        word = d.group(1) or d.group(2) or d.group(3)
        tabs = r"\t*" if m.group(1) else ""
        close = re.compile("^" + tabs + re.escape(word) + r"[ \t]*\r?$", re.M).search(part, nl + 1)
        end = close.start() if close else len(part)
        _spend(end - m.start())
        spans.append((nl + 1, end))
        done = end
    return spans


def _env_prefix(part: str, scanned: str, at: int) -> str:
    """The assignment words right before position `at` in its simple command,
    each as `export NAME=value; `, in their order."""
    assigned: list[str] = []
    i = at
    while True:
        j = i
        while j > 0 and scanned[j - 1] in " \t":
            j -= 1
        k = j
        while k > 0 and scanned[k - 1] not in _ENV_STOP:
            k -= 1
        if k == j or not _ENV_WORD.fullmatch(scanned[k:j]):
            break
        assigned.append(part[k:j])
        i = k
    _spend(at - i)
    return "".join("export " + w + "; " for w in reversed(assigned))


def _every_body(command: str) -> list[str]:
    """Every wrapper body (`_wrapper_bodies(..., every=True)`), `_WRAP_DEPTH`
    levels deep, in the order found, under `_expand`'s caps: what it found when
    one is reached."""
    found: list[str] = []
    budget = len(command) + _EXPAND_SLACK
    _WORK_LEFT[0] = _WORK_FACTOR * budget
    try:
        frontier = [command]
        for _ in range(_WRAP_DEPTH):
            frontier = [b for p in frontier for b in _wrapper_bodies(p, every=True)]
            budget -= sum(map(len, frontier))
            if not frontier or budget < 0:
                break
            found += frontier
    except _OverBudget:  # past the work cap: what was found so far
        pass
    finally:
        _WORK_LEFT[0] = float("inf")
    return found

@functools.lru_cache(maxsize=4)
def guard_parts(command: str) -> tuple[str, ...]:
    """The parts the Bash dispatcher hands every guard that reads parts: every
    wrapper body in `command` (`_every_body`), each once, in order, the
    command itself left out. Rewritten git lines are not among them: they
    fill in a git subcommand or a push, reset or branch flag, which only
    `ask-destructive-git` reads."""
    return tuple(b for b in dict.fromkeys(_every_body(command)) if b != command)
