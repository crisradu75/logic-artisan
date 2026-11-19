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

# --- 21+. Rebase, rebasing pull, branch reset and merging switch -------------
# One mutant per changed line that carries logic. Left out, and why: the
# continuation lines of the three reason strings (the tests match a phrase from
# one line of each, so editing another line changes nothing a test can see),
# `def`/`class` lines, closing brackets, `self.asked: dict = {}` (no wrong value
# still runs), and the stderr lines after the first of each note. A line that
# occurs more than once in the hook is anchored as a block starting at a unique
# neighbour (`_mut`'s `n`/`at`).
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
    # matchers and tables
    ("the history probe budget is zero",
     ("_PROBE_BUDGET_SECONDS = HOOK_WORST_CASE_SECONDS", 'HOOK_WORST_CASE_SECONDS["ask-destructive-git.py"]', "0.0")),
    ("git rebase is never matched",
     ("_REBASE = GitInvocation(", "rebase", "rebaseX")),
    ("git pull is never matched",
     ("_PULL = GitInvocation(", "pull", "pullX")),
    ("git switch is never matched by the history checks",
     ("_BRANCH_CHANGE = GitInvocation(", "(checkout|switch)", "(checkout)")),
    ("no rebase action is recognised, so --continue is probed",
     ("_REBASE_ACTION = re.compile(", '"--(?:"', '"---(?:"')),
    ("--con no longer reads as --continue",
     ('_abbrev("continue", 3)', '_abbrev("continue", 3)', '"continue"')),
    ("--edit-todo no longer reads as an action",
     ('_abbrev("edit-todo", 2)', '_abbrev("edit-todo", 2)', '"xedit-todo"')),
    ("the rebase action pattern never matches",
     ('_abbrev("edit-todo", 2)', '")")', '"X)")', 2, 1)),
    ("--ro no longer reads as --root",
     ("_REBASE_ROOT = re.compile(", '_abbrev("root", 2)', '_abbrev("root", 4)')),
    ("no long rebase option takes a value",
     ("_REBASE_VALUE_LONG = re.compile(", '"--(?:"', '"---(?:"')),
    ("--ont no longer reads as --onto, so its value is an operand",
     ('_abbrev("onto", 1), _abbrev("exec", 2), "strategy"', '_abbrev("onto", 1)', '"onto"')),
    ("--whitespace stops taking a value",
     ('_abbrev("whitespace", 1)', '_abbrev("whitespace", 1)', '"xwhitespace"')),
    ("the rebase value-option pattern never matches",
     ('_abbrev("whitespace", 1)', '")")', '"X)")', 2, 1)),
    ("-x stops taking a value",
     ("_REBASE_VALUE_SHORT = ", '"CxsX"', '"CsX"')),
    ("-S and -r stop owning the rest of their cluster",
     ("_REBASE_OPTIONAL_SHORT = ", '"Sr"', '""')),
    ("--reb no longer reads as --rebase",
     ("_PULL_REBASE = re.compile(", '_abbrev("rebase", 3)', '_abbrev("rebase", 6)')),
    ("--no-rebase is not recognised",
     ("_PULL_NO_REBASE = re.compile(", '_abbrev("no-rebase", 6)', '"xno-rebase"')),
    ("--depth stops taking a value",
     ('"--strategy", "--strategy-option", "--depth"', '"--depth"', '"--xdepth"')),
    ("--refmap stops taking a value",
     ('"--shallow-exclude", "--server-option"', '"--refmap"', '"--xrefmap"')),
    ("--negotiation-tip stops taking a value",
     ('    "--negotiation-tip",', '"--negotiation-tip"', '"--xnegotiation-tip"')),
    ("-s stops taking a value in a pull",
     ("_PULL_VALUE_SHORT = ", '"sXo"', '"Xo"')),
    ("-S stops owning the rest of its cluster in a pull",
     ("_PULL_OPTIONAL_SHORT = ", '"rjS"', '"rj"')),
    ("--rebase=false reads as a rebase",
     ("_NOT_REBASE = frozenset(", '"false", ', "")),
    ("--force- no longer reads as --force-create",
     ("_FORCE_CREATE_LONG = re.compile(", '_abbrev("force-create", 6)', '_abbrev("force-create", 7)')),
    ("--conflict stops taking a value in a branch reset",
     ("_BRANCH_VALUE_LONG = frozenset(", "frozenset({", "frozenset() and ({")),
    ("--c no longer reads as --conflict",
     ("_MERGE_SWITCH_LONG = re.compile(", '_abbrev("conflict", 1)', '"conflict"')),
    ("no redirection is recognised, so `2>/dev/null` is an operand",
     ("_REDIRECT = re.compile(", 'r"', 'r"(?!)')),
    # the three reasons
    ("the rebase reason loses the phrase the tests match",
     ('"already on a remote-tracking branch', "already on a remote-tracking", "already on a remote")),
    ("the branch-reset reason loses the phrase the tests match",
     ("the reset orphans them", "orphans them", "drops them")),
    ("the merging-switch reason loses the phrase the tests match",
     ("a merging branch change (", "merging branch change", "merge branch change")),
    # _words
    ("_words starts with a stray word",
     ("    words: list[str] = []", "= []", '= ["x"]')),
    ("_words drops the first word as a redirection target",
     ("    words: list[str] = []", "target = False", "target = True", 2, 1)),
    ("_words reads nothing",
     ("    words: list[str] = []", "scanned_tail):", "scanned_tail[:0]):", 3, 2)),
    ("a bare continuation becomes an empty operand",
     ("        if not real:", "if not real:", "if not real and False:")),
    ("everything after a redirection target is dropped",
     ("        if target:", "target = False", "target = True", 2, 1)),
    ("a comment's words become operands",
     ('elif flag.startswith("#"):', '"#"', '"#X"')),
    ("a redirection is never recognised",
     ("(redirect := _REDIRECT.match(flag))", "match(flag)", 'match("")')),
    ("a redirection's separate target becomes an operand",
     ("target = redirect.end() == len(flag)", "redirect.end() == len(flag)", "False")),
    ("a word is kept with its quotes' scanned text",
     ("            words.append(real)", "append(real)", "append(flag)")),
    ("_words loses its last word",
     ("    return words", "return words", "return words[:-1]")),
    # _cluster
    ("a short cluster's first letter is skipped",
     ("for i, ch in enumerate(letters):", "enumerate(letters)", "enumerate(letters[1:])")),
    ("an optional-value letter takes the next word",
     ("        if ch in optional:", "return False", "return True", 2, 1)),
    ("an attached value still takes the next word",
     ("return i == len(letters) - 1", "i == len(letters) - 1", "True")),
    ("a valueless cluster takes the next word",
     ("return i == len(letters) - 1", "return False", "return True", 2, 1)),
    # _rebase_range
    ("the rebase operands start with a stray `main`",
     ("    root = rewrites = skip = False", "root = rewrites = skip = False", "root = rewrites = skip = False; operands.append(\"main\")")),
    ("a value-option key keeps its `=value`",
     ('        key = word.partition("=")[0]', 'partition("=")[0]', 'partition("#")[0]')),
    ("a skipped value also skips every word after it",
     ("        key = word.partition(", "skip = False", "skip = True", 3, 2)),
    ("a long rebase option is read as a short cluster",
     ("            if _REBASE_ACTION.fullmatch(key):", "_REBASE_ACTION.fullmatch(key)", "_REBASE_ACTION.fullmatch(key) and False", 1)),
    ("an action on a rebase under way is probed",
     ("            if _REBASE_ACTION.fullmatch(key):", "return None", "pass", 2, 1)),
    ("--root is never recognised",
     ("root = root or _REBASE_ROOT", "root = root or", "root = root and")),
    ("an attached long value also skips the next word",
     ("skip = key == word and _REBASE_VALUE_LONG", "key == word and ", "")),
    ("`-` is read as an empty short cluster",
     ('elif word.startswith("-") and word != "-":', ' and word != "-"', "")),
    ("a rebase cluster's value letters are ignored",
     ("skip = _cluster(letters, _REBASE_VALUE_SHORT", "_REBASE_VALUE_SHORT", '""')),
    ("`-` is passed on instead of `@{-1}`",
     ('operands.append("@{-1}" if word == "-" else word)', '"@{-1}" if word == "-" else word', "word")),
    ("--root is ignored",
     ("    if root:", "if root:", "if False:")),
    ("--root's branch operand is ignored",
     ('return (operands[0] if operands else "HEAD"), None, True', "operands[0] if operands", '"HEAD" if operands')),
    # No mutant for `None, True`: with no upstream the third field is never read.
    ("a rebase's branch operand is ignored",
     ('operands[1] if len(operands) > 1 else "HEAD",', "operands[1] if len(operands) > 1", '"HEAD" if len(operands) > 1')),
    ("a bare rebase counts from main instead of its upstream",
     ('operands[0] if operands else "@{upstream}",', '"@{upstream}"', '"main"')),
    ("no option ever forces a replay",
     ('operands[0] if operands else "@{upstream}",', "rewrites,", "False,", 2, 1)),
    # _pull_rebase / _pull_upstream
    ("a pull starts out rebasing",
     ("    rebase: bool | None = None", "= None", "= True")),
    ("the pull operands start with a stray word",
     ("    rebase: bool | None = None", "= []", '= ["x"]', 2, 1)),
    ("a pull's skipped value also skips every word after it",
     ("    rebase: bool | None = None", "skip = False", "skip = True", 3, 2)),
    ("a pull's `=value` is not split from its key",
     ("    rebase: bool | None = None", 'partition("=")', 'partition("#")', 5, 4)),
    ("--rebase is not recognised",
     ("if _PULL_REBASE.fullmatch(key):", "_PULL_REBASE.fullmatch(key)", "False")),
    ("--rebase=false reads as a rebase (the value is ignored)",
     ("rebase = value.lower() not in _NOT_REBASE if eq else True", "value.lower() not in _NOT_REBASE if eq else True", "True")),
    ("--no-rebase is ignored",
     ("elif _PULL_NO_REBASE.fullmatch(key):", "rebase = False", "pass", 2, 1)),
    ("a pull's long value options take no value",
     ("skip = not eq and key in _PULL_VALUE_LONG", "not eq and key in _PULL_VALUE_LONG", "False")),
    ("-r is never found in a pull cluster",
     ('            r = letters.find("r")', 'find("r")', 'find("R")')),
    ("an -r owned by an earlier value letter still rebases",
     ("if r >= 0 and not any(ch in _PULL_VALUE_SHORT", " and not any(", " and True or any(")),
    ("-rfalse reads as a rebase",
     ("rebase = letters[r + 1:].lower() not in _NOT_REBASE", "letters[r + 1:].lower() not in _NOT_REBASE", "True")),
    ("a pull cluster's value letters are ignored",
     ("skip = _cluster(letters, _PULL_VALUE_SHORT", "_PULL_VALUE_SHORT", '""')),
    ("a pull's operands are dropped",
     ("    return rebase, operands", "rebase, operands", "rebase, []")),
    ("more than one pull branch is accepted",
     ("    if len(operands) > 2:", "> 2", "> 3")),
    ("a pull with a remote and branch uses the upstream",
     ("    if len(operands) < 2:", "< 2", "< 3")),
    ("a pull's refspec destination is used instead of its source",
     ('branch = operands[1].lstrip("+").partition(":")[0]', "[0]", "[2]")),
    ("refs/heads/ is never stripped from a pull branch",
     ('    if branch.startswith("refs/heads/"):', '"refs/heads/"', '"refs/headsX/"')),
    ("a stripped pull branch keeps its prefix",
     ("        branch = branch[len(", 'branch[len("refs/heads/"):]', "branch")),
    ("a pull's remote-tracking ref is built wrongly",
     ('    return "refs/remotes/" + operands[0]', '"refs/remotes/"', '"refs/remote/"')),
    # _reset_target
    ("the create letter is taken for the reset letter",
     ("    reset = values[1]", "values[1]", "values[0]")),
    ("every branch change resets `uniq`",
     ("    name: str | None = None", "= None", '= "uniq"')),
    ("the start point defaults to `uniq`",
     ("    name: str | None = None", "= []", '= ["uniq"]', 2, 1)),
    ("the reset parse skips its first word",
     ("    i = 0", "i = 0", "i = 1")),
    ("the reset parse skips its last word",
     ("    while i < len(words):", "len(words)", "len(words) - 1")),
    ("the reset parse rereads the first word",
     ("        word = words[i]", "words[i]", "words[0]")),
    ("the next word is taken to be the current one",
     ('nxt = words[i + 1] if i + 1 < len(words) else ""', "words[i + 1] if", "words[i] if")),
    ("--force-create is read as a short cluster",
     ("        nxt = words[i + 1]", '"--"', '"---"', 2, 1)),
    ("--force-create=name loses its attached name",
     ("        nxt = words[i + 1]", 'partition("=")', 'partition("#")', 3, 2)),
    ("checkout takes --force-create again",
     ('if subcommand == "switch" and _FORCE_CREATE_LONG.fullmatch(key):', 'subcommand == "switch" and ', "")),
    ("the attached and separate --force-create names are swapped",
     ("name, i = (value, i) if eq else (nxt, i + 1)", "if eq", "if not eq")),
    ("a long value option's value becomes the start point",
     ("elif word in _BRANCH_VALUE_LONG:", "i += 1", "i += 0", 2, 1)),
    ("a short cluster is read as an operand",
     ("elif word in _BRANCH_VALUE_LONG:", 'elif word.startswith("-"):', 'elif word.startswith("+"):', 3, 2)),
    ("a short cluster's first letter is skipped in a reset",
     ("for j, ch in enumerate(word[1:]):", "word[1:]", "word[2:]")),
    ("no letter takes a value in a reset",
     ("for j, ch in enumerate(word[1:]):", "values", '"xX"', 2, 1)),
    ("an attached name keeps its letter",
     ("value = word[j + 2:]", "j + 2", "j + 1")),
    ("a separate name is also read as the start point",
     ("value, i = nxt, i + 1", "i + 1", "i")),
    ("the create letter resets and the reset letter does not",
     ("if ch == reset:", "==", "!=")),
    ("a cluster keeps reading after its value letter",
     ("                        name = value", "break", "pass", 2, 1)),
    ("the start point is always HEAD",
     ("                        name = value", "append(word)", 'append("HEAD")', 5, 3)),
    ("the reset parse skips a word after each operand",
     ("                        name = value", "i += 1", "i += 2", 5, 4)),
    ("a command with no reset resets `uniq`",
     ("    if not name:", "return None", 'return "uniq", "HEAD"', 2, 1)),
    ("the start point defaults to `uniq` at the end",
     ('return name, (operands[0] if operands else "HEAD")', '"HEAD"', '"uniq"')),
    # _merges_on_switch
    ("the checkout -m -- <path> form reads as a merging switch",
     ('    if "--" in words:', '"--"', '"---"')),
    ("--merge is never recognised",
     ("if _MERGE_SWITCH_LONG.fullmatch(", "_MERGE_SWITCH_LONG.fullmatch(", "False and _MERGE_SWITCH_LONG.fullmatch(")),
    ("a cluster's first letter is skipped for -m",
     ("            for ch in word[1:]:", "word[1:]", "word[2:]")),
    ("-m is not the merge letter",
     ('                if ch == "m":', '"m"', '"M"')),
    ("a value letter no longer ends the -m search",
     ('                if ch == "m":', "break", "pass", 4, 3)),
    # _Probes
    ("the deadline is in the past",
     ("self.deadline = started + budget", "started + ", "started - ")),
    ("every probe in a directory shares one answer",
     ("key = (directory, tuple(args))", "(directory, tuple(args))", "directory")),
    ("an identical probe runs again",
     ("if key not in self.asked:", "key not in self.asked", "True")),
    ("the deadline is measured from the wrong end",
     ("left = self.deadline - time.monotonic()", "self.deadline - time.monotonic()", "time.monotonic() - self.deadline")),
    ("each history probe gets the full 3s, however late",
     ("timeout=min(GIT_TIMEOUT_SECONDS, left)", "min(GIT_TIMEOUT_SECONDS, left)", "GIT_TIMEOUT_SECONDS")),
    ("a probe starts after the budget is spent",
     ("if left > 0 else None", "left > 0", "left > -1")),
    ("a probe that did not run is not noted",
     ("self.missed = self.missed or self.asked[key] is None", "is None", "is False")),
    ("a missed probe is noted from the start",
     ("        self.missed = False", "False", "True")),
    ("the memo returns nothing",
     ("        return self.asked[key]", "self.asked[key]", "None")),
    ("a revision starting with a dash is probed",
     ('if not rev or rev.startswith("-"):', ' or rev.startswith("-")', "")),
    ("rev-parse loses --end-of-options",
     ('"rev-parse", "--verify", "--quiet", "--end-of-options"', ' "--end-of-options",', "")),
    ("a refused rev-parse still yields its output",
     ('sha = out.stdout.strip() if out is not None and out.returncode == 0 else ""', " and out.returncode == 0", "")),
    ("any rev-parse output passes as a SHA",
     ('return sha if re.fullmatch(r"[0-9a-f]{40,64}", sha) else None', "if re.fullmatch(", "if True or re.fullmatch(")),
    # _rewrites_published
    ("an unresolved branch is still probed",
     ("    tip = probes.commit(directory, branch)", "return False", "pass", 3, 2)),
    ("the upstream is not excluded from the range",
     ("    span = [tip]", "span = [tip]", "span = [tip]; upstream = None")),
    ("the upstream is never resolved",
     ("        base = probes.commit(directory, upstream)", "upstream)", '"main")')),
    ("an unresolved upstream is still counted",
     ("        base = probes.commit(directory, upstream)", "return False", "pass", 3, 2)),
    ("the up-to-date check asks the wrong way round",
     ('["merge-base", "--is-ancestor", base, tip]', "base, tip", "tip, base")),
    ("the range loses its upstream",
     ('        span.append("^" + base)', '"^" + base', "tip")),
    ("the first count also leaves out the remotes",
     ('every = probes.git(directory, ["rev-list", "--count", *span, "--"])', '*span, "--"]', '*span, "--not", "--remotes", "--"]')),
    ("a successful first count is read as a refusal",
     ("if every is None or every.returncode != 0:", "!= 0", "== 0")),
    ("the second count keeps the remotes",
     ('"--not", "--remotes", "--"])', '"--remotes", ', "")),
    ("a successful second count is read as a refusal",
     ("if local is None or local.returncode != 0:", "!= 0", "== 0")),
    ("equal counts read as published",
     ("return int(every.stdout) > int(local.stdout)", " > ", " >= ")),
    # _pull_rebases
    ("the command's own rebase flag is ignored",
     ("    if rebase is not None:", "return rebase", "pass", 2, 1)),
    ("the branch setting is never read",
     ('head = probes.git(directory, ["symbolic-ref"', '"--short", "HEAD"', '"--short", "NOHEAD"')),
    ("pull.rebase is never read",
     ('    keys = ["pull.rebase"]', '"pull.rebase"', '"pull.rebaseX"')),
    ("the branch setting no longer outranks pull.rebase",
     ('keys.insert(0, "branch." + head.stdout.strip() + ".rebase")', "insert(0, ", "insert(9, ")),
    ("a branch lookup that did not run is read anyway",
     ("if head is not None and head.stdout.strip():", "head is not None and ", "")),
    # _orphans_commits
    ("a branch name starting with a dash is probed",
     ('    if name.startswith("-"):', 'name.startswith("-")', "False")),
    ("the branch tip is never resolved",
     ('tip = probes.commit(directory, "refs/heads/" + name)', '"refs/heads/" + name', '"refs/heads/x"')),
    ("the start point is never resolved",
     ("    target = probes.commit(directory, start)", "start)", '"HEAD")')),
    ("an unresolved tip or start is still counted",
     ("    if tip is None or target is None:", "return False", "pass", 2, 1)),
    ("the other refs are counted instead of excluded",
     ('"rev-list", "--count", tip, "--not",', ' "--not",', "")),
    ("the branch itself is not excluded",
     ('"--exclude=" + name, "--branches"', '"--exclude=" + name, ', "")),
    ("tags no longer keep commits reachable",
     ('"--exclude=" + name, "--branches"', '"--tags", ', "")),
    ("remote-tracking refs no longer keep commits reachable",
     ('"--exclude=" + name, "--branches"', '"--remotes", ', "")),
    ("the start point is not excluded",
     ('"--exclude=" + name, "--branches"', "target, ", "")),
    ("an existing branch always orphans something",
     ("return out is not None and out.returncode == 0 and int(out.stdout) > 0", "> 0", ">= 0")),
    # _holds_staged_work
    ("the status probe drops --porcelain",
     ('["status", "--porcelain", "--untracked-files=no"]', '"--porcelain", ', "")),
    ("untracked files count as staged",
     ('["status", "--porcelain", "--untracked-files=no"]', ', "--untracked-files=no"', "")),
    ("a successful status probe is read as a refusal",
     ("out = probes.git(directory, [\"status\"", "!= 0", "== 0", 2, 1)),
    ("an unstaged change counts as staged",
     ("return any(line[:1].strip() for line", "line[:1].strip()", "line[:1]")),
    # _history_reasons
    ("the probes start their deadline at the epoch",
     ("    probes = _Probes(started)", "_Probes(started)", "_Probes(0.0)")),
    ("every command carries a rebase reason",
     ("    probes = _Probes(started)", "= []", "= [REBASE_REASON]", 2, 1)),
    ("no rebase is examined",
     ("    for m in _REBASE.finditer(scanned):", "finditer(scanned)", 'finditer("")')),
    ("a rebase probes the process cwd instead of its directory",
     ("    for m in _REBASE.finditer(scanned):", "scanned, cwd)", 'scanned, ".")', 2, 1)),
    ("a rebase's tail is read from its options group",
     ("target = _rebase_range(_words(m.group(2)", "m.group(2), command", "m.group(1), command")),
    ("an unnamed repository reaches the rebase probe",
     ("if directory and target and REBASE_REASON not in found:", "directory and ", "")),
    ("no pull is examined",
     ("    for m in _PULL.finditer(scanned):", "finditer(scanned)", 'finditer("")')),
    ("a pull probes the process cwd instead of its directory",
     ("    for m in _PULL.finditer(scanned):", "scanned, cwd)", 'scanned, ".")', 2, 1)),
    ("a pull's tail is read from its options group",
     ("rebase, operands = _pull_rebase(_words(m.group(2)", "m.group(2), command", "m.group(1), command")),
    ("a pull's upstream is always its own",
     ("        upstream = _pull_upstream(operands)", "_pull_upstream(operands)", '"@{upstream}"')),
    ("an unnamed repository reaches the pull probe",
     ("if directory and upstream and REBASE_REASON not in found:", "directory and ", "")),
    ("no branch change is examined",
     ("    for m in _BRANCH_CHANGE.finditer(scanned):", "finditer(scanned)", 'finditer("")')),
    ("a branch change probes the process cwd instead of its directory",
     ("    for m in _BRANCH_CHANGE.finditer(scanned):", "scanned, cwd)", 'scanned, ".")', 2, 1)),
    ("an unnamed repository reaches the branch probes",
     ("        if directory is None:", "is None", "is False")),
    ("the branch-change words are the subcommand word",
     ("words = _words(m.group(3), command[m.start(3):m.end(3)])", "m.group(3), command", "m.group(2), command")),
    ("the reset parse gets the options for its subcommand",
     ("target = _reset_target(words, m.group(2))", "m.group(2)", "m.group(1)")),
    ("a non-reset branch change reaches the reset probe",
     ("if target and BRANCH_RESET_REASON not in found:", "target and ", "")),
    ("the reset decision is inverted",
     ("if _orphans_commits(directory, *target, probes):", "if _orphans", "if not _orphans")),
    ("the reset reports the rebase reason",
     ("found.append(BRANCH_RESET_REASON)", "BRANCH_RESET_REASON", "REBASE_REASON")),
    ("the merge check gets the options for its subcommand",
     ("if _merges_on_switch(words, m.group(2))", "m.group(2)", "m.group(1)")),
    ("the merging-switch decision is inverted",
     ("if _holds_staged_work(directory, probes):", "if _holds", "if not _holds")),
    ("the merging switch reports the rebase reason",
     ("found.append(MERGE_SWITCH_REASON)", "MERGE_SWITCH_REASON", "REBASE_REASON")),
    ("a missed probe leaves no note",
     ("    if probes.missed:", "if probes.missed:", "if False:")),
    ("the missed-probe note changes its wording",
     ("a rebase or branch-change probe did not run", "did not run", "was skipped")),
    ("the history reasons are dropped",
     ('"asking about it. (hook: ask-destructive-git.py)",', "return found", "return []", 4, 3)),
    # _reasons
    ("the deadline starts at the epoch",
     ("    started = time.monotonic()", "time.monotonic()", "0.0")),
    ("the history reasons replace the earlier ones",
     ("found += _history_reasons(", "found +=", "found =")),
    ("the history check's stderr note changes its wording",
     ("the rebase and branch-change check raised", "check raised", "check threw")),
):
    _mut(_what, *_args)

# --- review round 2: no-replay set, fork-point, -c overrides, unquoting ----
for _what, _args in (
    ("no long option is in the no-replay set",
     ("_REBASE_NO_REPLAY_LONG = frozenset({", "frozenset({", "frozenset() and ({")),
    ("--keep-base leaves the no-replay set",
     ('"--rebase-merges", "--no-rebase-merges", "--keep-base"', '"--keep-base", ', "")),
    ("--autosquash leaves the no-replay set",
     ('"--autosquash", "--no-autosquash", "--quiet"', '"--autosquash", ', "")),
    ("--update-refs leaves the no-replay set",
     ('"--update-refs", "--no-update-refs", "--strategy"', '"--update-refs", ', "")),
    ("--autostash leaves the no-replay set",
     ('"--autostash", "--no-autostash", "--verify"', '"--autostash", ', "")),
    ("--no-fork-point leaves the no-replay set",
     ('"--fork-point", "--no-fork-point", "--rerere-autoupdate"', '"--no-fork-point", ', "")),
    ("--merge leaves the no-replay set",
     ('    "--merge",', '"--merge"', '"--xmerge"')),
    ("-r leaves the no-replay set",
     ("_REBASE_NO_REPLAY_SHORT = ", '"rqvnsXm"', '"qvnsXm"')),
    ("no -c override is read",
     ("_DASH_LOWER_C = re.compile(", "-c", "-k")),
    ("the tab escape is misread",
     ("_ANSI_C = {", '"t": ', '"T": ', 2, 1)),
    ("an escaped quote in $'...' keeps its backslash",
     ("_ANSI_C = {", "\"'\": \"'\", ", "", 3, 2)),
    ("no quoted segment is recognised",
     ("_QUOTED = re.compile(", 'r"""', 'r"""(?!)', 2, 1)),
    ("a hex escape is not recognised",
     ("_ANSI_ESCAPE = re.compile(", "x[0-9a-fA-F]{1,2}|", "")),
    ("a backslash in double quotes escapes nothing",
     ("_DOUBLE_ESCAPE = re.compile(", "re.compile(", 're.compile("(?!)" + ')),
    # _words, _unquote, _ansi_char
    ("words are not unquoted",
     ("real = _unquote(raw_tail", "_unquote(", "(")),
    ("a closing parenthesis stays on a word",
     ("real = _unquote(raw_tail", '.rstrip("', '.lstrip("')),
    ("_unquote starts with a stray character",
     ("    for m in _QUOTED.finditer(word):", "_QUOTED.finditer(word)", '_QUOTED.finditer("x" + word)')),
    ("an ANSI-C segment is read raw",
     ("            out.append(_ANSI_ESCAPE.sub(_ansi_char, ansi))", "_ANSI_ESCAPE.sub(_ansi_char, ansi)", "ansi")),
    ("an ANSI-C segment is never recognised",
     ("        if ansi is not None:", "is not None", "is None and False")),
    ("a double-quoted segment keeps its escapes",
     ('out.append(_DOUBLE_ESCAPE.sub(r"', "_DOUBLE_ESCAPE.sub(", "(lambda p, r, t: t)(")),
    ("a double-quoted segment is never recognised",
     ("        elif double is not None:", "is not None", "is None and False")),
    ("single, escaped and plain segments lose their text",
     ("out.append(next(g for g in (single, escaped, plain)", "(single, escaped, plain)", "(escaped, plain, single)")),
    ("_unquote drops its last segment",
     ('    return "".join(out)', '"".join(out)', '"".join(out[:-1])')),
    ("a hex escape reads as octal",
     ('    if code[0] == "x" and len(code) > 1:', '"x"', '"X"')),
    ("a hex escape is read in base 10",
     ("        return chr(int(code[1:], 16))", "16", "10")),
    ("an octal escape is not recognised",
     ('    if code[0] in "01234567":', '"01234567"', '"89"')),
    ("an octal escape is read in base 10",
     ("        return chr(int(code, 8))", ", 8)", ", 10)")),
    ("a named escape is not translated",
     ('    return _ANSI_C.get(code, "', "_ANSI_C.get(code, ", "(lambda c, d: d)(code, ")),
    # _config_overrides / _config_key
    ("an override's value is not unquoted",
     ('key, eq, value = _unquote(m.group(1)).partition("=")', "_unquote(m.group(1))", "m.group(1)")),
    ("a bare -c key is false",
     ('found[_config_key(key)] = value if eq else "true"', '"true"', '"false"')),
    ("override keys keep their case",
     ("found[_config_key(key)] = value", "_config_key(key)", "key")),
    ("the overrides are dropped",
     ("    for m in _DASH_LOWER_C.finditer(opts):", "finditer(opts)", 'finditer("")')),
    ("config sections keep their case",
     ('return ".".join([parts[0].lower(), *parts[1:-1], parts[-1].lower()])', "parts[0].lower()", "parts[0]")),
    ("config subsections are lowered",
     ('return ".".join([parts[0].lower(), *parts[1:-1], parts[-1].lower()])', "*parts[1:-1]", "*[q.lower() for q in parts[1:-1]]")),
    # _rebase_range
    ("a long option outside the no-replay set keeps the shortcut",
     ("rewrites = rewrites or key not in _REBASE_NO_REPLAY_LONG", "not in", "in")),
    ("--fork-point and --no-fork-point are ignored",
     ('fork_point = {"--fork-point": True, "--no-fork-point": False}', '"--no-fork-point": False', '"--no-fork-pointX": False')),
    ("a short option outside the no-replay set keeps the shortcut",
     ("rewrites = rewrites or ch not in _REBASE_NO_REPLAY_SHORT", "not in", "in")),
    ("a value letter's value is read as more letters",
     ("if ch in _REBASE_VALUE_SHORT + _REBASE_OPTIONAL_SHORT:", "break", "pass", 2, 1)),
    ("an upstream operand keeps fork-point on",
     ("    if fork_point is None and operands:", "fork_point = False", "fork_point = None", 2, 1)),
    ("fork-point is never passed on",
     ('operands[0] if operands else "@{upstream}",', "fork_point,", "False,", 3, 2)),
    # _pull_upstream
    ("`.` is read as a remote name",
     ('    if operands[0] == ".":', '"."', '"./"')),
    ("`.` rebases onto the remote-tracking ref",
     ('    if operands[0] == ".":', "return branch", 'return "refs/remotes/./" + branch', 4, 3)),
    # _Probes.commit / ref / setting
    ("`:/` gets a ^{commit} suffix",
     ('peeled = rev if rev.startswith(":/") else rev', '":/"', '":/X"')),
    ("no revision is peeled to a commit",
     ('peeled = rev if rev.startswith(":/") else rev', ' + "^{commit}"', "")),
    ("the ref probe accepts a dash",
     ("    def ref(self, directory: str, rev: str)", 'rev.startswith("-")', "False", 5, 4)),
    ("the ref probe drops --symbolic-full-name",
     ('"rev-parse", "--verify", "--quiet", "--symbolic-full-name", "--end-of-options", rev,', ' "--symbolic-full-name",', "")),
    ("a refused ref probe still yields its output",
     ('name = out.stdout.strip() if out is not None and out.returncode == 0 else ""', " and out.returncode == 0", "")),
    ("any ref probe output passes as a ref",
     ('return name if re.fullmatch(r"refs/', "if re.fullmatch(", "if True or re.fullmatch(")),
    ("an override is never consulted",
     ("        if _config_key(key) in overrides:", "in overrides", "in {}")),
    ("an override returns the wrong value",
     ("            return overrides[_config_key(key)]", "overrides[_config_key(key)]", '"true"')),
    ("the repository setting is read from the wrong key",
     ('out = self.git(directory, ["config", "--get", key])', "key]", '"x"]')),
    ("an unset repository setting reads as set",
     ("return out.stdout.strip() if out is not None and out.returncode == 0 else None", "returncode == 0", "returncode != 9")),
    # _rewrites_published / _replays_nothing
    ("the up-to-date shortcut always applies",
     ("if not rewrites and _replays_nothing(", "not rewrites and ", "True or ")),
    ("fork-point is never passed to the up-to-date check",
     ("if not rewrites and _replays_nothing(", "fork_point, probes)", "False, probes)")),
    ("an ancestry probe that cannot run asks for counts",
     ('    ancestor = probes.git(directory, ["merge-base"', "return True", "return False", 3, 2)),
    ("a non-ancestor upstream reads as up to date",
     ("    if ancestor.returncode != 0:", "return False", "return True", 2, 1)),
    ("fork-point is always on",
     ("ref = probes.ref(directory, upstream) if fork_point else None", "if fork_point", "if True")),
    ("no fork-point ref means not up to date",
     ("    if ref is None:", "return True", "return False", 2, 1)),
    ("the fork-point probe loses --end-of-options",
     ('["merge-base", "--fork-point", "--end-of-options", ref, tip]', ' "--end-of-options",', "")),
    ("the fork-point probe asks about the base",
     ('["merge-base", "--fork-point", "--end-of-options", ref, tip]', "ref, tip]", "ref, base]")),
    ("a fork-point probe that cannot run asks for counts",
     ('["merge-base", "--fork-point", "--end-of-options", ref, tip]', "return True", "return False", 3, 2)),
    ("a refused fork-point probe yields its output",
     ('found = out.stdout.strip() if out.returncode == 0 else ""', "if out.returncode == 0", "if True")),
    ("an older fork point reads as up to date",
     ('    return found in ("", base)', '("", base)', '("", base, found)')),
    # _pull_rebases / _is_true
    ("the pull settings ignore the -c overrides",
     ("value = probes.setting(directory, key, overrides)", "overrides)", "{})")),
    ("an unset pull setting reads as a decision",
     ("value = probes.setting(directory, key, overrides)", "is not None", "is None", 2, 1)),
    ("a pull setting's value is ignored",
     ("            return _is_true(value)", "_is_true(value)", "True")),
    ("an unconfigured pull rebases",
     ("            return _is_true(value)", "return False", "return True", 2, 1)),
    ("a false setting reads as true",
     ('return value.strip().lower() not in _NOT_REBASE and value.strip() != ""', "not in _NOT_REBASE", "in _NOT_REBASE")),
    ("an empty setting reads as true",
     ('return value.strip().lower() not in _NOT_REBASE and value.strip() != ""', ' and value.strip() != ""', "")),
    # _history_reasons
    ("the rebase target is unpacked in the wrong order",
     ("branch, upstream, rewrites, fork_point = target", "branch, upstream", "upstream, branch")),
    ("the fork-point setting is never read",
     ("            if fork_point is None:", "if fork_point is None:", "if False:")),
    ("the fork-point setting ignores the -c overrides",
     ('setting = probes.setting(directory, "rebase.forkPoint", overrides)', "overrides)", "{})")),
    ("the fork-point default is off",
     ("fork_point = setting is None or _is_true(setting)", "setting is None or ", "")),
    ("the fork-point setting is ignored",
     ("fork_point = setting is None or _is_true(setting)", "_is_true(setting)", "True")),
    ("the rebase decision is inverted",
     ("if _rewrites_published(directory, branch, upstream, rewrites, fork_point, probes):", "if _rewrites", "if not _rewrites")),
    ("the rebase reports the merging-switch reason",
     ("if _rewrites_published(directory, branch, upstream, rewrites, fork_point, probes):", "REBASE_REASON", "MERGE_SWITCH_REASON", 2, 1)),
    ("a pull that merges is probed as a rebase",
     ("if _pull_rebases(directory, rebase, overrides, probes) and", "_pull_rebases(directory, rebase, overrides, probes)", "True")),
    ("a rebasing pull takes the up-to-date shortcut",
     ('directory, "HEAD", upstream, True, False, probes', "upstream, True,", "upstream, False,")),
    ("the pull reports the merging-switch reason",
     ('directory, "HEAD", upstream, True, False, probes', "REBASE_REASON", "MERGE_SWITCH_REASON", 3, 2)),
):
    _mut(_what, *_args)

_pi = _LINES.index(_line("if _pull_rebases(directory, rebase, overrides, probes) and"))
_pb = _LINES[_pi - 1:_pi + 1]
MUTANTS.append((
    "a pull ignores its -c overrides",
    HOOK, _NL.join(_pb), _NL.join([_pb[0].replace("command[m.start(1):m.end(1)]", '""'), _pb[1]]), TARGETS,
))

_vi = _LINES.index(_line("    reset = values[1]"))
_vb = _LINES[_vi - 1:_vi + 1]
MUTANTS.append((
    "switch is read with checkout's value letters in a reset",
    HOOK, _NL.join(_vb), _NL.join([_vb[0].replace('"switch"', '"checkout"'), _vb[1]]), TARGETS,
))
_mi = _LINES.index(_line('    if "--" in words:'))
_mb = _LINES[_mi:_mi + 3]
MUTANTS.append((
    "switch's value letters become checkout's in the -m search",
    HOOK, _NL.join(_mb), _NL.join([_mb[0], _mb[1], _mb[2].replace('"switch"', '"checkout"')]), TARGETS,
))
_lt = "            timeout=GIT_TIMEOUT_SECONDS if timeout is None else timeout,"
assert _LIB_TEXT.count(_lt) == 1, _lt
MUTANTS.append((
    "run_git ignores a shorter timeout, so the history probes each get 3s",
    LIB, _lt, "            timeout=GIT_TIMEOUT_SECONDS,", TARGETS,
))
