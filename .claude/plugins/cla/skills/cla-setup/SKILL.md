---
name: cla-setup
description: "Set up or refresh a repo for the cla plugin: create whatever is missing of cla.io/ without overwriting anything, seed OpenSpec authoring rules, and populate or reconcile cla.io/project-facts.md from the repo's own manifests. Changes existing files only on the user's yes. Run with /cla:cla-setup."
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
  the chains' run notes out of git. Creates only what is missing.
- **Part 2, facts** — read the repo's own manifests and write or reconcile `cla.io/project-facts.md`,
  the one home for every command, path, port, install step and env file the other skills read.
  Proposes first, writes only on the user's yes, then runs the staleness checker.

Run it once at onboarding (marketplace install → `/cla:cla-setup` → install the `pre-push` hook) and
again whenever a skill reports missing or stale facts. A re-run on a set-up repo changes nothing
without a yes. It replaces the former `cla-init` and `sync-context` skills, which no longer exist.

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
  seed file in Part 1, check existence FIRST; if present, skip it untouched (no truncate, no
  overwrite, no re-seed, no merge) and report `exists (skipped)`.
- **The guard is load-bearing.** A bare `> "$f"` or `cat > "$f"` truncates an existing file and defeats
  never-clobber. ALWAYS guard with `[ -e "$f" ] ||`. Pinned idioms:
  - directory → `mkdir -p "$dir"` (idempotent by construction)
  - 0-byte ledger → `[ -e "$f" ] || : > "$f"`
  - seed file with content → `[ -e "$f" ] || cat > "$f" <<'EOF'` … `EOF`
- **Create only what is missing.** A partly set-up repo ends fully set up with every pre-existing
  piece byte-for-byte unchanged: a `.jsonl` with history or a filled `notes.md` is ALWAYS skipped,
  even though the seed content differs.
- **A change to an existing file needs the user's yes, every time:** item 5's rules update, item 6's
  deletion of retired ledgers, item 7's untracking of tracked run notes, and Part 2's writes to
  `cla.io/` files. The one unasked edit is item 7's: it appends one line to `.gitignore` when no
  line there already ignores the run notes, and changes nothing else in it.
- **Overlays are optional, and this skill never creates one.** `cla.io/overlays/<skill>.md` holds a
  repo's skill-specific rules when it has some; a skill without one runs on its generic procedure
  and `cla.io/project-facts.md`.
- **Report `created` vs `exists (skipped)` per target**, so a re-run is transparently a no-op.

## Part 1 — Structure

All paths relative to `$ROOT`. Every item is create-if-absent per the contract above.

### 1. `cla.io/` directories

```bash
mkdir -p "$ROOT/cla.io/decisions" "$ROOT/cla.io/feedback" "$ROOT/cla.io/retro" "$ROOT/cla.io/lessons-learned"
```

`cla.io/decisions/` gets no seed file — an empty dir is the correct initial state (it holds ad-hoc
shaped-decision `.md` files created by `shape-decision`/`multi-spec`).

### 2. Retro ledger (0-byte — an empty file is a valid empty JSONL ledger; NO `[]` or placeholder line)

```bash
# The only ledger lib/log_run.py accepts, appended via that shared writer
# (which takes the ledger filename as its argument and refuses any other):
#   spec-to-pr-runs     read by /cla:spec-to-pr-retro
# Every other ledger was retired because nothing read it (item 6 lists them). If
# you add one, give it a shape in log_run.py and a reader in the same change: an
# unread ledger is exhaust, not data.
for f in spec-to-pr-runs; do
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

### 5. OpenSpec authoring rules — `openspec/config.yaml`

The one path outside `cla.io/` and `.gitignore` this skill writes, and it is still project data. OpenSpec injects a
config's `rules:` into every artifact's authoring instructions, so the block below is how OpenSpec's
own stock limits reach every CLA authoring run.

- `openspec/` exists and neither `openspec/config.yaml` nor `openspec/config.yml` does → seed
  `config.yaml` and report `created`.
- Either file exists → leave it **byte-identical** and compare: the script below lists, under its
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

```bash
: "${ROOT:?ROOT unset: set it with the repo-root step at the top of this skill first}"
CFG="$ROOT/openspec/config.yaml"
RULES="$(cat <<'EOF'
rules:
  proposal:
    - Keep it to one page. Point to the specs and design instead of restating them.
  design:
    - Write design.md only when a stock trigger applies (a cross-cutting change, a new dependency or data model, security, performance or migration complexity, or real ambiguity), and name the trigger.
    - "Keep it to one page: for each decision, the choice, one line of why, and one line per rejected alternative. No history or transcripts."
    - Never restate the proposal or the specs.
  specs:
    - "Specify only outcomes a user or owner would recognise, and interfaces others depend on: a CLI flag, a file or ledger format a consumer reads, an API contract. Leave implementation choices to the implementer; put a detail a reviewer must agree on, such as a security parameter or a data model, in design.md. Internal steps are not spec material."
    - "Write each requirement, ADDED or MODIFIED, as one sentence of 500 characters or fewer in plain words, with at most 3 scenarios. No history, reasons, measurements, coined terms, file paths or code names, unless the name is the interface. A spec holds at most 8 requirements; when one is full, add a new capability rather than a ninth."
    - "A MODIFIED block keeps every live scenario. To cut a live requirement's scenarios or bring it within these limits, list it under REMOVED and add the rewrite under ADDED with a new heading. This overrides OpenSpec's instruction to keep an existing requirement whole."
    - "A change with no externally visible behaviour change (a refactor, tooling, docs, or a rule about how a skill file is worded) sets `skip_specs: true` in its .openspec.yaml and writes no spec delta. Never invent a requirement to satisfy validation."
    - Read existing specs cheaply first (`openspec list --specs`, then `openspec show <id> --type spec --json --no-scenarios`), and read in full only the specs this change touches.
  tasks:
    - "Give each requirement this change adds or modifies a test task whose test carries a `requirement: <spec> / <heading>` comment line above it, or a line `manual: <heading>: <reason>`. Scenarios are examples, not one test each."
    - "Cite headings, not line numbers. A `measured:` note gives the value; the command that produced it goes in the commit message."
EOF
)"
# Earlier wordings of shipped rules: the only lines the update may remove.
RETIRED="$(cat <<'EOF'
rules:
  specs:
    - State one behaviour per ADDED requirement in 500 characters or fewer, and put the detail in scenarios.
    - "State behaviour only, in plain words: one behaviour per ADDED requirement in 500 characters or fewer, with the detail in scenarios. No history, reasons, measurements or coined terms."
    - "A change with no externally visible behaviour change (a refactor, tooling, docs) sets `skip_specs: true` in its .openspec.yaml and writes no spec delta. Never invent a requirement to satisfy validation."
    - "Keep every scenario heading unique within its spec, so `<spec> / <heading>` names exactly one scenario."
  tasks:
    - "Give each ADDED or MODIFIED scenario a test task, or a `manual: <reason>` note."
    - "Give each scenario this change adds, or whose text it changes, a test task or a `manual: <reason>` note. A scenario carried forward unchanged in a MODIFIED block needs neither."
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
elif [ ! -d "$ROOT/openspec" ]; then
  echo "openspec/config.yaml: not written, no openspec/ (run openspec init, then add this block):"
  printf '%s\n' "$RULES"
else
  OLD="$CFG"; [ -e "$OLD" ] || OLD="$ROOT/openspec/config.yml"
  HAVE="$(tr -d '\r' < "$OLD" | sed 's/^[[:space:]]*//')"
  # $1 block, $2 mark, $3 = 1 lists the block's lines the file has, 0 those it lacks.
  rule_lines() {
    printf '%s\n' "$1" | while IFS= read -r line; do
      case "$line" in
        "  "[a-z]*:) KEY="${line#  }" ;;
        "    - "*) HAS=0; printf '%s\n' "$HAVE" | grep -Fxq -- "${line#    }" && HAS=1
          [ "$HAS" = "$3" ] && printf '%s %s %s\n' "$2" "$KEY" "${line#    }" ;;
      esac
    done
  }
  DIFF="$(rule_lines "$RULES" + 0; rule_lines "$RETIRED" - 1)"
  if [ -z "$DIFF" ]; then
    echo "openspec/${OLD##*/}: exists (skipped), rules current"
  else
    echo "openspec/${OLD##*/}: exists (skipped), missing or outdated rules (+ add, - remove):"
    printf '%s\n' "$DIFF"
  fi
fi
```

Each item that contains `: ` stays double-quoted, or YAML reads it as a mapping and OpenSpec drops
that artifact's rules.

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
commits, and refuse to start while git would see them. This adds the ignore line unless git already
ignores the notes (any equivalent pattern, CRLF or trailing spaces included), creating the file if
needed. The check ignores this machine's global excludes file (`core.excludesFile`): a pattern there
hides the notes here but not in any other clone, so it does not count as the repo's line.

```bash
: "${ROOT:?ROOT unset: set it with the repo-root step at the top of this skill first}"
line='cla.io/retro/*-run-notes-*.md'
probe='cla.io/retro/multi-lite-run-notes-x.md'
if git -C "$ROOT" -c core.excludesFile=/dev/null check-ignore -q --no-index "$probe"; then
  echo "exists (skipped): .gitignore run-notes line"
elif match="$(git -C "$ROOT" -c core.excludesFile=/dev/null check-ignore -v --no-index "$probe")"; then
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


## Part 2 — Facts

### Where a fact goes

- **`cla.io/project-facts.md` is the only home for a fact** — every command (install, dev, build,
  lint, test), path, port, workspace member, file map and env file a skill reads. A skill looks
  there and nowhere else, so a fact kept anywhere else is a fact no skill finds.
- **`cla.io/overlays/<skill>.md`, when present, holds only that skill's own rules** — a check, a
  limit or a preference that applies to one skill in this repo. Optional; a skill without one runs
  on its generic procedure.
- **A dated incident goes to `cla.io/lessons-learned/`**, where `/cla:codify-learnings` searches for
  re-offenses. One that would happen in any repo goes upstream through `/cla:report-upstream`.
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
- **Doc-sweep paths** — the fixed list of docs a change to application source should keep in sync
  (root guidance doc, per-subapp guidance docs, README, docs tree, spec tree).
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
- **Worktree convention** — where this repo puts worktrees, if it has a rule.

**Keep it terse: one fact per line, under its `##` section.** Skills that cite a section read the
whole file, so every line is paid on each read. A list-valued fact (an affected-file map) stays a
list.

### The terminology file (`cla.io/terminology.md`)

A second, distinct file — `cla.io/terminology.md` — holds canonical **internal naming
disambiguation**, not mechanical facts: one-sentence definitions for concepts specific to this repo's
own codebase or product, each naming any rejected alias terms to avoid. It never holds mechanical
facts (that is `project-facts.md`'s job) or external/regulatory/business-reference knowledge (a repo's
own glossary of that kind, if one exists, is untouched).

Entry format:

```
**Term**: one-sentence definition — what it IS, not what it does.
_Avoid_: rejected-alias-1, rejected-alias-2
```

**This skill owns the format above and the light reconciliation in item 11 — not the file's
content.** The file is written **inline**, in-session, by whichever skill resolves a term
(`shape-decision` first), because a disambiguation belongs to the moment it was resolved. It is
created **lazily** by the first skill that needs it — never pre-scaffolded here — and its absence is
never an error: a skill reading it uses the file's term when present and its own judgement otherwise.

### 8. Read the repo

Read whatever this repo actually has — do not assume any particular stack. Typical sources: the
workspace manifest, the root package/build manifest and its scripts, lint/test config, per-member
manifests, dev-server configs for ports, `.env.example` files, the root guidance doc (e.g.
`CLAUDE.md`) and any per-subapp guidance docs, `README.md`, and `openspec/specs/**` if the repo uses
OpenSpec. This is deliberately an LLM read-and-reason pass, not a stack-specific parser — that is what
makes it portable.

### 9. Read the existing state

- `cla.io/project-facts.md`, if present (a **reconcile**, not a from-scratch write).
- Every `cla.io/overlays/*.md` except the `*.local.md` files (glob generically — never a hardcoded
  skill list). Sort each line into one of four kinds: a **fact** (a command, path, port, install
  step, env file — anything the list above covers), a **skill-specific rule**, a **dated incident**,
  or **template scaffolding** (headings and HTML comments only, no content). In a repo that has not
  migrated yet, overlays may still sit at
  `${CLAUDE_PLUGIN_ROOT}/skills/*/references/project-context.md`; glob that too and say which you
  found.
- `cla.io/project-tokens.local.md`, if present, for the conformance guard's current token list.
- `cla.io/terminology.md`, if present — only for item 11.

### 10. Draft the changes

1. **The full proposed `cla.io/project-facts.md`.** Open with a heading and one line saying it is this
   repo's facts file, maintained by `/cla:cla-setup` and checked by
   `${CLAUDE_PLUGIN_ROOT}/skills/cla-setup/scripts/check_fact_paths.py`. Fold in every fact line
   item 9 found in an overlay, under its section.
2. **Each overlay's change.** Remove the fact lines just folded in; where a fact sits inside a
   sentence that also states a rule, rewrite the sentence to keep the rule and point at the facts
   file rather than deleting it. Move each dated incident to
   `cla.io/lessons-learned/lessons-learned.md`, appended at the end under a heading naming the
   overlay it came from (the log is newest-first, and these predate it); name any that would happen
   in any repo as a candidate for `/cla:report-upstream`. Keep the skill-specific rules as written.
   An overlay left with nothing but headings and comments — including one that never had more —
   is proposed for **deletion**: an absent overlay and an empty one mean the same thing, and the
   empty one invites facts back in.
3. **Legacy-location overlays are never edited.** One at
   `${CLAUDE_PLUGIN_ROOT}/skills/*/references/project-context.md` sits in the read-only plugin
   cache, so an edit fails or is discarded by the next update. Record a one-line migration
   recommendation instead: its facts to `cla.io/project-facts.md`, its rules to
   `cla.io/overlays/<skill>.md`.

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
3. Each overlay change from item 10, file by file: lines moved to the facts file, incidents moved to
   the lessons log, files proposed for deletion.
4. Migration recommendations for legacy-location overlays.
5. Proposed `project-tokens.local.md` additions, each with its one-line justification.
6. Any `cla.io/terminology.md` reconciliation from item 11.

Ask for a yes (`AskUserQuestion` or a plain yes/no) before writing anything; on a request for
changes, revise and ask again rather than applying part of it. On yes, write each confirmed file
with `Write`/`Edit` and delete each confirmed overlay with `rm --`. **Every target must be repo
content** — `cla.io/**`. A target that resolves inside the plugin tree is reported as a migration
recommendation, never written. A declined proposal leaves its file untouched.

**Then run the staleness checker against what was just written:**

```
python3 ${CLAUDE_PLUGIN_ROOT}/skills/cla-setup/scripts/check_fact_paths.py
```

It MUST exit 0, and the two non-zero codes mean different things — do not collapse them, because the
remedy differs and only one of them names a path to fix:

| Exit | Meaning | What to do |
|---|---|---|
| `0` | No stale path. | Done. |
| `1` | Stale paths found, each named with its file and line. | The write just made introduced or left them. Fix every path the checker names and re-run until it exits 0. |
| `2` | The checker could not look — an unresolvable repo root, an unreadable input, or a scan that extracted nothing. | **No path is named, so there is nothing to "fix" by editing the facts file.** Read the stderr reason and resolve *that* (pass `--repo-root`, fix the unreadable file). Never treat a 2 as a clean pass, and never re-run hoping for a 1. |

**Beyond this one run, the repo owns when the checker runs.** An installed plugin is a read-only
cache with no test gate over it, and nothing in the plugin schedules this script. If the repo wants
the check standing, it wires the command above into its own gate (test command, pre-commit hook, CI
step) and reads the exit code by the table above. A gate that still wires the plugin's old
`conformance-checks/tests` directory (the `0.x`-era shape, gone since `1.0.0`) either fails on a
missing directory or passes while checking nothing: say so in the report and recommend this program
instead.

## Report

One summary at the end:

- **Part 1:** each directory, ledger and seed file as `created` or `exists (skipped)`. For
  `openspec/config.yaml`: `created`, `rules current`, the `+`/`-` lines and whether the user agreed,
  or `not written` followed by the `rules:` block to paste; add the OpenSpec version line when it is
  older than 1.14.1. Each retired ledger `deleted` or `kept`, or that none is present. The run-notes
  line `created`, `exists (skipped)` or `un-ignored`, and each tracked notes file `untracked` or
  `kept tracked`, or that none is tracked.
- **Part 2:** `cla.io/project-facts.md` created or updated (which sections changed); each overlay
  trimmed or deleted and where its lines went; `project-tokens.local.md` entries added (or none);
  terminology fixes applied (or none); every declined proposal, named.
- **The staleness checker's exit code.** Not 0 → name every stale path it reported; this run is the
  only place that check happens, so a report that omits it loses it.
- **Every legacy-location migration recommendation** — the only findings this skill deliberately
  does not act on.

## Non-goals

- Does **NOT** create, read, or modify `.claude-plugin/plugin.json` or `.claude/settings*.json` —
  per-repo manual onboarding steps.
- Does **NOT** touch any plugin file (a `SKILL.md`, an agent, a hook). The plugin tree is a read-only
  cache.
- Does **NOT** create overlays, and never writes a fact into one.
- Does **NOT** write anything in Part 2 without the user's yes.
- Does **NOT** parse a stack-specific config format with a hardcoded parser — it reads and reasons
  about whatever this repo actually has.
- Does **NOT** author `cla.io/terminology.md` entries — only the format and item 11's reconciliation.
