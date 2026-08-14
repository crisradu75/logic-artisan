# Delta: cla-plugin — remove-update-cla

## MODIFIED Requirements

### Requirement: In-place activation and namespacing

The `cla` plugin SHALL be activated in place via `claude --plugin-dir ./.claude/plugins/cla` **in the canonical repo (development mode)**, so its scripts and skills run from the live working tree while the harness itself is being developed. A **consuming repo** SHALL activate the plugin via the marketplace install (`claude plugin marketplace add crisradu75/logic-artisan` then `claude plugin install cla@cris-logic-artisan --scope project`), which runs from a read-only versioned snapshot in the plugin cache — workable because all repo-local workflow state lives under the repo's own `cla.io/` tree, outside the plugin directory, so a read-only install reads and writes it unchanged. Each workflow SHALL be a skill (no thin command wrappers) and SHALL be invoked under the plugin namespace as `/cla:<skill>`.

#### Scenario: Skills resolve under the cla namespace

- **WHEN** a session is launched with `--plugin-dir ./.claude/plugins/cla` (canonical repo) or with the marketplace-installed plugin active (consuming repo)
- **THEN** each harness workflow is invocable as `/cla:<skill>` (e.g. `/cla:spec-to-pr`, `/cla:project-review`, `/cla:shape-decision`)
- **AND** no bare `.claude/commands/*.md` wrapper exists for any cla skill

#### Scenario: A marketplace install needs no write access to the plugin tree

- **WHEN** a consuming repo runs any cla skill from the cached marketplace install
- **THEN** every repo-local read/write the skill performs targets `cla.io/` (or other repo paths), never the plugin cache directory

#### Scenario: Internal composition uses the namespace

- **WHEN** one skill invokes another (e.g. `multi-pr` runs `spec-to-pr`, `spec-to-pr` reads `review-change`)
- **THEN** the invocation uses the `cla:`-namespaced form (`Skill(cla:<name>)`) and resolves within the plugin

### Requirement: Project-data scaffolding via `cla-init`

The `cla` plugin SHALL provide a `cla-init` skill at `.claude/plugins/cla/skills/cla-init/SKILL.md` (a `SKILL.md`, no command wrapper, invoked as `/cla:cla-init` per the plugin's namespacing convention) scoped exclusively to **project-data scaffolding**. `cla-init` SHALL bring a fresh or partially-scaffolded destination repo up to the project-data baseline the other cla skills expect, resolving the repo root via `git rev-parse --show-toplevel` (the plugin's standard repo-state resolution seam) so it writes to the correct `cla.io/` regardless of the current working directory.

`cla-init` SHALL create, when absent, the following `cla.io/` tree under the repo root:
- the directories `cla.io/decisions/`, `cla.io/feedback/`, `cla.io/retro/`, and `cla.io/lessons-learned/`;
- one empty (0-byte) retro ledger per retro-logging loop that has a reader — `cla.io/retro/spec-to-pr-runs.jsonl` and `cla.io/retro/codify-runs.jsonl`, both appended via the shared `lib/log_run.py` (which takes the ledger filename as its argument). An empty file is a valid empty JSONL ledger — no placeholder line. A loop with no analyzer skill SHALL NOT be given a ledger: the four that had none accumulated 19 records across five repos before being deleted;
- the feedback inbox `cla.io/feedback/notes.md` seeded with a minimal header;
- the rolling lessons-learned log `cla.io/lessons-learned/lessons-learned.md` seeded with a minimal header.

`cla-init` SHALL additionally seed, when absent, a skeleton overlay stub at `cla.io/overlays/<skill>.md` for each skill that **reads its own `cla.io/overlays/<skill>.md` overlay as a source of repo facts** (per the Per-skill project-context overlay requirement) but does not yet have the file. A skill that merely *names* the overlay marker to document another mechanism is NOT a consumer and SHALL NOT be seeded a stub. The stub SHALL open with a heading naming the owning skill and its role as a repo-local project overlay, and SHALL contain headed sections covering the fact categories the Per-skill project-context overlay requirement enumerates, so the stub is self-describing and can be filled in (or pruned) per destination repo. `cla-init` SHALL NOT populate the stub with real repo facts and SHALL NOT read, copy, or modify any asset-core file (a skill body, an agent, or a hook) — it only creates a stub file under `cla.io/overlays/`. `cla-init` SHALL NOT create, read, or modify the plugin manifest (`.claude-plugin/plugin.json`) or `.claude/settings.json`/`.claude/settings.local.json`; those remain per-repo manual onboarding steps.

The recommended onboarding order SHALL be: the marketplace install (`claude plugin marketplace add crisradu75/logic-artisan`, `claude plugin install cla@cris-logic-artisan --scope project`) to obtain the skills, then `cla-init` (scaffold project data), then `sync-context` (populate `cla.io/project-facts.md`). This order SHALL be documented in `cla-init`'s own SKILL.md, noting that the install provides the skills but never creates project data, so a repo that skips `cla-init` is left without the `cla.io/` tree and overlay stubs.

#### Scenario: A fresh repo is scaffolded

- **WHEN** `cla-init` runs in a repo that has no `cla.io/` tree and no overlay stubs
- **THEN** it creates `cla.io/decisions/`, `cla.io/feedback/`, `cla.io/retro/`, and `cla.io/lessons-learned/`
- **AND** it creates the empty (0-byte) retro ledgers (one per retro-logging loop), the seeded `cla.io/feedback/notes.md`, and the seeded `cla.io/lessons-learned/lessons-learned.md`
- **AND** it creates a `cla.io/overlays/<skill>.md` skeleton stub for every skill that references the overlay marker but lacks the file
- **AND** it writes `cla.io/` under the repo root resolved via `git rev-parse --show-toplevel`, regardless of the working directory it was invoked from

#### Scenario: Re-run is idempotent and never clobbers existing project data

- **WHEN** `cla-init` runs in a repo where some or all of the scaffold already exists (e.g. a `.jsonl` ledger with history, a filled-in `notes.md`, or a populated `cla.io/overlays/<skill>.md`)
- **THEN** every already-present directory and file is skipped untouched — not truncated, overwritten, re-seeded, or merged — even when the seed content differs from what exists
- **AND** only the genuinely missing pieces are created
- **AND** a run against a fully-scaffolded repo is a no-op that writes nothing

#### Scenario: Overlay stubs match the skills that consume an overlay

- **WHEN** `cla-init` seeds overlay stubs
- **THEN** it seeds a `cla.io/overlays/<skill>.md` stub for exactly those skills that read their own overlay as a repo-fact source and do not already have one
- **AND** a skill that only names the overlay marker to document another mechanism is NOT seeded a stub
- **AND** each stub is a skeleton (heading naming the skill plus headed fact-category sections), never populated with real repo facts
- **AND** no asset-core file (a skill body, an agent, or a hook) is read, copied, or modified in the process

#### Scenario: cla-init does not wire the manifest or settings

- **WHEN** `cla-init` runs
- **THEN** it does NOT create, read, or modify `.claude-plugin/plugin.json`
- **AND** it does NOT create, read, or modify `.claude/settings.json` or `.claude/settings.local.json`
- **AND** those remain documented as separate, per-repo manual onboarding steps

#### Scenario: Onboarding order is documented

- **WHEN** the plugin's onboarding is documented
- **THEN** `cla-init`'s SKILL.md states the order: marketplace install → `cla-init` → `sync-context`
- **AND** it notes that the install provides the skills but never creates project data, so a repo that skips `cla-init` is left without the `cla.io/` tree and overlay stubs

### Requirement: Conformance guard for the overlay separation

The `cla` plugin SHALL include a pytest conformance guard that mechanically enforces the fact/procedure separation (the Skill fact/procedure separation and Project-specific overlay convention requirements). The guard SHALL be a generic, repo-agnostic checker that fails when any **non-overlay synced core file** contains a project-specific token, where the token list is itself a per-repo project overlay. The guard SHALL obey the same fact/procedure split it enforces: the checker is generic *procedure*; the token list is a repo-specific *fact* held in an overlay.

**Home and portability.** The guard SHALL live in its own scope at `.claude/plugins/cla/conformance-checks/`, not inside any one skill: it enforces a rule about the whole plugin. Because the marketplace install distributes the entire `.claude/plugins/cla/` directory as one versioned snapshot, the guard reaches every destination repo by construction, with no per-file enumeration required. **Known coverage gap:** that same whole-directory distribution means files outside the guard's scan roots — `lib/`, the `*-checks/` scopes, `run_tests.py`, `mutate.py` — now ship to consumers unscanned; widening the scan roots is deliberately NOT attempted here, because those scopes legitimately contain project tokens as test fixtures and would need a fixture-aware exemption first. The gap SHALL be recorded as a tracked follow-up rather than silently carried. The guard SHALL NOT be implemented as a Claude Code hook and SHALL NOT block or interrupt authoring; it runs only in the test gate. The checker SHALL resolve the plugin tree relative to its own file location (a fixed internal layout identical in every repo), not via any repo-specific absolute path or repository name.

**Scan scope.** The guard SHALL scan every `SKILL.md` and every `references/**/*.md` file under `.claude/plugins/cla/skills/**`. It SHALL exclude from the scan: (a) overlay files — any file whose leaf name is exactly `project-context.md` or ends with `.local.md` (this covers every extracted fact overlay and the guard's own token-list file); (b) non-markdown / asset files; and (c) each scanned file's leading YAML frontmatter block (the content between the opening `---` on line 1 and its closing `---`). Because the exclusion is by leaf name, the token-list overlay is never flagged by the guard reading it. Frontmatter is excluded because a skill's `description:` / `argument-hint:` is trigger metadata that legitimately names the host repo and its apps so the skill fires — it is not portable procedure prose. The checker SHALL still report accurate 1-based line numbers for body violations (it skips frontmatter for matching, not for line counting).

**Token list as a per-repo overlay.** The token list SHALL live at `cla.io/project-tokens.local.md` — per-repo data, held with the rest of it and outside the plugin directory entirely, so a marketplace install never carries one repo's tokens to another, each destination repo supplies its own, and neither of the guard's scans can reach it. Its `*.local.md` leaf name keeps it recognizable under the repo-neutral overlay convention. The checker SHALL read the list as data — it MUST NOT hard-code any token in the checker source. The list SHALL be curated to distinctive, repo-specific compound tokens (e.g. package/app paths and product/tool names) and MUST NOT include generic words that legitimately appear in portable procedure prose, so false positives are controlled by curation rather than by the matcher. Matching SHALL be case-insensitive.

**Failure output.** When a scanned core file contains a listed token, the guard SHALL fail and report each violation with the offending file's repo-relative path, the matched token, and the line number (with a line excerpt), one violation per line, surfacing all violations in a single run rather than stopping at the first.

**Absent vs. empty token list.** If no token-list overlay is present, the guard SHALL pass trivially with a clear reason — a destination repo that has installed the plugin but not yet curated a token list MUST NOT get a failing result. If the overlay file IS present but yields no tokens, the guard SHALL FAIL with a clear message: a populated list broken by a later formatting change is a defect, not a fresh repo, and silently skipping it would disable the safety check with no signal. The failure message SHALL note that deleting the file is the way to intentionally disable the guard. The overlay supplies data to the guard; a missing overlay does not gate whether the guard runs, but a present-yet-empty one is treated as a broken list, not a trivial pass.

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
- **AND** that overlay lives in the repo's own `cla.io/` tree, outside the distributed plugin directory, so each destination repo supplies its own token list

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

The `cla` plugin SHALL support a single, repo-level **consolidated project-facts file** at `cla.io/project-facts.md` that holds the repo-wide facts shared across multiple skills — at minimum the workspace member list, the dev/build/test commands, the infrastructure ports, the affected-file map, the doc-sweep path list, and package/path names. It SHALL live in the `cla.io/` per-repo data tree, which is outside the distributed plugin directory, so the file is never carried between repos by an install and needs no additional exclusion. Each destination repo owns its own `cla.io/project-facts.md`.

A shared repo-wide fact SHALL exist in exactly one physical place — the consolidated file — and SHALL NOT be restated across per-skill overlays; a per-skill overlay or workflow that needs a shared fact SHALL reference it via a pointer to `cla.io/project-facts.md` rather than a copy. This one-physical-place rule is the canonical statement referenced by the **Per-skill project-context overlay**, **Project-specific overlay convention**, and **Skill fact/procedure separation** requirements.

Because the consolidated file is per-repo and may be absent (a fresh repo that has not yet run the context-refresh skill), a pointer to it SHALL degrade gracefully by **prompting the reader to run `/cla:sync-context`** to populate it, rather than failing. A pointer SHALL NOT keep an inline duplicate copy of the shared fact as its fallback — that would reintroduce the very duplication this requirement's one-physical-place rule exists to eliminate; the graceful-degradation instruction is the actionable prompt, not a second copy.

#### Scenario: Shared facts live in one file

- **WHEN** a repo-wide fact (e.g. the workspace member list, a dev command, a port, the affected-file map, or the doc-sweep path list) is recorded
- **THEN** it is written once in `cla.io/project-facts.md`
- **AND** it is not duplicated into any per-skill `cla.io/overlays/<skill>.md`

#### Scenario: The consolidated file is per-repo and never distributed

- **WHEN** the plugin is installed or updated in a destination repo
- **THEN** `cla.io/project-facts.md` is untouched by the install (it lives outside the distributed plugin directory)
- **AND** each destination repo supplies its own `cla.io/project-facts.md`

#### Scenario: A pointer degrades gracefully when the file is absent

- **WHEN** a skill body references `cla.io/project-facts.md` in a repo where that file does not exist yet
- **THEN** the reference prompts the reader to run `/cla:sync-context` to populate it (it does not carry an inline duplicate copy of the fact)
- **AND** the skill's procedure still runs rather than failing on the missing file

### Requirement: Consolidated domain-terminology file

The `cla` plugin SHALL support a single, repo-level **consolidated domain-terminology file** at `cla.io/terminology.md`, distinct in kind from `cla.io/project-facts.md`. Where the project-facts file holds mechanical, build-level facts, the terminology file holds **canonical internal-naming disambiguation**: one-sentence definitions for concepts specific to this repo's own codebase or product, each naming any rejected alias terms to avoid, in the entry format `**Term**: one-sentence definition — what it IS, not what it does. _Avoid_: rejected-alias-1, rejected-alias-2`. The terminology file is narrow by design — it SHALL NOT hold external, regulatory, or business-reference knowledge; a repo's own hand-authored glossary of that kind, if one exists, is untouched by this requirement and is never read, restructured, or superseded by it. It SHALL live in the `cla.io/` per-repo data tree, outside the distributed plugin directory, so it is never carried between repos by an install and needs no additional exclusion. Each destination repo owns its own `cla.io/terminology.md`, created **lazily** — only once the first term resolves, not pre-scaffolded empty by `cla-init`.

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

#### Scenario: The terminology file is never distributed across repos

- **WHEN** the plugin is installed or updated in a destination repo
- **THEN** `cla.io/terminology.md` is untouched by the install (it lives outside the distributed plugin directory)
- **AND** each destination repo supplies its own `cla.io/terminology.md`

### Requirement: Context-refresh skill

The `cla` plugin SHALL provide a **context-refresh skill** at `.claude/plugins/cla/skills/sync-context/SKILL.md` (a `SKILL.md`, invoked as `/cla:sync-context` per the plugin's namespacing convention) that reads the current repo and populates or reconciles the fact *content* of `cla.io/project-facts.md`. It SHALL extract facts by reading the repo's own manifests/config directly (an LLM-driven universal extractor), with **no stack-specific parser**, so it works across repos of differing tech stacks. It SHALL resolve the repo root via the plugin's standard repo-state resolution seam (`git rev-parse --show-toplevel`) so it writes to the correct `cla.io/` regardless of the working directory, creating the `cla.io/` directory if it does not exist.

The refresh skill SHALL be **self-sufficient**: when `cla.io/project-facts.md` is absent it SHALL create it, so running the skill alone on a fresh repo populates the facts (acting as fact-initialization) rather than requiring pre-existing content. It SHALL **propose** (for user confirmation, not silently apply) new `project-tokens.local.md` entries when it detects a new distinctive app/package token, following the same curation discipline the conformance guard's token list requires.

The refresh skill SHALL own fact **content** only: it populates `cla.io/project-facts.md` (the shared repo-wide facts) and the pointer lines in per-skill overlays. It SHALL NOT take over the structure-scaffolding role of `cla-init`, and the **skill-specific authored body** of a per-skill overlay (a skill's own incident history, bespoke checks, permission-set intent) remains human/LLM authored — `cla-init` scaffolds it as an empty stub, and it is filled independently of the refresh skill. `cla-init` remains unchanged — it scaffolds the `cla.io/` tree and empty per-skill overlay stubs and SHALL NOT populate facts. The documented onboarding order SHALL be the marketplace install (obtain the skills) then `cla-init` (structure) then `/cla:sync-context` (content), stated in the refresh skill's SKILL.md and `cla-init`'s SKILL.md.

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
- **THEN** the refresh skill's SKILL.md and `cla-init`'s SKILL.md state the order: marketplace install → `cla-init` → `/cla:sync-context`
- **AND** they note that the install provides the skills, `cla-init` scaffolds structure, and `/cla:sync-context` fills fact content

## REMOVED Requirements

### Requirement: Cross-repo update preserves the overlay

**Reason**: The `update-cla` file-sync mechanism is removed; distribution is exclusively the GitHub marketplace install, which never writes into a consuming repo, so there is no sync step from which overlays need protecting.
**Migration**: The overlay convention itself (fixed `cla.io/overlays/<skill>.md` paths, `*.local.md` markers) survives unchanged under the Project-specific overlay convention and Per-skill project-context overlay requirements; overlays live in the consuming repo and are untouched by a marketplace install by construction.

### Requirement: Sync provenance lockfile

**Reason**: The lockfile existed solely to give the sync engine per-file 3-way reconcile baselines; with the engine removed, `.cla-sync-lock.json` is deleted and no provenance is tracked.
**Migration**: Version provenance is the marketplace's pinned release tag (`.claude-plugin/marketplace.json` `ref` + `plugin.json` `version`, guarded by `test_marketplace_manifest.py`). Consuming repos delete any leftover `.cla-sync-lock.json` at their convenience; it is inert.

### Requirement: Three-way reconcile classification

**Reason**: Classification (`adapted` / `source-advanced` / `local-advanced` / `both-diverged`) only exists to merge per-file changes between a consumer's tree and a source tree; a marketplace install replaces the whole plugin snapshot, so there is nothing to classify.
**Migration**: A consuming repo's local strengths belong in `cla.io/` (overlays, `*.local.md`) which the install never touches; genuine improvements to portable core are contributed upstream via `/cla:report-upstream` instead of diverging locally.

### Requirement: Source-side deletion detection

**Reason**: Deletion detection compensated for file-sync's inability to remove files it no longer shipped; a marketplace install is a full snapshot, so removed files disappear on the next `/plugin marketplace update` without any bookkeeping.
**Migration**: None needed — snapshot semantics subsume it.

### Requirement: Source-agnostic provenance with a soft hub convention

**Reason**: Multi-source per-asset sync was a property of the lockfile's per-asset `source` field; with the engine and lockfile gone, the plugin has exactly one distribution source — the canonical repo's marketplace.
**Migration**: Cross-repo improvement flow is `/cla:report-upstream` (consumer → canonical issue) plus a normal release; per-asset multi-sourcing is retired without replacement.
