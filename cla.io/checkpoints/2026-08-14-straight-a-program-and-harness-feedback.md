# Checkpoint — 2026-08-14 — straight-A program, 0.10.0, and the harness-feedback round

## Where things stand

The CLA plugin went from a `SOLID` project-review verdict (C/C/B/B/B) to `0.10.0`
released, via an 11-change remediation program run through the harness's own
orchestrators. Everything from that program is merged. Since the release: three
docs PRs, a consumer-correctness PR, two feature PRs, and a placement round — all
merged. One PR is open (#80, this session's `codify-learnings` output) and the
working tree sits on its branch, clean. `main` is at `5b34448`; the branch adds
one commit, `b997789`. Twelve test scopes green throughout, one pre-existing
win32 skip.

## Landed

| PR | Subject |
|---|---|
| #69 | `release: 0.10.0` — tag `cla--v0.10.0` |
| #70 | README leads with the marketplace install; dev-mode demoted and scoped |
| #71 | Credit the OpenSpec and Anthropic skills CLA builds on |
| #72 | Guide section 2 splits by audience — consumer start vs harness-dev launcher |
| #73 | Consumer correctness: source-only scopes, sweep accounting, `git_state` naming |
| #74 | Shared skill-authoring doctrine + conflict-resolution procedure |
| #75 | Test-quality rules, deletion test, claim-density gate, plugin-repo review fallback |
| #76 | Reconcile TODO with the fix-all round |
| #77 | `multi-pr` argument binding, dangling slash-command lint, size-gate contradiction |
| #78 | Harness feedback loops — commit provenance, guard-the-guards, cost telemetry, `checkpoint` |
| #79 | Test-quality to Implement, conflict ownership split, trim `CLAUDE.md` and `spec-to-pr` |

Also merged earlier in the program: the stacked-chain mode branch (#68) and the
`release` skill (#67).

## In flight

- **PR #80 — `chore/codify-learnings-guard-evasion`** (open, base `main`).
  Deliberately not merged: merge authorization is per-artifact in this repo and
  was never given for this one.
  **Next action:** review it, then
  `ALLOW_PR_MERGE=1 gh pr merge 80 --squash --delete-branch`. Nothing depends on
  it and nothing is stacked on it.

- **The working tree is on that branch, not `main`.**
  **Next action:** after merging, `git -C <repo> checkout main && git pull && git fetch --prune`.

## Decided

- **`/cla:diagnose` is shaped and approved but not built.** Seven questions
  answered in `cla.io/decisions/diagnose-skill-2026-08-14.md`; that doc, not the
  original `mattpocock/skills` comparison, is the spec. Do not re-shape it.
- **No CI, still.** Reaffirmed rather than revisited. `run_tests.py` is the whole
  gate. If a change seems to need a workflow, raise it instead of adding one.
- **A published tag is never moved.** `cla--v0.10.0` is cut from reviewed `main`
  and stays where it is.
- **Squash is wrong for a stacked chain; merge commits are right.** Decided from a
  throwaway 5-phase empirical test, not from the docs. Landing order is
  retarget-child-first, then merge the parent.
- **Decided NOT to:** add a general "no shadowing any guarded command" check.
  `block-cd-in-bash` covers `cd` only; `git`/`rm`/`gh` are shadowable the same way
  and were left alone deliberately — one real offense, one narrow fix. Revisit
  only if the evasion recurs against a different guard.

## Open questions

- **Does the plugin work in a consuming repo?** Still the 1.0.0 gate. Installing
  and resolving paths is verified; running a real task end-to-end through the
  installed plugin is not. Settled by doing exactly that in a consumer.
- **What is the real skill-adoption rate?** `log-commit-provenance.py` is merged
  and wired but has never fired — hooks are read at plugin load, so it could not
  observe the session that created it. Settled by the first `cla.io/retro/commit-provenance.jsonl`
  lines appearing next session. The baseline it exists to replace, with the
  commands, measured at the end of this session:
  `git rev-list --count --no-merges 6bf0755..main` → 31, and
  `wc -l < cla.io/retro/spec-to-pr-runs.jsonl` → 1.
- **Is `/cla:checkpoint` any good?** This file is its first output, and it was
  produced by following the procedure by hand rather than by invoking the skill
  (see Traps). Settled by a real invocation next session.

## Traps

- **A skill or hook added mid-session is not invocable in that session.** The
  plugin registry and `hooks.json` are read at load. `Skill(cla:checkpoint)`
  returned `Unknown skill` despite the file being merged on disk two PRs earlier.
  Restart the session — do not debug the skill.
- **`gh pr merge --delete-branch` CLOSED a dependent PR** (#64), contradicting
  GitHub's documented retargeting. Recovery took a branch restore from
  `git rev-parse origin/main^2`, a push, `gh pr reopen`, and `gh pr edit --base main`.
  Retarget children *before* merging a parent.
- **Six claims stated as measured were not**, in one day. Five caught by review,
  one by production. `CLAUDE.md` check 3 now covers measurement claims — name the
  command or delete the claim.
- **Two shipped guards asserted nothing** and both read as correct. One greped for
  a function's name instead of calling it; one lost its `problems.append`, leaving
  `assert not []`. Only mutation found them. A green suite says the assertions
  passed, never that they could fail.
- **Do not author file content through a bash heredoc.** Four separate corruptions
  this session: `\n` collapsing to real newlines, `\b` becoming `\x08`, a literal
  null byte, and one file with every line doubled. Use `Write`/`Edit`, or `Write`
  a script and run it by absolute path.
- **`json.dumps` round-tripping `hooks.json` double-escapes every command string**
  and breaks three wiring tests. Edit that file as text.
- **The `cd` guard blocks a bare `cd` even in a read-only command.** Use
  `git -C <abs-path>` and absolute paths. Shadowing `cd` to get past it is now
  itself blocked, and was always the wrong move.

## Procedure notes from this first run

Recorded because the skill has never been invoked and this is the only evidence
about it:

- **Section 3 ("In flight") did most of the work**, as its own SKILL.md predicts.
  Sections 2 and 4 were mechanical.
- **"Omit a section if genuinely empty" was never exercised** — all six had real
  content. Untested branch.
- **The skill cannot report on the case that produced it.** It is written to be
  invoked, and the one thing a next session most needs to know here is that
  invoking it failed. That went in Traps, but nothing in the procedure prompts
  for "what went wrong with this skill".
