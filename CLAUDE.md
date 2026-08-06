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

### `claw` — start a session already inside a worktree

`claw` / `claw.cmd` is the sibling launcher for when you know up front that the work wants
isolation. It creates the worktree with plain git **before** Claude starts, then launches inside it:

```bash
./claw <name>   # .claude/worktrees/<name> on branch worktree-<name>, then claude in it
```

**Why it exists.** `guard-worktree-isolation.py` writes a presence heartbeat at SessionStart for
any session whose cwd is the primary clone — before you can type anything. A session that starts
there and only *then* runs `/cla:new-worktree` has already registered as a contender; when it
migrates, the beat stops refreshing but is never removed, so another session working legitimately
in the primary clone is blocked from committing until it ages out (an hour). A `claw`-launched
session has `git_dir != git_common_dir` from its first instant, so no heartbeat is ever written
and nobody is blocked.

Creation is delegated to `new-worktree/scripts/manual_worktree.py --print-path`, so base-branch
resolution, name validation, duplicate-branch refusal, and the Windows path-casing fallback are
the same tested code the skill uses — the launchers add only argument handling and the exec.

**It does not install dependencies or copy env files.** Those commands are per-repo facts living
in `new-worktree`'s `references/project-context.md` overlay, so a portable launcher cannot know
them. Ask the launched session to finish setup; from inside the worktree that writes no heartbeat.

`/cla:new-worktree` is still the right tool when you are already mid-session and only then realise
you want isolation. `claw` covers the up-front case; it does not replace the skill.

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
design. Each skill that ships tests (7 today), plus `hooks/`, plus `consistency-checks/`, is its
own isolated pytest scope — 9 in total — each with its own `pyproject.toml` (`testpaths =
["tests"]`, plus a `pythonpath` pointing at that scope's importable code — `["scripts"]` for a
skill and for `consistency-checks/`, `["."]` for `hooks/`, whose modules sit at the scope root).

`consistency-checks/` is the odd one out: not a skill (no `SKILL.md`) and not a guard hook, but a
home for checks that span *several* scopes and so can live in none of them — today, a drift check
over the sibling `log_run.py`/`aggregate.py` copies that the isolation rule below deliberately
prevents from sharing a module. It sits outside the synced set
(`skills`/`agents`/`hooks`/`output-styles`), so `update-cla` never propagates it to consuming
repos; it guards this repo's own source. Several scopes
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

### No CI — verification is local, by design

This repo runs **no GitHub Actions and no CI of any kind**, deliberately. The commands above are
the whole verification story: `run_tests.py` for every pytest scope, plus the Node suite. Run both
before calling a change done.

Do not add a workflow. If a change seems to need one, raise it rather than adding it.

Two consequences worth holding, since nothing else will catch them:

- **Platform-divergent code is only ever exercised on the machine you are on.** Several hooks shell
  out to real `git` and branch on Windows vs POSIX, and three symlink tests skip on Windows
  outright (see `TODO.md`). A green local run is evidence about that machine, not about the others.
- **Merging is unguarded.** Nothing blocks a merge on tests, so the local run before opening a PR
  is the only gate that exists.

## Architecture — the fact/procedure split

CLA is portable across repos because it strictly separates *procedure* (generic, synced
everywhere) from *facts* (per-repo, never synced):

- **Synced core** — `.claude/plugins/cla/{skills,agents,hooks,output-styles}/`: portable procedure
  only. A pytest **conformance guard** fails if a distinctive project token, or a hardcoded absolute
  developer path, leaks into synced core — one scanner covers `SKILL.md`/`references/*.md` prose
  under `skills/`, a second covers every `.py` file plus `agents/*.md` and `output-styles/*.md`
  (frontmatter-exempt the same way `SKILL.md`'s own `description:` is). Together that's every
  `.py`/`.md` in the tree — a non-`.py`/`.md` synced-core file (`hooks/hooks.json`, a skill's own
  `.mjs` script) is still outside both scanners; watch those by hand.
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
that sync the plugin. `hooks.json` itself wires two dispatchers (`dispatch-bash-pretooluse.py` for
the Bash/PowerShell matcher, `dispatch-edit-write-pretooluse.py` for the Edit/Write matcher), each
of which runs several leaf hooks in one Python process — 13 distinct leaf hooks between them
(`guard-worktree-isolation` runs on both matchers), plus `warn-lint-on-edit` wired directly on
PostToolUse: 14 leaf hook files in all. **Blocks**
(`block-*`) stop a tool call; **asks** (`ask-*`) escalate to a permission prompt instead of
blocking outright; **warns** (`warn-*`) surface a caution without blocking:

- **No direct push to main/master** (`block-direct-push-to-main`) — branch + PR for any change;
  a bare `Bash(cd ...)` (`block-cd-in-bash`) — the working dir is already repo root, and a `cd`
  persists and breaks later calls in the same session; use absolute paths instead.
- **Blocks:** `block-unsafe-recursive-delete` (`rm -rf` and PowerShell equivalents) ·
  `block-worktree-path-escape` (a Write/Edit escaping a worktree boundary from inside one) ·
  `block-dated-stamps-in-prose` (hardcoded dates rot) · `guard-worktree-isolation` (a
  branch-create/switch/commit in the primary clone while another session is live there too —
  git's HEAD is per-clone, not per-session, so two concurrent sessions would otherwise collide
  on one branch; also refreshes/clears this session's presence heartbeat on SessionStart/End).
- **Asks:** `ask-destructive-git` (a destructive-but-not-outright-blocked git command, e.g. a
  force-push or `reset --hard`) · `ask-git-identity` (no `user.email` configured, or the commit
  author doesn't match an expected identity when one is set) — both return exit 0 and escalate via
  `permissionDecision: "ask"` rather than blocking, since the action may be legitimate.
- **Warns:** `warn-branch-base` (branched off the wrong base) · `warn-lint-on-edit` (lints the
  edited file, feeds violations back non-blocking) · `warn-smoke-test-drift` (component/i18n edits
  that may break a UI smoke test — config-driven via a `smoke-test-drift.local.md` overlay beside
  the hook; a no-op with none present, which is this repo's own state, since it ships no product
  code) · `warn-stacked-pr-merge` (a merge that could auto-close an open child PR) ·
  `warn-comment-dates` · `warn-stray-scratch-artifact` (scratch files left in the repo root).

### Portability

`update-cla` is a pull-based, stdlib-only cross-repo updater: run it *in the repo that wants
updates*, pointing at a source repo (this one, canonically). It syncs only
`skills`/`agents`/`hooks`/`output-styles`, classifies each file against a per-repo `.cla-sync-lock.json`
(3-way reconcile), preserves local strengths, surfaces deletions without applying them, and never
auto-merges. Onboarding a fresh consuming repo: `cla-init` → `sync-context` → `update-cla`.
