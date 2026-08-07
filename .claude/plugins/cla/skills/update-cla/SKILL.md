---
name: update-cla
description: "Update this repo's cla plugin (.claude/plugins/cla/) from a canonical cla source repo — pulls newer core skills/agents/guard-hooks/output-styles, adapting to local context and PRESERVING this repo's own overlay (project-context.md plus any *.local.md files), never overwritten. The cross-repo update mechanism for the --plugin-dir-loaded harness. Discover → adapt → apply: conversation Claude does the LLM reasoning between phases, the script does only deterministic file/git work, with per-asset failure isolation and no auto-merge. Triggers on /cla:update-cla or phrasings like 'update the cla plugin from <repo>', 'pull newer cla into this repo', 'sync cla from <source>'."
argument-hint: "<source-repo> [asset]"
# Rewrites the plugin's own skills/agents/hooks/output-styles from another
# repo, so it must never self-trigger on a description match — only an
# explicit `/cla:update-cla <source>` starts it. Safe to set: nothing invokes
# this skill programmatically. Also keeps this long description out of the
# always-loaded skill listing until the command is typed.
disable-model-invocation: true
---

# update-cla

Pull-from-destination cross-repo update of this repo's **cla plugin** (`.claude/plugins/cla/`). Run **from the local repo** that wants updates, pointing at the **source repo** to pull newer core `cla` from. The skill is self-contained and stdlib-only, and lives inside the plugin it maintains (loaded via `--plugin-dir`). It syncs the plugin's core (skills / agents / guard-hooks / output-styles) and **never** touches this repo's project overlay (the fixed `project-context.md` filename plus any `*.local.md` files — see rule 5 below).

## Non-negotiable rules

These rules govern every adapted file. Read them first; they take precedence over any prose elsewhere in this skill.

**1. Preserve local strengths.** If the local version has content the source lacks — a workflow step source doesn't cover, a local-specific reference, a refinement the local author made, a workaround for a local quirk — **keep it**. Default merge stance is **additive, not overwrite**. Only drop local content when the source explicitly supersedes it (e.g., source renames a section that replaces the local one's purpose entirely, or source deliberately removes a feature the local version still has by accident). When in doubt, keep the local content and call it out in the per-file `change_summary`.

**2. Adapt for local context.** Swap plugin names, paths, examples, and terminology to match the destination. Preserve local heading style and conventions where they diverge from the source cosmetically (e.g., source's "## Steps" becomes "## Workflow" if that's the local repo's pattern). Preserve frontmatter fields the source lacks; adopt source frontmatter improvements only when they don't drop local fields. **Post-`cla-skill-context-extraction`, most project specifics live behind each skill's neutral `references/project-context.md` overlay, not scattered through the synced body** — since that overlay is itself sync-excluded (rule 5), the per-file adaptation surface this rule has to reason about on any given sync is much smaller than it was when facts and procedure were interleaved in one file.

**3. Source may be a re-specialized sibling fork, not an upstream.** When the local file is a *localized fork* of the source (both descend from a common asset but each was re-specialized to its own repo), the source is NOT a newer baseline to adopt — most of its diff is repo-specific swaps that would REVERSE the local adaptations. Detect this shape: the diff is dominated by convention swaps (branch prefixes, directory scopes, plugin names, permission-pattern style) that undo local choices, and/or source *deletes* content that is a deliberate local strength. When you see it, treat source as a **menu of portable improvements to cherry-pick** — take only genuinely new general-purpose content (a real bug fix, a new section covering a case local lacks) and **re-adapt it to local conventions** before writing; keep everything else local. Overwriting is the failure mode here, not the goal. **Post-extraction, this fork-reversal risk is largely confined to each skill's `references/project-context.md` overlay rather than spread through every `SKILL.md`/reference file** — a synced body that's now mostly portable procedure has far fewer spots where a source diff could plausibly reverse a local re-specialization.

**4. Verify every referenced tool/skill NAME exists in the destination, not just file paths.** A source file may reference a tool (in `allowed-tools`, in prose instructions) that's real in the source environment but doesn't exist here — checking that a *path* like `.claude/plugins/cla/skills/foo/bar.py` exists is not the same check. Before writing, run `ToolSearch` on every tool name the adapted content will reference (frontmatter `allowed-tools` and inline prose alike); drop or replace anything that doesn't resolve.

**5. Never overwrite the local project overlay.** A file whose leaf name is exactly `project-context.md`, or that ends with `.local.md`, is this repo's own project-specific overlay (repo-tuned review checks, project-specific reference content). `discover.py` already excludes them from the sync candidates, so they never appear in `divergences.json` — do NOT hand-add them to `adaptations.json` either. The overlay is local truth; the source's version, if any, is irrelevant.

## Why pull, not push

A prior push-based design (one source fans out to N destinations) forced the source-side Claude to adapt blind, sampling each target through thin slices (a `CLAUDE.md` snippet, a file listing) — the result was mechanical copies. Pulling instead puts the adapting Claude **inside the destination repo**, with full native context (local `CLAUDE.md`, plugin manifests, existing skills/conventions) — exactly the ingredient push-based sync was missing.

## Deterministic vs LLM

The skill is a **hybrid** — deterministic file/git work in the script, LLM reasoning in conversation:

- **Deterministic (script):** source-repo resolution, content hashing, source-vs-local divergence detection, state-file I/O, branch + commit + push + PR (in `pr` mode), worktree writes (in `worktree` mode).
- **LLM (you, in conversation):** per-asset adaptation — read the source version, the local existing version (if any), and the local repo's context; produce a final file per the non-negotiable rules above.

**Zero direct Anthropic API calls from the script.** All LLM work runs in conversation context — visible, pausable, no quota.

## When to use

- The canonical `cla` plugin (a core skill, agent, or guard hook) in another repo has evolved and you want this repo to catch up.
- You're onboarding this repo to a newer `cla` baseline that lives elsewhere.
- You want to selectively pull one skill without touching the rest.

**Onboarding order — `cla-init` → `/cla:sync-context` → `update-cla`.** `update-cla` syncs only the portable asset core and **never creates or populates project data** — it will not scaffold `cla.io/` or populate `cla.io/project-facts.md` for you. Full fallback detail if a step is skipped: `references/invocation.md`.

Scanned trees: `.claude/plugins/cla/skills`, `agents`, `hooks`, `output-styles` (`SCAN_DIRS`), **plus the four repo-root launchers `cla`/`cla.cmd`/`claw`/`claw.cmd` by name** (`SCAN_FILES`). The `.claude-plugin/` manifest is synced by hand; the project overlay is never synced (rule 5). A repo receiving a launcher for the FIRST time must run `git update-index --chmod=+x claw` (and `cla`) once — `apply.py` writes content, not file mode. Full detail: `references/invocation.md`.

## When NOT to use

- *Other* installed plugins' internal assets (a third-party `{plugin}/commands/`, `{plugin}/skills/`) — out of scope; this skill syncs only cla's own `skills`/`agents`/`hooks`/`output-styles` tree.
- `.claude/settings.json` — project-level config, out of scope (guard hooks wire themselves via the plugin's own `hooks/hooks.json`, no manual step needed). Full detail + the one hand-wired exception: `references/invocation.md`.

## Invocation

```
/cla:update-cla <source-repo> [asset-path]
```

`source-repo` (required) — absolute path, `~`-path, or a short name resolved via `~/.claude/sync-config.json`. `asset-path` (optional) — file/dir/glob under `.claude/plugins/cla/` to limit scope; defaults to all of it. Reads from `<source-repo>`, writes to CWD (override with `--local <path>`).

**Read `references/invocation.md` first** for asset-path examples, the full required-environment list (`git`, `gh` only for `--mode pr`, the optional `sync-config.json` schema — `ANTHROPIC_API_KEY` is NOT required), the flags table, and portability notes.

## Workflow — what you (conversation Claude) do

The user invokes `/cla:update-cla <source> [asset]`. You drive three phases: **Discover** (script) → **Adapt** (you reason) → **Apply** (script). **Read `references/phases.md` first** — it carries the full step-by-step procedure, exact script invocations, and state-file JSON shapes for all three phases below; this section holds only the load-bearing spine.

### Phase 1 — Discover (script call, no reasoning)

```
python3 .claude/plugins/cla/skills/update-cla/scripts/orchestrate.py discover \
    <source-repo> [<asset-path>] [--local <path>]
```

Compares source vs. local content hash per file; identical files skip silently, new files have no local counterpart. Diverging files classify against `.claude/plugins/cla/.cla-sync-lock.json`'s recorded ancestor into `divergent` / `source-advanced` / `local-advanced` / `both-diverged` (full decision table: `references/phases.md`). Binary and read-error files go to `skipped`, never round-tripped through the LLM. A lock-tracked local asset absent from source surfaces as `deleted-in-source` in a separate `deletions` array — **never auto-applied**. Writes `temp/sync-state/<RUN-ID>/divergences.json`.

**Display the discovery summary verbatim.** If `total = 0` and there are no deletions, report and exit.

### Phase 2 — Adapt (you reason; one rewrite per file)

For each file: read the source content, the local existing version (`null` for `new` files), and local repo context (`CLAUDE.md`, file listing, `plugin.json`), then act on the file's status per the table in `references/phases.md` (`source-advanced` → adopt freely; `local-advanced` → keep local, source would regress it; `both-diverged` → careful manual reconcile per rule 1; `divergent` → judgment alone, no ancestor available).

**One rewrite per file** — do this in a single pass per file, following `references/adaptation_prompt.md` and the non-negotiable rules above; do not iterate multiple draft rewrites of the same file inline. The most common failure is silently overwriting local content the source lacks (rule 3 especially). A `new` skill is still routed through `adaptations.json`, never `Write`n directly, so Phase 3 can perform its git-safety checks. Print a one-line `[i/N] <asset> — <summary>` per file, then write `adaptations.json` (schema: `references/phases.md`). Review any `deletions` by hand — **never auto-delete**; act outside this flow if removal is the right call.

### Phase 2.5 — Record upstream proposals (you reason; usually writes nothing)

A sync is the one moment when the same asset is in view in two repos at once — so it is
the moment a local file reveals itself as not merely *adapted* but genuinely **better**:
it fixes a defect in the portable harness, or covers a case source misses. Capture that
before the run ends, or it is lost until someone rediscovers it in another repo.

For each local divergence you kept, apply one test: **would every repo running the plugin
be better off if source adopted this?** Yes → append a proposal to `cla-upstream.md` at
the destination repo root. No → it is this repo's adaptation, which belongs in the
`project-context.md` overlay, not here.

**Read `references/upstream-proposals.md` first** for the admission test, the item shape,
the dedup rule, and the append-only discipline. Three things are load-bearing:

- **Not an inventory.** Most divergences are legitimate local adaptation. Recording them
  all buries the real defects, and a file that is mostly noise stops being read.
- **Never overwrite hand-written content.** These files are often long-form human
  analysis. Append only — never reorder, reword, renumber, or delete an existing item.
- **Most runs add nothing.** An empty result is the normal outcome, not a missed step.

This writes prose in the *destination* repo only. It never touches the source repo, never
edits code, and never marks an item ported — the source repo collects from these files
when it chooses to.

Then trigger Phase 3.

### Phase 3 — Apply (script call, no reasoning)

```
python3 .claude/plugins/cla/skills/update-cla/scripts/orchestrate.py apply \
    --run <RUN-ID> [--mode worktree|pr] [--local <path>]
```

- **`worktree`** (default) — writes adapted files directly into the local working tree; per-file dirty-worktree/binary-placeholder checks isolate failures without halting the run.
- **`pr`** — whole-tree dirty check, then branch + commit + push + `gh pr create`. **Opens a PR for review only — never runs `gh pr merge`.** Merging is always a manual, separate step by the user.

Every `wrote` outcome also best-effort updates `.claude/plugins/cla/.cla-sync-lock.json` (never fails the run on write failure) — see "Sync provenance lockfile" below. Full mode recipes: `references/phases.md`.

**Display the apply summary verbatim.**

## Sync provenance lockfile

`.claude/plugins/cla/.cla-sync-lock.json` records, per synced asset, the sha256 of the adapted content Phase 3 last wrote to local — the common ancestor Phase 1's 3-way classification needs. Auto-maintained by `apply` (never hand-edited), committed per destination repo, and excluded from the sync scan itself (it's a dotfile outside `SCAN_DIRS`). Full schema, the "written bytes not raw source" rationale, and the resulting label-noise caveat: `references/lockfile.md`.

## Failure semantics

**Never auto-merges.** `worktree` mode (default) writes straight to the working tree; `pr` mode opens a PR and stops — the user reviews and merges by hand. **Per-file isolation:** a failure on one asset does NOT halt the run. Outcome statuses: `wrote`, `skipped_dirty_worktree`, `skipped_binary`, `failure`. Exit codes from `apply`: `0` — at least one file succeeded OR nothing to write; `1` — every file failed; `2` — missing/unreadable state files (re-run discover, or Phase 2 never wrote `adaptations.json`).

## stdout / stderr discipline

- **stdout** — structured user-facing content: discovery summary, next-step prompts, final apply summary.
- **stderr** — diagnostics, warnings, per-file failure lines.

## Guards and known limitations

Two pytest guards protect this skill's cross-repo safety: a **conformance guard** (`tests/test_no_project_tokens.py` — no project-specific token leaks into synced-core `SKILL.md`/`references/**/*.md`, driven by the curated overlay `references/project-tokens.local.md`) and a **project-facts staleness guard** (`tests/test_project_facts_paths.py` — no dead repo-relative paths in `cla.io/project-facts.md` or any skill's `references/project-context.md` overlay). Run both with `pytest .claude/plugins/cla/skills/update-cla/tests`. Full mechanics, the token-list curation discipline, and this skill's known limitations (3-way classification labels but never auto-merges; single source per run; no reverse propagation; deletions surfaced, never auto-applied): `references/guards.md`.

## References

- `references/phases.md` — the full Phase 1/2/3 mechanics: exact script invocations, the 3-way status-classification table, and the `divergences.json`/`adaptations.json` schemas.
- `references/lockfile.md` — `.cla-sync-lock.json`'s full schema and maintenance rules.
- `references/invocation.md` — asset-path examples, required environment, the flags table, portability notes, and the onboarding-order fallback detail.
- `references/guards.md` — the conformance guard, the project-facts staleness guard, and this skill's known limitations.
- `references/adaptation_prompt.md` — the Phase 2 per-file adaptation prompt.
- `references/upstream-proposals.md` — the Phase 2.5 reverse channel: the admission test for a carry-back, the `cla-upstream.md` item shape, and the append-only rule that protects hand-written entries.
- `references/pr_template.md` — the PR body template rendered by `apply --mode pr`.
- `references/project-tokens.local.md` — **OVERLAY, not a generic reference.** This repo's own curated token list for the conformance guard; never synced, never treated as portable content.
