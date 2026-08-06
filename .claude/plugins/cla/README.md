# CLA — Cris Logic Artisan

A Claude Code **dev-workflow harness**, packaged as a plugin and loaded in-place via
`--plugin-dir`. CLA is not application code and holds no product logic — it is the *process*
layer: a set of skills, guard hooks, and helper agents that carry a change from a raw idea through
specification, isolated implementation, review, and a PR, then feed what was learned back into the
next run. It orchestrates on top of OpenSpec (the `opsx:*` skills) for the
spec artifacts themselves, and keeps all per-repo state (decisions, feedback, retro logs,
lessons-learned) in the repo's own `cla.io/` tree.

## Scope — what CLA is and isn't

- **Is:** a repeatable, guard-railed pipeline for turning intent into reviewed, shippable changes,
  plus the self-improvement loops that keep the pipeline sharp.
- **Is:** portable across repos and tech stacks — project specifics live behind neutral overlays,
  never baked into the synced core (see *Architecture*).
- **Isn't:** product/app code, a CI system, or a deploy tool. The single-change ship skills
  (`lite-pr`, `spec-to-pr`) stop at an **opened PR**; the `multi-*` chainers may merge a dependency
  PR to unblock its dependents during an unattended run — but nothing here deploys, and no PR is
  merged without you having chosen to run a chainer.
- **Isn't:** a store of project facts. Those live in `cla.io/` and per-skill overlays, which the
  cross-repo updater never touches.

## The software life cycle, phase by phase

CLA's skills map onto the arc of a change. Each is invocable as `/cla:<name>` or by natural
language; `[loop]` marks a self-improvement retro over prior runs of another skill.

| Phase | Skill | What it does |
|---|---|---|
| **0. Bootstrap** (per repo, once) | `cla-init` | Scaffold the `cla.io/` tree + empty overlay stubs (structure only, never facts) |
| | `sync-context` | Populate/reconcile `cla.io/project-facts.md` — the repo's shared facts (members, commands, ports, file maps) |
| | `save-permissions` | Persist tool permissions granted this session to `.claude/settings.local.json` |
| | `update-cla` | Pull newer CLA core from another repo, adapting to local context, preserving local overlays |
| **1. Discover & shape** | `feedback` | Capture rough notes one at a time → a dated, grounded triage doc under `cla.io/feedback/` |
| | `shape-decision` | Walk a decision option-by-option with pros/cons + a recommended pick |
| | (`opsx:explore`) | OpenSpec's thinking-partner mode for investigating a problem before committing to a change |
| **2. Specify & plan** | `multi-spec` | Turn a shaped decisions doc into a batch of full OpenSpec proposals (stops at proposals) |
| | `review-change` | Pre-implementation review of an OpenSpec change: verify claims, symbols, file/reference reality, size it |
| **3. Build & ship** | `new-worktree` | Start an isolated git worktree (deps installed, env carried over) for parallel/safe work |
| | `lite-pr` | Lightweight end-to-end path for a small change: implement + docs + tests + PR + one review round |
| | `spec-to-pr` | Drive one OpenSpec change end-to-end to an opened, archived PR with review fixes applied |
| | `multi-lite` | Chain several `lite-pr` runs extracted from one decisions doc, dependency-first |
| | `multi-pr` | Chain several OpenSpec changes → PRs, merging each before its dependents |
| **4. Review & assure** | `project-review` | CTO-level review of the whole repo: vision, structure, requirements, architecture, validation |
| | (agents) | `doc-sweeper` + `fact-gatherer` do the mechanical grep/verify legwork the ship + review skills delegate to |
| **5. Learn & improve** | `codify-learnings` | Review the current session for reusable lessons; propose doc/skill/hook/memory edits; log them `[loop]` |
| | `codify-retro` | Meta-review recent `codify-learnings` runs and improve that loop itself `[loop]` |
| | `spec-to-pr-retro` | Meta-review recent `spec-to-pr` runs and improve the orchestrator `[loop]` |

### Typical flows

- **Small change:** `shape-decision` → `lite-pr` (or straight to `lite-pr`).
- **Larger change:** `shape-decision` → `multi-spec` → `review-change` → `spec-to-pr`.
- **A batch off one decisions doc:** `multi-lite` (small) or `multi-pr` (spec-scale).
- **After a session:** `codify-learnings`; periodically `*-retro` to tune the loops.

## Always-on guardrails (hooks)

Guard hooks wire themselves via the plugin's own `hooks/hooks.json` when the plugin loads — no
`settings.json` step. They run throughout every phase. **Hard blocks** (`block-*`) stop a
tool call; **soft warns** (`warn-*`) surface a caution without blocking.

**Blocks:** `block-cd-in-bash` (working dir is already repo root; a `cd` persists and breaks later
calls) · `block-direct-push-to-main` · `block-unsafe-recursive-delete` (`rm -rf` and PowerShell
equivalents) · `block-worktree-path-escape` (writes escaping a worktree boundary) ·
`block-dated-stamps-in-prose` (hardcoded dates rot).

**Warns:** `warn-branch-base` (branched off the wrong base) · `warn-lint-on-edit` (lints the edited
file, feeds violations back non-blocking) · `warn-smoke-test-drift` (editing a literal a smoke test
depends on) · `warn-stacked-pr-merge` (a merge that could auto-close an open child PR) ·
`warn-comment-dates` · `warn-stray-scratch-artifact` (scratch files left in the repo root).

`guard-worktree-isolation` runs on SessionStart/End to maintain worktree isolation.

## Architecture — the fact/procedure split

CLA is portable because it separates *procedure* (generic, synced everywhere) from *facts*
(per-repo, never synced):

- **Synced core** — `skills/`, `agents/`, `hooks/`, `output-styles/`: portable procedure only. A
  pytest **conformance guard** fails if a distinctive project token, or a hardcoded absolute
  developer path, leaks into synced core — one scanner covers `SKILL.md`/reference prose under
  `skills/`, a second covers every `.py` file plus `agents/*.md` and `output-styles/*.md`.
- **Overlays** — each skill's `references/project-context.md` plus any `*.local.md`: the repo's own
  facts and tuned checks. Recognized by name, excluded from sync, never overwritten.
- **`cla.io/`** (repo root) — all per-repo state: `decisions/`, `feedback/`, `retro/` run ledgers,
  `lessons-learned/`, and the consolidated **`project-facts.md`** (one physical copy of every fact
  shared across skills). A **staleness guard** fails when a path named there no longer exists.

## Portability & updates

`update-cla` is a pull-based, stdlib-only cross-repo updater: run it *in the repo that wants
updates*, pointing at a source repo. It syncs only `skills`/`agents`/`hooks`/`output-styles`, classifies each file
against a per-repo `.cla-sync-lock.json` (3-way reconcile), preserves local strengths, surfaces
deletions without applying them, and **never auto-merges** (worktree write or PR, your call).

**Onboarding a fresh repo:** `cla-init` → `sync-context` → `update-cla`.

## Testing

Each skill *that ships tests* (7 today) and the `hooks/` dir is its own isolated pytest scope (own
`pyproject.toml` + `tests/`); several ship same-named helper modules, so they can't share one pytest
process. Run the whole suite at once:

```bash
python3 .claude/plugins/cla/run_tests.py        # every scope, aggregated pass/fail + exit code
python3 .claude/plugins/cla/run_tests.py -q     # extra args forwarded to each pytest
```

Run one scope in isolation with `pytest .claude/plugins/cla/skills/<name>/tests`.

## Layout

```
.claude/plugins/cla/
  .claude-plugin/plugin.json   manifest
  run_tests.py                 aggregating test runner (all scopes)
  .cla-sync-lock.json          per-repo sync provenance (auto-maintained by update-cla)
  agents/                      doc-sweeper, fact-gatherer (mechanical helpers)
  hooks/                       guard hooks + hooks.json wiring + tests
  output-styles/               the project's writing convention (force-for-plugin: true)
  skills/<name>/               (references/ scripts/ tests/ present as each skill needs)
    SKILL.md                   the skill (portable procedure)
    references/                supporting refs; project-context.md = per-repo overlay
    scripts/                   deterministic helpers (stdlib Python)
    tests/                     that skill's pytest scope
```

Per-repo state lives outside the plugin, at the repo root under `cla.io/`.
