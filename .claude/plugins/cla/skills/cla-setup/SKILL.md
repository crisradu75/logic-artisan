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

The one path outside `cla.io/`, `.gitignore` and the rules file of item 7a this skill writes, and it is still project data. OpenSpec injects a
config's `rules:` into every artifact's authoring instructions, so the block the script holds is how OpenSpec's
own stock limits reach every CLA authoring run.

- `openspec/` exists and neither `openspec/config.yaml` nor `openspec/config.yml` does → seed
  `config.yaml` and report `created`.
- Either file exists → leave it **byte-identical** and compare: the script lists, under its
  artifact, each shipped rule the file does not carry word for word (`+`) and each earlier wording
  of a shipped rule it still carries (`-`), or reports the rules current. OpenSpec reads
  `config.yaml` first, so a new `config.yaml` would silently hide an existing `config.yml`.
  `openspec init` writes `config.yaml` whenever neither exists, so this is the common path.
- Lines listed → show the user exactly those `+` and `-` lines and ask for a yes on that diff. Only
  on yes, add each `+` line under its artifact and delete each `-` line, and change nothing else: a
  line the script did not mark `-` is the repo's own and stays, however close it reads to a shipped
  rule. Never make this edit silently.
- `openspec/` absent → print the block and create nothing. `openspec init` owns that directory.

**OpenSpec version.** CLA relies on `openspec validate <change> --strict` failing a MODIFIED block that
drops a live scenario (verified on 1.14.1). When `openspec/` exists, run `openspec --version` and, if it
is older than 1.14.1, say so in the report and recommend upgrading.

Run the script, which holds the shipped `rules:` block and the earlier wordings, and report what it
prints. Any non-zero exit, or output with no `openspec/...:` status line, means the config was
not checked (exit 1: the script could not write or read it): say so, and never call the rules current.

```bash
: "${ROOT:?ROOT unset: set it with the repo-root step at the top of this skill first}"
SEED="${CLAUDE_PLUGIN_ROOT}/skills/cla-setup/scripts/seed_openspec_rules.py"
[ -f "$SEED" ] || { echo "openspec/config.yaml: NOT checked, seed script not found at $SEED (plugin root unresolved?)"; exit 1; }
python3 "$SEED" "$ROOT"
```

The script reads the `Test proof granularity:` line of `cla.io/project-facts.md` and compares the `tasks`
rule for that granularity (`requirement` when there is no line). When item 13 records a `scenario`
choice, re-run the script after the facts file is written, so the `tasks` rule offered matches it.

Each item in the script's `rules:` block that contains `: ` stays double-quoted, or YAML reads it as
a mapping and OpenSpec drops that artifact's rules.

### 6. Retired ledgers — `cla.io/retro/`

Ledgers a skill once wrote and nothing writes or reads any more. A repo onboarded earlier still
holds them, and no install removes them. This block only lists the ones present:

```bash
: "${ROOT:?ROOT unset: set it with the repo-root step at the top of this skill first}"
for f in codify-runs commit-provenance right-model-runs multi-pr-runs multi-spec-runs \
         multi-lite-runs project-review-runs lite-pr-runs shape-decision-runs feedback-runs; do
  if [ -e "$ROOT/cla.io/retro/$f.jsonl" ]; then echo "retired ledger: cla.io/retro/$f.jsonl"; fi
done
```

- Nothing printed → say none is present.
- Lines printed → show them and ask once whether to delete those files. Only on an explicit yes,
  `rm -- <each listed path>` (exactly the listed paths, nothing else under `cla.io/retro/`), and
  report each `deleted`; on anything else report each `kept` and leave it. The deletion is left
  uncommitted, like every other change this skill makes.

### 7. Ignore the chains' run notes — `.gitignore`

`/cla:multi-lite` and `/cla:multi-pr` keep their run notes as local working state that nothing
commits, and refuse to start while git would see them. This adds the ignore line unless a
`.gitignore` in the repo already ignores the notes (any equivalent pattern, CRLF or trailing spaces
included), creating the file if needed. Only a `.gitignore` counts: this machine's global excludes
and the clone's `.git/info/exclude` hide the notes here but not in any other clone.

```bash
: "${ROOT:?ROOT unset: set it with the repo-root step at the top of this skill first}"
line='cla.io/retro/*-run-notes-*.md'
probe='cla.io/retro/multi-lite-run-notes-x.md'
# The deciding pattern, as <source>:<line>:<pattern>; global excludes switched off.
match="$(git -C "$ROOT" -c core.excludesFile=/dev/null check-ignore -v --no-index "$probe")" || match=''
case "${match%%:*}" in
  .gitignore|*/.gitignore) from_repo=1 ;;
  *) from_repo=0 ;;
esac
if [ "$from_repo" = 1 ] && git -C "$ROOT" check-ignore -q --no-index "$probe"; then
  echo "exists (skipped): .gitignore run-notes line"
elif [ "$from_repo" = 1 ]; then
  # Matched but not ignored: a ! pattern un-ignores the notes on purpose.
  echo "un-ignored (left as is): $match"
else
  # A last line with no newline would swallow the new one.
  if [ -s "$ROOT/.gitignore" ] && [ -n "$(tail -c 1 "$ROOT/.gitignore")" ]; then echo >> "$ROOT/.gitignore"; fi
  printf '%s\n' "$line" >> "$ROOT/.gitignore"
  echo "created: .gitignore run-notes line"
fi
```

`un-ignored` → leave the file alone and tell the user the chains will not start until that `!` line
goes.

Ignoring does not untrack a notes file git already tracks; a re-run then edits it, which blocks
branch switches and lets a PR pick it up. List those:

```bash
: "${ROOT:?ROOT unset: set it with the repo-root step at the top of this skill first}"
git -C "$ROOT" ls-files -- 'cla.io/retro/*-run-notes-*.md' | sed 's/^/tracked run notes: /'
```

- Nothing printed → say none is tracked.
- Lines printed → show them and ask once whether to untrack them, warning that every other clone
  loses its working copies on its next pull (history keeps them). Only on an explicit yes,
  `git -C "$ROOT" rm -q --cached -- <each listed path>` (exactly the listed paths; the files stay on
  disk), and report each `untracked`; on anything else report each `kept tracked`. Left
  uncommitted, like item 6.

### 7a. The economy rules file — `.claude/rules/cla-economy.md`

An agent working in this repo outside any skill reads the repo's own instruction files (`CLAUDE.md`, `AGENTS.md`)
and `.claude/rules/*.md` and nothing from the plugin. A rules file with no `paths:` frontmatter loads at
launch with the same priority as `.claude/CLAUDE.md`, so this file gets the cost rules to that
agent. The plugin owns the file whole: it is compared on every run and replaced with no prompt when
it differs, so a hand edit is replaced and the report says so (the repo's own rules go in its
instruction files; `${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/instruction-files.md` says which). The file is usually committed in the repo, so an upgrade that changes it shows as an
ordinary diff; if `.claude/` is ignored it stays local. This skill never touches `CLAUDE.md` or `AGENTS.md`.

The text is `${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/economy-rules-file.md` with two sources
inlined at its markers: `orchestration-economy.md` whole, and the span of `model-routing.md`
between its `review-sizing` begin and end comments. Every source is read through `tr -d '\r'`, so a
CRLF checkout and an LF one write the same bytes. The block prints `created`, `replaced` (existing
content differed, and a second line says local edits were overwritten) or `unchanged`, and writes
only when the text differs. Before writing it requires every source to be present and non-empty,
the begin and end comments to occur exactly once each and in that order, and each include marker
in the frame to occur exactly once; it renders to a temporary file and moves that into place, so a
failed write leaves the existing file untouched. Any failure prints `NOT written` with the reason
and stops the block: report it, then carry on with item 8 (Part 2). A failure here never stops the
skill.

The harness substitutes the literal plugin path for the `CLAUDE_PLUGIN_ROOT` placeholder in this
text when the skill loads; it is not a shell variable. If the block prints an unsubstituted or empty root, it
aborts without writing.

```bash
: "${ROOT:?ROOT unset: set it with the repo-root step at the top of this skill first}"
PLUGIN="${CLAUDE_PLUGIN_ROOT}"
[ -n "$PLUGIN" ] || { echo ".claude/rules/cla-economy.md: NOT written, plugin root unresolved"; exit 1; }
REF="$PLUGIN/skills/_shared/references"
RULES_FILE="$ROOT/.claude/rules/cla-economy.md"
fail() { echo ".claude/rules/cla-economy.md: NOT written, $1"; exit 1; }
FRAME="$(tr -d '\r' < "$REF/economy-rules-file.md")"
COST="$(tr -d '\r' < "$REF/orchestration-economy.md")"
MODEL="$(tr -d '\r' < "$REF/model-routing.md")"
if [ -z "$FRAME" ] || [ -z "$COST" ] || [ -z "$MODEL" ]; then
  fail "a source is missing or empty under $REF"
fi
BEGIN='<!-- economy-rules-file:review-sizing:begin -->'
END='<!-- economy-rules-file:review-sizing:end -->'
INC_COST='<!-- include: cost-rules -->'
INC_SIZING='<!-- include: review-sizing -->'
[ "$(printf '%s\n' "$MODEL" | grep -cxF "$BEGIN")" = 1 ] && [ "$(printf '%s\n' "$MODEL" | grep -cxF "$END")" = 1 ] ||
  fail "model-routing.md must hold the review-sizing begin and end comments exactly once each"
LB="$(printf '%s\n' "$MODEL" | grep -nxF "$BEGIN" | cut -d: -f1)"
LE="$(printf '%s\n' "$MODEL" | grep -nxF "$END" | cut -d: -f1)"
[ "$LB" -lt "$LE" ] || fail "model-routing.md has the review-sizing end comment before the begin comment"
[ "$((LE - LB))" -gt 1 ] || fail "the review-sizing span in model-routing.md is empty"
SIZING="$(printf '%s\n' "$MODEL" | sed -n "$((LB + 1)),$((LE - 1))p")"
[ -n "$SIZING" ] || fail "the review-sizing span in model-routing.md is empty"
[ "$(printf '%s\n' "$FRAME" | grep -cxF "$INC_COST")" = 1 ] && [ "$(printf '%s\n' "$FRAME" | grep -cxF "$INC_SIZING")" = 1 ] &&
  [ "$(printf '%s\n' "$FRAME" | grep -cF '<!--')" = 2 ] ||
  fail "economy-rules-file.md must hold each include marker alone on a line exactly once, and no other comment"
NEW="$(printf '%s\n' "$FRAME" | while IFS= read -r line; do
  case "$line" in
    "$INC_COST") printf '%s\n' "$COST" ;;
    "$INC_SIZING") printf '%s\n' "$SIZING" ;;
    *) printf '%s\n' "$line" ;;
  esac
done)"
TMP="$RULES_FILE.tmp"
mkdir -p "$ROOT/.claude/rules" || fail "cannot create $ROOT/.claude/rules"
printf '%s\n' "$NEW" > "$TMP" || { rm -f "$TMP"; fail "cannot write $TMP"; }
if [ ! -e "$RULES_FILE" ]; then
  mv -f "$TMP" "$RULES_FILE" || { rm -f "$TMP"; fail "cannot move the new text into place"; }
  echo ".claude/rules/cla-economy.md: created"
elif tr -d '\r' < "$RULES_FILE" | cmp -s - "$TMP"; then
  rm -f "$TMP"
  echo ".claude/rules/cla-economy.md: unchanged"
else
  mv -f "$TMP" "$RULES_FILE" || { rm -f "$TMP"; fail "cannot move the new text into place"; }
  echo ".claude/rules/cla-economy.md: replaced"
  echo "any local edits to .claude/rules/cla-economy.md were overwritten; the repo's own rules go in its own instruction files"
fi
```

## Part 2 — Facts

### Where a fact goes

- **`cla.io/project-facts.md` holds the repo's facts** — every command (install, dev, build, lint,
  test), path, port, workspace member, file map and env file the skills read. A skill looks there
  for them and nowhere else.
- **`cla.io/overlays/<skill>.md`, when present, holds only that skill's own rules** — a check, a
  limit or a preference for one skill in this repo — **with any path or command only that rule
  uses** (where codify-learnings finds memory, the files a review-change check opens). Optional; a
  skill without one runs on its generic procedure.
- **A dated incident's story goes to `cla.io/lessons-learned/`, and any rule it states stays in the
  overlay** as one or two lines, since most skills never read the lessons log. One that would
  happen in any repo goes upstream through `/cla:report-upstream`.
- **Machine-read `*.local.md` files stay where they are and are never reshaped here:**
  `cla.io/overlays/branch-prefix.local.md` (spec-to-pr's branch prefix),
  `cla.io/project-tokens.local.md` (the token guard's list) and `cla.io/fleet.local.md` (this
  machine's list of repos for `/cla:spec-to-pr-retro`).

`cla.io/project-facts.md` holds, under headed sections (omit one that does not apply; add one for any
other repo-wide fact you find):

- **Workspace shape** — the workspace member list (apps/packages/services and their one-line roles),
  derived from the repo's own workspace manifest (e.g. `pnpm-workspace.yaml` + each `package.json`
  name, a Cargo workspace's `Cargo.toml`, a Go module's `go.work`, or whatever this repo actually uses
  — read the real manifest, never assume a stack).
- **Dev / build / test commands** — the repo's dependency-install command, and its dev/build/lint/test
  invocations (from its root manifest's scripts/tasks), including any workspace-wide fan-out and any
  suite deliberately excluded from the default aggregate (and why, and what it needs to run).
- **Ports** — every fixed local-dev port tied to a specific process, and what runs on it.
- **Affected-file map** — the per-change-type file lists reviewers use to identify what a change of a
  given shape touches.
- **Doc-sweep paths** — the fixed list of docs outside `openspec/` that any change should keep in
  sync (root guidance doc, per-subapp guidance docs, README, docs tree). A change's docs task and
  the Review and Revise docs checks read it.
- **Cross-file lockstep doc sets** — any set of files that must be updated together whenever a specific
  piece of core logic changes.
- **Test-file locations** — unit/integration/e2e/smoke test locations, including any excluded from the
  default aggregate.
- **The i18n layers** (if the repo has translated user-facing text) — each layer's file paths and
  whether they are independent of one another.
- **Env files** — gitignored env files tied to a specific local process, and which var(s) they carry
  that matter to a caller (never the secret VALUES — only paths/names).
- **Infrastructure** — local services a gate needs (a database stack, a container engine), the
  command that reports whether they are up, and whether the dev environment is shared across branches.
- **Dataset / data locations** — any committed mock/reference dataset a core computation loads from.
- **Test proof granularity** (a repo with `openspec/` only) — whether its tests prove each
  requirement (the default) or each scenario. Ask the user once, with the default recommended, and
  write exactly one line under a `## Test proof` heading: `- Test proof granularity: requirement`
  or `- Test proof granularity: scenario`.
  `${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/check_spec_proof.py` reads that line and exits 2 on
  any other form, so never reword or merge it. A reconcile keeps an existing line as written.
- **Spec map** (a repo with `openspec/` only, and only if the user takes the offer in "The spec map
  scaffold") — the path or glob of the file that maps the repo's capabilities and workflows to its
  specs, one bullet per path under a `## Spec map` heading, any layout. `check_spec_proof.py` reads
  it and exits 2 on a heading with no bullet, a line that is not a bullet, or a heading that reads as this one in another form (`### Spec map`). Never write the
  heading when there is no map, and never invent a path: a reconcile keeps an existing section as
  written.
- **Worktree convention** — where this repo puts worktrees, if it has a rule.

**Keep it terse: one fact per line, under its `##` section.** Skills that cite a section read the
whole file, so every line is paid on each read. A list-valued fact (an affected-file map) stays a
list.

### The terminology file (`cla.io/terminology.md`)

What it holds and its entry format are in
`${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/terminology-format.md`. Other skills write it
inline as terms resolve; this skill never creates it and only reconciles it (item 11).

### The spec map scaffold

A repo with many specs can keep one file that bridges its levels: **capabilities** (what the product
offers), then the **workflows** that deliver them (a user's journey, as ordered steps), then the
**specs** each workflow step links. It holds links only: no configurable value and no restated rule.
This skill offers a default scaffold and never imposes one.

- **When to offer.** `openspec/specs/` exists and the facts file has no `## Spec map` section.
  Offer once per run, with the recommended path `openspec/spec-map.md`. The user may name any
  other path inside the repo, never under the plugin tree; a path that already exists is never overwritten, so ask for another.
- **On yes.** Write the scaffold below at the chosen path with `Write`, with one bullet under
  "Specs not yet placed" per spec under `openspec/specs/` and per spec an open change adds (each link to `openspec/specs/<name>/spec.md`, relative to the map's folder), and add the path
  under a `## Spec map` heading in the facts file. The map then passes `check_spec_proof.py` at
  once, and the user moves each spec into the workflow step it governs.
- **On no.** Write no map and no heading. Say that the checker then reports nothing about a map.
- **Declaring a map has a cost.** From then on `check_spec_proof.py` fails on a spec (live, or added by a change in progress) no map
  file links and on a link to a spec that does not exist. Say so when offering.

````markdown
# Spec map

Links only: a rule lives in its spec, a value in its config.

## Capabilities

- **<Capability, one line>.** Delivered by <workflow name>.

## Workflows

### <Workflow name>

1. <Step>: link the spec this step governs, moved from "Specs not yet placed".

## Specs not yet placed

- [<spec name>](<path to openspec/specs/<spec name>/spec.md, relative to this file>)
````

### 8. Read the repo

Read whatever this repo actually has — do not assume any particular stack. Typical sources: the
workspace manifest, the root package/build manifest and its scripts, lint/test config, per-member
manifests, dev-server configs for ports, `.env.example` files, the root guidance docs (every instruction file that
exists, `CLAUDE.md` and `AGENTS.md`; see `${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/instruction-files.md`)
and any per-subapp guidance docs, `README.md`, and `openspec/specs/**` if the repo uses
OpenSpec. This is deliberately an LLM read-and-reason pass, not a stack-specific parser — that is what
makes it portable.

### 9. Read the existing state

- `cla.io/project-facts.md`, if present (a **reconcile**, not a from-scratch write).
- Every `cla.io/overlays/*.md` except the `*.local.md` files (glob generically — never a hardcoded
  skill list). Sort each line into one of five kinds:
  - **fact** — a command, path, port, install step or env file (anything the list above covers),
    unless only a rule in this overlay uses it;
  - **rule** — what this one skill must do here, with any path or command only that rule uses;
  - **incident** — a dated story. Pull out every rule it states for this repo ("Rule here: …",
    "before trusting X, check Y", "always pass …") and sort that as a rule; the rest is story;
  - **duplicate** — a rule the plugin or the repo's instruction files (`CLAUDE.md`, `AGENTS.md`) already state (say where);
  - **scaffolding** — headings, HTML comments, and the old pointer that sent readers to the
    retired `sync-context` skill for repo-wide facts.

  When unsure whether a line is a rule, call it one: a rule moved to the log is lost to every skill
  that does not read it. In a repo that has not migrated yet, overlays may still sit at
  `${CLAUDE_PLUGIN_ROOT}/skills/*/references/project-context.md`; glob that too and say which you
  found.
- `cla.io/project-tokens.local.md`, if present, for the conformance guard's current token list.
- `cla.io/terminology.md`, if present — only for item 11.

### 10. Draft the changes

1. **The full proposed `cla.io/project-facts.md`.** Open with a heading and one line saying it is this
   repo's facts file, maintained by `/cla:cla-setup` and checked by
   `${CLAUDE_PLUGIN_ROOT}/skills/cla-setup/scripts/check_fact_paths.py`. Fold in every fact line
   item 9 found in an overlay, under its section.
2. **Each overlay's change.** Remove the facts just folded in; where a fact sits inside a sentence
   that also states a rule, rewrite the sentence to keep the rule and point at the facts file.
   Keep every rule as written, and each rule pulled out of an incident as one or two lines under
   a dated heading. Move the incident's story to `cla.io/lessons-learned/lessons-learned.md`,
   appended at the end under a heading naming the overlay it came from (the log is newest-first,
   and these predate it; then apply the log's 6,000-word rule from `codify-learnings` Step 5); name any that would happen in any repo as a candidate for
   `/cla:report-upstream`. Drop duplicates and scaffolding. An overlay left with no rule is
   proposed for **deletion**: an absent overlay and an empty one mean the same thing, and the
   empty one invites facts back in.
3. **Legacy-location overlays are never edited.** One at
   `${CLAUDE_PLUGIN_ROOT}/skills/*/references/project-context.md` sits in the read-only plugin
   cache, so an edit fails or is discarded by the next update. Record a one-line migration
   recommendation instead: its facts to `cla.io/project-facts.md`, its rules to
   `cla.io/overlays/<skill>.md`.
4. **Test proof granularity**, when `openspec/` exists and the facts file has no `## Test proof`
   line: draft `- Test proof granularity: requirement` under a `## Test proof` heading, unless the
   user chooses `scenario` at item 13.

### 11. Optionally reconcile `cla.io/terminology.md`

If the file exists, scan it for near-duplicate terms (two entries naming the same concept with
different words) or conflicting definitions (one term defined two ways), and draft a merge or reword
for each. Absent file or no issues: skip silently.

### 12. Propose new `project-tokens.local.md` entries

If item 8 surfaced a new, distinctive app/package/service name (or other compound repo-specific
token) not yet in `cla.io/project-tokens.local.md`, draft the addition — distinctive compound tokens
only, never generic words that legitimately appear in portable prose; grep the plugin tree for each
candidate before proposing it.

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

It MUST exit 0. Exit 1 names each stale path: fix every one and re-run. Exit 2 means it could not
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
