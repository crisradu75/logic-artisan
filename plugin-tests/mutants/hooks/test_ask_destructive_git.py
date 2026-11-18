"""Mutant batch for `tests/hooks/test_ask_destructive_git.py` -- the ask-severity
guard over destructive git operations, in `ask-destructive-git.py`.

Run:
    python3 plugin-tests/mutate.py plugin-tests/mutants/hooks/test_ask_destructive_git.py

WHY THE FIRST MUTANT IS THE ONE IT IS. The batch that first proved
`git branch -D`'s bare-flag detection was run from outside this repo and
committed nowhere. `_force_deletes_a_branch`'s fast path --
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
# this regression is easy to miss in review: the decomposed rows keep passing
# and only the bare-`-D` spellings go silent, so the guard still looks alive.
# No row count is given here on purpose. An earlier version of this comment said
# "eight of the nine positive rows", which described a file state that had
# already moved on -- the parametrize list has grown since. A count copied into
# a comment beside the thing it counts is the staleness this repo keeps paying
# for; read `test_force_branch_delete_shapes_prompt` for the current rows.
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
_l4 = _line('_CHECKOUT = GitInvocation(')
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

# --- 6. `git branch` ---------------------------------------------------------
# Was: `_BRANCH` composed with `_GIT_CMD` swapped for a bare `git`. Since #526
# `GIT_CMD` is composed once, inside `_dispatch_lib.GitInvocation`, so that
# mutant lives in `test_dispatch_lib.py`'s batch. Here the subcommand word is
# corrupted, so no force-delete spelling matches.
_l6 = _line('_BRANCH = GitInvocation(')
_i6 = _cut(_l6, 'branch')
MUTANTS.append((
    "git branch stops being recognised, so a force-delete goes silent",
    HOOK, _l6, _l6[:_i6] + 'branchX' + _l6[_i6 + len('branch'):], TARGETS,
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

# --- 9. `_holds_work` stops failing CLOSED when the probe cannot run ---------
# The highest-value capability this batch originally missed, named by review.
#
# The whole working-tree-discard layer -- `git checkout <path>`, `git restore`,
# `git switch -f`, `git clean -fdx`, the commands this hook sees most often --
# is a CONDITIONAL probe rather than shape-matching: it asks git what would be
# lost, and only prompts if something would. `_holds_work`'s `if lines is None:
# return True` is the arm that decides what to do when the probe itself could
# not run, and the module docstring calls the alternative the worst outcome this
# layer has -- a guard that allows because it failed to look is indistinguishable
# from one that looked and approved.
#
# Mutating the CALL rather than the `return True`, because `return True` occurs
# four times in this file and `_line` would refuse it. `or False` turns a None
# into the "probe ran, found nothing" value, so the single-path branch below
# returns False and the prompt never fires -- fail-open, from one token.
#
# Killed by `test_a_wedged_git_prompts_rather_than_going_silent`, which stubs
# `_run_git` to return None and asserts a payload is still produced.
_l9 = _line("lines = _status_lines(cwd, paths, ignored)")
MUTANTS.append((
    "a wedged git makes the discard layer fail OPEN: the probe returning None "
    "is read as 'nothing would be lost' instead of 'ask'",
    HOOK, _l9, _l9 + " or False", TARGETS,
))

# --- 10-13. The stash check's own handler and its multi-directory reason -----
# Issue #438. The stash block once shared the discard check's `try`, so a
# stash-side exception skipped the discard and clean checks; and a deliberate
# multi-directory skip reported "COULD NOT BE RUN". Killed by
# `test_a_raising_stash_check_still_runs_the_discard_and_clean_checks` and
# `test_stashes_in_two_directories_ask_without_probing_each`.
_l10 = _line("if STASH_UNCHECKED_REASON not in found:")
MUTANTS.append((
    "a raising stash check no longer asks: its handler drops the unchecked reason",
    HOOK, _l10, _l10.replace("if STASH_UNCHECKED_REASON not in found:", "if False:"), TARGETS,
))

# The structural regression itself: a stash failure ends the function before the
# discard and clean checks run. Inserted as a one-line `if` ahead of the comment
# that opens the discard check's `try`, so the file still parses.
_l11 = _line("# Wrapped for the same reason as the stash check")
MUTANTS.append((
    "a stash-side exception skips the discard and clean checks again",
    HOOK, _l11,
    "    if STASH_UNCHECKED_REASON in found: return found" + _NL + _l11, TARGETS,
))

_l12 = _line("if len(stash_dirs) > 1:")
MUTANTS.append((
    "stashes in two directories are probed (one directory only) instead of asked about",
    HOOK, _l12, _l12.replace("> 1", "> 99"), TARGETS,
))

_l13 = _line("found.append(STASH_MULTI_DIR_REASON)")
MUTANTS.append((
    "the deliberate multi-directory skip reports 'COULD NOT BE RUN' again",
    HOOK, _l13, _l13.replace("STASH_MULTI_DIR_REASON", "STASH_UNCHECKED_REASON"), TARGETS,
))

# --- 14-20. The other `GitInvocation` matchers (#526) --------------------------
# Each of these lines changed from a composed regex to `GitInvocation`, so each
# gets its subcommand word corrupted. `_STASH` also loses the options group,
# which shifts the tail to group 1 and leaves `_stash_dirs` reading the wrong
# text.
for _name, _word, _what in (
    ("_PUSH", "push", "a force-push and a push that skips the pre-push guard go silent"),
    ("_RESET", "reset", "git reset --hard goes silent"),
    ("_SWITCH", "switch", "a forced git switch goes silent"),
    ("_RESTORE", "restore", "git restore of a dirty path goes silent"),
    ("_CLEAN", "clean", "git clean -f over untracked work goes silent"),
    ("_STASH", "stash", "a saving git stash during a merge goes silent"),
):
    _l = _line(_name + " = GitInvocation(")
    _i = _cut(_l, _word + "\\b")
    MUTANTS.append((
        f"{_name}'s subcommand word is corrupted: {_what}",
        HOOK, _l, _l[:_i] + _word + "X" + _l[_i + len(_word):], TARGETS,
    ))

_l20 = _line("_STASH = GitInvocation(")
MUTANTS.append((
    "_STASH stops capturing the global options, so the tail is read as the "
    "options and the stash check reads the wrong group",
    HOOK, _l20, _l20.replace("capture_opts=True", "capture_opts=False"), TARGETS,
))

# --- 21+. Rebase, branch reset and merging switch ---------------------------
# One mutant per changed line that carries logic. Left out, and why: the
# continuation lines of the three reason strings (the tests match a phrase from
# one line of each, so editing another line changes nothing a test can see),
# `def` lines, closing brackets, and `asked: dict = {}`, which has no wrong
# value that still runs. A line that occurs twice in the hook is anchored as a
# block starting at a unique neighbour (`_mut`'s `n`/`at`).
LIB = PLUGIN / "hooks" / "_dispatch_lib.py"
_LIB_TEXT = LIB.read_bytes().decode("utf-8")


def _mut(what: str, needle: str, old: str, new: str, n: int = 1, at: int = 0) -> None:
    """Replace `old` with `new` in line `at` of the `n`-line block that starts
    at the one line containing `needle`."""
    first = _line(needle)
    i = _LINES.index(first)
    block = _LINES[i:i + n]
    assert block[at].count(old) == 1, (old, block[at])
    mutated = list(block)
    mutated[at] = block[at].replace(old, new)
    MUTANTS.append((what, HOOK, _NL.join(block), _NL.join(mutated), TARGETS))


for _what, _args in (
    # imports and the shared directory helper
    ("the history checks lose `time`, so every command raises in _reasons",
     ("import time", "import time", "import time as _unused_time")),
    ("each history probe may take 12s instead of at most 3s",
     ("import GIT_TIMEOUT_SECONDS", "from _dispatch_lib import GIT_TIMEOUT_SECONDS", "GIT_TIMEOUT_SECONDS = 12.0")),
    ("the history probe budget becomes zero, so none of them ever runs",
     ("import HOOK_WORST_CASE_SECONDS", "from _dispatch_lib import HOOK_WORST_CASE_SECONDS",
      'HOOK_WORST_CASE_SECONDS = {"ask-destructive-git.py": 0.0}')),
    ("a stash probes the process cwd instead of the command's directory",
     ("d = _invocation_dir(", "scanned, cwd)", 'scanned, ".")')),
    ("GIT_DIR= no longer marks the repository as unnameable",
     ("_GIT_ENV_REPO.search(scanned):", "_GIT_ENV_REPO.search(scanned)", "False")),
    ("an unnameable repository resolves to the cwd instead of None",
     ("_GIT_ENV_REPO.search(scanned):", "return None", "return cwd", 2, 1)),
    ("the directory starts at the process cwd instead of the payload's",
     ("    d = cwd", "d = cwd", 'd = "."')),
    ("every -C is ignored",
     ("for c in _DASH_C.finditer(opts):", "finditer(opts)", 'finditer("")')),
    ("a relative -C stops resolving against the directory before it",
     ("os.path.normpath(os.path.join(d,", "os.path.join(d, ", "os.path.join(")),
    ("the resolved directory is dropped for the cwd",
     ("os.path.normpath(os.path.join(d,", "return d", "return cwd", 2, 1)),
    # constants
    ("the history probe budget is zero",
     ("_PROBE_BUDGET_SECONDS = HOOK_WORST_CASE_SECONDS", 'HOOK_WORST_CASE_SECONDS["ask-destructive-git.py"]', "0.0")),
    ("git rebase is never matched",
     ("_REBASE = GitInvocation(", "rebase", "rebaseX")),
    ("git switch is never matched by the history checks",
     ("_BRANCH_CHANGE = GitInvocation(", "(checkout|switch)", "(checkout)")),
    ("no rebase action is recognised, so --continue is probed",
     ("_REBASE_ACTION = re.compile(", '"(?:^|', '"X(?:^|')),
    ("--con no longer reads as --continue",
     ('_abbrev("continue", 3)', '_abbrev("continue", 3)', '"continue"')),
    ("--edit-todo no longer reads as an action",
     ('_abbrev("edit-todo", 2)', '_abbrev("edit-todo", 2)', '"xedit-todo"')),
    ("the rebase action pattern loses its terminator",
     ('_abbrev("edit-todo", 2)', "_END", '"X"', 2, 1)),
    ("--ro no longer reads as --root",
     ("_REBASE_ROOT = re.compile(", '_abbrev("root", 2)', '_abbrev("root", 4)')),
    ("no long rebase option takes a value",
     ("_REBASE_VALUE_LONG = re.compile(", '"--(?:"', '"---(?:"')),
    ("--ont no longer reads as --onto, so its value is an operand",
     ('_abbrev("onto", 1)', '_abbrev("onto", 1)', '"onto"')),
    ("--whitespace stops taking a value",
     ('_abbrev("whitespace", 1)', '_abbrev("whitespace", 1)', '"xwhitespace"')),
    ("the rebase value-option pattern never matches",
     ('_abbrev("whitespace", 1)', '")")', '"X)")', 2, 1)),
    ("-x stops taking a value",
     ("_REBASE_VALUE_SHORT = ", '"CxsX"', '"CsX"')),
    ("-S and -r stop owning the rest of their cluster",
     ("_REBASE_OPTIONAL_SHORT = ", '"Sr"', '""')),
    ("--force- no longer reads as --force-create",
     ("_FORCE_CREATE_LONG = re.compile(", '_abbrev("force-create", 6)', '_abbrev("force-create", 7)')),
    ("--conflict stops taking a value in a branch reset",
     ("_BRANCH_VALUE_LONG = frozenset(", "frozenset({", "frozenset() and ({")),
    ("--merge and --conflict are never recognised",
     ("_MERGE_SWITCH_LONG = re.compile(", "re.compile(", 're.compile("(?!)" + ')),
    ("--c no longer reads as --conflict",
     ('_abbrev("conflict", 1)', '_abbrev("conflict", 1)', '"conflict"')),
    ("no redirection is recognised, so `2>/dev/null` is an operand",
     ("_REDIRECT = re.compile(", 'r"', 'r"(?!)')),
    # the three reasons
    ("the rebase reason loses the phrase the tests match",
     ("rewrites commits already on a remote-tracking", "rewrites commits already", "rewrites commits")),
    ("the branch-reset reason loses the phrase the tests match",
     ("the reset orphans them", "orphans them", "drops them")),
    ("the merging-switch reason loses the phrase the tests match",
     ("a merging branch change (", "merging branch change", "merge branch change")),
    # _words
    ("_words starts with a stray word",
     ("    words: list[tuple[str, str]] = []", "= []", '= [("x", "x")]')),
    ("_words drops the first word as a redirection target",
     ("    words: list[tuple[str, str]] = []", "target = False", "target = True", 2, 1)),
    ("_words reads nothing",
     ("    words: list[tuple[str, str]] = []", "scanned_tail):", "scanned_tail[:0]):", 3, 2)),
    ("a continuation abutting a flag stays on it",
     ("flag = scanned_tail[m.start():m.end()].rstrip(", ".rstrip(", ".lstrip(")),
    ("a closing parenthesis stays on an operand",
     ("real = raw_tail[m.start():m.end()]", ".rstrip(", ".lstrip(")),
    ("a bare continuation becomes an empty operand",
     ("        if not flag:", "if not flag:", "if not flag and False:")),
    ("everything after a redirection target is dropped",
     ("        if target:", "target = False", "target = True", 2, 1)),
    ("a comment's words become operands",
     ('elif flag.startswith("#"):', '"#"', '"#X"')),
    ("a redirection is never recognised",
     ("(redirect := _REDIRECT.match(flag))", "match(flag)", 'match("")')),
    ("a redirection's separate target becomes an operand",
     ("target = redirect.end() == len(flag)", "redirect.end() == len(flag)", "False")),
    ("an operand's real text is replaced by its scanned text",
     ("words.append((flag, real))", "(flag, real)", "(flag, flag)")),
    ("_words loses its last word",
     ("    return words", "return words", "return words[:-1]")),
    # _takes_next_word
    ("a short cluster's first letter is skipped",
     ("for i, ch in enumerate(letters):", "enumerate(letters)", "enumerate(letters[1:])")),
    ("an optional-value letter takes the next word",
     ("if ch in _REBASE_OPTIONAL_SHORT:", "return False", "return True", 2, 1)),
    ("an attached value still takes the next word",
     ("return i == len(letters) - 1", "i == len(letters) - 1", "True")),
    ("a valueless cluster takes the next word",
     ("return i == len(letters) - 1", "return False", "return True", 2, 1)),
    # _rebase_range
    ("an action on a rebase under way is probed",
     ("if _REBASE_ACTION.search(scanned_tail):", "_REBASE_ACTION.search(scanned_tail)", "None")),
    ("the rebase operands start with a stray `main`",
     ("if _REBASE_ACTION.search(scanned_tail):", "= []", '= ["main"]', 3, 2)),
    ("--root is assumed",
     ("root = skip = False", "root = skip = False", "root = skip = True")),
    ("the rebase tail is read raw, so a quoted value splits",
     ("for flag, real in _words(scanned_tail, raw_tail):", "_words(scanned_tail,", "_words(raw_tail,")),
    ("a skipped value also skips every word after it",
     ("        if skip:", "skip = False", "skip = True", 2, 1)),
    ("a long option is read as a short cluster",
     ('elif flag.startswith("--"):', '"--"', '"---"')),
    ("--root is never recognised",
     ("root = root or _REBASE_ROOT", "root = root or", "root = root and")),
    ("every long option but a value option takes the next word",
     ("skip = _REBASE_VALUE_LONG.fullmatch(flag) is not None", "is not None", "is None")),
    ("`-` is read as an empty short cluster",
     ('elif flag.startswith("-") and flag != "-":', ' and flag != "-"', "")),
    ("a short cluster's first letter is dropped",
     ("skip = _takes_next_word(flag[1:])", "flag[1:]", "flag[2:]")),
    ("`-` is passed on instead of `@{-1}`",
     ('operands.append("@{-1}" if real == "-" else real)', '"@{-1}" if real == "-" else real', "real")),
    ("--root is ignored",
     ("    if root:", "if root:", "if False:")),
    ("--root's branch operand is ignored",
     ('return (operands[0] if operands else "HEAD"), None', "operands[0] if operands", '"HEAD" if operands')),
    ("a rebase's branch operand is ignored",
     ('operands[1] if len(operands) > 1 else "HEAD",', "operands[1] if len(operands) > 1", '"HEAD" if len(operands) > 1')),
    ("a bare rebase counts from main instead of its upstream",
     ('operands[0] if operands else "@{upstream}",', '"@{upstream}"', '"main"')),
    # _rewrites_published
    ("the upstream is not excluded from the range",
     ('span = [branch] if upstream is None else [branch, "^" + upstream]', '[branch, "^" + upstream]', "[branch]")),
    ("the first count also leaves out the remotes",
     ('every = git(directory, ["rev-list", "--count", *span, "--"])', '*span, "--"]', '*span, "--not", "--remotes", "--"]')),
    ("a successful first count is read as a refusal",
     ("if every is None or every.returncode != 0:", "!= 0", "== 0")),
    ("the second count keeps the remotes",
     ('"--not", "--remotes", "--"])', '"--remotes", ', "")),
    ("a successful second count is read as a refusal",
     ("if local is None or local.returncode != 0:", "!= 0", "== 0")),
    ("equal counts read as published",
     ("return int(every.stdout) > int(local.stdout)", " > ", " >= ")),
    # _reset_target
    ("the create letter is taken for the reset letter",
     ("    reset = values[1]", "values[1]", "values[0]")),
    ("a reset's first word is dropped",
     ("    words = _words(scanned_tail, raw_tail)", "raw_tail)", "raw_tail)[1:]")),
    ("every branch change resets `uniq`",
     ("    name: str | None = None", "= None", '= "uniq"')),
    ("the start point defaults to `uniq`",
     ("    name: str | None = None", "= []", '= ["uniq"]', 2, 1)),
    ("the reset parse skips its first word",
     ("    i = 0", "i = 0", "i = 1")),
    ("the reset parse skips its last word",
     ("    while i < len(words):", "len(words)", "len(words) - 1")),
    ("the reset parse rereads the first word",
     ("        flag, real = words[i]", "words[i]", "words[0]")),
    ("the next word is taken to be the current one",
     ('nxt = words[i + 1][1] if i + 1 < len(words) else ""', "words[i + 1][1]", "words[i][1]")),
    ("--force-create is read as a short cluster",
     ('        if flag.startswith("--"):', '"--"', '"---"')),
    ("--force-create=name loses its attached name",
     ('_, eq, value = real.partition("=")', 'partition("=")', 'partition("#")')),
    ("--force-create=name is not recognised",
     ('if _FORCE_CREATE_LONG.fullmatch(flag.partition("=")[0]):', 'flag.partition("=")[0]', "flag")),
    ("the attached and separate --force-create names are swapped",
     ("name, i = (value, i) if eq else (nxt, i + 1)", "if eq", "if not eq")),
    ("a long value option's value becomes the start point",
     ("elif flag in _BRANCH_VALUE_LONG:", "i += 1", "i += 0", 2, 1)),
    ("a short cluster is read as an operand",
     ('        elif flag.startswith("-"):', '"-"', '"+"')),
    ("a short cluster's first letter is skipped in a reset",
     ("for j, ch in enumerate(flag[1:]):", "flag[1:]", "flag[2:]")),
    ("no letter takes a value in a reset",
     ("                if ch in values:", "values", '"xX"')),
    ("an attached name keeps its letter",
     ("value = real[j + 2:]", "j + 2", "j + 1")),
    ("a separate name is also read as the start point",
     ("value, i = nxt, i + 1", "i + 1", "i")),
    ("the create letter resets and the reset letter does not",
     ("if ch == reset:", "==", "!=")),
    ("a cluster keeps reading after its value letter",
     ("                        name = value", "break", "pass", 2, 1)),
    ("the start point is always HEAD",
     ("                        name = value", "append(real)", 'append("HEAD")', 5, 3)),
    ("the reset parse skips a word after each operand",
     ("                        name = value", "i += 1", "i += 2", 5, 4)),
    ("a command with no reset resets `uniq`",
     ("    if not name:", "return None", 'return "uniq", "HEAD"', 2, 1)),
    ("the start point defaults to `uniq` at the end",
     ('return name, (operands[0] if operands else "HEAD")', '"HEAD"', '"uniq"')),
    # _orphans_commits
    ("the other refs are counted instead of excluded",
     ('"rev-list", "--count", "refs/heads/" + name, "--not",', ' "--not",', "")),
    ("the start point is not excluded",
     ('"--exclude=" + name,', "start, ", "")),
    ("an existing branch always orphans something",
     ("return out is not None and out.returncode == 0 and int(out.stdout) > 0", "> 0", ">= 0")),
    # _merges_on_switch
    ("the checkout -m -- <path> form reads as a merging switch",
     ('if "--" in scanned_tail.split():', '"--"', '"---"')),
    ("--merge is never recognised",
     ("if _MERGE_SWITCH_LONG.search(scanned_tail):", "search(scanned_tail)", 'search("")')),
    ("no short cluster is searched for -m",
     ("    for cluster in _SHORT_CLUSTER.findall(scanned_tail):", "findall(scanned_tail)", 'findall("")')),
    ("a cluster's first letter is skipped for -m",
     ("        for ch in cluster:", "in cluster", "in cluster[1:]")),
    ("-m is not the merge letter",
     ('            if ch == "m":', '"m"', '"M"')),
    ("a value letter no longer ends the -m search",
     ('            if ch == "m":', "break", "pass", 4, 3)),
    # _holds_staged_work
    ("the status probe drops --porcelain",
     ('["status", "--porcelain", "--untracked-files=no"]', '"--porcelain", ', "")),
    ("a successful status probe is read as a refusal",
     ("if out is None or out.returncode != 0:", "!= 0", "== 0")),
    ("an unstaged change counts as staged",
     ("return any(line[:1].strip() for line", "line[:1].strip()", "line[:1]")),
    # _history_reasons
    ("every probe in a directory shares one answer",
     ("key = (directory, tuple(args))", "(directory, tuple(args))", "directory")),
    ("an identical probe runs again",
     ("if key not in asked:", "key not in asked", "True")),
    ("the deadline is in the past",
     ("left = started + _PROBE_BUDGET_SECONDS - time.monotonic()", "started + ", "started - ")),
    ("each history probe gets the full 3s, however late",
     ("timeout=min(GIT_TIMEOUT_SECONDS, left)", "min(GIT_TIMEOUT_SECONDS, left)", "GIT_TIMEOUT_SECONDS")),
    ("a probe starts after the budget is spent",
     ("if left > 0 else None", "left > 0", "left > -1")),
    ("the memo returns nothing",
     ("        return asked[key]", "asked[key]", "None")),
    ("no branch change is examined",
     ("    for m in _BRANCH_CHANGE.finditer(scanned):", "finditer(scanned)", 'finditer("")')),
    ("no rebase is examined",
     ("    for m in _REBASE.finditer(scanned):", "finditer(scanned)", 'finditer("")')),
    ("a rebase's tail is read from its options group",
     ("target = _rebase_range(m.group(2)", "m.group(2)", "m.group(1)")),
    ("an unnamed repository reaches the rebase probe",
     ("if directory and target and REBASE_REASON not in found:", "directory and ", "")),
    ("the rebase decision is inverted",
     ("if _rewrites_published(directory, *target, git):", "if _rewrites", "if not _rewrites")),
    ("the rebase reports the merging-switch reason",
     ("found.append(REBASE_REASON)", "REBASE_REASON", "MERGE_SWITCH_REASON")),
    ("an unnamed repository reaches the branch probes",
     ("        if directory is None:", "is None", "is False")),
    ("the branch-change tail is the subcommand word",
     ("tail, raw = m.group(3), command[m.start(3):m.end(3)]", "m.group(3)", "m.group(2)")),
    ("the reset parse gets the options for its subcommand",
     ("target = _reset_target(tail, raw, m.group(2))", "m.group(2)", "m.group(1)")),
    ("a non-reset branch change reaches the reset probe",
     ("if target and BRANCH_RESET_REASON not in found:", "target and ", "")),
    ("the reset decision is inverted",
     ("if _orphans_commits(directory, *target, git):", "if _orphans", "if not _orphans")),
    ("the reset reports the rebase reason",
     ("found.append(BRANCH_RESET_REASON)", "BRANCH_RESET_REASON", "REBASE_REASON")),
    ("the merge check gets the options for its subcommand",
     ("if _merges_on_switch(tail, m.group(2))", "m.group(2)", "m.group(1)")),
    ("the merging-switch decision is inverted",
     ("if _holds_staged_work(directory, git):", "if _holds", "if not _holds")),
    ("the merging switch reports the rebase reason",
     ("found.append(MERGE_SWITCH_REASON)", "MERGE_SWITCH_REASON", "REBASE_REASON")),
    ("the history reasons are dropped",
     ("found.append(MERGE_SWITCH_REASON)", "return found", "return []", 2, 1)),
    # _reasons
    ("the deadline starts at the epoch",
     ("    started = time.monotonic()", "time.monotonic()", "0.0")),
    ("the history reasons replace the earlier ones",
     ("found += _history_reasons(", "found +=", "found =")),
    ("the history check's stderr note changes its wording",
     ("the rebase and branch-change check raised", "check raised", "check threw")),
):
    _mut(_what, *_args)

# The rebase directory and the branch-change directory lines are identical, so
# each is anchored by the line after it.
_ri = _LINES.index(_line("target = _rebase_range(m.group(2)"))
_rb = _LINES[_ri - 1:_ri + 1]
MUTANTS.append((
    "a rebase probes the process cwd instead of its directory",
    HOOK, _NL.join(_rb), _NL.join([_rb[0].replace("scanned, cwd)", 'scanned, ".")'), _rb[1]]), TARGETS,
))
_bi = _LINES.index(_line("        if directory is None:"))
_bb = _LINES[_bi - 1:_bi + 1]
MUTANTS.append((
    "a branch change probes the process cwd instead of its directory",
    HOOK, _NL.join(_bb), _NL.join([_bb[0].replace("scanned, cwd)", 'scanned, ".")'), _bb[1]]), TARGETS,
))
_fi = _LINES.index(_line("    for m in _REBASE.finditer(scanned):"))
_fb = _LINES[_fi - 1:_fi + 1]
MUTANTS.append((
    "every command carries a rebase reason",
    HOOK, _NL.join(_fb), _NL.join([_fb[0].replace("= []", "= [REBASE_REASON]"), _fb[1]]), TARGETS,
))
_vi = _LINES.index(_line("    for cluster in _SHORT_CLUSTER.findall(scanned_tail):"))
_vb = _LINES[_vi - 1:_vi + 1]
MUTANTS.append((
    "switch's value letters become checkout's in the -m search",
    HOOK, _NL.join(_vb), _NL.join([_vb[0].replace('"switch"', '"checkout"'), _vb[1]]), TARGETS,
))
_ti = _LINES.index(_line("    reset = values[1]"))
_tb = _LINES[_ti - 1:_ti + 1]
MUTANTS.append((
    "switch is read with checkout's value letters in a reset",
    HOOK, _NL.join(_tb), _NL.join([_tb[0].replace('"switch"', '"checkout"'), _tb[1]]), TARGETS,
))
_lt = "            timeout=GIT_TIMEOUT_SECONDS if timeout is None else timeout,"
assert _LIB_TEXT.count(_lt) == 1, _lt
MUTANTS.append((
    "run_git ignores a shorter timeout, so the history probes each get 3s",
    LIB, _lt, "            timeout=GIT_TIMEOUT_SECONDS,", TARGETS,
))
