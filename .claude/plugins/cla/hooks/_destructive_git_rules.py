#!/usr/bin/env python3
r"""The rule tables and text classifiers of `ask-destructive-git.py`.

Pure text: the matchers, flag patterns and reason strings for each shape that
hook asks about, and the functions that read an invocation's words (operands,
option clusters, a rebase's range, a pull's mode, a branch reset's target). No
function here runs git or reads the filesystem except `_invocation_dir`, which
only joins paths; the probes live in `_destructive_git_probes.py` and the
decision in `ask-destructive-git.py`, whose module docstring states the
detection scope these tables implement. Every matcher reads text that hook's
`_scan` has already quote-stripped, part by part.

Split out of that hook, which had grown past 2,400 lines; the names it used are
re-exported there, so a test or mutant batch that reaches one through the hook
still finds it.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

# Loaded by path, like every hook: the `_dispatch_lib` import below is made
# explicit rather than left to how the process happened to start.
_HOOKS_DIR = str(Path(__file__).resolve().parent)
if _HOOKS_DIR not in sys.path:
    sys.path.insert(0, _HOOKS_DIR)

from _dispatch_lib import GitInvocation  # noqa: E402
from _shell_read import _SEP, _TAIL, _abbrev, _unquote  # noqa: E402

# Group 1 is the global options (for `-C`), group 2 the tail.
_STASH = GitInvocation(r"stash\b" + _TAIL, capture_opts=True)
_DASH_C = re.compile(r"(?<![\w-])-C" + _SEP + r"""("[^"]*"|'[^']*'|\S+)""")
# These stash subcommands do not save-and-reset the tree. Anything else does,
# including operand-less `git stash`, `push`, `save`, option-only forms, and a
# tail the matcher cannot read (`2>&1`, `)`, `# note`): an allow-list of saving
# shapes would stay silent on every shape nobody listed.
_STASH_NON_SAVING = re.compile(
    r"[\s\\]*(?:list|show|pop|apply|drop|clear|create|store|branch)\b"
)
# Env vars that point git at a repository other than the one at the cwd.
_GIT_ENV_REPO = re.compile(r"(?:^|[\s;&|(])GIT_(?:DIR|WORK_TREE)=")
_OPERATION_MARKERS = ("MERGE_HEAD", "CHERRY_PICK_HEAD", "REVERT_HEAD")


# What may follow a flag. `\\` is in the set because the shell strips
# `\`+newline before word-splitting, so `git reset --hard\`+newline+`  HEAD~1`
# is an ordinary hard reset — and a terminator of `(?:\s|=|$)` rejected it,
# because the `\` sits directly against the `d`. That was fixed for
# `git branch -D` and NOT carried to `--force`/`--hard`, which left the two
# oldest and most-cited rules in this file bypassable by a line continuation
# long after the same bug was closed one rule over. `)` and a backtick end a flag
# too: `echo "$(git reset --hard)"` closes the substitution right against it.
_END = r"(?:[\s\\)`]|=|$)"

# Two shapes force a push. The long flag, where the terminator is what spares
# `--force-with-lease` / `--force-if-includes` (both are followed by `-`, which
# the boundary rejects); and a bundled short cluster containing `f`. The
# `-[A-Za-z]*f[A-Za-z]*` arm cannot reach into `--force-with-lease`, because the
# character after the leading `-` there is another `-`, not a letter.
#
# `--force` stays spelled OUT here, and that is a measured exception rather than
# an oversight: `git push` also has `--follow-tags`, `--force-with-lease` and
# `--force-if-includes`, so `--f`, `--fo`, `--for` and `--forc` are all
# ambiguous and git refuses them. There is no shorter spelling to miss.
_FORCE_FLAG = re.compile(
    r"(?:^|\s)(?:--force" + _END + r"|-[A-Za-z]*f[A-Za-z]*(?:[\s\\)`]|$))"
)
# `git push origin +feat:feat` — force expressed in the refspec, no flag at all.
_FORCE_REFSPEC = re.compile(r"(?:^|\s)\+\S+")
# `--hard` is `git reset`'s ONLY `--h*` option, so the floor is 1 and
# `git reset --h` is an ordinary hard reset. It went unmatched — the loosest
# abbreviation in the file, on the rule the module docstring names first.
_HARD_FLAG = re.compile(r"(?:^|\s)--" + _abbrev("hard", 1) + _END)
# The three ways a push skips the `pre-push` guard: git's own `--no-verify`
# (abbreviable down to `--no-veri`; `--no-ver` is ambiguous with `--no-verbose`), a
# `core.hooksPath` pointed elsewhere for this one command, and one of the hook's own
# overrides typed inline: `ALLOW_PUSH_TO_MAIN=1` (a push to the default branch) or
# `ALLOW_TAG_REWRITE=1` (deleting or moving a remote tag).
_NO_VERIFY = re.compile(r"(?:^|\s)--" + _abbrev("no-verify", 7) + _END)
# Read on the RAW command, not the quote-stripped one: `-c "core.hooksPath=/x"`,
# `GIT_CONFIG_KEY_0=core.hooksPath`, `GIT_CONFIG_PARAMETERS="'core.hooksPath=/x'"`
# and a `git config core.hooksPath /x && git push` all point the hooks elsewhere,
# and quoting is what hides them from the stripped text. Prose naming the setting
# beside a push asks too, which fails in the safe direction.
_HOOKS_PATH = re.compile(r"(?i)\bcore\.hookspath\b")
# On the stripped text, where a quoted `"1"` reads `"#"`; the value may be followed
# by any separator (`export ALLOW_PUSH_TO_MAIN=1;git push`).
_ALLOW_PUSH_TO_MAIN = re.compile(
    r"(?:^|[\s;&|({])ALLOW_(?:PUSH_TO_MAIN|TAG_REWRITE)=(?:1|\"#\"|'#')(?=[\s;&|)]|$)"
)
PUSH_GUARD_SKIP_REASON = (
    "a push that skips the pre-push guard (`--no-verify`, `core.hooksPath`, "
    "`ALLOW_PUSH_TO_MAIN=1` or `ALLOW_TAG_REWRITE=1`) — confirm the user asked to bypass it"
)

# `git push --mirror` makes the remote's refs match this repository's: every
# remote branch and tag this clone lacks is DELETED, the default branch included,
# and git does not hand those deletions to the `pre-push` guard, so nothing else
# stands in front of them. `--mirror` is push's only `--m*` option, so `--m`
# resolves (measured). Named miss: a remote configured to mirror
# (`git remote add --mirror=push`) mirrors on a plain `git push`, which no flag
# in the command shows.
_MIRROR_FLAG = re.compile(r"(?:^|\s)--" + _abbrev("mirror", 1) + _END)
MIRROR_REASON = (
    "a mirror push (`git push --mirror`), which can delete every remote branch and "
    "tag this clone lacks, the default branch included, and git does not check "
    "those deletions with the pre-push guard"
)

# Force-deleting a branch is the same hazard class as `reset --hard`: on a branch
# whose commit exists nowhere else it destroys that commit outright, recoverable
# only from the reflog, inside its expiry window, and only by someone who thinks
# to look.
#
# The predicate is DELETE-flag AND FORCE-flag, not "contains a capital D". An
# earlier cut matched only `-D` and the literal `--delete`+`--force` pair, which
# is 3 of the 8 spellings of the same act: `-d -f`, `-df`, `-fd`, `-d --force`
# and `--delete -f` all force-delete and all went unmatched. `git-branch(1)`
# states the relation outright — "`-D`: Shortcut for `--delete --force`", and
# `--force` "in combination with `-d` (or `--delete`), allow deleting the branch
# irrespective of its merged status". `-D` is shorthand for the pair; encoding
# the shorthand as if it were the operation is what left the gap.
#
# Bare `-d` stays unmatched, and that IS a considered exclusion rather than an
# oversight: `git-branch(1)` says a `--delete` without force must be "fully
# merged in its upstream branch, or in `HEAD` if no upstream was set", so git
# itself refuses the destructive case. Adding force is what overrides that
# refusal, which is why force is half the predicate.
# Both boundaries are ZERO-WIDTH, and that is load-bearing rather than stylistic.
# A consuming `(?:^|\s)...(?:\s|$)` eats the separator between two clusters, so
# `findall` resumes past it and the next cluster has no leading whitespace left
# to match: `-d -f` yielded only `-d`, and the pair went unmatched while the
# bundled `-df` was caught.
#
# The terminator admits a backslash as well as whitespace: the shell strips
# `\`+newline before word-splitting, so `git branch -D\`+newline+`  feat` is an
# ordinary force-delete, and a bare `(?=\s|$)` rejected it because the `\` sits
# directly against the `D`.
_SHORT_CLUSTER = re.compile(r"(?<!\S)-([A-Za-z]+)(?=[\s\\)`]|$)")

# `git branch`'s complete short-option alphabet, from `git branch -h`:
# -a -c -C -d -D -f -i -l -m -M -q -r -t -u -v. A dash-prefixed token whose
# letters are not all drawn from this set is NOT an option cluster — it is an
# option's ARGUMENT that merely looks like one, and treating it as flags is a
# false-positive machine. Measured, each verified against real git as harmless:
# `git branch -uDev feat` (the `-u` value supplies a capital D), `git branch
# --sort -HEAD` (the sort key does), `git branch -f -tdirect newb main` (the
# `-t` value supplies the `d`). Filtering on the alphabet drops all three and
# loses none of the sixteen genuine force-delete spellings.
_BRANCH_SHORT_OPTS = frozenset("acCdDfilmMqrtuv")
# Long-option prefixes, because git accepts any UNAMBIGUOUS abbreviation.
# `--delete` is the only `--d*` option `git branch` has, so every prefix down to
# `--d` resolves to it. `--force` shares `--fo` with `--format`, so `--forc` is
# the shortest unambiguous one — a looser `--fo[a-z]*` would fire on the
# perfectly ordinary `git branch --format=...`.
# The terminators admit `\` for the same reason `_SHORT_CLUSTER`'s does — a
# backslash continuation abutting the flag is an ordinary multi-line command,
# not a malformed one. All three patterns carry it; fixing only the short-flag
# one left `--delete\`+newline+`--force` silently unmatched.
_DELETE_LONG = re.compile(r"(?:^|\s)--d(?:e(?:l(?:e(?:t(?:e)?)?)?)?)?(?:[\s\\)`]|=|$)")
_FORCE_LONG = re.compile(r"(?:^|\s)--forc(?:e)?(?:[\s\\)`]|=|$)")


def _force_deletes_a_branch(tail: str) -> bool:
    """True when `tail` carries both a delete flag and a force flag.

    Short flags are gathered across every cluster in the tail, so `-df`, `-d -f`
    and `-f -d` are one case rather than three. A branch NAME cannot contribute:
    the cluster must be `-`-prefixed, which is also why a branch called
    `featureD` does not read as `-D`.
    """
    clusters = "".join(
        c for c in _SHORT_CLUSTER.findall(tail) if set(c) <= _BRANCH_SHORT_OPTS
    )
    if "D" in clusters:
        return True  # the documented shortcut, carrying both halves at once
    deleting = "d" in clusters or _DELETE_LONG.search(tail) is not None
    forcing = "f" in clusters or _FORCE_LONG.search(tail) is not None
    return deleting and forcing

# --- Working-tree discards ---------------------------------------------------
# `git checkout <path>`, `git restore <path>` and `git clean` throw away
# uncommitted work with no reflog entry. Unlike every rule above, these are
# CONDITIONAL: the shape alone is not enough, because the same commands are
# ordinary and frequent on a clean path, where they destroy nothing. See the
# module docstring's detection-scope bullet for the incident and for why the
# condition is what makes the rule affordable.
_CHECKOUT = GitInvocation(r"checkout\b" + _TAIL)
_SWITCH = GitInvocation(r"switch\b" + _TAIL)
_RESTORE = GitInvocation(r"restore\b" + _TAIL)
_CLEAN = GitInvocation(r"clean\b" + _TAIL)

# A FORCED checkout or switch needs no path operand to destroy the tree, and
# this is where the first cut of this rule was wrong. `git checkout -f`
# overwrites every modified tracked file; `git checkout -f <branch>` and
# `git switch -f <branch>` do the same and then move HEAD. Both were silent:
# the bare form yields no operands so nothing was probed, and the branch form
# yields the branch name, which matches no path and reports no work.
#
# The exclusion that let this through was stated as "git already refuses a
# checkout that would clobber uncommitted changes" — true of a BARE checkout
# and false of a forced one, since `-f` exists precisely to override that
# refusal. Exactly the relation `--force` has to `git branch -d` above, missed
# one command over. When force is present the operands are irrelevant and the
# probe asks about the whole tree.
#
# `git switch` is matched only in this forced form. Bare `git switch <branch>`
# refuses on conflict the same way bare `checkout` does, and `git switch` takes
# no pathspec at all — `restore` is its path-facing counterpart and is matched
# separately.
# git accepts any UNAMBIGUOUS long-option abbreviation, and each command's
# abbreviation floor differs because it depends on that command's own option
# set. `_FORCE_LONG`/`_DELETE_LONG` above already carry this reasoning for
# `git branch`; not carrying it across to the new commands left
# `git checkout --f`, `git switch --di other` and `git clean --f` silent while
# each really discarded the tree.
#
# The floors, each read off the command's own `--` options:
#   checkout — `--force` is its only `--f*`, so `--f` resolves.
#   clean    — likewise `--f`.
#   switch   — `--force` and `--force-create` share every prefix of `--force`,
#              so git REFUSES `--f`/`--fo`/`--forc` as ambiguous (verified) and
#              only the full `--force` is spellable. `--discard-changes` shares
#              `--d` with `--detach`, so `--di` is its shortest resolving form.
_FORCE_DISCARD = re.compile(
    r"(?:^|\s)(?:"
    + "--" + _abbrev("force", 1) + _END
    + r"|--" + _abbrev("discard-changes", 2) + _END
    + r"|-[A-Za-z]*f[A-Za-z]*(?:[\s\\)`]|$)"
    + r")"
)

# `git restore --staged <path>` rewrites the INDEX from HEAD and never touches
# the working tree, so it destroys nothing a probe of the working tree can see
# — it is the canonical "unstage this" command, and prompting on it would be
# the routine prompt this whole rule is shaped to avoid. `--staged --worktree`
# together DO touch the tree, so only the staged-without-worktree form is
# skipped. `-S`/`-W` are the short spellings, bundleable as `-SW`.
#
# Both take abbreviations, and the WORKTREE one is the dangerous half to miss:
# it appears under a NOT, so failing to match it drops the invocation entirely.
# `git restore --staged --w <path>` resets index AND worktree, and was silent.
# `--worktree` is restore's only `--w*` option and `--staged` its only `--st*`
# (`--source` shares only `--s`), so those are the floors.
_RESTORE_STAGED = re.compile(
    r"(?:^|\s)(?:--" + _abbrev("staged", 2) + _END
    + r"|-[A-Za-z]*S[A-Za-z]*(?:[\s\\)`]|$))"
)
_RESTORE_WORKTREE = re.compile(
    r"(?:^|\s)(?:--" + _abbrev("worktree", 1) + _END
    + r"|-[A-Za-z]*W[A-Za-z]*(?:[\s\\)`]|$))"
)

# Options whose VALUE is the next token, so that value is not a path operand.
# Narrow on purpose — an over-included token costs almost nothing, because the
# probe reports no work for a name that is not a file. The ones listed are the
# ones whose values plausibly collide with a real filename: `git checkout -b
# feature` in a tree holding a dirty file called `feature` would otherwise
# prompt. Long forms taking `=` need no entry; the `=` keeps them one token.
_VALUE_OPTS = frozenset(
    {"-b", "-B", "-t", "--track", "--orphan", "-s", "--source", "-e", "--exclude",
     "--conflict", "--pathspec-from-file"}
)


def _operands(scanned_tail: str, raw_tail: str) -> list[str]:
    """The path operands in a `checkout`/`restore`/`clean` tail.

    Tokenised against the QUOTE-STRIPPED tail so a quoted path containing
    spaces stays one token, then re-sliced out of the RAW tail at the same
    offsets to recover the real text — the round trip `strip_quoted_spans`'
    length-preserving placeholder exists for. Splitting the raw tail directly
    would tear `"my file.txt"` into two operands, neither of which is a path.

    After a `--` separator every remaining token is a path by definition, and
    that form is preferred when present. Without one, `git checkout main` and
    `git checkout main.py` are genuinely ambiguous — git resolves it by looking,
    and so does this: both are returned as candidates, and the probe reports no
    work for a branch name, so the ambiguity costs a pathspec argument rather
    than a parser. A trailing backslash is stripped because a line continuation
    abuts the token it follows, exactly as it does for `_SHORT_CLUSTER`.
    """
    tokens = [
        (scanned_tail[m.start():m.end()].rstrip("\\"),
         raw_tail[m.start():m.end()].rstrip("\\").strip("'\"`"))
        for m in re.finditer(r"\S+", scanned_tail)
    ]
    flags = [flag for flag, _ in tokens]
    if "--" in flags:
        return [real for _, real in tokens[flags.index("--") + 1:] if real]
    return _unseparated_operands(tokens)


def _names_a_tree_ish(scanned_tail: str) -> bool:
    """True when a `checkout` tail names a source tree BEFORE its `--`.

    `git checkout HEAD -- <path>` and `git checkout main -- <path>` write the
    named tree into the INDEX as well as the working tree, so they destroy
    staged work that a bare `git checkout -- <path>` cannot touch. Only the
    explicit `--` form is detected, because it is the only unambiguous one:
    without a separator, `git checkout HEAD f.txt` and `git checkout a.txt
    b.txt` are the same shape, and guessing between them is how this file
    acquired its false positives. Named in the module docstring's known misses.
    """
    tokens = [t for t in re.findall(r"\S+", scanned_tail)]
    if "--" not in tokens:
        return False
    before = tokens[: tokens.index("--")]
    skip_next = False
    for flag in before:
        if skip_next:
            skip_next = False
            continue
        if flag.startswith("-"):
            skip_next = flag in _VALUE_OPTS
            continue
        return True
    return False


def _unseparated_operands(tokens: list[tuple[str, str]]) -> list[str]:
    """Operands from a tail with no `--` separator."""
    operands: list[str] = []
    skip_next = False
    for flag, real in tokens:
        if skip_next:
            skip_next = False
            continue
        if flag.startswith("-"):
            skip_next = flag in _VALUE_OPTS
            continue
        if real:
            operands.append(real)
    return operands


# `git clean` refuses to delete anything without a force flag, and deletes
# nothing under `-n`/`--dry-run`, so neither shape is worth a prompt. Both
# accept a bundled cluster (`-fdx`, `-nd`), which is how they are usually
# typed.
# `--f` resolves for clean: `--force` is its only `--f*` option. See
# `_FORCE_DISCARD` for why each command's floor has to be read off its own
# option set rather than assumed.
_CLEAN_FORCE = re.compile(
    r"(?:^|\s)(?:--" + _abbrev("force", 1) + _END
    + r"|-[A-Za-z]*f[A-Za-z]*(?:[\s\\)`]|$))"
)
# `--dry-run` is clean's only `--d*` option, so `git clean -f --d` really is a
# dry run and prompting on it is pure noise. `_CLEAN_FORCE` two lines up got the
# abbreviation treatment while its sibling on the same predicate did not.
_CLEAN_DRY_RUN = re.compile(
    r"(?:^|\s)(?:--" + _abbrev("dry-run", 1) + _END
    + r"|-[A-Za-z]*n[A-Za-z]*(?:[\s\\)`]|$))"
)
# `-x` also removes ignored files; `-X` removes ONLY ignored files. Neither has
# a long form. Case matters, so these are two patterns rather than one.
#
# They are load-bearing rather than a refinement: `git status --porcelain` does
# not list an ignored file without `--ignored`, so a tree whose only untracked
# content is gitignored — a `.env`, a local config, a built directory — reported
# nothing and `git clean -fdx` sailed through silently, deleting exactly the
# files nothing recovers. Under `-X` the default `??` predicate is wrong in both
# directions at once: it prompted on untracked files `-X` will not touch, and
# stayed silent on the ignored ones it will.
_CLEAN_ALSO_IGNORED = re.compile(r"(?:^|\s)-[A-Za-z]*x[A-Za-z]*(?:[\s\\)`]|$)")
_CLEAN_IGNORED_ONLY = re.compile(r"(?:^|\s)-[A-Za-z]*X[A-Za-z]*(?:[\s\\)`]|$)")


def _line_kind(line: str) -> str:
    """What a `git status --porcelain` line says is at stake.

    The XY prefix is two columns, and column Y is the WORKING TREE. Reading the
    line as merely "`??` or not" over-prompts in three ordinary shapes, each
    verified against git: `M ` is staged with the worktree already matching the
    index, so `git checkout -- <path>` is a literal no-op; ` D` is deleted in
    the worktree, which a checkout RESTORES rather than destroys; and a
    `git restore --staged` on either never reaches the tree at all (handled by
    `_RESTORE_STAGED`, above). A prompt that fires on those becomes routine,
    which is how a checkpoint stops being read — the failure this whole rule is
    shaped to avoid.
    """
    if line.startswith("??"):
        return "untracked"
    if line.startswith("!!"):
        return "ignored"
    index, worktree = line[0:1], line[1:2]
    # Unmerged. A conflicted path holds resolution work that exists in no commit
    # and no reflog. `UD` in particular has `D` in the worktree column and was
    # classified "safe", so `git checkout -f` on a tree whose only status line
    # was `UD` threw away the resolution silently. A pathed `git checkout --`
    # refuses on an unmerged path, so this over-prompts slightly there — the
    # right side to err on.
    if "U" in (index, worktree) or index + worktree in ("DD", "AA"):
        return "worktree"
    if worktree not in (" ", "D", ""):
        return "worktree"
    # Column X — staged, with the worktree already matching. A PATHED discard
    # cannot reach this (it copies the index over a file that equals it), which
    # is why the first cut called it safe outright. A FORCED checkout can: it
    # moves HEAD and resets both index and worktree, so `M ` reverts and `A `
    # DELETES a file that was never committed anywhere. Measured — `git reset
    # --hard` on the identical tree already prompts, so calling it safe made the
    # two sibling rules disagree about the same state.
    return "index" if index not in (" ", "?", "") else "safe"


# `gh pr merge` — not destructive in the reset/force-push sense, but it is
# outward-facing and effectively irreversible: it publishes to a shared branch,
# can trigger deploys, and `--delete-branch` removes the source.
#
# It is here because AUTHORIZATION is the thing that fails, and a hook cannot
# read authorization. Observed twice in one session: two PRs merged that the
# user had asked to be *built*, not shipped — once by carrying a "merge and
# clean" instruction forward from an earlier, unrelated task. Both had to be
# reverted, one after review found it broken.
#
# So the prompt is unconditional rather than clever. When the merge IS
# authorized it costs a keystroke; when it is not, it is the only thing between
# an assumption and a shared branch. Unlike a rule stated in conversation, it
# survives compaction — which is exactly when the carry-forward mistake happens.
# Tokens between `gh` and `pr merge` are skipped so global options and their
# values match (`gh --repo owner/name pr merge`) — a value can contain `/`, so
# they are matched as generic tokens rather than a `[-\w]` word class, which
# missed exactly that shape.
#
# Separators are `_SEP` — horizontal whitespace, or a backslash line
# continuation — never a bare `\s`. `\s` matches a newline, so the skip walked
# across line breaks into an unrelated command and `gh auth status` + newline +
# `echo pr merge` fired. `_PUSH`/`_RESET` already exclude `\n` for this exact
# reason (see their comment above).
#
# But excluding the newline outright was ALSO wrong, and briefly shipped that
# way: `gh \`+newline+`pr merge` is an ordinary multi-line invocation and became
# a silent bypass. A continuation is a joined line, not a new command, so it is
# a separator; a bare newline is not.
#
# `_SEP` must be used at EVERY separator position, including between `pr` and
# `merge`. A first pass applied it to the `gh`→token and token→token positions
# and left the subcommand pair as `[ \t]`, which moved the identical bypass one
# token to the right — `gh pr \`+newline+`merge` was still silent. Same bug,
# different position, caught only by a review pass that re-probed the fix.
#
# The skip is LAZY with no lookahead. An earlier `(?!pr…)` guard was there to
# stop the skip running past the first `pr`, but laziness does that for free and
# the guard had its own bug: it could not skip a token that merely began with
# `pr`, so `gh --repo pr-tools/x pr merge` — and, after that was narrowed,
# `gh --repo pr pr merge` — were misses. Shortest-match-first handles both.
#
# The optional extension matches `gh.exe` / `gh.cmd`, ordinary spellings on
# this repo's primary platform, which bare `\bgh\s` missed entirely.
#
# `merge(?![\w-])` rather than `merge\b`: `\b` ends at a hyphen, so
# `gh pr merge-queue status` — a real, read-only subcommand — was prompting.
#
# Known misses, stated rather than implied: a shell alias, a case variant
# (`GH pr merge` — PowerShell resolves commands case-insensitively), and the
# REST equivalent `gh api -X PUT repos/o/n/pulls/N/merge`. A regex cannot
# resolve an alias, and the `gh api` surface is too broad to match without
# false-firing on every read-only API call. Named here so the gap is a known
# limitation rather than a surprise.
# `_SEP` is defined once, above, and shared with `_PUSH`/`_RESET`. The
# extension group is case-folded: it exists because Windows is the primary
# platform, and that shell resolves `gh.EXE` as readily as `gh.exe`, so a
# case-sensitive group would have been the same inconsistency one more time.
#
# The escaped dot sits OUTSIDE the case-folding group deliberately. With it
# inside, the source text would contain a letter-colon-backslash run, which the
# conformance guard's Windows-drive-path scanner flags as a hardcoded developer
# path. Same match either way; this spelling avoids the false alarm.
_GH_PR_MERGE = re.compile(
    r"\bgh(?:\.(?i:exe|cmd|bat|com|ps1))?" + _SEP
    + r"(?:[^\s&|;\n]+" + _SEP + r")*?pr" + _SEP + r"merge(?![\w-])"
)


# Named so `main()` can suppress THIS reason alone under `ALLOW_PR_MERGE=1`,
# without touching the force-push, reset and branch-delete checks. The narrow
# variable exists
# because `multi-pr` and `multi-lite` merge as an ordinary loop step of a long
# unattended run — an audit of every mutating command those skills emit found
# the merge prompt was the only NEW thing standing in their way. Silencing it
# with the broad `ALLOW_DESTRUCTIVE_GIT` would have disarmed force-push,
# branch-delete and
# `reset --hard` for the same commands, which is a strictly worse trade.
# An inline `ALLOW_PR_MERGE=1` env-assignment prefix authorizes a merge only when it
# heads that merge's own simple command, where a shell actually treats it as an
# assignment for that command. What may sit between the start of the merge's
# segment and `gh`: the prefix, alone or among other `NAME=value` assignments.
_WS = r"(?:[ \t]|\\\r?\n)"  # a `\`-continued newline is still the same command
_MERGE_AUTH_HEAD = re.compile(
    r"\s*(?:[A-Za-z_]\w*=\S*" + _WS + r"+)*?ALLOW_PR_MERGE=1" + _WS + r"+(?:[A-Za-z_]\w*=\S*" + _WS + r"+)*"
)
_SEGMENT_SEPARATORS = "&|;\n({"


def _segment_start(scanned: str, end: int) -> int:
    """Index where the simple command containing position `end` begins: after the last
    separator before it, where a backslash-continued newline is not a separator."""
    for i in range(end - 1, -1, -1):
        if scanned[i] in _SEGMENT_SEPARATORS:
            continued = scanned[i] == "\n" and scanned[:i].rstrip("\r").endswith("\\")
            if not continued:
                return i + 1
    return 0


def _every_merge_is_authorized(scanned: str) -> bool:
    """True when every `gh pr merge` in the quote-stripped command is the command its own
    `ALLOW_PR_MERGE=1` prefix heads.

    The prefix authorizes the one simple command it is part of. Matching it anywhere let a
    later, unrelated segment authorize an earlier merge (`gh pr merge 27; ALLOW_PR_MERGE=1
    true`), and let one prefixed merge carry an unprefixed second one.
    """
    merges = list(_GH_PR_MERGE.finditer(scanned))
    if not merges:
        return False
    for m in merges:
        start = _segment_start(scanned, m.start())
        if not _MERGE_AUTH_HEAD.fullmatch(scanned[start:m.start()]):
            return False
    return True

MERGE_REASON = (
    "a PR merge, which publishes to a shared branch and cannot be cleanly "
    "undone — confirm the user actually asked for this MERGE, not just for "
    "the work to be built"
)


DISCARD_REASON = (
    "a discard of uncommitted work — `git checkout <path>` and `git restore "
    "<path>` restore from the index, NOT from your last edit, so a file changed "
    "since it was last staged loses those changes with no reflog entry; the "
    "path(s) named here hold such changes right now"
)

# A forced checkout or switch names no path and is not a `<path>` form, so
# `DISCARD_REASON`'s wording — which asserts something about "the path(s) named
# here" — is false of it. That is the same defect `UNCHECKED_REASON` was split
# out to fix, left in the branch it was diagnosed from.
WHOLE_TREE_REASON = (
    "a FORCED checkout or switch (`-f` / `--discard-changes`), which overrides "
    "git's own refusal to clobber uncommitted changes — it resets the whole "
    "working tree and index, and overwrites untracked files colliding with the "
    "target branch; this tree holds work that would not survive it"
)

UNCHECKED_REASON = (
    "a command that can discard uncommitted work, whose safety check COULD NOT "
    "BE RUN — the hook is asking because it was unable to look, not because it "
    "found work at stake"
)

CLEAN_REASON = (
    "`git clean`, which deletes untracked files outright — the path(s) named "
    "here hold untracked files right now, and nothing recovers them"
)


STASH_REASON = (
    "`git stash` while a merge, cherry-pick or revert is in progress — the "
    "stash resets the tree and drops MERGE_HEAD / CHERRY_PICK_HEAD / REVERT_HEAD, "
    "so the next commit silently loses one side of the operation (no conflict "
    "markers, tests can stay green). To look at another version of a file use "
    "`git show <ref>:<path>`, or do the experiment in a scratch worktree"
)

STASH_UNCHECKED_REASON = (
    "`git stash` whose safety check COULD NOT BE RUN — the hook could not tell "
    "whether a merge, cherry-pick or revert is in progress, and a stash during "
    "one drops MERGE_HEAD and loses a side of it"
)

# A deliberate skip, not a failure: probing every directory would break the
# stated `HOOK_WORST_CASE_SECONDS`, so the hook asks instead. Saying "COULD NOT
# BE RUN" here reported a fault that never happened.
STASH_MULTI_DIR_REASON = (
    "`git stash` in more than one directory, which this hook did not probe "
    "(it checks one directory per command) — check each directory for a merge, "
    "cherry-pick or revert in progress, since a stash during one drops "
    "MERGE_HEAD and loses a side of it"
)


def _stash_dirs(scanned: str, command: str, cwd: str) -> list[str | None]:
    """Distinct directories a saving `git stash` in `command` would run in.

    Each `git -C <dir>` moves the directory, relative to the one before it, the
    way git applies repeated `-C`. `None` stands for a stash whose repository
    this hook cannot name: `--git-dir`/`--work-tree` or `GIT_DIR=`. (A `-C`
    value the shell expands names no real directory, which the probe reports as
    "could not check" rather than as a refusal.)
    """
    dirs: list[str | None] = []
    for m in _STASH.finditer(scanned):
        if _STASH_NON_SAVING.match(m.group(2)):
            continue
        d = _invocation_dir(command[m.start(1):m.end(1)], scanned, cwd)
        if d not in dirs:
            dirs.append(d)
    return dirs


def _invocation_dir(opts: str, scanned: str, cwd: str) -> str | None:
    """The directory one git invocation runs in, from its raw global options.

    Each `-C <dir>` moves it, relative to the one before, the way git applies
    repeated `-C`. `None` when this hook cannot name the repository:
    `--git-dir`/`--work-tree` or a `GIT_DIR=`/`GIT_WORK_TREE=` anywhere in the
    command.
    """
    if re.search(r"--(?:git-dir|work-tree)\b", opts) or _GIT_ENV_REPO.search(scanned):
        return None
    d = cwd
    for c in _DASH_C.finditer(opts):
        d = os.path.normpath(os.path.join(d, c.group(1).strip("'\"")))
    return d


# --- History rewrites and branch changes git does not refuse -------------------
# A rebase (or a rebasing `git pull`) of commits already on a remote-tracking
# branch, a `switch -C`/`checkout -B` over a branch whose commits are nowhere
# else, and a merging switch (`-m`, `--merge`, `--conflict`) over staged work.
# Each is CONDITIONAL, like the discards above: the same commands are routine
# when nothing is at stake, so each probes first.
#
# What these protect is recoverable with effort (the reflog keeps the old tips,
# the object store keeps a staged blob until `gc`), unlike the uncommitted work
# above, which nothing keeps. So they fail OPEN: a probe that cannot run, a
# refusal, a repository this hook cannot name and an exception are all silence.
# Asking on every rebase whenever git is slow would make the prompt routine. A
# probe that did not run says so on stderr, so a missed check is visible.
#
# NO TEXT FROM THE COMMAND REACHES GIT AS AN ARGUMENT, except as the value of an
# `=` option or behind `--end-of-options`. A quoted `"--output=<file>"` operand
# once reached `git rev-list` bare, and rev-list opened that file for writing:
# the hook truncated a file before the user was asked anything. Every revision
# is first resolved to a commit SHA by `rev-parse --end-of-options`, only SHAs
# reach the other probes, and an operand starting with `-` is silence. The
# probes, and the deadline they share, are in `_destructive_git_probes.py`.
_REBASE = GitInvocation(r"rebase\b" + _TAIL, capture_opts=True)
_PULL = GitInvocation(r"pull\b" + _TAIL, capture_opts=True)
# Group 1 the global options, 2 the subcommand word, 3 the tail.
_BRANCH_CHANGE = GitInvocation(r"(checkout|switch)\b" + _TAIL, capture_opts=True)

# Every pattern below is FULL-matched against one word's unquoted text, with any
# `=value` cut off first, so `"-i"` and `-i` read alike.
#
# `--continue`, `--abort`, `--skip`, `--quit`, `--edit-todo` and
# `--show-current-patch` act on a rebase already under way and rewrite nothing
# new. Floors read off `git rebase -h` (2.43) and checked against real git:
# `--co` is ambiguous with `--committer-date-is-author-date`, `--qui` with
# `--quiet`; `--ab`, `--sk`, `--ed` and `--sh` resolve.
_REBASE_ACTION = re.compile("--(?:" + "|".join((
    _abbrev("continue", 3), _abbrev("abort", 2), _abbrev("skip", 2), "quit",
    _abbrev("edit-todo", 2), _abbrev("show-current-patch", 2),
)) + ")")
_REBASE_ROOT = re.compile("--" + _abbrev("root", 2))
# The up-to-date shortcut (an upstream that is already an ancestor of the branch
# replays nothing) holds only when EVERY option is one of these, each measured on
# git 2.43 against an up-to-date branch whose author and committer dates differ:
# none of them moved HEAD. Any other option turns the shortcut off, so an option
# nobody measured asks instead of passing (`--whitespace=fix`, `--ignore-date`
# and `--committer-date-is-author-date` all replayed it; a list of replaying
# options missed those). Full spellings only: an abbreviation asks.
_REBASE_NO_REPLAY_LONG = frozenset({
    "--rebase-merges", "--no-rebase-merges", "--keep-base", "--no-keep-base",
    "--autosquash", "--no-autosquash", "--quiet", "--verbose", "--stat", "--no-stat",
    "--update-refs", "--no-update-refs", "--strategy", "--strategy-option",
    "--autostash", "--no-autostash", "--verify", "--no-verify", "--ff",
    "--fork-point", "--no-fork-point", "--rerere-autoupdate", "--no-rerere-autoupdate",
    "--merge",
})
_REBASE_NO_REPLAY_SHORT = "rqvnsXm"
# Long options whose value is the NEXT word, so that word is not an operand.
# `--strategy` has no abbreviation: every prefix is shared with
# `--strategy-option`, whose own floor is `--strategy-`.
_REBASE_VALUE_LONG = re.compile("--(?:" + "|".join((
    _abbrev("onto", 1), _abbrev("exec", 2), "strategy",
    _abbrev("strategy-option", 9), _abbrev("whitespace", 1), _abbrev("empty", 2),
)) + ")")
# Short options: these take a required value (attached, or the next word) ...
_REBASE_VALUE_SHORT = "CxsX"
# ... and these an optional one, attached only (`-Skey`, `-rcousins`).
_REBASE_OPTIONAL_SHORT = "Sr"

# `git pull`: `-r`/`--rebase[=<mode>]` rebases, `--no-rebase` merges, and with
# neither the `branch.<name>.rebase` / `pull.rebase` settings decide. Floors:
# `--re` is ambiguous with `--recurse-submodules` and `--refmap`.
_PULL_REBASE = re.compile("--" + _abbrev("rebase", 3))
_PULL_NO_REBASE = re.compile("--" + _abbrev("no-rebase", 6))
_PULL_VALUE_LONG = frozenset({
    "--strategy", "--strategy-option", "--depth", "--deepen", "--shallow-since",
    "--shallow-exclude", "--server-option", "--upload-pack", "--refmap",
    "--negotiation-tip",
})
_PULL_VALUE_SHORT = "sXo"
_PULL_OPTIONAL_SHORT = "rjS"
# The values git reads as "do not rebase" for `--rebase=` and the settings, and as
# false for `rebase.forkPoint`. An empty setting is false as well.
_NOT_REBASE = frozenset({"false", "no", "off", "0"})
# `git -c <key>=<value>`, which outranks the repository's own config.
_DASH_LOWER_C = re.compile(r"(?<![\w-])-c" + _SEP + r"""((?:"[^"]*"|'[^']*'|[^\s"'])+)""")

# `-C <name>`/`--force-create <name>` (switch only) and `-B <name>` (checkout)
# reset an existing branch to the start point. `--force-` is the floor: `--forc`
# is ambiguous with `--force`, measured.
_FORCE_CREATE_LONG = re.compile("--" + _abbrev("force-create", 6))
_BRANCH_VALUE_LONG = frozenset({"--create", "--orphan", "--conflict", "--pathspec-from-file"})
# `--conflict=<style>` implies `--merge`. Floors: `--m` resolves for both
# commands; `--c` resolves for checkout and is ambiguous for switch (git refuses
# it there, so matching it costs nothing).
_MERGE_SWITCH_LONG = re.compile("--(?:" + _abbrev("merge", 1) + "|" + _abbrev("conflict", 1) + ")")
_REDIRECT = re.compile(r"\d*(?:>>?|<<?|>&|<&|>\|)")

REBASE_REASON = (
    "a rebase (`git rebase`, or `git pull` with rebase) that rewrites commits "
    "already on a remote-tracking branch — publishing the result takes a "
    "force-push, and anyone who based work on the old commits is left holding "
    "duplicates (a rebase of local-only commits does not ask)"
)
BRANCH_RESET_REASON = (
    "`git switch -C` / `git checkout -B` over an existing branch holding commits "
    "that are on no other branch, tag, remote-tracking branch or the start point — "
    "the reset orphans them, recoverable only from the reflog and only within its "
    "expiry window"
)
MERGE_SWITCH_REASON = (
    "a merging branch change (`-m`, `--merge` or `--conflict`) while changes are "
    "staged — git documents that staged changes may be lost this way (recent git "
    "refuses instead); commit or stash them first"
)


def _words(scanned_tail: str, raw_tail: str) -> list[str]:
    """A tail's shell words, unquoted, minus what is not an argument: a `#`
    comment ends the list, and a redirection drops out with its target
    (`2> log`, `>out`). Both are recognised on the quote-stripped text, so a
    quoted `"#x"` or `">"` stays a word."""
    words: list[str] = []
    target = False
    for m in re.finditer(r"\S+", scanned_tail):
        flag = scanned_tail[m.start():m.end()]
        real = _unquote(raw_tail[m.start():m.end()].rstrip("\\)`"))
        if not real:
            continue
        if target:
            target = False
        elif flag.startswith("#"):
            break
        elif (redirect := _REDIRECT.match(flag)) is not None:
            target = redirect.end() == len(flag)
        else:
            words.append(real)
    return words


def _config_overrides(opts: str) -> dict[str, str]:
    """`git -c <key>=<value>` settings from an invocation's raw global options,
    keyed as `_config_key` spells them. A bare `-c <key>` is true."""
    found: dict[str, str] = {}
    for m in _DASH_LOWER_C.finditer(opts):
        key, eq, value = _unquote(m.group(1)).partition("=")
        found[_config_key(key)] = value if eq else "true"
    return found


def _config_key(key: str) -> str:
    """A config key as git compares it: section and name ignore case, a
    subsection (`branch.<name>.rebase`) does not."""
    parts = key.split(".")
    return ".".join([parts[0].lower(), *parts[1:-1], parts[-1].lower()])


def _cluster(letters: str, required: str, optional: str) -> bool:
    """True when a short-option cluster ends in an option whose value is the
    next word (`-ix`), not attached (`-xmake`) or optional (`-ri`)."""
    for i, ch in enumerate(letters):
        if ch in optional:
            return False
        if ch in required:
            return i == len(letters) - 1
    return False


def _rebase_range(words: list[str]) -> tuple[str, str | None, bool, bool | None] | None:
    """`(branch, upstream, rewrites, fork_point)` for the commits a rebase
    rewrites, `upstream..branch`; `upstream` is None under `--root`, where it is
    all of `branch`. `rewrites` is True unless every option is in the measured
    no-replay set. `fork_point` is the explicit `--[no-]fork-point`, else False
    with an upstream operand and None (the settings decide) without one, which
    is git's own default. None for an action on a rebase already under way.

    `git rebase [<upstream> [<branch>]]`: the upstream defaults to the current
    branch's `@{upstream}` and the branch to HEAD; `--onto` moves where the
    commits land, not which ones are rewritten. `-` is git's `@{-1}`.
    """
    operands: list[str] = []
    root = rewrites = skip = False
    fork_point: bool | None = None
    for word in words:
        key = word.partition("=")[0]
        if skip:
            skip = False
        elif word.startswith("--"):
            if _REBASE_ACTION.fullmatch(key):
                return None
            root = root or _REBASE_ROOT.fullmatch(key) is not None
            rewrites = rewrites or key not in _REBASE_NO_REPLAY_LONG
            fork_point = {"--fork-point": True, "--no-fork-point": False}.get(key, fork_point)
            skip = key == word and _REBASE_VALUE_LONG.fullmatch(key) is not None
        elif word.startswith("-") and word != "-":
            letters = word[1:]
            for ch in letters:
                rewrites = rewrites or ch not in _REBASE_NO_REPLAY_SHORT
                if ch in _REBASE_VALUE_SHORT + _REBASE_OPTIONAL_SHORT:
                    break
            skip = _cluster(letters, _REBASE_VALUE_SHORT, _REBASE_OPTIONAL_SHORT)
        else:
            operands.append("@{-1}" if word == "-" else word)
    if root:
        return (operands[0] if operands else "HEAD"), None, True, False
    if fork_point is None and operands:
        fork_point = False
    return (
        operands[1] if len(operands) > 1 else "HEAD",
        operands[0] if operands else "@{upstream}",
        rewrites,
        fork_point,
    )


def _pull_rebase(words: list[str]) -> tuple[bool | None, list[str]]:
    """`(rebase, operands)` of a `git pull`: `rebase` True or False when the
    command says, None when the settings decide."""
    rebase: bool | None = None
    operands: list[str] = []
    skip = False
    for word in words:
        key, eq, value = word.partition("=")
        if skip:
            skip = False
        elif word.startswith("--"):
            if _PULL_REBASE.fullmatch(key):
                rebase = value.lower() not in _NOT_REBASE if eq else True
            elif _PULL_NO_REBASE.fullmatch(key):
                rebase = False
            else:
                skip = not eq and key in _PULL_VALUE_LONG
        elif word.startswith("-"):
            letters = word[1:]
            r = letters.find("r")
            if r >= 0 and not any(ch in _PULL_VALUE_SHORT + _PULL_OPTIONAL_SHORT for ch in letters[:r]):
                rebase = letters[r + 1:].lower() not in _NOT_REBASE
            skip = _cluster(letters, _PULL_VALUE_SHORT, _PULL_OPTIONAL_SHORT)
        else:
            operands.append(word)
    return rebase, operands


def _pull_upstream(operands: list[str]) -> str | None:
    """What a rebasing pull rebases onto, as the refs stand BEFORE its fetch:
    `<remote>/<branch>` for `git pull <remote> <branch>`, else `@{upstream}`.
    None for more than one branch, which git refuses to rebase onto."""
    if len(operands) > 2:
        return None
    if len(operands) < 2:
        return "@{upstream}"
    branch = operands[1].lstrip("+").partition(":")[0]
    if operands[0] == ".":
        # `.` is this repository: the pull rebases onto the local branch, the
        # same rewrite as `git rebase <branch>`, so it is probed the same way.
        return branch
    if branch.startswith("refs/heads/"):
        branch = branch[len("refs/heads/"):]
    return "refs/remotes/" + operands[0] + "/" + branch


def _reset_target(words: list[str], subcommand: str) -> tuple[str, str] | None:
    """`(name, start point)` of a `switch -C`/`checkout -B`, else None.

    A short cluster is read letter by letter: the first value-taking letter owns
    the rest of the cluster or the next word, so `-cC` creates a branch named
    `C` rather than resetting one. The start point is the first operand, HEAD
    when there is none. A name or start point git would reject is passed on as
    it is: resolving it fails the same way, which is silence.
    """
    values = "cC" if subcommand == "switch" else "bB"
    reset = values[1]
    name: str | None = None
    operands: list[str] = []
    i = 0
    while i < len(words):
        word = words[i]
        nxt = words[i + 1] if i + 1 < len(words) else ""
        if word.startswith("--"):
            key, eq, value = word.partition("=")
            if subcommand == "switch" and _FORCE_CREATE_LONG.fullmatch(key):
                name, i = (value, i) if eq else (nxt, i + 1)
            elif word in _BRANCH_VALUE_LONG:
                i += 1
        elif word.startswith("-"):
            for j, ch in enumerate(word[1:]):
                if ch in values:
                    value = word[j + 2:]
                    if not value:
                        value, i = nxt, i + 1
                    if ch == reset:
                        name = value
                    break
        else:
            operands.append(word)
        i += 1
    if not name:
        return None
    return name, (operands[0] if operands else "HEAD")


def _merges_on_switch(words: list[str], subcommand: str) -> bool:
    """True for a branch change with `-m`, `--merge` or `--conflict`. A
    `checkout -m -- <path>` re-creates a conflict in a path instead, which the
    discard check already covers, so the `--` form is left to it."""
    if "--" in words:
        return False
    values = "cC" if subcommand == "switch" else "bB"
    for word in words:
        if word.startswith("--"):
            if _MERGE_SWITCH_LONG.fullmatch(word.partition("=")[0]):
                return True
        elif word.startswith("-"):
            for ch in word[1:]:
                if ch == "m":
                    return True
                if ch in values:
                    break
    return False


