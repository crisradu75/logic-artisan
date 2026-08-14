# codify-learnings — project context overlay

<!--
Project-specific overlay for the `codify-learnings` cla skill. This file is repo-local
(never distributed with the plugin). The generic SKILL.md supplies the procedure; this
file supplies the repo's facts. A skill runs fine against an empty stub — fill in
only the sections its SKILL.md references, delete the rest.
-->

## Default scope note

`repo-wide`. This repo holds no product code — it is the CLA harness itself
(`.claude/plugins/cla/`), so almost every session touches skills, hooks, or both and
repo-wide is the honest default.

Narrow only when a session was genuinely dominated by one area, e.g.:
- `scope: repo-wide (.claude/plugins/cla/hooks/)` — a session spent entirely in the guard layer
- `scope: repo-wide (cross-repo port from <peer-repo>)` — porting skills in from a peer

## Memory index glob

`~/.claude/projects/C--code-logic-artisan/memory/` — index file `MEMORY.md`, one fact per
sibling `*.md`. On Windows that resolves to
`C:\Users\<user>\.claude\projects\C--code-logic-artisan\memory\`.

There is exactly one such directory for this repo; if a glob ever matches more than one,
prefer the one whose slug matches this repo's path (`C--code-logic-artisan`).

## Repo stack + verification path

Verification path for this repo — a change is not "done" until the aggregated suite passes:

```bash
python3 .claude/plugins/cla/run_tests.py        # every pytest scope, aggregated
python3 .claude/plugins/cla/run_tests.py -q     # extra args forwarded to each scope
pytest .claude/plugins/cla/skills/<name>/tests  # one scope, while iterating
pytest .claude/plugins/cla/hooks/tests          # the hooks scope
node --test .claude/plugins/cla/skills/project-review/scripts/mechanical-checks.test.mjs
```

Never run bare `pytest` from the repo or plugin root — collection fails by design.

There is no CI — the local commands above are the whole verification story. Run
`run_tests.py` (every scope) plus the Node suite before calling a change done.

Scope count (skills with tests, plus `hooks/`) is stated in root `CLAUDE.md`, which owns
that fact — read it there rather than duplicating the number here. `run_tests.py`
reports per-scope skip counts — a skipped guard has not run, and several guards are
dormant without an overlay file, so treat a skip line as a finding rather than noise.

## Packages, paths, and app names

- Synced core (portable, no repo facts): `.claude/plugins/cla/{skills,agents,hooks,output-styles}/`
- Overlays (repo-local, never synced): each skill's `references/project-context.md`, any `*.local.md`
- Per-repo state: `cla.io/` — `decisions/`, `feedback/`, `retro/`, `lessons-learned/`
- Worktree convention: `.claude/worktrees/<name>` in the primary clone

## Incident / offense history

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

## Product / domain context

`logic-artisan` is the canonical home of CLA (Cris Logic Artisan), a Claude Code
dev-workflow harness packaged as a plugin. No application code — the deliverable is the
process layer, installed by other repos from the GitHub marketplace.

## Infrastructure values

No servers, ports, or env files. Behaviour-affecting env vars are the hooks' own escape
hatches: `ALLOW_PUSH_TO_MAIN`, `ALLOW_SHARED_CLONE_MUTATION`, `ALLOW_WORKTREE_PATH_ESCAPE`,
`ALLOW_DESTRUCTIVE_GIT`, `ALLOW_GIT_IDENTITY_MISMATCH`, `ALLOW_DATED_PROSE`,
`ALLOW_UNSAFE_RM`, `CLA_EXPECTED_GIT_EMAIL`. This list drifts as hooks are added — the
authoritative enumeration is the hook sources themselves:

```bash
grep -ohE '"(ALLOW|CLA)_[A-Z_]+"' .claude/plugins/cla/hooks/*.py | sort -u
```

## Repo file lists

Docs that must stay in lockstep with the code:
- root `CLAUDE.md` — skill table, scope count, guard-hook list, commands
- `.claude/plugins/cla/skills/*/SKILL.md` and their `references/*.md`
- `.claude/plugins/cla/hooks/_dispatch_lib.py` — `HOOK_WORST_CASE_SECONDS` must match each
  hook's real (call sites × timeout). The wiring test
  (`.claude/plugins/cla/hooks/tests/test_hooks_wiring.py`) asserts that every dispatched
  hook HAS an entry, that no entry is stale, and that the enforcing hooks' sum fits the
  handler budget — what it never verifies is that a given number matches that hook's real
  (call sites × timeout), so a wrong-but-small value passes silently
