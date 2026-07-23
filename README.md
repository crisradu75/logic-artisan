# logic-artisan

Canonical home of **CLA — Cris Logic Artisan**, a Claude Code dev-workflow harness packaged as a
plugin. This repo is the portable source of truth for the harness; individual projects pull it in
and adapt it to their own context, keeping their project-specific facts local.

## What's here

The plugin lives at **`.claude/plugins/cla/`** (nested at that path so `update-cla` can consume this
repo directly as a sync source). Its full scope, capabilities, and life-cycle map are documented in
the plugin's own README:

> **[.claude/plugins/cla/README.md](.claude/plugins/cla/README.md)**

```
.claude/plugins/cla/
  .claude-plugin/plugin.json   manifest
  README.md                    the harness's scope + capabilities, by life-cycle phase
  run_tests.py                 aggregating test runner (all scopes)
  skills/                      the workflow skills (spec-to-pr, lite-pr, multi-*, review, retro loops, …)
  agents/                      helper agents (doc-sweeper, fact-gatherer)
  hooks/                       always-on git/worktree guard hooks
```

## Canonical vs. per-repo

This repo carries **portable procedure only**. Every project-specific overlay
(`references/project-context.md`, `references/*.local.md`) here is a **neutral stub** — a destination
repo fills in its own facts. Per-repo state (`cla.io/` decisions, feedback, retro logs) is never
part of this repo.

## Using it in another repo

1. Copy or submodule this repo, or point `update-cla` at it.
2. In the destination: `cla-init` (scaffold `cla.io/` + overlay stubs) → `sync-context` (populate the
   repo's facts) → `update-cla <this-repo>` (pull/adapt the portable core).

## Testing

```bash
python3 .claude/plugins/cla/run_tests.py     # every pytest scope, aggregated pass/fail + exit code
```

---

Proprietary — see `.claude/plugins/cla/.claude-plugin/plugin.json`.
