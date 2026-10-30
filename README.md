# CLA — Cris Logic Artisan

**A Claude Code plugin that takes a change from idea to a reviewed pull request, with guardrails
on, and learns from each run.**

CLA holds no product code. It is the *process* layer: skills that run the workflow, guard hooks
that stop risky commands, and helper agents that do the mechanical checking. You install it into a
repo; the repo keeps its own facts.

```
/cla:lite-pr Rename the `retry_count` config key to `max_retries`, keeping a fallback for the old name
```

That one line plans the change, implements it on a branch, keeps docs and tests in step, runs the
tests, opens the PR, then reviews it and fixes what the review found. It never merges.

## Why CLA

- **Right-sized process.** A small change goes straight to `lite-pr`. A big one goes through an
  OpenSpec proposal, a pre-build review and `spec-to-pr`. Batches of either run unattended.
- **Review built in.** Every PR gets an automated review pass, sized by the risk the change
  declares.
- **Guardrails always on.** Nine hooks block, ask about or warn on risky tool calls: a force-push,
  an `rm -rf`, a `git stash` mid-merge, a file rewritten shorter.
- **Portable procedure, local facts.** The plugin carries only steps that work in any repo. Each
  repo's commands, paths and ports live in its own `cla.io/project-facts.md`.
- **It learns.** `codify-learnings` turns a session's failures into fixes, and `spec-to-pr-retro`
  tunes the orchestrator from its run ledger.

## The workflow at a glance

```
idea ─► feedback / shape-decision ─┬─► lite-pr ─────────────────────────────► PR   small change
                                   └─► multi-spec ─► review-change ─► spec-to-pr ─► PR   spec-scale
        batches: multi-lite (small) · multi-pr (spec-scale)
        after a session: codify-learnings · periodically: spec-to-pr-retro
```

Every skill runs as `/cla:<name>`. The [developer guide](DEVELOPER-GUIDE.md) walks the ladder one
step at a time; its [cheat sheet](DEVELOPER-GUIDE.md#cheat-sheet-i-want-to--which-skill) maps
"I want to…" to a skill.

## Quick start (Claude Code)

1. **Install CLA's dependencies.** CLA orchestrates other plugins and cannot declare them, so
   nothing installs them and nothing warns when one is missing. OpenSpec and `pr-review-toolkit`
   are required; `commit-commands` and `plugin-dev` are needed by some paths. The list, with which
   skill needs which, is in
   [the plugin README](.claude/plugins/cla/README.md#install-these-first--cla-calls-out-to-them-and-cannot-substitute-for-them).
2. **Install CLA into the repo:**

   ```bash
   claude plugin marketplace add crisradu75/logic-artisan
   ```

   ```bash
   claude plugin install cla@cris-logic-artisan --scope project
   ```

   Then run `claude plugin list` and check that `cla` shows no error.
3. **Set the repo up:** run `/cla:cla-setup` in a session. It creates `cla.io/` and fills in the
   repo's facts.
4. **Install the push guard**, once per clone. A plugin cannot write to `.git/hooks`. The command is
   in [Adopting CLA in another repo](DEVELOPER-GUIDE.md#10-adopting-cla-in-another-repo).

<details>
<summary><b>Windows:</b> install from the shell your sessions launch with</summary>

Use Git Bash, or a Claude Code session's own Bash tool. PowerShell's `Set-Location` rewrites path
casing to the on-disk name, and Claude Code keys an install by that exact string. A session started
from a shell with different casing for the same directory then finds `cla` "enabled in project
settings but isn't installed" (`claude plugin list` shows "✘ failed to load"), with no skills or
guard hooks active and nothing else saying so. If both spellings are in use, install from each.

</details>

**Updating:** `claude plugin marketplace update cris-logic-artisan`, then
`claude plugin update cla@cris-logic-artisan`, then restart the session. An update never touches
`cla.io/`, which lives in the repo, not in the plugin.

## GitHub Copilot CLI (experimental)

**Copilot CLI only**: nothing here targets the Copilot app or the cloud agent. These two lines come
from GitHub's documentation and **have never been run: the install is untested in a live Copilot
CLI**, so expect it to need fixes.

```bash
copilot plugin marketplace add crisradu75/logic-artisan
copilot plugin install cla@cris-logic-artisan
```

What to expect, per GitHub's docs and not from a run:

- Copilot reads `.github/plugin/marketplace.json` and the Agent Plugins 1.0 `plugin.json` at the
  plugin root, which takes precedence over `.claude-plugin/plugin.json`. The catalog pins the
  current release tag, and every tag since `cla--v2.1.1` carries that manifest, so Copilot should
  treat CLA as a 1.0 plugin.
- A 1.0 plugin offers Copilot its `skills/` directory. Agents load only from
  `com.github.copilot/agents/`, where CLA ships its two helper agents, generated from the Claude
  Code ones; they are also untested in a live Copilot CLI.
- **CLA's guard hooks do not run in Copilot.** They stay Claude-only until someone checks them in a
  live Copilot CLI (decided 2026-10-16), because GitHub's hooks reference says a Copilot
  `preToolUse` timeout lets the command through.
- Skill text that names Claude Code tools (`AskUserQuestion`, `Agent`, `${CLAUDE_PLUGIN_ROOT}`) is
  not ported, and whether skills answer to `/cla:<name>` is unknown. Tracked in issue #302.

The Claude Code install above is unchanged by any of this.

## Documentation

| Read | When you want |
|---|---|
| [DEVELOPER-GUIDE.md](DEVELOPER-GUIDE.md) | To learn CLA step by step: first session, first PR, the full ladder, worktrees, guardrails, adopting it in a repo |
| [The plugin README](.claude/plugins/cla/README.md) | Every skill by life-cycle phase, the guardrails, and the dependency list (the file an installing repo receives) |
| [CLAUDE.md](CLAUDE.md) | The rules for working in this repo (Claude Code reads it too) |

## Working on CLA itself

Here you run the plugin from the working tree, not from the marketplace, so a session uses the
code you are editing:

```bash
./cla           # claude --plugin-dir <repo>/.claude/plugins/cla --permission-mode auto --model sonnet --effort medium
```

Use `cla.cmd` on native Windows. `--permission-mode auto` skips confirmation prompts, so the guard
hooks are the safety layer. Without the launcher the skills and hooks are inert files: no
`/cla:*` commands, no guards. Run `/cla:new-worktree` whenever work needs its own copy of the repo.

**The gate.** There is no CI, by design. These two commands, run locally, are the whole check
before a merge:

```bash
pytest plugin-tests -q -n auto --dist loadfile
```

```bash
openspec validate --specs --strict
```

`-n auto --dist loadfile` needs `pytest-xdist`; without it, drop both flags. Plain `-n auto` is a
trap; CLAUDE.md, "The parallel gate", says why. Run one area with
`pytest plugin-tests/tests/<area>`: `conformance`, `consistency`, `launcher`, `hooks`, `lib` or
`skills/<name>`.

**What ships.** Only `.claude/plugins/cla/` is published. The tests live outside it, in
`plugin-tests/`, because an installing repo receives the whole plugin directory and can use only
what is in it.

```
cla (+ .cmd twin)              session launcher for THIS repo (loads the plugin from the tree)
.claude-plugin/                marketplace.json — the Claude Code catalog
.github/plugin/                marketplace.json — the GitHub Copilot CLI catalog
cla.io/                        this repo's own per-repo state (facts, decisions, feedback, retro ledgers)
openspec/                      OpenSpec config + specs for this repo's own changes
plugin-tests/                  the plugin's tests — one pytest scope, NOT published
.claude/skills/release/        repo-local skill invoked as /release — NOT published
.claude/plugins/cla/           everything below here IS published, and nothing else is
  .claude-plugin/plugin.json   manifest
  README.md                    the harness's scope + capabilities, by life-cycle phase
  skills/                      the workflow skills (spec-to-pr, lite-pr, multi-*, reviews, retro loops, …)
  skills/_shared/              references + scripts that several skills share (not a skill)
  agents/                      helper agents (doc-sweeper, fact-gatherer)
  hooks/                       always-on guard hooks (blocks, asks, warns) + dispatchers
  lib/log_run.py               writes the one run ledger (spec-to-pr-runs.jsonl), invoked as a program
  output-styles/               the project's writing convention (force-for-plugin: true)
```

**Facts stay out of the plugin.** This repo's own `cla.io/` is its own, like any installing repo's,
and never ships. `skills/_shared/scripts/check_no_project_tokens.py` fails if a project-specific
word or a developer's absolute path leaks into the plugin. It is a program, not a test, so an
installing repo can run it too.

The full contributor reference (layout, every script and why it exists, adding a skill) is
[DEVELOPER-GUIDE §11](DEVELOPER-GUIDE.md#11-working-on-cla-itself-this-repo).

---

Proprietary — see `.claude/plugins/cla/.claude-plugin/plugin.json`.
