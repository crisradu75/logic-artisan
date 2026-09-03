"""Mutant batch for `tests/hooks/test_ask_destructive_git.py` -- the ask-severity
guard over destructive git operations, in `ask-destructive-git.py`.

Run:
    python3 plugin-tests/mutate.py plugin-tests/mutants/hooks/test_ask_destructive_git.py

WHY THE FIRST MUTANT IS THE ONE IT IS. `test_guards_have_mutant_batches.py`'s
`_PENDING_ADOPTION` comment records that the batch proving `git branch -D`'s
bare-flag detection was run from outside this repo and committed nowhere, so
it "now exists nowhere". `_force_deletes_a_branch`'s fast path --
`if "D" in clusters: return True` -- is that detection: `-D` is documented
shorthand for `--delete --force` (`git-branch(1)`), and it is also the single
most common way anyone actually types a force-delete. MUTANTS[0] below
re-breaks exactly that path.

WHY THE MUTATIONS TARGET THE HOOK, NOT THE GUARD. Mutating the test file's own
assertions would prove the guard's prose reacts to a change in its own prose --
circular. Every mutant here edits `ask-destructive-git.py`, the file the guard
is actually meant to pin.

ANCHORS ARE LOCATED, NOT HAND-COPIED. This hook's source is dense with regex
literals (`\\s`, `\\\\`, character classes), and retyping one by hand is exactly
the kind of anchor mistake `mutate.py`'s own preflight exists to catch -- a typo
that quietly stops matching would disable the mutant it belongs to. `_line()`
finds the one line in the hook containing a short, backslash-free needle;
`old` is then built by slicing that line at a second backslash-free marker, so
nothing here is transcribed from the regex by hand and each mutant is
verifiable by reading the marker text alone.

Paths resolve from this file's own location, never an absolute developer path,
which would leak a machine path into synced core.
"""

from pathlib import Path

DEV = Path(__file__).resolve().parents[2]          # <repo>/plugin-tests
PLUGIN = DEV.parent / ".claude" / "plugins" / "cla"
HOOK = PLUGIN / "hooks" / "ask-destructive-git.py"
GUARD = DEV / "tests" / "hooks" / "test_ask_destructive_git.py"
TARGETS = [GUARD]

_RAW = HOOK.read_bytes()
_NL = "\r\n" if b"\r\n" in _RAW else "\n"
_TEXT = _RAW.decode("utf-8")
_LINES = _TEXT.split(_NL)


def _line(needle: str) -> str:
    """The one line in the hook source containing `needle`.

    Asserted unique HERE, at batch-load time, so a future edit that duplicates
    the needle fails loudly on import rather than silently building a mutant
    against the wrong line.
    """
    hits = [ln for ln in _LINES if needle in ln]
    assert len(hits) == 1, (needle, hits)
    return hits[0]


def _cut(line: str, marker: str) -> int:
    """`marker`'s start index in `line`, asserted to appear exactly once."""
    assert line.count(marker) == 1, (marker, line)
    return line.index(marker)


MUTANTS = []

# --- 1. `git branch -D` bare-flag shortcut ----------------------------------
# THE mutant `_PENDING_ADOPTION` says was lost. Cutting only this fast path
# still leaves every DECOMPOSED spelling (-d -f, -df, --delete --force, ...)
# caught by the deleting/forcing fallback beneath it -- which is exactly why
# this regression is easy to miss in review: eight of the nine positive rows
# in `test_force_branch_delete_shapes_prompt` keep passing, and only the
# first, most common row -- bare `-D` -- goes silent.
_l1 = _line('if "D" in clusters:')
MUTANTS.append((
    "git branch -D bare-flag shortcut stops being recognised as a force-delete "
    "(the detection issue #123 added, and the batch _PENDING_ADOPTION records "
    "as lost)",
    HOOK, _l1, _l1.replace('"D"', '"Z"'), TARGETS,
))

# --- 2. Force-push via a BUNDLED short-flag cluster -------------------------
# `_FORCE_FLAG`'s regex is the line after its `re.compile(` call. The long
# `--force" + _END` alternative is left untouched; only the short-cluster arm
# (`-f`, `-uf`, `-fu` -- how a hand-typed push most often looks) is cut.
_def2 = _line('_FORCE_FLAG = re.compile(')
_l2 = _LINES[_LINES.index(_def2) + 1]
# The marker text -- `r"|-[A-Za-z]*f[A-Za-z]*(?:[...]|$))"` -- recurs verbatim
# in `_FORCE_DISCARD` and `_CLEAN_FORCE` further down the file, so it is not by
# itself a safe file-wide anchor (`old` must be unique across the WHOLE file,
# per `mutate.py`'s preflight). The whole LINE is unique, so that is `old`; the
# marker is used only to locate where, WITHIN that already-unique line, to cut
# -- right after `+ _END + `, so `_END` (the boundary shared with `--force`)
# is left untouched and only the short-cluster alternative is removed, closing
# the group with a bare `)` in its place.
_m2 = 'r"|-[A-Za-z]*f[A-Za-z]*(?:['
_i2 = _cut(_l2, _m2)
MUTANTS.append((
    "a bundled short force-push flag (-f / -uf / -fu) stops being recognised; "
    "only the spelled-out --force survives",
    HOOK, _l2, _l2[:_i2] + 'r")"', TARGETS,
))

# --- 3. `git reset --hard` --------------------------------------------------
# One extra literal dash in `_HARD_FLAG` means the command text (which has
# exactly two) can never satisfy the pattern again -- the whole rule this
# hook's docstring names FIRST goes silent.
_l3 = _line('_HARD_FLAG = re.compile(')
_i3 = _cut(_l3, '--"')
MUTANTS.append((
    "git reset --hard stops being recognised at all",
    HOOK, _l3, _l3[:_i3] + '---"' + _l3[_i3 + len('--"'):], TARGETS,
))

# --- 4. Working-tree discard (`git checkout <path>` / `git restore <path>`) #
# `_CHECKOUT`'s own command-name literal is corrupted so the regex can never
# match real `git checkout` text again. This is the rule issue #184 added --
# a plain `git checkout <file>` mid-implementation restoring from the index
# and erasing uncommitted work with no reflog entry.
_l4 = _line('_CHECKOUT = re.compile(')
_i4 = _cut(_l4, 'checkout')
MUTANTS.append((
    "git checkout stops being recognised, so a discard of uncommitted work "
    "on a dirty tracked path goes silent",
    HOOK, _l4, _l4[:_i4] + 'checkoutX' + _l4[_i4 + len('checkout'):], TARGETS,
))

# --- 5. `gh pr merge` -------------------------------------------------------
# The literal "pr" the subcommand pair matches on is corrupted, so no spelling
# of `gh pr merge` can match. Authorization is the one thing this hook cannot
# read, so losing this rule silently removes the only check standing between
# an unattended run and a merge nobody asked for.
_l5 = _line(')*?pr" + _SEP + r"merge(?![')
_i5 = _cut(_l5, ')*?pr"')
MUTANTS.append((
    "gh pr merge stops being recognised under any spelling",
    HOOK, _l5, _l5[:_i5] + ')*?prx"' + _l5[_i5 + len(')*?pr"'):], TARGETS,
))

# --- 6. Case-folding / executable-suffix handling ---------------------------
# `_BRANCH`'s command match is pinned to the shared `_GIT_CMD` pattern, which
# is what lets `git.exe`, `GIT`, and `Git.Exe` all resolve to the same command.
# Swapping it for a bare case-sensitive, no-suffix literal is the exact defect
# `test_branch_delete_fires_on_every_executable_spelling`'s docstring says
# shipped once: the constant was pinned as a regex, nothing pinned the
# COMPOSITION in this guard's own file.
_l6 = _line('_BRANCH = re.compile(_GIT_CMD + _SEP + _G + r"branch\\b" + _TAIL)')
MUTANTS.append((
    "branch-delete stops recognising git.exe / GIT / Git.Exe -- only a bare "
    "lowercase 'git' still matches",
    HOOK, _l6, _l6.replace('_GIT_CMD', 'r"git"', 1), TARGETS,
))

# --- 7. Escape hatch: ALLOW_DESTRUCTIVE_GIT ---------------------------------
# The broad hatch's own gate is pinned to the wrong value, so exporting
# ALLOW_DESTRUCTIVE_GIT=1 (as every skill that documents it actually does) no
# longer takes the suppressing branch at all -- the override silently stops
# working while every guard it exists to bypass stays armed.
_l7 = _line('if os.environ.get("ALLOW_DESTRUCTIVE_GIT") == "1":')
MUTANTS.append((
    "the ALLOW_DESTRUCTIVE_GIT=1 escape hatch stops suppressing the prompt",
    HOOK, _l7, _l7.replace('== "1"', '== "2"'), TARGETS,
))

# --- 8. Negative case: the guarded push forms must stay silent -------------
# `--force-with-lease` / `--force-if-includes` are excluded ONLY because
# `_END` requires a boundary after `--force` -- both are followed by `-`,
# which `_END` rejects. Dropping `_END` from that alternative reopens exactly
# this false positive: the guarded, SAFER form starts prompting, which is
# what the module docstring says would make the prompt routine and stop being
# read. This is the boundary `test_benign_shapes_do_not_prompt` and
# `test_an_alternative_spelling_of_a_safe_command_still_stays_silent` pin.
_m8 = '--force" + _END + r"|'
_i8 = _cut(_l2, _m8)
MUTANTS.append((
    "--force-with-lease and --force-if-includes start prompting, punishing "
    "the safer, guarded push form",
    HOOK, _l2[_i8:_i8 + len(_m8)], '--force" + r"|', TARGETS,
))
