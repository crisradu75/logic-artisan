---
name: cla-init
description: "Idempotent, never-clobber project-data scaffolder for the cla plugin: creates a fresh (or partially-scaffolded) repo's cla.io/ tree — decisions/, feedback/, retro/, lessons-learned/ dirs, the empty .jsonl retro ledgers, the feedback/notes.md inbox, the lessons-learned log — and seeds skeleton references/project-context.md overlay stubs for skills that consume one. Creates only what's missing; never overwrites or re-seeds what already exists, so it's safe to re-run anytime. Does NOT wire the plugin manifest or settings (stays manual). Triggers on /cla:cla-init or natural language like 'scaffold cla.io', 'initialize the cla plugin data', 'onboard this repo to cla', 'set up the cla project data'."
argument-hint: "(no args — scaffolds the current repo)"
allowed-tools: Bash, Read, Grep, Glob
---

# /cla:cla-init — scaffold the cla plugin's project-data baseline

Bring a fresh or partially-scaffolded repo up to the project-data baseline the other `cla` skills
expect: the `cla.io/` tree (retro ledgers, feedback inbox, lessons-learned log, decisions dir) and
skeleton `references/project-context.md` overlay stubs for each skill that reads its own overlay.

This skill is **project-data only**. It does NOT sync, adapt, or touch any *asset-core* file
(`SKILL.md` bodies, agents, hooks) — that is `update-cla`'s job.

## When to use

Onboarding a repo to the `cla` plugin. The recommended order is **`cla-init` first** (scaffold this
repo's project data + overlay stubs), **then `/cla:sync-context`** (populate `cla.io/project-facts.md`
and the overlay pointers with this repo's actual facts — content, not structure), **then `update-cla`**
(sync/adapt the portable asset core from a source repo). `update-cla` never creates project data, so a
repo that skips `cla-init` is left without the `cla.io/` tree and the overlay stubs, and the
retro/feedback/learnings skills degrade or fail on first use; skipping `/cla:sync-context` leaves
`cla.io/project-facts.md` absent, so every skill that reads it gracefully falls back to its own
per-skill overlay (or a bare pointer) instead. `cla-init` is safe to re-run any time — a fully-scaffolded
repo re-runs as a no-op, and a repo that later grows a new overlay-consuming skill picks up its stub on
the next run.

Wiring the plugin manifest (`.claude-plugin/plugin.json`) and `.claude/settings.json` is **not** part
of this skill — see Non-goals below.

## Repo-root resolution

Resolve the repo root ONCE and write everything relative to it, so the scaffold lands in the right
place regardless of the working directory the skill is invoked from:

```bash
ROOT="$(git rev-parse --show-toplevel)"
```

If this errors (not inside a git working tree), stop and tell the user to run from within a git repo —
the plugin's standard repo-state resolution seam is git-based.

## Idempotent / never-clobber contract

- **Skip anything that exists — via a guarded idiom, never a bare redirect.** For every directory and
  every seed/stub file, check existence FIRST; if present, skip it untouched (no truncate, no
  overwrite, no re-seed, no merge) and report `exists (skipped)`.
- **The guard is load-bearing.** A bare `> "$f"` or `cat > "$f"` truncates an existing file and defeats
  never-clobber. ALWAYS guard with `[ -e "$f" ] ||`. Pinned idioms:
  - directory → `mkdir -p "$dir"` (idempotent by construction)
  - 0-byte ledger → `[ -e "$f" ] || : > "$f"`
  - seed/stub file with content → `[ -e "$f" ] || cat > "$f" <<'EOF'` … `EOF`
- **Create only what is missing.** A partially-scaffolded repo ends fully scaffolded with every
  pre-existing piece byte-for-byte unchanged. A `.jsonl` with history, a filled `notes.md`, or a
  populated `project-context.md` is ALWAYS skipped, even though the seed content differs.
- **Report `created` vs `exists (skipped)` per target**, so a re-run is transparently a no-op on
  already-present pieces.

## Scaffold manifest

All paths relative to `$ROOT`. Every item is create-if-absent per the contract above.

### 1. `cla.io/` directories

```bash
mkdir -p "$ROOT/cla.io/decisions" "$ROOT/cla.io/feedback" "$ROOT/cla.io/retro" "$ROOT/cla.io/lessons-learned"
```

`cla.io/decisions/` gets no seed file — an empty dir is the correct initial state (it holds ad-hoc
shaped-decision `.md` files created by `shape-decision`/`multi-spec`).

### 2. Retro ledgers (0-byte — an empty file is a valid empty JSONL ledger; NO `[]` or placeholder line)

```bash
# One ledger per loop that has a READER. Both are appended via the shared
# lib/log_run.py, which takes the ledger filename as its argument.
#
# There were four more (multi-pr, multi-spec, multi-lite, project-review). None
# had an analyzer skill, and between them they accumulated 19 records across
# five repos, so they were deleted. If you add a ledger here, add the skill that
# reads it in the same change — an unread ledger is exhaust, not data.
for f in spec-to-pr-runs codify-runs; do
  [ -e "$ROOT/cla.io/retro/$f.jsonl" ] || : > "$ROOT/cla.io/retro/$f.jsonl"
done
```

### 3. Feedback inbox — `cla.io/feedback/notes.md`

```bash
[ -e "$ROOT/cla.io/feedback/notes.md" ] || cat > "$ROOT/cla.io/feedback/notes.md" <<'EOF'
# App experience notes

<!-- Captured feedback lands here as bullet points. One observation per line. -->
EOF
```

### 4. Lessons-learned log — `cla.io/lessons-learned/lessons-learned.md`

```bash
[ -e "$ROOT/cla.io/lessons-learned/lessons-learned.md" ] || cat > "$ROOT/cla.io/lessons-learned/lessons-learned.md" <<'EOF'
# Lessons learned

<!-- Rolling log written by /cla:codify-learnings, which prepends each report. Newest entries at the top. -->
EOF
```

### 5. Per-skill overlay stubs

Seed a skeleton `references/project-context.md` for each skill that **consumes its own overlay** as a
source of this repo's facts and does not yet have the file.

**Discovery predicate (a mere marker mention is NOT a consumer).** "Reads its own overlay" ≠ "the
string `references/project-context.md` appears in the skill dir." Determine the consumer set as:

- **(a) Scan scope** — only each skill's `SKILL.md` and its non-overlay `references/*.md` files. Do NOT
  scan `scripts/` or `tests/` (they name the marker as the sync-exclusion mechanism, not to consume it).
  Seed the *candidate* set with `grep -rl 'references/project-context.md' "$ROOT"/.claude/plugins/cla/skills/*/SKILL.md "$ROOT"/.claude/plugins/cla/skills/*/references/*.md` (ignore no-match errors for skills without a `references/` dir), then apply the consumer test (b) and exclusions (c) to that candidate list — the grep only narrows *where to look*, it does not by itself decide consumer status.
- **(b) Consumer test** — count a skill as a consumer only when that text *directs reading the overlay
  for this repo's facts*: a "see/read `references/project-context.md` for this repo's …" or "inject the
  repo facts from `references/project-context.md`" instruction. A file that merely *names* the marker
  to document the preservation/exclusion convention is NOT a consumer.
- **(c) Explicit exclusions** — `update-cla` and `cla-init` are never seeded. `update-cla` names the
  marker only to document rule 5 (sync-preservation); `cla-init` (this skill) names it structurally in
  its own scaffold manifest + stub template. Both saturate a naive substring match yet neither consumes
  an overlay of its own.

For each consumer skill lacking the file, create the `references/` dir if absent, then write the stub:

```bash
mkdir -p "$ROOT/.claude/plugins/cla/skills/<skill>/references"
STUB="$ROOT/.claude/plugins/cla/skills/<skill>/references/project-context.md"
[ -e "$STUB" ] || cat > "$STUB" <<'EOF'
# <skill> — project context overlay

<!--
Project-specific overlay for the `<skill>` cla skill. This file is repo-local
(never synced by update-cla). The generic SKILL.md supplies the procedure; this
file supplies the repo's facts. A skill runs fine against an empty stub — fill in
only the sections its SKILL.md references, delete the rest.
-->

## Repo commands
<!-- build/lint/test/dev commands with this repo's package-manager + workspace tokens -->

## Packages, paths, and app names
<!-- workspace/app/package/dir names and file paths this skill touches -->

## Permission sets
<!-- repo-scoped tool-permission expectations, if the skill uses them -->

## Incident / offense history
<!-- past failures in this repo that justify a discipline rule in the skill -->

## Product / domain context
<!-- this repo's applications, data, market, concepts -->

## Infrastructure values
<!-- ports, service names, env-var names tied to this repo's processes -->

## Repo file lists
<!-- enumerated specs/docs/files this skill is expected to touch -->
EOF
```

Substitute `<skill>` per skill. The stub seeds the **full menu** of fact-category sections (matching the
categories the `cla-plugin` "Per-skill project-context overlay" requirement enumerates); the human
filling it in prunes the sections the skill doesn't use.

## Report

At the end, print a per-target summary — each directory, ledger, seed, and stub as `created` or
`exists (skipped)` — so a re-run is transparently a no-op on already-present pieces.

## Non-goals (pinned — never do these)

- Does **NOT** create, read, or modify `.claude-plugin/plugin.json` (the manifest) — a per-repo manual
  onboarding step.
- Does **NOT** create, read, or modify `.claude/settings.json` or `.claude/settings.local.json` — also
  manual, per-repo.
- Does **NOT** read, copy, or modify any asset-core file (a `SKILL.md` body, an agent, a hook). It only
  *creates a stub file alongside* a skill; it never edits the skill. Asset-core sync is `update-cla`'s job.
- Does **NOT** fill overlay stubs with real repo facts — stubs stay content-free skeletons; a human (or
  the extraction pass) fills them.
