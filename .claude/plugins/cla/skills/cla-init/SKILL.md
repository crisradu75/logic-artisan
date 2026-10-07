---
name: cla-init
description: "Idempotent, never-clobber project-data scaffolder for the cla plugin: creates a fresh (or partially-scaffolded) repo's cla.io/ tree — decisions/, feedback/, retro/, lessons-learned/ dirs, the empty .jsonl retro ledgers, the feedback/notes.md inbox, the lessons-learned log — and seeds skeleton cla.io/overlays/<skill>.md stubs for skills that consume one, plus OpenSpec authoring rules in a missing openspec/config.yaml (printed for pasting when the file exists). Creates only what's missing; never overwrites or re-seeds what already exists, so it's safe to re-run anytime. Does NOT wire the plugin manifest or settings (stays manual). Triggers on /cla:cla-init or natural language like 'scaffold cla.io', 'initialize the cla plugin data', 'onboard this repo to cla', 'set up the cla project data'."
argument-hint: "(no args — scaffolds the current repo)"
allowed-tools: Bash, Read, Grep, Glob
# Slash-command only (once per repo, at onboarding): keeps this description out of the
# always-loaded skill listing. Nothing invokes it programmatically.
disable-model-invocation: true
---

# /cla:cla-init — scaffold the cla plugin's project-data baseline

Bring a fresh or partially-scaffolded repo up to the project-data baseline the other `cla` skills
expect: the `cla.io/` tree (retro ledgers, feedback inbox, lessons-learned log, decisions dir) and
skeleton `cla.io/overlays/<skill>.md` overlay stubs for each skill that reads its own overlay.

This skill is **project-data only**. It does NOT touch any *asset-core* file (`SKILL.md` bodies,
agents, hooks) — those arrive with the plugin install.

## When to use

Onboarding a repo to the `cla` plugin. The recommended order is **the marketplace install first**
(`claude plugin marketplace add …` then `claude plugin install … --scope project`, which delivers the
portable asset core), **then `cla-init`** (scaffold this repo's project data + overlay stubs), **then
`/cla:sync-context`** (populate `cla.io/project-facts.md` and the overlay pointers with this repo's
actual facts — content, not structure). The install never creates project data, so a
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
  populated `cla.io/overlays/<skill>.md` is ALWAYS skipped, even though the seed content differs.
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
# Seeded: one ledger per loop with a RETRO skill reading it, appended via the
# shared lib/log_run.py (which takes the ledger filename as its argument):
#   spec-to-pr-runs     read by /cla:spec-to-pr-retro
#   codify-runs         read by /cla:codify-retro
# Not seeded — log_run.py creates each on its first append:
#   lite-pr-runs, shape-decision-runs, feedback-runs
#                       read by lib/ledger_summary.py, named in each skill
#   right-model-runs    no reader yet: right-model names /cla:project-review,
#                       which does not read it (tracked in #299)
#
# There were four more (multi-pr, multi-spec, multi-lite, project-review). No
# skill pointed a reader at them, so they were deleted. If you add a ledger, name
# its reader in the same change — an unread ledger is exhaust, not data.
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

Seed a skeleton `cla.io/overlays/<skill>.md` for each skill that **consumes its own overlay** as a
source of this repo's facts and does not yet have the file.

**Overlays live in the repo, not the plugin.** Under a marketplace install the plugin tree is a
read-only cache, so a per-repo fact stored beside the skill would be unwritable — and silently so,
since every consumer treats a missing overlay as the ordinary un-configured state.

**Discovery predicate (a mere marker mention is NOT a consumer).** "Reads its own overlay" ≠ "the
string `cla.io/overlays/` appears in the skill dir." Determine the consumer set as:

- **(a) Scan scope** — only each skill's `SKILL.md` and its `references/*.md` files. Do NOT
  scan `scripts/` or `tests/` (they name the marker mechanically, not to consume an overlay).
  Seed the *candidate* set with `grep -rl 'cla.io/overlays/' "${CLAUDE_PLUGIN_ROOT}"/skills/*/SKILL.md "${CLAUDE_PLUGIN_ROOT}"/skills/*/references/*.md` (ignore no-match errors for skills without a `references/` dir), then apply the consumer test (b) and exclusions (c) to that candidate list — the grep only narrows *where to look*, it does not by itself decide consumer status.
- **(b) Consumer test** — count a skill as a consumer only when that text *directs reading the overlay
  for this repo's facts*: a "see/read `cla.io/overlays/<skill>.md` for this repo's …" or "inject the
  repo facts from `cla.io/overlays/<skill>.md`" instruction. A file that merely *names* the marker
  to document the preservation/exclusion convention is NOT a consumer. **A skill citing a SIBLING's
  overlay does not make itself a consumer** — match on the skill's own name in the path.
- **(c) Explicit exclusion** — `cla-init` is never seeded. This skill names the marker structurally,
  in its own scaffold manifest + stub template, so it saturates a naive substring match without
  consuming an overlay of its own.

For each consumer skill lacking the file, write the stub:

```bash
mkdir -p "$ROOT/cla.io/overlays"
STUB="$ROOT/cla.io/overlays/<skill>.md"
[ -e "$STUB" ] || cat > "$STUB" <<'EOF'
# <skill> — project context overlay

<!--
Project-specific overlay for the `<skill>` cla skill. This file is repo-local
(it lives in cla.io/, outside the plugin, and is never synced). The generic
SKILL.md supplies the procedure; this file supplies the repo's facts. A skill
runs fine against an empty stub — fill in only the sections its SKILL.md
references, delete the rest.
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

### 6. OpenSpec authoring rules — `openspec/config.yaml`

The one path outside `cla.io/` this skill writes, and it is still project data. OpenSpec injects a
config's `rules:` into every artifact's authoring instructions, so the block below is how OpenSpec's
own stock limits reach every CLA authoring run.

- `openspec/` exists and neither `openspec/config.yaml` nor `openspec/config.yml` does → seed
  `config.yaml` and report `created`.
- Either file exists → leave it **byte-identical** and print the block for the user to paste.
  OpenSpec reads `config.yaml` first, so a new `config.yaml` would silently hide an existing
  `config.yml`. Never merge or append: never-clobber forbids it, and `openspec init` writes
  `config.yaml` whenever neither exists, so printing is the common path.
- `openspec/` absent → print the block and create nothing. `openspec init` owns that directory.

```bash
: "${ROOT:?ROOT unset: set it with the repo-root step at the top of this skill first}"
CFG="$ROOT/openspec/config.yaml"
RULES="$(cat <<'EOF'
rules:
  proposal:
    - Keep it to one page. Point to the specs and design instead of restating them.
  design:
    - Write design.md only when a stock trigger applies (a cross-cutting change, a new dependency or data model, security, performance or migration complexity, or real ambiguity), and name the trigger.
    - Never restate the proposal or the specs.
  specs:
    - State one behaviour per ADDED requirement in 500 characters or fewer, and put the detail in scenarios.
    - "A change with no externally visible behaviour change (a refactor, tooling, docs) sets `skip_specs: true` in its .openspec.yaml and writes no spec delta. Never invent a requirement to satisfy validation."
    - Read existing specs cheaply first (`openspec list --specs`, then `openspec show <id> --type spec --json --no-scenarios`), and read in full only the specs this change touches.
    - "Keep every scenario heading unique within its spec, so `<spec> / <heading>` names exactly one scenario."
  tasks:
    - "Give each scenario this change adds, or whose text it changes, a test task whose test carries a `scenario: <spec> / <heading>` comment line above it, or a line `manual: <heading>: <reason>`. A pure heading rename, or a scenario carried forward unchanged in a MODIFIED block, needs neither."
EOF
)"
if [ -d "$ROOT/openspec" ] && [ ! -e "$CFG" ] && [ ! -e "$ROOT/openspec/config.yml" ]; then
  if printf 'schema: spec-driven\n\n%s\n' "$RULES" > "$CFG"; then
    echo "openspec/config.yaml: created"
  else
    echo "openspec/config.yaml: write FAILED; add this block by hand:"
    printf '%s\n' "$RULES"
  fi
else
  if [ ! -d "$ROOT/openspec" ]; then
    echo "openspec/config.yaml: not written, no openspec/ (run openspec init, then add this block):"
  else
    echo "openspec/config.yaml: not written, a config exists; if it has no rules: block, add this one:"
  fi
  printf '%s\n' "$RULES"
fi
```

Each item that contains `: ` stays double-quoted, or YAML reads it as a mapping and OpenSpec drops
that artifact's rules.

## Report

At the end, print a per-target summary — each directory, ledger, seed, and stub as `created` or
`exists (skipped)` — so a re-run is transparently a no-op on already-present pieces. For
`openspec/config.yaml`, report `created`, or `not written` followed by the `rules:` block to paste.

## Non-goals (pinned — never do these)

- Does **NOT** create, read, or modify `.claude-plugin/plugin.json` (the manifest) — a per-repo manual
  onboarding step.
- Does **NOT** create, read, or modify `.claude/settings.json` or `.claude/settings.local.json` — also
  manual, per-repo.
- Does **NOT** read, copy, or modify any asset-core file (a `SKILL.md` body, an agent, a hook). It only
  *creates a stub file under `cla.io/overlays/`* (and, as project data, seeds a missing
  `openspec/config.yaml`); it never touches the skill itself, and it could not — the plugin tree is read-only. The asset core arrives with the plugin install.
- Does **NOT** fill overlay stubs with real repo facts — stubs stay content-free skeletons; a human (or
  the extraction pass) fills them.
