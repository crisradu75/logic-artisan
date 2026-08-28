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
./cla           # claude --plugin-dir <repo>/.claude/plugins/cla --permission-mode auto --model opus --effort medium
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
plugin-tests/                  the plugin's tests — one pytest scope, NOT published
.claude/skills/release/        repo-local skill invoked as /release — NOT published
.claude/plugins/cla/           everything below here IS published, and nothing else is
  .claude-plugin/plugin.json   manifest
  README.md                    the harness's scope + capabilities, by life-cycle phase
  skills/                      20 workflow skills (spec-to-pr, lite-pr, multi-*, reviews, retro loops, …)
  skills/_shared/              references + scripts that several skills share (not a skill)
  agents/                      helper agents (doc-sweeper, fact-gatherer)
  hooks/                       always-on guard hooks (blocks, asks, warns) + dispatchers
  lib/log_run.py               the one retro-ledger writer, invoked as a program
  output-styles/               the project's writing convention (force-for-plugin: true)
```

## Canonical vs. per-repo

This repo carries **portable procedure only**. Every project-specific overlay
(`cla.io/overlays/<skill>.md`, `*.local.md`) here is a **neutral stub** — a destination repo
fills in its own facts, and no install ever overwrites them — they live in the repo, outside the
plugin directory. Per-repo state (`cla.io/` decisions, feedback, retro logs) is never part of the
distributed core. A conformance guard
(`skills/_shared/scripts/check_no_project_tokens.py`) fails if a project-specific token or a
hardcoded developer path leaks into the synced core. It is a program rather than a test, so it
also runs in a consuming repo, which has no pytest gate over its plugin cache.

## Testing

There is **no CI, by design** — the two local runs below are the whole verification story and the
only gate before a merge:

```bash
pytest plugin-tests                                    # every pytest scope (1 today)
node --test plugin-tests/node/mechanical-checks.test.mjs   # the one Node suite pytest cannot reach
```

The plugin's tests deliberately live outside the plugin: `.claude/plugins/cla/` is published whole
to consuming repos and carries only assets a consumer can use. Run part of the suite with
`pytest plugin-tests/tests/<area>` — the areas are `conformance`, `consistency`, `launcher`,
`hooks`, `lib`, and `skills/<name>`.

---

Proprietary — see `.claude/plugins/cla/.claude-plugin/plugin.json`.
