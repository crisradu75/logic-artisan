# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

`logic-artisan` is the canonical home of **CLA — Cris Logic Artisan**, a Claude Code dev-workflow
harness packaged as a plugin. It holds no product/application code — it's the *process* layer
(skills, guard hooks, helper agents) that carries a change from idea → spec → isolated
implementation → review → opened PR, and feeds learnings back into the next run. Other repos install
this plugin from the GitHub marketplace and adapt it to their own context via overlays.

Everything lives under `.claude/plugins/cla/`, which is exactly the directory the marketplace
catalog publishes as the plugin's source path.

**Distribution is GitHub, and only GitHub.** `.claude-plugin/marketplace.json` at the repo root
publishes one plugin, `cla`, from this subdirectory (`git-subdir` source, `url` + `path`, schema
verified against the live docs). It pins an **exact release tag**, not a moving major tag, so
publishing a release is a deliberate three-file edit: bump `version` in the plugin's own
`plugin.json`, the `ref` here, and the release line below — all in one commit. A test fails when they disagree. Consumers
pick the new release up on `/plugin marketplace update`.

Consumers add the marketplace from the repo, never from a path:

```bash
claude plugin marketplace add crisradu75/logic-artisan
claude plugin install cla@cris-logic-artisan --scope project
```

Cut the tag with **`claude plugin tag`** (shape `<name>--v<version>`); it refuses unless
`plugin.json` and the marketplace entry already agree. **Current release: `cla--v0.10.0`.** `0.9.x`
is the validation line; it becomes `1.0.0` once a real task has been run end-to-end through the
plugin in a consuming repo.

**A published tag is never moved** — cut it only from `main`, only after review. **Never publish
from a local-directory marketplace.** Background for both rules, and the deleted `claw` launcher:
DEVELOPER-GUIDE.md "Release and distribution history".

**Launching a session in THIS repo:** use the `cla` (POSIX) / `cla.cmd` (Windows) launcher at the
repo root rather than typing `claude` directly. It resolves its own absolute path, so it always
passes `--plugin-dir <repo>/.claude/plugins/cla` regardless of your cwd:

```bash
./cla   # claude --plugin-dir <repo>/.claude/plugins/cla --permission-mode auto --model sonnet --effort medium
```

`--plugin-dir` loads the plugin live from this working tree, so you run the harness you are
editing. Without it the skills/hooks are inert files — no `/cla:*` commands, no guard hooks.
**Note:** `--permission-mode auto` bypasses per-action confirmation prompts; the guard hooks are
the safety layer.

**Starting work in a worktree.** Use `/cla:new-worktree` at any point — before starting, or once
you realise mid-flight that the work wants isolation. No penalty for deciding late.

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
design. Each skill that ships tests (5 today), plus `skills/_shared/`, plus `lib/`, plus `hooks/`,
plus `conformance-checks/`, plus `consistency-checks/`, plus `launcher-checks/`, is its own isolated
pytest scope — 11 in total — each with its own `pyproject.toml` (`testpaths = ["tests"]`, plus a
`pythonpath` pointing at that scope's importable code — `["scripts"]` for a skill and for
`consistency-checks`/`launcher-checks`, `["."]` for `hooks/` and `lib/`, whose modules sit at the
scope root, and none at all for `conformance-checks`, whose tests import nothing).

`lib/` and the three `*-checks/` scopes are the odd ones out: not skills (no `SKILL.md`) and not
guard hooks. `lib/` holds `log_run.py`, the one ledger writer every retro-logging skill invokes as
a program. `conformance-checks/` holds the four portable guards that police the fact/procedure split for the
whole plugin: no project token in synced core, no hardcoded plugin path, no dead path in
`cla.io/project-facts.md` or an overlay, and no SKILL.md with broken frontmatter or a reference
that resolves nowhere. `consistency-checks/` holds a drift check over the ledger-dir resolver that the isolation
rule below deliberately prevents from sharing a module, plus checks on this repo's own source;
**Three scopes are source-repo-only** — `consistency-checks/`, `launcher-checks/`, and `skills/release/tests/` assert facts about THIS repo's own source, so each carries a `SOURCE-REPO-ONLY.md` and `run_tests.py` skips it (with a summary SKIP row) in any repo that is not the canonical source; a consumer would otherwise get failures it cannot fix. `launcher-checks/` tests the repo-root `cla`/`cla.cmd` launchers, which live outside the plugin
tree entirely (`claw`/`claw.cmd` were deleted alongside the worktree-isolation guard, the hook they
existed to dodge).

All four sit outside the synced set (`skills`/`agents`/`hooks`/`output-styles`), but they do not
all mean the same thing by it. `consistency-checks` and `launcher-checks` guard this repo's own
source and are meant to stay here. `conformance-checks` is portable core that reaches
consuming repos because the marketplace publishes the whole plugin directory — where both guards
have caught real leaks. Several scopes
ship same-named helper modules (e.g. `scripts/aggregate.py`), so they can't
share one pytest process — this is why `run_tests.py` exists: it discovers every scope
(dir with both a pytest-configured `pyproject.toml` and a `tests/` subdir) and runs `pytest` once
per scope as a subprocess, then aggregates results. A dir with only one of those two signals is
treated as a "near-miss" (half-removed/misconfigured scope) and fails the run rather than being
silently skipped.

All scripts are stdlib-only Python (no third-party deps beyond pytest itself).

### Before shipping a change here, run four checks

The plugin's behaviour lives mostly in markdown, so a prose edit ships like code but
nothing compiles it. Every defect that reached review in this repo had one shape: the
artifact was checked, the system it lands in was not. These four checks are cheap and
each one comes from a real escape:

1. **Inserted a step into an ordered sequence?** Read the step immediately before and
   after **in the code**, not from memory of it. A phase added between two others
   inherits whatever the next one asserts on entry — a clean-tree check, a state file, a
   branch assumption.
2. **Rewrote a file rather than edited it?** Diff old against new and state what you
   dropped. A rewrite silently loses rules an edit would have preserved; "it reads better"
   is not evidence that nothing went missing.
3. **Asserting a diagnosis?** Search the same source for counterexamples before shipping
   it, not just for supporting cases. A table of three examples proves nothing if three
   counterexamples sit in the same file.
4. **Fixing a defect a review found?** Break the fix and confirm a test fails —
   `python3 .claude/plugins/cla/mutate.py <batch.py>` runs a batch of those (a batch is a
   Python module defining `MUTANTS`; see the tool's docstring) and reports survivors. A
   fix is a change like any other and earns the same evidence the original code needed;
   "the reviewer's finding is now handled" is not that evidence. A fix also has a second
   branch nobody looks at: correcting one return path of a function commonly breaks
   another, which is how `lint_profile` traded a silent no-op on the default path for the
   identical no-op on the overlay path.

**A clean mutation run is not a licence to stop.** It is evidence about the mutants you
thought of, and nothing else. Measured on this repo: commits `1cf09da` and `0027bc7` each
recorded "three mutations checked, all caught" and each shipped a critical that a later
review found — the mutants covered the branch the author was reasoning about, not the
branch they got wrong. So mutate what the fix *touches*, not what it targets, and treat a
green run as one input to the ship decision rather than the decision itself.

The one Node script in the plugin, `project-review/scripts/mechanical-checks.mjs`, has its own
sibling `node --test` suite. It is not a pytest scope, but `run_tests.py` **does** run it — as a
12th entry alongside the 11 pytest scopes — so a bare `run_tests.py` covers it. Run it alone only
while iterating on that one script:

```bash
node --test .claude/plugins/cla/skills/project-review/scripts/mechanical-checks.test.mjs
```

### No CI — verification is local, by design

This repo runs **no GitHub Actions and no CI of any kind**, deliberately. `run_tests.py` is the
whole verification story — every pytest scope plus the Node suite, in one command. Run it before
calling a change done.

Do not add a workflow. If a change seems to need one, raise it rather than adding it.

Two consequences worth holding, since nothing else will catch them:

- **Platform-divergent code is only ever exercised on the machine you are on.** Several hooks shell
  out to real `git` and branch on Windows vs POSIX, and the three directory-alias tests take a
  junction path on Windows and a symlink path everywhere else (`make_dir_alias`). A green local
  run is evidence about that machine, not about the others.
- **Merging is unguarded.** Nothing blocks a merge on tests, so the local run before opening a PR
  is the only gate that exists.

## Architecture — the fact/procedure split

CLA is portable across repos because it strictly separates *procedure* (generic, synced
everywhere) from *facts* (per-repo, never synced):

- **Synced core** — `.claude/plugins/cla/{skills,agents,hooks,output-styles}/`: portable procedure
  only. A pytest **conformance guard** fails if a distinctive project token, or a hardcoded absolute
  developer path, leaks into synced core — one scanner covers `SKILL.md`/`references/*.md` prose
  under `skills/`, a second covers every `.py` file plus `agents/*.md` and `output-styles/*.md`
  (frontmatter-exempt the same way `SKILL.md`'s own `description:` is). The source scanner covers
  eight roots — the four synced dirs plus `lib/` and the three `*-checks/` scopes — because the
  marketplace ships the whole directory. Four files still fall outside both scanners and are watched
  by hand: the plugin's own `README.md` (its install commands legitimately name this repo),
  `skills/_shared/README.md`, `run_tests.py`, and `mutate.py`. Non-`.py`/`.md` files
  (`hooks/hooks.json`, a skill's own `.mjs`) are outside both too. Listed in TODO.md.
- **Overlays** — `cla.io/overlays/<skill>.md` plus any `*.local.md` files beside them: the
  destination repo's own facts and tuned checks. They live in the repo, not the plugin directory,
  so an install never reaches them. In *this* repo they are neutral stubs (this is the source, not
  a consumer).
- **`cla.io/`** (repo root) — all per-repo state: `decisions/`, `feedback/`, `retro/` run ledgers,
  `lessons-learned/`, `project-tokens.local.md` (the conformance guard's curated token list), and
  (in a consuming repo) a consolidated `project-facts.md` and `terminology.md` (internal naming
  disambiguation, format owned by `sync-context`, written inline by other skills as terms resolve).
  Never part of the synced core; a staleness guard fails when a path named there no longer exists.

### Skill layout

```
.claude/plugins/cla/
  .claude-plugin/plugin.json   manifest
  run_tests.py                 aggregating test runner (all scopes + the Node suite)
  mutate.py                    mutation checker: break a fix, confirm a test fails, restore
  agents/                      doc-sweeper, fact-gatherer (mechanical helpers other skills delegate to)
  hooks/                       guard hooks + hooks.json wiring + tests
  output-styles/               the project's writing convention (force-for-plugin: true)
  skills/_shared/references/   references two or more skills read as authority (no SKILL.md — not a skill)
  skills/<name>/
    SKILL.md                   the skill itself (portable procedure)
    references/                supporting docs (portable; overlays live in cla.io/overlays/)
    scripts/                   deterministic helpers (stdlib Python)
    tests/                     that skill's isolated pytest scope
```

### Every script, and why it exists

A script earns its place only by doing something a direct command plus a sentence of prose
cannot do reliably. Seven that failed that bar were deleted; these are the survivors, and the
rule going in is the rule going out — **if a script here can't be justified in one line, it
isn't a survivor.** (Guard hooks are listed separately below.)

| Script | Why prose can't do it |
|---|---|
| `run_tests.py` | Runs each isolated scope as its own process and aggregates; there is no CI, so this is the only gate. |
| `mutate.py` | Breaks a fix, confirms a test fails, restores byte-exactly — a judgement no reading of the test can substitute for. |
| `lib/log_run.py` | The one ledger writer: validates the record, enforces the 4 KiB atomic-append ceiling, refuses a path-shaped ledger argument. |
| `consistency-checks/scripts/check_script_drift.py` | Compares the ledger-dir resolver across the writer and both readers. A divergence is silent — the retro reports zero runs, which reads as a cold start. |
| `codify-retro`, `spec-to-pr-retro` `scripts/aggregate.py` | Deterministic counting over 40–130 JSONL records, including malformed-shape and producer-drift buckets a reader would gloss. |
| `new-worktree/scripts/manual_worktree.py` | Routes around the Windows path-casing refusal, and refuses to remove a worktree holding uncommitted work — where a model slip destroys work. |
| `project-review/scripts/mechanical-checks.mjs` | Cross-file key-set parity from repo-supplied config; hand-grepping it is exactly what it replaces. Configured by 1 of 4 consuming repos today. |
| `spec-to-pr/scripts/probe_state.py` | Resume detection across `openspec status`, `gh`, and `<base>..<branch>` ranges, with branch-resolution fallback. |
| `_shared/scripts/git_state.py` | One deterministic exit code for "an in-progress rebase/cherry-pick/merge exists", checked at every commit boundary across four skills. |
| `spec-to-pr/scripts/_git_common.py` | Repo root plus the `branch-prefix.local.md` overlay contract, for `probe_state.py`. |

### Skills by life-cycle phase

Each skill is invocable as `/cla:<name>` or by natural language; `[loop]` marks a self-improvement
retro over prior runs of another skill.

| Phase | Skill | What it does |
|---|---|---|
| 0. Bootstrap (once per repo) | `cla-init` | Scaffold the `cla.io/` tree + empty overlay stubs |
| | `sync-context` | Populate/reconcile `cla.io/project-facts.md` |
| | `save-permissions` | Persist session tool permissions to `.claude/settings.local.json` |
| | `report-upstream` | File a defect in the plugin's own portable core as an issue against the canonical source |
| | `release` | Cut a new plugin release: preconditions, the three-file version bump, `claude plugin tag` |
| | `checkpoint` | Compact a session into a briefing the next one can resume from |
| 1. Discover & shape | `feedback` | Capture rough notes → a dated, grounded triage doc under `cla.io/feedback/` |
| | `shape-decision` | Walk a decision option-by-option with pros/cons + a recommended pick |
| 2. Specify & plan | `multi-spec` | Turn a shaped decisions doc into a batch of OpenSpec proposals |
| | `review-change` | Pre-implementation review of an OpenSpec change |
| 3. Build & ship | `new-worktree` | Start an isolated git worktree for parallel/safe work |
| | `lite-pr` | Lightweight end-to-end path for a small change: implement + docs + tests + PR |
| | `spec-to-pr` | Drive one OpenSpec change end-to-end to an opened, archived PR |
| | `multi-lite` / `multi-pr` | Chain several `lite-pr` / OpenSpec changes → PRs, dependency-first (multi-pr: merge each before its dependents, or stack PRs when merging is unavailable) |
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
of which runs several leaf hooks in one Python process — 7 distinct leaf hooks between them (5 on
the Bash matcher, 2 on Edit/Write), plus `warn-wholesale-rewrite` and `log-commit-provenance` wired directly on PostToolUse:
9 leaf hook files in all, which is what the bullets below enumerate. **Blocks**
(`block-*`) stop a tool call; **asks** (`ask-*`) escalate to a permission prompt instead of
blocking outright; **warns** (`warn-*`) surface a caution without blocking:

- **Blocks:** `block-cd-in-bash` (the working dir is already repo root, and a `cd` persists and
  breaks later calls in the same session; use absolute paths instead) ·
  `block-unsafe-recursive-delete` (`rm -rf` and PowerShell equivalents) ·
  `block-worktree-path-escape` (a Write/Edit escaping a worktree boundary from inside one).
- **Asks:** `ask-destructive-git` (a destructive-but-not-outright-blocked git command, e.g. a
  force-push or `reset --hard`) — returns exit 0 and escalates via `permissionDecision: "ask"`
  rather than blocking, since the action may be legitimate. Note this matters more than it looks:
  the harness runs `--permission-mode auto`, which suppresses the usual confirmations, so this
  hook is what restores one.
- **Warns:** `warn-stacked-pr-merge` (a merge into a branch that open child PRs are based on — states the retarget-vs-close rules and the squash hazard) ·
  `warn-comment-dates` · `warn-stray-scratch-artifact` (scratch files left in the repo root) ·
  `warn-wholesale-rewrite` (a `Write` replacing a tracked file with a materially shorter one —
  it asks you to name what you dropped, since a `Write` keeps only what you carried across).

**No direct push to main/master** is enforced by `hooks/git/pre-push`, NOT by a PreToolUse hook.
Git hands a `pre-push` hook the refspec it already resolved, so there is no command string to
parse and no `git.exe` / `-C` / quoting spelling that can evade it — and it covers pushes from a
terminal or IDE, which no PreToolUse hook ever saw. It is **not** installed automatically; a
plugin cannot write to `.git/hooks`. Per clone:

```bash
cp .claude/plugins/cla/hooks/git/pre-push .git/hooks/pre-push && chmod +x .git/hooks/pre-push
```

### Portability

Distribution is the GitHub marketplace and nothing else. A consuming repo installs the plugin as a
versioned snapshot pinned to an exact release tag, and picks up newer releases with
`/plugin marketplace update` — there is no per-file reconcile, and the install never writes
anywhere in the consuming repo outside the plugin cache.

Portability is therefore carried entirely by the fact/procedure split rather than by a merge
algorithm: the whole plugin directory ships verbatim, and everything repo-specific lives in the
consuming repo's own `cla.io/` tree (overlays, `project-facts.md`, `project-tokens.local.md`,
ledgers), which no install touches. Onboarding a fresh consuming repo: install from the
marketplace → `cla-init` (scaffold `cla.io/`) → `sync-context` (populate the facts).

A local improvement worth having everywhere goes upstream as an issue via `/cla:report-upstream`
and comes back in the next release — the deleted `update-cla` engine's per-asset multi-sourcing has
no replacement, by design.
