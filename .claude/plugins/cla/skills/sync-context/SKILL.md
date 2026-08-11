---
name: sync-context
description: "Populate or reconcile cla.io/project-facts.md — the repo-wide file of facts shared across cla skills (workspace members, dev/build/test commands, ports, the affected-file map, doc-sweep paths, test locations, i18n layers, env files). Reads the repo's own manifests directly via an LLM extractor (no stack-specific parser), so it works on any tech stack. Self-sufficient — creates cla.io/ and project-facts.md if missing, so it also covers fact-onboarding on a fresh repo (structure-only scaffolding is still /cla:cla-init's job). Proposes (never silently writes) new project-tokens.local.md entries for a new app/package name, and owns terminology.md's entry format. Triggers on /cla:sync-context or natural language like 'sync the project facts', 'refresh cla.io/project-facts.md', 'update the shared repo facts', 'the workspace member list is stale'."
argument-hint: "(no args — reads and reconciles the current repo)"
allowed-tools: Bash, Read, Grep, Glob, Write, Edit, AskUserQuestion
---

# /cla:sync-context — populate/reconcile the consolidated project-facts file

Read this repo's own manifests/config and populate or reconcile `cla.io/project-facts.md` — the single,
repo-level file holding every fact **shared across two or more `cla` skills** (per the plugin's
fact/procedure split and its shared-fact tie-break rule, below). This is the **content** half of
onboarding; `cla-init` supplies the **structure** (the `cla.io/` tree + empty per-skill overlay stubs)
and never populates facts; `update-cla` syncs the portable asset core and never touches project data.

## Composition boundary (read first)

**Onboarding order: `cla-init` (structure) → `/cla:sync-context` (content) → `update-cla` (portable core).**

- **`cla-init`** scaffolds the `cla.io/` tree (retro ledgers, feedback inbox, lessons-learned log,
  decisions dir) and empty `cla.io/overlays/<skill>.md` stubs for skills that consume one.
  It never writes real facts into any of them.
- **`/cla:sync-context` (this skill)** owns **fact content**: it populates/reconciles
  `cla.io/project-facts.md` (the shared repo-wide facts) and, where a per-skill overlay is missing its
  one-line pointer to `cla.io/project-facts.md`, adds that pointer line. It does **not** scaffold the
  `cla.io/` directory tree or empty overlay stubs (that stays `cla-init`'s job), and it does **not**
  write a skill's **skill-specific authored body** (that skill's own incident history, bespoke checks,
  permission-set intent) — that content stays human/LLM-authored independently of this skill (by hand,
  or via `/cla:codify-learnings`).
- **`update-cla`** syncs the plugin's portable asset core (`SKILL.md` bodies, agents, hooks) from a
  source repo and never creates or touches project data (`cla.io/`, any overlay).

This skill is **self-sufficient**: if `cla.io/` or `cla.io/project-facts.md` is absent, it creates them
— so running `/cla:sync-context` alone on a fresh repo (even one that skipped `cla-init`) acts as
fact-init, filling what `cla-init` otherwise leaves as empty structure. To be clear, "creates `cla.io/`"
means only the **bare top-level `cla.io/` directory** that `project-facts.md` lives in — never the
ledger/inbox subtree (`decisions/`, `feedback/`, `retro/`, `lessons-learned/`) or the empty per-skill
overlay stubs, which remain `cla-init`'s structure role (see Non-goals below). No contradiction: this
skill owns fact *content*, `cla-init` owns *structure*.

## Repo-root resolution

Resolve the repo root ONCE and read/write everything relative to it, so this works correctly regardless
of the working directory the skill is invoked from:

```bash
ROOT="$(git rev-parse --show-toplevel)"
```

If this errors (not inside a git working tree), stop and tell the user to run from within a git repo.

## The shared-fact tie-break rule (what belongs in `cla.io/project-facts.md`)

A fact goes into `cla.io/project-facts.md` when it **serves two or more `cla` skills, OR names a
repo-global command, port, workspace member, or path map**. A fact **stays** in a skill's own
`cla.io/overlays/<skill>.md` overlay when it is an example chosen to illustrate that skill's own
prose, or is that skill's own incident history, bespoke checks, or permission-set intent. When
reconciling, prefer leaving a borderline fact in its overlay over aggressively centralizing it — losing
skill-specific content is worse than a small amount of residual per-skill detail.

At minimum, `cla.io/project-facts.md` holds (organized under clear headed sections — omit any section
that genuinely doesn't apply to this repo, and add a section for any other repo-wide shared fact you
find that doesn't fit the categories below):

- **Workspace shape** — the workspace member list (apps/packages/services and their one-line roles),
  derived from the repo's own workspace manifest (e.g. `pnpm-workspace.yaml` + each `package.json`
  name, a Cargo workspace's `Cargo.toml`, a Go module's `go.work`, or whatever this repo actually uses
  — read the real manifest, never assume a stack).
- **Dev / build / test commands** — the repo's own dev/build/lint/test invocations (from its root
  manifest's scripts/tasks), including any workspace-wide fan-out mechanism and any suite deliberately
  excluded from the default aggregate (and why).
- **Ports** — every fixed local-dev port tied to a specific process, and what runs on it.
- **Affected-file map** — the per-change-type file lists reviewers use to identify what a change of a
  given shape touches (funnel/engine-shaped, backend-shaped, shared-package-shaped, etc. — whatever
  shapes this repo's own changes actually take).
- **Doc-sweep paths** — the fixed list of docs a change to application source should keep in sync
  (root guidance doc, per-subapp guidance docs, README, docs tree, spec tree).
- **Cross-file lockstep doc sets** — any set of files that must be updated together whenever a specific
  piece of core logic changes (e.g. this repo's own core formula/spec/doc trio, if it has one).
- **Test-file locations** — the repo's own unit/integration/e2e/smoke test file locations, including
  any that are deliberately excluded from the default test aggregate.
- **The i18n layers** (if the repo has translated user-facing text) — each layer's file paths and
  whether they're independent of one another.
- **Env files** — gitignored env files tied to a specific local process, and which var(s) they carry
  that matter to a caller (never the secret VALUES — only paths/names).
- **Dataset / data locations** — any committed mock/reference dataset a core computation loads from.
- **Repo conventions worth centralizing** — e.g. a fixed worktree directory convention — when you find
  the SAME convention restated verbatim across two or more overlays during reconciliation (see Step 3).

## The domain-terminology file (`cla.io/terminology.md`)

A second, distinct consolidated file — `cla.io/terminology.md` — holds canonical **internal
naming disambiguation**, not mechanical facts: one-sentence definitions for concepts specific to
this repo's own codebase or product, each naming any rejected alias terms to avoid. It is narrow
by design and never holds mechanical facts (that's `project-facts.md`'s job above) or external/
regulatory/business-reference knowledge (a repo's own hand-authored glossary of that kind, if one
exists, is untouched — this file neither reads nor supersedes it).

Entry format:

```
**Term**: one-sentence definition — what it IS, not what it does.
_Avoid_: rejected-alias-1, rejected-alias-2
```

**This skill owns the format above and the reconciliation logic below — it is NOT the exclusive
writer of the file's content.** Unlike `project-facts.md` (populated only by this skill, in a
batch pass), `cla.io/terminology.md` is written **inline**, in-session, by whichever consuming
skill resolves a term (`shape-decision` first; potentially others later) — the value of a
disambiguation is tied to the conversational moment it was resolved in, so capture cannot wait
for a later `/cla:sync-context` run. This skill's own role toward the file is limited to: (a)
documenting the format above for consuming skills to follow, and (b) an optional light
reconciliation pass (Step 5 below) that catches drift — nothing more.

The file is created **lazily** by whichever skill first needs it — never pre-scaffolded empty by
`cla-init`, and never treated as absent-means-broken: a pointer to it from another skill degrades
gracefully (use the file's canonical term if present and it covers the concept, otherwise proceed
using your own best judgement) rather than prompting a populate step the way the `project-facts.md`
pointer does.

## Workflow

### Step 1 — Read the repo's own manifests/config (LLM extraction, no stack-specific parser)

Read whatever this repo actually has — do not assume any particular stack. Typical sources (adapt to
what exists): the workspace manifest, the root package/build manifest and its scripts, lint/test config,
per-member manifests, `vite.config.*`/equivalent dev-server configs for ports, `.env.example` files,
the root guidance doc (e.g. `CLAUDE.md`) and any per-subapp guidance docs, `README.md`, and
`openspec/specs/**` if the repo uses OpenSpec. This is deliberately an LLM read-and-reason pass, not a
hardcoded parser — that's what makes this skill portable across differing tech stacks.

### Step 2 — Read the existing state

- `cla.io/project-facts.md`, if present (this is a **reconcile**, not a from-scratch write).
- Every `cla.io/overlays/*.md` (glob generically — don't hardcode a skill list) — note which facts
  each one currently restates that match the tie-break rule above, and whether it already carries the
  pointer sentence. In a repo that has not migrated yet, the overlays may still sit at
  `${CLAUDE_PLUGIN_ROOT}/skills/*/references/project-context.md`; glob both and say which you found.
- `cla.io/project-tokens.local.md`, if present, for the
  conformance guard's current curated token list.
- `cla.io/terminology.md`, if present — read only for the optional reconciliation pass in Step 5; this
  skill does not author its content from scratch (see "The domain-terminology file" above).

### Step 3 — Draft the reconciled `cla.io/project-facts.md`

Produce the full proposed file content, organized under headed sections per the categories above. Open
with a heading and a one-line note that this is the repo's consolidated, never-synced project-facts
file (lives in `cla.io/`, outside `update-cla`'s `SCAN_DIRS`), maintained by this skill and linted by
the staleness guard (`${CLAUDE_PLUGIN_ROOT}/conformance-checks/tests/test_project_facts_paths.py`).

While drafting, also look for a fact **restated verbatim (or near-verbatim) across two or more**
overlays that isn't in one of the categories above — that's a genuine tie-break hit found empirically
rather than by category; fold it in under a sensibly-named new section.

### Step 4 — Draft the overlay pointer additions (content only, never the skill-specific body)

**Overlays found at the LEGACY location are read-only — never edit one in place.** Step 2 deliberately
globs `${CLAUDE_PLUGIN_ROOT}/skills/*/references/project-context.md` so a repo mid-migration is still
inspected, but that path is inside the plugin, and in every repo that installed the plugin the tree is
a read-only cache: the edit fails, or lands somewhere the next update discards while reporting as
applied. Run the check in `${CLAUDE_PLUGIN_ROOT}/skills/codify-learnings/references/plugin-writability.md`
before drafting anything for such a file. Where it answers read-only, do not draft a pointer addition —
instead recommend, in the Step 6 report, that the overlay be **moved** to `cla.io/overlays/<skill>.md`,
which is repo content and writable. Only overlays already under `cla.io/overlays/` get pointer edits.

For each per-skill overlay that restates a fact you're centralizing and does NOT yet carry a pointer to
`cla.io/project-facts.md`, draft a **minimal, one-line pointer addition** using the graceful-degradation
wording: "For repo-wide facts (members, commands, ports, affected-file map, doc-sweep paths), see
`cla.io/project-facts.md` (run `/cla:sync-context` to populate it; falls back to this overlay if
absent)." Where the fact is embedded inside a skill-specific sentence rather than cleanly on its own
line, draft a rewritten sentence that points at `cla.io/project-facts.md` instead of deleting the
sentence outright (the not-line-separable case) — never leave the fact duplicated in both places once
the pointer exists. **Do not touch anything else in an overlay** — its skill-specific authored body
(incident history, bespoke checks, permission-set intent, illustrative examples) is out of scope for
this skill.

### Step 5 — Optionally reconcile `cla.io/terminology.md` (if present)

This skill does not author `cla.io/terminology.md` content from scratch — see "The domain-terminology
file" above. If the file exists, scan it for near-duplicate terms (two entries naming the same
underlying concept with different words) or internally conflicting definitions (the same term defined
two different ways, likely written by different sessions). Draft a proposed merge/reword fix for each
one found. Skip this step cleanly — no draft, nothing to report — if the file is absent or has no
issues; this is light maintenance, not a required pass.

### Step 6 — Propose new `project-tokens.local.md` entries (never silent)

If Step 1 surfaced a new, distinctive app/package/service name (or other compound repo-specific token)
that isn't yet in `cla.io/project-tokens.local.md`, draft the
candidate addition(s) — same curation discipline the conformance guard's token list requires (distinctive
compound tokens only, never generic words that legitimately appear in portable prose; verify each
candidate with a grep of the current synced core before proposing it).

### Step 7 — Present the proposal and get confirmation (interactive, not silent)

Show the user, in order:

1. Whether `cla.io/` and/or `cla.io/project-facts.md` were absent (fact-init) or present (reconcile).
2. The full drafted `cla.io/project-facts.md` content (or a diff against the existing file, if
   reconciling and the diff is small enough to read at a glance — use judgment; a from-scratch or
   heavily-changed file is clearer shown in full).
3. Each drafted overlay pointer addition, file by file.
4. Any proposed `project-tokens.local.md` additions, each with its one-line justification.
5. Any drafted `cla.io/terminology.md` reconciliation fixes from Step 5, if any were found.

Ask the user to confirm before writing anything (`AskUserQuestion` or a plain yes/no in conversation).
This skill never silently applies its draft — the same "propose, don't silently apply" discipline
`update-cla`'s adapt phase uses. On confirmation, write via `mkdir -p "$ROOT/cla.io"` (if needed) then
`Write`/`Edit` each confirmed file. If the user wants changes, revise the draft and re-confirm rather
than partially applying. **Every target must be repo content** — `cla.io/**` or a repo-level file.
If a confirmed target resolves inside the plugin tree, stop and report it as a migration
recommendation instead of writing it (Step 4).

### Step 8 — Report

Summarize what changed: `cla.io/project-facts.md` created vs updated (and which sections changed),
which overlays gained a pointer line, which `project-tokens.local.md` entries were added (or note none
were needed), and any `cla.io/terminology.md` reconciliation applied (or note none was needed/found).
If any candidate proposal was declined, say so and leave that file untouched.

## Non-goals (pinned — never do these)

- Does **NOT** scaffold the `cla.io/` directory tree of ledgers/inboxes, or create empty per-skill
  overlay stubs — that is `cla-init`'s role, unchanged by this skill.
- Does **NOT** write or edit a skill's **skill-specific authored body** (incident history, bespoke
  checks, permission-set intent, illustrative examples) — only the shared-fact content of
  `cla.io/project-facts.md` and the one-line pointer additions in overlays.
- Does **NOT** sync, adapt, or touch any asset-core file (`SKILL.md` bodies, agents, hooks) — that is
  `update-cla`'s job.
- Does **NOT** silently write anything — every change is proposed and confirmed first (Step 7).
- Does **NOT** parse any stack-specific config format with a hardcoded parser — it reads and reasons
  about whatever manifests/config this repo actually has (portability mechanism).
- Does **NOT** author `cla.io/terminology.md` content from scratch — that's written inline by whichever
  consuming skill resolves a term (see "The domain-terminology file" above); this skill only documents
  its format and optionally reconciles existing entries for drift/duplicates (Step 5).
