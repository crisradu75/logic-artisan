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
| Know why a rule exists | §12: [the evidence](docs/evidence.md) and [the release history](docs/history.md), kept in full |
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
  warn on risky tool calls: a force-push, an `rm -rf` through a symlink, a `cd` that would persist across calls. You
  never invoke them.
- **Helper agents** (`doc-sweeper`, `fact-gatherer`) do the mechanical grep-and-verify work that
  the ship and review skills hand off. You rarely call them. The PR reviewers (`code-reviewer`,
  `silent-failure-hunter`, `comment-analyzer`) come from `pr-review-toolkit`, not from CLA. They
  hold Bash and Edit, so the skill that dispatches one saves the diff to a file, names its path,
  and puts the diff-review rule (no git commands, no edits) in the prompt.

One split shapes everything: **procedure is portable, facts are per-repo.**

- **Procedure** lives in the plugin (`skills/`, `agents/`, `hooks/`, `output-styles/`, `lib/`) and is the
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
the setup half only. Deciding late costs nothing, which is why there is only one path; [the release
history](docs/history.md) tells how a second launcher was retired.

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
| | `block-unsafe-recursive-delete` | a recursive, forced delete (`rm -rf`, `Remove-Item -Recurse -Force`) whose target is itself a symlink or junction, which would delete the real files behind it |
| | `block-worktree-path-escape` | a Write or Edit outside the current worktree (section 7) |
| **Ask**: a permission prompt, since the action may be fine | `ask-destructive-git` | force-push, `reset --hard`, branch force-delete, PR merges, a `checkout`/`switch`/`restore`/`clean` that would discard uncommitted work, and a saving `git stash` during a merge, cherry-pick or revert; a push that skips the `pre-push` guard (`--no-verify`, `core.hooksPath`, or `ALLOW_PUSH_TO_MAIN=1`) |
| **Warn**: a caution, and the call runs | `warn-comment-dates` | a bare `YYYY-MM-DD` date added to a code comment in a `.py` or `.sh` file |
| | `warn-stacked-pr-merge` | `gh pr merge --delete-branch` on a PR whose branch open child PRs are based on (states the retarget-first rule and the squash hazard) |
| | `warn-stray-scratch-artifact` | a `git add` or `git commit` while an untracked root file named like a mangled temp path (`AppData`, `LocalTemp`, `scratchpad`) is present |
| | `warn-heredoc-escape-mangling` | a heredoc body whose backslash escape the shell layers eat (`\n` arrives as a real newline) |
| | `warn-wholesale-rewrite` | a Write that replaces a tracked file with a much shorter one (it asks you to name what you dropped) |

`ask-destructive-git` matters more than it looks. The launcher runs `--permission-mode auto`, which
turns off the usual confirmations, so this hook is what brings one back. Section 6 covers its
`ALLOW_PR_MERGE` hatch.

**Direct pushes to `main` are stopped by a git hook, not by these.** `hooks/git/pre-push` sees the
refspec git has already resolved, so no way of naming the target branch gets past it, and it covers
pushes from a terminal or an IDE too. Two things skip it: git's own `--no-verify` flag, and the
`ALLOW_PUSH_TO_MAIN=1` override the hook keeps for a genuine emergency. From a session,
`ask-destructive-git` asks before either. It refuses the remote's own default branch as well as
`main` and `master`. A plugin cannot write to `.git/hooks`, so install it once per clone:

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
   skill still reads the cost rules. Then it proposes `cla.io/project-facts.md` from the repo's own
   manifests, and writes it on your yes: workspace members, install/dev/build/test commands, ports, the affected-file map,
   test locations, env files. In a repo with `openspec/` it asks whether tests prove each
   requirement or each scenario, and offers a spec-map scaffold. It also lists retired ledgers and
   offers to delete them, and adds a `.gitignore` line so `multi-lite` and `multi-pr` run notes stay
   out of git. It is safe to re-run: apart from that line and the rules file, it writes facts and
   changes an existing file only on your yes. Re-run it whenever a skill reports missing or stale facts.

4. **Install the push guard**, once per clone (section 8). Here and below, `<plugin>` is the
   installed plugin's directory, a version-keyed copy under `~/.claude/plugins/cache/`;
   `find ~/.claude/plugins/cache -path '*hooks/git/pre-push'` prints the hook's path in each installed version.

   ```bash
   cp <plugin>/hooks/git/pre-push .git/hooks/pre-push && chmod +x .git/hooks/pre-push
   ```

**Updating.** Run `claude plugin marketplace update cris-logic-artisan`, then
`claude plugin update cla@cris-logic-artisan`, then restart the session. `cla.io/` is untouched,
because it lives in the repo and not in the plugin directory.

Overlays are optional: add `cla.io/overlays/<skill>.md` only when one skill needs a rule specific
to this repo.

**On GitHub Copilot CLI** the install is experimental: Copilot CLI only, untested in a live Copilot
CLI. The skills and the two helper agents are offered to Copilot, but the
guard hooks do not run in Copilot. The [README](README.md#github-copilot-cli-experimental) has the
commands and what to expect; issue #302 tracks the port.

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
  run `mutate.py` serially. `CLAUDE.md` states the rules; [the evidence](docs/evidence.md#the-parallel-gate-measurements-and-the-cache-incident) has the measurements.

- **The tests live outside the plugin.** `.claude/plugins/cla/` is published whole and carries only
  what an installing repo can use, so every test, mutation batch, the mutation runner and the pytest
  config live in `plugin-tests/` at the repo root. Bare `pytest` over that tree is the gate: one
  scope, with the old scope names kept as areas (`conformance/`, `consistency/`, `launcher/`,
  `hooks/`, `lib/`, and one folder per skill with tests plus `_shared/` under `skills/`). Iterate on
  one with `pytest plugin-tests/tests/<area>`. [The evidence](docs/evidence.md#why-the-twelve-test-scopes-became-one) tells why twelve scopes became one.

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
  guard reference are below, and the evidence behind each rule is in [docs/evidence.md](docs/evidence.md). Deferred work goes
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
| `plugin-tests/mutate.py` *(dev tree)* | Breaks a fix, confirms a test fails, restores byte-exactly — a judgement no reading of the test can substitute for. Opt-in: run only when the owner asks or a guard hook is rewritten ([evidence: "Mutation testing is opt-in"](docs/evidence.md#mutation-testing-is-opt-in-the-pr-behind-the-rule)). |
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

`CLAUDE.md` states each rule once, in its compressed form. The measurement, incident or decision
behind each rule is kept in full, under a heading naming the rule, in
**[docs/evidence.md](docs/evidence.md)**. The background to how CLA is released and distributed
(the catalog pin, the never-moved tag, the retired sync engine and launcher, the Copilot CLI port)
is in **[docs/history.md](docs/history.md)**. Neither is needed to use CLA; read them before you
question or change a rule.

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
