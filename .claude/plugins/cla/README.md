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

CLA's skills map onto the arc of a change. Each shipped skill is invocable as `/cla:<name>`, and
all but the two marked **you only** below can also be triggered by natural language; `[loop]`
marks a self-improvement retro over prior runs of another skill. One
skill, `release`, is not shipped — it acts on this repo's own distribution, so it is repo-local
and invoked bare as `/release`.

| Phase | Skill | Invoked by | What it does |
|---|---|---|---|
| **0. Bootstrap** (per repo, once) | `cla-init` | you or Claude | Scaffold the `cla.io/` tree + empty overlay stubs (structure only, never facts) |
| | `sync-context` | you or Claude | Populate/reconcile `cla.io/project-facts.md` — the repo's shared facts (members, commands, ports, file maps) |
| | `save-permissions` | you or Claude | Persist tool permissions granted this session to `.claude/settings.local.json` |
| **1. Discover & shape** | `feedback` | you or Claude | Capture rough notes one at a time → a dated, grounded triage doc under `cla.io/feedback/` |
| | `shape-decision` | you or Claude | Walk a decision option-by-option with pros/cons + a recommended pick |
| | (`opsx:explore`) | n/a — vendored | OpenSpec's thinking-partner mode for investigating a problem before committing to a change |
| **2. Specify & plan** | `multi-spec` | you or Claude | Turn a shaped decisions doc into a batch of full OpenSpec proposals (stops at proposals) |
| | `review-change` | you or Claude | Pre-implementation review of an OpenSpec change: verify claims, symbols, file/reference reality, size it |
| **3. Build & ship** | `new-worktree` | you or Claude | Start an isolated git worktree (deps installed, env carried over) for parallel/safe work |
| | `lite-pr` | you or Claude | Lightweight end-to-end path for a small change: implement + docs + tests + PR + one review round |
| | `spec-to-pr` | you or Claude | Drive one OpenSpec change end-to-end to an opened, archived PR with review fixes applied |
| | `multi-lite` | **you only** | Chain several `lite-pr` runs extracted from one decisions doc, dependency-first |
| | `multi-pr` | **you only** | Chain several OpenSpec changes → PRs, merging each before its dependents (or stacking PRs on their parents when merging is unavailable) |
| **4. Review & assure** | `project-review` | you or Claude | CTO-level review of the whole repo: vision, structure, requirements, architecture, validation |
| | `annotate` | you or Claude | Render a doc as a page, open it chrome-less, and collect the user's own comments against selected passages — read back and worked through here |
| | (agents) | n/a — dispatched | `doc-sweeper` + `fact-gatherer` do the mechanical grep/verify legwork the ship + review skills delegate to |
| **5. Learn & improve** | `codify-learnings` | you or Claude | Review the current session for reusable lessons; propose doc/skill/hook/memory edits; log them `[loop]` |
| | `codify-retro` | you or Claude | Meta-review recent `codify-learnings` runs and improve that loop itself `[loop]` |
| | `spec-to-pr-retro` | you or Claude | Meta-review recent `spec-to-pr` runs and improve the orchestrator `[loop]` |
| | `report-upstream` | you or Claude | File a defect in CLA's own portable core as an issue against the canonical source |
| | `checkpoint` | you or Claude | Compact a session into a resumable briefing (`cla.io/checkpoints/`) |
| **Any phase** (utility) | `right-model` | you or Claude | Recommend the cheapest model + effort combo that can plausibly do a described task well, then optionally start it |
| | `diagnose` | you or Claude | Find a failure's cause instead of guessing: deterministic loop, ranked falsifiable hypotheses, regression test before the fix. Escalated from either Test phase after two rounds on one cause |

**"Invoked by" is derived, not curated.** A skill reads **you only** exactly when its
`SKILL.md` frontmatter sets `disable-model-invocation: true`. Every skill that carries it is an
unattended orchestrator that opens and merges pull requests, so a description match must
never start one — only you typing the command. Everything else can be triggered either by
you or by Claude recognising the task. The two non-skill rows are marked `n/a`: `opsx:explore`
is OpenSpec's, not CLA's, and the agents are dispatched by other skills rather than invoked.

**One reading was deliberately rejected, and is recorded so it does not arrive again: that this
column also says something about what a skill may CALL.** It does not. It says how a skill
*starts*, and CLA's skills compose across it in both directions. `lite-pr` invokes
`Skill(shape-decision)` when a description is too open-ended to plan from — one `you or Claude`
row calling another — and the two **you only** rows are the heaviest callers in the tree:
`multi-lite` drives a full `lite-pr` run per candidate, `multi-pr` a full `spec-to-pr` run per
change. One distinction is worth stating, because it is easy to misread as a chain: consulting
another skill's *reference file* is not calling that skill. `spec-to-pr`'s Review reads
`skills/review-change/references/checklist.md` and executes it inline, and its `SKILL.md` forbids
`Skill(cla:review-change)` outright — the hop would cost a skill load and buy no capability.

### Typical flows

- **Small change:** `shape-decision` → `lite-pr` (or straight to `lite-pr`).
- **Larger change:** `shape-decision` → `multi-spec` → `review-change` → `spec-to-pr`.
- **A batch off one decisions doc:** `multi-lite` (small) or `multi-pr` (spec-scale).
- **After a session:** `codify-learnings`; periodically `*-retro` to tune the loops.

## Always-on guardrails (hooks)

Guard hooks wire themselves via the plugin's own `hooks/hooks.json` when the plugin loads — no
`settings.json` step. Two dispatchers (one for Bash/PowerShell, one for Edit/Write) each run
several leaf hooks in one Python process — 8 distinct leaf hooks between them (6 on the
Bash/PowerShell matcher, 2 on Edit/Write) — plus `warn-wholesale-rewrite` wired
directly on PostToolUse: 9 leaf hook files in all. They run throughout every phase.
**Blocks** (`block-*`) stop a tool call; **asks** (`ask-*`) escalate to a permission prompt
instead of blocking outright; **warns** (`warn-*`) surface a caution without blocking.

**Blocks:** `block-cd-in-bash` (working dir is already repo root; a `cd` persists and breaks later
calls) · `block-unsafe-recursive-delete` (`rm -rf` and PowerShell equivalents) ·
`block-worktree-path-escape` (writes escaping a worktree boundary).

**Asks:** `ask-destructive-git` (force-push, `reset --hard`, branch force-delete, PR merges, and other
destructive-but-possibly-legitimate git/gh commands; `ALLOW_PR_MERGE=1` drops only the PR-merge
confirmation, for the `multi-*` chainers' unattended runs). It also prompts on
`git checkout <path>`, `git restore <path>`, a forced `git checkout -f`/`git switch -f`, and
`git clean` — but only when they would actually destroy uncommitted work, so on a clean tree they
stay silent.

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
  prose under `skills/`, a second covers source files across five roots — `skills/`, `agents/`,
  `hooks/`, `output-styles/`, `lib/`. For which file types the second one opens, read
  `_iter_scanned_source_files` in the checker itself: this file is exempt from every scanner, so a
  suffix list copied here goes stale with nothing to catch it, and one did.
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

Each takes one optional flag, `--repo-root <path>` (default: the repo the process is in, resolved
via git), and reports through its exit code — **`0`** clean, **`1`** violations with every offending
file, line and path named, **`2`** could-not-run, which is never a pass. Stdlib Python only; nothing
to install.

**They do not have the same subject, and only one of them is worth putting in your gate.**

- **`check_fact_paths.py` reads YOUR repo.** Every repo-relative path named in
  `cla.io/project-facts.md` or in a `cla.io/overlays/<skill>.md` must still resolve on disk. This is
  the one that guards your `cla.io/` content, and the one worth wiring in. `/cla:sync-context` runs
  it once after it writes; **beyond that, you own when it runs** — your gate, your pre-commit, or by
  hand. Nothing in the plugin schedules it.
- **`check_no_project_tokens.py` reads a PLUGIN TREE**, and which one depends on how you installed.
  It scans that tree for leaked project tokens and hardcoded developer paths, using your
  `cla.io/project-tokens.local.md` as the vocabulary to scan *with*. `--repo-root` locates that
  token list — and, if the repo you point it at **vendors** a plugin tree at
  `.claude/plugins/cla/`, it scans that tree instead of the installed one. So:
  - **Marketplace install (the normal case).** There is no vendored tree, so it scans the read-only
    version-keyed cache — identical for everyone and clean by construction. **Wiring it into your
    gate there buys a check that passes without saying anything about your repo.** Run it if you
    want to confirm a release is clean against your own token list; do not mistake it for a check
    over your own files.
  - **Vendored tree (you keep a plugin tree in the repo and edit it).** Then it really is checking
    files you own, and it belongs in your gate exactly as it does in the authoring checklist.

> **Coming from a `0.x` release?** Every release up to and including `cla--v0.10.0` shipped the
> plugin's own pytest tree, and the guidance of that era told you to wire its
> `conformance-checks/tests` directory into your local gate. **Nothing from `1.0.0` on ships that
> tree, under any name** — it moved to the source repo's own
> development tree when the shipped plugin was reduced to assets you can actually invoke. A gate
> still pointing at it either fails on a missing directory or, worse, passes while checking nothing.
> Delete that wiring. What it was guarding about YOUR repo — dead paths in `cla.io/` — is now
> `check_fact_paths.py` above, which is the replacement to wire in; the token scan that scope also
> carried is `check_no_project_tokens.py`, whose subject is the plugin rather than your repo, so
> read the split above before deciding whether it belongs in your gate at all.

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
