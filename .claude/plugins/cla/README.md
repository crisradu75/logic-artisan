# CLA — Cris Logic Artisan

A Claude Code **dev-workflow harness**, installed from a marketplace. CLA holds no product code. It
is the *process* layer: skills, guard hooks and helper agents that carry a change from a raw idea
through specification, isolated implementation and review to a PR, then feed what was learned into
the next run. It builds on existing plugins rather than replacing them, and keeps all per-repo state
(facts, decisions, feedback, retro logs, lessons learned) in the repo's own `cla.io/` tree.

**New here?** Install the dependencies below, then follow *Installing and updating*. The
[developer guide](https://github.com/crisradu75/logic-artisan/blob/main/DEVELOPER-GUIDE.md) walks
through a first session and a first PR.

## Install these first — CLA calls out to them and cannot substitute for them

`plugin.json` has no field for declaring a dependency, so **nothing installs these for you and
nothing warns when one is missing.** A phase that needs an absent plugin simply cannot run, which
reads as CLA being broken.

| Dependency | Reached by | How hard |
|---|---|---|
| **OpenSpec** — the `opsx:*` / `openspec-*` skills **and** the `openspec` CLI | `spec-to-pr`, `multi-spec`, `multi-pr`, `review-change` | **Required** for the spec-scale path. The CLI is called directly — `validate`, `archive`, `status`. (`lite-pr` calls `openspec validate` once and documents skipping it in a repo not using OpenSpec, so it degrades rather than failing.) |
| **`pr-review-toolkit`** — `code-reviewer`, `silent-failure-hunter`, `comment-analyzer`, `pr-test-analyzer`, `type-design-analyzer` | every PR-review pass: `spec-to-pr`, `lite-pr` (and `multi-pr`/`multi-lite`, which chain them) | **Required.** The Revise phase names these agents directly and defines no fallback for their absence. CLA ships no reviewer of its own. The toolkit reviewers hold Bash and Edit, so each dispatch passes `model:` and a prompt that forbids git commands and file edits; that prompt is the only safeguard. |
| **`commit-commands`** | `lite-pr`'s commit/push/PR step, and `multi-lite`, which chains it | **Required for the lightweight path.** The spec-scale path commits directly and does not need it. |
| **`plugin-dev`** — `skill-reviewer` | two rows of the Revise agent-selection table, plus `lite-pr`'s own agent picking | **Conditional.** Fires on a changed `SKILL.md` **frontmatter**, a new skill, a new command under `.claude/commands/`, or a prose-dominant diff — not on a body-only prose edit that is not prose-dominant. On a prose-dominant diff its model follows "Review sizing by risk" in `model-routing.md`; the frontmatter and new-skill cases are not in that table, so they run on Sonnet as `lite-pr`'s Review and `spec-to-pr/references/revise.md` say. |

There is no `openspec apply` CLI subcommand — apply is a skill. See `spec-to-pr/SKILL.md` for the
full list of subcommands the CLI actually ships.

## Scope — what CLA is and isn't

- **Is:** a repeatable, guard-railed pipeline for turning intent into reviewed, shippable changes,
  plus the self-improvement loops that keep the pipeline sharp.
- **Is:** portable across repos and tech stacks — project specifics live in your repo's `cla.io/`,
  never baked into the synced core (see *Architecture*).
- **Isn't:** product/app code, a CI system, or a deploy tool. The single-change ship skills
  (`lite-pr`, `spec-to-pr`) stop at an **opened PR**; the `multi-*` chainers may merge a dependency
  PR to unblock its dependents during an unattended run — but nothing here deploys, and no PR is
  merged without you having chosen to run a chainer.
- **Isn't:** a store of project facts. Those live in `cla.io/project-facts.md`, in the repo rather
  than the plugin, so no install touches them.

## The software life cycle, phase by phase

CLA's skills map onto the arc of a change. Each shipped skill is invocable as `/cla:<name>`, and
all but those marked **you only** below can also be triggered by natural language; `[loop]`
marks a self-improvement retro over prior runs of another skill. One
skill, `release`, is not shipped — it acts on this repo's own distribution, so it is repo-local
and invoked bare as `/release`.

| Phase | Skill | Invoked by | What it does |
|---|---|---|---|
| **0. Bootstrap** (per repo; re-run when facts go stale) | `cla-setup` | **you only** | Create whatever is missing of `cla.io/`, seed OpenSpec authoring rules, write `.claude/rules/cla-economy.md` (the plugin owns it and replaces it on every run), and populate or reconcile `cla.io/project-facts.md` — the repo's facts (members, commands, ports, file maps) |
| | `save-permissions` | **you only** | Persist tool permissions granted this session to `.claude/settings.local.json` |
| **1. Discover & shape** | `feedback` | you or Claude | Capture rough notes one at a time → a dated, grounded triage doc under `cla.io/feedback/` |
| | `shape-decision` | you or Claude | Walk a decision option-by-option with pros/cons + a recommended pick |
| | (`opsx:explore`) | n/a — vendored | OpenSpec's thinking-partner mode for investigating a problem before committing to a change |
| **2. Specify & plan** | `multi-spec` | you or Claude | Turn a shaped decisions doc into a batch of full OpenSpec proposals (stops at proposals) |
| | `review-change` | you or Claude | Pre-implementation review of an OpenSpec change: verify claims, symbols, file/reference reality, size it |
| **3. Build & ship** | `new-worktree` | you or Claude | Start an isolated git worktree (deps installed, env carried over) for parallel/safe work |
| | `lite-pr` | you or Claude | Lightweight end-to-end path for a small change: implement + docs + tests + PR + one review round |
| | `spec-to-pr` | you or Claude | Drive one OpenSpec change end-to-end to an opened, archived PR with review fixes applied |
| | `multi-lite` | **you only** | Chain several `lite-pr` runs extracted from one decisions doc, dependency-first |
| | `multi-pr` | **you only** | Chain several OpenSpec changes → PRs, merging each before its dependents |
| **4. Review & assure** | `project-review` | you or Claude | CTO-level review of the whole repo: vision, structure, requirements, architecture, validation |
| | `annotate` | you or Claude | Render a doc as a page, open it chrome-less, and collect the user's own comments against selected passages — read back and worked through here |
| | (agents) | n/a — dispatched | `doc-sweeper` + `fact-gatherer` do the mechanical grep/verify legwork the ship + review skills delegate to. The PR reviewers (`code-reviewer`, `silent-failure-hunter`, `comment-analyzer`) are `pr-review-toolkit` agents, which read the change from a diff file |
| **5. Learn & improve** | `codify-learnings` | **you only** | Turn the current session's failures into up to three fixes — tools and hooks before docs — escalating any rule that failed again; log them `[loop]` |
| | `spec-to-pr-retro` | **you only** | Meta-review recent `spec-to-pr` runs and improve the orchestrator `[loop]` |
| | `report-upstream` | you or Claude | File a defect in CLA's own portable core as an issue against the canonical source |
| | `checkpoint` | you or Claude | Compact a session into a resumable briefing (`cla.io/checkpoints/`) |
| **Any phase** (utility) | `right-model` | **you only** | Recommend the cheapest model + effort combo that can plausibly do a described task well, then optionally start it |
| | `diagnose` | you or Claude | Find a failure's cause instead of guessing: deterministic loop, ranked falsifiable hypotheses, regression test before the fix. Escalated from either Test phase on one cause: after two rounds in spec-to-pr, after one fix and one retry in lite-pr |

**"Invoked by" comes from each skill's frontmatter.** A skill reads **you only** exactly when its
`SKILL.md` sets `disable-model-invocation: true`, for one of two reasons. `multi-lite` and
`multi-pr` open and merge pull requests unattended, so a description match must never start one.
The rest are run deliberately (onboarding, retros, settings), and the flag keeps their descriptions
out of the skill listing every session loads. Everything else starts either when you invoke it or
when Claude recognises the task. The two `n/a` rows are not CLA skills: `opsx:explore` is
OpenSpec's, and the agents are dispatched by other skills.

The column says how a skill *starts*, not what it may call. `lite-pr` calls `shape-decision` when an
ask is too open to plan, and `multi-lite` and `multi-pr` drive a full `lite-pr` or `spec-to-pr` run
per item. Reading another skill's reference file is not calling it: `spec-to-pr`'s Review runs
`skills/review-change/references/checklist.md` inline and never invokes `review-change`.

### Typical flows

- **Small change:** `shape-decision` → `lite-pr` (or straight to `lite-pr`).
- **Larger change:** `shape-decision` → `multi-spec` → `review-change` → `spec-to-pr`.
- **A batch off one decisions doc:** `multi-lite` (small) or `multi-pr` (spec-scale).
- **After a session:** `codify-learnings`; periodically `spec-to-pr-retro` to tune the orchestrator.

## Always-on guardrails (hooks)

The hooks wire themselves from the plugin's own `hooks/hooks.json` when it loads; there is no
`settings.json` step. Two dispatchers (Bash/PowerShell and Edit/Write) run 8 leaf hooks between
them in one Python process each, and `warn-wholesale-rewrite` runs on its own after a Write: 9 leaf
hooks, active in every phase.

| Severity | Hook | Fires on |
|---|---|---|
| **Block**: the call does not run | `block-cd-in-bash` | a `cd`, which persists and breaks later calls (the working directory is already the repo root) |
| | `block-unsafe-recursive-delete` | a recursive, forced delete (`rm -rf`, `Remove-Item -Recurse -Force`) whose target is itself a symlink or junction, which would delete the real files behind it |
| | `block-worktree-path-escape` | a write that escapes the worktree boundary |
| **Ask**: a permission prompt | `ask-destructive-git` | force-push, `reset --hard`, branch force-delete and PR merges (`ALLOW_PR_MERGE=1` drops only the merge prompt, for the chainers' unattended runs); `git checkout <path>`, `git restore <path>`, a forced `checkout -f`/`switch -f` and `git clean`, but only when they would destroy uncommitted work; a saving `git stash` while a merge, cherry-pick or revert is in progress, because it drops `MERGE_HEAD`; a push that skips the `pre-push` guard (`--no-verify`, `core.hooksPath`, or `ALLOW_PUSH_TO_MAIN=1`) |
| **Warn**: a caution, and the call runs | `warn-stacked-pr-merge` | `gh pr merge --delete-branch` on a PR whose branch open child PRs are based on (states the retarget-first rule and the squash hazard) |
| | `warn-comment-dates` | a bare `YYYY-MM-DD` date added to a code comment in a `.py` or `.sh` file |
| | `warn-stray-scratch-artifact` | a `git add` or `git commit` while an untracked root file named like a mangled temp path (`AppData`, `LocalTemp`, `scratchpad`) is present |
| | `warn-heredoc-escape-mangling` | a heredoc body whose backslash escape the shell layers eat |
| | `warn-wholesale-rewrite` | a Write that replaces a tracked file with a much shorter one |

**Direct pushes to `main` are NOT guarded by any of these.** That protection is a git `pre-push`
hook at `hooks/git/pre-push`, which sees the refspec git already resolved, so no way of naming the
target branch evades it (only git's `--no-verify` flag, or the hook's `ALLOW_PUSH_TO_MAIN=1`
emergency override, skips it, and `ask-destructive-git` asks before either). It refuses the
remote's own default branch as well as `main` and `master`. A plugin cannot write to `.git/hooks`, so **every clone installs it
once. `<plugin>` is this plugin's installed directory, a version-keyed copy under
`~/.claude/plugins/cache/`; `find ~/.claude/plugins/cache -path '*hooks/git/pre-push'` prints the hook's path in each installed version:

```bash
cp "<plugin>/hooks/git/pre-push" .git/hooks/pre-push && chmod +x .git/hooks/pre-push
```

Until you run that, nothing stops a direct push.

## Architecture — the fact/procedure split

CLA is portable because it separates *procedure* (generic, synced everywhere) from *facts*
(per-repo, never synced):

- **The plugin** (`skills/`, `agents/`, `hooks/`, `output-styles/`, `lib/`) holds portable
  procedure only. A conformance guard, `skills/_shared/scripts/check_no_project_tokens.py`, fails
  if a project-specific word or a developer's absolute path leaks into it. One scanner reads
  `SKILL.md` and reference prose under `skills/`; a second reads source files across all five
  roots (for the file types, read `_iter_scanned_source_files` in the checker; a list copied here
  went stale once). It is a program, not a test, so it runs in your repo too: an installed plugin
  is a read-only cache with no pytest gate over it.
- **Overlays** — optional `cla.io/overlays/<skill>.md` files holding a rule specific to one skill in
  your repo, plus the machine-read `*.local.md` files beside them (such as `branch-prefix.local.md`).
  A skill reads its overlay only if it is there; no skill needs one. Facts never go in an overlay.
  They live in YOUR repo, not in the plugin: the installed plugin tree is a read-only, version-keyed
  cache, so anything stored there would be unwritable and would vanish on the next update.
- **`cla.io/`** (repo root) — all per-repo state: `decisions/`, `feedback/`, the run ledger
  `retro/spec-to-pr-runs.jsonl`,
  `lessons-learned/`, and **`project-facts.md`** — the one home for every command, path, port,
  install step and env file a skill reads. A **staleness guard**
  (`skills/cla-setup/scripts/check_fact_paths.py`, also a program) fails
  when a path named there no longer exists.

## Installing and updating

CLA is installed from its marketplace and enabled per repo:

```bash
claude plugin marketplace add crisradu75/logic-artisan
claude plugin install cla@cris-logic-artisan --scope project
```

To take a newer release, refresh the catalog, update, then restart the session:

```bash
claude plugin marketplace update cris-logic-artisan
claude plugin update cla@cris-logic-artisan
```

**The installed tree is read-only.** Never edit it: it is a version-keyed cache, so an edit either
fails or lands somewhere the next update discards. A fix that belongs in the harness goes back via
**`/cla:report-upstream`**, which files it as an issue against the canonical source. A fact that
belongs to your repo goes in `cla.io/`.

**Onboarding a fresh repo:** install (above) → `/cla:cla-setup` (scaffold `cla.io/`, write the economy rules file
`.claude/rules/cla-economy.md` and populate the facts) → install the `pre-push` hook (see *Guardrails*).

<details>
<summary><b>Coming from 1.x?</b> What changed and the one run that migrates you</summary>

The `cla-init` and `sync-context` skills were merged into `/cla:cla-setup`. Run
it once: it reports what your `cla.io/` is missing, proposes moving facts out of overlays into
`project-facts.md` and the stories of dated incidents into `cla.io/lessons-learned/` (any rule they
state stays in the overlay), and proposes deleting overlays left with no rule. The same run:

- lists the retired ledgers it finds (`codify-runs.jsonl` among them; only `spec-to-pr-runs.jsonl`
  is still written) and deletes them on your yes;
- adds a `.gitignore` line for the `multi-lite`/`multi-pr` run notes, which are now local working
  state, and offers to untrack any notes files git already tracks. Both chainers refuse to start
  until git ignores their notes.

Also gone: `codify-retro` (`codify-learnings` now escalates a rule that failed again), and
`multi-pr`'s choice of merge policy. It has one now: merge only what a later change needs, and
leave the rest open.

`log_run.py` now refuses a `spec-to-pr` run record of the wrong shape, and `spec-to-pr-retro` skips
an old-shape record it cannot read and names it. To rewrite old records once, run the migration
script from a clone of the source repo (it does not ship):
`python3 <clone>/plugin-tests/scripts/migrate_run_records.py cla.io/retro/spec-to-pr-runs.jsonl --dry-run`,
then again without `--dry-run`.

The marketplace install is the only route in. `update-cla`, the old pull-based file-sync updater,
has been deleted; a repo still carrying a `.cla-sync-lock.json` from it can delete that too.

</details>

## Testing

**The plugin ships no tests, on purpose.** Everything in this directory is something you can
invoke, read, or have fire on your behalf. An installed plugin is a read-only, version-keyed cache
with no pytest gate over it, so a test filed here could never run in your repo.

CLA's own suite runs in the repo that develops it, as one pytest scope outside the plugin
directory: the skills' tests, the guards over the hooks and the shared library, and the source
repo's own launchers and catalog. There is no CI; that local run is the gate. **None of it is for
you to run.** To check your own repo, the two guards above are programs:

```bash
python3 <plugin>/skills/_shared/scripts/check_no_project_tokens.py
python3 <plugin>/skills/cla-setup/scripts/check_fact_paths.py
```

Each takes one optional flag, `--repo-root <path>` (default: the repo the process is in, resolved
via git), and reports through its exit code — **`0`** clean, **`1`** violations with every offending
file, line and path named, **`2`** could-not-run, which is never a pass. Stdlib Python only; nothing
to install.

**They do not have the same subject, and only one of them is worth putting in your gate.**

- **`check_fact_paths.py` reads YOUR repo.** Every repo-relative path named in
  `cla.io/project-facts.md` or in a `cla.io/overlays/<skill>.md` must still resolve on disk. This is
  the one that guards your `cla.io/` content, and the one worth wiring in. `/cla:cla-setup` runs
  it once after it writes; **beyond that, you own when it runs** — your gate, your pre-commit, or by
  hand. Nothing in the plugin schedules it. A path containing a placeholder (`{...}` or `<...>`) is
  never checked, so write example paths with one (`{plugin}/scripts/common.py`); a stale line whose
  path also ends a tracked path elsewhere carries a hint naming where.
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
  plugin.json                  GitHub Copilot CLI (Agent Plugins 1.0) manifest, untested in a live Copilot CLI
  agents/                      doc-sweeper, fact-gatherer (mechanical helpers)
  com.github.copilot/agents/   the same two agents for GitHub Copilot CLI, generated from agents/ (untested in a live Copilot CLI)
  hooks/                       guard hooks + hooks.json wiring, and git/pre-push
  lib/                         log_run.py — writes the one run ledger, spec-to-pr-runs.jsonl
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

MIT licensed; see [LICENSE](https://github.com/crisradu75/logic-artisan/blob/main/LICENSE) in the
source repo.
