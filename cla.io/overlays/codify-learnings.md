# codify-learnings — project context overlay

<!--
Project-specific overlay for the `codify-learnings` cla skill. This file is repo-local
(never distributed with the plugin). The generic SKILL.md supplies the procedure; this
file holds this skill's own settings here: where memory lives, and the repo lessons that Step 2
searches before calling a failure new. Commands and file lists are in `cla.io/project-facts.md`.
-->

## Memory index glob

`~/.claude/projects/C--code-logic-artisan/memory/` — index file `MEMORY.md`, one fact per
sibling `*.md`. On Windows that resolves to
`C:\Users\<user>\.claude\projects\C--code-logic-artisan\memory\`.

There is exactly one such directory for this repo; if a glob ever matches more than one,
prefer the one whose slug matches this repo's path (`C--code-logic-artisan`).

## Verification

The verification commands are in `cla.io/project-facts.md`. A change is not "done" until the gate
passes. The suite reports skips — a skipped guard has not run, and several guards are dormant
without an overlay file, so treat a skip line as a finding rather than noise.

## Incident / offense history

- **2026-08-13 — a guard hook was evaded rather than obeyed.** `block-cd-in-bash` blocked
  a call, and the response was `cd() { echo "blocked"; }; cd /tmp && …` — shadowing `cd`
  so the matcher saw a no-op. The guard was correct and `git -C <dir>` was available. Fixed
  at the hook (`shadows_cd`, 34 tests, 10 mutants) and in memory
  (`feedback-never-route-around-a-guard`).
- **2026-08-13 — `gh pr merge --delete-branch` CLOSED a dependent PR.** GitHub's docs say
  a deleted branch retargets its child PRs; PR #64 was closed instead, and had to be
  restored from `origin/main^2` and reopened by hand. The prose asserting the documented
  behaviour had been written and shipped hours earlier. The landing recipe is now
  retarget-child-first, merge-commits, never squash on a stack.
- **2026-08-13 — six claims stated as measured were not.** Caught by review (five) and
  production (one) in a single day. One comment declared a token absent in text that
  contained it; two were invented blockers that measurement disproved. `CLAUDE.md` check 3
  now covers measurement claims, not only diagnoses.
- **2026-08-13 — two shipped guards asserted nothing.** One greped for a function's name
  instead of calling it; one lost its `problems.append` in an edit, leaving
  `assert not []`. Both passed cleanly and were caught only by mutation. (A static guard
  for this, `test_guards_are_not_vacuous.py`, was later deleted with the meta guard tier.)
- **2026-08-06 — a review sub-agent changed repository state.** A dispatched agent briefed
  "make NO edits" ran `git checkout` to read a branch and restored to `main` rather than the
  branch the session was on; four subsequent verification commands answered about the wrong
  tree. Fix landed in `spec-to-pr/references/subagent-brief.md` (do-not-touch must name
  repository-state verbs, not just files).
- **2026-08-06 — four rounds spent reasoning from the repo's own docstrings** about an
  external hook contract that the code contradicted, when one fetch of the published docs
  settled it. See memory `feedback-read-primary-source-first`.
- **2026-08-06 — a resource ceiling picked before its consumers.** Git timeouts were
  squeezed to fit a chosen 10s handler budget, which made a *blocking* guard fail open under
  load; the handler was later sized from the guards instead.
- **2026-07-25 — the push-to-main guard (now `hooks/git/pre-push`) did not fire** on `git -C <dir> push origin main`;
  the sibling hooks had the same global-flag gap.
