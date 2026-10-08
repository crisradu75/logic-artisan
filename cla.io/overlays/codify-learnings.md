# codify-learnings — project context overlay

<!--
Project-specific overlay for the `codify-learnings` cla skill. This file is repo-local
(never distributed with the plugin). The generic SKILL.md supplies the procedure; this
file supplies the repo's facts: where memory lives, the verification commands, and the
repo lessons that Step 2 searches before calling a failure new.
-->

## Memory index glob

`~/.claude/projects/C--code-logic-artisan/memory/` — index file `MEMORY.md`, one fact per
sibling `*.md`. On Windows that resolves to
`C:\Users\<user>\.claude\projects\C--code-logic-artisan\memory\`.

There is exactly one such directory for this repo; if a glob ever matches more than one,
prefer the one whose slug matches this repo's path (`C--code-logic-artisan`).

## Repo stack + verification path

Verification path for this repo — a change is not "done" until the suite passes:

```bash
pytest plugin-tests -q -n auto --dist loadfile   # the whole suite: the gate
pytest plugin-tests/tests/hooks -n auto --dist loadfile   # one area, while iterating
pytest plugin-tests -k <name>            # one subject, across areas
node --test plugin-tests/node/mechanical-checks.test.mjs
```

`-n auto --dist loadfile` needs `pytest-xdist` and takes the suite from ~204s to ~74s.
Use `--dist loadfile`, never plain `-n auto`, and keep the flags off `addopts` so
`mutate.py` stays serial — CLAUDE.md's "The parallel gate" has the reasons.

The plugin's own tests do NOT live in the plugin. `.claude/plugins/cla/` ships to
consuming repos and carries only assets a consumer can use, so every test, mutation
batch and pytest config lives in this repo's own `plugin-tests/` tree instead.

There is no CI — the local commands above are the whole verification story. Run the
pytest gate plus the Node suite before calling a change done.

The suite reports skips — a skipped guard has not run, and several guards are
dormant without an overlay file, so treat a skip line as a finding rather than noise.

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

## Repo file lists

Docs that must stay in lockstep with the code:
- root `CLAUDE.md` — skill table, scope count, guard-hook list, commands
- `.claude/plugins/cla/skills/*/SKILL.md` and their `references/*.md`
- `.claude/plugins/cla/hooks/_dispatch_lib.py` — `HOOK_WORST_CASE_SECONDS` must match each
  hook's real (call sites × timeout). The wiring test
  (`plugin-tests/tests/hooks/test_hooks_wiring.py`) asserts that every dispatched
  hook HAS an entry, that no entry is stale, and that the enforcing hooks' sum fits the
  handler budget — what it never verifies is that a given number matches that hook's real
  (call sites × timeout), so a wrong-but-small value passes silently
