#!/usr/bin/env python3
r"""PreToolUse hook: WARN (never block) when a Bash heredoc body carries a
backslash escape that the shell/Python layering will silently eat.

THE FAILURE. Writing file content through `python3 - <<'PY' ... PY` looks safe
because the delimiter is quoted, so the shell does not expand `$` or backticks.
It does NOT protect a backslash escape that the INNER language then re-reads: a
`"\n"` intended as a two-character Python escape arrives as a real newline,
which inside a string literal is a `SyntaxError` — and inside a data string is a
silently wrong value. The same applies to `\r`, `\t`, `\b`, `\x00` and friends.

WHY A HOOK RATHER THAN ANOTHER SENTENCE. This is a third-instance re-offense.
It is already written down twice: user memory
(`feedback_no_heredocs_for_file_content` — "shell+Python layers mangle escapes
(\n, \b, \x00); use Write/Edit") and
`skills/_shared/references/bash-discipline.md` ("no heredoc subshells"). Both
were in context and it happened anyway, three times in one session (2026-08-23):
twice writing mutant batches whose anchors needed a literal `\n`, and once MORE
while writing the verification for the fix to the first two. A rule that loses
three times to the same shape is not under-stated; it is at the wrong rung.

DETECTION, deliberately narrow. The command must (a) open a heredoc, and (b)
carry a backslash escape from the set that actually gets eaten, in the heredoc
body. A heredoc with no such escape is left alone — heredocs are legitimate and
this repo uses them constantly for ordinary multi-line text. That narrowness is
the point: a hook that fires on every heredoc would be muted within a day.

WARN, never block. A heredoc containing `\n` can be entirely correct (a regex
written as a raw string, prose describing an escape). Blocking would over-fire
on a judgement the author is better placed to make; the warning just prompts a
look before a mangled file lands.

Best-effort: any parse failure exits 0 silently — a warning hook must never
disrupt the workflow.
"""

from __future__ import annotations

import json
import re
import sys

# Deliberately no `_dispatch_lib` import and no `sys.path` insert. The sibling
# warn hooks carry both because they use its git/quoting helpers; this one is
# pure text over the command string, so copying the block would have been an
# inert stanza whose own comment claimed a protection it did not provide.

# Opening delimiter: `<<WORD`, `<<'WORD'`, `<<"WORD"`, `<<-WORD`.
#
# The two lookarounds are not decoration — both were measured firing on real
# commands. `(?<!<)` rejects a HERESTRING (`grep foo <<<bar`), which otherwise
# matched at offset 1 and made `bar` a delimiter. `(?!<)` rejects the same shape
# from the other side. The arithmetic left-shift (`$((1 << n))`) also matches
# this pattern by construction — `n` is a valid delimiter name — and is excluded
# instead by requiring a terminator line, below.
_HEREDOC_OPEN = re.compile(r"(?<!<)<<(-?)\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\2(?!<)")

# The escapes that a shell/inner-language sandwich actually eats.
#
# Trimmed from the first cut's `[nrtbfva0xu]`. `\a \v \f \0` are near-noise —
# nobody writes them in a heredoc — and every character in the class widens the
# false-positive surface, which on a Windows checkout already includes `\t` and
# `\b` from any backslash-separated path with `temp` or `build` in it. `\U` and
# `\N` are added because they are real Python manglers the first cut missed.
_EATEN = "nrtbxuUN"


def _eaten_escapes(body: str) -> list[str]:
    """Distinct eaten escapes in `body`, sorted, skipping escaped backslashes.

    Counts backslash PARITY rather than looking one character behind. A single
    lookbehind gets `\\\\n` right (doubled, deliberate — leave it alone) but gets
    `\\\\\\n` wrong: three backslashes is an escaped backslash followed by a
    genuinely eaten `\\n`, and the lookbehind sees a backslash and stays silent.
    Only an odd run of backslashes actually escapes the character after it.

    PARITY ALONE IS A TWO-LAYER RULE, and a long even run is the three-layer
    case. "Even means the next character is literal" holds for shell → inner
    language. It stops holding when the inner language then re-reads the text as
    a string literal of its own: there, the author has DOUBLED an escape to
    survive one layer, and the run is even while the value still mangles.
    Measured — this hook stayed silent on a `python - <<'PY'` whose body carried
    `\\\\\\\\\\\\n` inside a `'''...'''` literal, and that command really did
    mangle and fail two steps later, which is the whole failure this hook exists
    to pre-empt.

    So a run of 4 or more also warns, whatever its parity. Exactly 2 stays
    silent: that is the one even run that is unambiguously a deliberate literal
    backslash-n, and it is common in a heredoc that writes a regex — widening to
    every even run would make this hook noisy on the file it most often guards.
    """
    found: set[str] = set()
    i = 0
    while i < len(body):
        if body[i] != "\\":
            i += 1
            continue
        run = 0
        while i < len(body) and body[i] == "\\":
            run += 1
            i += 1
        if (run % 2 or run >= 4) and i < len(body) and body[i] in _EATEN:
            found.add("\\" + body[i])
        # A run of exactly 2 is one `\\` pair — the next char is literal, and
        # that is the only even run left silent. See the docstring for why 4+
        # warns despite being even.
    return sorted(found)


def _heredoc_bodies(cmd: str) -> list[tuple[str, str]]:
    """Every `(delimiter, body)` pair the command opens.

    Two things this gets right that the first cut did not, both measured:

    - **Every opener on a line, not just the first.** `cat <<A <<B` opens two;
      `search()` found only `A` and left `B`'s body unscanned. Bash queues the
      bodies in opener order, which is what `finditer` reproduces.
    - **A terminator is REQUIRED.** Treating an unterminated opener's remaining
      text as the body sounds conservative, but it is what made `$((1 << n))`
      swallow the rest of the command and warn on any `\\n` anywhere in it. A
      real heredoc in a tool call is terminated; an arithmetic shift never is.
      The cost is a genuinely unterminated heredoc going unscanned — accepted,
      because a warn hook that cries wolf gets muted, and muted is the same as
      absent.

    Terminator matching follows bash: exact for `<<WORD`, leading whitespace
    stripped only for the tab-stripping `<<-WORD` form.
    """
    lines = cmd.splitlines()
    out: list[tuple[str, str]] = []
    consumed = 0  # index of the next line not yet claimed as some body

    for i, line in enumerate(lines):
        for m in _HEREDOC_OPEN.finditer(line):
            dash, delim = m.group(1), m.group(3)
            start = max(i + 1, consumed)
            end = None
            for j in range(start, len(lines)):
                candidate = lines[j].strip() if dash else lines[j]
                if candidate == delim:
                    end = j
                    break
            if end is None:
                continue  # unterminated — not a heredoc we can trust
            out.append((delim, "\n".join(lines[start:end])))
            consumed = end + 1
    return out


def offending_heredocs(cmd: str) -> list[tuple[str, list[str]]]:
    """`(delimiter, sorted distinct escapes)` for each body carrying an eaten escape."""
    found = []
    for delim, body in _heredoc_bodies(cmd):
        escapes = _eaten_escapes(body)
        if escapes:
            found.append((delim, escapes))
    return found


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0
    if not isinstance(payload, dict):
        return 0
    tool_input = payload.get("tool_input")
    cmd = tool_input.get("command", "") if isinstance(tool_input, dict) else ""
    if not isinstance(cmd, str) or not cmd:
        return 0

    offenders = offending_heredocs(cmd)
    if not offenders:
        return 0

    detail = "; ".join(
        f"<<{delim} carries {', '.join(esc)}" for delim, esc in offenders
    )
    print(
        f"[warn-heredoc-escape-mangling] {detail}. A quoted heredoc delimiter "
        f"stops the shell expanding `$` and backticks, but NOT a backslash "
        f"escape the inner language re-reads: `\\n` arrives as a real newline, "
        f"which is a SyntaxError inside a string literal and a silently wrong "
        f"value inside data. If the escape is meant to survive, use Write/Edit "
        f"for the file, or Write a script and run it by path.",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
