# logic-artisan

Canonical home of **CLA — Cris Logic Artisan**, a Claude Code dev-workflow harness packaged as a
plugin. This repo is the portable source of truth for the harness; individual projects pull it in
via `update-cla` and adapt it to their own context, keeping their project-specific facts local.

CLA holds no product/application code — it is the *process* layer: skills, guard hooks, and helper
agents that carry a change from idea → spec → isolated implementation → review → opened PR, and
feed learnings back into the next run.

## Quick start

Launch a session with the harness active using the launchers at the repo root (a cached
marketplace install can't do this — the skills/hooks read and write repo-local state, so the
plugin must load live from the working tree):

```bash
./cla           # claude --plugin-dir <repo>/.claude/plugins/cla --permission-mode auto --model sonnet --effort medium
```

Use `cla.cmd` on native Windows. It resolves its own absolute path, so it works
from any cwd. For isolated work, start a session and run `/cla:new-worktree` — there is no
penalty for deciding mid-session, so the old `claw` launcher that created the worktree first is
gone. **Note:** `--permission-mode auto` bypasses Claude Code's per-action confirmation
prompts — intentional for this harness, but worth knowing before you run it. Without a launcher
(or a manual `claude --plugin-dir`), the skills and hooks are inert files on disk — no `/cla:*`
commands, no guards.

## Documentation

- **[DEVELOPER-GUIDE.md](DEVELOPER-GUIDE.md)** — progressive introduction: first
  session, first PR, the full workflow ladder, worktrees, guardrails, the learning loops.
- **[.claude/plugins/cla/README.md](.claude/plugins/cla/README.md)** — the harness's full scope,
  capabilities, and life-cycle map, skill by skill.
- **[CLAUDE.md](CLAUDE.md)** — working-in-this-repo instructions (also read by Claude Code itself).

## What's here

The plugin lives at **`.claude/plugins/cla/`** (nested at that path so `update-cla` can consume
this repo directly as a sync source):

```
cla (+ .cmd twin)              session launcher for THIS repo (loads the plugin from the tree)
.claude-plugin/                marketplace.json — how every other repo installs CLA
cla.io/                        this repo's own per-repo state (decisions, feedback, retro ledgers)
openspec/                      OpenSpec config + specs for this repo's own changes
.claude/plugins/cla/
  .claude-plugin/plugin.json   manifest
  README.md                    the harness's scope + capabilities, by life-cycle phase
  run_tests.py                 aggregating test runner (all pytest scopes)
  skills/                      18 workflow skills (spec-to-pr, lite-pr, multi-*, reviews, retro loops, …)
  agents/                      helper agents (doc-sweeper, fact-gatherer)
  hooks/                       always-on guard hooks (blocks, asks, warns) + dispatchers + tests
  output-styles/               the project's writing convention (force-for-plugin: true)
  consistency-checks/          cross-scope drift checks (this repo only — never synced)
  launcher-checks/             tests for the repo-root launchers (this repo only — never synced)
```

## Canonical vs. per-repo

This repo carries **portable procedure only**. Every project-specific overlay
(`cla.io/overlays/<skill>.md`, `*.local.md`) here is a **neutral stub** — a destination repo
fills in its own facts, and `update-cla` never overwrites them. Per-repo state (`cla.io/`
decisions, feedback, retro logs) is never part of the synced core. Pytest conformance guards fail
the suite if a project-specific token or a hardcoded developer path leaks into the synced core.

## Using it in another repo

1. Copy or clone this repo somewhere reachable, or point `update-cla` at an existing checkout.
2. In the destination: `/cla:cla-init` (scaffold `cla.io/` + overlay stubs) → `/cla:sync-context`
   (populate the repo's facts) → `/cla:update-cla <this-repo>` (pull/adapt the portable core).

See the developer guide's [Adopting CLA in another repo](DEVELOPER-GUIDE.md#10-adopting-cla-in-another-repo)
section for details.

## Testing

There is **no CI, by design** — the local run below is the whole verification story and the only
gate before a merge:

```bash
python3 .claude/plugins/cla/run_tests.py     # every pytest scope (10 today), aggregated pass/fail + exit code
node --test .claude/plugins/cla/skills/project-review/scripts/mechanical-checks.test.mjs   # the one Node suite
```

Do not run bare `pytest` from the repo or plugin root — scopes are isolated on purpose (several
ship same-named helper modules) and collection fails by design. Run one scope with
`pytest .claude/plugins/cla/skills/<name>/tests` (or `hooks/tests`, `consistency-checks/tests`,
`launcher-checks/tests`).

---

Proprietary — see `.claude/plugins/cla/.claude-plugin/plugin.json`.
