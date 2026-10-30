# CLA developer guide

**CLA — Cris Logic Artisan** is a Claude Code plugin that carries a change from idea to a reviewed
pull request. This guide starts with one session and one small PR, then adds a step at a time:
shaping decisions, spec-driven changes, batches, worktrees, and the loops that improve the next
run. Each section builds on the one before it.

**How to read it:**

| You want to… | Read |
|---|---|
| Get going | §1 to §3: how CLA is built, a first session, a first PR |
| Take on bigger work | §4 to §7: shaping, spec-scale changes, batches, worktrees |
| Know why a command was blocked | §8, the guardrails |
| Improve the next run | §9, the learning loops |
| Install CLA in your repo | §10 |
| Work on CLA itself | §11, then `CLAUDE.md` |
| Know why a rule exists | §12 and the release history: the evidence, kept in full |
| Find a skill by task | the [cheat sheet](#cheat-sheet-i-want-to--which-skill) |

## 1. The mental model

CLA is a *process* layer, not product code. It has three kinds of pieces:

- **Skills** (`/cla:<name>`) are the workflows. Each carries a change through a phase of its life:
  capture → decide → specify → build → review → learn. You run one by slash command, and
  all but `multi-lite`, `multi-pr`, `cla-setup`, `save-permissions`, `codify-learnings`,
  `spec-to-pr-retro` and `right-model` — which set `disable-model-invocation: true` (the first two
  open and merge PRs unattended; the rest are run deliberately and kept out of the always-loaded
  listing) — can also start when you describe the task in plain words.
- **Guard hooks** are always-on guardrails, wired when the plugin loads. They block, ask about or
  warn on risky tool calls: a force-push, an `rm -rf`, a `cd` that would persist across calls. You
  never invoke them.
- **Helper agents** (`doc-sweeper`, `fact-gatherer`) do the mechanical grep-and-verify work that
  the ship and review skills hand off. You rarely call them. The PR reviewers (`code-reviewer`,
  `silent-failure-hunter`, `comment-analyzer`) come from `pr-review-toolkit`, not from CLA. They
  hold Bash and Edit, so the skill that dispatches one saves the diff to a file, names its path,
  and puts the diff-review rule (no git commands, no edits) in the prompt.

One split shapes everything: **procedure is portable, facts are per-repo.**

- **Procedure** lives in the plugin (`skills/`, `agents/`, `hooks/`, `output-styles/`) and is the
  same in every repo that uses CLA.
- **Facts** live in the repo. `cla.io/project-facts.md` is the one home for every command, path,
  port, install step and env file a skill reads. The rest of the repo-root `cla.io/` tree holds
  decisions, feedback, the run ledger, the lessons log, the machine-read `*.local.md` files, and
  optional per-skill overlays (`cla.io/overlays/<skill>.md`) for a rule one skill needs in this
  repo only. Installing or updating the plugin never touches any of it.

## 2. Your first session

**In a repo that installed CLA** (section 10): start `claude` as usual. The plugin is already
active; there is no launcher to run.

**In this repo, developing CLA:** use the launcher at the repo root. It loads the plugin from the
working tree, so you run the code you are editing:

```bash
./cla                      # macOS / Linux / Git Bash
cla.cmd                    # native Windows
```

The launcher prints, then runs:

```
claude --plugin-dir <repo>/.claude/plugins/cla --permission-mode auto --model sonnet --effort medium
```

Anything after `./cla` goes to `claude`, so `./cla --model opus --effort high` overrides the
defaults when a session needs the top tier.

Two things to know before your first prompt:

- **`--permission-mode auto` skips per-action confirmations.** That is intended: the guard hooks
  are the safety layer.
- **The CLA output style applies automatically** (`force-for-plugin: true`): short sentences,
  bullets over paragraphs, answer first. Replies read terser than stock Claude Code.

Check it worked: type `/cla:` and the skill list should autocomplete.

## 3. Your first change: `lite-pr`

`lite-pr` is the light end-to-end path for a small, well-understood change. Reach for it first. It
implements, keeps docs and tests in step, opens a PR, then runs one automated review pass with one
fix round. It never merges.

```
/cla:lite-pr Rename the `retry_count` config key to `max_retries`, keeping a
deprecation fallback for the old name
```

The phases, in order:

1. **Explore** (optional): only for an open-ended ask. It hands off to `shape-decision` (section 4).
2. **Plan**: posted in the conversation so you can see it. It does not wait for approval.
3. **Implement** on a branch: code, `spec.md`, the instruction file (`CLAUDE.md` or `AGENTS.md`)
   and tests, kept in step.
4. **Test**: the one place the run stops. An unresolved failure halts it.
5. **Ship**: commit, push, open the PR.
6. **Review**: one automated pass over the opened PR, then one fix round. A fix made under high
   risk gets one more pass over its own diff. Ship writes a `Risk:` line in the PR body, and that
   line picks the reviewers and their models ("Review sizing by risk" in
   `_shared/references/model-routing.md`).

The PR opens *before* the review, and one fix round is the whole budget. Deeper, multi-round
review is `spec-to-pr`'s job.

Run with no arguments, it takes the change from the conversation (say, a `shape-decision` that just
finished) and asks only when there is nothing to go on. There is no escalation mid-run: if the
change turns out bigger than expected, stop and re-plan, split it, or move to section 5.

## 4. Shape first, build second

Two skills come before any build, for when you know something is wrong or wanted but not yet what
to do about it.

**`feedback` gets rough notes out of your head and grounded in the repo.**

```
/cla:feedback the retro aggregator double-counts reruns
```

Give it notes one at a time and say "done" to finish. For each note it reads the repo (which file,
a probable root cause, never a confirmed diagnosis) and writes a dated triage doc under
`cla.io/feedback/`. It captures; it does not debug.

**`shape-decision` walks one decision to a documented pick.**

```
/cla:shape-decision should hook config live in hooks.json or per-hook overlay files?
```

It walks the options one at a time with pros and cons, recommends one, and writes a decisions doc
under `cla.io/decisions/`. `multi-spec`, `multi-lite` and `multi-pr` all take that doc as input.

A typical small change: `shape-decision` → `lite-pr`, or straight to `lite-pr` when the shape is
already clear.

## 5. Spec-scale changes: `multi-spec` → `review-change` → `spec-to-pr`

When a change is too big for one prompt, CLA runs it through OpenSpec (the vendored `opsx:*`
skills) rather than skip the thinking. CLA orchestrates around OpenSpec; it does not replace it.
For open exploration first, use `opsx:explore`.

1. **`multi-spec`** turns a decisions doc into a batch of OpenSpec proposals (`proposal.md`,
   `tasks.md` and spec deltas; `design.md` only on a stock trigger), written and committed one
   change at a time. It stops at proposals: nothing is built yet. With no argument it takes the
   newest doc under `cla.io/decisions/`.

   ```
   /cla:multi-spec cla.io/decisions/hook-config-redesign.md
   ```

2. **`review-change`** reviews one proposal before any code exists: it checks its claims, confirms
   the symbols, files and references it names exist, sizes it, and sends parallel review agents
   when it is large.

   ```
   /cla:review-change add-hook-config-overlay
   ```

3. **`spec-to-pr`** drives one OpenSpec change to an opened PR: implement, keep docs and tests in
   step, apply review fixes, archive the change, open the PR. It always stops before merge.

   ```
   /cla:spec-to-pr add-hook-config-overlay
   ```

   It also takes a fresh description and creates the change first. With no argument it takes the
   change from the conversation (typically an `opsx:explore` that just finished); with nothing to go
   on and exactly one open change, it resumes that one. It asks only when there are none or several.

### Reading a change yourself: `annotate`

`review-change` checks a change against the repo's standards. `annotate` puts it in front of
*you*: it renders a Markdown file, or a whole OpenSpec change, as a page in a chrome-less browser
window, served on loopback. Select any passage and comment on it. Each comment is saved with its
passage, in a file the session reads back and works through.

```
/cla:annotate <change-id or openspec/changes/<change-id>>
/cla:annotate <path>.md
```

A change opens on an overview: the proposal's why, each promise with its coverage and any
**BREAKING** mark, the requirements each capability adds, modifies, removes or renames, and how many
tasks are done. Tabs hold the proposal, design, tasks and spec deltas, with each passage's
counterpart inlined beneath the block it answers (two lines until clicked). In a spec delta, a
REMOVED requirement is muted and struck through, and a MODIFIED one shows a word diff against the
main spec. An archived change shows "no base": archiving wrote its text into the main spec, so the
text it replaced is gone.

The coverage view lists claims nothing names. Read it as a reading aid, not a verdict: an uncovered
row means no task names that file, not that the work is missing.

`annotate` never writes to what you are reading; the page is served read-only, and a test pins that
across a full annotate-and-rebuild cycle. In a later session, say "read my annotations" to pick the
comments back up.

## 6. Batches: `multi-lite` and `multi-pr`

One decisions doc often yields several independent changes. The chainers run them
dependency-first, unattended:

- **`multi-lite`** pulls every `lite-pr`-sized candidate out of a decisions doc, orders them,
  confirms the plan with you once, then runs `lite-pr` on each.
- **`multi-pr`** does the same at spec scale: it runs `spec-to-pr` on each OpenSpec change in
  dependency order, and makes sure every Critical and Important review finding is fixed before it
  moves on.

```
/cla:multi-lite cla.io/decisions/hook-config-redesign.md
/cla:multi-pr change-a change-b        # or no args = auto-discover every open change
```

**The one place CLA merges.** The single-change skills stop at an opened PR. A chainer must land a
dependency before the changes that build on it. Both chainers merge the same way, from one shared
reference (`skills/_shared/references/chain-merge.md`), through the `ask-destructive-git` guard:

```
ALLOW_PR_MERGE=1 gh pr merge <#> --squash --delete-branch --match-head-commit <head>
```

The prefix drops *only* the PR-merge confirmation, for that one command; a force-push or
`reset --hard` still prompts. Before each merge the chainer checks the PR again: the full test gate
is green on the exact head being merged, the head has not moved since review, and GitHub reports no
conflicts or failing checks. A re-run after an interruption never merges commits pushed after
review; those PRs stay open for you. Nothing merges unless you chose to run a chainer.

`multi-lite` asks for its merge policy at the plan gate:

- **`merge-each-clean`** (recommended) merges every candidate whose review left no Critical or
  Important finding open. A 9-candidate run ends with open PRs only for the candidates that could
  not merge, each with its reason.
- **`merge-dependencies-only`** merges only what must land before a later candidate: one another
  candidate builds on, or one whose files change shared environment state (a migration, seed data,
  provisioning). The rest stay open for you. An autonomous run gets this policy unless it names the
  wider one.

`multi-pr` merges only a change a later change needs: one it depends on, or one that changed shared
environment state. Every other PR stays open for you. Some host runtimes refuse `gh pr merge`
whatever the allowlist says. Either chainer then stops merging for the rest of the run, and
`multi-pr` halts before the change that needed the merge.

## 7. Parallel and safe: worktrees

Git's HEAD belongs to the clone, not the session, so two sessions in one clone collide on one
branch. CLA's answer is worktrees, and there is one way in: **`/cla:new-worktree`**.

Run it before you start, or the moment you realise mid-session that the work wants its own copy.
It creates the worktree, moves you into it, installs dependencies and carries over gitignored env
files (repo facts a plain `git worktree add` cannot know). Run inside an existing worktree, it does
the setup half only. Deciding late costs nothing, which is why there is only one path; the release
history tells how a second launcher was retired.

`block-worktree-path-escape` stops a Write or Edit from leaving the worktree, a common slip when a
stale absolute path sneaks into a prompt.

## 8. The guardrails you'll meet

The hooks wire themselves from `hooks/hooks.json` when the plugin loads; there is no
`settings.json` step. Two dispatchers each run several leaf hooks in one Python process (6 on the
Bash/PowerShell matcher, 2 on Edit/Write), and `warn-wholesale-rewrite` runs on its own after a
Write: **9 leaf hooks**, in three severities.

| Severity | Hook | Fires on |
|---|---|---|
| **Block**: the call does not run | `block-cd-in-bash` | a `cd`, which persists across calls (the working directory is already the repo root; use absolute paths) |
| | `block-unsafe-recursive-delete` | `rm -rf` and its PowerShell equivalents |
| | `block-worktree-path-escape` | a Write or Edit outside the current worktree (section 7) |
| **Ask**: a permission prompt, since the action may be fine | `ask-destructive-git` | force-push, `reset --hard`, branch force-delete, PR merges, a `checkout`/`switch`/`restore`/`clean` that would discard uncommitted work, and a saving `git stash` during a merge, cherry-pick or revert |
| **Warn**: a caution, and the call runs | `warn-comment-dates` | a bare `YYYY-MM-DD` date added to a code comment in a `.py` or `.sh` file |
| | `warn-stacked-pr-merge` | a merge into a branch that open child PRs are based on (states the retarget-or-close rules and the squash hazard) |
| | `warn-stray-scratch-artifact` | scratch files left in the repo root |
| | `warn-heredoc-escape-mangling` | a heredoc body whose backslash escape the shell layers eat (`\n` arrives as a real newline) |
| | `warn-wholesale-rewrite` | a Write that replaces a tracked file with a much shorter one (it asks you to name what you dropped) |

`ask-destructive-git` matters more than it looks. The launcher runs `--permission-mode auto`, which
turns off the usual confirmations, so this hook is what brings one back. Section 6 covers its
`ALLOW_PR_MERGE` hatch.

**Direct pushes to `main` are stopped by a git hook, not by these.** `hooks/git/pre-push` sees the
refspec git has already resolved, so no spelling of the command gets past it, and it covers pushes
from a terminal or an IDE too. A plugin cannot write to `.git/hooks`, so install it once per clone:

```bash
cp .claude/plugins/cla/hooks/git/pre-push .git/hooks/pre-push && chmod +x .git/hooks/pre-push
```

Why not a PreToolUse hook, since the question recurs: it would have to parse a command string, and
every spelling it missed was a hole (`--all`, `--mirror`, `heads/main`, `git.exe`, a here-string, a
quoted remote). They were closed one at a time and the list never ended. The cost of the git hook is
the `cp` line above.

When a hook fires, read its message before working around it: each says why it fired and what to
do instead.

## 9. The learning loops and `cla.io/`

Every run leaves state in the repo-root `cla.io/` tree: decisions, feedback docs, the run ledger
(`retro/spec-to-pr-runs.jsonl`), lessons learned, and the repo's `project-facts.md`. Two `[loop]`
skills read it:

- **`codify-learnings`**: run it at the end of a session worth learning from. It reviews the whole
  session for failures, checks each against the rules earlier runs wrote, and proposes up to three
  fixes (tools and hooks before docs) to apply with one prompt. It logs the fixes and repeat
  offenses in `cla.io/lessons-learned/`. The live log stays under 6,000 words; its oldest entries
  move to `lessons-learned-archive.md` beside it, which the skill's search also reads.

  ```
  /cla:codify-learnings
  ```

- **`spec-to-pr-retro`**: run it now and then. It reviews recent `spec-to-pr` runs from the ledger
  and proposes edits to the orchestrator. `codify-learnings` needs no retro of its own, because it
  already escalates a rule that failed again.

A ledger earns its place by having a reader. `lib/log_run.py` accepts one, `spec-to-pr-runs`, which
`spec-to-pr-retro` reads. `cla-setup` lists the ledgers retired for having no reader and offers to
delete any a repo still holds.

Utilities for any phase:

- **`right-model`**: describe a task and get the cheapest model and effort that can plausibly do it
  well, then optionally start it. It leans cheap and escalates only on a concrete signal.
- **`diagnose`**: find a failure's cause instead of guessing at fixes. It builds a deterministic
  pass/fail loop, ranks falsifiable hypotheses before touching anything, and writes the regression
  test before the fix. Both Test phases hand off to it on one stated cause: spec-to-pr after two
  rounds, lite-pr after one fix and one retry.
- **`checkpoint`**: compact a long session into a resumable briefing in `cla.io/checkpoints/`.
- **`project-review`**: a CTO-level review of the whole repo: vision, structure, requirements,
  architecture, validation.
- **`save-permissions`**: save the tool permissions granted this session to
  `.claude/settings.local.json`, so the next session does not ask again.

## 10. Adopting CLA in another repo

CLA installs *into* a repo, scoped to that project, not globally. In the repo that will use it:

1. **Install the plugins CLA depends on.** CLA orchestrates other plugins, and `plugin.json` has no
   way to declare a dependency, so nothing installs them and nothing warns when one is missing. A
   phase that needs an absent plugin cannot run, which looks like CLA being broken. OpenSpec and
   `pr-review-toolkit` are required, `commit-commands` on the light path, `plugin-dev` in some
   cases. **Which skill needs which, and how hard:**
   [the plugin's own README](.claude/plugins/cla/README.md#install-these-first--cla-calls-out-to-them-and-cannot-substitute-for-them).
   The list lives only there, because that file is the one an installing repo receives, and copies
   of it drifted before.

2. **Install CLA from the marketplace.** You get a snapshot pinned to an exact release tag:

   ```bash
   claude plugin marketplace add crisradu75/logic-artisan
   claude plugin install cla@cris-logic-artisan --scope project
   ```

   Then run `claude plugin list` and check that `cla`'s status is not an error (such as "isn't
   installed").

   > **Windows:** run the install from the shell your sessions launch with: Git Bash, or a Claude
   > Code session's own Bash tool. PowerShell's `Set-Location` rewrites path casing to the on-disk
   > name, and Claude Code keys an install by that exact string. A session started from a shell
   > with different casing for the same directory then finds `cla` "enabled in project settings but
   > isn't installed" (`claude plugin list` shows "✘ failed to load"), with none of `cla`'s skills
   > or guard hooks active and nothing else saying so. If both spellings are in use, install from
   > each.

3. **Run `/cla:cla-setup`.** It creates whatever is missing of `cla.io/` (never overwriting what is
   there), seeds the OpenSpec authoring rules, and writes `.claude/rules/cla-economy.md`, the
   economy rules file the plugin owns and replaces whole on every run, so an agent outside any
   skill still reads the cost rules. Then it fills `cla.io/project-facts.md` from the repo's own
   manifests: workspace members, install/dev/build/test commands, ports, the affected-file map,
   test locations, env files. In a repo with `openspec/` it asks whether tests prove each
   requirement or each scenario, and offers a spec-map scaffold. It also lists retired ledgers and
   offers to delete them, and adds a `.gitignore` line so `multi-lite` and `multi-pr` run notes stay
   out of git. It is safe to re-run: apart from that line and the rules file, it changes an
   existing file only on your yes. Re-run it whenever a skill reports missing or stale facts.

4. **Install the push guard**, once per clone (section 8):

   ```bash
   cp <plugin>/hooks/git/pre-push .git/hooks/pre-push && chmod +x .git/hooks/pre-push
   ```

**Updating.** Run `claude plugin marketplace update cris-logic-artisan`, then
`claude plugin update cla@cris-logic-artisan`, then restart the session. `cla.io/` is untouched,
because it lives in the repo and not in the plugin directory.

Overlays are optional: add `cla.io/overlays/<skill>.md` only when one skill needs a rule specific
to this repo.

### Going further

**The checkers you can wire into your own gate.** The plugin ships no tests: the installed tree is
a read-only cache with no pytest gate over it. Its checks ship as stdlib-Python programs instead,
each taking an optional `--repo-root` and exiting `0` clean, `1` with the violations named, or `2`
when it could not run.

```bash
python3 <plugin>/skills/cla-setup/scripts/check_fact_paths.py
```

That one checks *your* repo: every repo-relative path named in `cla.io/project-facts.md` or an
overlay must still exist. `/cla:cla-setup` runs it once after it writes, and nothing else schedules
it, so **your repo owns when it runs.**

Its sibling, `<plugin>/skills/_shared/scripts/check_no_project_tokens.py`, scans a *plugin* tree
for leaked project words and developer paths, using your `cla.io/project-tokens.local.md` as the
word list. Which tree it scans decides whether it belongs in your gate. `--repo-root` locates the
word list; if that repo carries its own copy of the plugin at `.claude/plugins/cla/`, the scan
targets that copy (`_vendored_plugin_root`), and otherwise the tree the script itself lives in.
Against an ordinary **marketplace install** it scans the read-only cache, which is clean by
construction, so wiring it into your gate checks nothing about your repo. Against a **vendored
copy** it checks files your repo owns, and is worth running for the same reason the authoring
checklist runs it.

**Coming from a `0.x` release?** A gate that still wires the plugin's `conformance-checks/tests`
directory should drop that wiring: the directory has not shipped since `1.0.0`, so the gate either
fails on a missing path or passes while checking nothing. `check_fact_paths.py` replaces the half
of it that was about your repo.

**Fixes flow one way.** A skill improved while working in your repo goes back with
`/cla:report-upstream`, which files an issue against this repo, and returns in the next release.
There is no per-file sync; the old `update-cla` engine was deleted when the marketplace became the
only way to install.

## 11. Working on CLA itself (this repo)

Contributing to CLA rather than using it? The rules are in `CLAUDE.md`, which every session here
loads. This section is the reference behind them: what runs, where things live, and why each
script exists.

- **The gate is local; there is no CI, by design:**

  ```bash
  pytest plugin-tests -q -n auto --dist loadfile    # the whole suite
  openspec validate --specs --strict                # the live specs
  ```

  Both green is the only gate before a PR. Watch the skip count: a skipped guard has not run (one
  pre-push permission-bit test always skips on Windows), and the skip count is how you check a
  parallel run against a serial one. `-n auto --dist loadfile` needs `pytest-xdist`; without it,
  drop both flags. Use `--dist loadfile`, never plain `-n auto`, and when a mutation batch is run,
  run `mutate.py` serially. `CLAUDE.md` states the rules; section 12 has the measurements.

- **The tests live outside the plugin.** `.claude/plugins/cla/` is published whole and carries only
  what an installing repo can use, so every test, mutation batch, the mutation runner and the pytest
  config live in `plugin-tests/` at the repo root. Bare `pytest` over that tree is the gate: one
  scope, with the old scope names kept as areas (`conformance/`, `consistency/`, `launcher/`,
  `hooks/`, `lib/`, and one folder per skill with tests plus `_shared/` under `skills/`). Iterate on
  one with `pytest plugin-tests/tests/<area>`. Section 12 tells why twelve scopes became one.

- **Keep facts out of the plugin.** A conformance guard fails if a project-specific word or a
  developer's absolute path leaks into `skills/`, `agents/`, `hooks/`, `output-styles/` or `lib/`.
  It is a program (`skills/_shared/scripts/check_no_project_tokens.py`), not a test, so an
  installing repo can run it too. This repo's own `cla.io/` is its own, like any installing repo's,
  and never ships.

- **Shipped scripts are stdlib-only Python.** The spec-to-pr retro aggregator carries a copy of
  `lib/log_run.py`'s ledger-directory resolver, kept in step by hand;
  `plugin-tests/tests/consistency/test_ledger_dir_agrees.py` checks that the writer and the
  aggregator resolve the same directory when run from a subdirectory of the repo.

- **`CLAUDE.md` holds the rules; read it before a change.** The layout, the script table and the
  guard reference are below, and the evidence behind each rule is in section 12. Deferred work goes
  in GitHub issues. A root `TODO.md` is not a backlog: `/cla:spec-to-pr`'s Handoff writes leftover
  review suggestions there, in this repo and in every installing repo.

- **Platform-specific code runs only on the machine you are on.** Several hooks call real `git` and
  branch on Windows vs POSIX, and the directory-alias tests use a junction on Windows and a symlink
  elsewhere (the shared `make_dir_alias` fixture in `plugin-tests/tests/conftest.py`). A green local
  run is evidence about that machine only.

- **The Playwright suite is opt-in.** `plugin-tests/tests/skills/annotate/test_page_in_a_browser.py`
  drives the annotation page in a real headless Chromium. It calls `pytest.importorskip` at module
  level, so a checkout without Playwright sees one skip, and nothing in the shipped plugin depends
  on it. Enable it with:

  ```bash
  pip install playwright && playwright install chromium
  ```

### Layout

The published plugin; everything here ships to an installing repo:

```
.claude/plugins/cla/
  .claude-plugin/plugin.json   manifest
  plugin.json                  GitHub Copilot CLI (Agent Plugins 1.0) manifest, untested in a live Copilot CLI
  agents/                      doc-sweeper, fact-gatherer (mechanical helpers other skills delegate to)
  com.github.copilot/agents/   the same two agents for GitHub Copilot CLI, generated from agents/ (untested in a live Copilot CLI)
  hooks/                       guard hooks + hooks.json wiring
  lib/log_run.py               the one ledger writer, invoked as a program
  output-styles/               the project's writing convention (force-for-plugin: true)
  skills/_shared/references/   references two or more skills read as authority (no SKILL.md — not a skill);
                               `model-routing.md` holds the review-sizing table, `orchestration-economy.md` the chain cost rules, `economy-rules-file.md` the frame `/cla:cla-setup` renders into a repo's `.claude/rules/cla-economy.md`, `instruction-files.md` how skills read and write a repo's `CLAUDE.md` or `AGENTS.md`
  skills/<name>/
    SKILL.md                   the skill itself (portable procedure)
    references/                supporting docs (portable; overlays live in cla.io/overlays/); `lite-pr/references/`
                               holds `measured-by.md`, `mutation-gate.md` and `diagnose-escalation.md`, each read only when its trigger in `lite-pr/SKILL.md` fires, and `review-fix-weight.md`, a worked example
    scripts/                   deterministic helpers (stdlib Python)
```

**`lib/` is the odd one out**: not a skill (no `SKILL.md`) and not a guard hook. It holds
`log_run.py`, the one ledger writer, which `spec-to-pr` runs as a program.

The repo-root trees that do NOT ship:

```
plugin-tests/                  the repo's ONE pytest scope
  pyproject.toml               testpaths, norecursedirs, and the 10-entry pythonpath
  mutate.py                    mutation checker: break a fix, confirm a test fails, restore
  tests/<area>/                conformance, consistency, launcher, hooks, lib, skills/<name>
  mutants/<area>/              mutation batches, named after the area or skill they test — a sibling of tests/, never a child
  scripts/measure_load.py
  scripts/meter.py
  scripts/migrate_run_records.py
  scripts/sync_copilot_agents.py
.claude/skills/release/        repo-local skill, invoked as /release (not /cla:release)
  SKILL.md
  scripts/check_shipped_tree.py
  scripts/check_copilot_models.py
.claude/skills/openspec-*/     OpenSpec's generated skills (with .claude/commands/opsx/)
.claude-plugin/                marketplace.json — the Claude Code catalog
.github/plugin/                marketplace.json — the GitHub Copilot CLI catalog
```

`pyproject.toml` sets `testpaths = ["tests"]`, `norecursedirs` (pytest's default list plus
`mutants`), and a `pythonpath` that reaches into the plugin, because the scripts under test stay
shipped and only their tests moved. A guard's batch is found by name: `mutants/hooks/` for a hook,
`mutants/<skill>/` (no `skills/` level) for a skill's scripts. Sitting beside `tests/` keeps the
batches from being collected as tests. A batch is optional. `plugin-tests/tests/launcher/` tests
the repo-root `cla`/`cla.cmd` launchers, which live outside the plugin tree.

### The guards that police the fact/procedure split

Of the four portable guards, **two reach installing repos and two do not, and where they live is
the difference.** No project word in the plugin
(`skills/_shared/scripts/check_no_project_tokens.py`) and no dead path in
`cla.io/project-facts.md` or an overlay (`skills/cla-setup/scripts/check_fact_paths.py`) are skill
scripts inside the shipped tree, so an installing repo gets them and can run them as programs. No
hardcoded plugin path and no SKILL.md with broken frontmatter or a dead reference are pytest guards
in `plugin-tests/`. They police the plugin's own source and never reach an installing repo, on
purpose: that repo has no pytest gate over its plugin cache, so a guard filed as a test could not
run there.

`check_no_project_tokens.py` runs as a program and, in this repo, also as a subprocess of a
`plugin-tests/tests/conformance/` test. One scanner covers `SKILL.md`/`references/*.md` prose under
`skills/`; a second covers source files under **five** roots (`skills/`, `agents/`, `hooks/`,
`output-styles/` and `lib/`), because the marketplace ships the whole directory (`.md` there is
frontmatter-exempt the same way `SKILL.md`'s own `description:` is). The two scanner families reach
different files: the hardcoded-path one (`test_no_hardcoded_plugin_paths.py`) reaches strictly more
file types than the project-token one, so a file can be covered by one and not the other. **The
suffix lists are not written in any doc**: read `SCANNED_SUFFIXES`/`REQUIRED_SUFFIXES` in that guard
and `_iter_scanned_source_files` in the checker. Some shipped files are reached by no scanner on
purpose (the plugin's own `README.md` names this repo and the plugin path), and nothing tracks
which.

### Every script, and why it exists

A script earns its place only by doing something a command plus a sentence of prose cannot do
reliably. Scripts that failed that bar were deleted; these are the survivors. **If a script here
cannot be justified in one line, it is not a survivor.** (Guard hooks are in section 8.)

Shipped scripts are given relative to `.claude/plugins/cla/` without that prefix: a bare top-level
path (`lib/...`) for a script outside `skills/`, and a skill-relative path (`<skill>/scripts/...`,
no leading `skills/`) for a script that belongs to one.

| Script | Why prose can't do it |
|---|---|
| `plugin-tests/mutate.py` *(dev tree)* | Breaks a fix, confirms a test fails, restores byte-exactly — a judgement no reading of the test can substitute for. Opt-in: run only when the owner asks or a guard hook is rewritten (section 12, "Mutation testing is opt-in"). |
| `lib/log_run.py` | The one ledger writer: validates the record against its shape, enforces the 4 KiB atomic-append ceiling, refuses every ledger name but `spec-to-pr-runs.jsonl`. |
| `plugin-tests/scripts/measure_load.py` *(dev tree)* | Counts the words each skill puts in front of the model (session listing, `SKILL.md`, reachable references, curated per-run profiles) so a token-cutting change quotes a measured before/after; fails when a profile entry is no longer named directly by the file it says forces the read. |
| `plugin-tests/scripts/meter.py` *(dev tree)* | Totals the tokens a session transcript's `usage` fields record, split by model and counting main chat and subagents together, so a token-diet change quotes measured spend instead of word counts; one API message appears once per content block in a transcript, and a plain sum counts it several times. |
| `plugin-tests/scripts/migrate_run_records.py` *(dev tree)* | One-off rewrite of old-shape `spec-to-pr-runs.jsonl` records into the shape `log_run.py` enforces: every mapping comes from a shape found in a real ledger, a valid record is left untouched, and one that still fails is reported and left exactly as it was. |
| `plugin-tests/scripts/sync_copilot_agents.py` *(dev tree)* | Writes the Copilot CLI copy of each helper agent from its Claude Code agent: the body is copied unchanged and `tools` and `model` are mapped by documented tables and `color` is dropped, which is a rewrite of frontmatter that a sentence of prose would get wrong. The tests import it and fail when a committed copy differs. |
| `cla-setup/scripts/check_fact_paths.py` | Existence-checks every repo-relative path the facts file and overlays name, in the *consuming* repo — which has no pytest gate over the plugin cache, so a checker filed as a test is unreachable there. It skips a path `_is_machine_local` accepts (read the function for the rule). It also reports a path under a top-level directory that git history shows was renamed or removed, and skips one whose first part never was a top-level name here. A path with a placeholder (`{...}`, `<...>`) is never checked; a stale line whose path also ends a tracked path elsewhere gets a hint naming up to three (`_stale_hint`). |
| `cla-setup/scripts/seed_openspec_rules.py` | Seeds or compares the OpenSpec `rules:` block in the *consuming* repo's config. The block was an 8172-byte bash block in `SKILL.md`, and a Bash-tool command that long is cut off on Windows: in the Bash tool here, `echo "<padding>" | wc -c` of about 9.3 KB failed with `unexpected EOF while looking for matching quote` and of about 5.7 KB ran (issue #385), so the model could not paste a bigger block. The comparison (quoted and CRLF forms, artifact names, config left byte-identical) is also the part a model gets wrong when it improvises. The one place the rules text lives; a test pins it equal to this repo's own config. |
| `_shared/scripts/check_no_project_tokens.py` | Four scans in one run over the consuming repo's install (prose tokens, source tokens, absolute developer paths, readability); the readability check is what stops the other three passing vacuously. |
| `_shared/scripts/check_spec_proof.py` | Ties each requirement a branch adds or changes (or each scenario, when `cla.io/project-facts.md` opts in) to a test marker or `manual: <spec> / <heading>: <reason>` line, and flags markers naming nothing (a scenario marker is `scenario: <spec> / <scenario>`, or `scenario: <spec> / <requirement> / <scenario>`, which must also name the requirement the scenario sits under), repeated headings, an empty corpus and specs over the 500-character, 3-scenario and 8-requirement limits it reads from `rules.specs`, and notes (never fails on) a live spec whose Purpose is not a `**Serves:**` line plus one sentence. Once `cla.io/project-facts.md` declares a `## Spec map`, it also fails on a spec (live, or added by a change in progress, and not removed whole by one) no map file links and on a map link to a missing spec; with no declaration it prints nothing about a map. It needs the merge-base diff and a scan of every test file, which prose cannot do reliably and which a consuming repo (no pytest gate over the plugin) must run itself. |
| `spec-to-pr-retro/scripts/spec_to_pr_aggregate.py` | Deterministic counting over every repo's spec-to-pr ledger listed in `cla.io/fleet.local.md` (falling back to this repo's, and saying so), because any one repo's sample is thin enough to mislead; reports how often Revise's round 2 (which runs only after round 1 fixed a Critical, or an Important on a high-risk PR) still finds something, the evidence its default rests on; `--nudge` is the one line Handoff prints when recent runs keep exhausting a cap (Revise: with findings left open) or repeating a warn reason. |
| `new-worktree/scripts/manual_worktree.py` | Routes around the Windows path-casing refusal, and refuses to remove a worktree holding uncommitted work — where a model slip destroys work. |
| `.claude/skills/release/scripts/check_shipped_tree.py` *(repo-local)* | Enumerates the tracked plugin tree against a 16-pattern allowlist before a tag is cut. `git-subdir` has no exclusion field, and the obvious denylist was measured to miss 7 of 72 dev-only files — including the two runners and the release skill itself. |
| `.claude/skills/release/scripts/check_copilot_models.py` *(repo-local)* | Fetches GitHub's supported-models table for Copilot CLI and refuses the release when a `MODEL_MAP` ID is missing from it. A model GitHub renamed makes Copilot use the session model with no error, and nothing else reads the IDs against that list, so a sentence of prose in the skill would be skipped. It needs the network (exit 2 when the page cannot be read); its tests build a page with the table's layout. |
| `annotate/scripts/annotations_store.py` | The annotation corpus: append-only merge rule, tombstones, and a refusal to read past a conflict marker rather than fabricate a corpus from both sides. |
| `annotate/scripts/render_doc.py` | Markdown → an annotatable page whose every block carries a source line, plus the anchor check that says which annotations the last edit orphaned. |
| `annotate/scripts/render_html.py` | Instruments an author's own HTML in place — attributes spliced at source offsets, so stripping them returns the original bytes and the document under review stays the document under review. Refuses a file whose markup already uses those attributes, because that collision mis-anchors every annotation in the element and is invisible on the page. |
| `annotate/scripts/annotate_server.py` | Serves the page on loopback, validates each record before it reaches the file, and opens a chrome-less browser window. |
| `annotate/scripts/openspec_change.py` | Extracts a change's claims and the links between them, with thresholds measured over 355 real changes rather than reasoned about — the first cut left 83% of promises falsely uncovered. |
| `annotate/scripts/sweep_changes.py` | Runs the link detector over a corpus of real changes and reports the coverage split — the command behind every coverage threshold in `openspec_change.py`, and how a consuming repo re-measures before trusting the coverage tab. |
| `annotate/scripts/render_change.py` | Lays a change's files into one annotatable page, binding each claim to its block one-match-or-none and keeping injected counterparts outside the blocks whose offsets they would corrupt. |
| `multi-pr/scripts/check_cite_drift.py` | Finds where each `path:line` cite in a later chain change now points, by reading the cited text at the chain-start commit and searching the merged tree for it. Prose can say "the cite moved" but cannot say where to, or that the text now occurs twice. |
| `spec-to-pr/scripts/probe_state.py` | Resume detection across `openspec status`, `gh`, and `<base>..<branch>` ranges, with branch-resolution fallback. |
| `_shared/scripts/git_state.py` | One deterministic exit code for "an in-progress rebase/cherry-pick/merge exists", checked at every commit boundary across five skills. |
| `spec-to-pr/scripts/_git_common.py` | Repo root plus the `branch-prefix.local.md` overlay contract, for `probe_state.py`. |

### Adding a skill

Four contracts, each enforced by a test, so a miss fails the suite instead of shipping:

1. **`skills/<name>/SKILL.md` is the entrypoint, and the directory name is the command.** Its
   frontmatter needs a non-empty `name` and `description`, and `name` must equal the directory, or
   `/cla:<dir>` resolves to nothing. Pinned by `plugin-tests/tests/conformance/test_skill_lint.py`.
2. **The `description` is trigger metadata, not documentation.** Natural-language invocation
   matches against it; keep it under the length ceiling the same test enforces. Write it in the
   third person and name concrete trigger phrases.
3. **Every reference the body names must exist.** A bare `references/<file>` means *this skill's
   own* file; to cite another skill's, write the explicit
   `${CLAUDE_PLUGIN_ROOT}/skills/<owner>/references/<file>`. Both mistakes fail the same test.
4. **Project-specific facts never go in the body.** The skill reads them from
   `cla.io/project-facts.md`; a rule specific to one repo goes in `cla.io/overlays/<name>.md`, which
   the skill reads only if present. No skill may require an overlay, and nothing seeds one. The
   token guard fails the suite if a repo name leaks into the body.

Then add the skill to the plugin README's phase table and to the cheat sheet below. If its
frontmatter forbids model invocation, also add it to the one sentence naming those skills in
`CLAUDE.md` and in section 1. `plugin-tests/tests/consistency/test_doc_facts.py` fails if the phase
table misses the skill or any of those three copies disagrees with the frontmatter; nothing checks
the counts. A new skill's tests go in `plugin-tests/tests/skills/<name>/`, not beside the skill.

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

### Mutation testing is opt-in: the PR behind the rule

Decided by the owner on 2026-10-14. A mutation batch (`mutate.py` planting bugs and confirming a
test catches each) is no longer a required step anywhere. It runs only when the owner asks for it,
or when a guard hook under `.claude/plugins/cla/hooks/` is rewritten. The floor that stays
everywhere is breaking each review fix by hand once and confirming a test fails, then restoring it.
The rules about reading the killing test and running `mutate.py` serially, never beside a reading
agent, still apply whenever a batch is run. This supersedes the story below.

The evidence is PR #365 ("feat: spec-proof-checker", merged as `f929ac2`). The facts about that PR
below are from its body (`gh pr view 365`). Its body reports an earlier version of the batch run with 40 of 40
killed. The batch was then extended to 67 mutants, and that run was stopped by the owner before it
finished, on the decision that mutation testing is opt-in. The extended batch was never run to
completion against the final code (`plugin-tests/mutants/_shared/test_check_spec_proof.py`). The
review found its defects without it: round 1 found 5 and the single review over the whole diff
found 7 Important, and each fix was broken by hand once with a test failing. The evidence for
PR #320 in the superseded section below (from its own `gh pr view 320` figures) shows the same
shape: 2 test gaps against 16 review findings. The owner's stated reason (2026-10-14, not from
either PR body) was that each batch run is serial and blocks the agent for a long time, and that
the cost is "prohibitively expensive as a validation process with no clear benefit".

### Superseded: mutation runs only for guards and checkers: the PR behind the rule

*Superseded by "Mutation testing is opt-in" above; kept for its evidence.* Check 4 used to require a mutation batch for every review fix. It now requires one only in a guard
hook or a checker, once per PR, after the last fix. Every other fix needs one test that fails
without it, shown by breaking the fix by hand.

**The rule's wording before this change.** Check 4: "Break the fix and confirm a test fails:
`python3 plugin-tests/mutate.py <batch.py>`". The table row for a review fix: "that area, plus a
mutation batch over what the fix touches". The clean-run bullet: "Plant bugs in everything the fix
touches, not only the line it meant to fix."

The evidence is PR #320 ("annotate: make the change page readable for a human reviewer", merged
2026-10-09, merge commit `ca3b13a`). Every number below is from its body (`gh pr view 320`) or from
`git show 18bb37c`. Most of its code is the annotate change page, which renders documents. That
code is not a guard or a checker.

- **Review found the defects.** The first review round had 2 critical and 11 important findings.
  The second had 3 important findings. The fixes follow OpenSpec 1.14.1's own `dist/` code. The PR
  body credits no defect to a mutation run.
- **Mutation runs found 2 test gaps.** Each was a mutant that survived and got a new test: the
  "listed under New Capabilities" rule at the first push, and an "unknown" capability shown as
  "modified" in the first fix round.
- **One killed mutant protected a wrong behaviour.** The batch at the first push held "a MODIFIED
  header matches the main spec only with identical spacing", which replaced
  `" ".join(name.split())` with `return name`. A test killed it, and that run reported 26 of 26
  killed. The simpler form was the right one: OpenSpec's `normalizeRequirementName` counts inner
  spacing. Review found it as critical 1. This is the false reassurance "A killed mutant" below
  describes. `git show 18bb37c -- plugin-tests/mutants/annotate/test_openspec_change.py` shows the
  mutant replaced.
- **The batches were re-run in each round.** They ran serially, as `mutate.py` must. The runs
  covered 78 mutants at the first push, 111 after the first fix round and 135 after the second.

So outside the guards and checkers, each round paid for serial batch runs. Against 16 review
findings, the runs found 2 test gaps, and they reported one wrong test as a pass. A guard is
different: a broken one fails silently, and a planted bug is the cheap way to see it fail.

The stories behind check 4 and the clean-run, survivor and concurrent-run rules are all about
guards or checkers. That is why the rule keeps mutation runs for them. (The "A killed mutant" case
came from a consuming repo; its rule applies whenever a batch runs.) `1cf09da` and `0027bc7` ("A
clean mutation run") changed two guard hooks since deleted, warn-lint-on-edit and
block-direct-push-to-main. `lint_profile` (check 4) was in warn-lint-on-edit. `check_labels_agree` ("A survivor") is a consistency guard test, and
`check_script_drift` ("Concurrent mutation runs") was a guard, since deleted.

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

The never-move-a-tag rule, the no-local-marketplace rule, and why a release is a five-file edit
are each told under "Release and distribution history" below.

## Release and distribution history

Background a working session rarely needs, which is why it lives here rather than in `CLAUDE.md`.
The operative rules — the five-file bump, the preconditions, the never-move invariant — are in
`/release`'s own SKILL.md (repo-local at `.claude/skills/release/`, not shipped, because a
consuming repo has no catalog of its own to bump); this section is only the *why* behind them.

**How the catalog publishes.** `.claude-plugin/marketplace.json` at the repo root publishes one
plugin, `cla`, from `.claude/plugins/cla/` (`git-subdir` source, `url` + `path`, schema verified
against the live docs). It pins an **exact release tag**, not a moving major tag, which is why a
release is a deliberate five-file edit and why consumers pick a new release up only on
`/plugin marketplace update`. Consumers add the marketplace from the repo:

```bash
claude plugin marketplace add crisradu75/logic-artisan
claude plugin install cla@cris-logic-artisan --scope project
```

**The Copilot CLI catalog and manifest (2026-10-16, Copilot CLI only, untested in a live Copilot CLI).**
`.github/plugin/marketplace.json` publishes the same `cla` plugin to GitHub Copilot CLI, and
`.claude/plugins/cla/plugin.json` is the Agent Plugins 1.0 manifest beside the Claude one. They exist
because Copilot's docs list `github` and `url` sources and no `git-subdir`, so the Claude catalog's
entry is not documented as readable by it. Each carries the release version, which is why a release
is a five-file edit and why `plugin-tests/tests/skills/release/test_release_preconditions.py` checks
all five (a dry run of `claude plugin tag` with the Copilot pair left at an old version still passed,
so it sees only the Claude pair). The root manifest also needed a fifteenth allowlist pattern in
`check_shipped_tree.py`, or `/release` refused it. Claude Code did not take the plugin name from the
root manifest: a copy whose root manifest had a different name still loaded as `cla` from
`.claude-plugin/plugin.json`. The catalog always pins the current release tag, which carries the root manifest (it first
shipped in `cla--v2.1.1`; `cla--v2.1.0` lacks it), so the Copilot behaviour described here applies to every pin since. The root manifest's description does
not say the install is untested (2026-10-16, owner decision): it ships inside the release tag, which
is never moved, so the claim would outlive the first live test there. The README, this guide and the
spec carry it, and the docs test requires it beside the install command, within one heading section.
Nothing was run in Copilot: the
install line (Copilot CLI only, untested in a live Copilot CLI: `copilot plugin marketplace add
crisradu75/logic-artisan`, then `copilot plugin install cla@cris-logic-artisan`) comes from the docs.
The decisions are in `cla.io/decisions/copilot-cli-port-2026-10-16.md`; skills and hooks are
not ported yet (issue #302). **The guard hooks do not run in Copilot**: the owner decided on
2026-10-16 to wait for a live test, because the decisions file records (from a docs summary, untested
in a live Copilot CLI) that a Copilot `preToolUse` timeout always lets the command through, which would
weaken a guard meant to block when it fails.

**The Copilot CLI helper agents (2026-10-16, Copilot CLI only, untested in a live Copilot CLI).**
GitHub's plugin reference says an Agent Plugins 1.0 plugin keeps Copilot custom agents in
`com.github.copilot/agents/` and that the location cannot be configured, so Copilot cannot be pointed
at `agents/`. The Copilot copies there (five when this entry was written, two since the three reviewers were removed) are generated by `plugin-tests/scripts/sync_copilot_agents.py`,
and `test_copilot_agents_agree.py` fails when a copy's instructions, description or tools differ from
its Claude agent. The root manifest needs no entry for them (the docs list no fields for its
`com.github.copilot` extension), and `check_shipped_tree.py` took a sixteenth pattern. The mapping:
`tools: ["Read","Grep","Glob"]` becomes `["read","search"]` (the docs' primary aliases; the docs say the Claude
names are accepted too, untested), `model` becomes a Copilot model ID from the CLI reference's supported-models
table (the docs say an ID Copilot cannot honour falls back to the session model, so a stale ID loses the
choice and does not break the agent; `/release` therefore runs `check_copilot_models.py`, which refuses
when a `MODEL_MAP` ID is not in that table), and `color` is dropped. The script also reports a copy
whose Claude agent is gone, and `--write` deletes it. The instruction text still names the
tools `Read`, `Grep` and `Glob` and the `offset` and `limit` read arguments; the docs say Copilot accepts the
aliases (untested), but its own read tool may take different arguments. Claude Code did not load the copies: a
`claude -p` run listed the same five `cla:` agents as main (five at the time; the three reviewers were
removed later, see "CLA's own reviewer agents were removed" below).

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

**CLA's own reviewer agents were removed (2026-10-26).** `reviewer-agents` (2026-10-12) shipped
read-only copies of `code-reviewer`, `silent-failure-hunter` and `comment-analyzer`, so a reviewer
could not run `git checkout`. The owner then removed them and relies on the `pr-review-toolkit`
agents the plugin already requires: the copies claimed no token saving
(`openspec/changes/archive/2026-10-12-reviewer-agents/proposal.md`), a per-call `model` overrides an
agent file's model (`cla.io/decisions/reviewer-agents-live-check-2026-10-12.md`), and the one recorded
reviewer `git checkout` in this repo (`cla.io/lessons-learned/lessons-learned-archive.md`) was
handled by a brief rule. **The cost, accepted by the owner:** the toolkit reviewers hold Bash and
Edit, so the brief is the only safeguard, and nothing but the diff-review rule (`subagent-brief.md`
slot 3, carried verbatim by `lite-pr` and `revise.md`, pinned by `test_reviewer_dispatch.py`) stands
between a reviewer and a state-changing command. Two peer repos recorded such incidents:
market-distiller-mcp (a `code-reviewer` reverted 7 files) and claude-plugins (a `git checkout --`
on about 344 uncommitted lines). If one recurs here, the removed agents are in git history at
`.claude/plugins/cla/agents/` before this change.

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
| Set up CLA in a new repo | marketplace install → `/cla:cla-setup` |
| Pull newer CLA core into a repo | `claude plugin marketplace update cris-logic-artisan`, then `claude plugin update cla@cris-logic-artisan` |
| Report a defect in the portable core | `report-upstream` |
| Publish a new version of the plugin | `/release` (repo-local, not `/cla:release`) |
| Hand off a long session | `checkpoint` |
