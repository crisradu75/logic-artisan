#!/usr/bin/env python3
"""PostToolUse (Write): warn when a wholesale rewrite silently drops content.

A `Write` to an existing tracked file replaces it entirely. That is the shape in
which content disappears without anyone deciding to remove it: the new version
reads well on its own, so nothing prompts a comparison against what it replaced.

The incident that added this hook: an output-style file was rewritten 121 -> 93
lines. Review found four separate rules dropped with no intent behind any of
them -- an anti-telegraphic-writing rule, a scope statement, and two exemptions
that a table depended on. Every one had survived the previous edit-based changes
to the same file. The same session had already shipped a rewritten guard whose
replacement lost six behaviours the original had.

So this fires on `Write`, never `Edit`. An `Edit` is surgical: whatever it does
not name, it keeps. A `Write` keeps only what the author remembered to carry
across, and remembering is exactly what fails.

It warns, never blocks. Deliberate shortening is common and legitimate -- this
hook cannot tell a good cut from a lost rule, and should not try. Its whole job
is to make the author say which one it was, at the moment they still remember.

Measured in WORDS, not lines. Line count is the obvious proxy and the wrong one:
re-wrapping a hard-wrapped markdown file at a different column drops a fifth of
its lines while losing not one word, and in a plugin whose behaviour lives mostly
in markdown that reflow case would have been the single largest source of false
warnings. Whitespace-split word count is unmoved by reflow and still falls the
moment real content goes.

Baseline is `git show HEAD:./<path>`, so an untracked or brand-new file is silent
(nothing was replaced) and a shrink is measured against the last committed state.
Several small writes across one session therefore accumulate rather than each
resetting the baseline, which is the behaviour that matches the risk.

The `./` in that revspec is load-bearing, not decoration. A bare `HEAD:<path>` is
resolved from the REPOSITORY TOP LEVEL and ignores `-C` entirely, so with a
project dir below the repo root every lookup either missed (silent hook, forever,
no signal) or -- worse -- resolved a same-named file at the root and reported a
loss that never happened. `./` makes the path relative to `-C`.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

# Below this the file is too small for a "shrink" to mean anything -- trimming a
# stub, tightening a short list. In words, so it tracks content and not wrapping.
MIN_BASELINE_WORDS = 150

# Fraction of the committed file that must survive before this stays quiet.
KEEP_RATIO = 0.85

# ...and an absolute floor, so a small file just over MIN_BASELINE_WORDS cannot
# trip the ratio by losing a sentence. Replaying the ratio rule over this repo's
# own history showed every genuine event dropping far more than this, so the
# floor costs no real signal and removes the whole small-file noise band.
MIN_DROPPED_WORDS = 80

# 3s, matching `_dispatch_lib.GIT_TIMEOUT_SECONDS`, not 5.
#
# The outside-project path now chains THREE subprocesses — `_repo_root_for`,
# then the `git show`, then `_head_exists` — so at 5s each the worst case was
# 15s against a hooks.json PostToolUse timeout of exactly 15. A wedged git would
# kill the handler, which is the "silently stopped guarding" shape this hook
# exists to catch. At 3s the worst case is 9s, inside the budget.
#
# Not covered by `HOOK_WORST_CASE_SECONDS`: that table is asserted to contain no
# entries for undispatched hooks, and this one is wired directly on PostToolUse.
# So the bound has to be right here rather than caught by the wiring test.
_GIT_TIMEOUT_SECONDS = 3


def _word_count(text: str) -> int:
    """Whitespace-delimited words. Immune to re-wrapping; falls when content goes."""
    return len(text.split())


def _repo_root_for(file_path: Path) -> Path | None:
    """The git work-tree root containing `file_path`, or None if there is none.

    Exists because `CLAUDE_PROJECT_DIR` is the LAUNCH directory, not "the repo
    being edited". A session that enters a git worktree after launch writes every
    file outside it, so keying solely off that variable made this hook return 0
    for the rest of the session -- a guard that silently stopped guarding, in a
    plugin whose own tooling (`/cla:new-worktree`, worktree helpers)
    makes that the common path rather than an edge case.

    Called ONLY when the path falls outside the project dir, so the ordinary
    same-repo write pays nothing for it.
    """
    try:
        result = subprocess.run(
            ["git", "-C", str(file_path.parent), "rev-parse", "--show-toplevel"],
            capture_output=True,
            timeout=_GIT_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    root = result.stdout.decode("utf-8", "replace").strip()
    if not root:
        return None
    try:
        return Path(root).resolve()
    except OSError:
        return None


def _head_exists(repo: Path) -> bool:
    """True when `repo` is a git repo with at least one commit.

    Separates "there is no baseline" (not a repo, or no commits yet -- both
    legitimately silent) from "there IS a baseline and this hook still could not
    find the path", which is a real defect worth announcing.

    Replaces matching two English phrases out of git's stderr. Neither
    `fatal: not a git repository` nor `fatal: invalid object name 'HEAD'`
    contains either phrase, so the diagnostic printed on every Write in a scratch
    directory -- and phrase-matching breaks under a non-English `LANG` for every
    case. Asking git the question is locale-independent, and it costs one
    subprocess only on the already-failed path.
    """
    try:
        return subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "--verify", "--quiet", "HEAD"],
            capture_output=True,
            timeout=_GIT_TIMEOUT_SECONDS,
        ).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def _committed_word_count(repo: Path, rel_path: str) -> int | None:
    """Words in `rel_path` at HEAD, or None when there is no usable baseline.

    None means "nothing to compare against" -- untracked, brand new, no commits
    yet, not a repo, git missing, or binary. Every one of those is a legitimate
    silent no-op.

    The exception is a git that RAN and still could not resolve the path: that
    means this hook built the path wrong, not that the file is new. Nothing else
    in a session reveals that, and a guard that is silently dead looks exactly
    like a guard that ran and approved -- so it says so on stderr and still
    returns None. Fail open, degrade loudly.
    """
    try:
        result = subprocess.run(
            ["git", "-C", str(repo), "show", f"HEAD:./{rel_path}"],
            capture_output=True,
            timeout=_GIT_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.SubprocessError):
        # git absent, or wedged past the timeout. Not worth a message: anything
        # else the session does with git fails visibly in the same breath.
        return None

    if result.returncode != 0:
        # No HEAD at all -- not a repo, or no commits yet -- is an environment
        # condition with no baseline to compare against, not a path this hook
        # built wrong. Silent, and asked as a QUESTION rather than read out of
        # git's prose: the phrase test below cannot see this case (neither
        # `fatal: not a git repository` nor `fatal: invalid object name 'HEAD'`
        # contains either phrase), which is why the diagnostic used to print on
        # every Write in a scratch directory.
        if not _head_exists(repo):
            return None
        # There IS a baseline. A path that still will not resolve against it
        # means either the file is simply not in HEAD (untracked or new --
        # ordinary, silent) or this hook built the path wrong, which nothing
        # else in a session reveals and which a silently-dead guard makes
        # indistinguishable from one that ran and approved.
        err = result.stderr.decode("utf-8", "replace")
        if "does not exist in" not in err and "exists on disk" not in err:
            print(
                f"[warn-wholesale-rewrite] disabled for this write: git could not "
                f"resolve {rel_path!r} in HEAD ({err.strip()[:160]})",
                file=sys.stderr,
            )
        return None

    try:
        return _word_count(result.stdout.decode("utf-8"))
    except UnicodeDecodeError:
        return None  # binary blob: no word count to compare


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0
    if not isinstance(payload, dict):
        return 0

    # Edit preserves what it does not name; only Write can drop content silently.
    if payload.get("tool_name") != "Write":
        return 0

    tool_input = payload.get("tool_input")
    raw_path = tool_input.get("file_path", "") if isinstance(tool_input, dict) else ""
    if not isinstance(raw_path, str) or not raw_path:
        return 0

    try:
        project_root = Path(os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())).resolve()
        file_path = Path(raw_path)
        file_path = (project_root / file_path) if not file_path.is_absolute() else file_path
        file_path = file_path.resolve()
    except OSError:
        # A deleted cwd, or a path component on a disconnected drive. This hook
        # must never be the thing that raises inside someone's tool call.
        return 0

    # The write is usually inside the launch directory. When it is not -- the
    # worktree case, which this plugin's own tooling makes routine -- fall back
    # to the work tree that actually contains the file. Returning 0 here instead,
    # as this hook originally did, switched it off for the rest of any session
    # that entered a worktree, with no output to say so.
    repo_root = project_root
    try:
        rel = file_path.relative_to(project_root).as_posix()
    except ValueError:
        found = _repo_root_for(file_path)
        if found is None:
            return 0  # genuinely outside any repo; not ours to judge
        try:
            rel = file_path.relative_to(found).as_posix()
        except ValueError:
            return 0
        repo_root = found

    baseline = _committed_word_count(repo_root, rel)
    if baseline is None or baseline < MIN_BASELINE_WORDS:
        return 0

    try:
        new_words = _word_count(file_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError):
        # File vanished between the write and this hook, or was replaced with
        # non-text -- either way there is nothing countable to compare.
        return 0

    dropped = baseline - new_words
    if dropped < MIN_DROPPED_WORDS or new_words >= baseline * KEEP_RATIO:
        return 0

    pct = round(100 * dropped / baseline)
    msg = (
        f"[warn-wholesale-rewrite] {rel}: replaced {baseline} committed words "
        f"with {new_words} ({pct}% shorter, {dropped} words gone).\n"
        "A Write keeps only what you carried across. Before calling this done, "
        "diff it against the committed version and say what you dropped and why "
        "— naming the cuts is the check; a shorter file is not evidence that "
        "nothing was lost."
    )
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": msg,
        }
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
