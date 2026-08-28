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
on Edit/Write), plus `warn-wholesale-rewrite` and `log-commit-provenance` wired directly on PostToolUse: **10 leaf hooks**, in
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
  memory — interactively, then logs the run.

  ```
  /cla:codify-learnings
  ```

- **`codify-retro`** and **`spec-to-pr-retro`** — meta-loops. Run periodically, they review recent
  runs of `codify-learnings` / `spec-to-pr` from the ledgers and improve the loop itself.

The discipline throughout: log every run now, build the analyzer only once the ledger justifies it
(several `*-retro` skills are deliberately not built yet — see issue #174).

Two utilities worth knowing at any phase:

- **`right-model`** — describe a task, get the cheapest model + effort combo that can plausibly do
  it well, and optionally start it with those settings. Bias is downward; it escalates only on a
  concrete signal.
- **`save-permissions`** — persist tool permissions granted this session to
  `.claude/settings.local.json`, so the next session doesn't re-prompt.

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

Improvement flows one way, and deliberately so: a skill improved while working in a consuming repo
is reported back with `/cla:report-upstream` (which files an issue against this repo) and returns
in the next release. There is no per-asset sync — the legacy `update-cla` engine that provided one
was deleted when the marketplace became the sole distribution route.

## 11. Working on CLA itself (this repo)

Contributing to the harness rather than using it? The extra rules:

- **Run the whole verification story locally — there is no CI, by design:**

  ```bash
  pytest plugin-tests    # all pytest scopes (1) — the whole suite, one command
  node --test plugin-tests/node/mechanical-checks.test.mjs
  ```

  Both green is the only gate before a PR — and they ARE two commands: `pytest` does not reach the
  Node suite. Watch the skip count — a skipped guard has not run (one pre-push permission-bit test
  always skips on Windows).

- **The plugin's tests do not live in the plugin.** `.claude/plugins/cla/` is published whole to
  consuming repos and carries only assets a consumer can use, so every test, mutation batch, the
  mutation runner and the pytest config live in `plugin-tests/` at the repo root. Source-repo-only
  is now structural rather than declared: the dev tree exists only here, so there is nothing to mark
  and nothing to skip. The `SOURCE-REPO-ONLY.md` mechanism and its guard were deleted with the
  runner that read them.
- **Bare `pytest` over the dev tree IS the gate** — the inversion of the old rule, which forbade it.
  There is one scope now, not twelve, because the split rested on a single module-basename collision
  that no longer exists. Inside `plugin-tests/tests/` the old scope names survive as areas
  (`conformance/`, `consistency/`, `launcher/`, `hooks/`, `lib/`, and 6 skills with tests plus
  `_shared/` under `skills/`). Iterate on one with `pytest plugin-tests/tests/<area>`.

- **Keep facts out of the synced core.** A conformance guard fails if a project-specific token or an
  absolute developer path leaks into `skills/`, `agents/`, `hooks/`, `output-styles/` or `lib/`. It
  is a program (`skills/_shared/scripts/check_no_project_tokens.py`), not a test, precisely so it
  also runs in a consuming repo, which has no pytest gate over its plugin cache. Overlays in this
  repo stay neutral stubs — this is the source, not a consumer.

- **Scripts are stdlib-only Python** (no third-party deps beyond pytest itself), with one Node
  exception noted above. Same-named sibling scripts that must stay in lockstep are watched by
  `plugin-tests/scripts/check_script_drift.py`.

- **`CLAUDE.md` is the authoritative working-instructions file** — read it before a change; it
  covers the launchers, the scope layout, and the platform caveats in more depth. Deferred work
  lives in GitHub issues.

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

Then update the counts: the skill tables in `CLAUDE.md` and the plugin README, and the cheat sheet
below. `plugin-tests/tests/consistency/test_doc_facts.py` fails if you forget. A new skill's tests
go in `plugin-tests/tests/skills/<name>/`, not beside the skill.

## Release and distribution history

Background a working session rarely needs, which is why it lives here rather than in `CLAUDE.md`.
The operative rules — the three-file bump, the preconditions, the never-move invariant — are in
`/release`'s own SKILL.md (repo-local at `.claude/skills/release/`, not shipped, because a
consuming repo has no catalog of its own to bump); this section is only the *why* behind them.

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
| Stop re-approving the same permissions | `save-permissions` |
| Get a whole-repo health review | `project-review` |
| Capture this session's lessons | `codify-learnings` |
| Tune the loops themselves | `codify-retro`, `spec-to-pr-retro` |
| Set up CLA in a new repo | marketplace install → `cla-init` → `sync-context` |
| Pull newer CLA core into a repo | `/plugin marketplace update` |
| Report a defect in the portable core | `report-upstream` |
| Publish a new version of the plugin | `/release` (repo-local, not `/cla:release`) |
| Hand off a long session | `checkpoint` |
