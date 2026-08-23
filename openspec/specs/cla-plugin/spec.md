# cla-plugin Specification

## Purpose

Specifies the architecture of the `cla` Claude Code plugin — the portable dev-workflow harness this
repo canonically hosts and distributes to other repos through its GitHub marketplace. Covers: the
core/state boundary and the two activation modes (in-place for this repo, marketplace snapshot for a
consumer); the repo-state resolution seam every plugin script must use;
the repo-neutral project-context overlay convention; the
fact/procedure separation every skill must observe and the mechanical guards that enforce it
(conformance guard, project-facts staleness guard); the project-data scaffolding (`cla-init`) and
context-refresh (`sync-context`) skills that populate a destination repo's `cla.io/` tree; and the
skill-authoring disciplines (progressive disclosure, thin-orchestrator execution) that keep the
synced core lean. This is the spec for the harness's own architecture, not for any downstream
consumer's project — a consuming repo's own facts live behind the overlays this spec defines, never
in this file.
## Requirements
### Requirement: Core/state boundary

The reusable dev-workflow harness core SHALL live in an in-repo plugin at `.claude/plugins/cla/` (manifest `.claude/plugins/cla/.claude-plugin/plugin.json` with name `cla`), containing only stateless, portable assets that a consuming repo can use: `skills/`, `agents/`, `hooks/`, `output-styles/`, and the shared `lib/` those skills invoke (see the **Shipped-asset boundary** requirement for what this excludes and why). Repo-local, machine-local, or external assets MUST NOT be moved into the plugin and SHALL remain project-level in one of three homes:

1. **The cla plugin's durable workflow *data* SHALL live under a single top-level `cla.io/` directory** — the retro ledgers (`cla.io/retro/*.jsonl`), the lessons-learned log (`cla.io/lessons-learned/`), shaped decisions (`cla.io/decisions/`), and captured feedback notes (`cla.io/feedback/`). This data is tool-neutral, first-class repo content and is deliberately NOT buried in the `.claude/` harness-config dotfolder.
2. **Claude Code harness config and other project-level assets SHALL remain under `.claude/`** — `worktrees/`, `settings.json` (project-specific hook wiring + env), `settings.local.json` (permissions), repo-local skills under `.claude/skills/`, and any other host-repo-specific commands/skills/assets a destination repo layers on top of the plugin.
3. **The plugin's own validation machinery SHALL live under a top-level `plugin-tests/` directory** in the canonical source repo — tests, mutation corpora, the mutation runner, the pytest configuration, and the checks that assert facts about this repo's own source. It is neither workflow data (it is not produced by running a workflow) nor harness config (it configures nothing at session time), which is why it is a third home rather than a corner of either of the first two. It exists only in the canonical source repo; a consuming repo has no counterpart.

#### Scenario: Core assets are in the plugin, state stays project-level

- **WHEN** the repo is inspected
- **THEN** the harness skills, agents, and guard hooks resolve from `.claude/plugins/cla/`
- **AND** the cla workflow data (`cla.io/retro/*.jsonl`, `cla.io/lessons-learned/`, `cla.io/decisions/`, `cla.io/feedback/`) lives under the top-level `cla.io/` directory
- **AND** `.claude/worktrees/`, `.claude/settings*.json`, `.claude/skills/`, and any other host-repo-specific project-level assets remain under `.claude/`, and none of the above is present inside `.claude/plugins/cla/`

#### Scenario: Validation machinery is a third home, outside the plugin

- **WHEN** the canonical source repo is inspected
- **THEN** the plugin's tests, mutation corpora, mutation runner, and pytest configuration live under the top-level `plugin-tests/` directory
- **AND** none of them is present inside `.claude/plugins/cla/`, under `cla.io/`, or under `.claude/` outside the plugin

### Requirement: In-place activation and namespacing

The `cla` plugin SHALL be activated in place via `claude --plugin-dir ./.claude/plugins/cla` **in the canonical repo (development mode)**, so its scripts and skills run from the live working tree while the harness itself is being developed. A **consuming repo** SHALL activate the plugin via the marketplace install (`claude plugin marketplace add crisradu75/logic-artisan` then `claude plugin install cla@cris-logic-artisan --scope project`), which runs from a read-only versioned snapshot in the plugin cache — workable because all repo-local workflow state lives under the repo's own `cla.io/` tree, outside the plugin directory, so a read-only install reads and writes it unchanged.

Each **harness workflow** — a workflow that carries a consuming repo's own work from idea to shipped change — SHALL be a skill (no thin command wrappers) and SHALL be invoked under the plugin namespace as `/cla:<skill>`. A workflow whose subject is instead **the plugin's own distribution** (per the **Shipped-asset boundary** requirement) is not a harness workflow: it SHALL live as a repo-local skill under `<repo>/.claude/skills/<name>/` in the canonical repo and SHALL be invoked bare as `/<name>`, carrying no plugin namespace, because a consuming repo has nothing for it to act on.

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

#### Scenario: A distribution workflow is invoked without the namespace

- **WHEN** the workflow that cuts this plugin's releases is invoked in the canonical repo
- **THEN** it resolves from `<repo>/.claude/skills/` and is invoked bare (e.g. `/release`), not as `/cla:release`
- **AND** it is absent from a consuming repo's skill list, because it never shipped

### Requirement: Repo-state resolution seam

Plugin scripts SHALL resolve repo locations independently of their own position in the tree, because the plugin's nested position under `.claude/plugins/cla/…` breaks any position-dependent resolver. Specifically: (a) scripts that read/write the retro dir (the shared writer `lib/log_run.py` and each retro loop's aggregator — `codify-retro/scripts/codify_aggregate.py` and `spec-to-pr-retro/scripts/spec_to_pr_aggregate.py`) SHALL resolve it as `CLAUDE_RETRO_DIR` when set, otherwise `<git rev-parse --show-toplevel>/cla.io/retro`; (b) scripts that resolve a repo root for other repo files (`probe_state.py` via `_git_common.py`) SHALL resolve it via `git rev-parse --show-toplevel`, NOT a fixed `Path(__file__).resolve().parents[N]` depth. Scripts MUST NOT rely on walking to a `.claude` ancestor of the script nor on `${CLAUDE_PROJECT_DIR}` (empty in the script environment). A skill-bundled file (one that ships WITH the plugin, e.g. `references/required-permissions.json`) SHALL be resolved skill-relative to the script, while a project-level target — including every overlay under `cla.io/overlays/` — SHALL be resolved from the repo root.

Each retro loop's aggregator SHALL carry a module basename distinct from every other aggregator in the plugin, **and each aggregator's test file SHALL carry a distinct basename as well**.

The reason is a **forward** one and SHALL NOT be recorded as a present import collision, because there is none: each retro test file loads its own aggregator by explicit file path under a distinct module name via `importlib.util.spec_from_file_location`, no test file imports an aggregator by bare module name, and the plugin's test scopes are executed as separate subprocesses — so no two aggregators, and no two aggregator test files, are ever resident in one interpreter. The requirement exists because the plugin's per-scope pytest split is consolidated into a **single** pytest scope, and two test files sharing the basename `test_aggregate.py` under one rootdir break pytest **collection** (a distinct failure from import shadowing). Distinct basenames are therefore a precondition of that consolidation, not a fix for a defect observable before it.

#### Scenario: A plugin script writes to the repo's retro dir

- **WHEN** a retro/state script runs from `.claude/plugins/cla/…` with `CLAUDE_RETRO_DIR` unset
- **THEN** it resolves the repo root via `git rev-parse --show-toplevel` and writes under that repo's `cla.io/retro/`

#### Scenario: Override is honored

- **WHEN** `CLAUDE_RETRO_DIR` is set to an absolute path
- **THEN** the script uses it directly and does not consult git

#### Scenario: A repo-root script resolves independently of depth

- **WHEN** a repo-root-consuming script (e.g. `probe_state.py`) runs from `.claude/plugins/cla/skills/spec-to-pr/scripts/`
- **THEN** it finds the repo root via `git rev-parse --show-toplevel` (not `parents[N]`)
- **AND** it resolves the repo's `cla.io/overlays/branch-prefix.local.md` from that repo root, never from its own position in the plugin tree

#### Scenario: The two retro aggregators do not share a module name

- **WHEN** the plugin's retro aggregators are enumerated
- **THEN** `codify-retro` and `spec-to-pr-retro` each name their aggregator script distinctly
- **AND** the **test file** for each aggregator is named distinctly too — no two test files anywhere in the plugin share the basename `test_aggregate.py`, so a single consolidated pytest rootdir can collect both
- **AND** every skill instruction, test, and cross-file path list that names an aggregator names the distinct one — including each test file's own `SCRIPT` path constant, the module docstrings that open `"""Tests for aggregate.py …"""`, and the `consistency-checks` path lists

### Requirement: Project-specific overlay convention

Project-specific content (repo-tuned review checks, monorepo-shaped agent prompts, repo paths) SHALL be contained in **repo-neutral overlay files** under `cla.io/overlays/`: one `<skill>.md` per consuming skill, plus any `*.local.md` siblings for a narrower per-repo setting. They live in the repo, NOT inside the plugin, for two reasons: a marketplace-installed plugin tree is a read-only cache a destination repo cannot write to, and every reader treats a missing overlay as the ordinary un-configured state, so an overlay the reader cannot reach degrades silently to a default rather than erroring. A generic skill body SHALL remain repo-agnostic and reference its overlay by the fixed repo-neutral path `cla.io/overlays/<skill>.md`. Each destination repo fills in its own overlay content behind that fixed path.

**Legacy location.** Overlays previously sat beside the skill at `references/project-context.md`, and that leaf name remains a recognized overlay marker so a repo mid-migration is neither re-synced over nor dropped from the staleness guard's scan. New overlays SHALL NOT be created there.

**Exception for repo-wide shared facts.** A fact that is *shared across multiple skills* (a repo-wide command, port, member list, path map, or doc list) MAY instead live once in the repo-level consolidated project-facts file `cla.io/project-facts.md` (per the **Consolidated project-facts file** requirement), rather than being co-located and restated in each consuming skill's `references/`. This is the sole exception to co-location, and it applies ONLY to that single repo-level shared file — per-skill overlays themselves remain co-located under the skill's `references/`. A per-skill overlay references such a shared fact by a pointer to `cla.io/project-facts.md`.

#### Scenario: Repo checks live in a repo-neutral overlay

- **WHEN** `review-change` or `project-review` runs
- **THEN** its generic body reads its repo-specific checks from `cla.io/overlays/<skill>.md` in the repo it is running in

#### Scenario: A generic skill references its overlay without naming the repo

- **WHEN** a generic `SKILL.md` (or a reference it reads, e.g. `checklist.md`) points at its project overlay
- **THEN** the reference is the fixed repo-neutral path `cla.io/overlays/<skill>.md`
- **AND** no hardcoded repository-name prefix appears in that reference

#### Scenario: A skill carries multiple local overlay files

- **WHEN** a skill needs more than one project-local overlay file alongside its `cla.io/overlays/<skill>.md`
- **THEN** each additional file is named with a `*.local.md` leaf suffix
- **AND** every such file is recognized as project-local overlay by the same convention

#### Scenario: A repo-wide shared fact lives in the consolidated file, not each overlay

- **WHEN** a fact is shared across multiple skills (e.g. a repo-wide command, port, member list, or the doc-sweep path list)
- **THEN** it lives once in `cla.io/project-facts.md` rather than co-located and restated in each skill's `references/`
- **AND** a per-skill overlay that needs it carries a pointer to `cla.io/project-facts.md`, while per-skill overlays otherwise remain co-located under `references/`

### Requirement: Guard hooks provided by the plugin

The generic git/worktree guard hooks SHALL be provided by the plugin via `.claude/plugins/cla/hooks/hooks.json`, which MUST use the top-level `{"hooks": {…}}` wrapper (a bare `{"<Event>": …}` shape loads without error but never fires). Hook commands SHALL locate their script via `${CLAUDE_PLUGIN_ROOT}` and the repo via `${CLAUDE_PROJECT_DIR}`. Any project-level hooks specific to the host repo (outside the plugin's generic guard set) SHALL remain wired in that repo's own `.claude/settings.json`, out of the plugin.

#### Scenario: A plugin guard hook fires

- **WHEN** a session with `--plugin-dir ./.claude/plugins/cla` triggers a matched tool call
- **THEN** the corresponding guard hook executes (verifiable via `/hooks` showing Source: Plugin)
- **AND** the hook resolves its script through `${CLAUDE_PLUGIN_ROOT}` and the repo through `${CLAUDE_PROJECT_DIR}`

#### Scenario: Wrapper shape is enforced

- **WHEN** `.claude/plugins/cla/hooks/hooks.json` is authored
- **THEN** its top level is a `"hooks"` object keyed by event name, not a bare event map

### Requirement: Skill fact/procedure separation

Every `cla` plugin skill SHALL separate **project-specific facts** from **generic procedure**, keeping only procedure in its synced core (`SKILL.md` and non-overlay `references/`) and placing every project-specific fact behind that skill's repo-neutral project-context overlay (`cla.io/overlays/<skill>.md`, per the Project-specific overlay convention) — OR, for a **repo-wide fact shared across multiple skills**, in the repo-level consolidated project-facts file `cla.io/project-facts.md` (per the **Consolidated project-facts file** requirement), referenced from the overlay by a pointer. The governing rule of thumb SHALL be **"extract a fact, keep a procedure."**

A **fact** (which MUST be extracted to the overlay or, when shared across skills, to `cla.io/project-facts.md`, never left in a synced core file) is any content whose value is specific to *this* repository, including but not limited to:
- concrete shell commands with repo-specific tokens (e.g. package-manager invocations, filtered workspace/test commands, app/server start commands, specific script paths);
- package, workspace, app, or directory names and file paths (e.g. `apps/*`, `packages/*`, a backend project dir);
- permission sets scoped to this repo's tools (e.g. a skill-bundled required-permissions list);
- incident, offense, or past-failure history particular to work done in this repo;
- product/domain prose describing this repo's applications, data, market, or concepts;
- fixed infrastructure values such as port numbers, service names, and env-var names tied to this repo's processes;
- enumerated lists of this repo's files, specs, or docs to touch.

A **procedure** (which SHALL remain generic in `SKILL.md` / non-overlay references) is content whose value is independent of any particular repo, including: workflow phases and their ordering; discipline, escalation, and stop/continue rules; verdict/size-gate logic; JSON/log schemas and their field contracts; the shape and structure of a review, plan, or report; and generic tool-usage patterns.

**Blended content** — a generic rule justified by a specific past incident, or a generic phase that names a repo command as its example — SHALL be split: the generic rule/phase stays in `SKILL.md` (reworded to be repo-agnostic, with a "see `cla.io/overlays/<skill>.md`" pointer where the concrete detail aids the reader), and the incident detail or concrete command moves to the overlay. Extraction SHALL preserve behavior — a skill run against a repo whose overlay is filled in MUST retain the same effective guidance it had before extraction (relocation of specifics, not loss of capability).

The **shared/skill-specific tie-break** SHALL be: a fact goes to `cla.io/project-facts.md` when it serves two or more skills OR names a repo-global command, port, workspace member, or path map; a fact stays in a skill's own overlay when it is an example chosen to illustrate *that* skill's prose, or is that skill's own incident history / bespoke checks / permission-set intent. This requirement applies to every skill that carries project specifics; skills that are already fully generic (no facts to extract) satisfy it trivially and need no overlay.

#### Scenario: A synced skill body carries no repo-specific facts

- **WHEN** any `cla` skill's `SKILL.md` or a non-overlay `references/` file is inspected after extraction
- **THEN** it contains no project-specific fact (no repo-specific command, package/path name, permission set, incident history, product prose, port, or repo file list)
- **AND** every such fact it previously carried is present in that skill's `cla.io/overlays/<skill>.md` overlay, or in `cla.io/project-facts.md` when the fact is shared across skills

#### Scenario: Procedure is preserved generically

- **WHEN** a skill's workflow phases, discipline/escalation rules, verdict logic, or schemas are inspected after extraction
- **THEN** they remain in `SKILL.md` / non-overlay references, reworded to be repo-agnostic rather than removed
- **AND** the skill's effective guidance is unchanged for a repo whose overlay is filled in

#### Scenario: A blended incident-justified rule is split

- **WHEN** a discipline rule in a skill is justified by a specific past incident in this repo
- **THEN** the generic rule stays in `SKILL.md`, reworded to be repo-agnostic
- **AND** the incident detail moves to that skill's `cla.io/overlays/<skill>.md` overlay
- **AND** the generic rule points at `cla.io/overlays/<skill>.md` where the concrete detail aids the reader

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

Each `cla` skill that carries project specifics SHALL route them through that skill's single per-skill overlay file at `cla.io/overlays/<skill>.md` — living in the repo, not the plugin, because a marketplace-installed plugin tree is a read-only cache that a destination repo cannot write to, and because every reader treats a missing overlay as the ordinary un-configured state, so an unreachable overlay fails silently. Recognized by the **Project-specific overlay convention**, which already governs the overlay's fixed repo-neutral path, its repo-name-free referencing, and the `*.local.md` leaf-suffix form for additional local files. This requirement does not restate those mechanics; it builds on them by fixing the overlay's **role and shape** so the file can be **stubbed by a scaffolding step and linted by a conformance guard**.

An overlay file SHALL be self-describing enough to be regenerated as an empty stub and filled in per destination repo. It SHALL open with a heading naming the owning skill and its role as a project overlay, and SHALL organize its content under headed sections that map to the fact categories the owning skill needs (for example: repo commands, package/path names, permission sets, incident/offense history, product/domain prose, infrastructure values, and repo file lists — only those the skill actually uses). A destination repo with an empty or absent overlay SHALL still run the skill's generic procedure; the overlay supplies the repo-specific detail, it does not gate the procedure.

A per-skill overlay SHALL contain only the facts **specific to that skill** (for example its own incident/offense history, its bespoke review checks, its permission-set intent). **Repo-wide facts shared across skills** SHALL NOT be restated in a per-skill overlay; per the one-physical-place rule of the **Consolidated project-facts file** requirement they live once in `cla.io/project-facts.md`, and a per-skill overlay that needs such a fact SHALL carry a pointer to `cla.io/project-facts.md` rather than a copy.

#### Scenario: The overlay is stubbable and lintable

- **WHEN** a scaffolding step generates an empty overlay for a skill, or a conformance guard inspects it
- **THEN** the overlay's expected shape is a heading naming the owning skill plus headed sections for the fact categories that skill uses
- **AND** the generic `SKILL.md` remains valid and runnable against an empty stub (the overlay supplies detail, it does not gate the procedure)

#### Scenario: An empty or absent overlay does not gate the procedure

- **WHEN** a skill runs in a destination repo whose `cla.io/overlays/<skill>.md` is an empty stub or absent
- **THEN** the skill's generic procedure still runs to completion
- **AND** only the repo-specific detail the overlay would otherwise supply is missing (the overlay supplies detail, it does not gate the procedure)

#### Scenario: A per-skill overlay holds only skill-specific facts

- **WHEN** a per-skill `cla.io/overlays/<skill>.md` is authored or trimmed
- **THEN** it contains only facts specific to that skill plus, where it needs a repo-wide fact, a pointer to `cla.io/project-facts.md`
- **AND** it does not restate a shared repo-wide fact that lives in `cla.io/project-facts.md`

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

The `cla` plugin SHALL include a conformance checker that mechanically enforces the fact/procedure separation (the Skill fact/procedure separation and Project-specific overlay convention requirements). The checker SHALL be a generic, repo-agnostic program that fails when any **non-overlay synced core file** contains a project-specific token, where the token list is itself a per-repo project overlay. The checker SHALL obey the same fact/procedure split it enforces: the checker is generic *procedure*; the token list is a repo-specific *fact* held in an overlay.

**Home and portability.** The checker SHALL live at `.claude/plugins/cla/skills/_shared/scripts/check_no_project_tokens.py` — in the shared area that belongs to no single skill, because it enforces a rule about the whole plugin — and SHALL be invocable directly as `python3 <path-to-checker>`, requiring no pytest and no test scope in the repo that runs it. It reads the **consuming repo's** data (the token-list overlay in that repo's `cla.io/` tree), which is why it is a skill helper rather than a test: a consuming repo has no test gate over the plugin cache, so a checker filed as a pytest module is unreachable there in practice. Because the marketplace install distributes the entire `.claude/plugins/cla/` directory as one versioned snapshot, the checker reaches every destination repo by construction, with no per-file enumeration required. **Known coverage gap:** that same whole-directory distribution means files outside the checker's scan roots ship to consumers unscanned. Once the plugin's validation machinery moved out (per the **Shipped-asset boundary** requirement), that gap narrowed to `lib/` alone — the `*-checks/` scopes and both runners no longer ship at all, so they can no longer carry a token to a consumer. The residual gap SHALL be recorded as a tracked follow-up rather than silently carried. The checker's **scan roots SHALL name only directories that exist in the shipped tree**: the iteration skips a missing root silently, so a stale entry shrinks the scan with no signal and produces a clean result that covered less than it claims. The checker SHALL NOT be implemented as a Claude Code hook and SHALL NOT block or interrupt authoring; it runs on demand — notably at skill-authoring time, per the authoring validation checklist. The checker SHALL resolve the plugin tree relative to its own file location (a fixed internal layout identical in every repo), not via any repo-specific absolute path or repository name; any positional fallback depth it uses SHALL correspond to its actual location in the tree.

**Checks performed.** A single invocation SHALL perform every check the guard is responsible for and SHALL NOT stop at the first that fails: (a) the prose scan for project tokens over synced-core `SKILL.md` and `references/**/*.md`; (b) the source scan for project tokens over the plugin's scanned source roots; (c) the hardcoded absolute-developer-path scan over that same source; and (d) the readability check that every file the scans claim to have inspected was actually readable. Check (d) is not optional: an unreadable file is silently "clean" to every other scan, so it is what keeps the others from passing vacuously.

**Scan scope.** The checker SHALL scan every `SKILL.md` and every `references/**/*.md` file under `.claude/plugins/cla/skills/**`. It SHALL exclude from the scan: (a) overlay files — any file whose leaf name is exactly `project-context.md` or ends with `.local.md` (this covers every extracted fact overlay and the checker's own token-list file); (b) non-markdown / asset files; and (c) each scanned file's leading YAML frontmatter block (the content between the opening `---` on line 1 and its closing `---`). Because the exclusion is by leaf name, the token-list overlay is never flagged by the checker reading it. Frontmatter is excluded because a skill's `description:` / `argument-hint:` is trigger metadata that legitimately names the host repo and its apps so the skill fires — it is not portable procedure prose. The checker SHALL still report accurate 1-based line numbers for body violations (it skips frontmatter for matching, not for line counting).

**Token list as a per-repo overlay.** The token list SHALL live at `cla.io/project-tokens.local.md` — per-repo data, held with the rest of it and outside the plugin directory entirely, so a marketplace install never carries one repo's tokens to another, each destination repo supplies its own, and neither of the checker's scans can reach it. Its `*.local.md` leaf name keeps it recognizable under the repo-neutral overlay convention. The checker SHALL read the list as data — it MUST NOT hard-code any token in the checker source. The list SHALL be curated to distinctive, repo-specific compound tokens (e.g. package/app paths and product/tool names) and MUST NOT include generic words that legitimately appear in portable procedure prose, so false positives are controlled by curation rather than by the matcher. Matching SHALL be case-insensitive.

**Failure output and exit status.** When a scanned core file contains a listed token, the checker SHALL report each violation with the offending file's repo-relative path, the matched token, and the line number (with a line excerpt), one violation per line, surfacing all violations in a single run rather than stopping at the first, and SHALL exit **non-zero**. A clean run SHALL exit **0** and SHALL state what was scanned and how many files, so that a scan which inspected nothing is visible rather than indistinguishable from a clean result. The exit status SHALL distinguish "violations were found" from "the checker could not do its job" (bad arguments, or an input present but unreadable), so a caller scripting the result can tell a leak from a broken run.

**Absent vs. empty token list.** If no token-list overlay is present, the checker SHALL exit 0 with a clear reason — a destination repo that has installed the plugin but not yet curated a token list MUST NOT get a failing result. If the overlay file IS present but yields no tokens, the checker SHALL FAIL with a clear message: a populated list broken by a later formatting change is a defect, not a fresh repo, and silently skipping it would disable the safety check with no signal. The failure message SHALL note that deleting the file is the way to intentionally disable the checker. The overlay supplies data to the checker; a missing overlay does not gate whether the checker runs, but a present-yet-empty one is treated as a broken list, not a trivial pass.

#### Scenario: A project token in a synced core file fails the guard

- **WHEN** a non-overlay `SKILL.md` or `references/**/*.md` file under `.claude/plugins/cla/skills/**` contains a token listed in the per-repo token-list overlay
- **THEN** the checker exits non-zero
- **AND** the output reports the offending file's repo-relative path, the matched token, and the line number with an excerpt

#### Scenario: A skill's frontmatter description is exempt from the scan

- **WHEN** a scanned `SKILL.md` names a project-specific token only inside its leading YAML frontmatter block (e.g. the `description:` field naming the host repo so the skill triggers)
- **THEN** the checker does not flag that occurrence
- **AND** a token appearing in the same file's body (after the closing frontmatter `---`) is still reported, with its accurate 1-based line number

#### Scenario: Overlay files are exempt from the scan

- **WHEN** the checker scans the plugin's skill files
- **THEN** any file whose leaf name is exactly `project-context.md` or ends with `.local.md` is excluded from the scan (including the token-list overlay itself and every extracted fact overlay)
- **AND** a project token appearing inside such an overlay file does not fail the checker

#### Scenario: The token list is per-repo data, not hard-coded

- **WHEN** the checker runs
- **THEN** it reads its tokens from the `*.local.md` token-list overlay rather than from any list embedded in the checker source
- **AND** that overlay lives in the repo's own `cla.io/` tree, outside the distributed plugin directory, so each destination repo supplies its own token list

#### Scenario: An absent token list is a trivial pass

- **WHEN** the checker runs in a repo with no token-list overlay present
- **THEN** the checker exits 0 with a clear reason
- **AND** it does not fail merely because the token list has not yet been curated

#### Scenario: A present-but-empty token list fails

- **WHEN** the checker runs with a token-list overlay that is present but yields no tokens (e.g. broken by a formatting change)
- **THEN** the checker exits non-zero with a clear message
- **AND** the message indicates that deleting the file is the way to intentionally disable the checker

#### Scenario: The plugin tree is resolved relative to the checker's own location

- **WHEN** the checker resolves the plugin tree to scan
- **THEN** it derives the root by walking up from its own file's location (`Path(__file__)`), a fixed internal layout identical in every repo
- **AND** it does not use any repo-specific absolute path or repository name to find the plugin tree
- **AND** any positional (`parents[N]`) fallback it falls back to resolves to the plugin root from the checker's actual location, not from a location it previously occupied

#### Scenario: The checker is a program, not an authoring-time hook

- **WHEN** the checker is added to the plugin
- **THEN** it is a script invocable as `python3 <path>` that needs no pytest and no test scope in the repo running it
- **AND** it is not a `PreToolUse` (or other) hook and never blocks or interrupts editing

#### Scenario: A single run performs every check and reports all of them

- **WHEN** the checker runs and more than one of its checks finds violations
- **THEN** violations from every check are reported in that one run
- **AND** the run does not stop at the first check that fails

#### Scenario: An unreadable file is a failure, not a clean result

- **WHEN** a file inside the checker's scan roots cannot be read
- **THEN** the checker reports it rather than counting it as scanned-and-clean
- **AND** the run does not exit 0

#### Scenario: Every scan root names a directory that still ships

- **WHEN** the checker's source scan roots are enumerated
- **THEN** each one resolves to a directory present in the shipped plugin tree
- **AND** no entry names a directory that has been moved out, which the iteration would skip silently while still reporting a clean result

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

### Requirement: Project-facts staleness guard

The `cla` plugin SHALL include a **portable staleness checker** — a program at `.claude/plugins/cla/skills/sync-context/scripts/check_fact_paths.py`, invocable as `python3 <path-to-checker>` and requiring no pytest — that fails when any **repo-relative path** named in `cla.io/project-facts.md` or in a per-skill `cla.io/overlays/<skill>.md` no longer resolves on disk (as either a file or a directory). It lives with `sync-context` because it lints exactly what that skill produces, and it reads the **consuming repo's** data, which is why it is a skill helper rather than a test: a consuming repo has no test gate over the plugin cache. The checker SHALL resolve the **repo root** from the process, via `git rev-parse --show-toplevel` with a fallback that never accepts the user's global `~/.claude`, since the paths it checks are repo-relative and `cla.io/project-facts.md` lives at the repo root, outside the plugin tree — it SHALL NOT assume the plugin-root resolution the conformance checker uses, and it SHALL NOT resolve the repo from a fixed depth relative to its own file. It SHALL report every stale path (file, line, and the path) one per line in a single run rather than stopping at the first.

**Exit status.** A clean run SHALL exit **0** and SHALL state what was scanned and how many files, so a scan that inspected nothing is visible rather than indistinguishable from a clean result. A run that finds stale paths SHALL exit **non-zero** after naming every one of them. The exit status SHALL distinguish "stale paths were found" from "the checker could not do its job" (bad arguments, or an input present but unreadable), so a caller scripting the result can tell a stale path from a broken run.

The checker SHALL be stack-agnostic: it checks path existence only and SHALL NOT parse any stack-specific config (`pnpm-workspace.yaml`, `Cargo.toml`, etc.), and the set of recognized top-level path prefixes SHALL be **derived from the repo's own top-level entries** (not a hardcoded list), so the checker ports to a repo of any layout. If `cla.io/project-facts.md` is absent, the checker SHALL exit 0 with a stated reason (a fresh repo that has not yet run `/cla:sync-context` MUST NOT get a failing result).

The checker SHALL extract path candidates conservatively — treating a token as a repo-relative path only when it clearly is one: it contains a path separator; is not a URL, `~`-path, glob, or placeholder; and its first segment names an actual top-level entry in the repo. Before existence-checking, it SHALL strip surrounding backticks/punctuation and any trailing `:line[:col]` suffix. On an ambiguous token it SHALL err toward **not** flagging (a false staleness failure trains people to ignore the checker).

The checker checks **path existence only**; it does NOT validate the non-path mechanical facts the refresh skill produces (commands, ports, member counts) — those are kept fresh by `/cla:sync-context` and human review, not by this checker. It also does not detect a fact duplicated between `cla.io/project-facts.md` and an overlay. These limits SHALL be stated in the checker so its coverage is not overstated.

#### Scenario: A stale path in the facts file fails the guard

- **WHEN** `cla.io/project-facts.md` or a per-skill overlay names a repo-relative path that no longer exists on disk (as file or directory)
- **THEN** the checker exits non-zero
- **AND** it reports the offending file, the line number, and the stale path, one violation per line, surfacing all stale paths in a single run

#### Scenario: The guard is stack-agnostic and repo-derived

- **WHEN** the checker runs
- **THEN** it checks only whether named repo-relative paths resolve on disk, parsing no stack-specific config
- **AND** the top-level path prefixes it recognizes are derived from the repo's own top-level entries, not a hardcoded list

#### Scenario: An ambiguous non-path token is not flagged

- **WHEN** a token in a scanned file contains no path separator, or is a URL / glob / placeholder, or its first segment is not an actual top-level repo entry
- **THEN** the checker does not treat it as a repo-relative path and does not flag it
- **AND** a directory path, and a path written with a trailing `:line` suffix or surrounding punctuation, is still resolved correctly (existence-checked after stripping)

#### Scenario: The checker runs as a program against the consuming repo

- **WHEN** a consuming repo invokes the checker as `python3 <path-to-checker>` from within that repo
- **THEN** it resolves that repo as its root and scans that repo's `cla.io/` files
- **AND** it does not require pytest, a test scope, or any configuration in the consuming repo

#### Scenario: A clean run states what it scanned

- **WHEN** the checker completes without finding a stale path
- **THEN** it exits 0 and reports how many files it scanned
- **AND** a run that scanned zero files is distinguishable from one that scanned files and found nothing stale

### Requirement: Skill token-efficiency disciplines

cla-plugin skills SHALL be authored to minimize the static token cost of the skill definition, and orchestrator/multi-phase skills SHALL additionally be executed to minimize the runtime context they accumulate — both without weakening correctness-gating behavior. Two disciplines are load-bearing:

1. **Progressive disclosure of skill definitions** (applies to every skill large enough to have movable content). A skill's `SKILL.md` SHALL keep inline ONLY the content that must be in context for every run: correctness-gating invariants, hoisted skill-level rules, phase order, caps, and the autonomy/halt contract — each stated as a one-liner where possible. Mechanics (step-by-step procedures), rationale, templates, and examples SHALL live in on-demand `references/*.md` files (per-phase or per-topic; the requirement is a mandatory reference-read step, NOT a specific `references/<phase>.md` filename pattern). A multi-phase skill SHALL give each phase a mandatory "read its reference file first" step so the executing agent loads that phase's mechanics on demand rather than carrying every phase's mechanics inline for the whole run. Correctness-gating invariants MUST NOT be relocated out of the inline `SKILL.md` context — each phase's inline stub SHALL remain self-sufficient for its own invariant even if the phase's reference file is not read. Any repo-specific content moved out of `SKILL.md` (worked examples naming real symbols/files, dated incidents) SHALL be routed to a project overlay (`cla.io/overlays/<skill>.md` / `*.local.md` / `cla.io/project-facts.md`), NOT into a generic synced-core reference file, per the existing **Skill fact/procedure separation** and **Project-specific overlay convention** requirements. The authoring recipe for this transformation — the keep-inline/move boundary, the checklist of correctness-gating invariants that commonly get dropped during a restructure, and the validation steps — is `.claude/plugins/cla/skills/_shared/references/skill-authoring.md`.

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

### Requirement: Review-fix evidence gate

A skill that applies fixes for review findings SHALL require, before the commit that lands those fixes, that the fix be shown to be load-bearing: break what the fix touches and confirm a test fails. This gate SHALL be stated as **procedure the agent performs**, and a shipped skill SHALL NOT discharge it by mandating the invocation of a runner at the plugin root, because a consuming repo receives only the plugin's shippable assets and such a path may not resolve there.

The gate SHALL preserve, in the procedure text, the reasoning that makes it more than ceremony: that a fix for a Critical/Important finding is a change like any other and earns the same evidence the original code needed; that "the reviewer's finding is now handled" is not that evidence; that what is broken MUST be **what the fix touches**, not only what it targets, because correcting one return path routinely breaks another; and that a clean run is evidence about the mutants the author thought of and nothing else. A surviving mutant SHALL be fixed, or named in the skill's terminal report with a reason.

#### Scenario: The gate is stated without a plugin-root runner invocation

- **WHEN** a shipped skill's review-fix step states the mutation gate
- **THEN** the step describes the procedure to perform (break what the fix touches, confirm a test fails)
- **AND** it names no `${CLAUDE_PLUGIN_ROOT}` runner script to invoke

#### Scenario: The obligation survives the loss of its tooling

- **WHEN** the plugin no longer ships a mutation runner
- **THEN** the gate remains required before the fix commit
- **AND** an unresolved surviving mutant is still either fixed or named in the terminal report with a reason

#### Scenario: The named precedents are retained

- **WHEN** the gate's text is revised
- **THEN** it still states that the break must cover what the fix touches rather than only what it targets
- **AND** it still states that a clean run is evidence only about the mutants the author thought of

### Requirement: Shipped-asset boundary

The plugin directory `.claude/plugins/cla/` SHALL contain **only assets a consuming repo can use** —
skills it can invoke, agents and hooks that fire in its sessions, output styles it renders, scripts
those skills call, and the manifest and README that describe them. This is a structural obligation
rather than a convention, because the `cla` plugin is distributed as a `git-subdir` marketplace
entry, whose source descriptor supports `url`, `path`, `ref` and `sha` and **no exclusion field**:
everything under `path` ships, so what lives there is the only lever.

**What is excluded, and where it lives.** The plugin's own validation machinery — every test
directory, every mutation corpus, every pytest configuration, the mutation runner, and the checks
that assert facts about this repo's own source — SHALL live **outside** the plugin directory, at
`<repo>/plugin-tests/` in the canonical source repo. It SHALL be organised as a **single pytest
scope** with one `pyproject.toml`, and the repo's verification gate SHALL be a bare `pytest`
invocation over that scope; the plugin SHALL NOT ship an aggregating test runner, because a single
scope has nothing to aggregate. A separately-configured Node test suite MAY live in the same dev
tree and be run by its own command.

**Source-repo-only marking is by construction, not by declaration.** Because the dev tree is never
published, every asset in it is source-repo-only inherently. The plugin SHALL NOT carry per-directory
marker files declaring an asset source-repo-only, nor a guard that checks such markers, nor
skip logic in a runner that reads them — a mechanism whose whole subject is "which shipped assets do
not really ship" has no subject once nothing dev-only ships.

**A workflow about the plugin's own distribution is not a plugin workflow.** A skill whose subject is
publishing this plugin — editing the marketplace catalog at the source repo's root, editing that
repo's own release line, or cutting this plugin's release tags — operates on assets a consuming repo
does not own and cannot act on. Such a skill SHALL be a repo-local skill under
`<repo>/.claude/skills/<name>/` rather than a plugin skill, and SHALL resolve its paths repo-relative
rather than through `${CLAUDE_PLUGIN_ROOT}`.

**Dangling references are part of the boundary.** When an asset moves out of or is deleted from the
plugin, every shipped file that names it — a skill instruction, a precondition, a scanner's root
list — SHALL be re-pointed or pruned in the same change. A scanner that silently skips a root that no
longer exists SHALL have that root removed from its list rather than left to shrink the scan without
signal.

**How the boundary is enforced.** This boundary SHALL be verified mechanically at release time, by
the **Release-time shipped-asset scan** required of the publication workflow — not by a guard in the
repo's test suite. Enforcement at the publication gate is chosen because that is where the
consequence becomes irreversible: a published tag is what a consumer has already fetched and is never
moved, so the check belongs at the last point before that. The accepted cost is that drift
introduced between releases is not detected until the next one; the boundary is therefore a rule the
repo is expected to hold to while editing, with the scan as the backstop rather than the enforcement
of first resort.

**Documentation is inside the boundary, not adjacent to it.** A statement in this repo's own
documentation about what reaches a consuming repo — which assets ship, which checks fire downstream,
what a consumer can invoke — SHALL be true of the published tree. Such a statement SHALL NOT be
carried in a softened or narrowed form once it is false; it SHALL be deleted or replaced with what
is true. A false claim about the consumer's tree is the same defect class as a mis-shipped asset,
because both mislead about what the consumer received, and neither is visible from inside this repo.

#### Scenario: The published tree carries no validation machinery

- **WHEN** the contents of `.claude/plugins/cla/` are enumerated
- **THEN** no test directory, mutation corpus, `pyproject.toml`, or mutation runner is present
- **AND** every remaining file is an asset a consuming repo can invoke, read, or have fire on its behalf

#### Scenario: The dev tree is one scope with a bare gate

- **WHEN** the repo's test suite is run
- **THEN** it is invoked as a bare `pytest` over `<repo>/plugin-tests/`, needing no aggregating runner
- **AND** the dev tree carries exactly one `pyproject.toml`

#### Scenario: No source-repo-only marker mechanism survives

- **WHEN** the plugin and the dev tree are inspected
- **THEN** no per-directory source-repo-only marker file exists
- **AND** no guard asserts the presence or contents of such markers, and no runner skips a scope based on one

#### Scenario: The release workflow is repo-local

- **WHEN** the workflow that publishes this plugin is invoked
- **THEN** it resolves as a repo-local skill under `<repo>/.claude/skills/`, not under the plugin namespace
- **AND** it references its own files by repo-relative paths rather than `${CLAUDE_PLUGIN_ROOT}`

#### Scenario: A scan root removed from the tree is removed from the scanner

- **WHEN** a directory named in a shipped scanner's root list is moved out of the plugin
- **THEN** that entry is removed from the scanner's root list in the same change
- **AND** the scanner does not silently skip it and report a smaller scan as a clean result

#### Scenario: The boundary is checked at the publication gate

- **WHEN** a release of the plugin is prepared
- **THEN** the boundary is verified by the release-time shipped-asset scan before any tag is cut
- **AND** the repo's test suite does not carry a second guard duplicating that check

#### Scenario: A false claim about the consumer's tree is deleted, not reworded

- **WHEN** a statement in this repo's documentation asserts that some asset ships to, or fires in, a consuming repo, and the asset no longer does
- **THEN** the statement is removed rather than narrowed or qualified
- **AND** any surrounding text that remains true is preserved unchanged

### Requirement: Release-time shipped-asset scan

The workflow that publishes this plugin SHALL verify the **Shipped-asset boundary** mechanically
before cutting a tag, as a precondition alongside the others it already enforces (on the default
branch, working tree clean, up to date with the remote, test gate green, work reviewed and merged).
The scan SHALL be performed at release time rather than in the repo's test suite, because that is
where the consequence lands: a tag is what a consumer fetches, and a published tag is never moved.

**Structural allowlist, not a denylist.** The scan SHALL enumerate every file that would be
published and SHALL fail any file that does not match a **declared shape** on a fixed allowlist,
naming that file. It SHALL NOT be expressed as a list of forbidden shapes. A denylist detects only
the shapes its author anticipated, and every asset class the boundary was written about — the
aggregating test runner, the mutation runner, the source-repo-only markers, the source-drift
checker, and the publication workflow's own skill file — has a shape that no reasonable denylist of
test artifacts would name.

**Enumeration source.** The scan SHALL enumerate the published set as the repository's **tracked**
files under the plugin directory, because the plugin is published from the repository and tracked
files are exactly the files that ship. It SHALL NOT enumerate the working directory, which contains
untracked build and cache artifacts that never reach a consumer.

**The allowlist grows only with a stated reason.** Each allowlist entry SHALL carry a recorded
reason for the shape it admits, and the entry count SHALL be capped by a companion check at its size
when the convention landed, so the list can shrink freely but can grow only in a change that raises
the cap deliberately. A pattern added without a reason, or a cap raised silently, converts the
allowlist into a formality.

**A declared shape SHALL be narrow enough to exclude what the boundary excludes.** An entry
that admits any file at any depth beneath a directory, or that admits a compound extension whose
final segment happens to be allowed, re-opens the hole the allowlist exists to close while still
reporting a clean scan. Each entry SHALL be written so that a dev-asset shape placed inside an
otherwise-shipped directory is still rejected, and the allowlist's coverage SHALL be demonstrated
against planted files of each excluded shape rather than asserted.

**Refusal, not warning.** When the scan finds a file matching no declared shape, the publication
workflow SHALL refuse to proceed and SHALL name every offending file in one run rather than stopping
at the first. It SHALL NOT offer to continue, and the offending file SHALL NOT be removed as part of
the release.

**A scan that inspected nothing is a failure.** The scan SHALL report how many files it examined,
and SHALL exit with a distinct "could not run" status — separable from both "clean" and "violations
found" — when the enumeration is empty or the enumeration command fails. An empty enumeration
reported as zero violations is indistinguishable from a clean tree and would certify the tree it
never read.

**The enforcement window is release-time only, and that is a stated tradeoff.** Drift introduced
between two releases SHALL NOT be expected to surface before the next release. This is accepted in
exchange for the check firing at the one deliberate gate the repo already has, rather than adding a
guard to the suite.

**The scan is not a shipped asset.** The scan SHALL live outside the plugin directory, with the
repo-local publication workflow it serves. Placing the check against shipping unusable assets inside
an asset a consumer cannot use would make it the first thing the check should have caught.

#### Scenario: An undeclared file shape blocks the release

- **WHEN** the publication workflow runs its preconditions and a tracked file under the plugin directory matches no declared shape on the allowlist
- **THEN** the workflow refuses to proceed and names that file by its repo-relative path
- **AND** no version bump is written and no tag is cut

#### Scenario: Every offending file is named in one run

- **WHEN** more than one tracked file under the plugin directory matches no declared shape
- **THEN** all of them are reported in that single run
- **AND** the scan does not stop at the first one

#### Scenario: The scan refuses to certify an empty enumeration

- **WHEN** the scan's enumeration of the published set yields no files, or the enumeration command fails
- **THEN** the scan reports a "could not run" status distinct from both a clean result and a violations result
- **AND** it does not report zero violations

#### Scenario: A clean scan states what it examined

- **WHEN** every enumerated file matches a declared shape
- **THEN** the scan reports the number of files examined and the number of patterns applied
- **AND** the publication workflow proceeds to its remaining preconditions

#### Scenario: The allowlist is enumerated with a reason per entry

- **WHEN** the allowlist is inspected
- **THEN** each entry records the reason the shape it admits is a consumer-usable asset
- **AND** a companion check caps the number of entries, so an entry can be added only by raising the cap in the same change

#### Scenario: The scan enumerates tracked files, not the working directory

- **WHEN** the plugin directory contains untracked cache or build artifacts
- **THEN** the scan does not report them, because they are not part of what is published
- **AND** a tracked file of an undeclared shape is still reported

#### Scenario: The scan lives outside the published tree

- **WHEN** the contents of the plugin directory are enumerated
- **THEN** the scan itself is not among them
- **AND** it resolves from the repo-local publication workflow's own directory

#### Scenario: A dev-asset shape inside an allowed directory is still rejected

- **WHEN** a test file, a pytest configuration, or a mutation corpus is placed inside a directory whose other contents are legitimately shipped
- **THEN** the scan rejects it and names it, because no declared shape admits it
- **AND** the allowlist is not satisfied by a broad directory or extension wildcard that would have accepted it

