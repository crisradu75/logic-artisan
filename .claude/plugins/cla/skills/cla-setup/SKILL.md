---
name: cla-setup
description: "Set up or refresh a repo for the cla plugin: create whatever is missing of cla.io/ without overwriting anything there, seed OpenSpec authoring rules, write the economy rules file .claude/rules/cla-economy.md (replaced whole on every run), and populate or reconcile cla.io/project-facts.md from the repo's own manifests. Changes any other existing file only on the user's yes, apart from appending one line to .gitignore. Run with /cla:cla-setup."
argument-hint: "(no args — sets up the current repo)"
allowed-tools: Bash, Read, Write, Edit, Grep, Glob, AskUserQuestion
# Slash-command only: run deliberately, at onboarding and when facts go stale. Keeps this
# description out of the always-loaded skill listing; other skills tell the user to run it.
disable-model-invocation: true
---

# /cla:cla-setup — set up a repo's `cla.io/` and its facts

One skill for a repo's own `cla` data, in two parts:

- **Part 1, structure** — create whatever is missing of the `cla.io/` tree, the run ledger, the
  feedback inbox and lessons log, and the OpenSpec authoring rules; report retired ledgers and keep
  the chains' run notes out of git, and write the economy rules file. Creates only what is missing,
  except that rules file, which it replaces whole.
- **Part 2, facts** — read the repo's own manifests and write or reconcile `cla.io/project-facts.md`,
  the one home for every command, path, port, install step and env file the other skills read.
  Proposes first, writes only on the user's yes, then runs the staleness checker.

Run it once at onboarding (marketplace install → `/cla:cla-setup` → install the `pre-push` hook) and
again whenever a skill reports missing or stale facts. A re-run on a set-up repo changes nothing
without a yes, except that it replaces the economy rules file with the plugin's current text and appends the run-notes line to `.gitignore` when that is missing. It replaces the former `cla-init` and `sync-context` skills, which no longer exist.

The plugin itself (`SKILL.md` bodies, agents, hooks) arrives with the install and is never touched
here: it is a read-only cache.

**Resolving `${CLAUDE_PLUGIN_ROOT}`.** This `SKILL.md` arrives with the placeholder substituted, but a
`references/` file opened with `Read` carries it literally, and it is not an environment variable in
Bash — an unset variable silently runs the command against `/skills/...`. Before running a command
that contains the literal text, replace it with the plugin root: the `Base directory for this skill`
path with `/skills/<name>` removed, or the absolute path of any plugin file you have read, cut
at `.../plugins/cla`. If neither works, say so and stop. Detail:
`${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/plugin-root.md`.

**Step detail lives in `references/`.** Items 5, 6, 7, 7a, 9 to 12, "Where a fact goes" and "The spec
map scaffold" are stubs here: each states what the step does and when it asks, and names the reference
to **read before running the step**. The never-clobber contract below applies to every step, including
those.

## Repo-root resolution

Resolve the repo root ONCE and read and write everything relative to it:

```bash
ROOT="$(git rev-parse --show-toplevel)"
```

If this errors (not inside a git working tree), stop and tell the user to run from within a git repo.

## Never-clobber contract

- **Skip anything that exists — via a guarded idiom, never a bare redirect.** For every directory and
  seed file in Part 1 (the rules file of item 7a is the one exception, replaced whole), check existence FIRST; if present, skip it untouched (no truncate, no
  overwrite, no re-seed, no merge) and report `exists (skipped)`.
- **The guard is load-bearing.** A bare `> "$f"` or `cat > "$f"` truncates an existing file and defeats
  never-clobber. ALWAYS guard with `if [ -e "$f" ]`. Every pinned idiom echoes its outcome, so the
  per-target report below needs no second command:
  - directory → `if [ -e "$dir" ]; then echo "exists (skipped): $dir"; else mkdir -p "$dir"; echo "created: $dir"; fi`
  - 0-byte ledger → `if [ -e "$f" ]; then echo "exists (skipped): $f"; else : > "$f"; echo "created: $f"; fi`
  - seed file with content → `if [ -e "$f" ]; then echo "exists (skipped): $f"; else cat > "$f" <<'EOF'` … `EOF`, then `echo "created: $f"; fi`
- **Create only what is missing.** A partly set-up repo ends fully set up with every pre-existing
  piece byte-for-byte unchanged, the rules file aside: a `.jsonl` with history or a filled
  `notes.md` is ALWAYS skipped, even though the seed content differs.
- **A change to an existing file needs the user's yes, every time**; each item says where it asks.
  The unasked writes are item 7's appended `.gitignore` line and item 7a's rules file, which the
  plugin owns whole and replaces on every run.
- **Overlays are optional, and this skill never creates one.** `cla.io/overlays/<skill>.md` holds a
  repo's skill-specific rules when it has some; a skill without one runs on its generic procedure
  and `cla.io/project-facts.md`.
- **Report `created` vs `exists (skipped)` per target**, so a re-run is transparently a no-op. The
  rules file reports `created`, `replaced` or `unchanged` instead.

## Part 1 — Structure

All paths relative to `$ROOT`. Items 1 to 4 create what is missing and skip what exists. Item 5 compares an existing OpenSpec config and edits it only on a yes. Item 6 deletes retired ledgers only on a yes. Item 7 appends one line to `.gitignore` unasked and untracks notes only on a yes. Item 7a replaces its rules file whole on every run.

### 1. `cla.io/` directories

```bash
for dir in decisions feedback retro lessons-learned; do
  d="$ROOT/cla.io/$dir"
  if [ -e "$d" ]; then echo "exists (skipped): $d"; else mkdir -p "$d"; echo "created: $d"; fi
done
```

`cla.io/decisions/` gets no seed file — an empty dir is the correct initial state (it holds ad-hoc
shaped-decision `.md` files created by `shape-decision`/`multi-spec`).

### 2. Retro ledger (0-byte — an empty file is a valid empty JSONL ledger; NO `[]` or placeholder line)

```bash
# The one ledger lib/log_run.py accepts; /cla:spec-to-pr-retro reads it.
for f in spec-to-pr-runs; do
  p="$ROOT/cla.io/retro/$f.jsonl"
  if [ -e "$p" ]; then echo "exists (skipped): $p"; else : > "$p"; echo "created: $p"; fi
done
```

### 3. Feedback inbox — `cla.io/feedback/notes.md`

```bash
f="$ROOT/cla.io/feedback/notes.md"
if [ -e "$f" ]; then echo "exists (skipped): $f"; else cat > "$f" <<'EOF'
# App experience notes

<!-- Captured feedback lands here as bullet points. One observation per line. -->
EOF
echo "created: $f"; fi
```

### 4. Lessons-learned log — `cla.io/lessons-learned/lessons-learned.md`

```bash
f="$ROOT/cla.io/lessons-learned/lessons-learned.md"
if [ -e "$f" ]; then echo "exists (skipped): $f"; else cat > "$f" <<'EOF'
# Lessons learned

<!-- Rolling log written by /cla:codify-learnings, which prepends each report. Newest entries at the top. -->
EOF
echo "created: $f"; fi
```

### 5. OpenSpec authoring rules — `openspec/config.yaml`

Seeds or compares the OpenSpec `rules:` block through `scripts/seed_openspec_rules.py`. An existing
`config.yaml` or `config.yml` stays **byte-identical** unless the user says yes to the exact `+` and `-`
lines the script lists; `openspec/` absent → create nothing. A non-zero exit, or output with no
`openspec/...:` status line, means the config was not checked: say so, never call the rules current.
**Read `references/openspec-rules.md` first** for the cases, the version check, the script call and the
quoting rule. If item 13 records a `scenario` test-proof choice, re-run the item 5 script after the
facts file is written.

### 6. Retired ledgers — `cla.io/retro/`

Lists the retired ledgers still present; deletes exactly the listed paths, and only on the user's
explicit yes. **Read `references/ledgers-and-run-notes.md` first** for the block and the ask.

### 7. Ignore the chains' run notes — `.gitignore`

Appends one ignore line for the chains' run notes to the repo's `.gitignore` unasked, unless a
`.gitignore` already ignores them; then lists run notes git already tracks and untracks exactly the
listed paths only on the user's explicit yes. Nothing is committed. **Read the same
`references/ledgers-and-run-notes.md` first** for the blocks, the `un-ignored` case and the ask.

### 7a. The economy rules file — `.claude/rules/cla-economy.md`

The plugin owns this file whole: it is rendered from `_shared/references` sources and replaced with no
prompt whenever it differs (report `created`, `replaced` or `unchanged`). A failure prints `NOT written`
with the reason and stops only this block; carry on with item 8. This skill never touches `CLAUDE.md`
or `AGENTS.md`. **Read `references/economy-rules-block.md` first** for the sources, the checks before
writing and the block.

## Part 2 — Facts

### Where a fact goes

`cla.io/project-facts.md` holds the repo's facts (commands, paths, ports, env files); an optional
`cla.io/overlays/<skill>.md` holds only that skill's own rules; a dated incident's story goes to
`cla.io/lessons-learned/`; machine-read `*.local.md` files are never reshaped here. **Read
`references/facts-file.md` first** for the section list of the facts file, the exact `Test proof`,
`Full gate` and `Spec map` line forms, and the terminology file. Keep the facts file terse: one fact
per line, under its `##` section.

### The spec map scaffold

Offered once per run, only when `openspec/specs/` exists and the facts file has no `## Spec map`
section; written only on the user's yes, at a path inside the repo, never overwriting a file and never
under the plugin tree. Declining writes no map and no heading. Declaring a map has a cost (the checker
then fails on an unlinked spec): say so when offering. **Read `references/spec-map-scaffold.md`
first** for the recommended path, what goes in the file and the scaffold text.

### 8. Read the repo

Read whatever this repo actually has — do not assume any particular stack. Typical sources: the
workspace manifest, the root package/build manifest and its scripts, lint/test config, per-member
manifests, dev-server configs for ports, `.env.example` files, the root guidance docs (every instruction file that
exists, `CLAUDE.md` and `AGENTS.md`; see `${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/instruction-files.md`)
and any per-subapp guidance docs, `README.md`, and `openspec/specs/**` if the repo uses
OpenSpec. This is deliberately an LLM read-and-reason pass, not a stack-specific parser — that is what
makes it portable.

### 9. Read the existing state

Read `cla.io/project-facts.md` (a reconcile when present), every `cla.io/overlays/*.md` except the
`*.local.md` files, `cla.io/project-tokens.local.md` and `cla.io/terminology.md`, sorting each overlay
line into fact, rule, incident, duplicate or scaffolding. When unsure whether a line is a rule, call it
one. Reads only; nothing is written until item 13. **Read `references/overlay-reconcile.md` first**
(items 9 to 12 are all in it).

### 10. Draft the changes

Draft the full proposed facts file, each overlay's change, a migration recommendation for any
legacy-location overlay (never edited), and the Test proof line. Detail in
`references/overlay-reconcile.md`.

### 11. Optionally reconcile `cla.io/terminology.md`

If the file exists, draft merges for near-duplicate or conflicting terms; absent file or no issues:
skip silently. Detail in `references/overlay-reconcile.md`.

### 12. Propose new `project-tokens.local.md` entries

Draft additions for new distinctive compound repo-specific tokens only, never generic words; grep the
plugin tree for each candidate first. Detail in
`references/overlay-reconcile.md`.

### 13. Confirm, write, check

Show the user, in order:

1. Whether `cla.io/project-facts.md` was absent (created) or present (reconciled).
2. The drafted `cla.io/project-facts.md` — in full when new or heavily changed, else as a diff.
3. Each overlay change from item 10, file by file: rules kept, lines moved to the facts file,
   stories moved to the lessons log, duplicates dropped (and where they are stated), files proposed
   for deletion.
4. Migration recommendations for legacy-location overlays.
5. Proposed `project-tokens.local.md` additions, each with its one-line justification.
6. Any `cla.io/terminology.md` reconciliation from item 11.
7. The spec map offer from "The spec map scaffold", when it applies, with its own yes and path.
8. Test proof granularity, when `openspec/` exists and the facts file has no `## Test proof` line:
   ask once, with `requirement` recommended (the line is item 10's draft 4). Without an answer the
   checker silently uses `requirement`.

Ask for a yes (`AskUserQuestion` or a plain yes/no) before writing anything; on a request for
changes, revise and ask again rather than applying part of it. On yes, write each confirmed file
with `Write`/`Edit` and delete each confirmed overlay with `rm --`. **Every target must be repo
content** — `cla.io/**`, or the spec map path the user chose in "The spec map scaffold". A target that resolves inside the plugin tree is reported as a migration
recommendation, never written. A declined proposal leaves its file untouched.

**Then run the staleness checker against what was just written:**

```
python3 ${CLAUDE_PLUGIN_ROOT}/skills/cla-setup/scripts/check_fact_paths.py
```

It MUST exit 0. Exit 1 names each stale path: fix every one and re-run. A path containing a
placeholder (`{...}` or `<...>`) is never checked, so write an example path with one. A line that
says `found at <path>` means the path exists only deeper in the tree: it is likely such an example. Exit 2 means it could not
look (stderr says why): fix that, and never read a 2 as a pass. Nothing in the plugin runs it
again; a repo that wants it standing wires it into its own gate. A gate still wiring the `0.x`
`conformance-checks/tests` directory checks nothing: say so and recommend this program.

## Report

One summary at the end, item by item: each target's outcome in the words its item uses, each
overlay's lines and where they went (kept, facts file, lessons log, dropped), every declined
proposal, the checker's exit code with every stale path it named, and every legacy-location
recommendation.

## Non-goals

- Does **NOT** create, read, or modify `.claude-plugin/plugin.json` or `.claude/settings*.json` —
  per-repo manual onboarding steps.
- Does **NOT** touch any plugin file (a `SKILL.md`, an agent, a hook). The plugin tree is a read-only
  cache.
- Does **NOT** create overlays, and never writes a fact into one.
- Does **NOT** touch `CLAUDE.md` or `AGENTS.md`: the economy rules file of item 7a is the plugin's own file, and
  the repo's rules stay in its instruction files.
- Does **NOT** write anything in Part 2 without the user's yes.
- Does **NOT** parse a stack-specific config format with a hardcoded parser — it reads and reasons
  about whatever this repo actually has.
- Does **NOT** author `cla.io/terminology.md` entries — only item 11's reconciliation.
