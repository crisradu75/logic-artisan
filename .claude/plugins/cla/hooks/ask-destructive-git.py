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
  after this destroyed a commit holding 45 sections of run notes, recovered only via `git reflog` plus `git show <sha>:<path>`.

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
  exclusion said "revisit only with evidence of a real incident", and an
  incident is that evidence: a `git checkout <file>` run mid-implementation to undo a
  hand-edit restored the file from the index — the PRE-implementation state —
  erasing ~50 lines of uncommitted work, with no reflog entry and nothing to
  recover from. The trap is that `git checkout <file>` READS as "undo my last
  edit" while it means "reset to the index"; those coincide only when the file
  was clean before you touched it, which is exactly the case that does not hold
  mid-implementation, and also when the loss is most expensive.

  The noise objection is answered by a CONDITION rather than by dropping the
  rule, because these commands only destroy something when their paths are
  dirty. `_holds_work` (in `_destructive_git_probes.py`) probes that. On a clean path the command is a
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
  (in the incident that added this check, one side of about 47 files, noticed
  only because the test count dropped). The prompt names the safe alternatives, `git show <ref>:<path>` and
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
- A push that skips the `pre-push` guard: `--no-verify` (down to `--no-veri`),
  `-c core.hooksPath=...`, or one of that hook's own overrides typed into the
  command, `ALLOW_PUSH_TO_MAIN=1` (a push to the default branch) or
  `ALLOW_TAG_REWRITE=1` (deleting or moving a remote tag). That guard is the only
  one on the default branch and on remote tags, and each of these skips it
  without a word.
- `git push --mirror` (down to `--m`), which deletes every remote branch and tag
  the clone lacks, the default branch included; git never hands those deletions
  to the `pre-push` guard. Its own reason. Known miss: a remote configured to
  mirror (`git remote add --mirror=push`) mirrors on a plain `git push`.
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
  deep (a fourth level asks), when a git subcommand or a `push`/`reset`/`branch`
  flag is quoted (`git push "-f"`) or comes from a `$NAME` the same command
  assigns a literal (`X=push; git $X -f`). A git subcommand from any other
  expansion (`git $X`, `git "$@"`, `git pu$X`), a flag with an unknown
  expansion glued on (`--force$X`), or an unquoted unassigned `$NAME` among a
  push, reset or branch's options (`git push $F origin x`), asks as
  unresolved. `_expand` (in `_shell_read.py`) has the rules and the named
  misses, among them a
  backtick span that opens on an earlier line (or across a `\`-newline) and
  closes on git's line: a substituted flag later on that line is not read,
  and a git word glued to that closing backtick asks. One named false ask:
  prose (a heredoc commit message, say) that lists four or more wrapper names
  in code spans, with the word git somewhere after them, can read as wrappers
  nested past the cap and ask. `bash -c "git status"`
  and `eval "$(ssh-agent)"` stay silent. Its reading is linear and
  capped, so no command keeps the hook past its handler timeout.

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

import functools
import json
import os
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

# This hook is four files. Here: the decision (`_reasons`) and `main`. The
# shared shell reading every Bash guard uses is `_shell_read.py`; the rule
# tables and text classifiers are `_destructive_git_rules.py`; the git probes
# and the one deadline they share are `_destructive_git_probes.py`. Every name
# the decision uses is imported here by name, so a test or a mutant batch that
# reaches one through this module still finds it. A test that REPLACES one
# patches the module that looks it up (`_destructive_git_probes` for every git
# call): `_run_git` and the probe budget are deliberately not imported here,
# so patching them on this module fails loudly instead of changing nothing.
from _dispatch_lib import strip_quoted_spans as _strip_quoted_spans  # noqa: E402,F401
from _shell_read import (  # noqa: E402,F401
    _BRANCH,
    _EXPAND_MAX_LINES,
    _EXPAND_ROUNDS,
    _EXPAND_SLACK,
    _PART_SEP,
    _PUSH,
    _RESET,
    _WORK_FACTOR,
    _WRAP_DEPTH,
    UNRESOLVED_REASON,
    WRAP_DEPTH_REASON,
    _abbrev,
    _expand,
    _stripped,
    _unquote,
    expand,
)
from _destructive_git_rules import (  # noqa: E402,F401
    _ALLOW_PUSH_TO_MAIN,
    _CHECKOUT,
    _CLEAN,
    _CLEAN_ALSO_IGNORED,
    _CLEAN_DRY_RUN,
    _CLEAN_FORCE,
    _CLEAN_IGNORED_ONLY,
    _FORCE_DISCARD,
    _FORCE_FLAG,
    _FORCE_REFSPEC,
    _GH_PR_MERGE,
    _HARD_FLAG,
    _HOOKS_PATH,
    _MIRROR_FLAG,
    _NO_VERIFY,
    _RESTORE,
    _RESTORE_STAGED,
    _RESTORE_WORKTREE,
    _SWITCH,
    BRANCH_RESET_REASON,
    CLEAN_REASON,
    DISCARD_REASON,
    MERGE_REASON,
    MERGE_SWITCH_REASON,
    MIRROR_REASON,
    PUSH_GUARD_SKIP_REASON,
    REBASE_REASON,
    STASH_MULTI_DIR_REASON,
    STASH_REASON,
    STASH_UNCHECKED_REASON,
    UNCHECKED_REASON,
    WHOLE_TREE_REASON,
    _config_key,
    _config_overrides,
    _every_merge_is_authorized,
    _force_deletes_a_branch,
    _line_kind,
    _names_a_tree_ish,
    _operands,
    _stash_dirs,
)
from _destructive_git_probes import (  # noqa: E402,F401
    _Probes,
    _status_lines,
    _history_reasons,
    _holds_work,
    _is_true,
    _operation_in_progress,
    _replays_nothing,
)


@functools.lru_cache(maxsize=4)
def _scan(command: str) -> tuple[str, str, str | None]:
    """The text every check reads, its quote-stripped twin (offsets agree),
    and the reason to ask when `_expand` could not read all of it (None when
    it could). The expansion is `_shell_read.expand`'s cached one, which the
    dispatcher has usually computed already for the other guards."""
    parts, unread = expand(command)
    if len(parts) == 1:
        return command, _stripped(command), unread
    return (
        _PART_SEP.join(parts),
        _PART_SEP.join(_stripped(p) for p in parts),
        unread,
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
    command, scanned, unread = _scan(command)
    # Every git call below, fail-closed or fail-open, draws on this one
    # deadline: `_destructive_git_probes.py` says how it bounds the hook.
    probes = _Probes(started)
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
    if any(_MIRROR_FLAG.search(m.group(1)) for m in pushes):
        found.append(MIRROR_REASON)
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
    if unread:
        found.append(unread)
    # Operands are collected across EVERY matching invocation in the command and
    # asked in one `git status` each, so a `&&` chain of six checkouts is two
    # subprocesses, not twelve. Three is the ceiling: those two plus the shared
    # whole-tree fallback below, which is memoised so a batch refusal on both
    # halves still costs one. The time they spend is bounded by `probes`'
    # deadline, not by their count; the count keeps a long chain from spending
    # it on one probe per invocation.
    tree_cache: list = []

    def whole_tree():
        if not tree_cache:
            # `--ignored` unconditionally, so one cached answer serves the
            # discard check and a `git clean -x` alike.
            tree_cache.append(_status_lines(cwd, [], ignored=True, probes=probes))
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
        # directory is asked about rather than probed once per directory, so a
        # chain of stashes cannot spend the shared deadline one by one.
        stash_dirs = _stash_dirs(scanned, command, cwd)
        if len(stash_dirs) > 1:
            found.append(STASH_MULTI_DIR_REASON)
        elif stash_dirs == [None]:
            found.append(STASH_UNCHECKED_REASON)
        elif stash_dirs:
            in_progress = _operation_in_progress(stash_dirs[0], probes)
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
                probes,
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
            probes,
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

    # After every probe above, never before: these spend only what those left
    # of the shared deadline, so the fail-closed checks are the ones a slow git
    # cannot starve. Fail open, unlike the two handlers above; the section
    # comment above `_REBASE` in `_destructive_git_rules.py` says why.
    try:
        found += _history_reasons(command, scanned, cwd, probes)
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
    # the fixed order force-push, mirror push, push-guard skip, reset --hard,
    # branch force-delete, unread, stash, working-tree
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
