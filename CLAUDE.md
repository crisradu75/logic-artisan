# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

`logic-artisan` is the canonical home of **CLA — Cris Logic Artisan**, a Claude Code dev-workflow
harness packaged as a plugin. It holds no product/application code — it's the *process* layer
(skills, guard hooks, helper agents) that carries a change from idea → spec → isolated
implementation → review → opened PR, and feeds learnings back into the next run. Other repos pull
this plugin in via `update-cla` and adapt it to their own context.

Everything lives under `.claude/plugins/cla/`, nested at that path specifically so `update-cla` can
consume this repo directly as a sync source.

**Launching a session with the plugin active:** `claude --plugin-dir` loads the plugin live, in
place, from this working tree — required because the skills/hooks read and write repo-local state
(`cla.io/`, the sync lockfile), which a cached marketplace install (`enabledPlugins` + a registered
marketplace, itself a real settings-file mechanism, just the wrong one for this) can't do. Use the
`cla` (POSIX) / `cla.cmd` (Windows) launcher at the repo root instead of typing `claude` directly —
it resolves its own absolute path, so the flag it prints/runs is `--plugin-dir <repo>/.claude/plugins/cla`
regardless of your cwd:

```bash
./cla   # claude --plugin-dir <repo>/.claude/plugins/cla --permission-mode auto --model sonnet --effort medium
```

Without it, the skills/hooks are just inert files on disk — no `/cla:*` commands, no guard hooks.
**Note:** `--permission-mode auto` bypasses Claude Code's normal per-action confirmation prompts —
intentional for this harness, but worth knowing before you run it.

## Commands

Run the full test suite (aggregates every isolated pytest scope):

```bash
python3 .claude/plugins/cla/run_tests.py        # every scope, aggregated pass/fail + exit code
python3 .claude/plugins/cla/run_tests.py -q     # extra args forwarded to each scope's pytest
python3 .claude/plugins/cla/run_tests.py -k branch   # filter by name across scopes
```

Run a single scope in isolation (e.g. while iterating on one skill):

```bash
pytest .claude/plugins/cla/skills/<name>/tests
pytest .claude/plugins/cla/hooks/tests
```

**Do not run bare `pytest` from the plugin root or repo root** — it will fail collection by
design. Each skill that ships tests (7 today) plus `hooks/` is its own isolated pytest scope, each
with its own `pyproject.toml` (`testpaths = ["tests"]`, plus a `pythonpath` pointing at that
scope's importable code — `["scripts"]` for a skill, `["."]` for `hooks/`, whose modules sit at
the scope root). Several scopes
ship same-named helper modules (e.g. `scripts/aggregate.py`, `scripts/log_run.py`), so they can't
share one pytest process — this is why `run_tests.py` exists: it discovers every scope
(dir with both a pytest-configured `pyproject.toml` and a `tests/` subdir) and runs `pytest` once
per scope as a subprocess, then aggregates results. A dir with only one of those two signals is
treated as a "near-miss" (half-removed/misconfigured scope) and fails the run rather than being
silently skipped.

All scripts are stdlib-only Python (no third-party deps beyond pytest itself).

The one Node script in the plugin, `project-review/scripts/mechanical-checks.mjs`, has its own
sibling `node --test` suite (not a pytest scope, so `run_tests.py` doesn't discover it):

```bash
node --test .claude/plugins/cla/skills/project-review/scripts/mechanical-checks.test.mjs
```

## Architecture — the fact/procedure split

CLA is portable across repos because it strictly separates *procedure* (generic, synced
everywhere) from *facts* (per-repo, never synced):

- **Synced core** — `.claude/plugins/cla/{skills,agents,hooks,output-styles}/`: portable procedure
  only. A pytest **conformance guard** fails if a distinctive project token, or a hardcoded absolute
  developer path, leaks into synced core — one scanner covers `SKILL.md`/`references/*.md` prose
  under `skills/`, a second covers every `.py` file plus `agents/*.md` and `output-styles/*.md`
  (frontmatter-exempt the same way `SKILL.md`'s own `description:` is), so the whole tree is
  mechanically checked, not just `skills/`.
- **Overlays** — each skill's `references/project-context.md` plus any `*.local.md` files: the
  destination repo's own facts and tuned checks. Recognized by name, excluded from sync, never
  overwritten by `update-cla`. In *this* repo they are neutral stubs (this is the source, not a
  consumer).
- **`cla.io/`** (repo root) — all per-repo state: `decisions/`, `feedback/`, `retro/` run ledgers,
  `lessons-learned/`, and (in a consuming repo) a consolidated `project-facts.md` and `terminology.md`
  (internal naming disambiguation, format owned by `sync-context`, written inline by other skills as
  terms resolve). Never part of the synced core; a staleness guard fails when a path named there no
  longer exists.

### Skill layout

```
.claude/plugins/cla/
  .claude-plugin/plugin.json   manifest
  run_tests.py                 aggregating test runner (all scopes)
  .cla-sync-lock.json          per-repo sync provenance (auto-maintained by update-cla)
  agents/                      doc-sweeper, fact-gatherer (mechanical helpers other skills delegate to)
  hooks/                       guard hooks + hooks.json wiring + tests
  output-styles/               the project's writing convention (force-for-plugin: true)
  skills/<name>/
    SKILL.md                   the skill itself (portable procedure)
    references/                supporting docs; project-context.md = per-repo overlay
    scripts/                   deterministic helpers (stdlib Python)
    tests/                     that skill's isolated pytest scope
```

### Skills by life-cycle phase

Each skill is invocable as `/cla:<name>` or by natural language; `[loop]` marks a self-improvement
retro over prior runs of another skill.

| Phase | Skill | What it does |
|---|---|---|
| 0. Bootstrap (once per repo) | `cla-init` | Scaffold the `cla.io/` tree + empty overlay stubs |
| | `sync-context` | Populate/reconcile `cla.io/project-facts.md` |
| | `save-permissions` | Persist session tool permissions to `.claude/settings.local.json` |
| | `update-cla` | Pull newer CLA core from another repo, adapting to local context |
| 1. Discover & shape | `feedback` | Capture rough notes → a dated, grounded triage doc under `cla.io/feedback/` |
| | `shape-decision` | Walk a decision option-by-option with pros/cons + a recommended pick |
| 2. Specify & plan | `multi-spec` | Turn a shaped decisions doc into a batch of OpenSpec proposals |
| | `review-change` | Pre-implementation review of an OpenSpec change |
| 3. Build & ship | `new-worktree` | Start an isolated git worktree for parallel/safe work |
| | `lite-pr` | Lightweight end-to-end path for a small change: implement + docs + tests + PR |
| | `spec-to-pr` | Drive one OpenSpec change end-to-end to an opened, archived PR |
| | `multi-lite` / `multi-pr` | Chain several `lite-pr` / OpenSpec changes → PRs, dependency-first |
| 4. Review & assure | `project-review` | CTO-level review of the whole repo |
| 5. Learn & improve | `codify-learnings` | Review a session for reusable lessons; propose doc/skill/hook/memory edits `[loop]` |
| | `codify-retro`, `spec-to-pr-retro` | Meta-review recent runs of a loop and improve the loop itself `[loop]` |
| Any phase (utility) | `right-model` | Recommend the cheapest model + effort combo for a described task, then optionally start it |

Typical flows: small change → `shape-decision` → `lite-pr` (or straight to `lite-pr`); larger
change → `shape-decision` → `multi-spec` → `review-change` → `spec-to-pr`; a batch off one
decisions doc → `multi-lite` or `multi-pr`.

### Guard hooks (conventions enforced, not just advised)

Wired automatically via `.claude/plugins/cla/hooks/hooks.json` when the plugin loads (no
`settings.json` step needed) — these apply in this repo's own sessions too, not only in repos
that sync the plugin. **Blocks** (`block-*`) stop a tool call; **warns** (`warn-*`) surface a
caution without blocking:

- **No direct push to main/master** (`block-direct-push-to-main`) — branch + PR for any change;
  a bare `Bash(cd ...)` (`block-cd-in-bash`) — the working dir is already repo root, and a `cd`
  persists and breaks later calls in the same session; use absolute paths instead.
- **Blocks:** `block-unsafe-recursive-delete` (`rm -rf` and PowerShell equivalents) ·
  `block-worktree-path-escape` (a Write/Edit escaping a worktree boundary from inside one) ·
  `block-dated-stamps-in-prose` (hardcoded dates rot) · `guard-worktree-isolation` (a
  branch-create/switch/commit in the primary clone while another session is live there too —
  git's HEAD is per-clone, not per-session, so two concurrent sessions would otherwise collide
  on one branch; also refreshes/clears this session's presence heartbeat on SessionStart/End).
- **Warns:** `warn-branch-base` (branched off the wrong base) · `warn-lint-on-edit` (lints the
  edited file, feeds violations back non-blocking) · `warn-smoke-test-drift` · `warn-stacked-pr-merge`
  (a merge that could auto-close an open child PR) · `warn-comment-dates` ·
  `warn-stray-scratch-artifact` (scratch files left in the repo root).

### Portability

`update-cla` is a pull-based, stdlib-only cross-repo updater: run it *in the repo that wants
updates*, pointing at a source repo (this one, canonically). It syncs only
`skills`/`agents`/`hooks`/`output-styles`, classifies each file against a per-repo `.cla-sync-lock.json`
(3-way reconcile), preserves local strengths, surfaces deletions without applying them, and never
auto-merges. Onboarding a fresh consuming repo: `cla-init` → `sync-context` → `update-cla`.
