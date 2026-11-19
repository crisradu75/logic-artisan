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
SHAPE (via the shared `GitInvocation` matcher, after quote-stripping) closes
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
  `_FORCE_DISCARD`. A merging (`-m`) or resetting (`-C`/`-B`) branch change has
  its own condition, below.

  Known misses in this rule, named rather than implied. A path quoted at
  something other than a token boundary (`git checkout -- dir/"f.txt"`) — the
  operand keeps its inner quote and matches nothing, consistent with
  `strip_quoted_spans`' own disclaimer about partial quoting.
  `--pathspec-from-file=<f>`, whose paths live in a file a regex cannot read. A
  `git clean` run from a SUBDIRECTORY with no path operands, where the probe
  asks about the whole repository and so over-prompts on untracked files
  outside the directory clean would touch.
- `git stash` (bare, `push`, `save`, or options only such as `-u`) while a merge,
  cherry-pick or revert is in progress, i.e. `MERGE_HEAD`, `CHERRY_PICK_HEAD` or
  `REVERT_HEAD` exists in the git dir. Stash saves the tree and resets it, and
  that reset removes the in-progress marker: the next commit then has one parent
  and one side of the merge is gone, with no conflict markers and a green suite
  (issue #398: one side of about 47 files, noticed only because the test count
  dropped). The prompt names the safe alternatives, `git show <ref>:<path>` and
  a scratch worktree. Outside such a state stash is routine and stays silent, as
  do `list`, `show`, `pop`, `apply`, `drop`, `clear`, `create`, `store` and
  `branch`, none of which save-and-reset. The git dir comes from `git rev-parse
  --absolute-git-dir` run in the command's directory (cwd, moved by each
  `git -C <dir>`), so a linked worktree checks its own marker files. A stash
  whose repository cannot be named (`--git-dir`, `GIT_DIR=`, `-C ~/x`, `-C $V`, a `-C` path that does not exist)
  asks as unchecked. Any tail that is not a non-saving subcommand counts as
  saving, so `git stash 2>&1` and `(git stash)` are covered.
- `git rebase`, and a `git pull` that rebases (`-r`, `--rebase[=<mode>]`, or
  `branch.<name>.rebase` / `pull.rebase` set), when the commits it rewrites
  (`<upstream>..<branch>`, all of `<branch>` under `--root`) include one
  already on a remote-tracking branch, ANY remote's, not only the upstream: a
  branch pushed without `-u` is published all the same. Rewriting it takes a
  force-push, and the guarded `--force-with-lease` form does not ask, so this
  is the checkpoint. A pull rebases onto `<remote>/<branch>` when it names
  them (onto `<branch>` itself when the remote is `.`, this repository), else
  onto `@{upstream}`, read BEFORE its fetch runs. Settings come from a
  `git -c` override in the command first, then the repository's config.
  Silent: a rebase of local-only commits onto a fresh base (nobody else has
  them and `ORIG_HEAD` undoes it); a rebase onto an upstream that is already
  an ancestor of the branch, which replays nothing, but only when every option
  is in a measured no-replay set (`_REBASE_NO_REPLAY_LONG`; any other option,
  an abbreviation included, asks) and, under fork-point (the default without
  an upstream operand, unless `--no-fork-point` or `rebase.forkPoint=false`),
  `merge-base --fork-point` finds no older point in the upstream's reflog;
  never for a pull, whose fetch can move the upstream; a rebase on a dirty
  tree, because git refuses that itself and `--autostash` keeps the changes in
  the stash when the re-apply conflicts
  (measured, git 2.43); and `--continue`, `--abort`, `--skip`, `--quit`,
  `--edit-todo` and `--show-current-patch`, which rewrite nothing new and are
  never probed.
  Known miss: "on a remote" means a remote-tracking ref in THIS clone. A stale
  or missing one (a single-branch clone, a branch pushed to a URL rather than a
  remote, refs never fetched) makes pushed commits look local.
- `git switch -C <name>` / `--force-create` (switch only: checkout has no such
  option), and `git checkout -B <name>`, when
  `<name>` already exists and holds commits on no other branch, tag or
  remote-tracking branch, nor in the start point. git resets it without a word,
  orphaning them: the same loss as a force-delete. Creating a new branch, or a
  reset that keeps every commit reachable, is silent.
- A merging branch change, `checkout`/`switch` with `-m`, `--merge` or
  `--conflict`, while changes are STAGED. git-checkout(1) says staged changes
  may be lost this way; git 2.43 refuses instead (measured), so on recent git
  this prompt is one extra keystroke on a rare command. Unstaged changes are
  silent: a conflicted merge keeps them in the markers and as index stage 3.
  These three fail OPEN when their probe cannot run, unlike the discards above:
  what they protect is still in the reflog or the object store. A probe that
  did not run leaves one note on stderr. Their words are read by their unquoted
  text, so `"-i"` is `-i`, and no command text reaches git as an option: every
  revision is resolved by `rev-parse --end-of-options` and only commit SHAs go
  on to the other probes (a quoted `"--output=<file>"` once made `rev-list`
  truncate that file before the user was asked).
- A push that skips the `pre-push` guard on the default branch: `--no-verify`
  (down to `--no-veri`), `-c core.hooksPath=...`, or the hook's own
  `ALLOW_PUSH_TO_MAIN=1` override typed into the command. That guard is the only
  one on the default branch, and each of these skips it without a word.
- `gh pr merge`, including behind global options and as `gh.exe`/`gh.cmd`. Not
  destructive in the same sense, but outward-facing and effectively
  irreversible, and the thing that fails there is AUTHORIZATION — which a hook
  cannot read, so the prompt is unconditional. NOT matched (regex cannot reach
  them, and they are named rather than implied): a shell alias, a case variant
  like `GH pr merge`, and the REST form `gh api -X PUT .../pulls/N/merge`.
  See `_GH_PR_MERGE` for the incident that added it.
- Every shape above also when a shell wrapper runs it from quoted text
  (`bash -c "..."`, `sh -c`, `zsh -c`, `eval "..."`, `pwsh -Command`,
  `-EncodedCommand`, `Invoke-Expression`/`iex`, `cmd /c`), nested up to three
  deep, and when a git subcommand or a `push`/`reset`/`branch` flag comes from a
  `$NAME` the same command assigns a literal (`X=push; git $X -f`). A git
  subcommand from any other expansion (`git $X`, `git "$@"`, `git $(...)`), or
  an unquoted unassigned `$NAME` among a push, reset or branch's options
  (`git push $F origin x`), asks as unresolved. `_expand` has the rules and
  the named misses; `bash -c "git status"` and `eval "$(ssh-agent)"` stay
  silent.

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
commit"; the exclusion survives, its stated reason does not. `git switch -C`
and `git checkout -B` reset a branch the same way and ARE checked, because a
condition (commits nothing else reaches) keeps that prompt rare; carrying the
same condition to `git branch -f/-M/-C` is open.

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

import base64
import functools
import json
import os
import re
import sys
import time
from pathlib import Path

# Why this bootstrap is needed: neither the
# dispatcher's in-process load nor pytest puts the hooks dir at sys.path[0] for
# this file, so the `_dispatch_lib` import below is made explicit rather than
# left to depend on how the process happened to start.
_HOOKS_DIR = str(Path(__file__).resolve().parent)
if _HOOKS_DIR not in sys.path:
    sys.path.insert(0, _HOOKS_DIR)

from _dispatch_lib import GitInvocation  # noqa: E402
from _dispatch_lib import Deadline  # noqa: E402
from _dispatch_lib import GIT_SEP as _GIT_SEP  # noqa: E402
from _dispatch_lib import GIT_TIMEOUT_SECONDS  # noqa: E402
from _dispatch_lib import HOOK_WORST_CASE_SECONDS  # noqa: E402
from _dispatch_lib import run_git as _run_git  # noqa: E402
from _dispatch_lib import strip_quoted_spans as _strip_quoted_spans  # noqa: E402

# Horizontal whitespace, or a backslash line continuation. A continuation is a
# JOINED line, not a new command, so it separates tokens; a bare newline ends
# the command and must not. Both rules below and `_GH_PR_MERGE` share this —
# four review rounds each found the same bug one construct over, every time
# because one position used a plain `\s` or excluded the newline outright.
# Imported rather than defined here: `GIT_GLOBAL_OPTS` needs the same thing, and
# the two drifting is exactly how `git -C . \`+newline+`push --force` stayed a
# silent bypass after every OTHER separator position had been fixed.
_SEP = _GIT_SEP

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
# Each is `GIT_CMD`, `_SEP`, the global options, then the subcommand and tail,
# matched by `GitInvocation` in linear time: the regex it replaced took 25 s on
# a 28 KB `git -c git -c git ... status`, past the hook timeout (#526).
_PUSH = GitInvocation(r"push\b" + _TAIL)
_RESET = GitInvocation(r"reset\b" + _TAIL)
_BRANCH = GitInvocation(r"branch\b" + _TAIL)
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

def _abbrev(word: str, floor: int) -> str:
    """Regex for any prefix of `word` at least `floor` characters long.

    git accepts any UNAMBIGUOUS long-option abbreviation, so a matcher that
    spells an option out in full is a silent bypass for every shorter spelling
    git still resolves. `floor` is that command's shortest resolving prefix and
    must be read off THAT command's own option set — it differs per command, and
    guessing it wrong fails in both directions (too low over-matches a prefix git
    refuses; too high misses one it accepts).

    Generated rather than hand-written. The nesting is fine at four characters
    and stops being fine at fifteen: a hand-written `--discard-changes` form
    shipped here with unbalanced parentheses, and the whole module then failed to
    import — which the dispatcher reports as a hook that did not run, i.e. every
    check in this file silently off.
    """
    out = ""
    for char in reversed(word[floor:]):
        out = "(?:" + re.escape(char) + out + ")?"
    return re.escape(word[:floor]) + out


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
# The three ways a push skips the `pre-push` guard on the default branch: git's own
# `--no-verify` (abbreviable down to `--no-veri`; `--no-ver` is ambiguous with
# `--no-verbose`), a `core.hooksPath` pointed elsewhere for this one command, and the
# hook's own `ALLOW_PUSH_TO_MAIN=1` override typed inline.
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
    r"(?:^|[\s;&|({])ALLOW_PUSH_TO_MAIN=(?:1|\"#\"|'#')(?=[\s;&|)]|$)"
)
PUSH_GUARD_SKIP_REASON = (
    "a push that skips the pre-push guard on the default branch (`--no-verify`, "
    "`core.hooksPath`, or `ALLOW_PUSH_TO_MAIN=1`) — confirm the user asked to bypass it"
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


def _operation_in_progress(directory: str) -> bool | None:
    """True when a merge, cherry-pick or revert is in progress in `directory`.

    `None` means the probe could not run (no git, or a hang past the timeout),
    the same sentinel `_status_lines` uses. A refusal (not a repository) is
    False: git is about to reject the stash the same way. But a directory that
    does not exist is NOT a refusal we can trust: it may be a path the shell
    would have translated (`/c/...` under Git Bash), so that is "could not check".
    """
    result = _run_git(directory, ["rev-parse", "--absolute-git-dir"])
    if result is None:
        return None
    if result.returncode != 0:
        return False if os.path.isdir(directory) else None
    git_dir = result.stdout.strip()
    return any(os.path.exists(os.path.join(git_dir, n)) for n in _OPERATION_MARKERS)


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
# reach the other probes, and an operand starting with `-` is silence.
#
# Budget: these probes run after the four above and spend only what those left
# of `HOOK_WORST_CASE_SECONDS["ask-destructive-git.py"]`, so that entry stays
# true however many there are. `_reasons()` must keep them last for that.
_PROBE_BUDGET_SECONDS = HOOK_WORST_CASE_SECONDS["ask-destructive-git.py"]
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
# One segment of a shell word each: `$'...'`, `'...'`, `"..."` or `$"..."`, a
# backslash escape, or plain text; a closing quote may be missing.
_QUOTED = re.compile(
    r"""\$'((?:[^'\\]|\\.)*)'?|'([^']*)'?|\$?"((?:[^"\\]|\\.)*)"?|\\(.)|([^'"\\$]+|.)""", re.S
)
_ANSI_ESCAPE = re.compile(r"\\(x[0-9a-fA-F]{1,2}|[0-7]{1,3}|.)", re.S)
# Inside double quotes a backslash escapes only these.
_DOUBLE_ESCAPE = re.compile(r'\\([\\"$`])')
_ANSI_C = {
    "n": "\n", "t": "\t", "r": "\r", "a": "\a", "b": "\b", "f": "\f", "v": "\v",
    "e": "\x1b", "E": "\x1b", "\\": "\\", "'": "'", '"': '"', "?": "?",
}

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


def _unquote(word: str) -> str:
    """One shell word as the command receives it: `'...'`, `"..."`, `$'...'`
    (ANSI-C escapes), `$"..."` and backslashes, at any point in the word, so
    `ma"in"`, `$'main'` and `--rebase="false"` read as `main` and `--rebase=false`.
    An unterminated quote runs to the end of the word."""
    out: list[str] = []
    for m in _QUOTED.finditer(word):
        ansi, single, double, escaped, plain = m.groups()
        if ansi is not None:
            out.append(_ANSI_ESCAPE.sub(_ansi_char, ansi))
        elif double is not None:
            out.append(_DOUBLE_ESCAPE.sub(r"\1", double))
        else:
            out.append(next(g for g in (single, escaped, plain) if g is not None))
    return "".join(out)


def _ansi_char(m: re.Match) -> str:
    """One `$'...'` escape: hex `x` plus digits, octal digits, or a named one (`t`)."""
    code = m.group(1)
    if code[0] == "x" and len(code) > 1:
        return chr(int(code[1:], 16))
    if code[0] in "01234567":
        return chr(int(code, 8))
    return _ANSI_C.get(code, "\\" + code)


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
    discard check above already covers, so the `--` form is left to it."""
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


class _Probes:
    """The history checks' git calls: one shared deadline, each identical call
    run once, and every revision from the command resolved to a SHA before it
    goes anywhere else."""

    def __init__(self, started: float) -> None:
        # Also no later than the handler's own deadline, when the probe measured
        # it (`CLA_HOOK_T0`): these run last, after every reason above is found,
        # and a handler killed here would drop those reasons with it. Without a
        # measurement the handler's figure is a guess, and the hook's own budget
        # alone applies. Counted from `started`, which is earlier than now, so
        # the bound errs early.
        handler = Deadline()
        budget = _PROBE_BUDGET_SECONDS
        if handler.measured:
            budget = min(budget, handler.remaining())
        self.deadline = started + budget
        self.asked: dict = {}
        self.missed = False

    def git(self, directory: str, args: list[str]):
        key = (directory, tuple(args))
        if key not in self.asked:
            left = self.deadline - time.monotonic()
            self.asked[key] = (
                _run_git(directory, args, timeout=min(GIT_TIMEOUT_SECONDS, left))
                if left > 0 else None
            )
            self.missed = self.missed or self.asked[key] is None
        return self.asked[key]

    def commit(self, directory: str, rev: str) -> str | None:
        """`rev` as a full commit SHA, or None. `--end-of-options` keeps a
        `--output=<file>` from being read as an option; a leading `-` is
        refused outright."""
        if not rev or rev.startswith("-"):
            return None
        # `:/<text>` names the youngest commit whose message matches, so it is
        # a commit already; a `^{commit}` suffix would join the search text.
        peeled = rev if rev.startswith(":/") else rev + "^{commit}"
        out = self.git(directory, ["rev-parse", "--verify", "--quiet", "--end-of-options", peeled])
        sha = out.stdout.strip() if out is not None and out.returncode == 0 else ""
        return sha if re.fullmatch(r"[0-9a-f]{40,64}", sha) else None

    def ref(self, directory: str, rev: str) -> str | None:
        """The full ref name `rev` spells (`refs/remotes/origin/main`), or None
        for a revision that is not a ref. git prints it; the command never
        reaches `merge-base` itself."""
        if rev.startswith("-"):
            return None
        out = self.git(directory, [
            "rev-parse", "--verify", "--quiet", "--symbolic-full-name", "--end-of-options", rev,
        ])
        name = out.stdout.strip() if out is not None and out.returncode == 0 else ""
        return name if re.fullmatch(r"refs/[^\s]+", name) else None

    def setting(self, directory: str, key: str, overrides: dict[str, str]) -> str | None:
        """A config value: a `-c` override from the command first, else the
        repository's own, else None when unset."""
        if _config_key(key) in overrides:
            return overrides[_config_key(key)]
        out = self.git(directory, ["config", "--get", key])
        return out.stdout.strip() if out is not None and out.returncode == 0 else None


def _rewrites_published(
    directory: str, branch: str, upstream: str | None, rewrites: bool,
    fork_point: bool, probes: _Probes,
) -> bool:
    """True when the commits the rebase rewrites include one already reachable
    from a remote-tracking branch: two counts over the same range, the second
    leaving out everything `--remotes` reaches. Any remote counts, not only the
    upstream, because a branch pushed without `-u` is published all the same.

    A branch already up to date with its upstream (the upstream is an ancestor
    of it) replays nothing, unless `rewrites` says an option may force it, or
    fork-point finds an older point in the upstream's reflog: there git drops
    the commits the upstream has since lost and replays the rest.
    """
    tip = probes.commit(directory, branch)
    if tip is None:
        return False
    span = [tip]
    if upstream is not None:
        base = probes.commit(directory, upstream)
        if base is None:
            return False
        if not rewrites and _replays_nothing(directory, upstream, base, tip, fork_point, probes):
            return False
        span.append("^" + base)
    every = probes.git(directory, ["rev-list", "--count", *span, "--"])
    if every is None or every.returncode != 0:
        return False
    local = probes.git(directory, ["rev-list", "--count", *span, "--not", "--remotes", "--"])
    if local is None or local.returncode != 0:
        return False
    return int(every.stdout) > int(local.stdout)


def _replays_nothing(
    directory: str, upstream: str, base: str, tip: str, fork_point: bool, probes: _Probes
) -> bool:
    """True when git would report the branch up to date: `base` is an ancestor
    of `tip` and, under fork-point, the fork point is `base` or there is none.
    A probe that cannot run counts as up to date, so the check fails open."""
    ancestor = probes.git(directory, ["merge-base", "--is-ancestor", base, tip])
    if ancestor is None:
        return True
    if ancestor.returncode != 0:
        return False
    ref = probes.ref(directory, upstream) if fork_point else None
    if ref is None:
        return True
    out = probes.git(directory, ["merge-base", "--fork-point", "--end-of-options", ref, tip])
    if out is None:
        return True
    found = out.stdout.strip() if out.returncode == 0 else ""
    return found in ("", base)


def _pull_rebases(
    directory: str, rebase: bool | None, overrides: dict[str, str], probes: _Probes
) -> bool:
    """Whether a `git pull` rebases: the command's own flag, else
    `branch.<current>.rebase`, else `pull.rebase`, each from a `-c` override
    before the repository's config. The branch name comes from git's own
    output, never from the command."""
    if rebase is not None:
        return rebase
    head = probes.git(directory, ["symbolic-ref", "--quiet", "--short", "HEAD"])
    keys = ["pull.rebase"]
    if head is not None and head.stdout.strip():
        keys.insert(0, "branch." + head.stdout.strip() + ".rebase")
    for key in keys:
        value = probes.setting(directory, key, overrides)
        if value is not None:
            return _is_true(value)
    return False


def _is_true(value: str) -> bool:
    """A config value as git's `--rebase`/`forkPoint` reading takes it."""
    return value.strip().lower() not in _NOT_REBASE and value.strip() != ""


def _orphans_commits(directory: str, name: str, start: str, probes: _Probes) -> bool:
    """True when branch `name` exists and holds commits on no other branch, tag
    or remote-tracking branch, nor in `start` — what the reset would orphan.
    A branch that does not exist yet does not resolve: silence, since creating
    it loses nothing."""
    if name.startswith("-"):
        return False
    tip = probes.commit(directory, "refs/heads/" + name)
    target = probes.commit(directory, start)
    if tip is None or target is None:
        return False
    out = probes.git(directory, [
        "rev-list", "--count", tip, "--not",
        "--exclude=" + name, "--branches", "--tags", "--remotes", target, "--",
    ])
    return out is not None and out.returncode == 0 and int(out.stdout) > 0


def _holds_staged_work(directory: str, probes: _Probes) -> bool:
    """True when the index differs from HEAD anywhere: porcelain column X is not
    blank. `--untracked-files=no` keeps `??` lines, whose X is `?`, out."""
    out = probes.git(directory, ["status", "--porcelain", "--untracked-files=no"])
    if out is None or out.returncode != 0:
        return False
    return any(line[:1].strip() for line in out.stdout.splitlines())


def _history_reasons(command: str, scanned: str, cwd: str, started: float) -> list[str]:
    """The rebase, branch-reset and merging-switch reasons in `command`."""
    probes = _Probes(started)
    found: list[str] = []
    for m in _REBASE.finditer(scanned):
        directory = _invocation_dir(command[m.start(1):m.end(1)], scanned, cwd)
        target = _rebase_range(_words(m.group(2), command[m.start(2):m.end(2)]))
        if directory and target and REBASE_REASON not in found:
            branch, upstream, rewrites, fork_point = target
            if fork_point is None:
                overrides = _config_overrides(command[m.start(1):m.end(1)])
                setting = probes.setting(directory, "rebase.forkPoint", overrides)
                fork_point = setting is None or _is_true(setting)
            if _rewrites_published(directory, branch, upstream, rewrites, fork_point, probes):
                found.append(REBASE_REASON)
    for m in _PULL.finditer(scanned):
        directory = _invocation_dir(command[m.start(1):m.end(1)], scanned, cwd)
        rebase, operands = _pull_rebase(_words(m.group(2), command[m.start(2):m.end(2)]))
        upstream = _pull_upstream(operands)
        if directory and upstream and REBASE_REASON not in found:
            # Always `rewrites`: the fetch can move the upstream past HEAD, so
            # "up to date" before it says nothing about after.
            overrides = _config_overrides(command[m.start(1):m.end(1)])
            if _pull_rebases(directory, rebase, overrides, probes) and _rewrites_published(
                directory, "HEAD", upstream, True, False, probes
            ):
                found.append(REBASE_REASON)
    for m in _BRANCH_CHANGE.finditer(scanned):
        directory = _invocation_dir(command[m.start(1):m.end(1)], scanned, cwd)
        if directory is None:
            continue
        words = _words(m.group(3), command[m.start(3):m.end(3)])
        target = _reset_target(words, m.group(2))
        if target and BRANCH_RESET_REASON not in found:
            if _orphans_commits(directory, *target, probes):
                found.append(BRANCH_RESET_REASON)
        if _merges_on_switch(words, m.group(2)) and MERGE_SWITCH_REASON not in found:
            if _holds_staged_work(directory, probes):
                found.append(MERGE_SWITCH_REASON)
    if probes.missed:
        print(
            "[ask-destructive-git] a rebase or branch-change probe did not run "
            "(git missing, a timeout, or the hook's time budget spent) — not "
            "asking about it. (hook: ask-destructive-git.py)",
            file=sys.stderr,
        )
    return found


# --- Shell wrappers and expansions --------------------------------------------
# Every matcher above reads the command's quote-stripped text, so a command that
# hands git to another shell inside quotes (`bash -c "git push -f origin x"`,
# `sh -c '...'`, `eval "..."`, `pwsh -Command '...'`, `Invoke-Expression`,
# `cmd /c`) was blanked and allowed, and so was a git whose subcommand or flag
# the shell fills in (`X=push; git $X -f origin x`). `_expand` closes both:
#
# - A WRAPPER's argument words are read, unquoted, joined and appended to the
#   command as a line of their own, and wrappers inside that line are read the
#   same way, `_WRAP_DEPTH` levels deep. A body is appended only when it holds
#   `git` or `gh`, so `eval "$(ssh-agent)"` costs nothing. A wrapper word is
#   found outside quotes wherever it sits, so `echo bash -c 'git push -f'` asks
#   too: one extra prompt on a command that names a destructive one, rather than
#   a list of every prefix that can run a command.
# - A git at a command's start whose SUBCOMMAND is quoted or comes from `$...`
#   or a backtick is rewritten with the value: a quoted literal is unquoted,
#   and a `$NAME` assigned a literal in the same command (`NAME=v`, `export`,
#   PowerShell `$NAME = 'v'`) is tried with each value it is given. Anything
#   else (an unassigned, computed or positional name, `$(...)`) asks:
#   `UNRESOLVED_REASON`.
# - The same for a `$NAME` in the arguments of `git push`, `git reset` and
#   `git branch`, whose flags alone decide a prompt. An unquoted name that
#   cannot be resolved asks only while no plain operand has been seen
#   (`git push $F origin x`); after one (`git push origin $BRANCH`, the common
#   shape) it is left alone. A quoted `"$NAME"` is one word, the way a value is
#   passed (`git branch "$NAME"`), and a `$(...)` is a computed value; neither
#   asks. Known misses, named: a flag from an expansion after an operand or in
#   double quotes, a refspec from one (`+main`), a command name from one
#   (`$CMD push -f`), a
#   quoted `git` (`'git' push -f`), and a prefix command that takes a value
#   (`timeout 60 git $X`), which hides the command's start.
#
# Appended text goes after a blank line, so no line continuation or tail joins
# it to the line before, and each part is quote-stripped on its own, so an odd
# quote in one part cannot pair with one in the next. The result is the command
# itself whenever nothing was appended, so every other command reads exactly as
# before. Appended text is capped at the command's own length plus
# `_EXPAND_SLACK`; past that, or past `_WRAP_DEPTH`, the command asks rather
# than being read partly.
_WRAP_DEPTH = 3
_EXPAND_ROUNDS = 4
_EXPAND_SLACK = 4096
_EXPAND_MAX_LINES = 64
_PART_SEP = "\n\n"
# Where a command word may start: after a path separator inside the word, or
# after whitespace, an operator or the start of the text.
_WORD_START = r"(?:(?<=[/\\])|(?<![^\s;&|(){}`!]))"
_WRAPPER = re.compile(
    _WORD_START
    + r"(?i:bash|sh|zsh|dash|ksh|mksh|ash|fish|csh|tcsh|su|pwsh|powershell|cmd"
    r"|eval|iex|invoke-expression)(?i:\.exe)?(?=[ \t]|\\\r?\n)"
)
# `-EncodedCommand` and its PowerShell spellings: `-e`, `-ec`, `-en` onward.
_PS_ENCODED = re.compile(r"(?i)-(?:ec|" + _abbrev("encodedcommand", 1) + ")")
_HAS_GIT = re.compile(r"(?i)git|gh")
# A `$NAME` or `${NAME}`, optionally inside double quotes: the one expansion
# shape `_expand` resolves.
_SINGLE_VAR = re.compile(r'"?\$(?:([A-Za-z_]\w*)|\{([A-Za-z_]\w*)\})"?')
# A shell assignment word (`X=`, `export X=`), and a PowerShell one (`$X =`).
_ASSIGN = re.compile(
    r"(?:^|(?<=[\s;&|(){}`]))(?:(?:export|local|declare|readonly|typeset)[ \t]+"
    r"(?:-\w+[ \t]+)*)?([A-Za-z_]\w*)="
)
_PS_ASSIGN = re.compile(r"(?:^|(?<=[\s;&|(){}]))\$([A-Za-z_]\w*)[ \t]*=(?!=)[ \t]*")
# A value is taken as literal only when it is plain text a shell would not
# expand or a PowerShell expression would not compute.
_LITERAL_VALUE = re.compile(r"[\w ./:+=,@%~^-]*")
# A word that is a prefix to the command after it, not the command.
_COMMAND_PREFIXES = frozenset(
    "sudo env command exec time nohup nice xargs builtin then do else elif if while until".split()
)
_GIT_SUBCOMMAND_EXPANDED = GitInvocation(r"(?=[$`\"'])", capture_opts=True)
# Global options that take the next word as their value. The matcher may read
# one as a bare flag, which makes its value look like the subcommand.
_GIT_VALUE_OPT = re.compile(r"-[cC]|--(?:git-dir|work-tree|namespace|super-prefix)")
_TAIL_RE = re.compile(_TAIL)
_STOP = frozenset(" \t\r\n;&|<>()")


@functools.lru_cache(maxsize=128)
def _stripped(part: str) -> str:
    """`part` quote-stripped. Several readers below strip the same part; one
    pass serves them all."""
    return _strip_quoted_spans(part)


UNRESOLVED_REASON = (
    "a git command whose subcommand or flags come from a shell expansion this "
    "guard cannot resolve (`git $X ...`, `git push $F ...`), so it cannot tell "
    "whether this force-pushes, hard-resets or force-deletes a branch"
)


def _word_end(text: str, i: int) -> int:
    """End of the shell word that starts at `i`: quotes, backslash escapes,
    `$(...)` and backtick spans are part of the word; unquoted whitespace or an
    operator ends it. An unterminated quote runs to the end of the text."""
    n = len(text)
    while i < n:
        ch = text[i]
        if ch == "\\":
            i += 2
        elif ch == "'":
            j = text.find("'", i + 1)
            i = n if j < 0 else j + 1
        elif ch == '"':
            j = i + 1
            while j < n and text[j] != '"':
                j += 2 if text[j] == "\\" else 1
            i = j + 1
        elif ch == "`":
            j = text.find("`", i + 1)
            i = n if j < 0 else j + 1
        elif text.startswith("$(", i):
            depth, j = 0, i + 1
            while j < n:
                depth += (text[j] == "(") - (text[j] == ")")
                if depth == 0:
                    break
                j += 1
            i = j + 1
        elif ch in _STOP:
            break
        else:
            i += 1
    return min(i, n)


def _command_words(text: str, i: int) -> list[tuple[int, int]]:
    """The `(start, end)` of each word from `i` to the end of its simple
    command. A redirection operator is skipped (its target stays a word); a
    line continuation is not an end."""
    spans: list[tuple[int, int]] = []
    n = len(text)
    while i < n:
        ch = text[i]
        if ch in " \t":
            i += 1
        elif ch == "\\" and text.startswith("\n", i + 1):
            i += 2
        elif ch == "\\" and text.startswith("\r\n", i + 1):
            i += 3
        elif ch in "<>":
            i += 1
            while i < n and text[i] in "<>&|":
                i += 1
        elif ch in _STOP:
            break
        else:
            end = _word_end(text, i)
            spans.append((i, end))
            i = end
    return spans


def _has_expansion(word: str) -> bool:
    """True when the shell substitutes part of `word`: a `$` that starts a
    parameter or command substitution, or a backtick, outside single quotes.
    `$'...'` is a literal: the `'` after its `$` starts no expansion, and the
    single-quote rule then skips its text."""
    i, n, double = 0, len(word), False
    while i < n:
        ch = word[i]
        if ch == "\\":
            i += 2
            continue
        if ch == "'" and not double:
            j = word.find("'", i + 1)
            i = n if j < 0 else j + 1
            continue
        if ch == '"':
            double = not double
        elif ch == "`":
            return True
        elif ch == "$" and i + 1 < n and (word[i + 1].isalnum() or word[i + 1] in "_{(@*#?!$-"):
            return True
        i += 1
    return False


def _at_command_start(scanned: str, start: int) -> bool:
    """True when the word holding position `start` is where a command starts:
    `git` is the whole word or its last path element, and only operators,
    assignments, options and prefix words (`sudo`, `env`, ...) come before it
    in its simple command."""
    i = start
    if i > 0 and scanned[i - 1] not in " \t\n;&|(){}`!/\\":
        return False
    while i > 0 and scanned[i - 1] not in " \t\n;&|(){}`!":
        i -= 1
    while True:
        while i > 0 and scanned[i - 1] in " \t":
            i -= 1
        if i == 0 or scanned[i - 1] in "\n;&|(){}`!":
            return True
        end = i
        while i > 0 and scanned[i - 1] not in " \t\n;&|(){}`!":
            i -= 1
        word = scanned[i:end]
        if not (
            word.lower() in _COMMAND_PREFIXES
            or word.startswith("-")
            or re.fullmatch(r"[A-Za-z_]\w*=\S*", word)
        ):
            return False


def _assignments(parts: list[str]) -> dict[str, list[str | None]]:
    """Every value each name is assigned in the command, in any part; None for
    a value that is not a plain literal."""
    found: dict[str, list[str | None]] = {}
    for part in parts:
        scanned = _stripped(part)
        for pattern in (_ASSIGN, _PS_ASSIGN):
            for m in pattern.finditer(scanned):
                end = _word_end(part, m.end())
                raw = part[m.end():end]
                value: str | None = None
                # A bare word after PowerShell's `=` is a command it runs
                # (`$X = Get-Verb`), so only a quoted string is a literal there.
                bare_ps = pattern is _PS_ASSIGN and not raw.startswith(("'", '"'))
                if not bare_ps and not _has_expansion(raw) and not part.startswith("(", end):
                    value = _unquote(raw)
                    if not _LITERAL_VALUE.fullmatch(value):
                        value = None
                found.setdefault(m.group(1), []).append(value)
    return found


def _wrapper_bodies(part: str) -> list[str]:
    """The text each shell wrapper in `part` hands to a shell: its words after
    the wrapper, unquoted and joined, plus a decoded `-EncodedCommand`."""
    bodies: list[str] = []
    for m in _WRAPPER.finditer(_stripped(part)):
        words = [_unquote(part[a:b]) for a, b in _command_words(part, m.end())]
        bodies.append(" ".join(words))
        for flag, value in zip(words, words[1:]):
            if _PS_ENCODED.fullmatch(flag):
                try:
                    bodies.append(base64.b64decode(value).decode("utf-16-le"))
                except (ValueError, UnicodeDecodeError):
                    pass
    return [b for b in bodies if _HAS_GIT.search(b)]


def _resolve(raw: str, names: dict[str, list[str | None]]) -> list[str] | None:
    """The values word `raw` can take, or None when one cannot be known."""
    if not _has_expansion(raw):
        return [_unquote(raw)]
    var = _SINGLE_VAR.fullmatch(raw)
    if var is None:
        return None
    values = names.get(var.group(1) or var.group(2))
    if not values or any(v is None for v in values):
        return None
    return list(dict.fromkeys(values))


def _rewrites(part: str, names: dict[str, list[str | None]]) -> tuple[list[str], bool]:
    """Lines `part` can stand for once one expansion in a git command is
    filled in, and whether some expansion could not be resolved."""
    scanned = _stripped(part)
    lines: list[str] = []
    unresolved = False

    def tail_end(at: int) -> int:
        return _TAIL_RE.match(scanned, at).end()

    for m in _GIT_SUBCOMMAND_EXPANDED.finditer(scanned):
        opts = scanned[m.start(1):m.end(1)].split()
        if not _at_command_start(scanned, m.start()) or (
            opts and _GIT_VALUE_OPT.fullmatch(opts[-1])
        ):
            continue
        sub = m.end()
        end = _word_end(part, sub)
        values = _resolve(part[sub:end], names)
        if values is None:
            unresolved = True
            continue
        stop = tail_end(end)
        lines += [part[m.start():sub] + v + part[end:stop] for v in values]
        if len(lines) > _EXPAND_MAX_LINES:
            return lines, True
    for pattern in (_PUSH, _RESET, _BRANCH):
        for m in pattern.finditer(scanned):
            if not _at_command_start(scanned, m.start()):
                continue
            operand = False
            for a, b in _command_words(part[: m.end(1)], m.start(1)):
                raw = part[a:b]
                if not _has_expansion(raw):
                    operand = operand or not _unquote(raw).startswith("-")
                    continue
                values = _resolve(raw, names)
                if values is None:
                    unresolved = unresolved or (
                        not operand and raw.startswith("$") and _SINGLE_VAR.fullmatch(raw) is not None
                    )
                    continue
                lines += [part[m.start():a] + v + part[b:m.end(1)] for v in values]
                if len(lines) > _EXPAND_MAX_LINES:
                    return lines, True
                break  # the rewritten line is read again for the next one
    return lines, unresolved


def _expand(command: str) -> tuple[list[str], bool]:
    """`command` as a list of parts to read: the command itself, then each
    wrapper body and each rewritten git line. The flag is True when an
    expansion could not be resolved or the reading stopped at its cap."""
    parts = [command]
    budget = len(command) + _EXPAND_SLACK
    frontier = [command]
    for _ in range(_WRAP_DEPTH):
        frontier = [b for p in frontier for b in _wrapper_bodies(p)]
        if not frontier:
            break
        parts += frontier
        budget -= sum(len(b) for b in frontier)
        if budget < 0:
            return parts, True
    else:
        if any(_wrapper_bodies(p) for p in frontier):
            return parts, True
    names = _assignments(parts)
    unresolved = False
    seen = set(parts)
    frontier = list(parts)
    for _ in range(_EXPAND_ROUNDS):
        new: list[str] = []
        for part in frontier:
            lines, missed = _rewrites(part, names)
            unresolved = unresolved or missed
            for line in lines:
                if line not in seen:
                    seen.add(line)
                    new.append(line)
        if not new:
            return parts, unresolved
        parts += new
        budget -= sum(len(line) for line in new)
        if budget < 0 or len(parts) > _EXPAND_MAX_LINES:
            return parts, True
        frontier = new
    return parts, True


@functools.lru_cache(maxsize=4)
def _scan(command: str) -> tuple[str, str, bool]:
    """The text every check reads, its quote-stripped twin (offsets agree),
    and whether `_expand` met an expansion it could not resolve."""
    parts, unresolved = _expand(command)
    if len(parts) == 1:
        return command, _stripped(command), unresolved
    return (
        _PART_SEP.join(parts),
        _PART_SEP.join(_stripped(p) for p in parts),
        unresolved,
    )


def _reasons(command: str, cwd: str) -> list[str]:
    """Every destructive shape present in `command`, as human-readable causes.

    `cwd` is where the command is about to run, and is the working directory
    the working-tree probes are resolved against. Every other check here is
    pure text inspection; those two are the only reason this function needs a
    directory at all.

    `command` is read as `_scan` expands it: wrapper bodies and rewritten git
    lines are part of it from here on, so every check below covers them too.
    """
    started = time.monotonic()
    command, scanned, unresolved = _scan(command)
    found: list[str] = []
    if any(
        _FORCE_FLAG.search(m.group(1)) or _FORCE_REFSPEC.search(m.group(1))
        for m in _PUSH.finditer(scanned)
    ):
        found.append(
            "a force-push, which rewrites a remote branch other worktrees or "
            "collaborators may already have based work on"
        )
    pushes = list(_PUSH.finditer(scanned))
    if pushes and (
        _ALLOW_PUSH_TO_MAIN.search(scanned)
        or _HOOKS_PATH.search(command)
        or any(_NO_VERIFY.search(m.group(1)) for m in pushes)
    ):
        found.append(PUSH_GUARD_SKIP_REASON)
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
    if unresolved:
        found.append(UNRESOLVED_REASON)
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
    # The stash check has its own handler. Sharing the discard check's handler
    # meant a stash-side exception (a NUL in a `-C` path raises ValueError) was
    # logged as the discard check and skipped the discard and clean checks.
    try:
        # At most ONE probe: a command whose stashes run in more than one
        # directory is asked about rather than probed once per directory, which
        # keeps `HOOK_WORST_CASE_SECONDS` at its stated 4 x 3s.
        stash_dirs = _stash_dirs(scanned, command, cwd)
        if len(stash_dirs) > 1:
            found.append(STASH_MULTI_DIR_REASON)
        elif stash_dirs == [None]:
            found.append(STASH_UNCHECKED_REASON)
        elif stash_dirs:
            in_progress = _operation_in_progress(stash_dirs[0])
            if in_progress:
                found.append(STASH_REASON)
            elif in_progress is None:
                found.append(STASH_UNCHECKED_REASON)
    except Exception as exc:  # noqa: BLE001 — see the comment above the `try`
        if STASH_UNCHECKED_REASON not in found:
            found.append(STASH_UNCHECKED_REASON)
        print(
            f"[ask-destructive-git] the stash check raised "
            f"{type(exc).__name__}: {exc} — asking rather than assuming. "
            "(hook: ask-destructive-git.py)",
            file=sys.stderr,
        )

    # Wrapped for the same reason as the stash check: see the comment above it.
    try:
        discard_paths: list[str] = []
        discard_whole_tree = False
        # Accumulated per invocation and unioned, because the kinds at stake are
        # a property of the COMMAND, not of the batch. A first cut decided them
        # once from `discard_whole_tree`, which gave every pathed discard
        # `{"worktree"}` — and `git checkout HEAD -- <path>` and
        # `git restore --staged --worktree <path>` are pathed AND reset the
        # index, so on a staged-but-clean-in-tree file they were silent while
        # really wiping the staged content. Widening the whole `else` branch
        # instead would put the routine prompt back on a bare
        # `git checkout -- <path>`, which is what `_line_kind` exists to avoid.
        discard_wanted: set[str] = set()
        for pattern in (_CHECKOUT, _SWITCH, _RESTORE):
            for m in pattern.finditer(scanned):
                tail = m.group(1)
                if pattern is _RESTORE:
                    if _RESTORE_STAGED.search(tail):
                        if not _RESTORE_WORKTREE.search(tail):
                            continue
                        # `--staged --worktree` resets the index by definition.
                        discard_wanted.add("index")
                elif _FORCE_DISCARD.search(tail):
                    # Force overrides git's own refusal, so the operands say
                    # nothing about the blast radius — the whole tree is at risk,
                    # in all three columns. `untracked` belongs here because `-f`
                    # also overrides git's refusal to clobber an untracked file
                    # colliding with one in the target branch: measured, a tree
                    # holding only `?? collide.txt` was silent, and the real
                    # command overwrote it with the branch's version.
                    discard_whole_tree = True
                    discard_wanted |= {"worktree", "index", "untracked"}
                    continue
                elif pattern is _SWITCH:
                    # `git switch` is matched ONLY in its forced form, which the
                    # branch above has already taken. Falling through to
                    # `_operands` contributed the BRANCH NAME to the probe, so
                    # `git switch -c docs` prompted whenever a `docs/` path was
                    # dirty — pure false-positive surface, since a bare switch
                    # refuses on conflict. The module docstring claimed this
                    # `continue` existed before it did.
                    continue
                if pattern is _CHECKOUT and _names_a_tree_ish(tail):
                    # `git checkout HEAD -- <path>` writes the named tree into
                    # the index too.
                    discard_wanted.add("index")
                discard_wanted.add("worktree")
                discard_paths += _operands(tail, command[m.start(1):m.end(1)])
        if discard_whole_tree or discard_paths:
            if _holds_work(
                cwd,
                [] if discard_whole_tree else discard_paths,
                discard_wanted,
                "ignored" in discard_wanted,
                whole_tree,
            ):
                found.append(
                    WHOLE_TREE_REASON if discard_whole_tree else DISCARD_REASON
                )

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
    except Exception as exc:  # noqa: BLE001 — see the comment above the `try`
        # A DISTINCT reason, not `DISCARD_REASON`. That text ends "the path(s)
        # named here hold such changes right now", which is a measurement — and
        # this is the one branch where nothing was measured. Reusing it made the
        # prompt assert a fact it did not have, in exactly the case where the
        # guard is blind, and for commands (`git clean -fdx`, `git switch -f`)
        # that name no path and run no checkout.
        if UNCHECKED_REASON not in found:
            found.append(UNCHECKED_REASON)
        # stderr from an exit-0 hook reaches the debug log only, so this costs
        # nothing and is the difference between a guard silently degraded for
        # weeks and a report someone can act on.
        print(
            f"[ask-destructive-git] the working-tree discard check raised "
            f"{type(exc).__name__}: {exc} — asking rather than assuming. "
            "(hook: ask-destructive-git.py)",
            file=sys.stderr,
        )

    # After every probe above, never before: these spend only the time those
    # left (`_PROBE_BUDGET_SECONDS`). Fail open, unlike the two handlers above;
    # the section comment says why.
    try:
        found += _history_reasons(command, scanned, cwd, started)
    except Exception as exc:  # noqa: BLE001 — see the comment above the `try`
        print(
            f"[ask-destructive-git] the rebase and branch-change check raised "
            f"{type(exc).__name__}: {exc} — not asking about them. "
            "(hook: ask-destructive-git.py)",
            file=sys.stderr,
        )

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
        or _every_merge_is_authorized(_scan(command)[1])
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
    # command text (`_every_merge_is_authorized`, above). Force-push and
    # `reset --hard` have no narrow equivalent, so those (and any mix that
    # includes them) still name the broad, env-only variable — worded as
    # "export" so the inline/environment distinction is explicit.
    #
    # `found == [MERGE_REASON]` depends on `_reasons()` always appending in
    # the fixed order force-push, reset --hard, branch force-delete, stash, working-tree
    # discard (or the forced whole-tree one), clean, unchecked, rebase, branch
    # reset, merging switch, merge — never in
    # the order the command text names them. Only one property is load-bearing:
    # MERGE STAYS LAST, and it does so structurally, because its check is the
    # only one outside the `try` above and sits after it. That is what makes list
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
