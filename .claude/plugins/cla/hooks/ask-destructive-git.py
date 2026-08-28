#!/usr/bin/env python3
r"""PreToolUse hook: escalate history-destroying git commands to a prompt.

Why ASK rather than BLOCK
-------------------------
`.claude/settings.local.json` allows `Bash(git *)` wholesale, and the launcher
runs `--permission-mode auto`. Between them, the genuinely irreversible git
operations run unattended: a force-push (rewrites a remote branch other people
and other worktrees may have based work on), `reset --hard` (discards
uncommitted work with no reflog entry for what was in the working tree), and a
branch force-delete (destroys a commit reachable from nowhere else).

The `git/pre-push` hook covers pushes that TARGET main/master. It does not
cover a force-push to a feature branch, which is the common shape here —
`/cla:spec-to-pr` and `/cla:multi-lite` both work on feature branches and both
run unattended.

A hard block is the wrong instrument. These commands are legitimate often
enough (fixing up a review branch, resetting a botched worktree) that blocking
would train people to set the override env var permanently, which is strictly
worse than a prompt. `permissionDecision: "ask"` escalates to the user's own
permission prompt instead: one keystroke, and — unlike a rule stated in
conversation — it survives compaction, which is exactly the failure mode that
makes conversational guardrails unreliable on a long unattended run.

An `ask` decision also holds in EVERY permission mode, including the `auto`
this harness launches with. A hook can tighten what the permission rules
permit; it cannot loosen it.

Why not a `deny` rule in settings.json instead
----------------------------------------------
Argument-shaped deny rules are fragile: `Bash(git push --force *)` matches
neither `git push -f` nor `git push origin main --force`. Matching the command
SHAPE (via the shared `GIT_GLOBAL_OPTS` blob, after quote-stripping) closes
both, and puts the rule in the same place as every other git guard here.

Detection scope
---------------
- `git push` carrying `--force`, or any bundled short-option cluster
  containing `f` (`-f`, `-uf`, `-fu`). Bundling is the form a hand-typed push
  most often takes, and matching only the standalone `-f` token missed it.
- `git push` with a `+`-prefixed refspec (`git push origin +feat:feat`), which
  is git's other force syntax and carries no flag at all.
- `git reset` carrying `--hard`.
- `git branch` carrying a DELETE flag and a FORCE flag: `-D`, which
  `git-branch(1)` defines as "Shortcut for `--delete --force`", and equally
  `-d -f`, `-df`, `-fd`, `-d --force`, `--delete -f`, and unambiguous
  abbreviations of the long forms. Same hazard class as `reset --hard`: a
  branch whose commit exists nowhere else loses that commit outright,
  recoverable only from the reflog and only within its expiry window. Added
  after issue #123, where this destroyed a commit holding 45 sections of run
  notes, recovered only via `git reflog` plus `git show <sha>:<path>`.

  Bare `-d` is deliberately NOT matched, and this one IS considered: per
  `git-branch(1)` a delete without force requires the branch to be "fully
  merged in its upstream branch, or in `HEAD` if no upstream was set", so git
  refuses the destructive case itself. Force is what overrides that refusal,
  which is why force is half the predicate rather than `-D` being the whole of
  it. Matching only `-D` — the first cut here — covered 3 of the 8 spellings
  of one act.
- `git checkout <path>`, `git restore <path>` and `git clean` — but ONLY when
  the paths they name actually hold uncommitted work. These three were excluded
  for a long time, on the ground that they are frequent enough in ordinary flow
  that an unconditional prompt would bury the operations above in noise. That
  exclusion said "revisit only with evidence of a real incident", and issue #184
  is that evidence: a `git checkout <file>` run mid-implementation to undo a
  hand-edit restored the file from the index — the PRE-implementation state —
  erasing ~50 lines of uncommitted work, with no reflog entry and nothing to
  recover from. The trap is that `git checkout <file>` READS as "undo my last
  edit" while it means "reset to the index"; those coincide only when the file
  was clean before you touched it, which is exactly the case that does not hold
  mid-implementation, and also when the loss is most expensive.

  The noise objection is answered by a CONDITION rather than by dropping the
  rule, because these commands only destroy something when their paths are
  dirty. `_holds_work` below probes that. On a clean path the command is a
  no-op and the hook stays silent, so ordinary flow is untouched.

  Pathless `git checkout <branch>` stays out of scope: git already refuses it
  when it would clobber uncommitted changes. No branch-versus-path parser
  enforces that — see `_operands`, where the probe resolves the ambiguity for
  free. That argument holds ONLY without force, so `git checkout -f`,
  `git checkout --force <branch>`, `git switch -f` and
  `git switch --discard-changes` are matched and probe the whole tree instead;
  `-f` exists precisely to override the refusal being relied on. See
  `_FORCE_DISCARD`.

  Known misses in this rule, named rather than implied. A path quoted at
  something other than a token boundary (`git checkout -- dir/"f.txt"`) — the
  operand keeps its inner quote and matches nothing, consistent with
  `strip_quoted_spans`' own disclaimer about partial quoting.
  `--pathspec-from-file=<f>`, whose paths live in a file a regex cannot read. A
  `git clean` run from a SUBDIRECTORY with no path operands, where the probe
  asks about the whole repository and so over-prompts on untracked files
  outside the directory clean would touch.
- `gh pr merge`, including behind global options and as `gh.exe`/`gh.cmd`. Not
  destructive in the same sense, but outward-facing and effectively
  irreversible, and the thing that fails there is AUTHORIZATION — which a hook
  cannot read, so the prompt is unconditional. NOT matched (regex cannot reach
  them, and they are named rather than implied): a shell alias, a case variant
  like `GH pr merge`, and the REST form `gh api -X PUT .../pulls/N/merge`.
  See `_GH_PR_MERGE` for the incident that added it.

`--force-with-lease` and `--force-if-includes` are deliberately NOT matched:
they are the guarded forms that refuse to clobber an unseen remote update, and
prompting on them would make the prompt routine — which is how a checkpoint
stops being read. The `(?:\s|=|$)` boundary excludes them for free, since
`--force` there is followed by `-`.

Also out of scope, and worth naming because the reason is NOT "they are safe":
`git branch --force <existing> <start-point>` and `git branch -M`/`-C` over an
existing name. Per `git-branch(1)`, `--force` resets an existing branch to a new
start-point, so if the old tip was reachable from nowhere else it is orphaned —
the same outcome as a force-delete. They are excluded because ref-moving is
frequent in ordinary flow and prompting on it would make the prompt routine,
which is how a checkpoint stops being read. An earlier revision of this hook
excluded them on the false ground that they "move a ref, they do not destroy a
commit"; the exclusion survives, its stated reason does not.

Likewise out of scope: `git push origin --delete <branch>` and
`git push origin :<branch>`, which delete a REMOTE branch. Named here so the
omission reads as a decision rather than an oversight.

Best-effort, not an exhaustive git parser — see `GIT_GLOBAL_OPTS`'s own
docstring for the option shapes it does and does not consume.

Escape hatches:
  - `ALLOW_PR_MERGE=1` — drops ONLY the PR-merge confirmation. This is the one
    to use for a skill that merges as an ordinary step of a long unattended run
    (`multi-pr`, `multi-lite`); force-push, `reset --hard`, `branch -D` and the
    working-tree discards stay checked. Prefer it per-command over exporting it.
  - `ALLOW_DESTRUCTIVE_GIT=1` — drops every check below, for a deliberate
    unattended batch. Environment only: this hook runs before the command's own
    shell exists, so an inline prefix on the command text never reaches this
    process's `os.environ` and silently does nothing. Export it (or set it for
    the whole session) — there is no per-command form, unlike `ALLOW_PR_MERGE`.

`ALLOW_DESTRUCTIVE_GIT`'s scope widened when `gh pr merge` was added, and the
name stopped describing it — it now also silences an AUTHORIZATION checkpoint,
so a value exported weeks ago for a force-push batch would wave through every
PR merge too. `ALLOW_PR_MERGE` exists so that trade never has to be made: an
unattended run that merges declares exactly that, and keeps its force-push,
branch-delete and reset guards, and can be granted per-command rather than
exported for a whole session. The stderr `DISABLED` notice fires on every command either one
suppresses.

Exit codes:
  0 — always. The decision travels as JSON on stdout, never as an exit code:
      exit 2 would be a hard block, which is the behavior this hook exists to
      avoid. Returning 0 with no output is the "nothing to ask about" case.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

# Why this bootstrap is needed: neither the
# dispatcher's in-process load nor pytest puts the hooks dir at sys.path[0] for
# this file, so the `_dispatch_lib` import below is made explicit rather than
# left to depend on how the process happened to start.
_HOOKS_DIR = str(Path(__file__).resolve().parent)
if _HOOKS_DIR not in sys.path:
    sys.path.insert(0, _HOOKS_DIR)

from _dispatch_lib import GIT_CMD as _GIT_CMD  # noqa: E402
from _dispatch_lib import GIT_GLOBAL_OPTS as _G  # noqa: E402
from _dispatch_lib import run_git as _run_git  # noqa: E402
from _dispatch_lib import strip_quoted_spans as _strip_quoted_spans  # noqa: E402

# Horizontal whitespace, or a backslash line continuation. A continuation is a
# JOINED line, not a new command, so it separates tokens; a bare newline ends
# the command and must not. Both rules below and `_GH_PR_MERGE` share this —
# four review rounds each found the same bug one construct over, every time
# because one position used a plain `\s` or excluded the newline outright.
_SEP = r"(?:[ \t]|\\\r?\n)+"

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
_PUSH = re.compile(_GIT_CMD + _SEP + _G + r"push\b" + _TAIL)
_RESET = re.compile(_GIT_CMD + _SEP + _G + r"reset\b" + _TAIL)
_BRANCH = re.compile(_GIT_CMD + _SEP + _G + r"branch\b" + _TAIL)

# Two shapes force a push. The long flag, where `(?:\s|=|$)` is what spares
# `--force-with-lease` / `--force-if-includes` (both are followed by `-`, which
# the boundary rejects); and a bundled short cluster containing `f`. The
# `-[A-Za-z]*f[A-Za-z]*` arm cannot reach into `--force-with-lease`, because the
# character after the leading `-` there is another `-`, not a letter.
_FORCE_FLAG = re.compile(
    r"(?:^|\s)(?:--force(?:\s|=|$)|-[A-Za-z]*f[A-Za-z]*(?:\s|$))"
)
# `git push origin +feat:feat` — force expressed in the refspec, no flag at all.
_FORCE_REFSPEC = re.compile(r"(?:^|\s)\+\S+")
_HARD_FLAG = re.compile(r"(?:^|\s)--hard(?:\s|=|$)")

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
_SHORT_CLUSTER = re.compile(r"(?<!\S)-([A-Za-z]+)(?=[\s\\]|$)")

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
_DELETE_LONG = re.compile(r"(?:^|\s)--d(?:e(?:l(?:e(?:t(?:e)?)?)?)?)?(?:[\s\\]|=|$)")
_FORCE_LONG = re.compile(r"(?:^|\s)--forc(?:e)?(?:[\s\\]|=|$)")


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
_CHECKOUT = re.compile(_GIT_CMD + _SEP + _G + r"checkout\b" + _TAIL)
_SWITCH = re.compile(_GIT_CMD + _SEP + _G + r"switch\b" + _TAIL)
_RESTORE = re.compile(_GIT_CMD + _SEP + _G + r"restore\b" + _TAIL)
_CLEAN = re.compile(_GIT_CMD + _SEP + _G + r"clean\b" + _TAIL)

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
_FORCE_DISCARD = re.compile(
    r"(?:^|\s)(?:--force(?:[\s\\]|=|$)|--discard-changes(?:[\s\\]|=|$)"
    r"|-[A-Za-z]*f[A-Za-z]*(?:[\s\\]|$))"
)

# `git restore --staged <path>` rewrites the INDEX from HEAD and never touches
# the working tree, so it destroys nothing a probe of the working tree can see
# — it is the canonical "unstage this" command, and prompting on it would be
# the routine prompt this whole rule is shaped to avoid. `--staged --worktree`
# together DO touch the tree, so only the staged-without-worktree form is
# skipped. `-S`/`-W` are the short spellings, bundleable as `-SW`.
_RESTORE_STAGED = re.compile(
    r"(?:^|\s)(?:--staged(?:[\s\\]|=|$)|-[A-Za-z]*S[A-Za-z]*(?:[\s\\]|$))"
)
_RESTORE_WORKTREE = re.compile(
    r"(?:^|\s)(?:--worktree(?:[\s\\]|=|$)|-[A-Za-z]*W[A-Za-z]*(?:[\s\\]|$))"
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
_CLEAN_FORCE = re.compile(
    r"(?:^|\s)(?:--force(?:[\s\\]|=|$)|-[A-Za-z]*f[A-Za-z]*(?:[\s\\]|$))"
)
_CLEAN_DRY_RUN = re.compile(
    r"(?:^|\s)(?:--dry-run(?:[\s\\]|=|$)|-[A-Za-z]*n[A-Za-z]*(?:[\s\\]|$))"
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
_CLEAN_ALSO_IGNORED = re.compile(r"(?:^|\s)-[A-Za-z]*x[A-Za-z]*(?:[\s\\]|$)")
_CLEAN_IGNORED_ONLY = re.compile(r"(?:^|\s)-[A-Za-z]*X[A-Za-z]*(?:[\s\\]|$)")


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
    return "safe" if line[1:2] in (" ", "D", "") else "worktree"


def _status_lines(cwd: str, paths: list[str], ignored: bool):
    """Porcelain lines for `paths`, or a sentinel saying why there are none.

    Tri-state on purpose, because the two ways of getting no answer must not be
    treated alike:

    - `None` — the probe could NOT RUN: no git on PATH, or a git that hung past
      `GIT_TIMEOUT_SECONDS`. The check did not happen, and a guard that allows
      because it failed to look is indistinguishable from one that looked and
      approved, which is the worst outcome this layer has.
    - `False` — the probe ran and git REFUSED (non-zero): a pathspec outside the
      repository, an unknown pathspec magic, not a repository at all.

    An empty `paths` asks about the whole tree.

    (An earlier revision of this docstring named "a wedged git holding an index
    lock" as a `None` trigger. Measured: with `.git/index.lock` present,
    `git status --porcelain` returns 0 and correct output — it takes the lock
    non-fatally — so a held lock produces neither sentinel. The claim was
    reasoned rather than run, which is the failure CLAUDE.md's check 3 names.)
    """
    args = ["status", "--porcelain"] + (["--ignored"] if ignored else [])
    if paths:
        args += ["--", *paths]
    result = _run_git(cwd, args)
    if result is None:
        return None
    if result.returncode != 0:
        return False
    return [line for line in result.stdout.splitlines() if line.strip()]


def _holds_work(cwd, paths, wanted, ignored, whole_tree) -> bool:
    """True when the matched commands would destroy something of kind `wanted`.

    `whole_tree` is a zero-argument callable returning the pathless probe's
    lines, memoised by the caller so it costs at most one extra subprocess per
    hook run however many times this is asked.

    A REFUSAL is silence only when a single path was probed — there, "git is
    about to reject the real command the same way" is exactly true. It is NOT
    true of a batch: this hook merges the operands of every matching invocation
    into one probe to keep the subprocess count at two, and git rejects the
    whole call for one bad pathspec. So

        git checkout -- ../outside && git checkout -- tracked.txt

    refused the merged probe, returned silence, and the shell then ran the
    second command and destroyed `tracked.txt`. A refused BATCH therefore falls
    back to the whole tree rather than to silence — over-prompting on a command
    that half-fails, which is the right side to err on.
    """
    lines = _status_lines(cwd, paths, ignored)
    if lines is None:
        return True
    if lines is False:
        if len(paths) <= 1:
            return False
        lines = whole_tree()
        if lines is None:
            return True
        if lines is False:
            return False
    return any(_line_kind(line) in wanted for line in lines)


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
# An inline `ALLOW_PR_MERGE=1` env-assignment prefix, at the start of the whole
# command or of a segment after a shell separator. Anchored so it cannot be
# satisfied by the string appearing mid-command (inside an echoed message, say)
# — it has to sit where a shell would actually treat it as an assignment.
_ALLOW_MERGE_PREFIX = re.compile(r"(?:^|[&|;]\s*)ALLOW_PR_MERGE=1[ \t]")

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

CLEAN_REASON = (
    "`git clean`, which deletes untracked files outright — the path(s) named "
    "here hold untracked files right now, and nothing recovers them"
)


def _reasons(command: str, cwd: str) -> list[str]:
    """Every destructive shape present in `command`, as human-readable causes.

    `cwd` is where the command is about to run, and is the working directory
    the working-tree probes are resolved against. Every other check here is
    pure text inspection; those two are the only reason this function needs a
    directory at all.
    """
    scanned = _strip_quoted_spans(command)
    found: list[str] = []
    if any(
        _FORCE_FLAG.search(m.group(1)) or _FORCE_REFSPEC.search(m.group(1))
        for m in _PUSH.finditer(scanned)
    ):
        found.append(
            "a force-push, which rewrites a remote branch other worktrees or "
            "collaborators may already have based work on"
        )
    if any(_HARD_FLAG.search(m.group(1)) for m in _RESET.finditer(scanned)):
        found.append(
            "`git reset --hard`, which discards uncommitted working-tree "
            "changes with no reflog entry to recover them from"
        )
    if any(_force_deletes_a_branch(m.group(1)) for m in _BRANCH.finditer(scanned)):
        found.append(
            "a force-delete of a branch (`git branch -D`, or `-d` with "
            "`--force`) — if its commit exists nowhere else it is destroyed, "
            "recoverable only from the reflog and only within its expiry window"
        )
    # Operands are collected across EVERY matching invocation in the command and
    # asked in one `git status` each, so a `&&` chain of six checkouts is two
    # subprocesses, not twelve. Three is the ceiling: those two plus the shared
    # whole-tree fallback below, which is memoised so a batch refusal on both
    # halves still costs one. That is what
    # `HOOK_WORST_CASE_SECONDS["ask-destructive-git.py"]` states; a
    # per-invocation probe would make that entry a fiction.
    tree_cache: list = []

    def whole_tree():
        if not tree_cache:
            # `--ignored` unconditionally, so one cached answer serves the
            # discard check and a `git clean -x` alike.
            tree_cache.append(_status_lines(cwd, [], ignored=True))
        return tree_cache[0]

    # Everything below this point parses operands and leaves the process. It is
    # wrapped because `main()` calls `_reasons()` once and the dispatcher
    # DISCARDS an errored hook's stdout entirely — so an exception raised here,
    # after the four text-only reasons are already in `found`, would silently
    # un-prompt a force-push. Failing to check is the "could not run" case, and
    # that case asks.
    try:
        discard_paths: list[str] = []
        discard_whole_tree = False
        for pattern in (_CHECKOUT, _SWITCH, _RESTORE):
            for m in pattern.finditer(scanned):
                tail = m.group(1)
                if pattern is _RESTORE:
                    if _RESTORE_STAGED.search(tail) and not _RESTORE_WORKTREE.search(tail):
                        continue
                elif _FORCE_DISCARD.search(tail):
                    # Force overrides git's own refusal, so the operands say
                    # nothing about the blast radius — the whole tree is at risk.
                    discard_whole_tree = True
                    continue
                discard_paths += _operands(tail, command[m.start(1):m.end(1)])
        if discard_whole_tree or discard_paths:
            if _holds_work(
                cwd,
                [] if discard_whole_tree else discard_paths,
                {"worktree"},
                False,
                whole_tree,
            ):
                found.append(DISCARD_REASON)

        clean_paths: list[str] = []
        clean_wanted: set[str] = set()
        clean_whole_tree = False
        for m in _CLEAN.finditer(scanned):
            tail = m.group(1)
            if not _CLEAN_FORCE.search(tail) or _CLEAN_DRY_RUN.search(tail):
                continue
            if _CLEAN_IGNORED_ONLY.search(tail):
                clean_wanted.add("ignored")
            elif _CLEAN_ALSO_IGNORED.search(tail):
                clean_wanted |= {"untracked", "ignored"}
            else:
                clean_wanted.add("untracked")
            paths = _operands(tail, command[m.start(1):m.end(1)])
            if paths:
                clean_paths += paths
            else:
                # A pathless clean means the whole tree, and merging it into the
                # union as "no paths" LOST that: `git clean -fd && git clean -fd
                # sub` probed only `sub` and went silent on an untracked file at
                # the root the first command would have deleted.
                clean_whole_tree = True
        if clean_wanted and _holds_work(
            cwd,
            [] if clean_whole_tree else clean_paths,
            clean_wanted,
            "ignored" in clean_wanted,
            whole_tree,
        ):
            found.append(CLEAN_REASON)
    except Exception:  # noqa: BLE001 — see the comment above the `try`
        if DISCARD_REASON not in found:
            found.append(DISCARD_REASON)

    if _GH_PR_MERGE.search(scanned):
        found.append(MERGE_REASON)
    return found


def _cwd_of(payload: object) -> str:
    """Where the matched command will run.

    Falls back to the process cwd when the payload omits it (older payload
    shapes, and this hook's own tests, which set the process cwd instead) —
    the same contract `block-unsafe-recursive-delete.py` uses.
    """
    cwd = payload.get("cwd") if isinstance(payload, dict) else None
    return cwd if isinstance(cwd, str) and cwd else os.getcwd()


def main() -> int:
    if os.environ.get("ALLOW_DESTRUCTIVE_GIT") == "1":
        # Only worth saying when there was something to prompt about; otherwise
        # every `ls` in the session would carry the notice. But when a
        # force-push or a `reset --hard` sails through because of a switch
        # somebody exported weeks ago, that has to be visible.
        try:
            payload = json.load(sys.stdin)
        except json.JSONDecodeError:
            return 0
        tool_input = payload.get("tool_input", {}) if isinstance(payload, dict) else {}
        command = tool_input.get("command") if isinstance(tool_input, dict) else None
        if isinstance(command, str) and command and _reasons(command, _cwd_of(payload)):
            print(
                "[ask-destructive-git] note: this command would normally prompt "
                "for confirmation, but the check is DISABLED by "
                "ALLOW_DESTRUCTIVE_GIT=1. Unset it to re-enable. "
                "(hook: ask-destructive-git.py)",
                file=sys.stderr,
            )
        return 0
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0
    tool_input = payload.get("tool_input", {}) if isinstance(payload, dict) else {}
    command = tool_input.get("command") if isinstance(tool_input, dict) else None
    if not isinstance(command, str) or not command:
        return 0

    found = _reasons(command, _cwd_of(payload))

    # `ALLOW_PR_MERGE=1` drops ONLY the merge reason. A command that also
    # force-pushes still prompts, on the force-push — which is the whole point
    # of a narrow variable over the broad one. Announced on stderr for the same
    # reason the broad hatch is: a merge sailing through because of a switch set
    # earlier in the run must not look like one the guard deliberately allowed.
    #
    # Honoured from the COMMAND TEXT as well as the environment, and the command
    # text is the form to prefer. A PreToolUse hook runs BEFORE the command is
    # executed, so an inline `ALLOW_PR_MERGE=1 gh pr merge …` prefix never
    # reaches this process's `os.environ` — reading only the environment would
    # mean the per-command form silently did nothing, which is exactly how it
    # was first written. Matching the prefix here is what makes "authorize this
    # one command" expressible at all; the environment form remains for a
    # caller that genuinely wants it set for a whole run.
    # Scanned on the QUOTE-STRIPPED text, like every other matcher in this file.
    # Scanning the raw command made the escape hatch satisfiable by prose: the
    # anchor `(?:^|[&|;]\s*)` accepts a separator that sits INSIDE a quoted span,
    # which the shell treats as one literal and never evaluates as an assignment.
    # Both of these silenced the prompt entirely:
    #
    #   gh pr merge 27 && echo "; ALLOW_PR_MERGE=1 done"
    #   git commit -m "fix hook; ALLOW_PR_MERGE=1 now bypasses it" && gh pr merge 27
    #
    # The second is the shape a session working on THIS hook writes. The guard
    # exists because authorization is the one thing a hook cannot read, so a
    # bypass firing on unrelated text removes exactly the protection it adds --
    # and the stderr note below then announced a disabling nobody requested.
    #
    # A genuine inline `ALLOW_PR_MERGE=1 gh pr merge …` prefix is unquoted, so it
    # survives stripping intact and the per-command form still works.
    if found and (
        os.environ.get("ALLOW_PR_MERGE") == "1"
        or _ALLOW_MERGE_PREFIX.search(_strip_quoted_spans(command))
    ):
        kept = [r for r in found if r != MERGE_REASON]
        if len(kept) != len(found):
            print(
                "[ask-destructive-git] note: the PR-merge confirmation is "
                "DISABLED by ALLOW_PR_MERGE=1 for this command. Force-push, "
                "reset --hard and branch force-delete are still checked. "
                "(hook: ask-destructive-git.py)",
                file=sys.stderr,
            )
        found = kept
    if not found:
        return 0

    # A reader's only lever against a PreToolUse hook is an inline command-text
    # prefix — `ALLOW_DESTRUCTIVE_GIT` is env-only (see the module docstring's
    # "Escape hatches" section, above), so recommending it here for a
    # merge-only prompt sends the reader to a variable that silently does
    # nothing as an inline prefix. When the merge reason is the ONLY one
    # present, point at the narrow variable that's actually honoured from
    # command text (`_ALLOW_MERGE_PREFIX`, above). Force-push and
    # `reset --hard` have no narrow equivalent, so those (and any mix that
    # includes them) still name the broad, env-only variable — worded as
    # "export" so the inline/environment distinction is explicit.
    #
    # `found == [MERGE_REASON]` depends on `_reasons()` always appending in
    # the fixed order force-push, reset --hard, branch force-delete, working-tree
    # discard, clean, merge (never in the order the command text names them) —
    # merge stays LAST, which is what makes list
    # equality a safe "merge is the only reason" test. If `_reasons()`'s check
    # order or set of reasons ever changes, re-verify this equality still means
    # what it says.
    if found == [MERGE_REASON]:
        hatch_note = (
            "Prefix this one command with ALLOW_PR_MERGE=1 to authorize a "
            "deliberate unattended merge without this prompt; "
        )
    else:
        hatch_note = (
            "Set ALLOW_DESTRUCTIVE_GIT=1 in the environment to run a "
            "deliberate unattended batch without this prompt; "
        )

    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "ask",
            "permissionDecisionReason": (
                "This command performs "
                + " and ".join(found)
                + ". Confirm it is what you intend. ("
                + hatch_note
                + "hook: ask-destructive-git.py)"
            ),
        }
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
