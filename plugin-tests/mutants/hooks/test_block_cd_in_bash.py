"""Mutant batch for `tests/hooks/test_block_cd_in_bash.py`.

Run: python3 plugin-tests/mutate.py plugin-tests/mutants/hooks/test_block_cd_in_bash.py

`hooks/block-cd-in-bash.py` blocks `cd` inside a Bash tool call because the
working directory persists across calls in this session and silently breaks
whatever runs next. It has two separate rules, pinned by two separate halves
of the guard: the DIRECTIVE rule (a real `cd` that would move the working
directory) and the SHADOWING rule (a redefinition of `cd` as a function or
alias, blocked because it disables the guard rather than because it moves
anything). These mutants re-break one capability at a time across both rules,
plus the quote-stripping that keeps prose/commit-message `cd` from being
falsely flagged, plus the message text that tells a blocked caller which rule
fired.

The no-space shadow form (`cd() { ... }`, mutant 1 below) is the highest-value
entry here: `cla.io/overlays/codify-learnings.md` records a real 2026-08-13
incident where exactly that form was used to evade this guard, which is why
`shadows_cd` and its own test coverage exist at all.

The hook is a `.py` file with CRLF line endings on this checkout (confirmed:
`b"\\r\\n" in HOOK.read_bytes()`), so every anchor below is confined to a
single physical line — no `\\n` appears in any `old` string.

Paths resolve from this file's own location, never an absolute developer path.
"""

from pathlib import Path

DEV = Path(__file__).resolve().parents[2]  # <repo>/plugin-tests
PLUGIN = DEV.parent / ".claude" / "plugins" / "cla"
HOOK = PLUGIN / "hooks" / "block-cd-in-bash.py"
TARGETS = [DEV / "tests" / "hooks" / "test_block_cd_in_bash.py"]

MUTANTS = [
    (
        # Capability: SHADOWING via the no-space function form `cd() { ... }`.
        # This is the exact evasion recorded in cla.io/overlays/codify-learnings.md
        # (2026-08-13) — the space form `cd () { ... }` was already caught as a
        # side effect of the directive matcher, the no-space form was not, and
        # `shadows_cd` was added specifically to close that hole. Dropping this
        # alternative from `_SHADOW` reopens the exact hole the hook exists to
        # close: `cd() { :; }` (and its parenthesised-with-space sibling, which
        # shares this same alternative) would no longer be recognised as a
        # redefinition at all.
        "shadows_cd loses the cd() {...} form, reopening the exact 2026-08-13 evasion",
        HOOK,
        '    r"|cd\\s*\\(\\s*\\)\\s*\\{"                    # cd() {          /  cd ()  {',
        '    r""                                      # cd() {          /  cd ()  { [disabled]',
        TARGETS,
    ),
    (
        # Capability: SHADOWING via `alias cd=...`. A shell alias is a second,
        # equally real way to redefine what the word `cd` means, and the hook's
        # own docstring calls out `alias cd=true` by name. Dropping this
        # alternative would let `alias cd=true` (and `alias cd=/bin/true; cd
        # /tmp`, which the guard also pins) sail past shadows_cd undetected.
        "shadows_cd loses the alias cd=... form",
        HOOK,
        '    r"|alias\\s+cd="                          # alias cd=...',
        '    r""                                        # alias cd=... [disabled]',
        TARGETS,
    ),
    (
        # Capability: the DIRECTIVE rule catches `cd` at the very START of a
        # command, not just after a separator. Real Bash calls in this repo are
        # very often a bare `cd /some/path` with nothing before it — that is the
        # single most common way this hook actually fires. Dropping the `^`
        # alternative means a leading `cd` no longer counts as a directive at
        # all; only `cd` preceded by `;`, `&`, `|`, or a newline would still be
        # caught.
        "the directive matcher stops treating a leading cd as a directive",
        HOOK,
        '    pattern = re.compile(r"(?:^|[;&|\\n])\\s*cd\\s+\\S", re.MULTILINE)',
        '    pattern = re.compile(r"(?:[;&|\\n])\\s*cd\\s+\\S", re.MULTILINE)',
        TARGETS,
    ),
    (
        # Capability: the DIRECTIVE rule catches a `cd` after a bare `;`
        # separator, not just at the start of a command. Unlike the `\n` case
        # (which `re.MULTILINE`'s `^` already matches redundantly, making a
        # `\n`-only mutant here unkillable — confirmed empirically and left
        # out rather than included), `;` mid-string is NOT covered by `^` at
        # all, so dropping it from the separator class genuinely stops a
        # command like `ls; cd /tmp` from being recognised as containing a
        # directive.
        "the directive matcher stops treating a bare ; as a cd separator",
        HOOK,
        '    pattern = re.compile(r"(?:^|[;&|\\n])\\s*cd\\s+\\S", re.MULTILINE)',
        '    pattern = re.compile(r"(?:^|[&|\\n])\\s*cd\\s+\\S", re.MULTILINE)',
        TARGETS,
    ),
    (
        # Capability: DOUBLE-quote spans are blanked before matching, so a `;`
        # or `cd` sitting inside a double-quoted commit message doesn't arm the
        # matcher. Turning this `re.sub` into a no-op means a command like
        # `git commit -m "stage first; cd into dist"` keeps its `; cd into
        # dist` visible to the directive matcher, which then sees `;` (a real
        # separator, now unmasked) directly followed by `cd into` and wrongly
        # blocks an ordinary commit.
        "double-quoted spans are no longer blanked, so a ; cd inside one is seen",
        HOOK,
        '    stripped = re.sub(r\'"[^"]*"\', \'""\', stripped)',
        '    stripped = stripped',
        TARGETS,
    ),
    (
        # Capability: SINGLE-quote spans get the same treatment as double-quote
        # ones — a separate `re.sub` call, so it is a separate capability that
        # can regress independently of the double-quote one above. Turning it
        # into a no-op means `git commit -m 'stage first; cd into dist'` keeps
        # its `; cd into dist` visible and is wrongly blocked the same way.
        "single-quoted spans are no longer blanked, so a ; cd inside one is seen",
        HOOK,
        '    stripped = re.sub(r"\'[^\']*\'", "\'\'", cmd)',
        '    stripped = cmd',
        TARGETS,
    ),
    (
        # Capability: the two block reasons print DIFFERENT messages, and the
        # shadow message is what tells a blocked caller "the thing you tried is
        # not a real cd, it's an evasion — do not route around a guard this
        # way" rather than the generic "cd persists across calls" explanation.
        # Losing the "redefines `cd`" wording collapses that distinction: the
        # caller (or a human reading stderr) can no longer tell a redefinition
        # was the actual offense, which is exactly the information this
        # message exists to carry.
        "the shadow-block message stops saying the command redefines `cd`",
        HOOK,
        '            "blocked: this command redefines `cd` as a shell function or alias. "',
        '            "blocked: this command changed what the word cd does. "',
        TARGETS,
    ),
]
