# CLA developer guide

A progressive introduction to **CLA — Cris Logic Artisan**, the Claude Code dev-workflow harness
that lives in this repo. Each section builds on the one before it: start a session, ship one small
change, then climb the ladder to shaped decisions, spec-driven changes, batches, and the loops
that make the next run better. Skim the [cheat sheet](#cheat-sheet-i-want-to--which-skill) if you
just need the right skill name.

## 1. The mental model

CLA is a *process* layer, not product code. Three kinds of pieces, one split that makes it
portable:

- **Skills** (`/cla:<name>`) — the workflows. Each one carries a change through a phase of its
  life: capture → decide → specify → build → review → learn. You invoke them by slash command;
  all but `multi-lite`, `multi-pr`, `cla-init`, `save-permissions`, `codify-learnings`,
  `spec-to-pr-retro` and `right-model` — which set
  `disable-model-invocation: true` (the first two open and merge PRs unattended; the rest are run
  deliberately and kept out of the always-loaded listing) — can also be triggered by describing
  what you want in natural language.
- **Guard hooks** — always-on guardrails wired automatically when the plugin loads. They block,
  ask, or warn on risky tool calls (a push to main, an `rm -rf`, a commit that would collide with
  another session). You don't invoke them; they fire when a convention is about to be broken.
- **Helper agents** (`doc-sweeper`, `fact-gatherer`) — mechanical grep/verify workers the ship and
  review skills delegate to. You rarely call them directly.

The split that everything obeys: **procedure is portable, facts are per-repo.**

- Portable procedure lives in the synced core (`skills/`, `agents/`, `hooks/`, `output-styles/`)
  and is identical in every repo that uses CLA.
- Your repo's facts live in overlays (`cla.io/overlays/<skill>.md`, `*.local.md`) and in the
  repo-root `cla.io/` tree (decisions, feedback, retro ledgers, `project-facts.md`). They sit in
  the repo, not the plugin directory, so installing or updating the plugin never touches them.

Keep that split in mind and the rest of the harness follows from it.

## 2. Your first session

Two audiences, two starts — pick yours:

**In a repo that installed CLA from the marketplace** (section 10): start `claude` normally.
The installed plugin is already active — there is no launcher to run, and none is shipped.
Check it worked: type `/cla:` and the skill list should autocomplete.

**In THIS repo (developing the harness):** use the launcher at the repo root, which loads the
plugin live from the working tree so you run the harness you are editing:

```bash
./cla                      # macOS / Linux / Git Bash
cla.cmd                    # native Windows
```

The launcher prints, then runs:

```
claude --plugin-dir <repo>/.claude/plugins/cla --permission-mode auto --model opus --effort medium
```

Everything after `./cla` is forwarded to `claude`, so `./cla --model sonnet --effort low` overrides
the default when a session doesn't need the top tier.

Two things to know before your first prompt:

- **`--permission-mode auto` skips per-action confirmation prompts.** Intentional — the guard
  hooks are the safety layer — but know it before you run it.
- **The CLA output style applies automatically** (`force-for-plugin: true`): short sentences,
  bullets over paragraphs, answer first. Session prose will look terser than stock Claude Code.

Check it worked: type `/cla:` and the skill list should autocomplete.

## 3. Your first change: `lite-pr`

`lite-pr` is the lightweight end-to-end path for a small, well-understood change — the one to
reach for first. It implements, keeps docs and tests in sync, opens a PR, then runs one automated
PR-review pass with a single fix round. It never merges.

```
/cla:lite-pr Rename the `retry_count` config key to `max_retries`, keeping a
deprecation fallback for the old name
```

The phases, in order — Explore → Plan → Implement → Test → Ship → Review:

1. **Explore** (optional) — only when the ask is genuinely open-ended; it hands off to
   `shape-decision` for the same Q&A described in section 4.
2. **Plan** — posted in the conversation for visibility, not a blocking gate.
3. **Implement** on a branch: code + `spec.md`/`CLAUDE.md`/tests kept in sync.
4. **Test** — the flow's only stop point: an unresolved failure halts the run.
5. **Ship** — commit, push, PR opened.
6. **Review** — one automated PR-review pass on the opened PR, with a single fix round.

Note the order: the PR opens *before* the review pass, and one fix round is the whole budget —
deeper multi-round review is `spec-to-pr`'s territory.

Invoked with no arguments, it infers the change from the conversation (say, a just-finished
`shape-decision`); it asks only when there's no usable context. And there is no mid-flight
escalation path: if the change turns out bigger than expected during Implement, stop and reassess
manually — re-plan, split it, or switch to the spec-scale path in section 5.

## 4. Shape first, build second

Two capture-and-decide skills sit upstream of any build, for when you know something is wrong or
wanted but not yet *what to do about it*.

**`feedback` — get raw notes out of your head and grounded in the repo.**

```
/cla:feedback the retro aggregator double-counts reruns
```

It takes notes one at a time (keep typing them; say "done" to finish), does a read-only grounding
pass per note (which file, a probable root cause — never a confirmed diagnosis), and writes a
dated triage doc under `cla.io/feedback/`. Capture only — it deliberately refuses to debug.

**`shape-decision` — walk one decision to a documented pick.**

```
/cla:shape-decision should hook config live in hooks.json or per-hook overlay files?
```

It walks the options one at a time with pros/cons, recommends a pick, and writes a decisions doc
under `cla.io/decisions/`. That doc is a first-class input: `multi-spec`, `multi-lite`, and
`multi-pr` all consume it directly.

Typical small-change flow: `shape-decision` → `lite-pr` (or straight to `lite-pr` when the shape
is already obvious).

## 5. Spec-scale changes: `multi-spec` → `review-change` → `spec-to-pr`

When a change is too big to hold in one prompt, CLA drives it through OpenSpec (the vendored
`opsx:*` skills) instead of skipping the thinking:

1. **`multi-spec`** — turn a shaped decisions doc into a batch of full OpenSpec proposals
   (`proposal.md`, `tasks.md` and spec deltas; `design.md` only on a stock trigger), authored and committed one change at a
   time. It stops at proposals — nothing is implemented yet.

   ```
   /cla:multi-spec cla.io/decisions/hook-config-redesign.md
   ```

   (With no argument it picks the most recent doc under `cla.io/decisions/`.)

2. **`review-change`** — pre-implementation review of one proposal: verifies its claims, checks
   that named symbols/files/references actually exist, sizes it, and dispatches parallel review
   agents when it's large. Cheap insurance before any code is written.

   ```
   /cla:review-change add-hook-config-overlay
   ```

3. **`spec-to-pr`** — drive one OpenSpec change end-to-end: implement, keep docs/tests in sync,
   apply review fixes, archive the change, open the PR. Stops before merge, always.

   ```
   /cla:spec-to-pr add-hook-config-overlay
   ```

   It also accepts a fresh description (it creates the change first). With no argument it infers
   the change from the conversation (typically a just-finished `opsx:explore`); with no usable
   context and exactly one open change, it resumes that change. It prompts only when zero or
   several exist — don't run it bare and expect a pick-list.

For exploration *before* any of this, `opsx:explore` is the thinking-partner mode — CLA
orchestrates around OpenSpec rather than replacing it.

**When you want to read a proposal yourself rather than have an agent check it, use `annotate`.**
`review-change` reviews a change against the repo's standards; `annotate` puts it in front of *you*.
It renders a Markdown document — or a whole OpenSpec change — as a self-contained page, opens it in
a chrome-less browser window and serves it on loopback, so you can select any passage and comment on
it. Each comment is stored with the passage it is about, in a file the session reads back and works
through.

```
/cla:annotate <change-id or openspec/changes/<change-id>>
/cla:annotate <path>.md
```

A change opens as one page with proposal, design, tasks and spec deltas in tabs, each passage's
counterpart inlined beneath the block it answers to — tabs alone show one side at a time — plus a
derived coverage view of which claims nothing names. Read that view as a reading aid rather than a
verdict: an uncovered row means no task names that bullet's file, not that the work is missing.

It never writes to what you are annotating; the page is served read-only and a test pins that across
a full annotate-and-rebuild cycle. Say "read my annotations" in a later session to pick the comments
back up.

## 6. Batches: `multi-lite` and `multi-pr`

One decisions doc often yields several independent changes. The chainers run them
dependency-first, unattended:

- **`multi-lite`** — extracts every lite-pr-sized candidate from a decision-shaped doc, sequences
  them, confirms the plan once up front, then runs `lite-pr` on each.
- **`multi-pr`** — same idea at spec scale: runs `spec-to-pr` on each OpenSpec change in
  dependency order, and enforces that every Critical/Important review finding is actually fixed
  before moving on.

```
/cla:multi-lite cla.io/decisions/hook-config-redesign.md
/cla:multi-pr change-a change-b        # or no args = auto-discover every open change
```

**The one place CLA merges — when it can.** The single-change skills stop at an opened PR, but a
chainer must get a dependency's code under its dependents before they can build on it. The default
is a merge, through the `ask-destructive-git` guard: `ALLOW_PR_MERGE=1 gh pr merge <#> --squash
--delete-branch` — the prefix drops *only* the PR-merge confirmation, for that one command.
Force-push and `reset --hard` still prompt. No PR is ever merged without you having chosen to run
a chainer.

`multi-lite` asks for its merge policy at the plan gate. **`merge-each-clean`** (recommended)
merges every candidate whose review left no Critical/Important finding unresolved. Before each
merge it checks the PR again: the full test gate is green on the exact head being merged, the head
has not moved, and GitHub reports no conflicts or failing checks. A re-run after an interruption
finishes what the run left undecided, but never merges commits pushed after review — those PRs
stay open for you. A 9-candidate run then ends with
open PRs only for the candidates that could not merge, each with its reason.
**`merge-dependencies-only`** merges only what must land before a later candidate: one another
candidate builds on, or one whose changed files move shared environment state (a migration, seed
data, provisioning). It leaves the rest open for you. An autonomous invocation gets `merge-dependencies-only` unless it names
the wider policy.

Some host runtimes refuse `gh pr merge` outright, regardless of allowlist. For that case (or by
choice, when you want the whole chain reviewable before anything lands) `multi-pr` has a
**stacked** policy: no merges at all — each dependent branches off its parent's feature branch via
`spec-to-pr`'s `--pr-base` flag, its PR opens against the parent, and the run ends by handing you
the ordered, parents-first landing commands. Land a stack with **merge commits**
(`gh pr merge <#> --merge --delete-branch`), never squash — squashing a stacked parent makes every
child PR re-show the parent's diff and conflict; the details and the squash-required alternative
live in `multi-pr`'s change-loop reference.

## 7. Parallel and safe: worktrees

Git's HEAD is per-clone, not per-session — two concurrent sessions in the primary clone would
collide on one branch. CLA's answer is worktrees.

One way in, at any point: **`/cla:new-worktree`**. Run it before you start, or the moment you
realise mid-flight that the work wants isolation — the skill creates the worktree, migrates you,
installs dependencies, and carries over gitignored env files (per-repo facts a plain `git worktree
add` cannot know). Run inside a worktree that already exists, it detects that and runs the setup
half only.

There is no penalty for deciding late, which is why there is only one path. There used to be a
second launcher, `claw`, whose only job was to create the worktree *before* Claude started — it
existed to dodge a presence-heartbeat guard that could block a second session from committing for
an hour. That guard was deleted (0 recorded blocks across 127 session transcripts), and the
launcher went with it.

`block-worktree-path-escape` stops a Write/Edit from escaping the worktree boundary from inside
one — a common failure mode when a stale absolute path sneaks into a prompt.

## 8. The guardrails you'll meet

Hooks wire themselves from `hooks/hooks.json` at plugin load — no `settings.json` step. Two
dispatchers each run several leaf hooks in one Python process (6 on the Bash/PowerShell matcher, 2
on Edit/Write), plus `warn-wholesale-rewrite` wired directly on PostToolUse: **9 leaf hooks**, in
three severities.

- **Blocks** stop the tool call:
  `block-cd-in-bash` (the working dir is already repo root, and a `cd` persists across calls — use
  absolute paths), `block-unsafe-recursive-delete` (`rm -rf` and its PowerShell equivalents),
  `block-worktree-path-escape` (section 7).
- **Asks** escalate to a permission prompt, because the action may be legitimate:
  `ask-destructive-git` (force-push, `reset --hard`, branch force-delete, PR merges, and a
  `git checkout`/`git switch`/`git restore`/`git clean` that would discard uncommitted work — see section 6 for the
  `ALLOW_PR_MERGE` hatch). This matters more than it looks: the launcher runs
  `--permission-mode auto`, which suppresses the usual confirmations, so this hook is what
  restores one.
- **Warns** surface a caution and let the call through: `warn-comment-dates`,
  `warn-stacked-pr-merge` (a merge into a branch that open child PRs are based on — states the retarget-vs-close rules and the squash hazard),
  `warn-stray-scratch-artifact` (scratch files left in the repo root),
  `warn-heredoc-escape-mangling` (a heredoc body carrying a backslash escape the shell/inner-language
  layering eats — `\n` arrives as a real newline), and
  `warn-wholesale-rewrite` (a `Write` replacing a tracked file with a materially shorter one — it
  asks you to name what you dropped, since a `Write` keeps only what you carried across).

**Direct pushes to `main` are not guarded by any of these.** That protection is a git `pre-push`
hook at `hooks/git/pre-push`, which git hands the already-resolved refspec, so no command spelling
can evade it and it covers pushes from a terminal or IDE too. A plugin cannot write to
`.git/hooks`, so every clone installs it once:

```bash
cp .claude/plugins/cla/hooks/git/pre-push .git/hooks/pre-push && chmod +x .git/hooks/pre-push
```

**Why a git hook and not a PreToolUse hook, since the question recurs.** A PreToolUse hook has to
parse a command string, and every spelling it does not anticipate is a hole: `--all`, `--mirror`,
`heads/main`, `git.exe`, a here-string, a quoted remote. Several were closed one at a time and the
list never felt finished. The git hook sees the refspec git has already resolved, so there is no
string left to evade — and it covers pushes from a terminal or an IDE, which no PreToolUse hook ever
saw. The cost is the `cp` line above, once per clone.

When a hook fires, read its message before working around it — each one states why and what to do
instead. The guards encode the harness's conventions; routing around them defeats the point.

## 9. The learning loops and `cla.io/`

Every run leaves state behind in the repo-root `cla.io/` tree — decisions, feedback docs, retro
ledgers (`retro/*-runs.jsonl`), lessons learned, and (in a consuming repo) the consolidated
`project-facts.md`. That state feeds the `[loop]` skills:

- **`codify-learnings`** — run it at the end of a session worth learning from. It reviews the
  conversation for reusable lessons and proposes concrete edits — to docs, skills, hooks, or
  memory — interactively, then logs the fixes and re-offenses in `lessons-learned/`.

  ```
  /cla:codify-learnings
  ```

- **`spec-to-pr-retro`** — a meta-loop. Run periodically, it reviews recent `spec-to-pr` runs from
  the ledger and improves the orchestrator. `codify-learnings` needs no retro of its own: it checks
  each session failure against the rules earlier runs wrote, and escalates a rule that failed again.

The discipline throughout: a ledger earns its place by a reader. `lib/log_run.py` accepts one,
`spec-to-pr-runs`, which `spec-to-pr-retro` reads. The ledgers retired for having no reader are
listed by `cla-init`, which offers to delete the ones a repo still holds.

Three utilities worth knowing at any phase:

- **`right-model`** — describe a task, get the cheapest model + effort combo that can plausibly do
  it well, and optionally start it with those settings. Bias is downward; it escalates only on a
  concrete signal.
- **`save-permissions`** — persist tool permissions granted this session to
  `.claude/settings.local.json`, so the next session doesn't re-prompt.
- **`diagnose`** — find a failure's cause rather than guessing at fixes: build a deterministic
  pass/fail loop, rank falsifiable hypotheses before touching anything, write the regression test
  before the fix. Both Test phases escalate to it after two rounds spent on one stated cause.

## 10. Adopting CLA in another repo

CLA is installed *into* a repo, scoped to that project, not installed globally. Four steps, in the
destination repo:

1. **Install the plugins CLA depends on.** CLA is orchestration over existing skills, not a
   replacement for them, and `plugin.json` has no way to declare a dependency — so nothing installs
   these for you, and nothing warns when one is missing. A phase that needs an absent plugin simply
   cannot run, which reads as CLA being broken.

   OpenSpec and `pr-review-toolkit` are required outright; `commit-commands` on the lightweight
   path; `plugin-dev` conditionally. **Which skill reaches which, and how hard each one is:**
   [the plugin's own README](.claude/plugins/cla/README.md#install-these-first--cla-calls-out-to-them-and-cannot-substitute-for-them).
   That file is the one a consuming repo receives, so the list lives there and nowhere else — three
   copies of a four-row table is three things to keep in sync, and an earlier draft of this very
   section had already drifted from its sibling before either was read.

2. **Install CLA from the marketplace** — the plugin arrives as a versioned snapshot pinned to an
   exact release tag:

   ```bash
   claude plugin marketplace add crisradu75/logic-artisan
   claude plugin install cla@cris-logic-artisan --scope project
   ```

   Then run `claude plugin list` and check `cla`'s status isn't an error (e.g. "isn't installed").

   > **Windows:** run the install from the same shell your sessions launch with — Git Bash, or a
   > Claude Code session's own Bash tool. PowerShell's `Set-Location` rewrites path casing to the
   > on-disk name, and Claude Code records an install keyed by that exact string; a session launched
   > from a shell using a different casing for the same directory can then find `cla` "enabled in
   > project settings but isn't installed" — a status `claude plugin list` reports as
   > "✘ failed to load" — with none of `cla`'s skills or guard hooks active, and nothing else saying
   > so. If both spellings are genuinely in use, install from each.

3. **`/cla:cla-init`** — scaffold the `cla.io/` tree and empty overlay stubs. Idempotent and
   never-clobber: safe to re-run on a partially-scaffolded repo.
4. **`/cla:sync-context`** — populate `cla.io/project-facts.md` with the repo's facts: workspace
   members, dev/build/test commands, ports, affected-file map, test locations, env files. This is
   the single physical copy of every fact the skills share.

Then fill in the per-skill `cla.io/overlays/<skill>.md` overlays as the skills prompt for
facts. Pick up newer releases with `/plugin marketplace update`; your overlays and `cla.io/` are
untouched by an install, because they live in the repo rather than the plugin directory.

**Optionally, wire the staleness checker into the destination repo's own gate.** The plugin ships no
test tree — the installed tree is a read-only cache with no pytest gate over it, so a guard filed as
a test module would be unreachable there — so the conformance guards ship as stdlib-Python programs
you invoke, each taking an optional `--repo-root` and reporting `0` clean / `1` violations named /
`2` could-not-run:

```bash
python3 <plugin>/skills/sync-context/scripts/check_fact_paths.py
```

That is the one whose subject is the destination repo: every repo-relative path named in
`cla.io/project-facts.md` or an overlay must still resolve. `/cla:sync-context` runs it once after
it writes, and nothing else schedules it — **the consuming repo owns when it runs.**

Its sibling, `<plugin>/skills/_shared/scripts/check_no_project_tokens.py`, scans a *plugin* tree for
leaked tokens and developer paths, using the repo's `cla.io/project-tokens.local.md` as the
vocabulary to scan with. **Which tree it scans depends on the install**, and that decides whether it
belongs in a gate: `--repo-root` locates the token list, and if that repo vendors a plugin tree at
`.claude/plugins/cla/` the scan re-targets to it (`_vendored_plugin_root`), otherwise it falls back
to the tree the script itself lives in. So against an ordinary **marketplace install** it scans the
read-only cache — clean by construction, and wiring it into that repo's gate asserts nothing about
that repo. Against a **vendored tree** it checks files the repo owns, and earns its place there for
the same reason the authoring checklist runs it.

A repo whose gate still wires the plugin's `0.x`-era `conformance-checks/tests` directory should
delete that wiring — that directory has not shipped since `1.0.0`, and a gate pointing at it either
fails on a missing path or passes while checking nothing. `check_fact_paths.py` is what replaces the
half of it that was about the consuming repo.

Improvement flows one way, and deliberately so: a skill improved while working in a consuming repo
is reported back with `/cla:report-upstream` (which files an issue against this repo) and returns
in the next release. There is no per-asset sync — the legacy `update-cla` engine that provided one
was deleted when the marketplace became the sole distribution route.

## 11. Working on CLA itself (this repo)

Contributing to the harness rather than using it? The rules themselves are in `CLAUDE.md`, which
every session here loads. This section is the reference behind them: what runs, where things live,
and why each script exists.

- **Run the whole verification story locally — there is no CI, by design:**

  ```bash
  pytest plugin-tests -q -n auto --dist loadfile    # all pytest scopes (1) — the whole suite
  node --test plugin-tests/node/mechanical-checks.test.mjs
  openspec validate --specs --strict                # the live specs
  ```

  All three green is the only gate before a PR — and `pytest` does not reach the Node suite, so it
  is a separate command. Watch the skip count — a skipped guard has not run (one pre-push permission-bit test
  always skips on Windows), and the skip count is also how you check a parallel run against a
  serial one. `-n auto --dist loadfile` needs `pytest-xdist`; drop both flags without it. Use
  `--dist loadfile` rather than plain `-n auto`, and run `mutate.py` serially — `CLAUDE.md` states
  the rules, and section 12 has the measurements behind them.

- **The plugin's tests do not live in the plugin.** `.claude/plugins/cla/` is published whole to
  consuming repos and carries only assets a consumer can use, so every test, mutation batch, the
  mutation runner and the pytest config live in `plugin-tests/` at the repo root. Source-repo-only
  is now structural rather than declared: the dev tree exists only here, so there is nothing to mark
  and nothing to skip. The `SOURCE-REPO-ONLY.md` mechanism and its guard were deleted with the
  runner that read them.
- **Bare `pytest` over the dev tree IS the gate** — the inversion of the old rule, which forbade it.
  There is one scope now, not twelve, because the split rested on a single module-basename collision
  that no longer exists. Inside `plugin-tests/tests/` the old scope names survive as areas
  (`conformance/`, `consistency/`, `launcher/`, `hooks/`, `lib/`, and 5 skills with tests plus
  `_shared/` under `skills/`). Iterate on one with `pytest plugin-tests/tests/<area>`.

- **Keep facts out of the synced core.** A conformance guard fails if a project-specific token or an
  absolute developer path leaks into `skills/`, `agents/`, `hooks/`, `output-styles/` or `lib/`. It
  is a program (`skills/_shared/scripts/check_no_project_tokens.py`), not a test, precisely so it
  also runs in a consuming repo, which has no pytest gate over its plugin cache. Overlays in this
  repo stay neutral stubs — this is the source, not a consumer.

- **Scripts are stdlib-only Python** (no third-party deps beyond pytest itself), with one Node
  exception, `project-review/scripts/mechanical-checks.mjs`. The spec-to-pr retro aggregator
  carries a copy of `lib/log_run.py`'s ledger-directory resolver, kept in step by hand;
  `plugin-tests/tests/consistency/test_ledger_dir_agrees.py` checks that the writer and the
  aggregator resolve the same directory, run from a subdirectory of the repo.

- **`CLAUDE.md` is the authoritative working-instructions file** — read it before a change. It
  holds the rules only; the layout, the script table and the guard reference are below, and the
  evidence behind each rule is in section 12. Deferred work lives in GitHub issues: `TODO.md` was
  retired on 2026-08-28 (issues #173–180), and the root `TODO.md` that reappears is a different
  artifact — `/cla:spec-to-pr`'s Handoff writes Suggestion residue there, in this repo and in every
  consuming repo.

- **Platform-divergent code is only ever exercised on the machine you are on.** Several hooks shell
  out to real `git` and branch on Windows vs POSIX, and the directory-alias tests take a junction
  path on Windows and a symlink path everywhere else (the shared `make_dir_alias` fixture in
  `plugin-tests/tests/conftest.py`). A green local run is evidence about that machine, not about the
  others.

- **The Playwright suite is opt-in by construction.**
  `plugin-tests/tests/skills/annotate/test_page_in_a_browser.py` drives the annotation page in a
  real headless Chromium. It calls `pytest.importorskip` at module level, so a checkout without
  Playwright runs the suite exactly as before and sees one skip — nothing is added to the install
  path, and nothing in the shipped plugin depends on it. Enable it with:

  ```bash
  pip install playwright && playwright install chromium
  ```

### Layout

The published plugin — everything here ships to a consuming repo:

```
.claude/plugins/cla/
  .claude-plugin/plugin.json   manifest
  agents/                      doc-sweeper, fact-gatherer (mechanical helpers other skills delegate to)
  hooks/                       guard hooks + hooks.json wiring
  lib/log_run.py               the one ledger writer, invoked as a program
  output-styles/               the project's writing convention (force-for-plugin: true)
  skills/_shared/references/   references two or more skills read as authority (no SKILL.md — not a skill)
  skills/<name>/
    SKILL.md                   the skill itself (portable procedure)
    references/                supporting docs (portable; overlays live in cla.io/overlays/)
    scripts/                   deterministic helpers (stdlib Python)
```

**`lib/` is the odd one out in the plugin**: not a skill (no `SKILL.md`) and not a guard hook. It
holds `log_run.py`, the one ledger writer, which `spec-to-pr` invokes as a program.

…and the two repo-root trees that do NOT ship, which is where the tests and the release workflow
went:

```
plugin-tests/                  the repo's ONE pytest scope
  pyproject.toml               testpaths, norecursedirs, and the 9-entry pythonpath
  mutate.py                    mutation checker: break a fix, confirm a test fails, restore
  tests/<area>/                conformance, consistency, launcher, hooks, lib, skills/<name>
  mutants/<area>/              mutation batches, mirroring tests/ — a sibling, never a child
  scripts/measure_load.py
  scripts/migrate_run_records.py
  node/mechanical-checks.test.mjs
.claude/skills/release/        repo-local skill, invoked as /release (not /cla:release)
  SKILL.md
  scripts/check_shipped_tree.py
```

`pyproject.toml` sets `testpaths = ["tests"]`, `norecursedirs` (pytest's default list plus
`mutants` and `node`), and a `pythonpath` reaching out of the dev tree into the plugin, because the
scripts under test stay shipped and only their tests moved. `mutants/` mirrors `tests/`'s
subdirectory names so a guard's batch is found by name, and sits beside `tests/` so the batches are
never collected as tests. A batch is optional. `plugin-tests/tests/launcher/` tests the repo-root
`cla`/`cla.cmd` launchers, which live outside the plugin tree entirely.

### The guards that police the fact/procedure split

Of the four portable guards, **two reach consuming repos and two do not, and the difference is
where they live.** No project token in synced core
(`skills/_shared/scripts/check_no_project_tokens.py`) and no dead path in `cla.io/project-facts.md`
or an overlay (`skills/sync-context/scripts/check_fact_paths.py`) are skill scripts inside the
shipped tree, so a consumer gets them and can run them as programs. No hardcoded plugin path and no
SKILL.md with broken frontmatter or a dead reference are pytest guards in `plugin-tests/`; they
police the plugin's own source and do not reach a consumer at all, which is deliberate — a consuming
repo has no pytest gate over its plugin cache, so a guard filed as a test module is unreachable
there in practice.

`check_no_project_tokens.py` runs as a program and, in this repo, also as a subprocess of a
`plugin-tests/tests/conformance/` test. One scanner covers `SKILL.md`/`references/*.md` prose under
`skills/`; a second covers source files under **five** roots — `skills/`, `agents/`, `hooks/`,
`output-styles/` and `lib/` — because the marketplace ships the whole directory (`.md` there is
frontmatter-exempt the same way `SKILL.md`'s own `description:` is). The two scanner families do
not have the same reach: the hardcoded-path one (`test_no_hardcoded_plugin_paths.py`) reaches
strictly more file types than the project-token one, which is why a file can be covered by one and
not the other. **The suffix lists are not written in any doc**: read
`SCANNED_SUFFIXES`/`REQUIRED_SUFFIXES` in that guard and `_iter_scanned_source_files` in the
checker. Some shipped files are reached by no scanner on purpose (the plugin's own `README.md` names
this repo and the plugin path), and nothing tracks which.

### Every script, and why it exists

A script earns its place only by doing something a direct command plus a sentence of prose
cannot do reliably. Seven that failed that bar were deleted; these are the survivors, and the
rule going in is the rule going out — **if a script here can't be justified in one line, it
isn't a survivor.** (Guard hooks are listed in section 8.)

Shipped scripts are given relative to `.claude/plugins/cla/` and never repeat that prefix — a bare
top-level path (`lib/...`) for a script outside `skills/`, and a
skill-relative path (`<skill>/scripts/...`, no leading `skills/`) for a script that belongs to one.

| Script | Why prose can't do it |
|---|---|
| `plugin-tests/mutate.py` *(dev tree)* | Breaks a fix, confirms a test fails, restores byte-exactly — a judgement no reading of the test can substitute for. |
| `lib/log_run.py` | The one ledger writer: validates the record against its shape, enforces the 4 KiB atomic-append ceiling, refuses every ledger name but `spec-to-pr-runs.jsonl`. |
| `plugin-tests/scripts/measure_load.py` *(dev tree)* | Counts the words each skill puts in front of the model (session listing, `SKILL.md`, reachable references, curated per-run profiles) so a token-cutting change quotes a measured before/after; fails when a profile entry is no longer named directly by the file it says forces the read. |
| `plugin-tests/scripts/migrate_run_records.py` *(dev tree)* | One-off rewrite of old-shape `spec-to-pr-runs.jsonl` records into the shape `log_run.py` enforces: every mapping comes from a shape found in a real ledger, a valid record is left untouched, and one that still fails is reported and left exactly as it was. |
| `sync-context/scripts/check_fact_paths.py` | Existence-checks every repo-relative path the facts file and overlays name, in the *consuming* repo — which has no pytest gate over the plugin cache, so a checker filed as a test is unreachable there. |
| `_shared/scripts/check_no_project_tokens.py` | Four scans in one run over the consuming repo's install (prose tokens, source tokens, absolute developer paths, readability); the readability check is what stops the other three passing vacuously. |
| `spec-to-pr-retro/scripts/spec_to_pr_aggregate.py` | Deterministic counting over every repo's spec-to-pr ledger listed in `cla.io/fleet.local.md` (falling back to this repo's, and saying so), because any one repo's sample is thin enough to mislead; reports how often Revise's automatic round 2 still finds something, the evidence its default rests on; `--nudge` is the one line Handoff prints when recent runs keep exhausting a cap (Revise: with findings left open) or repeating a warn reason. |
| `new-worktree/scripts/manual_worktree.py` | Routes around the Windows path-casing refusal, and refuses to remove a worktree holding uncommitted work — where a model slip destroys work. |
| `.claude/skills/release/scripts/check_shipped_tree.py` *(repo-local)* | Enumerates the tracked plugin tree against a 14-pattern allowlist before a tag is cut. `git-subdir` has no exclusion field, and the obvious denylist was measured to miss 7 of 72 dev-only files — including the two runners and the release skill itself. |
| `project-review/scripts/mechanical-checks.mjs` | Cross-file key-set parity from repo-supplied config; hand-grepping it is exactly what it replaces. Configured by 1 of 4 consuming repos on 2026-10-08: agentic-air declares 6 checks in its own copy of the plugin, in project-review's `project-context.md` reference file, section "Mechanical checks — repo specifics" (run in that repo on 2026-10-08: `awk '/^## Mechanical checks — repo specifics/{f=1;next} /^## /{f=0} f' <that file> \| grep -c '"type":'` → 6). That repo copied the plugin into its own tree and is no longer on the marketplace plugin, so its config does not live in `cla.io/overlays/project-review.md`, where the other three (claude-plugins, interoga-ro, market-distiller-mcp) would put it (`grep -c '"type"' */cla.io/overlays/project-review.md` → 0 in each). Decision P4a in `cla.io/decisions/plugin-surface-simplification-2026-10-08.md` scheduled its deletion on the 0-of-4 count and is being re-decided. |
| `annotate/scripts/annotations_store.py` | The annotation corpus: append-only merge rule, tombstones, and a refusal to read past a conflict marker rather than fabricate a corpus from both sides. |
| `annotate/scripts/render_doc.py` | Markdown → an annotatable page whose every block carries a source line, plus the anchor check that says which annotations the last edit orphaned. |
| `annotate/scripts/render_html.py` | Instruments an author's own HTML in place — attributes spliced at source offsets, so stripping them returns the original bytes and the document under review stays the document under review. Refuses a file whose markup already uses those attributes, because that collision mis-anchors every annotation in the element and is invisible on the page. |
| `annotate/scripts/annotate_server.py` | Serves the page on loopback, validates each record before it reaches the file, and opens a chrome-less browser window. |
| `annotate/scripts/openspec_change.py` | Extracts a change's claims and the links between them, with thresholds measured over 355 real changes rather than reasoned about — the first cut left 83% of promises falsely uncovered. |
| `annotate/scripts/sweep_changes.py` | Runs the link detector over a corpus of real changes and reports the coverage split — the command behind every threshold in `openspec_change.py`, and how a consuming repo re-measures before trusting the coverage tab. |
| `annotate/scripts/render_change.py` | Lays a change's files into one annotatable page, binding each claim to its block one-match-or-none and keeping injected counterparts outside the blocks whose offsets they would corrupt. |
| `spec-to-pr/scripts/probe_state.py` | Resume detection across `openspec status`, `gh`, and `<base>..<branch>` ranges, with branch-resolution fallback. |
| `_shared/scripts/git_state.py` | One deterministic exit code for "an in-progress rebase/cherry-pick/merge exists", checked at every commit boundary across four skills. |
| `spec-to-pr/scripts/_git_common.py` | Repo root plus the `branch-prefix.local.md` overlay contract, for `probe_state.py`. |

### Adding a skill

Four contracts, each enforced by a test rather than by convention — so a miss fails the suite
rather than shipping. (It was five: a fifth required a test scope to carry `pyproject.toml` AND
`tests/` together, enforced by the deleted runner's "near-miss" rule. Both the requirement and its
enforcer are gone — a skill has no scope of its own any more.)

1. **`skills/<name>/SKILL.md` is the entrypoint, and the directory name is the command.** Its
   frontmatter needs a non-empty `name` and `description`, and `name` must equal the directory —
   otherwise `/cla:<dir>` resolves to nothing. Pinned by
   `plugin-tests/tests/conformance/test_skill_lint.py`.
2. **The `description` is trigger metadata, not documentation.** It is what natural-language
   invocation matches against; keep it under the style ceiling the same test enforces. Write it in
   the third person and name concrete trigger phrases.
3. **Every reference the body names must exist.** A bare `references/<file>` means *this skill's
   own* file; to cite another skill's, write the explicit
   `${CLAUDE_PLUGIN_ROOT}/skills/<owner>/references/<file>`. Both mistakes fail the same test.
4. **Project-specific facts go in an overlay, never in the body.** If the skill reads
   `cla.io/overlays/<name>.md`, add it to `cla-init`'s seeding list so a fresh repo gets a stub.
   The token guard fails the suite if a repo name leaks into the body.

Then add the skill to the plugin README's phase table and to the cheat sheet below. If its frontmatter
forbids model invocation, also add it to the one sentence naming those skills in `CLAUDE.md` and in
section 1. `plugin-tests/tests/consistency/test_doc_facts.py` fails if the phase table
misses the skill or any of those three copies disagrees with the frontmatter; nothing checks the
counts. A new skill's tests
go in `plugin-tests/tests/skills/<name>/`, not beside the skill.

## 12. Evidence behind CLAUDE.md's rules

`CLAUDE.md` states each rule once, in its compressed form, and points here from its first
paragraph for the measurement, incident or decision that produced it. Kept verbatim so the evidence
survives; each heading names the rule it backs. Where `CLAUDE.md` compressed a rule when it became
rules-only (change `claude-md-rules-only`), the full earlier wording is kept here too, so nothing the
compression left out is lost.

### The parallel gate: measurements and the cache incident

**Measured on this repo 2026-09-05:** serial 296.6s and `-n auto --dist loadfile` 149.6s
(2.0x). The pass count moved several times inside the branch that measured it and is deliberately not repeated here — run the command; `--collect-only -q` gives the total without executing anything. Plain `-n auto` ran 84.9s and 100.9s on
two consecutive invocations of the same tree — and **the first of those failed 3 tests
the other two forms passed**, all in `tests/hooks/test_hooks_wiring.py`
(`test_wiring_refuses_when_the_probe_is_unusable`, the `truncated` cases). The second
invocation was green. So the plain `-n auto` trap CLAUDE.md describes is not a hypothetical any more; it is the most
recent measurement, and the failure did not reproduce on demand, which is the whole
problem with it.

The mechanism was never proven, but the shared state it named was real and is now gone.
Those tests built their environment with `_inherited_env`, which copies the real `HOME`,
so the probe resolved its cache to the **developer's own** `~/.cache/cla/pyexe` and wrote
it — one shared mutable file, several xdist workers, and `--dist loadfile` keeps that
file's tests on one worker, which fits only plain `-n auto` failing. An autouse fixture in
`plugin-tests/tests/hooks/conftest.py` now relocates it per test via `CLA_PROBE_CACHE`.

**State this carefully.** The failure never reproduced on demand, so no run count proves
it fixed, and none is offered as if it did. What is measured is narrower and is the
reason the change is worth having anyway: deleting `~/.cache/cla/pyexe` and running the
full suite used to recreate it and now does not. A test suite writing a developer's home
directory was a defect on its own terms, whatever it did to the scheduler.

**Numbers here go stale, and this paragraph has been stale before.** Re-measure rather
than quoting it; the counts above move with every test added.

**The rules' full wording, as `CLAUDE.md` carried it before the rules-only compression.**
`loadfile` pins every test in a file to one worker. Without it a module's tests are split across
workers, and `tests/skills/annotate/test_page_in_a_browser.py` has module-scoped fixtures that own
a loopback server port and a Chromium process — two workers building those race for the port.
That suite skips wherever Playwright is absent, which is exactly why a green plain `-n auto` here
is not evidence: it means those tests did not run.

A parallel run is trusted only when its pass AND skip counts match a serial run of the same tree.
Skip counts matter here specifically: `tests/consistency/` and `tests/launcher/` skip their whole
scope conditionally, and the annotate browser suite skips without Playwright — so a dropped scope
shows up as a skip-count change and nowhere else. The check is necessary, not sufficient: it
catches gross divergence, not a test passing for the wrong reason.

### Why `mutate.py` stays serial

It shells out as `pytest -q -x <targets>` and reads the exit code to decide killed vs survived — a
judgement its own docstring says every check exists to protect. This is why `-n auto` is NOT in an
`addopts` key: `addopts` applies to every invocation, so putting it there would silently change how
the mutation runner executes.

### Why `--dist loadfile` is worth its premium

The peer repo `claude-plugins` hit the same class of
failure from a different cause and recorded the rule as "the full-suite pass is luck
about which worker gets which file, not evidence of safety". The premium over plain
`-n auto` was 18s when first measured and about 50-65s on 2026-09-05; either way it is
the whole price of not finding out the hard way, and the run above is what finding out
looks like.

### Why the twelve test scopes became one

The twelve-scope split existed for exactly one reason — pytest's default import mode cannot hold
two test modules with the same basename — and the collision set is now empty. Measured with
`git ls-files '.claude/plugins/cla/**/tests/*.py' | xargs -n1 basename | sort | uniq -d`, the only
duplicate is `conftest.py`, which pytest special-cases per directory. (Note for anyone re-deriving
this: the split's usual justification named a second collision on `scripts/log_run.py`, which
`git ls-files | grep log_run` shows never existed — one module, one test. The measurement, not the
folklore.)

### Why the Playwright suite earns its exception

Keep it to what a string cannot answer — geometry, stacking, what a breakpoint does to the flow,
whether a round-trip leaves the page in the state it claims. Anything checkable by reading the
generated source belongs in `test_render_doc.py`, which is cheaper and always runs.

**Why it earns the exception.** Every other check on the annotation page is a string grep
against generated HTML and JS, which is all a stdlib suite can do. During the
review of the margin change, a reviewer simulated 21 plausible regressions
against the rendered page and **19 survived all 46 tests then covering it** — and
two defects that shipped in that change were found only by driving a browser: an
open drawer laid on top of the margin at 1440px, and a note drawn at
`top:-135.78px` beside nothing for a block on a hidden tab. Neither has a string
to grep for. Its mutant batch re-breaks six such regressions and all six die
(`plugin-tests/mutants/annotate/test_page_in_a_browser.py`).

### The five checks: the shape every escape had

The plugin's behaviour lives mostly in markdown, so a prose edit ships like code but nothing
compiles it. Every defect that reached review in this repo had one shape: the artifact was checked,
the system it lands in was not.

### Check 1: what an inserted step inherits

**The rule's wording before the plain-language rewrite.** A phase added between two others
inherits whatever the next one asserts on entry — a clean-tree check, a state file, a branch
assumption.

### Check 2: why a rewrite is diffed

A rewrite silently loses rules an edit would have preserved; "it reads better" is not evidence that
nothing went missing.

### Check 3: the escapes that produced it

**The rule's full wording before the rules-only compression.** Two halves, and the second is the
one that keeps escaping. For a **diagnosis**, search the same source for counterexamples before
shipping it, not just for supporting cases — a table of three examples proves nothing if three
counterexamples sit in the same file. For a **measurement** — "measured", "verified", "zero
violations", any number — name the command that produced it, in the same commit. If you cannot name
one, you did not measure it: delete the claim or go run it. Reasoning that feels like measurement is
the most expensive thing in this repo, because it ships with a measurement's authority. **And a
measurement is evidence about the tree and conditions it ran on, nothing else.** A pair asserting
sameness — "unchanged", "same counts", "no regression" — must come from one tree, and say so;
measured on two it asserts a third claim, that conditions matched, with no command behind it. A
before/after delta is the exception, not a violation: "faster", "up exactly N" are two trees by
construction, so name both. Re-asserting an earlier number as current is the same defect with one
run missing, and a number true under one platform, shell or edition is not true generally until
someone runs the others.

Measured 2026-09-12, three times in one session: a firing count restated as 84 that re-ran at 86 (test runs had moved it); a gap table that went stale inside the change that invalidated it, claiming 33% headroom where 2.4% remained; and a `Remove-Item` failure measured on Windows PowerShell 5.1 and reported as universal, where the tool actually runs pwsh 7.6.6 and the command works. Recorded in `cla.io/lessons-learned/lessons-learned.md` (2026-08-14): review caught six such claims in one session, and in one of them the comment's own text contained the token it declared absent. Two more were invented blockers — "widening the scan roots fails on the test fixtures" survived until someone widened the scan roots and got zero violations. A seventh was caught by the merge check on the PR that added this very rule: a commit count nobody had run, in three files including the hook written to measure it.

### Check 4: the fix's second branch

A fix is a change like any other and earns the same evidence the original code needed; "the
reviewer's finding is now handled" is not that evidence. A fix also has a second branch nobody
looks at: correcting one return path of a function commonly breaks another, which is how
`lint_profile` traded a silent no-op on the default path for the identical no-op on the overlay
path.

### Check 5: the escape that produced it

Check 5 is check 4's second-branch problem one level up: there, the other branch is inside the
function; here, it is in a file you were not looking at. Running the one scope you work in green is
what makes the omission feel finished.

Measured 2026-08-23 — `scan()` in `check_fact_paths.py` gained a third return value, the three callers in `tests/conformance/` were updated, that scope passed, and a fourth caller in `tests/consistency/` went red only when the full suite ran. One `grep -rn "<name>(" ` would have found it before the first edit.

### A clean mutation run: the commits behind the rule

Measured on this repo: commits `1cf09da` and `0027bc7` each
recorded "three mutations checked, all caught" and each shipped a critical that a later
review found — the mutants covered the branch the author was reasoning about, not the
branch they got wrong.

### A killed mutant: the case behind the rule

The kill proves the suite reacts to that edit; it proves neither the code nor the test right. A
test written from a wrong mental model kills mutants exactly as reliably as a correct one, and the
green result reads as confirmation. Worst where the mutant is the *simpler* form of the code: if the
simpler form is correct, the test defending the original is defending the defect, and the gate pins
it while reporting green.

Reported from a
consuming repo (issue #193), where the assertion killing a column-offset mutant was
itself the defect: the mutant died, the gate reported green, and the wrong belief
reached a PR. A review agent reasoning from the type's stated invariant caught it
there; no gate did.

### A survivor: the batch behind the rule

Some mutants cannot be killed, because the edit is unobservable in a correct tree — a floor
constant that only binds when something is missing, or two expressions that agree on every input
the real files reach. **Where a guard's two candidate rules agree on all correct inputs, mutate the
input, not the guard** (CLAUDE.md now says it as "add a bad input file instead of breaking the
check"). Never leave one in a batch: a survivor nobody acts on trains the next reader to skip the
whole list.

Measured 2026-08-28 with
`python3 plugin-tests/mutate.py plugin-tests/mutants/consistency/test_check_labels_agree.py`
over a then-nine-mutant batch: two survived and neither could have done otherwise. The
`defined - _delegated_labels() - covered` one was fixed by mutating the *prose* the guard
reads instead of the guard, which does discriminate and is killed; the `_MIN_MARKED_LINES`
floor constant was deleted from the batch with the reason recorded in it.

(The batch has since been reworked, so re-run it rather
than expecting nine.)

### Concurrent mutation runs: the flake behind the rule

Recorded after
a guard flaked 3-of-5 runs under a concurrent batch, and reproduced twice on 2026-08-28
during the review of the commit that added CLAUDE.md's rule — one agent read a mutated
`check_script_drift.py`, another aborted at preflight on a leftover `.mutate-backup`.

### Matching the checking to the change

The five checks are priced for a *fix* or a new component — the cases where being wrong is
expensive and invisible. An increment to something already built and already tested does not earn
them, and paying them anyway is not caution, it is waste with the shape of rigour.

### Repeated green runs: the session behind the rule

Recorded
2026-08-22, after adding a navigation rail to `annotate` cost five full scope runs, a whole
sweep of the entire suite, and an unrelated change to a server, for an edit whose real gate
was one 13-second run over that one area and looking at the page. (The runner those runs
used is gone; the lesson is about the count, not the command.)

### Unarchived merges: the measurement behind the rule

Measured 2026-08-28: three fully-implemented merged changes had accumulated unarchived (merged without Archive), and `openspec/specs/cla-plugin/spec.md` was missing 11 requirements — the shipped skills carried behaviour no live spec described.

### The scan roots: why five

It was eight until the dev tree moved out; the three `*-checks/` entries then named directories that no longer exist, and a stale root is worse than a missing one, because the guard refuses to run at all rather than quietly scanning less.

### The coverage lists: why they are not restated

They were spelled out in CLAUDE.md's architecture paragraph and went stale inside the very change that widened them — twice, once in the widening and once in the fix, each time three lines below a sentence saying not to restate them.

Both used to be written out as a list and a count, and both went stale while nothing noticed — the defect issue #178 named.

### No CI: the decision behind the rule

Not an incident — an owner decision. CI existed briefly: `.github/workflows/tests.yml` ran pytest on
ubuntu and windows × Python 3.11/3.13 plus the Node suite, added in #18. It was deleted in #24
(commit `b444dd2`, "This repo does not want CI"), which also wrote down the two consequences
CLAUDE.md still carries: code that differs by platform is exercised only on the machine you are on,
and nothing gates a merge, so the local run before opening a PR is the only gate.
`git log --oneline -- .github/workflows` shows both commits.

### Stdlib-only shipped scripts: why

No incident either; the reason is the rule's own. A repo installs the plugin as a copied folder and
never runs a `pip install` for it, so a third-party import in a shipped script fails on the first
machine that lacks the package. The rule is as old as this repo's first CLAUDE.md (`85af744`, #2:
"All scripts are stdlib-only Python"). The one exception, the Playwright browser suite, is test-only
and opt-in; its case is under "Why the Playwright suite earns its exception" above.

### Releasing: the history behind the rules

The never-move-a-tag rule, the no-local-marketplace rule, and why a release is a three-file edit
are each told under "Release and distribution history" below.

## Release and distribution history

Background a working session rarely needs, which is why it lives here rather than in `CLAUDE.md`.
The operative rules — the three-file bump, the preconditions, the never-move invariant — are in
`/release`'s own SKILL.md (repo-local at `.claude/skills/release/`, not shipped, because a
consuming repo has no catalog of its own to bump); this section is only the *why* behind them.

**How the catalog publishes.** `.claude-plugin/marketplace.json` at the repo root publishes one
plugin, `cla`, from `.claude/plugins/cla/` (`git-subdir` source, `url` + `path`, schema verified
against the live docs). It pins an **exact release tag**, not a moving major tag, which is why a
release is a deliberate three-file edit and why consumers pick a new release up only on
`/plugin marketplace update`. Consumers add the marketplace from the repo:

```bash
claude plugin marketplace add crisradu75/logic-artisan
claude plugin install cla@cris-logic-artisan --scope project
```

**The versioning line.** The `0.9.x`/`0.10.x` validation line closed when a real task was run
end-to-end through the plugin in a consuming repo — the gate `1.0.0` was waiting on. Versioning
from there is ordinary semver, as `CLAUDE.md` states it.

**A published tag is never moved.** `0.9.0` was cut, a consumer installed it, and the very next fix
therefore became `0.9.1` rather than a re-tag — moving it would have changed what that consumer had
already fetched. That single episode is the origin of the rule.

**A local-directory marketplace is a development convenience, never a distribution route.** It was
used once, to exercise an install before the catalog change was pushed, and it carries a trap worth
naming: the catalog is then read from a working tree, so a locally-bumped `ref` advertises a tag
that may never have been pushed — the install fails with nothing visibly wrong in the manifest.
Sourcing the catalog from GitHub keeps catalog and tag moving together through one push.

**An install is a snapshot, not a link.** Every source type — including a local path — is copied
into the versioned cache at `~/.claude/plugins/cache`. That is why developing the harness itself
uses `--plugin-dir` (section 2) instead: it is the only mode that reads the working tree live.

**The `claw` launcher and the isolation guard, both deleted.** `claw` existed only to create a
worktree *before* Claude started, so a session would never register a presence heartbeat in the
primary clone — a heartbeat written by the worktree-isolation guard, which could block a second
session from committing for an hour. That hook recorded 0 blocks across 127 session transcripts and
was deleted; the launcher went with it, leaving `/cla:new-worktree` (section 7) as the single path.

**The `update-cla` file-sync engine, deleted.** It predated the marketplace and duplicated it
badly: a per-file 3-way reconcile with a provenance lockfile, solving a problem a whole-directory
versioned snapshot does not have. Worse, it synced the launchers that kept consumers on it. A repo
still carrying a `.cla-sync-lock.json` can delete that file; nothing reads it.

Migrating a repo off it is two commands plus that deletion — `claude plugin marketplace add
crisradu75/logic-artisan`, then `claude plugin install cla@cris-logic-artisan --scope project` —
and also drop any in-repo `.claude/plugins/cla/` copy it kept. An unreferenced copy is dead weight,
but a repo that *also* launches with `--plugin-dir` pointed at it runs two registrations of the
same skills, and nothing detects that. Two things the sync used to handle now happen once, at
migration time: a repo with a tuned check must author its `*.local.md` overlay after installing
(an absent overlay is a silent no-op, and nothing warns), and improvements now flow one way —
`/cla:report-upstream` files an issue here and the fix returns in the next release.

**If drift detection is ever rebuilt, three constraints killed the last attempt** and are worth
carrying into any replacement: treat an asset already identical to source as satisfied, not as
"missing from the group"; check overlay presence against local state rather than only when the
asset is being rewritten, or it never fires for already-synced repos — the entire affected
population; and tolerate any malformed declaration shape, since one bad edit would otherwise break
discovery for every consumer.

## Cheat sheet: "I want to…" → which skill

| I want to… | Reach for |
|---|---|
| Ship a small, clear change | `lite-pr` |
| Dump rough observations somewhere useful | `feedback` |
| Decide between approaches | `shape-decision` |
| Turn a decision into spec proposals | `multi-spec` |
| Sanity-check a proposal before building | `review-change` |
| Read and mark up a document or a change yourself | `annotate` |
| Drive one spec'd change to a PR | `spec-to-pr` |
| Run a batch of small changes unattended | `multi-lite` |
| Run a batch of spec'd changes unattended | `multi-pr` |
| Work in parallel without collisions | `/cla:new-worktree`, at any point in a session |
| Pick the cheapest adequate model for a task | `right-model` |
| Stop guessing at a stubborn failure | `diagnose` |
| Stop re-approving the same permissions | `save-permissions` |
| Get a whole-repo health review | `project-review` |
| Capture this session's lessons | `codify-learnings` |
| Tune the spec-to-pr loop | `spec-to-pr-retro` |
| Set up CLA in a new repo | marketplace install → `cla-init` → `sync-context` |
| Pull newer CLA core into a repo | `/plugin marketplace update` |
| Report a defect in the portable core | `report-upstream` |
| Publish a new version of the plugin | `/release` (repo-local, not `/cla:release`) |
| Hand off a long session | `checkpoint` |
