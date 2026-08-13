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
  life: capture → decide → specify → build → review → learn. You invoke them by slash command or
  by describing what you want in natural language.
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

From the repo root:

```bash
./cla                      # macOS / Linux / Git Bash
cla.cmd                    # native Windows
```

The launcher prints, then runs:

```
claude --plugin-dir <repo>/.claude/plugins/cla --permission-mode auto --model sonnet --effort medium
```

Everything after `./cla` is forwarded to `claude`, so `./cla --model opus` overrides the default.

Three things to know before your first prompt:

- **In THIS repo, load the plugin live from the working tree** (`--plugin-dir`), so you are running
  the harness you are editing rather than a cached snapshot of a release. A consuming repo does the
  opposite and runs the marketplace install; that works because repo-local state lives in `cla.io/`,
  outside the plugin directory. Without either, the skills are inert files and no guard runs.
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
   (`proposal.md`/`design.md`/`tasks.md`/`specs/` each), authored and committed one change at a
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

**The one place CLA merges.** The single-change skills stop at an opened PR, but a chainer must
merge a dependency PR before its dependents can build on it. That merge goes through the
`ask-destructive-git` guard: it runs `ALLOW_PR_MERGE=1 gh pr merge <#> --squash --delete-branch` —
the prefix drops *only* the PR-merge confirmation, for that one command, and the source branch is
deleted on merge. Force-push and `reset --hard` still prompt. No PR is ever merged without you
having chosen to run a chainer.

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
dispatchers each run several leaf hooks in one Python process (5 on the Bash/PowerShell matcher, 2
on Edit/Write), plus `warn-wholesale-rewrite` wired directly on PostToolUse: **8 leaf hooks**, in
three severities.

- **Blocks** stop the tool call:
  `block-cd-in-bash` (the working dir is already repo root, and a `cd` persists across calls — use
  absolute paths), `block-unsafe-recursive-delete` (`rm -rf` and its PowerShell equivalents),
  `block-worktree-path-escape` (section 7).
- **Asks** escalate to a permission prompt, because the action may be legitimate:
  `ask-destructive-git` (force-push, `reset --hard`, PR merges — see section 6 for the
  `ALLOW_PR_MERGE` hatch). This matters more than it looks: the launcher runs
  `--permission-mode auto`, which suppresses the usual confirmations, so this hook is what
  restores one.
- **Warns** surface a caution and let the call through: `warn-comment-dates`,
  `warn-stacked-pr-merge` (a merge that could auto-close an open child PR),
  `warn-stray-scratch-artifact` (scratch files left in the repo root), and
  `warn-wholesale-rewrite` (a `Write` replacing a tracked file with a materially shorter one — it
  asks you to name what you dropped, since a `Write` keeps only what you carried across).

**Direct pushes to `main` are not guarded by any of these.** That protection is a git `pre-push`
hook at `hooks/git/pre-push`, which git hands the already-resolved refspec, so no command spelling
can evade it and it covers pushes from a terminal or IDE too. A plugin cannot write to
`.git/hooks`, so every clone installs it once:

```bash
cp .claude/plugins/cla/hooks/git/pre-push .git/hooks/pre-push && chmod +x .git/hooks/pre-push
```

When a hook fires, read its message before working around it — each one states why and what to do
instead. The guards encode the harness's conventions; routing around them defeats the point.

## 9. The learning loops and `cla.io/`

Every run leaves state behind in the repo-root `cla.io/` tree — decisions, feedback docs, retro
ledgers (`retro/*-runs.jsonl`), lessons learned, and (in a consuming repo) the consolidated
`project-facts.md`. That state feeds the `[loop]` skills:

- **`codify-learnings`** — run it at the end of a session worth learning from. It reviews the
  conversation for reusable lessons and proposes concrete edits — to docs, skills, hooks, or
  memory — interactively, then logs the run.

  ```
  /cla:codify-learnings
  ```

- **`codify-retro`** and **`spec-to-pr-retro`** — meta-loops. Run periodically, they review recent
  runs of `codify-learnings` / `spec-to-pr` from the ledgers and improve the loop itself.

The discipline throughout: log every run now, build the analyzer only once the ledger justifies it
(several `*-retro` skills are deliberately not built yet — see `TODO.md`).

Two utilities worth knowing at any phase:

- **`right-model`** — describe a task, get the cheapest model + effort combo that can plausibly do
  it well, and optionally start it with those settings. Bias is downward; it escalates only on a
  concrete signal.
- **`save-permissions`** — persist tool permissions granted this session to
  `.claude/settings.local.json`, so the next session doesn't re-prompt.

## 10. Adopting CLA in another repo

CLA is installed *into* a repo, scoped to that project, not installed globally. Three steps, in the
destination repo:

1. **Install from the marketplace** — the plugin arrives as a versioned snapshot pinned to an exact
   release tag:

   ```bash
   claude plugin marketplace add crisradu75/logic-artisan
   claude plugin install cla@cris-logic-artisan --scope project
   ```

2. **`/cla:cla-init`** — scaffold the `cla.io/` tree and empty overlay stubs. Idempotent and
   never-clobber: safe to re-run on a partially-scaffolded repo.
3. **`/cla:sync-context`** — populate `cla.io/project-facts.md` with the repo's facts: workspace
   members, dev/build/test commands, ports, affected-file map, test locations, env files. This is
   the single physical copy of every fact the skills share.

Then fill in the per-skill `cla.io/overlays/<skill>.md` overlays as the skills prompt for
facts. Pick up newer releases with `/plugin marketplace update`; your overlays and `cla.io/` are
untouched by an install, because they live in the repo rather than the plugin directory.

Improvement flows one way, and deliberately so: a skill improved while working in a consuming repo
is reported back with `/cla:report-upstream` (which files an issue against this repo) and returns
in the next release. There is no per-asset sync — the legacy `update-cla` engine that provided one
was deleted when the marketplace became the sole distribution route.

## 11. Working on CLA itself (this repo)

Contributing to the harness rather than using it? The extra rules:

- **Run the whole verification story locally — there is no CI, by design:**

  ```bash
  python3 .claude/plugins/cla/run_tests.py    # all pytest scopes (10), aggregated
  node --test .claude/plugins/cla/skills/project-review/scripts/mechanical-checks.test.mjs
  ```

  Both green is the only gate before a PR. Watch the skip count in the summary — a skipped guard
  has not run (one pre-push permission-bit test always skips on Windows).

- **Never run bare `pytest` from the repo or plugin root.** Each scope (4 skills with tests, plus
  `skills/_shared/`, `lib/`, `hooks/`, `conformance-checks/`, `consistency-checks/`,
  `launcher-checks/`) is isolated on purpose — several ship
  same-named helper modules. Iterate on one scope with
  `pytest .claude/plugins/cla/skills/<name>/tests`.

- **Keep facts out of the synced core.** Pytest conformance guards fail the suite if a
  project-specific token or an absolute developer path leaks into `skills/`, `agents/`, `hooks/`,
  or `output-styles/`. Overlays in this repo stay neutral stubs — this is the source, not a
  consumer.

- **Scripts are stdlib-only Python** (no third-party deps beyond pytest itself), with one Node
  exception noted above. Same-named sibling scripts that must stay in lockstep are watched by
  `consistency-checks/`.

- **`CLAUDE.md` is the authoritative working-instructions file** — read it before a change; it
  covers the launchers, the scope layout, and the platform caveats in more depth. Deferred work
  lives in `TODO.md`.

## Release and distribution history

Background a working session rarely needs, kept out of `CLAUDE.md` so that file stays operative.

**A local-directory marketplace is a development convenience, never a distribution route.** It was
used once, to exercise the install before the catalog change was pushed, and it carries a trap worth
naming: the catalog is then read from a working tree, so a locally-bumped `ref` advertises a tag that
may never have been pushed — the install fails with nothing visibly wrong in the manifest. Sourcing
the catalog from GitHub keeps catalog and tag moving together through one push.

For developing the harness itself, use `--plugin-dir` (below) rather than any marketplace: it is the
only mode that reads this working tree live. Every source type — including a local path — is copied
into the versioned cache at `~/.claude/plugins/cache`, so an install is a snapshot, not a link.

Cut the tag with **`claude plugin tag`**, which uses the shape `<name>--v<version>` and refuses
unless `plugin.json` and the marketplace entry already agree.

**Current release: `cla--v0.9.3`.** `0.9.x` is the validation line; it becomes `1.0.0` once a real
task has been run end-to-end through the plugin in a consuming repo (the propagation decision's own
Q7 gate — installing and resolving paths is verified, running a task through it is not).

**A published tag is never moved.** `0.9.0` was cut, a consumer installed it, and the very next fix
therefore became `0.9.1` rather than a re-tag — moving it would have changed what that consumer had
already fetched. Cut the tag only from `main`, and only after the work is reviewed.

The marketplace install is the only distribution mechanism. The legacy `update-cla` file-sync
engine was deleted once it was superseded; a consuming repo still carrying a `.cla-sync-lock.json`
can delete it, as nothing reads it any more.

**Launching a session in THIS repo:** `claude --plugin-dir` loads the plugin live, in
place, from this working tree — required here because the skills/hooks read and write repo-local
state under `cla.io/` and, while developing the harness, you want the working tree
rather than a cached copy of a release. Use the
`cla` (POSIX) / `cla.cmd` (Windows) launcher at the repo root instead of typing `claude` directly —
it resolves its own absolute path, so the flag it prints/runs is `--plugin-dir <repo>/.claude/plugins/cla`
regardless of your cwd:

```bash
./cla   # claude --plugin-dir <repo>/.claude/plugins/cla --permission-mode auto --model sonnet --effort medium
```

Without it, the skills/hooks are just inert files on disk — no `/cla:*` commands, no guard hooks.
**Note:** `--permission-mode auto` bypasses Claude Code's normal per-action confirmation prompts —
intentional for this harness, but worth knowing before you run it.

**Starting work in a worktree.** Use `/cla:new-worktree` at any point in a session — before
starting, or once you realise mid-flight that the work wants isolation. There is no longer a
penalty for deciding late.

There used to be a second launcher, `claw`, whose only job was to create the worktree *before*
Claude started. It existed to dodge `guard-worktree-isolation.py`, which wrote a presence
heartbeat at SessionStart for any session in the primary clone and could block a second session
from committing for an hour. That hook was deleted (0 recorded blocks across 127 session
transcripts), so the workaround went with it.

## Cheat sheet: "I want to…" → which skill

| I want to… | Reach for |
|---|---|
| Ship a small, clear change | `lite-pr` |
| Dump rough observations somewhere useful | `feedback` |
| Decide between approaches | `shape-decision` |
| Turn a decision into spec proposals | `multi-spec` |
| Sanity-check a proposal before building | `review-change` |
| Drive one spec'd change to a PR | `spec-to-pr` |
| Run a batch of small changes unattended | `multi-lite` |
| Run a batch of spec'd changes unattended | `multi-pr` |
| Work in parallel without collisions | `/cla:new-worktree`, at any point in a session |
| Pick the cheapest adequate model for a task | `right-model` |
| Stop re-approving the same permissions | `save-permissions` |
| Get a whole-repo health review | `project-review` |
| Capture this session's lessons | `codify-learnings` |
| Tune the loops themselves | `codify-retro`, `spec-to-pr-retro` |
| Set up CLA in a new repo | marketplace install → `cla-init` → `sync-context` |
| Pull newer CLA core into a repo | `/plugin marketplace update` |
| Report a defect in the portable core | `report-upstream` |
