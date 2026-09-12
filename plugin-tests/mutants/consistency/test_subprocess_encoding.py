"""Mutation batch for test_subprocess_encoding.py.

The guard claims that no `subprocess.run(..., text=True)` in the three trees this
repo owns can lose its `encoding=`/`errors=` pin without a test going red.

**The checker lives INSIDE the guard file.** `_unpinned_calls`, `_is_spawn` and
`_scanned_files` are defined in the test module, so every mutant here edits the
guard itself and the killing assertion comes from that same file's seeded-input
tests. That is the shape the guard was built for — its own docstring records that
the AST version replaced a line-based one "defeated three separate ways, each
proven by a surviving mutation".

**Provenance, stated because it decides what a kill means here.** Mutants 1-3
re-break defects the line-based version actually shipped, as recorded in the
guard's module docstring. Mutants 4-6 are constructed probes for decisions the AST
version added — `encoding=` alone as a text-mode trigger, the narrowing in
`_is_spawn`, and the three-root scan. None of the second group is historical, and
saying so matters: a batch claiming history it does not have is the defect
`test_check_labels_agree.py`'s header records going stale twice.

**What this batch does NOT prove.** Mutants 1-5 are killed by seeded-input tests —
`ast.parse` of a snippet — not by the sweep over real files. They show the
checker's DECISIONS are pinned; they say nothing about whether the sweep reaches
any particular file. Mutant 6 is the only one that exercises that half, via the
named anchors in `test_the_scan_reaches_the_places_the_first_version_missed`.

**A REAL GAP, found by this batch, reported rather than fixed here — and since
CLOSED by issue #246.** `_is_spawn` is a four-way conjunction, and the cry-wolf
corpus pinned only the conjunction as a whole. Measured by simulating each
candidate against `test_the_checker_does_not_cry_wolf`'s then-seven cases:

    drop `func.attr in _SPAWNERS`          SURVIVES
    drop `func.value.id in _SPAWN_MODULES` SURVIVES   (run as a real mutant too)
    drop BOTH                              killed
    always True                            killed

The cause was that every negative case in that corpus is rejected by an EARLIER
condition: `open(...)` is an `ast.Name` not an `ast.Attribute`, and
`path.read_text` / `widget.Label` / `parser.add_argument` all fail `attr in
_SPAWNERS`. No case was a spawner NAME on a non-subprocess module, so the module
check never executed.

Two cry-wolf cases closed it, one per conjunct — `asyncio.run(coro, text=True)`
for the module half, `subprocess.CompletedProcess(args, 0, text=True)` for the
callee half. Mutants 7-8 re-break each and both die. **The sequence is the point
and is why this paragraph keeps its original shape:** a batch that reports an
unkillable mutant as a finding, rather than quietly dropping it, is what turned
this from a survivor nobody would action into a fix.

**Anchors are single-line except mutants 5, 7 and 8.** Every file here is CRLF, so
a bare `\\n` in an anchor matches nothing — see `mutate.py`'s docstring. Those
three remove or span two lines at once, so they derive the separator from the
file's own bytes rather than spelling it and pinning the batch to one platform.

Run: python3 plugin-tests/mutate.py plugin-tests/mutants/consistency/test_subprocess_encoding.py
"""

from pathlib import Path

DEV = Path(__file__).resolve().parents[2]

GUARD = DEV / "tests" / "consistency" / "test_subprocess_encoding.py"
TARGET = [GUARD]

# Derived, not spelled: `\r\n` outright would work on this checkout and pin the
# batch to Windows. Mutants 5, 7 and 8 span lines; the rest stay within one.
_NL = "\r\n" if b"\r\n" in GUARD.read_bytes() else "\n"

MUTANTS = [
    # ---- 1-3: the three defeats the line-based version actually shipped ----
    (
        "the errors= half of the pin stops being checked, so a STRICT decode — "
        "which still raises in the reader thread — reads as pinned",
        GUARD,
        '        elif "errors" not in kwargs:',
        "        elif False:",
        TARGET,
    ),
    (
        "universal_newlines drops out of the text-mode set, so CPython's exact "
        "alias for text=True becomes a one-token way to silence the guard",
        GUARD,
        'for name in ("text", "universal_newlines")',
        'for name in ("text",)',
        TARGET,
    ),
    (
        "the no-encoding= report is dropped, leaving only the errors= branch: the "
        "original defect, a bare text=True, walks straight through",
        GUARD,
        '            problems.append((node.lineno, "no encoding="))',
        "            pass",
        TARGET,
    ),

    # ---- 4-6: decisions the AST rewrite added ----
    (
        "encoding= alone stops counting as text mode, so subprocess.run(cmd, "
        "capture_output=True, encoding='cp1252') — a strict decode — reads as safe",
        GUARD,
        'text_mode = "encoding" in kwargs or any(',
        "text_mode = any(",
        TARGET,
    ),
    (
        "_is_spawn stops narrowing at all — any attribute call on a bare name is "
        "a spawner, so the guard flags path.read_text(encoding='utf-8') and starts "
        "crying wolf. Pins the conjunction as a whole; mutants 7-8 pin each half, "
        "which nothing did until issue #246",
        GUARD,
        "        and func.attr in _SPAWNERS" + _NL
        + "        and isinstance(func.value, ast.Name)" + _NL
        + "        and func.value.id in _SPAWN_MODULES",
        "        and isinstance(func.value, ast.Name)",
        TARGET,
    ),
    (
        "the sweep collapses to the plugin root, dropping the dev tree and the "
        "repo-local skills tree — the 84-to-27 under-scan the guard names",
        GUARD,
        "        if not root.is_dir():",
        "        if not root.is_dir() or root != _PLUGIN_ROOT:",
        TARGET,
    ),

    # ---- 7-8: ISSUE #246 — each conjunct of _is_spawn, separately ----
    #
    # Mutant 5 above pins the conjunction AS A WHOLE and its comment used to end
    # "see the header for why neither half is pinned alone". Neither was: every
    # case in the cry-wolf corpus was rejected by the first condition that looked
    # at it, so the second never executed and dropping either half survived the
    # whole suite. Measured before the fix, by patching `_is_spawn` and running
    # the corpus:
    #
    #     drop `func.attr in _SPAWNERS`           SURVIVES
    #     drop `func.value.id in _SPAWN_MODULES`  SURVIVES
    #     drop BOTH                               killed  (mutant 5)
    #
    # Two corpus cases fixed that, one per conjunct, and these re-break each.
    (
        "the module half of _is_spawn stops narrowing, so any `<name>.run(...)` "
        "is a spawner and asyncio.run(coro, text=True) gets flagged — the guard "
        "cries wolf on an ordinary call",
        GUARD,
        "        and isinstance(func.value, ast.Name)" + _NL
        + "        and func.value.id in _SPAWN_MODULES",
        "        and isinstance(func.value, ast.Name)",
        TARGET,
    ),
    (
        "the callee half of _is_spawn stops narrowing, so any attribute on a "
        "subprocess module is a spawner and subprocess.CompletedProcess(args, 0, "
        "text=True) — what a test fake constructs — gets flagged",
        GUARD,
        "        and func.attr in _SPAWNERS" + _NL,
        "",
        TARGET,
    ),
]
