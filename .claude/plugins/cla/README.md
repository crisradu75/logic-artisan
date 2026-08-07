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
| **Any phase** (utility) | `right-model` | Recommend the cheapest model + effort combo that can plausibly do a described task well, then optionally start it |

### Typical flows

- **Small change:** `shape-decision` → `lite-pr` (or straight to `lite-pr`).
- **Larger change:** `shape-decision` → `multi-spec` → `review-change` → `spec-to-pr`.
- **A batch off one decisions doc:** `multi-lite` (small) or `multi-pr` (spec-scale).
- **After a session:** `codify-learnings`; periodically `*-retro` to tune the loops.

## Always-on guardrails (hooks)

Guard hooks wire themselves via the plugin's own `hooks/hooks.json` when the plugin loads — no
`settings.json` step. Two dispatchers (one for Bash/PowerShell, one for Edit/Write) each run
several leaf hooks in one Python process; 14 leaf hooks in all. They run throughout every phase.
**Blocks** (`block-*`) stop a tool call; **asks** (`ask-*`) escalate to a permission prompt
instead of blocking outright; **warns** (`warn-*`) surface a caution without blocking.

**Blocks:** `block-cd-in-bash` (working dir is already repo root; a `cd` persists and breaks later
calls) · `block-direct-push-to-main` · `block-unsafe-recursive-delete` (`rm -rf` and PowerShell
equivalents) · `block-worktree-path-escape` (writes escaping a worktree boundary) ·
`block-dated-stamps-in-prose` (hardcoded dates rot) · `guard-worktree-isolation` (a
branch-create/switch/commit in the primary clone while another session is live there too — git's
HEAD is per-clone, not per-session; also refreshes/clears the session's presence heartbeat on
SessionStart/End).

**Asks:** `ask-destructive-git` (force-push, `reset --hard`, PR merges, and other
destructive-but-possibly-legitimate git/gh commands; `ALLOW_PR_MERGE=1` drops only the PR-merge
confirmation, for the `multi-*` chainers' unattended runs) · `ask-git-identity` (no `user.email`
configured, or the commit author doesn't match an expected identity when one is set).

**Warns:** `warn-branch-base` (branched off the wrong base) · `warn-lint-on-edit` (lints the edited
file, feeds violations back non-blocking) · `warn-smoke-test-drift` (component/i18n edits that may
break a UI smoke test — config-driven via a `smoke-test-drift.local.md` overlay beside the hook; a
silent no-op with none present) · `warn-stacked-pr-merge` (a merge that could auto-close an open
child PR) · `warn-comment-dates` · `warn-stray-scratch-artifact` (scratch files left in the repo
root).

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

Each skill *that ships tests* (7 today), plus `hooks/`, `consistency-checks/`, and
`launcher-checks/`, is its own isolated pytest scope (own `pyproject.toml` + `tests/`) — 10 in
all; several ship same-named helper modules, so they can't share one pytest process. Run the whole
suite at once:

```bash
python3 .claude/plugins/cla/run_tests.py        # every scope, aggregated pass/fail + exit code
python3 .claude/plugins/cla/run_tests.py -q     # extra args forwarded to each pytest
```

Run one scope in isolation with `pytest .claude/plugins/cla/skills/<name>/tests`. The one Node
script (`project-review/scripts/mechanical-checks.mjs`) has its own sibling `node --test` suite,
outside `run_tests.py`'s discovery:

```bash
node --test .claude/plugins/cla/skills/project-review/scripts/mechanical-checks.test.mjs
```

There is no CI — these local runs are the whole verification story.

## Layout

```
.claude/plugins/cla/
  .claude-plugin/plugin.json   manifest
  run_tests.py                 aggregating test runner (all scopes)
  .cla-sync-lock.json          per-repo sync provenance (auto-maintained by update-cla)
  agents/                      doc-sweeper, fact-gatherer (mechanical helpers)
  hooks/                       guard hooks + hooks.json wiring + tests
  output-styles/               the project's writing convention (force-for-plugin: true)
  consistency-checks/          cross-scope drift checks — guards this repo's own source, never synced
  launcher-checks/             tests for the repo-root cla/claw launchers — never synced
  skills/<name>/               (references/ scripts/ tests/ present as each skill needs)
    SKILL.md                   the skill (portable procedure)
    references/                supporting refs; project-context.md = per-repo overlay
    scripts/                   deterministic helpers (stdlib Python)
    tests/                     that skill's pytest scope
```

Per-repo state lives outside the plugin, at the repo root under `cla.io/`.
