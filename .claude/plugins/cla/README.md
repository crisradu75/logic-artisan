# CLA — Cris Logic Artisan

A Claude Code **dev-workflow harness**, distributed as a marketplace plugin. CLA is not
application code and holds no product logic — it is the *process*
layer: a set of skills, guard hooks, and helper agents that carry a change from a raw idea through
specification, isolated implementation, review, and a PR, then feed what was learned back into the
next run. It builds on existing skills rather than replacing them, and keeps all per-repo state
(decisions, feedback, retro logs, lessons-learned) in the repo's own `cla.io/` tree.

## Install these first — CLA calls out to them and cannot substitute for them

`plugin.json` has no field for declaring a dependency, so **nothing installs these for you and
nothing warns when one is missing.** A phase that needs an absent plugin simply cannot run, which
reads as CLA being broken.

| Dependency | Reached by | How hard |
|---|---|---|
| **OpenSpec** — the `opsx:*` / `openspec-*` skills **and** the `openspec` CLI | `spec-to-pr`, `multi-spec`, `multi-pr`, `review-change` | **Required** for the spec-scale path. The CLI is called directly — `validate`, `archive`, `status`. (`lite-pr` calls `openspec validate` once and documents skipping it in a repo not using OpenSpec, so it degrades rather than failing.) |
| **`pr-review-toolkit`** — `code-reviewer`, `silent-failure-hunter`, `pr-test-analyzer`, `comment-analyzer`, `type-design-analyzer` | every PR-review pass: `spec-to-pr`, `lite-pr` (and `multi-pr`/`multi-lite`, which chain them) | **Required.** The Revise phase names these agents directly and defines no fallback for their absence. |
| **`commit-commands`** | `lite-pr`'s commit/push/PR step, and `multi-lite`, which chains it | **Required for the lightweight path.** The spec-scale path commits directly and does not need it. |
| **`plugin-dev`** — `skill-reviewer` | two rows of the Revise agent-selection table, plus `lite-pr`'s own agent picking | **Conditional.** Fires on a changed `SKILL.md` **frontmatter**, a new skill, a new command under `.claude/commands/`, or a prose-dominant diff — not on a body-only prose edit. On the prose-dominant row it is never demoted. |

There is no `openspec apply` CLI subcommand — apply is a skill. See `spec-to-pr/SKILL.md` for the
full list of subcommands the CLI actually ships.

## Scope — what CLA is and isn't

- **Is:** a repeatable, guard-railed pipeline for turning intent into reviewed, shippable changes,
  plus the self-improvement loops that keep the pipeline sharp.
- **Is:** portable across repos and tech stacks — project specifics live behind neutral overlays,
  never baked into the synced core (see *Architecture*).
- **Isn't:** product/app code, a CI system, or a deploy tool. The single-change ship skills
  (`lite-pr`, `spec-to-pr`) stop at an **opened PR**; the `multi-*` chainers may merge a dependency
  PR to unblock its dependents during an unattended run (or, under `multi-pr`'s stacked policy,
  merge nothing and stack the PRs instead) — but nothing here deploys, and no PR is merged without
  you having chosen to run a chainer.
- **Isn't:** a store of project facts. Those live in `cla.io/` and per-skill overlays, which sit in
  the repo rather than the plugin, so no install touches them.

## The software life cycle, phase by phase

CLA's skills map onto the arc of a change. Each shipped skill is invocable as `/cla:<name>` or by
natural language; `[loop]` marks a self-improvement retro over prior runs of another skill. One
skill, `release`, is not shipped — it acts on this repo's own distribution, so it is repo-local
and invoked bare as `/release`.

| Phase | Skill | What it does |
|---|---|---|
| **0. Bootstrap** (per repo, once) | `cla-init` | Scaffold the `cla.io/` tree + empty overlay stubs (structure only, never facts) |
| | `sync-context` | Populate/reconcile `cla.io/project-facts.md` — the repo's shared facts (members, commands, ports, file maps) |
| | `save-permissions` | Persist tool permissions granted this session to `.claude/settings.local.json` |
| **1. Discover & shape** | `feedback` | Capture rough notes one at a time → a dated, grounded triage doc under `cla.io/feedback/` |
| | `shape-decision` | Walk a decision option-by-option with pros/cons + a recommended pick |
| | (`opsx:explore`) | OpenSpec's thinking-partner mode for investigating a problem before committing to a change |
| **2. Specify & plan** | `multi-spec` | Turn a shaped decisions doc into a batch of full OpenSpec proposals (stops at proposals) |
| | `review-change` | Pre-implementation review of an OpenSpec change: verify claims, symbols, file/reference reality, size it |
| **3. Build & ship** | `new-worktree` | Start an isolated git worktree (deps installed, env carried over) for parallel/safe work |
| | `lite-pr` | Lightweight end-to-end path for a small change: implement + docs + tests + PR + one review round |
| | `spec-to-pr` | Drive one OpenSpec change end-to-end to an opened, archived PR with review fixes applied |
| | `multi-lite` | Chain several `lite-pr` runs extracted from one decisions doc, dependency-first |
| | `multi-pr` | Chain several OpenSpec changes → PRs, merging each before its dependents (or stacking PRs on their parents when merging is unavailable) |
| **4. Review & assure** | `project-review` | CTO-level review of the whole repo: vision, structure, requirements, architecture, validation |
| | `annotate` | Render a doc as a page, open it chrome-less, and collect the user's own comments against selected passages — read back and worked through here |
| | (agents) | `doc-sweeper` + `fact-gatherer` do the mechanical grep/verify legwork the ship + review skills delegate to |
| **5. Learn & improve** | `codify-learnings` | Review the current session for reusable lessons; propose doc/skill/hook/memory edits; log them `[loop]` |
| | `codify-retro` | Meta-review recent `codify-learnings` runs and improve that loop itself `[loop]` |
| | `spec-to-pr-retro` | Meta-review recent `spec-to-pr` runs and improve the orchestrator `[loop]` |
| | `report-upstream` | File a defect in CLA's own portable core as an issue against the canonical source |
| | `checkpoint` | Compact a session into a resumable briefing (`cla.io/checkpoints/`) |
| **Any phase** (utility) | `right-model` | Recommend the cheapest model + effort combo that can plausibly do a described task well, then optionally start it |

### Typical flows

- **Small change:** `shape-decision` → `lite-pr` (or straight to `lite-pr`).
- **Larger change:** `shape-decision` → `multi-spec` → `review-change` → `spec-to-pr`.
- **A batch off one decisions doc:** `multi-lite` (small) or `multi-pr` (spec-scale).
- **After a session:** `codify-learnings`; periodically `*-retro` to tune the loops.

## Always-on guardrails (hooks)

Guard hooks wire themselves via the plugin's own `hooks/hooks.json` when the plugin loads — no
`settings.json` step. Two dispatchers (one for Bash/PowerShell, one for Edit/Write) each run
several leaf hooks in one Python process — 8 distinct leaf hooks between them (6 on the
Bash/PowerShell matcher, 2 on Edit/Write) — plus `warn-wholesale-rewrite` and `log-commit-provenance` wired
directly on PostToolUse: 10 leaf hook files in all. They run throughout every phase.
**Blocks** (`block-*`) stop a tool call; **asks** (`ask-*`) escalate to a permission prompt
instead of blocking outright; **warns** (`warn-*`) surface a caution without blocking.

**Blocks:** `block-cd-in-bash` (working dir is already repo root; a `cd` persists and breaks later
calls) · `block-unsafe-recursive-delete` (`rm -rf` and PowerShell equivalents) ·
`block-worktree-path-escape` (writes escaping a worktree boundary).

**Asks:** `ask-destructive-git` (force-push, `reset --hard`, branch force-delete, PR merges, and other
destructive-but-possibly-legitimate git/gh commands; `ALLOW_PR_MERGE=1` drops only the PR-merge
confirmation, for the `multi-*` chainers' unattended runs).

**Warns:** `warn-stacked-pr-merge` (a merge into a branch that open child PRs are based on — states the retarget-vs-close rules and the squash hazard) ·
`warn-comment-dates` · `warn-stray-scratch-artifact` (scratch files left in the repo root) ·
`warn-heredoc-escape-mangling` (a heredoc body carrying a backslash escape the shell/inner-language
layering eats) · `warn-wholesale-rewrite` (a `Write` replacing a tracked file with a materially
shorter one).

**Direct pushes to `main` are NOT guarded by any of these.** That protection is a git `pre-push`
hook at `hooks/git/pre-push`, which sees the refspec git already resolved, so no command spelling
can evade it — but a plugin cannot write to `.git/hooks`, so **every clone installs it once**:

```bash
cp "<plugin>/hooks/git/pre-push" .git/hooks/pre-push && chmod +x .git/hooks/pre-push
```

Until you run that, nothing stops a direct push.

## Architecture — the fact/procedure split

CLA is portable because it separates *procedure* (generic, synced everywhere) from *facts*
(per-repo, never synced):

- **Synced core** — `skills/`, `agents/`, `hooks/`, `output-styles/`: portable procedure only. A
  **conformance guard** — `skills/_shared/scripts/check_no_project_tokens.py`, run as a program
  (exit 0 clean / 1 violations / 2 could-not-run) — fails if a distinctive project token, or a
  hardcoded absolute developer path, leaks into synced core: one scanner covers `SKILL.md`/reference
  prose under `skills/`, a second covers every `.py` file plus `agents/*.md` and `output-styles/*.md`,
  across five roots — `skills/`, `agents/`, `hooks/`, `output-styles/`, `lib/`.
  It is a program rather than a test precisely so it runs here — an installed plugin is a read-only
  cache with no pytest gate over it, so a guard filed as a test module would be unreachable.
- **Overlays** — `cla.io/overlays/<skill>.md` plus any `*.local.md` beside them: the repo's own
  facts and tuned checks. They live in YOUR repo, not in the plugin: the installed plugin tree is a
  read-only, version-keyed cache, so a fact stored there would be unwritable and would vanish on
  the next update. A plugin update never touches them.
- **`cla.io/`** (repo root) — all per-repo state: `decisions/`, `feedback/`, `retro/` run ledgers,
  `lessons-learned/`, and the consolidated **`project-facts.md`** (one physical copy of every fact
  shared across skills). A **staleness guard** (`skills/sync-context/scripts/check_fact_paths.py`, also a program) fails
  when a path named there no longer exists.

## Installing and updating

CLA is installed from its marketplace and enabled per repo:

```bash
claude plugin marketplace add crisradu75/logic-artisan
claude plugin install cla@cris-logic-artisan --scope project
claude plugin update cla@cris-logic-artisan      # take a newer release (restart to apply)
```

**The installed tree is read-only.** Never edit it: it is a version-keyed cache, so an edit either
fails or lands somewhere the next update discards. A fix that belongs in the harness goes back via
**`/cla:report-upstream`**, which files it as an issue against the canonical source. A fact that
belongs to your repo goes in `cla.io/`.

**Onboarding a fresh repo:** install (above) → `cla-init` (scaffold `cla.io/`) → `sync-context`
(populate the facts) → install the `pre-push` hook (see *Guardrails*).

The marketplace install is the only route in. `update-cla`, the old pull-based file-sync updater,
has been deleted; a repo still carrying a `.cla-sync-lock.json` from it can delete that too.

## Testing

**The plugin ships no tests, and that is deliberate.** Everything under this directory is an asset
you can invoke, read, or have fire on your behalf; nothing here is validation machinery you have no
way to run. An installed plugin is a read-only, version-keyed cache with no pytest gate over it, so
a test filed here would be unreachable in your repo by construction.

CLA's own suite therefore runs only in the repo that develops it, where it is one isolated
pytest scope — 1 in total, down from 12 — living outside the plugin directory entirely. Each skill
*that ships tests* (6 today) has its tests there rather than beside itself, alongside the guards over
the hooks, the shared library, and the source repo's own launchers and catalog. The one Node script
(`project-review/scripts/mechanical-checks.mjs`) has a `node --test` suite in the same place.

There is no CI — that local run is the whole verification story. **Nothing in it is a command for
you to run**; if you want to check your own repo's conformance, the two guards above are programs:

```bash
python3 <plugin>/skills/_shared/scripts/check_no_project_tokens.py
python3 <plugin>/skills/sync-context/scripts/check_fact_paths.py
```

## Layout

```
.claude/plugins/cla/
  .claude-plugin/plugin.json   manifest
  agents/                      doc-sweeper, fact-gatherer (mechanical helpers)
  hooks/                       guard hooks + hooks.json wiring, and git/pre-push
  lib/                         log_run.py — the one retro-ledger writer
  output-styles/               the project's writing convention (force-for-plugin: true)
  skills/<name>/               (references/ scripts/ present as each skill needs)
    SKILL.md                   the skill (portable procedure)
    references/                supporting refs (portable — overlays live in your cla.io/)
    scripts/                   deterministic helpers (stdlib Python)
```

That is the whole published tree. The suite, the mutation corpora, the pytest configuration and the
release workflow all live outside it, in the canonical source repo only — see *Testing* above.

Per-repo state lives outside the plugin, at your repo root under `cla.io/` — including
`overlays/<skill>.md`. Nothing in the plugin tree is yours to edit.
