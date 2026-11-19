#!/usr/bin/env python3
"""Shell-text helpers for the git-matching Bash guards: quote stripping and the
linear-time git invocation matcher.

`strip_quoted_spans` blanks the text a shell treats as data (quoted spans, and
by whitelist some heredoc bodies) while keeping every offset, and
`GitInvocation` finds `git <global options> <subcommand>` in that text in linear
time. `GIT_CMD`, `GIT_SEP` and `GIT_GLOBAL_OPTS` are the shared pieces of the
grammar. Every leaf hook that matches a git command line imports from here
(`plugin-tests/tests/hooks/test_dispatch_lib.py`'s `_GIT_HOOK_FILES` holds the
list), and so do `_shell_read.py` and `_destructive_git_rules.py`. The two
commit-honesty guards hand each `GitInvocation` match to `_git_commit_args.py`,
which reads the arguments; `ask-broad-git-add.py` imports `strip_quoted_spans`
and `GIT_CMD` and walks tokens itself. Both ways are linear on hostile input;
composing `GIT_GLOBAL_OPTS` into a regex is not, see `GitInvocation`.

It lived in `_dispatch_lib.py` until that file held the dispatcher runner, the
budget and these helpers at once. It imports nothing outside the standard
library and nothing from its siblings, so it loads under `python3 -I` from any
cwd once its importer has put the hooks dir on `sys.path`, the bootstrap every
hook carries. Keep it import-cheap and side-effect-free: a failure here takes out
every git guard at once.
"""

from __future__ import annotations

import re

# --- Git command-line matching helpers --------------------------------------
# Shared by every git-matching guard (the module docstring says where the list
# is kept). Previously each of those files carried its own literal copy of this
# pattern — a bug fixed in one copy could silently persist in the others, and
# did: a long
# global option with a space-separated (non-`=`) value (`git --work-tree
# <path> push origin main`) bypassed all of them, and a quoted `-c`/`-C` value
# containing a space (`git -C "/path with space" checkout -b x`) bypassed the
# two hooks that didn't call `strip_quoted_spans` before matching. One
# definition, one fix site closes both classes at once and keeps them closed.


# The git executable token, including the Windows extension forms.
#
# `\bgit\s+` cannot match `git.exe` -- `\s` does not match `.` -- so every git
# guard in this plugin silently allowed the extension spellings. Measured before
# this constant existed: `git push origin main` blocked (exit 2) while
# `git.exe push origin main` and `git.cmd push origin main` both exited 0. That
# was the whole guard set at once: the push-to-main block, both `ask-*`
# confirmations, worktree isolation, and two warns.
#
# Reachable by ordinary use rather than by evasion -- PowerShell is a primary
# shell for this harness and its tab-completion emits `git.exe`.
#
# `_destructive_git_rules._GH_PR_MERGE` already spelled the sibling tool as
# `\bgh(?:\.(?i:exe|cmd|bat|com|ps1))?`, with a comment saying it exists
# "because Windows is the primary platform". The identical reasoning was never
# applied to `git`. This constant exists so the fix lands once instead of in six
# separate regexes -- the same rationale as `GIT_GLOBAL_OPTS` above.
#
# The command NAME is case-folded too. It was not, on the reasoning that this
# "matches the `gh` precedent" -- but that precedent is a gap, not a design, and
# citing it turned one oversight into two. Windows filesystems and shells are
# case-insensitive, so `GIT push origin main` and `GIT.EXE push origin main`
# both RUN, and both walked past every guard below while the lowercase
# `git.exe` was blocked. Closing the common spelling and leaving the trivially
# adjacent one open is not a defensible stopping point.
#
# This is a TRADE, not a free win, and the cost was measured rather than
# assumed. An earlier draft of this comment claimed an unrelated uppercase path
# segment could not match "because what follows it is a separator" -- true only
# while `GIT` is a NON-TERMINAL segment. Measured against the real composed
# pattern, against a `commit`-matching guard (measured, not reasoned):
#
#     cd /srv/GIT commit      old: no match   new: MATCHES
#     ls /d/GIT commit        old: no match   new: MATCHES
#
# Note WHICH guard: a terminal uppercase `GIT` path segment followed by a word
# is only reachable where that word is the subcommand being matched, so the
# exposure is a `commit` matcher's (`commit` is an ordinary English word),
# not a `push` matcher's -- `push` does not appear after a directory name in
# normal usage. Both cases above return no args at all.
#
# Sharper still: `strip_quoted_spans` deliberately does not blank HEREDOC bodies
# (its own docstring says so), so an uppercase `GIT` in ordinary prose inside a
# heredoc reaches `_COMMIT` too -- confirmed by running it, not inferred.
#
# Taken deliberately: an enforcing guard that over-blocks announces itself and
# is trivially worked around, whereas the `GIT push` bypass it closes is silent
# and defeats the guard entirely. Both directions are pinned by tests -- see
# `test_git_cmd_matches_every_runnable_spelling` and
# `test_git_cmd_does_not_over_match`.
GIT_CMD = r"\b(?i:git)(?:\.(?i:exe|cmd|bat|com|ps1))?"


def _blank_keeping_substitutions(text: str) -> str:
    """`text` with every character replaced by `#`, EXCEPT the `$(...)` and
    backtick substitutions the shell executes, which stay verbatim. Same length.
    An escaped `$` or backtick is literal text and is blanked."""
    out: list[str] = []
    i = 0
    while i < len(text):
        ch = text[i]
        if ch == "\\":
            out.append("##"[: len(text) - i])
            i += 2
            continue
        if ch == "$" and text.startswith("$(", i):
            depth, j = 0, i + 1
            while j < len(text):
                depth += (text[j] == "(") - (text[j] == ")")
                if depth == 0:
                    break
                j += 1
            end = min(j, len(text) - 1)  # unterminated: runs to the end
        elif ch == "`":
            j = i + 1
            while j < len(text) and text[j] != "`":
                j += 2 if text[j] == "\\" else 1
            end = min(j, len(text) - 1)
        else:
            out.append("#")
            i += 1
            continue
        out.append(text[i : end + 1])
        i = end + 1
    return "".join(out)[: len(text)]


_HEREDOC_OP = re.compile(
    r"(?<!<)<<(?!<)[ \t]*(?:'([A-Za-z0-9_]+)'|\"([A-Za-z0-9_]+)\"|\\([A-Za-z0-9_]+))"
)
# Any heredoc operator at all, used only for the operator-count cap.
_ANY_HEREDOC = re.compile(r"<<(?!<)")
# Caps. Past either, every body is left VISIBLE (a guard fails toward asking).
_HEREDOC_MAX_OPS = 200
_HEREDOC_MAX_LINE = 4096

# Words that run, or hand text to, an interpreter, or wrap a command that does.
# Matched on the basename of every word of the command, so `/bin/bash` and
# `bash.exe` count.
_INTERPRETERS = frozenset(
    "bash sh zsh dash ksh csh tcsh fish pwsh powershell cmd node deno bun perl "
    "ruby php lua ssh source eval xargs exec busybox su sudo env nohup command .".split()
)
_WORD_SPLIT = re.compile(r"[\s|;&()<>\"'`$={},]+")
_SHELL_VAR = re.compile(r"\$\{?(?:SHELL|0)\b")

# The ONLY heredoc that is blanked outright: the WHOLE command is one message
# command and nothing else. It is matched in full, from the first character to
# the last, so the shell cannot be reading it any other way: no comment, no
# single quote, no backslash, no pipe, no redirect, no `$`, no backtick and no
# second heredoc can appear anywhere outside the body, and the only words are
# plain words or short double-quoted strings of safe characters.
_W = r"[A-Za-z0-9_.,:=@+%~/-]+"
_DQ = r"\"[A-Za-z0-9 ._,:/()#@%+=~-]*\""
_ARG = rf"(?:{_W}|{_DQ})"
_MESSAGE_COMMAND = re.compile(
    rf"(?:(?:git (?:add|status)|cd)(?: {_ARG})* && )*"
    r"(?:git (?:commit|tag|notes)|gh (?:pr (?:create|edit|comment|review|merge)"
    r"|issue (?:create|edit|comment)|release create))"
    rf"(?: {_ARG})* \"\$\(cat <<(?P<q>['\"])(?P<w>[A-Za-z0-9_]+)(?P=q)[ \t]*\r?\n"
    r"(?P<body>(?:(?!(?P=w))[^\n]*\n)*)"
    r"(?P=w)\r?\n\)\""
    rf"(?: {_ARG})*"
    rf"(?: && (?:git (?:status|push|add|log|diff|show|fetch|pull)"
    rf"|gh pr (?:view|checks|create|edit|comment|ready)|cd)(?: {_ARG})*)*"
    r"\s*"
)


def _runs_an_interpreter(text: str) -> bool:
    if _SHELL_VAR.search(text):
        return True
    for word in _WORD_SPLIT.split(text):
        base = word.replace("\\", "/").rsplit("/", 1)[-1].lower()
        for ext in (".exe", ".cmd", ".bat", ".com", ".ps1"):
            if base.endswith(ext):
                base = base[: -len(ext)]
                break
        if base in _INTERPRETERS or base.startswith("python"):
            return True
    return False


def _blank_heredoc_bodies(cmd: str) -> str:
    """Blank heredoc text that is data; leave every other body as it was.

    Two things are blanked, both by whitelist, everything else stays VISIBLE.

    1. The body of a message heredoc, only when the WHOLE command fully matches
       `_MESSAGE_COMMAND` (one `git commit|tag|notes` / `gh pr|issue|release`
       command whose message is `"$(cat <<'WORD' ... WORD newline )"`, with
       nothing in the command the shell could read differently).
    2. Markdown backtick spans in the body of the FIRST heredoc operator, which
       main always blanked: only when the body has no quote character (main
       paired quotes before backticks) and that operator has a plain quoted
       delimiter, nothing before its line contains `<<`, `#`, a backtick, a
       backslash or an unbalanced quote, the operator line has none of those
       either, and no interpreter word appears anywhere in the command.

    Newlines and length are kept. One linear pass; past `_HEREDOC_MAX_OPS`
    operators nothing is blanked."""
    if "<<" not in cmd:
        return cmd
    ops = list(_HEREDOC_OP.finditer(cmd))
    if not ops or len(_ANY_HEREDOC.findall(cmd)) > _HEREDOC_MAX_OPS:
        return cmd
    out = list(cmd)
    message = _MESSAGE_COMMAND.fullmatch(cmd)
    if message is not None:
        _blank_data(out, *message.span("body"))
        return "".join(out)
    first = ops[0]
    if cmd.find("<<") != first.start():
        return cmd  # an earlier `<<` the shell may read as the real operator
    nl = cmd.find("\n", first.end())
    if nl < 0 or nl - cmd.rfind("\n", 0, first.start()) > _HEREDOC_MAX_LINE:
        return cmd
    delim = first.group(1) or first.group(2) or first.group(3)
    term = cmd.find("\n" + delim + "\n", nl)
    if term < 0 and not cmd.endswith("\n" + delim):
        return cmd  # no terminator line: left visible
    body_end = term + 1 if term >= 0 else len(cmd) - len(delim)
    for ch in ("#", "`", "\\"):
        at = cmd.find(ch)
        if at != -1 and at < nl:
            return cmd
    head = cmd[:nl]
    if (head.count("'") - (2 if first.group(1) else 0)) % 2 or (
        head.count('"') - (2 if first.group(2) else 0)
    ) % 2:
        return cmd  # an unbalanced quote: the operator may be inside a string
    if _runs_an_interpreter(cmd[: nl + 1] + cmd[body_end:]):  # words in the body are data
        return cmd
    body = cmd[nl + 1 : body_end]
    if "'" in body or '"' in body:
        return cmd  # main paired quotes first; with none here raw pairing is the same
    for span in re.finditer(r"`[^`]*`", body):
        _blank_data(out, nl + 1 + span.start() + 1, nl + 1 + span.end() - 1)
    return "".join(out)


def _blank_data(out: list[str], a: int, b: int) -> None:
    """Blank `out[a:b]` in place, keeping line breaks so line structure holds."""
    for i in range(a, b):
        if out[i] not in "\r\n":
            out[i] = "#"


def strip_quoted_spans(cmd: str) -> str:
    """Replaces the contents of every quoted span with same-length,
    non-whitespace placeholder characters (the quote delimiters themselves are
    left in place) EXCEPT command substitutions the shell executes: the body of
    a `$(...)` or backtick span inside double quotes, and any unquoted backtick
    span, stays visible (single-quoted text is never executed, so it is always
    blanked). A matcher below doesn't trip on a `git commit` mentioned
    inside an echoed string or a commit message, AND so a global option's quoted
    value (`-C "/path with space"`) becomes a single whitespace-free token
    before `GIT_GLOBAL_OPTS` tries to match it — the value-consuming
    alternatives below all use `\\S+`, which cannot span an un-stripped
    internal space on its own.

    Length-preserving is deliberate, not incidental: it's what lets a caller
    that captures a match GROUP against the scanned string (e.g. a branch
    name) re-slice the SAME start/end offsets out of the original, unscanned
    command to recover the real text — a naive collapse-to-`''` would shift
    every later offset and silently return the placeholder instead of the
    real value for anything captured after the first quoted span. Note the
    re-sliced text still carries its surrounding quote characters, so callers
    strip them (`.strip("'\\"")`) before use.

    Scope, stated precisely so nobody assumes more than it does:

    - Heredoc bodies stay VISIBLE (as on main) except by whitelist
      (`_blank_heredoc_bodies`). (1) The body of a message heredoc is blanked
      only when the WHOLE command fully matches `_MESSAGE_COMMAND`: optional
      `git add|status`/`cd` words and `&&`, then `git commit|tag|notes` or
      `gh pr create|edit|comment|review|merge`, `gh issue create|edit|comment`,
      `gh release create` (no global options), plain words or short
      double-quoted strings of safe characters, then
      `"$(cat <<'WORD'` newline body newline `WORD` newline `)"`, then optional
      such words and `&& git status|push|add|log|diff|show|fetch|pull`. Because
      it is a full match there is no comment, single quote, backslash, pipe,
      redirect, `$`, backtick or second heredoc anywhere outside the body, so
      the shell cannot be reading the operator any other way, and no
      interpreter can be handed the text. (2) Markdown backtick spans in the
      body of the FIRST heredoc operator stay blanked, as on main, only when the
      body has no quote character (main paired quotes before backticks) and the
      operator has a plain quoted delimiter, no earlier `<<`, `#`, backtick or
      backslash appears up to its line, quotes before it balance, and no
      interpreter word (`bash sh ssh source . eval xargs sudo env python*
      $SHELL $0 …`, any path or `.exe` form) is outside the body. A bare
      `$(cat <<…)` never qualifies: its output may be run. Everything else
      (bare `cat <<'EOF'`, `tee`, `git commit -F -`, `--body-file -`, unquoted
      or odd delimiters, `<<-`, a missing terminator, `<<<`) is visible. Past
      200 operators or a 4096-char operator line nothing is blanked.
    - Accepted: a flag now ends at `)` or a backtick (`_destructive_git_rules.py`'s
      `_END`), so prose such as `# undo with (git reset --hard)` in a comment, or
      a PowerShell backtick escape, can ask; comments were always scanned.
    - NOT handled HERE — `bash -c '…'` / `sh -c` / `eval '…'` bodies are
      quoted, so blanked. `_shell_read.py` reads them: the Bash dispatcher runs
      every guard that reads parts on each wrapper body `guard_parts` finds, and
      `ask-destructive-git.py` reads `expand` (wrapper bodies that hold git, and
      `git $X` expansions) itself. A caller that uses this function alone, with
      neither, still sees a wrapped command blanked.
    - NOT handled — the paren counter ignores quotes and `case` patterns, and
      the single-quote pass runs first, so an apostrophe in earlier prose can
      pair with a later one.
    - NOT handled — escaped or nested quotes (`\\'`, `"a 'b' c"` interactions),
      including a double quote inside a `$(...)` that sits in double quotes.
    - NOT handled — `<(...)` / `>(...)` process substitution inside double
      quotes, which the shell does not execute there; unquoted ones were never
      blanked.
    - INTENTIONALLY matches shell semantics for a mid-word apostrophe:
      `echo don't && git push origin main && echo won't` collapses the span
      between the two apostrophes, so the `git push` disappears from the
      scanned string and the hook allows it. That is CORRECT — bash reads the
      same span as one single-quoted literal and never runs the push. Do not
      "fix" this by requiring quotes to sit at token boundaries; that would
      make the hooks fire on commands the shell would not execute."""

    def _placeholder(match: re.Match[str]) -> str:
        span = match.group(0)
        return span[0] + "#" * (len(span) - 2) + span[-1]

    def _double_quoted(match: re.Match[str]) -> str:
        span = match.group(0)
        return span[0] + _blank_keeping_substitutions(span[1:-1]) + span[-1]

    stripped = _blank_heredoc_bodies(cmd)
    stripped = re.sub(r"'[^']*'", _placeholder, stripped)
    stripped = re.sub(r'"[^"]*"', _double_quoted, stripped)
    # No backtick pass: an unquoted backtick span is a command substitution the
    # shell runs, and one inside single quotes is already blanked above.
    return stripped


# git GLOBAL options that may sit between `git` and the subcommand — consumed
# so `git -c core.x=y commit`, `git -C /path checkout`, `git --work-tree /path
# push origin main` are not a bypass. `-c KEY=VAL` / `-C PATH` take a
# following value token (bare, or — once `strip_quoted_spans` has run — a
# same-length `#`-filled quoted token such as `"################"`, which is
# whitespace-free and so matches `\S+` as one token). A NAMED, closed set of long options that also
# take their value as a separate space-delimited token (`--git-dir`,
# `--work-tree`, `--namespace`, `--super-prefix`) get the same optional
# space-value treatment; every other short/long flag is a single token
# (`--long[=val]` only, no bare-space form). The named-option list is
# deliberately closed rather than "any --long-opt may take a following
# value" — a blanket rule risks the matcher swallowing the real subcommand
# token whenever a value-less flag (`--bare`, `--no-pager`, `--paginate`) is
# immediately followed by it. Best-effort, not an exhaustive git-argument
# parser: an option shape outside this list, or one this hasn't been tested
# against, can still slip through — see each hook's own docstring for its
# specific detection scope.
# Horizontal whitespace, or a backslash line continuation. Defined HERE rather
# than in a leaf hook because `GIT_GLOBAL_OPTS` below needs it and every git-
# matching hook imports it — one definition, so the two cannot drift.
#
# A continuation is a JOINED line, so it separates tokens; a bare newline ENDS
# the command and must not. Getting one separator position wrong is this
# package's most repeated defect, and `GIT_GLOBAL_OPTS` was the last position
# still on a plain `\s+` after `_SEP` fixed the others. That plain `\s+` was
# wrong in BOTH directions at once, each verified against a real shell:
#
#   git -C . \<newline> push --force origin f   — one command, ran, NOT matched
#   git -c x=y<newline>  push --force origin f  — two commands, matched as one
#
# The first silently disarmed the force-push, `reset --hard`, branch-delete and
# working-tree-discard guards alike, because every one of them composes this
# blob. A guard that allows the thing it exists to stop is the worst failure
# this layer has, and it sat behind the one separator nobody re-checked.
GIT_SEP = r"(?:[ \t]|\\\r?\n)+"

_GIT_GLOBAL_VALUE_OPTS = r"(?:git-dir|work-tree|namespace|super-prefix)"
# The four option shapes, shared by `GIT_GLOBAL_OPTS` and `_GIT_OPT_STEPS` below
# so the two cannot drift.
_GIT_OPT_VALUED = r"-[cC]" + GIT_SEP + r"\S+"
_GIT_OPT_NAMED = r"--" + _GIT_GLOBAL_VALUE_OPTS + r"\b"
_GIT_OPT_SHORT = r"-[A-Za-z]"
_GIT_OPT_LONG = r"--[A-Za-z][\w-]*(?:=\S+)?"
# The grammar as one regex. Kept as the reference definition and for repos
# whose own hooks import it, but no guard here composes it into a search
# any more: see `GitInvocation` for why (it took 25 s on a 28 KB command).
GIT_GLOBAL_OPTS = (
    r"(?:"  # outer repetition group — zero or more options, each followed by whitespace
    r"(?:"  # inner alternation — exactly one option-shape per repetition
    r"(?:" + _GIT_OPT_VALUED + r")"
    r"|(?:" + _GIT_OPT_NAMED + r"(?:=\S+|" + GIT_SEP + r"\S+)?)"
    r"|(?:" + _GIT_OPT_SHORT + r")"
    r"|(?:" + _GIT_OPT_LONG + r")"
    r")"
    + GIT_SEP +
    r")*"
)

# One step of `GIT_GLOBAL_OPTS`: one option and its trailing separator, in the
# order the regex engine tries them. Each step has one useful end: a shorter
# `\S+` or separator leaves the next item starting on a character no option and
# no subcommand can start with. The named option's `=value` and value-less
# forms are left to the long-option step, which reads them to the same end with
# only failing steps tried in between; the regex reading `--git-dir=x` both
# ways is what made a run of them exponential.
_GIT_OPT_STEPS = tuple(
    re.compile(shape + GIT_SEP)
    for shape in (
        _GIT_OPT_VALUED,
        _GIT_OPT_NAMED + GIT_SEP + r"\S+",
        _GIT_OPT_SHORT,
        _GIT_OPT_LONG,
    )
)
_GIT_HEAD = re.compile(GIT_CMD + GIT_SEP)


class GitMatch:
    """The parts of `re.Match` the git guards read: `group`, `start`, `end`,
    `span`. Group 0 runs from `git` to the end of the match."""

    __slots__ = ("string", "_spans")

    def __init__(self, string: str, spans: list[tuple[int, int]]) -> None:
        self.string = string
        self._spans = spans

    def span(self, group: int = 0) -> tuple[int, int]:
        return self._spans[group]

    def start(self, group: int = 0) -> int:
        return self._spans[group][0]

    def end(self, group: int = 0) -> int:
        return self._spans[group][1]

    def group(self, group: int = 0) -> str | None:
        start, end = self._spans[group]
        return None if start < 0 else self.string[start:end]


class GitInvocation:
    """Finds `GIT_CMD + GIT_SEP + GIT_GLOBAL_OPTS + after` in linear time.

    Same matches, groups and spans as `re.compile(<that>).finditer` and
    `.search`, but without the regex's re-walks. The regex walks the
    option run again from every `git` inside it, quadratic on `git -c git
    -c git ... status`; and `-c`/`-C` and the named long options each parse
    two ways (with a value, or as a bare flag), so on `git -c -c -c ... x` it
    tries every split, exponential (a 95-byte command took 6 s).

    Here the options are walked as steps, in the regex's own order: from a
    position, each step that matches is followed to its end first, and only
    when every step fails is `after` tried there. The answer from a position
    depends on nothing before it, so each position is worked out once per
    text and shared by every `git` that reaches it.

    `capture_opts=True` adds the options run as group 1, ahead of `after`'s
    groups, the way `"(" + GIT_GLOBAL_OPTS + ")"` numbered it. Pass text
    that has been through `strip_quoted_spans`, as with the regex, and
    `after` starts at the subcommand word, not at whitespace or a backslash
    (see `_GIT_OPT_STEPS` for why that keeps one end per step).
    """

    def __init__(self, after: str, capture_opts: bool = False) -> None:
        self.after = re.compile(after)
        self.capture_opts = capture_opts
        # Each step's one-end reading holds only while `after` cannot match at
        # whitespace or a backslash, so such a pattern is refused here rather
        # than matched wrongly later. Three probes catch a pattern that matches
        # empty or a separator before a word; they are a check, not a proof.
        if any(self.after.match(probe) for probe in (" x", "\tx", "\\x")):
            raise ValueError(
                f"GitInvocation: {after!r} can match at whitespace or a backslash; "
                "start it at the subcommand word"
            )

    def _resolve(self, text: str, start: int, failed: set) -> tuple | None:
        """`(position, after_match)` for the first place, in the regex's
        backtracking order, that options from `start` reach and `after`
        matches; None when there is none. `failed` holds the positions already
        known to lead nowhere, and gains the ones this call rules out.

        Only failures are kept: a success ends the match, and the next `git`
        searched for starts after it, beyond every position this call saw."""
        stack = [[start, 0]]  # each: a position, and the next step to try there
        while stack:
            frame = stack[-1]
            pos, step = frame
            if step < len(_GIT_OPT_STEPS):
                frame[1] = step + 1
                m = _GIT_OPT_STEPS[step].match(text, pos)
                if m is not None and m.end() not in failed:
                    stack.append([m.end(), 0])
                continue
            stack.pop()
            m = self.after.match(text, pos)
            if m is not None:
                return pos, m
            failed.add(pos)
        return None

    def finditer(self, text: str):
        failed: set = set()
        pos = 0
        while True:
            head = _GIT_HEAD.search(text, pos)
            if head is None:
                return
            found = self._resolve(text, head.end(), failed)
            if found is None:
                pos = head.start() + 1
                continue
            opts_end, m = found
            spans = [(head.start(), m.end())]
            if self.capture_opts:
                spans.append((head.end(), opts_end))
            spans += [m.span(g) for g in range(1, self.after.groups + 1)]
            yield GitMatch(text, spans)
            pos = m.end()

    def search(self, text: str) -> GitMatch | None:
        return next(self.finditer(text), None)
