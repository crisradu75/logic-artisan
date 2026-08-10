# cla-plugin Specification

## Purpose

Specifies the architecture of the `cla` Claude Code plugin — the portable dev-workflow harness this
repo canonically hosts and distributes to other repos via `update-cla`. Covers: the core/state
boundary and in-place activation; the repo-state resolution seam every plugin script must use;
the repo-neutral project-context overlay convention; the cross-repo sync mechanism (discover →
3-way reconcile → apply, with a provenance lockfile and source-side deletion detection); the
fact/procedure separation every skill must observe and the mechanical guards that enforce it
(conformance guard, project-facts staleness guard); the project-data scaffolding (`cla-init`) and
context-refresh (`sync-context`) skills that populate a destination repo's `cla.io/` tree; and the
skill-authoring disciplines (progressive disclosure, thin-orchestrator execution) that keep the
synced core lean. This is the spec for the harness's own architecture, not for any downstream
consumer's project — a consuming repo's own facts live behind the overlays this spec defines, never
in this file.

## Requirements

### Requirement: Core/state boundary

The reusable dev-workflow harness core SHALL live in an in-repo plugin at `.claude/plugins/cla/` (manifest `.claude/plugins/cla/.claude-plugin/plugin.json` with name `cla`), containing only stateless, portable assets: `skills/`, `agents/`, and `hooks/`. Repo-local, machine-local, or external assets MUST NOT be moved into the plugin and SHALL remain project-level in one of two homes:

1. **The cla plugin's durable workflow *data* SHALL live under a single top-level `cla.io/` directory** — the retro ledgers (`cla.io/retro/*.jsonl`), the lessons-learned log (`cla.io/lessons-learned/`), shaped decisions (`cla.io/decisions/`), and captured feedback notes (`cla.io/feedback/`). This data is tool-neutral, first-class repo content and is deliberately NOT buried in the `.claude/` harness-config dotfolder.
2. **Claude Code harness config and other project-level assets SHALL remain under `.claude/`** — `worktrees/`, `settings.json` (project-specific hook wiring + env), `settings.local.json` (permissions), and any other host-repo-specific commands/skills/assets a destination repo layers on top of the plugin.

#### Scenario: Core assets are in the plugin, state stays project-level

- **WHEN** the repo is inspected
- **THEN** the harness skills, agents, and guard hooks resolve from `.claude/plugins/cla/`
- **AND** the cla workflow data (`cla.io/retro/*.jsonl`, `cla.io/lessons-learned/`, `cla.io/decisions/`, `cla.io/feedback/`) lives under the top-level `cla.io/` directory
- **AND** `.claude/worktrees/`, `.claude/settings*.json`, and any other host-repo-specific project-level assets remain under `.claude/`, and none of the above is present inside `.claude/plugins/cla/`

### Requirement: In-place activation and namespacing

The `cla` plugin SHALL be activated in place via `claude --plugin-dir ./.claude/plugins/cla` (not a cached marketplace install), so its scripts run from the repo and can read/write repo-local state. Each workflow SHALL be a skill (no thin command wrappers) and SHALL be invoked under the plugin namespace as `/cla:<skill>`.

#### Scenario: Skills resolve under the cla namespace

- **WHEN** a session is launched with `--plugin-dir ./.claude/plugins/cla`
- **THEN** each harness workflow is invocable as `/cla:<skill>` (e.g. `/cla:spec-to-pr`, `/cla:project-review`, `/cla:shape-decision`)
- **AND** no bare `.claude/commands/*.md` wrapper exists for any cla skill

#### Scenario: Internal composition uses the namespace

- **WHEN** one skill invokes another (e.g. `multi-pr` runs `spec-to-pr`, `spec-to-pr` reads `review-change`)
- **THEN** the invocation uses the `cla:`-namespaced form (`Skill(cla:<name>)`) and resolves within the plugin

### Requirement: Repo-state resolution seam

Plugin scripts SHALL resolve repo locations independently of their own position in the tree, because the plugin's nested position under `.claude/plugins/cla/…` breaks any position-dependent resolver. Specifically: (a) scripts that read/write the retro dir (the shared writer `lib/log_run.py` and each retro loop's `aggregate.py`) SHALL resolve it as `CLAUDE_RETRO_DIR` when set, otherwise `<git rev-parse --show-toplevel>/cla.io/retro`; (b) scripts that resolve a repo root for other repo files (`probe_state.py` via `_git_common.py`) SHALL resolve it via `git rev-parse --show-toplevel`, NOT a fixed `Path(__file__).resolve().parents[N]` depth. Scripts MUST NOT rely on walking to a `.claude` ancestor of the script nor on `${CLAUDE_PROJECT_DIR}` (empty in the script environment). A skill-bundled file (e.g. `references/branch-prefix.local.md`) SHALL be resolved skill-relative to the script, while a project-level target SHALL be resolved from the repo root.

#### Scenario: A plugin script writes to the repo's retro dir

- **WHEN** a retro/state script runs from `.claude/plugins/cla/…` with `CLAUDE_RETRO_DIR` unset
- **THEN** it resolves the repo root via `git rev-parse --show-toplevel` and writes under that repo's `cla.io/retro/`

#### Scenario: Override is honored

- **WHEN** `CLAUDE_RETRO_DIR` is set to an absolute path
- **THEN** the script uses it directly and does not consult git

#### Scenario: A repo-root script resolves independently of depth

- **WHEN** a repo-root-consuming script (e.g. `probe_state.py`) runs from `.claude/plugins/cla/skills/spec-to-pr/scripts/`
- **THEN** it finds the repo root via `git rev-parse --show-toplevel` (not `parents[N]`)
- **AND** it reads its skill-bundled `references/branch-prefix.local.md` skill-relative while still resolving repo files at the repo root

### Requirement: Project-specific overlay convention

Project-specific content (repo-tuned review checks, monorepo-shaped agent prompts, repo paths) SHALL be contained in **repo-neutral overlay files** whose leaf filename is either exactly `project-context.md` (the canonical single per-skill overlay) or matches the glob `*.local.md` (additional per-skill local overlay files), co-located in the consuming skill's `references/` directory (e.g. `.claude/plugins/cla/skills/review-change/references/project-context.md`). The overlay marker SHALL NOT embed the name of any repository; a generic skill body SHALL remain repo-agnostic and reference its overlay by the fixed repo-neutral path `references/project-context.md`. Each destination repo fills in its own overlay content behind that fixed filename. The overlay marker SHALL be recognized by convention on the **leaf filename** (not on intermediate path components), so a directory that merely contains an overlay stays syncable.

**Exception for repo-wide shared facts.** A fact that is *shared across multiple skills* (a repo-wide command, port, member list, path map, or doc list) MAY instead live once in the repo-level consolidated project-facts file `cla.io/project-facts.md` (per the **Consolidated project-facts file** requirement), rather than being co-located and restated in each consuming skill's `references/`. This is the sole exception to co-location, and it applies ONLY to that single repo-level shared file — per-skill overlays themselves remain co-located under the skill's `references/`. A per-skill overlay references such a shared fact by a pointer to `cla.io/project-facts.md`.

#### Scenario: Repo checks live in a repo-neutral overlay

- **WHEN** `review-change` or `project-review` runs
- **THEN** its generic body reads its repo-specific checks from a co-located `references/project-context.md` overlay file

#### Scenario: A generic skill references its overlay without naming the repo

- **WHEN** a generic `SKILL.md` (or a reference it reads, e.g. `checklist.md`) points at its project overlay
- **THEN** the reference is the fixed repo-neutral path `references/project-context.md`
- **AND** no hardcoded repository-name prefix appears in that reference

#### Scenario: A skill carries multiple local overlay files

- **WHEN** a skill needs more than one project-local overlay file alongside `project-context.md`
- **THEN** each additional file is named with a `*.local.md` leaf suffix
- **AND** every such file is recognized as project-local overlay by the same convention

#### Scenario: A repo-wide shared fact lives in the consolidated file, not each overlay

- **WHEN** a fact is shared across multiple skills (e.g. a repo-wide command, port, member list, or the doc-sweep path list)
- **THEN** it lives once in `cla.io/project-facts.md` rather than co-located and restated in each skill's `references/`
- **AND** a per-skill overlay that needs it carries a pointer to `cla.io/project-facts.md`, while per-skill overlays otherwise remain co-located under `references/`

### Requirement: Cross-repo update preserves the overlay

The `update-cla` skill SHALL update a repo's `.claude/plugins/cla/` from a canonical `cla` source repo while preserving every project-local overlay file — any file under `.claude/plugins/cla/` whose leaf filename is exactly `project-context.md` or matches the glob `*.local.md`. This preserve rule SHALL be enforced by `discover.py`'s `_is_excluded` (matching on the leaf filename, so overlay files never appear in `divergences.json` and are never overwritten) and documented in `update-cla`'s SKILL.md. The rule SHALL be defined by convention, not by any repo name.

#### Scenario: Overlay survives an update

- **WHEN** `update-cla` syncs newer core into `.claude/plugins/cla/`
- **THEN** every `project-context.md` overlay file and every `*.local.md` overlay file is left unmodified
- **AND** only non-overlay core assets are updated

#### Scenario: discover.py excludes overlays by the neutral convention

- **WHEN** `discover.py` walks the source tree and evaluates a file
- **THEN** a file whose leaf name is `project-context.md` or ends with `.local.md` is excluded from the sync candidates (never surfaced as `divergent` or `new`)
- **AND** the exclusion decision does not depend on any repository-name prefix

### Requirement: Guard hooks provided by the plugin

The generic git/worktree guard hooks SHALL be provided by the plugin via `.claude/plugins/cla/hooks/hooks.json`, which MUST use the top-level `{"hooks": {…}}` wrapper (a bare `{"<Event>": …}` shape loads without error but never fires). Hook commands SHALL locate their script via `${CLAUDE_PLUGIN_ROOT}` and the repo via `${CLAUDE_PROJECT_DIR}`. Any project-level hooks specific to the host repo (outside the plugin's generic guard set) SHALL remain wired in that repo's own `.claude/settings.json`, out of the plugin.

#### Scenario: A plugin guard hook fires

- **WHEN** a session with `--plugin-dir ./.claude/plugins/cla` triggers a matched tool call
- **THEN** the corresponding guard hook executes (verifiable via `/hooks` showing Source: Plugin)
- **AND** the hook resolves its script through `${CLAUDE_PLUGIN_ROOT}` and the repo through `${CLAUDE_PROJECT_DIR}`

#### Scenario: Wrapper shape is enforced

- **WHEN** `.claude/plugins/cla/hooks/hooks.json` is authored
- **THEN** its top level is a `"hooks"` object keyed by event name, not a bare event map

### Requirement: Sync provenance lockfile

`update-cla` SHALL maintain a per-repo sync provenance lockfile at `.claude/plugins/cla/.cla-sync-lock.json` in each destination repo. The lockfile SHALL be a JSON object keyed by the relative asset path (the same posix `asset_path` string `discover.py`/`apply.py` use), each value an object carrying `last_synced_sha256` (the sha256 of the adapted content actually WRITTEN to the local file at apply time — the exact bytes now on disk, which is the ancestor the next reconcile's local-side comparison returns to, NOT the raw source content's hash), `source_sha256` (the sha256 of the RAW SOURCE content those bytes were adapted from — the baseline the source-side comparison returns to), and `source` (the source repo's short name). Both hashes SHALL be recorded: either alone collapses the two comparisons onto one baseline and makes one of the four classification labels unreachable. The lockfile SHALL be written/updated inside `apply.py`'s write path (both `apply_worktree` and `apply_pr`), at the point the adapted content is written, with exactly one entry written or updated per file whose apply outcome is `wrote`; a file with any other outcome (`skipped_dirty_worktree`, `skipped_binary`, `skipped_malformed`, `failure`) SHALL leave its prior lock entry unchanged. A file whose outcome is `skipped_kept_local` SHALL update its entry: `keep_local` set to `true`, `last_synced_sha256` re-hashed from the local file on disk, and `source_sha256` advanced to the raw source the decision was made against — so the decision, and the source it was made against, survive the session. A subsequent `wrote` outcome for the same asset SHALL clear `keep_local`. `discover.py` SHALL surface a recorded `keep_local` as `kept_local_previously` on that asset's file record. In `pr` mode the lockfile SHALL be written before the sync commit (`git add -A`) so it is committed in the same PR as the applied files; in `worktree` mode it is written into the working tree alongside them. Provenance SHALL live only in the lockfile — asset frontmatter SHALL NOT be polluted and stays `name`/`description`/`allowed-tools`/`argument-hint`. A failure to write the lockfile SHALL be reported to stderr but SHALL NOT fail an apply run whose files already landed. The lockfile itself SHALL be excluded from the sync scan (it is per-repo provenance, never a synced asset) — it is a dotfile and lives outside `SCAN_DIRS`, so it never appears in `divergences.json`.

#### Scenario: Apply records provenance for each written file

- **WHEN** `apply` writes a file with outcome `wrote`
- **THEN** `.claude/plugins/cla/.cla-sync-lock.json` gains or updates that asset's entry with `last_synced_sha256` set to the sha256 of the adapted content written to that file (the exact bytes on disk) and `source` set to the source repo's short name
- **AND** a file whose outcome was `skipped_dirty_worktree`, `skipped_binary`, `skipped_malformed`, or `failure` keeps its prior lock entry unchanged

#### Scenario: Apply refuses content bearing the doubled-newline corruption fingerprint

- **WHEN** `apply` is about to write a file whose `adapted_content` (after CRLF/CR-to-LF normalization) has a newline count roughly 2x its non-empty line count
- **THEN** the file is NOT written, its outcome is `skipped_malformed`, and its prior lock entry (if any) is left unchanged
- **AND** `adapted_content` is otherwise normalized to LF line endings before being written, regardless of whether it also triggers this refusal

#### Scenario: In pr mode the lockfile is committed in the same PR

- **WHEN** `apply` runs in `pr` mode and writes at least one file with outcome `wrote`
- **THEN** `.claude/plugins/cla/.cla-sync-lock.json` is written before the sync commit and is included in the same commit/PR as the applied files (not left uncommitted on the pushed branch)

#### Scenario: The lockfile is never a sync candidate

- **WHEN** `discover.py` walks the tree
- **THEN** `.claude/plugins/cla/.cla-sync-lock.json` never appears in `divergences.json` as `divergent`, `new`, or any 3-way status
- **AND** it is excluded both as a dotfile and by living outside `SCAN_DIRS`

#### Scenario: Provenance does not touch frontmatter

- **WHEN** an asset with YAML frontmatter is synced
- **THEN** its frontmatter fields remain `name`/`description`/`allowed-tools`/`argument-hint` with no version/provenance key added
- **AND** the provenance for that asset lives only in `.cla-sync-lock.json`

### Requirement: Three-way reconcile classification

`discover.py` SHALL classify a divergence against TWO recorded ancestors rather than one: `last_synced_sha256` (the adapted bytes last written to local) and `source_sha256` (the raw source those bytes were adapted from). Each side SHALL be compared against its own baseline: `local_moved` is `local_sha256 != last_synced_sha256`, and `source_moved` is `source_sha256(current) != source_sha256(recorded)`. When there is no lock entry for an asset, the classification SHALL fall back to today's 2-way `divergent`. When neither side moved, the status SHALL be `adapted` — local and source differ only because the adoption was adapted, and there is nothing upstream to pull. When only source moved, the status SHALL be `source-advanced`. When only local moved, the status SHALL be `local-advanced`. When both moved, the status SHALL be `both-diverged`. An identical file (`source_sha256 == local_sha256`) SHALL be dropped silently as today and never reach classification.

`local-advanced` SHALL be reachable for an adapted file. Recording only the adapted ancestor made that label require a verbatim adoption, so a deliberate divergence could never receive it, while a fix introduced during the adapt phase landed inside the ancestor bytes and reported `source-advanced` — the label whose Phase-2 guidance is to adopt source. Two consuming repos reported the resulting silent revert independently.

A lock entry lacking `source_sha256` (or carrying a non-string value) SHALL default it to `last_synced_sha256`, which collapses the four-way table to exactly the three labels the single-ancestor rules produced, and SHALL make `adapted` unreachable for such an entry. A missing `source_sha256` SHALL NOT be treated as a conflict.

The classification SHALL be a label that guides Phase-2 adaptation; it SHALL NOT auto-merge content — `apply.py` treats every to-write file identically regardless of label.

#### Scenario: Neither side moved since the sync

- **WHEN** an asset's local sha equals `last_synced_sha256` and its source sha equals the recorded `source_sha256`
- **THEN** `discover.py` classifies it `adapted` (the two differ only because the adoption was adapted; nothing upstream to pull)

#### Scenario: Source advanced, local untouched

- **WHEN** an asset's local sha equals `last_synced_sha256` and its source sha differs from the recorded `source_sha256`
- **THEN** `discover.py` classifies it `source-advanced`

#### Scenario: Local advanced, source untouched

- **WHEN** an asset's source sha equals the recorded `source_sha256` and its local sha differs from `last_synced_sha256`
- **THEN** `discover.py` classifies it `local-advanced`
- **AND** this holds whether the asset was adopted verbatim or adapted

#### Scenario: Both sides diverged

- **WHEN** an asset's source and local shas both differ from the lock ancestor and from each other
- **THEN** `discover.py` classifies it `both-diverged`

#### Scenario: No lock entry falls back to 2-way

- **WHEN** an asset differs between source and local but has no lockfile entry
- **THEN** `discover.py` classifies it `divergent` (today's 2-way behavior), consulting no ancestor

#### Scenario: A legacy lock entry without source_sha256 keeps the previous labels

- **WHEN** an asset's lock entry was written before `source_sha256` existed, or carries a non-string value for it
- **THEN** `discover.py` defaults that baseline to `last_synced_sha256`
- **AND** produces exactly the label the single-ancestor rules produced, never `adapted`

### Requirement: Source-side deletion detection

`discover.py` SHALL walk the local `SCAN_DIRS` tree (applying BOTH the same `_is_excluded` overlay filter AND the same `_matches_filter` asset-path filter as the source walk) and detect source-side deletions, disambiguated by the lockfile. Because the local deletion walk applies the run's `filter_pattern` exactly as the source walk does, a scoped run (e.g. `discover <source> skills/foo/`) SHALL consider only lock-tracked assets within that scope, and SHALL NEVER surface an out-of-scope lock-tracked asset as a false `deleted-in-source`. A local asset (in scope) that is present in the lockfile (previously synced) but absent from the current source SHALL be surfaced as a deletion record with status `deleted-in-source`, carrying `asset_path`, `local_sha256`, and the lock's `last_synced_sha256` and `source`. A local asset with no lockfile entry SHALL be left alone (it is overlay or genuinely local content the source never had). A never-synced overlay file (leaf filename exactly `project-context.md` or ending `.local.md`, per the overlay-convention exclusion rule) SHALL NEVER be flagged as a deletion — it is `_is_excluded`, so it never enters the lockfile nor the local-tree walk. `update-cla` SHALL NEVER auto-delete a file: deletions SHALL be recorded in `divergences.json` (in a dedicated `deletions` array, distinct from `files`) and surfaced in the discover summary for manual review only. A rename SHALL surface as a `deleted-in-source` record for the old path plus a `new` record for the new path, which the Phase-2 LLM recognizes as a pair.

#### Scenario: A previously synced asset removed from source is surfaced

- **WHEN** a local asset is present in the lockfile but absent from the current source tree
- **THEN** `discover.py` records it in the `deletions` array with status `deleted-in-source` and its lock provenance (`last_synced_sha256`, `source`)
- **AND** no file is auto-deleted — the record is surfaced for manual review

#### Scenario: A local-only asset with no lock entry is left alone

- **WHEN** a local asset has no lockfile entry and is absent from source
- **THEN** `discover.py` does not flag it as a deletion (it is overlay or genuinely local)

#### Scenario: A never-synced overlay is never flagged as a deletion

- **WHEN** a local file whose leaf name is `project-context.md` or ends with `.local.md` is absent from source
- **THEN** it is excluded by `_is_excluded`, never enters the lockfile, and is never recorded as a deletion

#### Scenario: A rename surfaces as delete plus new

- **WHEN** a previously synced asset is renamed in source
- **THEN** `discover.py` surfaces a `deleted-in-source` record for the old path and a `new` record for the new path

#### Scenario: A scoped run does not surface out-of-scope deletions

- **WHEN** `discover.py` runs with an asset-path filter and a lock-tracked asset outside that filter is absent from the current source
- **THEN** it is NOT surfaced as `deleted-in-source` — the local deletion walk applies the same `_matches_filter` scope as the source walk, so only in-scope assets are considered

### Requirement: Source-agnostic provenance with a soft hub convention

The sync mechanism SHALL be source-agnostic: the lockfile records the `source` per asset, so asset X MAY canonically come from repo A and asset Y from repo B, and an improvement made in any repo SHALL be pullable everywhere by running `update-cla` against that repo for that asset. No single canonical hub SHALL be hard-coded in the scripts. `update-cla`'s SKILL.md SHALL document a soft, non-enforced "prefer the hub for generic core" default as guidance for newcomers only — not a constraint the tooling checks or enforces.

#### Scenario: Different assets carry different canonical sources

- **WHEN** two assets are synced from two different source repos over time
- **THEN** each asset's lockfile entry records its own `source`, and neither pull assumes a single canonical hub

#### Scenario: The hub preference is documentation, not enforcement

- **WHEN** a user reads `update-cla`'s SKILL.md
- **THEN** it describes a soft "prefer the hub for generic core" default
- **AND** no script rejects or warns on a sync from a non-hub source

### Requirement: Skill fact/procedure separation

Every `cla` plugin skill SHALL separate **project-specific facts** from **generic procedure**, keeping only procedure in its synced core (`SKILL.md` and non-overlay `references/`) and placing every project-specific fact behind that skill's repo-neutral project-context overlay (`references/project-context.md`, per the Project-specific overlay convention) — OR, for a **repo-wide fact shared across multiple skills**, in the repo-level consolidated project-facts file `cla.io/project-facts.md` (per the **Consolidated project-facts file** requirement), referenced from the overlay by a pointer. The governing rule of thumb SHALL be **"extract a fact, keep a procedure."**

A **fact** (which MUST be extracted to the overlay or, when shared across skills, to `cla.io/project-facts.md`, never left in a synced core file) is any content whose value is specific to *this* repository, including but not limited to:
- concrete shell commands with repo-specific tokens (e.g. package-manager invocations, filtered workspace/test commands, app/server start commands, specific script paths);
- package, workspace, app, or directory names and file paths (e.g. `apps/*`, `packages/*`, a backend project dir);
- permission sets scoped to this repo's tools (e.g. a skill-bundled required-permissions list);
- incident, offense, or past-failure history particular to work done in this repo;
- product/domain prose describing this repo's applications, data, market, or concepts;
- fixed infrastructure values such as port numbers, service names, and env-var names tied to this repo's processes;
- enumerated lists of this repo's files, specs, or docs to touch.

A **procedure** (which SHALL remain generic in `SKILL.md` / non-overlay references) is content whose value is independent of any particular repo, including: workflow phases and their ordering; discipline, escalation, and stop/continue rules; verdict/size-gate logic; JSON/log schemas and their field contracts; the shape and structure of a review, plan, or report; and generic tool-usage patterns.

**Blended content** — a generic rule justified by a specific past incident, or a generic phase that names a repo command as its example — SHALL be split: the generic rule/phase stays in `SKILL.md` (reworded to be repo-agnostic, with a "see `references/project-context.md`" pointer where the concrete detail aids the reader), and the incident detail or concrete command moves to the overlay. Extraction SHALL preserve behavior — a skill run against a repo whose overlay is filled in MUST retain the same effective guidance it had before extraction (relocation of specifics, not loss of capability).

The **shared/skill-specific tie-break** SHALL be: a fact goes to `cla.io/project-facts.md` when it serves two or more skills OR names a repo-global command, port, workspace member, or path map; a fact stays in a skill's own overlay when it is an example chosen to illustrate *that* skill's prose, or is that skill's own incident history / bespoke checks / permission-set intent. This requirement applies to every skill that carries project specifics; skills that are already fully generic (no facts to extract) satisfy it trivially and need no overlay.

#### Scenario: A synced skill body carries no repo-specific facts

- **WHEN** any `cla` skill's `SKILL.md` or a non-overlay `references/` file is inspected after extraction
- **THEN** it contains no project-specific fact (no repo-specific command, package/path name, permission set, incident history, product prose, port, or repo file list)
- **AND** every such fact it previously carried is present in that skill's `references/project-context.md` overlay, or in `cla.io/project-facts.md` when the fact is shared across skills

#### Scenario: Procedure is preserved generically

- **WHEN** a skill's workflow phases, discipline/escalation rules, verdict logic, or schemas are inspected after extraction
- **THEN** they remain in `SKILL.md` / non-overlay references, reworded to be repo-agnostic rather than removed
- **AND** the skill's effective guidance is unchanged for a repo whose overlay is filled in

#### Scenario: A blended incident-justified rule is split

- **WHEN** a discipline rule in a skill is justified by a specific past incident in this repo
- **THEN** the generic rule stays in `SKILL.md`, reworded to be repo-agnostic
- **AND** the incident detail moves to that skill's `references/project-context.md` overlay
- **AND** the generic rule points at `references/project-context.md` where the concrete detail aids the reader

#### Scenario: A pure-fact reference file is folded into the overlay

- **WHEN** a skill's non-overlay reference file is entirely project-specific fact (e.g. a repo-scoped permission-set list or an incident-history log)
- **THEN** its content is relocated into that skill's project-context overlay (or an accompanying `*.local.md` overlay file)
- **AND** no synced core reference file remains that is wholly project-specific fact

#### Scenario: A mixed fact/procedure reference file is split, not wholly folded

- **WHEN** a skill's non-overlay reference file blends a generic checklist/rubric shape with project-specific bullets, paths, or examples (partially, not wholly, project fact)
- **THEN** the generic shape (e.g. a checklist structure, a grading rubric, a schema) remains in that reference file, reworded to be repo-agnostic
- **AND** the project-specific bullets/paths/examples move to that skill's project-context overlay
- **AND** the reference file points at the overlay for the relocated detail

#### Scenario: A fact shared across skills is placed in the consolidated file

- **WHEN** a project-specific fact serves two or more skills, or names a repo-global command, port, workspace member, or path map
- **THEN** it is placed once in `cla.io/project-facts.md`, not restated in each skill's overlay
- **AND** each consuming skill's overlay references it by a pointer to `cla.io/project-facts.md`

### Requirement: Per-skill project-context overlay

Each `cla` skill that carries project specifics SHALL route them through that skill's single per-skill overlay file — the `references/project-context.md` marker defined by the **Project-specific overlay convention**, which already governs the overlay's fixed repo-neutral path, its repo-name-free referencing, and the `*.local.md` leaf-suffix form for additional local files. This requirement does not restate those mechanics; it builds on them by fixing the overlay's **role and shape** so the file can be **stubbed by a scaffolding step and linted by a conformance guard**.

An overlay file SHALL be self-describing enough to be regenerated as an empty stub and filled in per destination repo. It SHALL open with a heading naming the owning skill and its role as a project overlay, and SHALL organize its content under headed sections that map to the fact categories the owning skill needs (for example: repo commands, package/path names, permission sets, incident/offense history, product/domain prose, infrastructure values, and repo file lists — only those the skill actually uses). A destination repo with an empty or absent overlay SHALL still run the skill's generic procedure; the overlay supplies the repo-specific detail, it does not gate the procedure.

A per-skill overlay SHALL contain only the facts **specific to that skill** (for example its own incident/offense history, its bespoke review checks, its permission-set intent). **Repo-wide facts shared across skills** SHALL NOT be restated in a per-skill overlay; per the one-physical-place rule of the **Consolidated project-facts file** requirement they live once in `cla.io/project-facts.md`, and a per-skill overlay that needs such a fact SHALL carry a pointer to `cla.io/project-facts.md` rather than a copy.

#### Scenario: The overlay is stubbable and lintable

- **WHEN** a scaffolding step generates an empty overlay for a skill, or a conformance guard inspects it
- **THEN** the overlay's expected shape is a heading naming the owning skill plus headed sections for the fact categories that skill uses
- **AND** the generic `SKILL.md` remains valid and runnable against an empty stub (the overlay supplies detail, it does not gate the procedure)

#### Scenario: An empty or absent overlay does not gate the procedure

- **WHEN** a skill runs in a destination repo whose `references/project-context.md` is an empty stub or absent
- **THEN** the skill's generic procedure still runs to completion
- **AND** only the repo-specific detail the overlay would otherwise supply is missing (the overlay supplies detail, it does not gate the procedure)

#### Scenario: A per-skill overlay holds only skill-specific facts

- **WHEN** a per-skill `references/project-context.md` is authored or trimmed
- **THEN** it contains only facts specific to that skill plus, where it needs a repo-wide fact, a pointer to `cla.io/project-facts.md`
- **AND** it does not restate a shared repo-wide fact that lives in `cla.io/project-facts.md`

### Requirement: Project-data scaffolding via `cla-init`

The `cla` plugin SHALL provide a `cla-init` skill at `.claude/plugins/cla/skills/cla-init/SKILL.md` (a `SKILL.md`, no command wrapper, invoked as `/cla:cla-init` per the plugin's namespacing convention) scoped exclusively to **project-data scaffolding**. `cla-init` SHALL bring a fresh or partially-scaffolded destination repo up to the project-data baseline the other cla skills expect, resolving the repo root via `git rev-parse --show-toplevel` (the plugin's standard repo-state resolution seam) so it writes to the correct `cla.io/` regardless of the current working directory.

`cla-init` SHALL create, when absent, the following `cla.io/` tree under the repo root:
- the directories `cla.io/decisions/`, `cla.io/feedback/`, `cla.io/retro/`, and `cla.io/lessons-learned/`;
- one empty (0-byte) retro ledger per retro-logging loop that has a reader — `cla.io/retro/spec-to-pr-runs.jsonl` and `cla.io/retro/codify-runs.jsonl`, both appended via the shared `lib/log_run.py` (which takes the ledger filename as its argument). An empty file is a valid empty JSONL ledger — no placeholder line. A loop with no analyzer skill SHALL NOT be given a ledger: the four that had none accumulated 19 records across five repos before being deleted;
- the feedback inbox `cla.io/feedback/notes.md` seeded with a minimal header;
- the rolling lessons-learned log `cla.io/lessons-learned/lessons-learned.md` seeded with a minimal header.

`cla-init` SHALL additionally seed, when absent, a skeleton project-context overlay stub at `references/project-context.md` for each skill that **reads its own `references/project-context.md` overlay as a source of repo facts** (per the Per-skill project-context overlay requirement) but does not yet have the file. A skill that merely *names* the overlay marker to document another mechanism — for example `update-cla`, which references the filename only to describe the sync-preservation convention — is NOT a consumer and SHALL NOT be seeded a stub. The stub SHALL open with a heading naming the owning skill and its role as a repo-local project overlay, and SHALL contain headed sections covering the fact categories the Per-skill project-context overlay requirement enumerates, so the stub is self-describing and can be filled in (or pruned) per destination repo. `cla-init` SHALL NOT populate the stub with real repo facts and SHALL NOT read, copy, or modify any asset-core file (a skill body, an agent, or a hook) — it only creates a stub file alongside a skill. `cla-init` SHALL NOT create, read, or modify the plugin manifest (`.claude-plugin/plugin.json`) or `.claude/settings.json`/`.claude/settings.local.json`; those remain per-repo manual onboarding steps.

The recommended onboarding order SHALL be `cla-init` (scaffold project data) then `update-cla` (sync/adapt the asset core), and this order SHALL be documented in both `cla-init`'s own SKILL.md and `update-cla`'s SKILL.md, noting that `update-cla` never creates project data so skipping `cla-init` leaves the `cla.io/` tree and overlay stubs missing.

#### Scenario: A fresh repo is scaffolded

- **WHEN** `cla-init` runs in a repo that has no `cla.io/` tree and no overlay stubs
- **THEN** it creates `cla.io/decisions/`, `cla.io/feedback/`, `cla.io/retro/`, and `cla.io/lessons-learned/`
- **AND** it creates the empty (0-byte) retro ledgers (one per retro-logging loop), the seeded `cla.io/feedback/notes.md`, and the seeded `cla.io/lessons-learned/lessons-learned.md`
- **AND** it creates a `references/project-context.md` skeleton stub for every skill that references the overlay marker but lacks the file
- **AND** it writes `cla.io/` under the repo root resolved via `git rev-parse --show-toplevel`, regardless of the working directory it was invoked from

#### Scenario: Re-run is idempotent and never clobbers existing project data

- **WHEN** `cla-init` runs in a repo where some or all of the scaffold already exists (e.g. a `.jsonl` ledger with history, a filled-in `notes.md`, or a populated `project-context.md`)
- **THEN** every already-present directory and file is skipped untouched — not truncated, overwritten, re-seeded, or merged — even when the seed content differs from what exists
- **AND** only the genuinely missing pieces are created
- **AND** a run against a fully-scaffolded repo is a no-op that writes nothing

#### Scenario: Overlay stubs match the skills that consume an overlay

- **WHEN** `cla-init` seeds overlay stubs
- **THEN** it seeds a `references/project-context.md` stub for exactly those skills that read their own overlay as a repo-fact source and do not already have one
- **AND** a skill that only names the overlay marker to document another mechanism (e.g. `update-cla`'s sync-preservation convention) is NOT seeded a stub
- **AND** each stub is a skeleton (heading naming the skill plus headed fact-category sections), never populated with real repo facts
- **AND** no asset-core file (a skill body, an agent, or a hook) is read, copied, or modified in the process

#### Scenario: cla-init does not wire the manifest or settings

- **WHEN** `cla-init` runs
- **THEN** it does NOT create, read, or modify `.claude-plugin/plugin.json`
- **AND** it does NOT create, read, or modify `.claude/settings.json` or `.claude/settings.local.json`
- **AND** those remain documented as separate, per-repo manual onboarding steps

#### Scenario: Onboarding order is documented

- **WHEN** the plugin's onboarding is documented
- **THEN** both `cla-init`'s SKILL.md and `update-cla`'s SKILL.md state the order `cla-init` → `update-cla`
- **AND** they note that `update-cla` never creates project data, so a repo that skips `cla-init` is left without the `cla.io/` tree and overlay stubs

### Requirement: Conformance guard for the overlay separation

The `cla` plugin SHALL include a pytest conformance guard that mechanically enforces the fact/procedure separation (the Skill fact/procedure separation and Project-specific overlay convention requirements). The guard SHALL be a generic, repo-agnostic checker that fails when any **non-overlay synced core file** contains a project-specific token, where the token list is itself a per-repo project overlay. The guard SHALL obey the same fact/procedure split it enforces: the checker is generic *procedure*; the token list is a repo-specific *fact* held in an overlay.

**Home and portability.** The guard SHALL live in its own scope at `.claude/plugins/cla/conformance-checks/`, not inside any one skill: it enforces a rule about the whole plugin and MUST outlive the sync tool. Because that path is outside `SCAN_DIRS`, the guard's files SHALL be named individually in `discover.SCAN_FILES` so `update-cla` still carries them to destination repos as portable core for as long as file-sync distribution exists. It SHALL NOT be implemented as a Claude Code hook and SHALL NOT block or interrupt authoring; it runs only in the test gate. The checker SHALL resolve the plugin tree relative to its own file location (a fixed internal layout identical in every repo), not via any repo-specific absolute path or repository name.

**Scan scope.** The guard SHALL scan every `SKILL.md` and every `references/**/*.md` file under `.claude/plugins/cla/skills/**`. It SHALL exclude from the scan: (a) overlay files — any file whose leaf name is exactly `project-context.md` or ends with `.local.md` (this covers every extracted fact overlay and the guard's own token-list file); (b) non-markdown / asset files; and (c) each scanned file's leading YAML frontmatter block (the content between the opening `---` on line 1 and its closing `---`). Because the exclusion is by leaf name, the token-list overlay is never flagged by the guard reading it. Frontmatter is excluded because a skill's `description:` / `argument-hint:` is trigger metadata that legitimately names the host repo and its apps so the skill fires — it is not portable procedure prose. The checker SHALL still report accurate 1-based line numbers for body violations (it skips frontmatter for matching, not for line counting).

**Token list as a per-repo overlay.** The token list SHALL live at `cla.io/project-tokens.local.md` — per-repo data, held with the rest of it and outside the synced core entirely, so `discover.py` never syncs it, each destination repo supplies its own, and neither of the guard's scans can reach it. Its `*.local.md` leaf name keeps it recognizable under the repo-neutral overlay convention. The checker SHALL read the list as data — it MUST NOT hard-code any token in the checker source. The list SHALL be curated to distinctive, repo-specific compound tokens (e.g. package/app paths and product/tool names) and MUST NOT include generic words that legitimately appear in portable procedure prose, so false positives are controlled by curation rather than by the matcher. Matching SHALL be case-insensitive.

**Failure output.** When a scanned core file contains a listed token, the guard SHALL fail and report each violation with the offending file's repo-relative path, the matched token, and the line number (with a line excerpt), one violation per line, surfacing all violations in a single run rather than stopping at the first.

**Absent vs. empty token list.** If no token-list overlay is present, the guard SHALL pass trivially with a clear reason — a destination repo that has synced the guard but not yet curated a token list (the overlay is never seeded by sync) MUST NOT get a failing result. If the overlay file IS present but yields no tokens, the guard SHALL FAIL with a clear message: a populated list broken by a later formatting change is a defect, not a fresh repo, and silently skipping it would disable the safety check with no signal. The failure message SHALL note that deleting the file is the way to intentionally disable the guard. The overlay supplies data to the guard; a missing overlay does not gate whether the guard runs, but a present-yet-empty one is treated as a broken list, not a trivial pass.

#### Scenario: A project token in a synced core file fails the guard

- **WHEN** a non-overlay `SKILL.md` or `references/**/*.md` file under `.claude/plugins/cla/skills/**` contains a token listed in the per-repo token-list overlay
- **THEN** the guard test fails
- **AND** the failure reports the offending file's repo-relative path, the matched token, and the line number with an excerpt

#### Scenario: A skill's frontmatter description is exempt from the scan

- **WHEN** a scanned `SKILL.md` names a project-specific token only inside its leading YAML frontmatter block (e.g. the `description:` field naming the host repo so the skill triggers)
- **THEN** the guard does not flag that occurrence
- **AND** a token appearing in the same file's body (after the closing frontmatter `---`) is still reported, with its accurate 1-based line number

#### Scenario: Overlay files are exempt from the scan

- **WHEN** the guard scans the plugin's skill files
- **THEN** any file whose leaf name is exactly `project-context.md` or ends with `.local.md` is excluded from the scan (including the token-list overlay itself and every extracted fact overlay)
- **AND** a project token appearing inside such an overlay file does not fail the guard

#### Scenario: The token list is per-repo data, not hard-coded

- **WHEN** the checker runs
- **THEN** it reads its tokens from the `*.local.md` token-list overlay rather than from any list embedded in the checker source
- **AND** that overlay is excluded from `update-cla` sync (each destination repo supplies its own token list)

#### Scenario: An absent token list is a trivial pass

- **WHEN** the guard runs in a repo with no token-list overlay present
- **THEN** the guard passes with a clear reason
- **AND** it does not fail CI merely because the token list has not yet been curated

#### Scenario: A present-but-empty token list fails

- **WHEN** the guard runs with a token-list overlay that is present but yields no tokens (e.g. broken by a formatting change)
- **THEN** the guard fails with a clear message
- **AND** the message indicates that deleting the file is the way to intentionally disable the guard

#### Scenario: The plugin tree is resolved relative to the test file's own location

- **WHEN** the checker resolves the plugin tree to scan
- **THEN** it derives the root by walking up from its own file's location (`Path(__file__)`), a fixed internal layout identical in every repo
- **AND** it does not use any repo-specific absolute path or repository name to find the plugin tree

#### Scenario: The guard is a test, not an authoring-time hook

- **WHEN** the guard is added to the plugin
- **THEN** it is a pytest test in an existing skill's `tests/` under `.claude/plugins/cla/skills/**`
- **AND** it is not a `PreToolUse` (or other) hook and never blocks or interrupts editing; it runs only in the test gate

### Requirement: Consolidated project-facts file

The `cla` plugin SHALL support a single, repo-level **consolidated project-facts file** at `cla.io/project-facts.md` that holds the repo-wide facts shared across multiple skills — at minimum the workspace member list, the dev/build/test commands, the infrastructure ports, the affected-file map, the doc-sweep path list, and package/path names. It SHALL live in the `cla.io/` per-repo data tree, which is outside `update-cla`'s sync scan roots (`SCAN_DIRS`), so the file is never synced across repos and needs no additional sync-exclusion. Each destination repo owns its own `cla.io/project-facts.md`.

A shared repo-wide fact SHALL exist in exactly one physical place — the consolidated file — and SHALL NOT be restated across per-skill overlays; a per-skill overlay or workflow that needs a shared fact SHALL reference it via a pointer to `cla.io/project-facts.md` rather than a copy. This one-physical-place rule is the canonical statement referenced by the **Per-skill project-context overlay**, **Project-specific overlay convention**, and **Skill fact/procedure separation** requirements.

Because the consolidated file is per-repo and may be absent (a fresh repo that has not yet run the context-refresh skill), a pointer to it SHALL degrade gracefully by **prompting the reader to run `/cla:sync-context`** to populate it, rather than failing. A pointer SHALL NOT keep an inline duplicate copy of the shared fact as its fallback — that would reintroduce the very duplication this requirement's one-physical-place rule exists to eliminate; the graceful-degradation instruction is the actionable prompt, not a second copy.

#### Scenario: Shared facts live in one file

- **WHEN** a repo-wide fact (e.g. the workspace member list, a dev command, a port, the affected-file map, or the doc-sweep path list) is recorded
- **THEN** it is written once in `cla.io/project-facts.md`
- **AND** it is not duplicated into any per-skill `references/project-context.md`

#### Scenario: The consolidated file is per-repo and never synced

- **WHEN** `update-cla` syncs the plugin's portable core
- **THEN** `cla.io/project-facts.md` is not a sync candidate (it lives outside `SCAN_DIRS`)
- **AND** each destination repo supplies its own `cla.io/project-facts.md`

#### Scenario: A pointer degrades gracefully when the file is absent

- **WHEN** a skill body references `cla.io/project-facts.md` in a repo where that file does not exist yet
- **THEN** the reference prompts the reader to run `/cla:sync-context` to populate it (it does not carry an inline duplicate copy of the fact)
- **AND** the skill's procedure still runs rather than failing on the missing file

### Requirement: Consolidated domain-terminology file

The `cla` plugin SHALL support a single, repo-level **consolidated domain-terminology file** at `cla.io/terminology.md`, distinct in kind from `cla.io/project-facts.md`. Where the project-facts file holds mechanical, build-level facts, the terminology file holds **canonical internal-naming disambiguation**: one-sentence definitions for concepts specific to this repo's own codebase or product, each naming any rejected alias terms to avoid, in the entry format `**Term**: one-sentence definition — what it IS, not what it does. _Avoid_: rejected-alias-1, rejected-alias-2`. The terminology file is narrow by design — it SHALL NOT hold external, regulatory, or business-reference knowledge; a repo's own hand-authored glossary of that kind, if one exists, is untouched by this requirement and is never read, restructured, or superseded by it. It SHALL live in the `cla.io/` per-repo data tree, outside `update-cla`'s sync scan roots (`SCAN_DIRS`), so it is never synced across repos and needs no additional sync-exclusion. Each destination repo owns its own `cla.io/terminology.md`, created **lazily** — only once the first term resolves, not pre-scaffolded empty by `cla-init`.

Unlike `cla.io/project-facts.md`, whose content is populated exclusively by the context-refresh skill in a batch reconcile pass, `cla.io/terminology.md` SHALL be **written inline** by any consuming skill, in-session, the moment a term resolves — never batched to a later pass — because the value of a disambiguation is tied to the conversational moment it was resolved in. The **context-refresh skill** (`sync-context`, per the **Context-refresh skill** requirement) SHALL own the terminology file's entry format and the reconciliation logic for existing entries (de-duplication and conflict-flagging) — as well as documenting that creation is lazy and performed by whichever consuming skill needs the file first, NOT by `sync-context` itself — documented in its own SKILL.md. `sync-context` SHALL NOT be the exclusive writer of the file's content and SHALL NOT itself create the file — any consuming skill applies the documented format directly via its own `Edit`/`Write` calls, without invoking `/cla:sync-context` as a sub-step.

A pointer to `cla.io/terminology.md` SHALL be a **soft, degrade-gracefully reference**: every consuming skill SHALL treat it as an optional enhancement, never a hard requirement — reading the canonical term if the file is present and covers the concept, and proceeding on its own judgement if the file is absent or silent on that term. This is a deliberate divergence from `cla.io/project-facts.md`'s pointer convention (which prompts the reader to run `/cla:sync-context`): the terminology file legitimately stays unpopulated for a long time in a repo that hasn't yet run a skill that writes to it, and prompting "run sync-context to populate it" would mislead, since sync-context does not itself generate terminology content — only documents its format.

#### Scenario: A resolved term is written inline, not batched

- **WHEN** a consuming skill (e.g. `shape-decision`) resolves a naming ambiguity or disambiguates a fuzzy term during a live session
- **THEN** it writes the entry to `cla.io/terminology.md` directly, in that same session, via `Edit`/`Write`
- **AND** it does not defer the write to a later `/cla:sync-context` run

#### Scenario: The terminology file is lazily created

- **WHEN** the first term resolves in a repo where `cla.io/terminology.md` does not yet exist
- **THEN** the consuming skill creates the file at that point, following the entry format `sync-context` documents
- **AND** `cla-init` does not pre-scaffold an empty `cla.io/terminology.md`

#### Scenario: The terminology file never duplicates an external glossary

- **WHEN** a repo already maintains its own external/regulatory/business-reference glossary (e.g. a hand-authored `docs/glossary.md`)
- **THEN** `cla.io/terminology.md` holds only internal/product naming disambiguation
- **AND** no `cla` skill reads, writes, restructures, or supersedes the repo's own external glossary as part of this requirement

#### Scenario: A pointer degrades gracefully without prompting a populate step

- **WHEN** a skill body references `cla.io/terminology.md` in a repo where the file is absent or has no entry covering the term in question
- **THEN** the skill's procedure still runs to completion, using its own best judgement for naming
- **AND** the reference does not block on, or insist on, populating the file first (unlike the `project-facts.md` pointer's "run `/cla:sync-context`" prompt)

#### Scenario: sync-context owns the format, not exclusive writes

- **WHEN** any consuming skill writes an entry to `cla.io/terminology.md`
- **THEN** it follows the entry format and de-duplication/conflict-flagging rules documented in `sync-context`'s SKILL.md
- **AND** the write itself is performed by the consuming skill directly, not by invoking `/cla:sync-context` as a sub-step

#### Scenario: The terminology file is never synced across repos

- **WHEN** `update-cla` syncs the plugin's portable core
- **THEN** `cla.io/terminology.md` is not a sync candidate (it lives outside `SCAN_DIRS`)
- **AND** each destination repo supplies its own `cla.io/terminology.md`

### Requirement: Context-refresh skill

The `cla` plugin SHALL provide a **context-refresh skill** at `.claude/plugins/cla/skills/sync-context/SKILL.md` (a `SKILL.md`, invoked as `/cla:sync-context` per the plugin's namespacing convention) that reads the current repo and populates or reconciles the fact *content* of `cla.io/project-facts.md`. It SHALL extract facts by reading the repo's own manifests/config directly (an LLM-driven universal extractor), with **no stack-specific parser**, so it works across repos of differing tech stacks. It SHALL resolve the repo root via the plugin's standard repo-state resolution seam (`git rev-parse --show-toplevel`) so it writes to the correct `cla.io/` regardless of the working directory, creating the `cla.io/` directory if it does not exist.

The refresh skill SHALL be **self-sufficient**: when `cla.io/project-facts.md` is absent it SHALL create it, so running the skill alone on a fresh repo populates the facts (acting as fact-initialization) rather than requiring pre-existing content. It SHALL **propose** (for user confirmation, not silently apply) new `project-tokens.local.md` entries when it detects a new distinctive app/package token, following the same curation discipline the conformance guard's token list requires.

The refresh skill SHALL own fact **content** only: it populates `cla.io/project-facts.md` (the shared repo-wide facts) and the pointer lines in per-skill overlays. It SHALL NOT take over the structure-scaffolding role of `cla-init`, and the **skill-specific authored body** of a per-skill overlay (a skill's own incident history, bespoke checks, permission-set intent) remains human/LLM authored — `cla-init` scaffolds it as an empty stub, and it is filled independently of the refresh skill. `cla-init` remains unchanged — it scaffolds the `cla.io/` tree and empty per-skill overlay stubs and SHALL NOT populate facts. The documented onboarding order SHALL be `cla-init` (structure) then `/cla:sync-context` (content) then `update-cla` (portable core), stated in the refresh skill's SKILL.md, `update-cla`'s SKILL.md, and `cla-init`'s SKILL.md.

The refresh skill SHALL additionally **document, in its own SKILL.md, the entry format and reconciliation logic for `cla.io/terminology.md`** (per the **Consolidated domain-terminology file** requirement), without being that file's exclusive writer — content is written inline by whichever consuming skill resolves a term. The refresh skill MAY perform a light, optional reconciliation pass over an existing `cla.io/terminology.md` (catching near-duplicate or conflicting entries), but SHALL NOT author its content from scratch.

#### Scenario: Refresh populates the consolidated facts file

- **WHEN** `/cla:sync-context` runs in a repo
- **THEN** it reads the repo's own manifests/config and writes the repo-wide facts into `cla.io/project-facts.md`
- **AND** it uses no stack-specific parser (it reads whatever config the repo has)

#### Scenario: Refresh acts as fact-init on a fresh repo

- **WHEN** `/cla:sync-context` runs in a repo where `cla.io/project-facts.md` (and possibly `cla.io/` itself) is absent
- **THEN** it creates the `cla.io/` directory if needed, creates the file, and populates it
- **AND** it does not require `cla-init` to have pre-populated any fact content (cla-init only scaffolds empty structure)

#### Scenario: Refresh resolves the repo root regardless of working directory

- **WHEN** `/cla:sync-context` runs from a subdirectory of the repo
- **THEN** it resolves the repo root via `git rev-parse --show-toplevel`
- **AND** it writes `cla.io/project-facts.md` under that root, not relative to the working directory

#### Scenario: Refresh proposes new token-list entries for confirmation

- **WHEN** `/cla:sync-context` detects a new distinctive app/package token not yet in `project-tokens.local.md`
- **THEN** it proposes the addition for the user to confirm
- **AND** it does not silently add the token (the same curation discipline the conformance guard's token list requires)

#### Scenario: Refresh owns content, not structure

- **WHEN** `/cla:sync-context` runs
- **THEN** it writes only fact content (into `cla.io/project-facts.md` and the pointer lines of per-skill overlays)
- **AND** it does not scaffold the `cla.io/` directory tree of ledgers/inboxes or empty overlay stubs, which remain `cla-init`'s role
- **AND** the skill-specific authored body of a per-skill overlay is not owned by the refresh skill

#### Scenario: Onboarding order is documented

- **WHEN** the plugin's onboarding is documented
- **THEN** the refresh skill's SKILL.md, `update-cla`'s SKILL.md, and `cla-init`'s SKILL.md state the order `cla-init` → `/cla:sync-context` → `update-cla`
- **AND** they note that `cla-init` scaffolds structure, `/cla:sync-context` fills fact content, and `update-cla` syncs the portable core

### Requirement: Project-facts staleness guard

The `cla` plugin SHALL include a **portable staleness guard** — a pytest test alongside the conformance guard under `.claude/plugins/cla/conformance-checks/tests/` — that fails when any **repo-relative path** named in `cla.io/project-facts.md` or in a per-skill `references/project-context.md` no longer resolves on disk (as either a file or a directory). The guard SHALL resolve the **repo root** (e.g. via the parent of `.claude/` or `git rev-parse --show-toplevel`), since the paths it checks are repo-relative and `cla.io/project-facts.md` lives at the repo root, outside the plugin tree — it SHALL NOT assume the plugin-root resolution the conformance guard uses. It SHALL report every stale path (file, line, and the path) one per line in a single run rather than stopping at the first.

The guard SHALL be stack-agnostic: it checks path existence only and SHALL NOT parse any stack-specific config (`pnpm-workspace.yaml`, `Cargo.toml`, etc.), and the set of recognized top-level path prefixes SHALL be **derived from the repo's own top-level entries** (not a hardcoded list), so the guard ports to a repo of any layout. If `cla.io/project-facts.md` is absent, the guard SHALL pass trivially (a fresh repo that has not yet run `/cla:sync-context` MUST NOT get a failing result).

The guard SHALL extract path candidates conservatively — treating a token as a repo-relative path only when it clearly is one: it contains a path separator; is not a URL, `~`-path, glob, or placeholder; and its first segment names an actual top-level entry in the repo. Before existence-checking, it SHALL strip surrounding backticks/punctuation and any trailing `:line[:col]` suffix. On an ambiguous token it SHALL err toward **not** flagging (a false staleness failure trains people to ignore the guard).

The guard checks **path existence only**; it does NOT validate the non-path mechanical facts the refresh skill produces (commands, ports, member counts) — those are kept fresh by `/cla:sync-context` and human review, not by this guard. It also does not detect a fact duplicated between `cla.io/project-facts.md` and an overlay. These limits SHALL be stated in the guard so its coverage is not overstated.

#### Scenario: A stale path in the facts file fails the guard

- **WHEN** `cla.io/project-facts.md` or a per-skill overlay names a repo-relative path that no longer exists on disk (as file or directory)
- **THEN** the guard test fails
- **AND** it reports the offending file, the line number, and the stale path, one violation per line, surfacing all stale paths in a single run

#### Scenario: The guard is stack-agnostic and repo-derived

- **WHEN** the guard runs
- **THEN** it checks only whether named repo-relative paths resolve on disk, parsing no stack-specific config
- **AND** the top-level path prefixes it recognizes are derived from the repo's own top-level entries, not a hardcoded list

#### Scenario: An ambiguous non-path token is not flagged

- **WHEN** a token in a scanned file contains no path separator, or is a URL / glob / placeholder, or its first segment is not an actual top-level repo entry
- **THEN** the guard does not treat it as a repo-relative path and does not flag it
- **AND** a directory path, and a path written with a trailing `:line` suffix or surrounding punctuation, is still resolved correctly (existence-checked after stripping)

### Requirement: Skill token-efficiency disciplines

cla-plugin skills SHALL be authored to minimize the static token cost of the skill definition, and orchestrator/multi-phase skills SHALL additionally be executed to minimize the runtime context they accumulate — both without weakening correctness-gating behavior. Two disciplines are load-bearing:

1. **Progressive disclosure of skill definitions** (applies to every skill large enough to have movable content). A skill's `SKILL.md` SHALL keep inline ONLY the content that must be in context for every run: correctness-gating invariants, hoisted skill-level rules, phase order, caps, and the autonomy/halt contract — each stated as a one-liner where possible. Mechanics (step-by-step procedures), rationale, templates, and examples SHALL live in on-demand `references/*.md` files (per-phase or per-topic; the requirement is a mandatory reference-read step, NOT a specific `references/<phase>.md` filename pattern). A multi-phase skill SHALL give each phase a mandatory "read its reference file first" step so the executing agent loads that phase's mechanics on demand rather than carrying every phase's mechanics inline for the whole run. Correctness-gating invariants MUST NOT be relocated out of the inline `SKILL.md` context — each phase's inline stub SHALL remain self-sufficient for its own invariant even if the phase's reference file is not read. Any repo-specific content moved out of `SKILL.md` (worked examples naming real symbols/files, dated incidents) SHALL be routed to a project overlay (`references/project-context.md` / `*.local.md` / `cla.io/project-facts.md`), NOT into a generic synced-core reference file, per the existing **Skill fact/procedure separation** and **Project-specific overlay convention** requirements. The authoring recipe for this transformation — the keep-inline/move boundary, the checklist of correctness-gating invariants that commonly get dropped during a restructure, and the validation steps — is `.claude/plugins/cla/skills/spec-to-pr/references/progressive-disclosure.md`.

2. **Thin-orchestrator runtime execution** (applies to orchestrator-shaped skills — those that drive sub-skills/agents across phases; a small non-orchestrating skill has no raw-material handling to delegate and is out of this discipline's scope). An orchestrator skill SHALL delegate raw-material handling to sub-agents so that only conclusions — not the raw files, diffs, grep output, or intermediate material — return to the parent context. As standing I/O hygiene it SHALL read slices rather than whole files, pipe large command output through `tail`/`head`, and route large intermediate material through a scratch file handed to a delegate rather than inlining it. It SHALL batch independent tool calls into a single message, and SHALL prefer terse, schema'd (structured) agent output over prose essays. Delegating fix *application* to a sub-agent SHALL NOT relocate the orchestrator's own post-fix re-verification discipline (proving a discharged finding's defect is actually gone) — the delegate applies edits; the orchestrator still verifies.

Adherence SHALL be measured by a static `wc` proxy on `SKILL.md` size (before/after on any edit that claims a reduction) plus the skill's existing per-run retro loop. A mechanical size-guard / size-lint SHALL NOT be added — a raw size threshold is crude and false-positive-prone; the `wc` proxy is a manual check, and the retro loop is the durable signal against silent re-inflation. Because the `wc` proxy is gameable by relocating correctness-gating invariants out of `SKILL.md` (shrinking the file without reducing loaded correctness content), the "correctness-gating invariants stay inline" scenario below is the intended guard against that, and a size reduction that came from invariant flight rather than mechanics relocation SHALL NOT be treated as a genuine efficiency win.

#### Scenario: A skill definition progressively discloses its mechanics

- **WHEN** a cla-plugin multi-phase skill's `SKILL.md` is inspected
- **THEN** correctness-gating invariants, hoisted rules, phase order, caps, and the autonomy/halt contract are present inline
- **AND** per-phase step-by-step mechanics, rationale, templates, and examples live in `references/*.md` (per-phase or per-topic) rather than inline
- **AND** each phase carries a mandatory "read its reference file first" step (a reference-read step, not a specific filename pattern)
- **AND** any relocated repo-specific worked example lives in a project overlay, not a generic synced-core reference file

#### Scenario: Correctness-gating invariants stay inline

- **WHEN** mechanics are moved out of a `SKILL.md` into `references/*.md`
- **THEN** no correctness-gating invariant (a hoisted skill-level rule, a git-state/staging discipline, the autonomy gate, a per-loop cap) is among the relocated content
- **AND** each such invariant remains readable inline in `SKILL.md`
- **AND** each phase's inline stub is self-sufficient for that phase's invariant (carries the invariant itself, not merely a pointer to the reference file)

#### Scenario: An orchestrator skill runs thin

- **WHEN** an orchestrator skill processes bulk raw material (a large diff, a wide file set, verbose command output)
- **THEN** it delegates the raw-material handling to a sub-agent (or reads only slices / pipes through `tail`/`head` / routes it through a scratch file) so only conclusions return to the parent context
- **AND** it batches independent tool calls into a single message
- **AND** dispatched agents return terse structured output rather than prose essays

#### Scenario: Efficiency is measured, not size-gated

- **WHEN** an edit claims a `SKILL.md` size reduction
- **THEN** the reduction is validated with a `wc` before/after comparison
- **AND** the durable guard against re-inflation is the skill's existing retro loop, NOT a mechanical size-guard or size-lint
