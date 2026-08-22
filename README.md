# logic-artisan

Canonical home of **CLA — Cris Logic Artisan**, a Claude Code dev-workflow harness packaged as a
plugin. This repo is the portable source of truth for the harness; individual projects install it
from the GitHub marketplace and adapt it to their own context, keeping their project-specific facts
local.

CLA holds no product/application code — it is the *process* layer: skills, guard hooks, and helper
agents that carry a change from idea → spec → isolated implementation → review → opened PR, and
feed learnings back into the next run.

## Install (any repo)

Two commands, scoped to the project:

```bash
claude plugin marketplace add crisradu75/logic-artisan
claude plugin install cla@cris-logic-artisan --scope project
```

Then run `claude plugin list` and check `cla`'s status isn't an error (e.g. "isn't installed") —
see the Windows note below for a way that can happen silently.

> **Windows:** run the install from the same shell your sessions launch with — Git Bash, or a
> Claude Code session's own Bash tool. PowerShell's `Set-Location` rewrites path casing to the
> on-disk name, and Claude Code records an install keyed by that exact string; a session launched
> from a shell using a different casing for the same directory can then find `cla` "enabled in
> project settings but isn't installed" — a status `claude plugin list` reports as
> "✘ failed to load" — with none of `cla`'s skills or guard hooks active, and nothing else saying
> so. If both spellings are genuinely in use, install from each.

Then, inside the repo: `/cla:cla-init` (scaffold `cla.io/` + overlay stubs) and `/cla:sync-context`
(populate the repo's facts). Pick up later releases with `/plugin marketplace update`. Details:
[Adopting CLA in another repo](DEVELOPER-GUIDE.md#10-adopting-cla-in-another-repo).

## Developing the harness (this repo only)

Do NOT use the marketplace install here. The launchers at the repo root load the plugin live from
the working tree, so you run the harness you are editing rather than a cached snapshot:

```bash
./cla           # claude --plugin-dir <repo>/.claude/plugins/cla --permission-mode auto --model sonnet --effort medium
```

Use `cla.cmd` on native Windows; both resolve their own path, so any cwd works. For isolated work,
run `/cla:new-worktree` at any point — no penalty for deciding mid-session. **Note:**
`--permission-mode auto` bypasses per-action confirmation prompts; the guard hooks are the safety
layer. Without a launcher (or a manual `claude --plugin-dir`), the skills and hooks are inert files
on disk — no `/cla:*` commands, no guards.

## Documentation

- **[DEVELOPER-GUIDE.md](DEVELOPER-GUIDE.md)** — progressive introduction: first
  session, first PR, the full workflow ladder, worktrees, guardrails, the learning loops.
- **[.claude/plugins/cla/README.md](.claude/plugins/cla/README.md)** — the harness's full scope,
  capabilities, and life-cycle map, skill by skill.
- **[CLAUDE.md](CLAUDE.md)** — working-in-this-repo instructions (also read by Claude Code itself).

## What's here

The plugin lives at **`.claude/plugins/cla/`** — exactly the directory the marketplace catalog
publishes as the plugin's source path:

```
cla (+ .cmd twin)              session launcher for THIS repo (loads the plugin from the tree)
.claude-plugin/                marketplace.json — how every other repo installs CLA
cla.io/                        this repo's own per-repo state (decisions, feedback, retro ledgers)
openspec/                      OpenSpec config + specs for this repo's own changes
.claude/plugins/cla/
  .claude-plugin/plugin.json   manifest
  README.md                    the harness's scope + capabilities, by life-cycle phase
  run_tests.py                 aggregating test runner (all pytest scopes + the Node suite)
  skills/                      21 workflow skills (spec-to-pr, lite-pr, multi-*, reviews, retro loops, …)
  skills/_shared/              references + one script that several skills share (not a skill)
  agents/                      helper agents (doc-sweeper, fact-gatherer)
  hooks/                       always-on guard hooks (blocks, asks, warns) + dispatchers + tests
  output-styles/               the project's writing convention (force-for-plugin: true)
  conformance-checks/          portable guards for the fact/procedure split
  consistency-checks/          cross-scope drift checks (assert this repo's own source)
  launcher-checks/             tests for the repo-root launchers (assert this repo's own source)
```

## Canonical vs. per-repo

This repo carries **portable procedure only**. Every project-specific overlay
(`cla.io/overlays/<skill>.md`, `*.local.md`) here is a **neutral stub** — a destination repo
fills in its own facts, and no install ever overwrites them — they live in the repo, outside the
plugin directory. Per-repo state (`cla.io/` decisions, feedback, retro logs) is never part of the
distributed core. Pytest conformance guards fail
the suite if a project-specific token or a hardcoded developer path leaks into the synced core.

## Testing

There is **no CI, by design** — the local run below is the whole verification story and the only
gate before a merge:

```bash
python3 .claude/plugins/cla/run_tests.py     # every pytest scope (12 today), aggregated pass/fail + exit code
node --test .claude/plugins/cla/skills/project-review/scripts/mechanical-checks.test.mjs   # the one Node suite
```

Do not run bare `pytest` from the repo or plugin root — scopes are isolated on purpose (several
ship same-named helper modules) and collection fails by design. Run one scope with
`pytest .claude/plugins/cla/skills/<name>/tests` (or `hooks/tests`, `consistency-checks/tests`,
`launcher-checks/tests`).

---

Proprietary — see `.claude/plugins/cla/.claude-plugin/plugin.json`.
