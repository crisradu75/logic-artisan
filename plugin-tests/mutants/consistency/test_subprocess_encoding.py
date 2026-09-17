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
guard's module docstring. Mutants 4-9 are constructed probes for decisions the AST
version added — `encoding=` alone as a text-mode trigger, the narrowing in
`_is_spawn`, and the three-root scan. None of the second group is historical, and
saying so matters: a batch claiming history it does not have is the defect
`test_check_labels_agree.py`'s header records going stale twice.

**What this batch does NOT prove.** Every mutant but 6 is killed by seeded-input tests —
`ast.parse` of a snippet — not by the sweep over real files. They show the
checker's DECISIONS are pinned; they say nothing about whether the sweep reaches
any particular file. Mutant 6 is the only one that exercises that half, via the
named anchors in `test_the_scan_reaches_the_places_the_first_version_missed`.

**A REAL GAP, found by this batch, reported rather than fixed at the time, and
NOW CLOSED (issue #246).** `_is_spawn` is a four-way conjunction, and the
cry-wolf corpus pinned only the conjunction as a whole — NEITHER narrowing
condition was pinned on its own. Measured by simulating each candidate against
`test_the_checker_does_not_cry_wolf`'s seven cases as they then stood:

    drop `func.attr in _SPAWNERS`          SURVIVES
    drop `func.value.id in _SPAWN_MODULES` SURVIVES   (run as a real mutant too)
    drop BOTH                              killed
    always True                            killed

The cause is that every negative case in that corpus is rejected by an EARLIER
condition: `open(...)` is an `ast.Name` not an `ast.Attribute`, and
`path.read_text` / `widget.Label` / `parser.add_argument` all fail `attr in
_SPAWNERS`. No case was a spawner NAME on a non-subprocess module, so the module
check never executed.

Three cases now close it, one per condition, each rejected by that condition
ALONE: `asyncio.run(coro, text=True)` (cond 4), `subprocess.list2cmdline(cmd,
text=True)` (cond 2) and `os.path.run(cmd, text=True)` (cond 3, which is a crash
guard rather than a narrowing — without it `func.value.id` raises
AttributeError). Mutant 5 still pins the conjunction as a whole; mutants 7-9
below pin each condition separately, and 7 and 8 are the two that used to
survive.

**Anchors are single-line except mutant 5.** Every file here is CRLF, so a bare
`\\n` in an anchor matches nothing — see `mutate.py`'s docstring. Mutant 5 needs to
remove two lines at once, so it derives the separator from the file's own bytes
rather than spelling it and pinning the batch to one platform.

Run: python3 plugin-tests/mutate.py plugin-tests/mutants/consistency/test_subprocess_encoding.py
"""

from pathlib import Path

DEV = Path(__file__).resolve().parents[2]

GUARD = DEV / "tests" / "consistency" / "test_subprocess_encoding.py"
TARGET = [GUARD]

# Derived, not spelled: `\r\n` outright would work on this checkout and pin the
# batch to Windows. Only mutant 5 spans lines; the rest stay within one.
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
        "crying wolf. Pins the conjunction; see the header for why neither half "
        "is pinned alone",
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

    # ---- 7-9: the conjunction, one condition at a time ----
    #
    # THE GAP IN THE HEADER ABOVE IS NOW CLOSED, and these are the mutants that
    # say so. Three cases were added to `test_the_checker_does_not_cry_wolf`,
    # each rejected by exactly ONE condition, so each condition now decides a
    # case on its own rather than being shadowed by an earlier one.
    (
        # Condition 4. `asyncio.run(coro, text=True)` is an Attribute call whose
        # attr IS a spawner and whose value IS a Name — only the module check
        # rejects it. This mutant SURVIVED before that case existed.
        "_is_spawn stops checking the MODULE, so any object with a .run/.Popen "
        "method is treated as subprocess",
        GUARD,
        "        and func.value.id in _SPAWN_MODULES",
        "        and True",
        TARGET,
    ),
    (
        # Condition 2, the other half of the same conjunction, and the other
        # measured survivor. `subprocess.list2cmdline(cmd, text=True)` is on the
        # spawn module and is not a spawner, so only the callee check rejects it.
        "_is_spawn stops checking the CALLEE, so any subprocess attribute call "
        "is treated as a spawn",
        GUARD,
        "        and func.attr in _SPAWNERS",
        "        and True",
        TARGET,
    ),
    (
        # Condition 3, which is not a narrowing at all but a CRASH guard:
        # `os.path.run(...)` has an Attribute where `func.value.id` expects a
        # Name, so removing this line makes `_is_spawn` raise AttributeError on
        # a shape that occurs in ordinary code.
        "_is_spawn stops requiring the module to be a bare name, so a dotted "
        "callee raises AttributeError instead of being rejected",
        GUARD,
        "        and isinstance(func.value, ast.Name)" + _NL,
        "",
        TARGET,
    ),
]
