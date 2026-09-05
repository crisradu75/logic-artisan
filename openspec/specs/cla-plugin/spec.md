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

### Requirement: A retro aggregator survives a malformed record and counts what it skipped

A retro aggregator SHALL treat a malformed record as one lost record, never as a lost run. Its input is a ledger every producer writes as prose instructing a model, so a record of an unexpected shape is the expected case rather than the exceptional one; an aggregator that aborts on one hands the whole repository's retrospective to whichever record is worst. Measured before this requirement existed: a single record carrying a count where a list belonged aborted the aggregate for a repository holding 26 runs, and that repository was one of only two with retros in its history.

**Every drift class an aggregator warns about SHALL also be tallied into its structured output.** The two are not alternatives. A warning is written to a stream nobody reads after the fact, while the JSON is what the retro reasons from — so a class that only warns is invisible at exactly the moment it matters, and the metric it degraded reads identically to one computed over every record. This is not a new rule: `codify_aggregate.py`'s module docstring already states it, and this requirement makes it binding on both aggregators rather than on whichever one happened to be written more carefully.

**A count that skipped records SHALL be discoverable beside the count of records read.** `runs_analyzed` reporting N while a phase metric ran on fewer than N is not a defect in the metric; it becomes one only when nothing in the output says so. Measured: 20 records across three repositories were dropped from every phase-derived metric while the reported sample size stayed whole.

**An aggregator SHALL be able to read more than one ledger in a single run, and SHALL NOT attribute a multi-ledger result to a single ledger's path.** A retrospective's conclusions are bounded by its sample, and the repository where a loop is designed is routinely the one with the fewest runs of it — measured here at 8 records against a fleet of 156, where the local sample put round-cap exhaustion at 4 of 5 and the fleet put it at 6 of 129. Naming one path for a result drawn from several is worse than naming none, because it reads as provenance.

#### Scenario: One malformed record does not abort the aggregate

- **WHEN** a ledger holds a record whose field carries a different container type than the aggregator expects
- **THEN** the aggregator skips that field, analyzes every other record, and exits successfully
- **AND** it does not abort, and does not return an empty result for the whole ledger

#### Scenario: A skipped record is counted, not only warned about

- **WHEN** an aggregator skips a field because its container shape drifted
- **THEN** the drift is tallied into the structured output, naming the field
- **AND** the tally is not satisfied by a message on the diagnostic stream alone

#### Scenario: A degraded sample is visible beside the reported one

- **WHEN** some records are dropped from a metric while the reported record count includes them
- **THEN** the output carries a count of the records that drifted, so a reader can tell a whole sample from a partial one
- **AND** a clean ledger reports zero there rather than omitting the field, so zero is a measurement rather than an absence

#### Scenario: Several ledgers aggregate into one result

- **WHEN** an aggregator is given more than one ledger path in a single run
- **THEN** it analyzes the records of all of them together
- **AND** the output names every path it read
- **AND** it does not report a single-ledger provenance field for a result drawn from several

#### Scenario: The single-ledger contract is unchanged

- **WHEN** an aggregator is given one ledger path, or none at all
- **THEN** it resolves and reports that one path exactly as it did before multi-ledger reading existed
- **AND** a caller written against the single-ledger output continues to work unmodified

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

**Source scan scope.** The scan-scope rule above governs the PROSE scan alone. The source scan SHALL select files by suffix under the scan roots: every `.py` and every `.json` anywhere beneath them, plus every `.md` under `agents/` or `output-styles/`. It SHALL apply the same overlay exclusion, and SHALL skip bytecode and cache directories, because a stale artifact still holds the string it was compiled from and would report a leak already fixed in source. The frontmatter exemption SHALL apply only to the `.md` files, which are the only ones that have frontmatter. `.json` is in scope because a shipped configuration file may carry English prose in comment keys, and prose in synced core is what this guard exists to catch; the suffix selects files under the scan roots only, so a manifest lying outside every root is NOT drawn in by it and is covered by the marketplace-manifest guard instead. A shipped file the source scan's suffix rule does not reach SHALL be recorded as a deliberate exemption with a stated reason rather than left as an unnoticed gap, and that record SHALL fail when a scanner has since grown to reach the file, so an exemption cannot outlive its reason.

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

#### Scenario: A project token in a shipped JSON file fails the guard

- **WHEN** a `.json` file under one of the checker's scan roots contains a token listed in the per-repo token-list overlay — for instance English prose in a `_comment` key naming the host repo
- **THEN** the checker exits non-zero and reports it like any other source violation
- **AND** a `.json` file outside every scan root, such as the plugin manifest, is not scanned by this checker

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

### Requirement: The live specification set is validated where it is written

A skill that writes or hand-edits the live specification set SHALL validate that set's own parse integrity before the commit that lands the edit, and SHALL NOT treat validation of a *change* as covering it. The two are different objects: a change's validation reads the change, while the defect here is a structurally broken document under the live specification directory, which every per-change check passes over.

**The obligation attaches to the edit, not to the delta.** It SHALL cover any hand-edit to a live specification's prose — filling a placeholder section, rewording, adding a canonical heading — including edits that pass through no delta and no archive at all. A live specification is a parsed document rather than a prose file, and the guidance SHALL say so where such edits are performed, because the flow otherwise treats one as a comment.

**Where a step's own remediation instructs a hand-edit to a live specification, that step SHALL carry the validation with it.** A remediation that adds a canonical heading is itself capable of producing a duplicated heading, which closes the section and makes every requirement below it invisible to validation, listing and archiving while the file still reads correctly to a human.

**In a sequence of changes, a broken live set SHALL halt rather than warn.** Each change starts from the specification set the previous one left, so the failure compounds and surfaces at a later change's archive, far from the edit that caused it.

This requirement is distinct from any check comparing a delta's modified-requirement block against the live specification for silently dropped scenarios: that concerns the *content* a sync writes, whereas this concerns the live set's *parse integrity after any edit*, and the measured instance passed through no delta at all.

#### Scenario: EVERY write site validates the live set, not only the change

- **WHEN** any phase in any skill materializes or edits the live specification set
- **THEN** that phase validates the live set before the commit that lands the edit
- **AND** a result naming a broken specification halts and surfaces rather than proceeding to commit
- **AND** a skill with one compliant write site and another that writes without validating does not satisfy this

#### Scenario: The no-delta, no-archive write site runs the check

- **WHEN** a skill edits a live specification in place, creating no delta and running no archive
- **THEN** that skill's own step runs the live-set validation before its commit
- **AND** this is satisfied by the check running at that site, not by another file describing the rule

#### Scenario: A chain validates before it merges

- **WHEN** a change in a sequence leaves the live specification set failing validation
- **THEN** it is treated as a structural failure that halts the sequence
- **AND** the check runs before that change's pull request is merged, so the failing specifications do not reach the base branch and the branch is still available to fix on
- **AND** it is not deferred to the next change, whose archive would fail instead

#### Scenario: A check that could not run is not reported as a broken specification

- **WHEN** the validation exits non-zero without naming a failing specification
- **THEN** it is reported as a tooling fault
- **AND** it is not attributed to the change's own specifications, and does not halt a sequence as a structural failure

#### Scenario: A run that validated nothing is not a pass

- **WHEN** the validation reports that it found no items to validate
- **THEN** that is distinguished from a clean result rather than recorded as success
- **AND** a repository not using the specification tooling has that stated once rather than accruing vacuous passes

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

The gate SHALL further state that a **killed** mutant does not discharge it either: the kill establishes that the suite reacts to that edit, not that the code or the test is correct, so the assertion that killed the mutant SHALL be read and confirmed to state the wanted behaviour. Every shipped markdown file stating this gate SHALL carry that clause — a site restating the gate without it briefs its reader against a two-outcome contract in which a kill is self-certifying.

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

#### Scenario: A killed mutant does not discharge the gate

- **WHEN** a mutant is killed by an existing test
- **THEN** the gate requires the killing assertion to be read and confirmed to state the wanted behaviour
- **AND** the kill alone is not recorded as evidence that the code or the test is correct

#### Scenario: Every site stating the gate states the same contract

- **WHEN** more than one shipped markdown file states the mutation gate
- **THEN** each site carries the killed-mutant clause rather than only the site that was edited last

### Requirement: Sequencing edges beyond the source dependency graph

A skill that sequences a batch of changes SHALL establish, before the batch runs, the edges its source dependency graph cannot express, and SHALL NOT present a merge or landing policy in vocabulary that can only see that graph. A dependency list records **source-level** need — one change's code or spec requiring another's — and two edges outside it are each sufficient to break a later change whose own work is correct.

**Shared mutable environment state.** A change that applies a migration to a shared environment, seeds shared fixture data, or performs a provisioning step SHALL create a merge-before-next edge **regardless of whether any other change depends on its code**. That state has already moved for every subsequent branch, so only merging its source makes the tree consistent with it again.

The skill SHALL determine this **per change, from named artifacts, as an orchestrator-computed fact rather than a user preference** — the change is unimplemented at sequencing time, so the determination SHALL name the sources that are available then rather than a diff that does not yet exist. A negative SHALL carry its derivation rather than the bare word, on the same reasoning the skill already applies to a counted zero elsewhere: a determination whose default is negative and whose negative is never shown is an exemption rather than a check.

**It SHALL survive any autonomy mode.** Where the skill offers a mode that pre-answers its gate with recommended defaults, this determination SHALL NOT be among the pre-answered items, and SHALL appear in whatever output that mode requires. An unattended run is where this edge was measured to cost the most, so establishing it only in attended runs inverts the fix.

**Every statement of the policy SHALL name both edges**, including any hoisted summary that binds when the detailed reference is not loaded, and including the statement that governs the merge itself — a summary keyed on the dependency list alone is the form in which this defect is actually met, and the statement nearest the merge is the one that decides it.

**A policy that performs no merges SHALL NOT silently absorb this edge.** Where the skill offers a stacked or open-all policy, or falls back to one mid-run, a change sitting after a shared-state edge cannot satisfy it by branching, and the conflict SHALL be surfaced rather than proceeded through.

**Stale delta baselines.** Where a batch's changes are authored against one baseline of a shared specification set and no delta is applied before the others are written — which holds whether authoring is sequential or parallel — a modified-requirement block that replaces its requirement wholesale SHALL be treated as a collision risk. The obligation SHALL attach to **every in-scope change carrying such a block**, not only to those whose capability another in-scope change also touches: text that reached the live specification after authoring moves the baseline identically whether it came from a sibling in this batch, a change landed by another workflow, or a hand edit. Each such change's delta SHALL be re-checked against the live specification **as of that moment**, not as the delta was authored, before that change is reviewed.

The skill SHALL additionally compute and name which capabilities are touched by more than one in-scope change, which prioritises the check and identifies the sibling to compare against. This SHALL NOT rest on an individual change's own task list happening to warn, which is the only thing that has caught it.

**The result SHALL carry its denominator**, so that a check which failed to run is distinguishable from one that ran and found nothing: how many in-scope changes were scanned, how many carried spec deltas, and how many capabilities were found. A non-zero exit from the enumeration SHALL be reported as a failed check rather than as an empty result, since a run from an unexpected working directory otherwise yields a confident batch-wide clean answer.

**Both edges SHALL be delivered, not only recorded.** A finding this step produces is acted on by a review that runs in a later phase, from a different reference; recording it in a run artifact that nothing reads back SHALL NOT satisfy this requirement. The skill SHALL feed each finding into the invocation that starts the change it concerns, by the same channel that already carries that change's inherited obligations.

#### Scenario: An independent change that moved shared state still merges first

- **WHEN** a change in a batch applies a migration, seeds shared fixture data, or provisions shared infrastructure
- **THEN** it creates a merge-before-next edge even though no other change depends on its code
- **AND** the sequencing step records that edge next to the change's dependency list

#### Scenario: A policy summary does not describe only the dependency edge

- **WHEN** a skill states a merge-policy default in terms of dependents and independents
- **THEN** the statement names the shared-environment-state edge as well as the source dependency
- **AND** it does so in the hoisted summary too, not only in the detailed reference

#### Scenario: A stale delta baseline is checked whether or not a sibling overlaps

- **WHEN** an in-scope change carries a block that replaces a requirement wholesale
- **THEN** its delta is re-checked against the live specification as of that moment, before that change is reviewed
- **AND** the check attaches even when no other in-scope change touches that capability
- **AND** the capabilities touched by more than one in-scope change are additionally computed and named

#### Scenario: A check that could not run is not reported as a clean batch

- **WHEN** the enumeration of a change's spec deltas exits non-zero
- **THEN** it is reported as a failed check rather than as a change contributing no capabilities
- **AND** the result carries how many changes were scanned and how many carried deltas

#### Scenario: A finding reaches the review it is for

- **WHEN** sequencing produces a re-base obligation or a shared-state edge for a named change
- **THEN** it is delivered in the invocation that starts that change, by the channel already carrying inherited obligations
- **AND** recording it in a run artifact that nothing reads back does not satisfy the requirement

#### Scenario: The determination survives an autonomy mode

- **WHEN** a mode pre-answers the pre-flight gate with recommended defaults
- **THEN** the shared-state determination is still made per change, from artifacts
- **AND** it appears with its derivation in that mode's required output

### Requirement: Cross-change obligation carry

A skill that drives a SEQUENCE of changes SHALL treat an obligation one change creates for a later one as chain state that is both **recorded** and **delivered**, and SHALL NOT discharge it by recording alone. An obligation here is an addition a change's own review or fix round makes — a stored field, column, response key, or required behaviour — that the change itself does not consume, whose sole justification is that a named later change reads it. Such an obligation is invisible to every check scoped to a single change: the downstream change's artifacts stay internally consistent while never mentioning it.

The obligation SHALL be derived from what the prerequisite **actually became**, not from the batch as proposed. A chain plan's dependency list is a snapshot taken before any review round runs, and a prerequisite's review round is precisely where these obligations are created, so a downstream change reviewed against the plan is reviewed against a state its prerequisite has already left. The derivation SHALL also cover findings the run set aside as belonging to a **different** change: such a finding names its consumer explicitly, yet it is by construction absent from both the applied-findings list and the diff, so a derivation resting on those two alone discards the most explicit obligation available to it.

**The record SHALL remain readable across sessions.** Where the record lives in a per-run, date-named artifact, the reading step SHALL read the whole family of such artifacts rather than only the current run's, because a run resumed on a later date creates a new one — and a reader scoped to the current run's file makes every obligation an earlier session recorded invisible on precisely the path the mechanism exists to survive.

**Delivery SHALL travel in the invocation that starts the downstream change** — the same argument channel that already carries that change's caps and its stacked-chain base — so that recording an obligation and delivering it are not separable acts. A carry list the orchestrator writes and then does not feed into the dependent's own review is indistinguishable from never having written it, and SHALL NOT be accepted as satisfying this requirement.

When obligations are delivered, the downstream change's **pre-implementation** review SHALL emit one verdict per obligation — honoured, violated, or not addressed — as a required output field ahead of any other finding, and SHALL settle "not addressed" mechanically, by the absence of the obligation's literal token anywhere in that change's own artifacts, rather than by judgement. The count of verdict lines SHALL equal the count of delivered obligations; a missing line SHALL NOT read as a pass.

**The required field SHALL be defined where review behaviour is defined, not in the orchestrator that delivers it.** Where a plugin names one file as the single source of truth for a review's checks, report shape and verdict rubric, this field belongs in that file: an orchestrator-side copy prescribes a position in a template it does not own, and — where the review may be produced by dispatched agents rather than inline — reaches neither the agents' prompts nor the material they are given. The obligation SHALL be settled before any size or mode gate selects between review paths, so the answer does not depend on which path ran.

**A non-honoured verdict SHALL be wired into the verdict that selects the fix round**, not only reported: it SHALL be a Critical finding and SHALL exclude a "ready" verdict. A report that can pair "not addressed" with "ready" has a required field that changes nothing. Where the report format omits empty sections by default, this field SHALL be exempted — its honoured lines are the answer, and omitting them removes the evidence that anyone looked.

**A non-honoured obligation SHALL NOT be discharged by making the token match.** Pasting the token into narrative prose satisfies the mechanical check while changing nothing an implementer does; the discharge SHALL be an implementable task naming the field and its consumer, plus the requirement delta where the obligation is a required field or behaviour.

**Delivered obligations SHALL be answered on a resumed run.** Where phase-resumption is driven by a state probe, and that probe reports no state for the review phase, a resumed change skips review entirely — so the obligation step SHALL run regardless of the probe's verdict whenever obligations were delivered. The skill SHALL surface the verdict lines in its own terminal report so the delivering caller can count them against what it sent; without that count, a run that answered every obligation and one that discarded the delivery are indistinguishable to the caller — the same "written and fed nowhere" failure one layer up.

An empty carry SHALL be recorded explicitly rather than left as an absent section. It SHALL be recorded as the **derivation** — the counts each source yielded, at least one of them a command's output — and not as a bare marker word, because a bare marker is satisfiable by typing it and therefore only renames the "nobody looked" failure it is meant to exclude.

**A dedicated checker script SHALL NOT be added for this.** The per-obligation check is one `grep` for one token against one change directory, which the plugin's script bar — a script earns its place only by doing something a direct command plus a sentence of prose cannot do reliably — does not clear. The recurring failure was never that the grep was hard to run; it was that nobody was obliged to run it.

#### Scenario: The obligation is delivered, not merely recorded

- **WHEN** a change's review or fix round creates an obligation for a named later change in the chain
- **THEN** the obligation is recorded in the run's own notes with the token to grep for, the creating change, the owing change, and the failure if dropped
- **AND** the later change's invocation carries that obligation as an argument
- **AND** the recording step names the reading step, so a row written but never delivered is a defect rather than a completed step

#### Scenario: The carry is derived from the prerequisite's actual state

- **WHEN** a prerequisite's own review round adds a field after a dependent's artifacts were authored
- **THEN** the obligation is derived from the applied findings and the prerequisite's final diff
- **AND** it is not derived from the chain plan's description of that prerequisite

#### Scenario: The downstream review answers for each obligation by name

- **WHEN** a change is reviewed with inherited obligations delivered to it
- **THEN** the report opens with one honoured / violated / not-addressed line per obligation, before any other finding
- **AND** a token absent from the whole change directory yields "not addressed" without judgement
- **AND** a non-honoured verdict is a Critical finding applied to the artifacts before implementation

#### Scenario: The required field is defined where the reviewer reads it

- **WHEN** a plugin names one file as the single source of truth for review behaviour
- **THEN** the obligation field is defined in that file rather than in the orchestrator that delivers it
- **AND** it is settled before the gate that selects between an inline and a dispatched review
- **AND** the obligations reach whatever material a dispatched reviewer is given

#### Scenario: A non-honoured verdict changes the verdict

- **WHEN** a report carries a "not addressed" obligation line
- **THEN** the verdict cannot be "ready"
- **AND** the field is exempt from the rule that omits empty sections

#### Scenario: The discharge is implementable, not a matching token

- **WHEN** a "not addressed" obligation is fixed
- **THEN** the fix adds a task naming the field and its consumer
- **AND** a token pasted into narrative prose alone is re-flagged rather than accepted

#### Scenario: A resumed change still answers

- **WHEN** a change is resumed and the state probe reports no review-phase state
- **THEN** the obligation step runs anyway and emits its verdict lines
- **AND** the delivering caller can count those lines against the obligations it sent

#### Scenario: The record survives a resume on a later date

- **WHEN** the record lives in a per-run, date-named artifact and the run resumes on a later date
- **THEN** the reading step reads the whole family of those artifacts, not only the current run's

#### Scenario: An empty carry is written down as its derivation

- **WHEN** a change creates no obligation for any later change
- **THEN** that is recorded for that change as the counts its derivation sources yielded
- **AND** at least one of those counts is the output of a named command, so the entry is falsifiable rather than a word

### Requirement: Unattended-run turn liveness

A skill that drives a multi-step run designed to proceed without a human present SHALL state, among its hoisted skill-level rules, that a turn is never ended while nothing is pending that would re-invoke the session. The obligation SHALL be stated as a **check the agent can apply without judgement** — whether the message contains a tool call — rather than only as a prohibition on how a message reads, because the judgement form has been observed to fail in the one way that matters: an author writes a closing-shaped status report and then behaves like its reader.

The rule SHALL distinguish itself from the existing no-confirmation-prompt rules such skills already carry. Those forbid *asking permission*; this failure asks nothing, and an orchestrator hitting it believes it is continuing. The stated discriminator SHALL be whether a pending event will re-invoke the session — a backgrounded dispatch whose completion notification wakes it — and NOT whether a question was asked. The rule SHALL state that announcing the next step is not a mechanism.

The exhaustive set of conditions under which ending a turn is legitimate SHALL be exactly two: a backgrounded dispatch is genuinely in flight, or the run is complete. A skill SHALL NOT add a third. In particular it SHALL NOT admit "blocked on a decision already surfaced to the user", because that clause is satisfied by writing a paragraph and is therefore the shape a stalling orchestrator most easily adopts — a genuine blocker is surfaced with a tool call, which does not end the turn at all. Every skill stating this rule SHALL name the same two, so no two skills assert differently-sized exhaustive sets.

The rule SHALL be restated at the seam between units of work in whichever reference file carries that seam's procedure, because the seam is reached with the reference closed and the orchestrator running on the `SKILL.md` summary.

The rule's three properties — the mechanical check, the pending-event discriminator, and "announcing the next step is not a mechanism" — SHALL appear together in one block of prose rather than scattered across a file. A rule whose parts arrive separately can be gutted while each part survives somewhere, and a guard that checks for them file-wide cannot tell the two apart.

#### Scenario: The rule is stated mechanically, not only as a prohibition

- **WHEN** an unattended-run skill states its turn-liveness rule
- **THEN** the rule gives a check requiring no judgement (whether the message carries a tool call)
- **AND** it does not rest solely on the agent noticing that its own text reads as an ending

#### Scenario: The rule is distinguished from the no-pause rules

- **WHEN** the rule appears alongside an existing "no ready-to-continue pauses" rule
- **THEN** it states that the failure it covers asks the user nothing
- **AND** it names the pending-event discriminator rather than the asked-a-question one

#### Scenario: The seam carries its own restatement

- **WHEN** a skill's per-unit loop lives in a reference file
- **THEN** that file restates the obligation at the point where one unit ends and the next begins
- **AND** it says why the restatement is there rather than relying on the hoisted copy

#### Scenario: The exhaustive set is the same two everywhere

- **WHEN** two skills each state the turn-liveness rule
- **THEN** both name the same two legitimate conditions
- **AND** neither admits a third that a paragraph of prose could satisfy

#### Scenario: The rule's parts arrive together

- **WHEN** a skill states the rule
- **THEN** the mechanical check, the discriminator, and "announcing is not a mechanism" sit in one block
- **AND** a guard over them distinguishes that from the three merely appearing somewhere in the file

### Requirement: Completeness signals read the claim, not the glyph

A skill that reports a task list complete SHALL NOT rest that report solely on checkbox state. A checkbox count is a presence check on the glyph: it cannot distinguish a task that was done from one that was ticked. An artifact-presence flag is weaker still — it does not read task state at all — so neither is evidence that the work behind a task happened.

A task whose text asserts a **measurement** — a confirmed value, a count, a mutation-test result — SHALL record the measured value inline on the ticked line rather than the tick standing as its own evidence, and the post-check SHALL re-measure a small sample rather than trusting the ticks wholesale.

The skill SHALL state the underlying convention as well as enforcing it: a task is `[ ]` until it is done, and the prose beneath it explains why it is still open.

**A mechanical scan of a ticked task's body for self-negating text is NOT required, and the reason is recorded so it is not re-attempted blind.** It was built and withdrawn: measured over this repo's own archived `tasks.md` corpus — 173 ticked tasks — such a scan reached 6 lines, produced 0 true positives and 4 false positives, and its trip words collided with vocabulary the skills use deliberately. A repo whose task prose sits on the task line rather than beneath it gets no coverage from the obvious implementation. Anyone rebuilding it SHALL first measure the target corpus, and SHALL reuse the task parser the plugin already ships rather than hand-rolling one. Full evidence: GitHub issue #105.

#### Scenario: A measurement-bearing task carries its measurement

- **WHEN** a task asserts a confirmed value, a count, or a mutation-test result
- **THEN** the ticked line records the measured value
- **AND** a sample of such tasks is re-measured rather than trusted

### Requirement: A measurement names the command that produced it

A skill that owns a commit-creating step SHALL require, at **every** such step rather than only the first, that every measurement the change asserts — a count, a coverage figure, "measured", "verified", "zero X", any number offered as fact, in the diff or in the message — names the exact command that produced it, as one git trailer per claim at the end of the commit message. The trailer's format SHALL require the command to be **runnable as written**: a trailer naming "the test suite" or an elided invocation reproduces nothing and satisfies a bare-token rule, which is the failure the trailer exists to close. The same obligation SHALL cover any measurement written into the PR body.

**The obligation SHALL be stated at the pre-commit stop, not at authoring time.** This is the requirement's whole point and is not a placement preference. The rule has existed as project guidance for months and kept failing in careful work, and the reason is that it had no chokepoint: `grep -rin "five checks\|check 3" .claude/plugins/cla/` returns 0 — no shipped asset referenced it — while of the five such pre-ship checks this repo states, exactly one (rewrote-a-file) has a moment-of-edit mechanism, `hooks/warn-wholesale-rewrite.py` on the `Write` matcher. Project guidance loads at session start; the claims are written hundreds of tool calls later. The stop the skill already performs before committing is where the author is already halted and already assembling claims into a message, so that is where the obligation binds.

**The discharge SHALL be an edit rather than an answer.** A claim the author cannot pair with a runnable command has exactly two exits: run the command now, or delete the claim and restate it as the reasoning it is. A skill SHALL NOT offer a third exit in which the claim ships and the command is owed. A change asserting no measurement SHALL carry no trailer, and a skill SHALL NOT accept a null certification such as `Measured-by: none` — a line certifying a check nobody performed is worse than no line, because it reads as evidence that one happened.

**The trigger SHALL be a claim the change asserts, not a check that ran.** The standing pre-ship gates — the test suite, the linters, the conformance scripts every commit runs anyway — are not claims the change puts into the diff or the message, and a skill SHALL NOT require a trailer for them. Trailering them turns the block into fixed boilerplate on every commit, and a block identical every time stops being read, which costs precisely what the step was added to buy. This is the same decay the null certification above is forbidden for, reached by over-application rather than by emptiness.

**Adoption SHALL be recorded rather than asserted.** Nothing gates a single commit, so a trailer that was never written is invisible; the obligation's own effectiveness would otherwise be an unfalsifiable claim, which is the failure this requirement exists to prevent. The plugin's commit-provenance hook SHALL record, per commit, the count of measurement trailers and their values, so the question is answered from a ledger. Under the line ceiling that ledger enforces, the trailer VALUES SHALL be shortened before the record is dropped, and the count SHALL remain exact — a dropped line would remove the commit from the denominator the ledger exists to supply.

**A row SHALL be written only for a commit the recorded command actually made.** Reading HEAD proves a commit exists, never that this command created it, so a hook that records on HEAD alone re-records its predecessor's work every time a commit-shaped command commits nothing. Each such row inflates the denominator the ledger exists to supply, and once written it is indistinguishable from a real one. Two conditions SHALL both hold before a row is written: the last movement of HEAD was a commit, and the sha is not the one the ledger's last row already carries. Neither SHALL be treated as sufficient alone — a commit that stages nothing leaves the first satisfied, and a sha from another branch's older work leaves the second satisfied.

**A commit SHALL NOT go unrecorded because of a command it merely shares a call with.** One invocation holds several commands, and every test deciding whether something is a commit is about one of them. So the invocation SHALL be split into its commands before any such test is applied, on line breaks as well as on the shell's operators. Under-recording costs the same denominator as over-recording and is harder to notice: a commit with no row reads exactly like a commit that never happened.

**The trailer token SHALL be distinguishable from narrative prose.** Bare `Measured:` is ordinary narrative text in the shipped tree (`git grep -l "Measured:" -- .claude/plugins/cla | wc -l` — 4 tracked files, none of them a trailer; `grep -rl` answers 5 because it also opens a `__pycache__` `.pyc`), so a bare token would collide both with a drift check over shipped prose and with `git log --grep`. The hyphenated git-trailer form `Measured-by:` is load-bearing rather than cosmetic.

**This obligation is NOT covered by the Completeness-signals requirement above**, whose measurement clause reads in full: *"A task whose text asserts a **measurement** — a confirmed value, a count, a mutation-test result — SHALL record the measured value inline on the ticked line rather than the tick standing as its own evidence, and the post-check SHALL re-measure a small sample rather than trusting the ticks wholesale."* That binds a **task list** to record a **value**; this binds a **commit** to name a **command**. A recorded value is the claim restated in another place — it is exactly what every escape this requirement addresses already had. Only the command lets a reader reproduce it, and the two clauses also bind different artifacts at different moments, so neither subsumes the other.

**A keyword scan over the diff SHALL NOT be the mechanism, and the measurement is recorded so it is not re-attempted blind.** The Completeness-signals requirement already records one withdrawal of this idea for ticked task bodies (GitHub issue #105: 173 ticked tasks, 6 lines reached, 0 true positives, 4 false positives, trip words colliding with vocabulary the skills use deliberately) and requires that anyone rebuilding it measure the target corpus first. Re-measured here for the diff-side variant, over this repo's own history:

```
git log -8 -p --format= --unified=0 | grep -cE '^\+'
  -> 7280 added lines

git log -8 -p --format= --unified=0 | grep -E '^\+' | grep -icE 'measured|verified|counted|\bzero\b|no (violation|hit|match|instance|offender)s?\b|[0-9]+ of [0-9]+|exactly (one|two|three|four|five|six|seven|eight|nine|ten|[0-9]+)\b'
  -> 169 hits (2.3%)
```

A systematic 21-line sample of those 169 (every 8th hit, `| awk 'NR%8==1'`) was dominated by test function names, string literals inside assertions, spec scenario prose, and claims that already named their command. That is issue #105's failure shape again, so the mechanism SHALL be authored rather than discovered: the author wrote the claims and needs no scanner to find them, and what gets checked is the artifact.

#### Scenario: A change asserting a measurement carries its command

- **WHEN** a Ship step commits a change whose text asserts a count, a coverage figure, or any number offered as fact
- **THEN** the commit message carries one trailer per claim naming the exact command that produced it
- **AND** the command is a real invocation runnable as written

#### Scenario: A claim with no command is edited, not carried

- **WHEN** the author cannot name a command for a measurement the change asserts
- **THEN** the claim is either backed by running the command now or deleted and restated as reasoning
- **AND** no exit exists in which the claim ships with the command owed

#### Scenario: A change asserting nothing certifies nothing

- **WHEN** a change asserts no measurement
- **THEN** the commit message carries no measurement trailer
- **AND** a null certification line is not written in its place

#### Scenario: The rule binds at every commit chokepoint

- **WHEN** a skill states the obligation for a commit-creating step
- **THEN** it is stated after that step's pre-commit state check and before its commit, not among the skill's authoring-time guidance
- **AND** a skill with more than one commit-creating step states it at each, rather than at the first and by reference elsewhere

#### Scenario: A standing gate is not a claim the change asserts

- **WHEN** a change runs the pre-ship test suite, linters, and conformance scripts every commit runs
- **THEN** those results earn no trailer
- **AND** a trailer is written only for a number the change puts into the diff or the message

#### Scenario: Adoption is answerable from the ledger

- **WHEN** a commit is recorded by the commit-provenance hook
- **THEN** the record carries the exact count of measurement trailers and their values
- **AND** an oversize record sheds trailer values rather than being dropped, leaving the count intact

#### Scenario: A command that committed nothing records nothing

- **WHEN** a commit-shaped command runs and creates no commit
- **THEN** no row is written, whether HEAD was last moved by a checkout, a merge or a pull, or whether the command staged nothing and left HEAD where its predecessor put it
- **AND** neither the reflog condition nor the ledger-dedupe condition alone is relied on, since each admits a case the other rejects

#### Scenario: A commit is recorded despite its neighbours in the same call

- **WHEN** one invocation makes a commit and also runs a command that reads history or carries a dry-run flag
- **THEN** the commit is recorded, because the invocation is split into its commands before any commit test is applied
- **AND** a command that itself reads history or is a dry run still records nothing

### Requirement: Deferred findings are separated by reason

A skill reporting findings it did not apply SHALL split them into named subsections distinguishing a hold that cannot be resolved now, a hold whose trigger has not fired, and an item skipped for neither reason. The third SHALL be mechanically detectable, so that a policy breach is found by a grep rather than by re-reading every item.

Collapsing all three under one label SHALL be treated as a defect rather than a formatting preference: undifferentiated, a genuine breach and a legitimate hold read identically, which leaves only two options — accept the section unread, or re-read it in full on every change.

#### Scenario: A skipped item is distinguishable from a legitimate hold

- **WHEN** a fix round reports items it did not apply
- **THEN** each appears under one of the three named subsections
- **AND** a non-empty "skipped" list fails the reporting phase under a no-deferrals policy

### Requirement: Planting doctrine is carried where tests are authored

The plugin SHALL carry, in a shared reference read at the point tests are authored, the rules that decide whether a test can fail at all. That reference SHALL distinguish rules applying to any test from rules applying only to a **gate** — a check whose feature is detecting something — and SHALL say which is which at its head, so a reader writing an ordinary unit test is not sent through gate doctrine that does not apply to them.

Where the reference states how a planted failure goes wrong, it SHALL give **checkable conditions rather than an exhortation**. "Confirm what moved" is not a condition; "diff the file and confirm the change is in the data, re-parse it and confirm it is well-formed, and read the failure message for the value you planted" is three.

The reference SHALL state that planting exercises only the implementation that exists, and therefore cannot reach an input the author never enumerated — and SHALL direct that anything parsing an external contract is enumerated from its primary source **before** it is planted against.

**A landed plant that dies.** The conditions above separate a plant that reached the value under test from one that missed. The reference SHALL also carry the case they do not reach, where the plant lands, the mutant dies, and the kill still establishes nothing: a test written from a wrong mental model kills mutants exactly as reliably as a correct one, so the green result reads as confirmation of the error. It SHALL give this trap its own remedy — read the killing assertion and confirm it states the wanted behaviour — rather than folding it into the did-it-land conditions, which every instance of it passes. It SHALL name the shape carrying the highest risk: a mutant that is the **simpler** form of the code, where if the simpler form is correct then the test defending the original is defending the defect.

**Scope boundary.** Guidance about when planting is worth its cost is routing, and SHALL NOT be read as narrowing any other obligation. In particular the **Review-fix evidence gate** stays unconditional: a fix for a review finding earns its evidence regardless of which technique supplies it. A reference stating both SHALL say so explicitly, because the two sit close enough to be read as one.

**Unreachability at the operating point.** The reference SHALL also carry the sibling case, where the enumerated input space is correct and the guard is nonetheless unreachable because the volume it meets in ordinary operation sits outside the range where it acts: a minimum-sample precondition larger than any real batch, a threshold pinned against a backfill-sized sample or against a different statistic than the code measures, or an alarm over an aggregate too coarse to see the sub-population that failed.

It SHALL require any new alarm, threshold or minimum-sample precondition to state the volume it will meet in ordinary steady-state operation **and the source of that figure**, so the number can be re-derived rather than guessed — the omission that produces this defect is an author choosing a number while holding a backfill-sized sample, which requiring the number alone leaves available. It SHALL require the guard's outcome to be stated at both ends of that range, since one end distinguishes "cannot fire" from "fires constantly" and neither end alone does.

It SHALL state where this sits relative to the planting rules rather than leaving the reader to infer it, and SHALL NOT claim the planting rules reach none of it. A plant against the live tree does not reach it — the comparison it fires is correct, and what goes unexamined is the precondition gating when that comparison runs — but a neighbouring rule whose remedy is to supply the check with bad state DOES reach it, conditionally on that state being sized to the real operating point. Where such a condition exists it SHALL be stated, because a reader told the neighbouring rules are irrelevant is steered away from the only remedy the reference offers.

#### Scenario: A reader is routed before being asked to read gate doctrine

- **WHEN** the shared test-quality reference is opened
- **THEN** its head names which sections apply to any test and which apply only to a gate

#### Scenario: The cost guidance does not narrow the review-fix gate

- **WHEN** the reference says a planted failure is unnecessary for some assertions
- **THEN** it states that this leaves the review-fix evidence obligation unchanged

#### Scenario: A trap is stated as something the reader can check

- **WHEN** the reference describes a plant that FAILED TO LAND on the value under test
- **THEN** it names the conditions distinguishing a landed plant from one that missed
- **AND** a trap of a different shape gives its own remedy rather than being forced into that form

#### Scenario: A plant that lands and kills is still examined

- **WHEN** the reference is read by someone whose plant landed and whose mutant died
- **THEN** it states that the kill proves the suite reacts to the edit, not that the code or the test is correct
- **AND** it directs the killing assertion to be read and confirmed to state the wanted behaviour
- **AND** it names the simpler-form mutant as the highest-risk shape

#### Scenario: A correct guard that cannot fire at its real volume is covered

- **WHEN** the reference is read by someone adding an alarm, threshold, or minimum-sample precondition
- **THEN** it requires the volume that alarm will meet in ordinary steady-state operation to be stated
- **AND** it requires both directions to be answered at that volume — that the alarm can fire, and that it fires only when it should
- **AND** it states that a plant against the live tree reaches none of this, because the comparison it fires is correct and what goes unexamined is the precondition gating when that comparison runs
- **AND** where a neighbouring rule's remedy does reach it, the condition under which it does is stated rather than left implicit

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

### Requirement: A fix brief binds the defect and offers the remedy

A cla-plugin sub-agent brief whose purpose is to remedy a defect SHALL state the defect and the
proposed fix as separately-named fields carrying different authority, and SHALL NOT merge them into a
single instruction.

The **defect** — what is true now and why that is wrong — SHALL be **binding**: the dispatched agent
may not decide the defect is acceptable and stop. The **candidate remedy** — the fix the dispatching
orchestrator proposes — SHALL be **rejectable with reasons**, and a reasoned rejection SHALL be a
successful return rather than a failure return, so that the return status carries no penalty for
having been right.

The brief's terminal contract for such a dispatch SHALL ask for evidence that the **defect** is gone,
not evidence that the remedy landed. Concretely, `done` SHALL require the defect check named in the
brief — the command or read that exhibits the defect — re-run with its output showing the defect
absent, in addition to whatever work evidence the contract already requires. The contract SHALL state
explicitly that evidence the candidate remedy was applied is NOT evidence the defect is gone, because
a compliant agent that implements a wrong remedy returns work evidence that is entirely genuine, and
the regression it ships is indistinguishable from success under a contract keyed on the remedy.

A brief that cannot name a defect check SHALL be treated as a brief whose defect is not grounded,
rather than as a case exempt from the contract.

The dispatching skill SHALL NOT achieve this by adding a permission for the agent to disagree while
leaving the terminal contract unchanged. A permission stated beside an instruction that carries a
deliverable does not reach a compliant agent; what the terminal contract *requires* is the only lever
that does.

Where a brief format is shared across skills and cited by slot name, this SHALL be introduced as a
second form of the existing task slot rather than as an additional slot, so that citing sites naming
the slot list remain correct.

**Where a fix dispatch is briefed over more than one finding, its return SHALL carry a per-finding
outcome in addition to an overall status.** A dispatch spanning a set of findings whose return
carries only one status cannot express the ordinary mixed result — most findings remedied, one
remedy rejected — and forcing it into a single status either discards the completed work or hides
the rejection. Since every branch that consumes such a return triages, counts, and reports **per
finding**, the return SHALL be per finding too. A dispatch over a single finding SHALL use the same
contract, returning a one-row list, so that there is one contract rather than two.

#### Scenario: A fix brief separates the two fields

- **WHEN** a skill dispatches an agent to remedy a defect
- **THEN** the brief names the defect in its own field, marked binding
- **AND** it names the candidate remedy in a separate field, marked rejectable
- **AND** the two are not merged into one instruction sentence

#### Scenario: The terminal contract asks for defect-gone evidence

- **WHEN** a fix dispatch's terminal contract is stated
- **THEN** `done` requires the brief's named defect check, re-run, with output showing the defect absent
- **AND** the contract states that evidence the remedy was applied is not evidence the defect is gone
- **AND** a return claiming `done` without defect-gone evidence is treated as not done

#### Scenario: A reasoned rejection is a successful return

- **WHEN** the dispatched agent finds the candidate remedy wrong
- **THEN** it returns a rejection status distinct from the blocked status, with its reason
- **AND** that return is treated as a successful outcome, not a delegate failure
- **AND** the orchestrator's response is to re-decide the remedy rather than to resolve a blocker

#### Scenario: The slot list is not renumbered

- **WHEN** the fix-brief form is added to a shared brief format cited by slot name
- **THEN** it is introduced as a second form of the existing task slot
- **AND** no slot is renamed, renumbered, or added
- **AND** every site citing the brief by slot name remains correct without edits

#### Scenario: A brief that cannot name a defect check

- **WHEN** an orchestrator authoring a fix brief cannot name a check that exhibits the defect
- **THEN** the brief is treated as one whose defect is not grounded
- **AND** it is NOT treated as a dispatch exempt from the terminal contract
- **AND** the stated remedy is to ground the defect before dispatching, not to waive the field

#### Scenario: Every site restating the terminal contract states the same one

- **WHEN** the terminal contract is restated outside the brief that defines it
- **THEN** every site briefing a dispatch that remedies a defect states the three-status form
- **AND** a site briefing a dispatch that never remedies a defect is left unchanged
- **AND** no fix dispatch briefs against a contract with fewer statuses than the definition carries

#### Scenario: A permission to disagree does not satisfy the requirement

- **WHEN** a skill adds prose permitting the dispatched agent to disagree with the proposed fix
- **AND** the terminal contract's evidence requirement is left keyed on the remedy having been applied
- **THEN** the requirement is NOT satisfied
- **AND** the stated remedy is to change what `done` requires, not to add a further permission

#### Scenario: A dispatch over a set of findings reports each one

- **WHEN** a fix dispatch is briefed over more than one finding at once
- **THEN** its return carries one overall status AND one outcome row per finding the brief enumerated
- **AND** a finding whose remedy is rejected is identifiable from that list rather than only from the overall status
- **AND** a dispatch over a single finding returns a one-row list under the same contract

### Requirement: A rejected remedy has a receiving branch in the fix loop

A skill whose fix loop triages findings into outcomes SHALL define an outcome for a rejected remedy.
A rejection SHALL discharge the round's attempt at the finding without closing the finding, SHALL NOT
be counted as untriaged residue by the loop's exit gate, and SHALL NOT consume a round.

**Triaged and closed SHALL be distinguished, and the exit gate SHALL test both.** A loop whose exit
gate counts only untriaged findings SHALL NOT be considered to satisfy this requirement: a rejected
finding is triaged and still open, so such a gate reports the loop clean while a Critical finding is
live, and the skill's own completion signal then endorses shipping it. The gate SHALL count
*untriaged* findings (in no outcome) and *open* findings (in an outcome but not closed) separately,
SHALL require both to be zero to exit clean, and where open findings remain with budget available
SHALL re-enter the loop rather than exit.

**The terminal report SHALL carry a bucket for a rejected-but-open finding**, distinct from the
bucket for consciously-deferred findings and from the bucket for suggestion-level residue. An
outcome a report cannot print is an outcome nobody reads.

**Where a rejection cites a disproved defect, the finding SHALL be closed rather than re-attempted.**
Where the agent's stated reason is that a factual claim the defect rested on is wrong and the defect
does not survive its correction, re-deciding the remedy is the wrong next move — there is no defect
left to remedy — and a loop that re-attempts it will do so until its cap is exhausted. Such a finding
SHALL be recorded as closed by disproof, with the corrected claim as the evidence, and SHALL NOT be
recorded as fixed.

#### Scenario: A rejection is triaged rather than counted as residue

- **WHEN** a dispatched delegate returns a rejection of the candidate remedy
- **THEN** the fix loop's triage records it as a third outcome beside applied and deferred
- **AND** the exit gate does not count that finding as untriaged residue
- **AND** the round is not marked warn on account of the rejection

#### Scenario: A rejection reopens the remedy, not the finding

- **WHEN** a finding's remedy is rejected
- **THEN** the finding remains open and is re-attempted with a re-decided remedy
- **AND** the finding is not recorded as resolved by the rejection

#### Scenario: The exit gate does not release the loop on an open finding

- **WHEN** a round ends with a rejected finding triaged and still open, and no untriaged findings
- **THEN** the exit gate does not report the loop clean
- **AND** with budget remaining the loop re-enters rather than exiting
- **AND** at cap exhaustion the round is warned and the open finding is captured as residue

#### Scenario: A rejected finding has a home in the terminal report

- **WHEN** a run ends with a finding whose remedy was rejected and which is still open
- **THEN** the terminal report prints it under a bucket of its own
- **AND** it is not filed as a conscious deferral or as suggestion-level residue

#### Scenario: A rejection citing a disproved defect closes the finding

- **WHEN** the rejection's stated reason is that the defect does not survive the correction of a claim it rested on
- **THEN** the finding is closed rather than re-attempted with a re-decided remedy
- **AND** the corrected claim is recorded as the evidence of closure
- **AND** the finding is not recorded as fixed

#### Scenario: A rejection costs no round

- **WHEN** a round contains a rejected remedy
- **THEN** no round cap is raised and no additional round is consumed by the rejection

### Requirement: A brief's factual claims are checkable and carry their source

A cla-plugin brief that states a defect SHALL list the factual sub-claims the defect rests on — a
type's field list, a signature, a line number, a count — as separately-enumerated rows, each naming
the source that resolves it (a path with a line, or a runnable command). Such sub-claims SHALL NOT
ship as unattributed ground truth inside the defect prose, where nothing marks them as claims and
nothing tells the reader where they came from.

Each row SHALL additionally carry a **provenance tag** recording whether the claim was verified by the
party writing the brief or merely reported to it. Two values SHALL be distinguished: a claim someone
has actually resolved against its source, and a claim relayed from a dispatched agent's report without
independent resolution. Without the tag the source field says only where a claim *could* be checked,
not whether anyone did, and the rows the reader most needs to re-run are indistinguishable from the
rows already settled — which is the condition that let a four-field claim about a three-field type
ship as ground truth.

The tag SHALL apply to a brief's fact rows and SHALL NOT be required of a review report's claim table;
extending it there is a separate concern with a separate consumer.

The dispatched agent's first action SHALL be to re-resolve each row against its named source, each row
resolving to verbatim evidence or an explicit not-found, per the grounding contract the plugin already
applies to review claims. The brief SHALL state that resolving-quote-or-not-found rule in its own text
rather than only citing the document that defines it, because a dispatched agent reads the brief and
does not load the plugin's review checklist.

A wrong sub-claim SHALL NOT automatically void the defect. Three outcomes SHALL be distinguished:

1. Every row resolves as stated — the agent proceeds.
2. A row is wrong **and** the defect does not survive its correction — the agent returns the remedy
   rejected, with the corrected row, and does not implement.
3. A row is wrong **but** the defect survives its correction — the agent corrects the row, proceeds,
   and reports the correction.

Corrections SHALL be returned in a required field that is printed with an explicit empty marker when
there are none, and SHALL NOT be omitted when empty: an omitted field and a field nobody filled in are
indistinguishable to the reader, which defeats the purpose of requiring it.

#### Scenario: The defect's factual sub-claims are enumerated with sources

- **WHEN** a fix brief states a defect resting on a field list, a signature, a line number, or a count
- **THEN** each such claim appears as its own row rather than inside the defect prose
- **AND** each row names the path-with-line or the runnable command that resolves it
- **AND** each row carries a provenance tag saying whether the claim was independently resolved or relayed unverified

#### Scenario: The agent re-resolves the rows before implementing

- **WHEN** an agent receives a fix brief carrying fact rows
- **THEN** its first action is to re-resolve each row against its named source
- **AND** each row resolves to verbatim evidence or an explicit not-found

#### Scenario: A wrong sub-claim that the defect survives is corrected, not escalated

- **WHEN** a fact row is wrong and the defect remains real once the row is corrected
- **THEN** the agent corrects the row and proceeds with the work
- **AND** it returns the correction in the required corrections field

#### Scenario: A wrong sub-claim that the defect depends on stops the work

- **WHEN** a fact row is wrong and the defect does not survive the row's correction
- **THEN** the agent returns the remedy rejected with the corrected row
- **AND** it does not implement the candidate remedy

#### Scenario: The corrections field is never omitted

- **WHEN** an agent returns from a fix dispatch having found no wrong fact rows
- **THEN** the corrections field is present with an explicit empty marker
- **AND** it is not omitted from the return

### Requirement: An orchestrator-specified remedy is reviewed as a decision

A cla-plugin skill that applies fixes SHALL NOT let a remedy the orchestrator itself specified escape
the scrutiny a delegated remedy receives. A delegated remedy is reviewed by the agent that may reject
it; an orchestrator-applied remedy has no such reader, because the party that decided it is also the
party triaging the findings on it.

Where the fix is applied by the orchestrator itself — below a delegation threshold, or in a
pre-implementation artifact-fix loop where no delegate exists — the orchestrator's own post-fix
re-verification SHALL additionally check the applied remedy against the change's own design document,
specifically its rejected-alternatives or explicitly-rejected-decisions content, and confirm the
remedy does not reintroduce something that document rejected. The design document SHALL be the named
source for this check; the proposal and the task list SHALL NOT be substituted for it.

**A hit is a Critical finding on the fix itself, not a note.** Where the check finds that the applied
remedy reintroduces something the design document rejected, the skill SHALL treat it as a Critical
finding against that remedy and SHALL NOT let the fix stand on the reasoning that it resolved the
original finding — resolving one finding by reintroducing a rejected decision is the failure this
check exists to catch, and it is indistinguishable from success on the original finding's own
evidence. The remedy SHALL be withdrawn or re-specified, and where the design document's rejection is
the thing now judged wrong, that document SHALL be amended explicitly rather than contradicted
silently; "the fix brief said so" SHALL NOT be accepted as an amendment.

Each such remedy SHALL be **marked** as orchestrator-specified on the record the skill already keeps
for that finding's triage outcome, so that a later reader can tell which changes had no independent
author. The mark SHALL NOT be specified as a field of a structure the skill does not have. Where a
later review round runs over that diff, the marked hunks SHALL be named to it along with the same
rejected-alternatives check. Where no later round runs, the marks SHALL surface in the skill's
terminal report.

**Marking SHALL be required only where it discriminates.** In a fix loop that has no delegate at all,
every remedy is orchestrator-specified, so a per-remedy mark distinguishes nothing and its presence
would read as a signal it does not carry; there the fact SHALL be stated once for the loop instead.
Per-remedy marking SHALL be required where delegated and orchestrator-applied remedies can occur in
the same round. The adjudication check itself SHALL run on both.

This obligation SHALL NOT be discharged by raising a round cap or by making an additional round
unconditional. The control is in-round and is deliberately weaker than an independent reader; the
skill's text SHALL say so rather than implying the two are equivalent.

#### Scenario: An orchestrator-applied fix is checked against the rejected alternatives

- **WHEN** the orchestrator applies a fix for a finding itself rather than delegating it
- **THEN** its post-fix re-verification reads the change's design document rejected-alternatives content
- **AND** it confirms the applied remedy does not reintroduce a rejected alternative

#### Scenario: The check finds a reintroduced rejected alternative

- **WHEN** the rejected-alternatives check finds that the applied remedy reintroduces a rejected decision
- **THEN** it is raised as a Critical finding against that remedy
- **AND** the remedy is withdrawn or re-specified rather than allowed to stand on having resolved the original finding
- **AND** where the rejection itself is judged wrong, the design document is amended explicitly rather than contradicted silently

#### Scenario: The remedy is marked for the next reader

- **WHEN** a fix round contains a remedy the orchestrator specified
- **THEN** that finding's record carries an orchestrator-specified marker
- **AND** a later review round over that diff is told which hunks carry the marker
- **AND** where no later round runs, the marker appears in the terminal report

#### Scenario: The control does not change a round cap

- **WHEN** this obligation is stated in a skill
- **THEN** no round cap or default round count is raised to satisfy it
- **AND** the text states that the in-round check is weaker than an independent reader

#### Scenario: The check reads the document as it stood before the remedy

- **WHEN** the orchestrator's remedy is itself an edit to the rejected-alternatives document
- **THEN** the check reads that document as captured at the start of the fix round, before the round's edits
- **AND** a remedy is never adjudicated against a document the same remedy just edited
- **AND** the pre-edit content is obtained without requiring the document to be committed, since a fix loop that runs before the change is first committed would otherwise have no version to read

#### Scenario: A fix loop with no rejected-alternatives document is out of scope

- **WHEN** a skill applies orchestrator-specified fixes but operates on no change directory
- **THEN** it has no rejected-alternatives document and the check does not bind it
- **AND** the marking obligation does not bind it either, there being nothing for a later reader to check a mark against
- **AND** the obligation is stated as conditional on such a document existing
- **AND** the absence of the document is not reported as a breach of the obligation

### Requirement: Grounding contract enumerates the claim shapes that do not look like claims

A cla-plugin review workflow whose grounding contract binds every claim to evidence SHALL additionally
enumerate, beside that rule, the sentence shapes whose truth depends on something outside the artifact
but whose grammar is not assertive. The enumeration SHALL be stated as part of the grounding contract
rather than as further independent numbered checks appended to the workflow's check list.

The reason SHALL be recorded with the enumeration: the failures this addresses are **recognition**
failures, not procedure failures. In each reported instance the reviewer already held the grounding
rule, already held the license to read source, and did not engage either — because the sentence
presented as an explanation, a comparison, a specification of output, or a trade rather than as an
assertion about existing code.

**Four shapes SHALL be named**, each stated as a trigger, a resolution naming what to read and what to
resolve it against, a failure mode, and a severity floor. A shape stated only as an instruction to
confirm that a claim is grounded SHALL NOT satisfy this requirement.

1. **Producible state.** Triggered by an artifact specifying a fixed set of example, demo, fixture, or
   sample states a surface must show. Resolution: name and read the production function or query that
   would produce each state; resolve the predicate gating it against the **real data the system will run on** rather than
   the fixture's; record the producing path with the corpus figure, or an explicit not-producible with
   the line that forbids it. Having searched and found no producing path SHALL resolve as **not producible**; NOT having searched SHALL resolve as unresolved, and SHALL carry no severity floor. The negative default applies once the reviewer has looked, because an absent producing path is itself the finding — it does not apply to a reviewer who ran out of budget, which the grounding contract already routes to unresolved. Severity floor: an unproducible state written as a requirement is
   **Critical**, because such a requirement does not fail loudly — the available resolution under
   implementation pressure is to invent the data.
2. **Precedent strictness.** Triggered by an artifact naming an existing shipped implementation as the
   precedent it mirrors, follows, or is modelled on. Resolution: read the named precedent's actual
   mechanism at its path; for each provision the new requirement imposes, record whether the precedent
   satisfies it, does not satisfy it, or does not have it; for each provision the precedent does not
   satisfy, state what the extra strictness buys and who pays. Severity floor: **Important**, rising
   to **Critical** where the provision blocks implementation. The text SHALL state why no other check
   finds this: every other check asks whether the artifact is strong enough, and this one asks whether
   it is stronger than it needs to be.
3. **Guarantee class.** Triggered by an artifact stating that a mechanism prevents, controls,
   serialises, or makes impossible a hazard. Resolution: classify the guarantee as a **code property**
   — a constraint, a lock, a registration, a type, a test that goes red — or a **deployment property**,
   true only because of how many processes, instances, workers, or regions run today; for a code
   property, quote the enforcing line; for a deployment property, require the artifact to say so and to
   name the trigger condition that changes it. Leaving the guarantee unclassified SHALL itself be the
   failure, because the two read identically in prose and the gap becomes visible only once the
   deployment fact changes, at which point the hazard returns with no code change and nothing red.
   Severity floor: a deployment property with no named trigger is **Important**; a deployment property
   described as a code property is **Critical**, being a false statement about what the code enforces.
4. **Compensating coverage and exclusion reach.** Triggered in two ways. Where a change gives up
   automated coverage for a named alternative, the resolution SHALL be to read the named replacement
   and confirm what kind of assertion it actually runs, then state its strength relative to what was
   given up — the given-up half is visible in the diff and the replacement is a promise, so the promise
   is the half verified. Where an exclusion entry is added to any keyed allowlist or denylist, the resolution SHALL be to enumerate the components or modules reachable only
   through the excluded surface and, for each, name where it is otherwise covered or state that it is
   not. Severity floor: **Important** for an unverified compensating claim, **Critical** where the
   replacement is measurably weaker than what it replaced.

**The list SHALL be stated as open, by signature rather than by disclaimer.** The common signature
SHALL be given — a sentence is a claim under this contract when its truth depends on something outside
the artifact even though its grammar is not assertive — together with the grammars that hide one: an
explanation, a comparison to something shipped, a specification of output shape, and a trade. A
sentence matching that signature SHALL be in scope whether or not it appears among the named shapes.

**Exactly one numbered check SHALL be added to the workflow's check list**, pointing at the shape list
rather than restating it, so that the shapes are reached during the workflow's verification sweep and
not only by a reader of the contract section. No existing check SHALL be renumbered or reworded, and
every enumeration of which checks the orchestrator runs SHALL be updated to name the new one.

**That check SHALL be stated as outside the mechanical portion that defaults to a fact-gathering
sub-agent**, and the exclusion SHALL appear in the paragraph where the delegation decision is made, not
only where the check is defined. Each shape returns a judgement — a comparison of two mechanisms, a
classification, an assessment of one test's strength against another's — rather than a pass or fail
row, so a sub-agent returning a pass/fail table cannot carry it.

The shapes SHALL be stated so that no repository-specific mechanism, product name, or infrastructure
identifier from the reporting instances travels into the portable text.

#### Scenario: The shapes are named inside the grounding contract

- **WHEN** the review workflow's grounding contract is stated
- **THEN** the four claim shapes are enumerated as part of that contract
- **AND** they are not added as four further independent numbered checks

#### Scenario: Each shape is executable rather than an instruction to verify

- **WHEN** a claim shape is stated
- **THEN** it names its trigger, the resolution steps naming what to read and what to resolve it against, its failure mode, and its severity floor
- **AND** a shape whose text only instructs the reviewer to confirm the claim is grounded is treated as not meeting the requirement

#### Scenario: An unproducible demo state resolves negative rather than unresolved

- **WHEN** a reviewer has searched for the production path that would produce a specified demo state and found none
- **THEN** the state resolves as not producible rather than as unresolved
- **AND** the requirement specifying it is graded Critical
- **AND** where the reviewer has not searched, the row resolves as unresolved instead and carries no severity floor

#### Scenario: A guarantee is classified before it is accepted

- **WHEN** an artifact states that a mechanism prevents a hazard
- **THEN** the reviewer classifies the guarantee as a code property or a deployment property
- **AND** a code property is resolved by quoting the enforcing line
- **AND** a deployment property is accepted only where the artifact says so and names the trigger that changes it

#### Scenario: A compensating-coverage claim is read rather than accepted

- **WHEN** a change gives up automated coverage in exchange for a named alternative
- **THEN** the reviewer reads the named replacement and records what kind of assertion it actually runs
- **AND** states the replacement's strength relative to what was given up

#### Scenario: An exclusion's reach is enumerated

- **WHEN** an exclusion entry is added to a keyed allowlist or denylist
- **THEN** the components or modules reachable only through the excluded surface are enumerated
- **AND** each is paired with where it is otherwise covered, or stated to be uncovered

#### Scenario: The enumeration carries its reason

- **WHEN** the claim shapes are stated in the contract
- **THEN** the text says why they are enumerated — that these are recognition failures, not procedure failures
- **AND** it is stated with the list rather than left to a reader to infer from the shapes themselves

#### Scenario: A shape carries no trace of the instance that produced it

- **WHEN** a shape is written from a specific reported failure
- **THEN** its text names no repository, product, module, route, or infrastructure identifier from that instance
- **AND** the shape is stated so a repository with a different architecture can still apply it
- **AND** a shape that can only fire in the reporting instance's kind of product is rewritten or dropped

#### Scenario: An unnamed shape matching the signature is in scope

- **WHEN** an artifact carries a sentence whose truth depends on code, corpus, precedent, deployment, or a test file, phrased as an explanation, a comparison, an output specification, or a trade
- **THEN** the contract covers it whether or not it matches one of the named shapes
- **AND** the contract states this as a signature rather than as a closing disclaimer

#### Scenario: The shapes reach the reviewers who produce the findings

- **WHEN** a review dispatches agents to produce its findings rather than adjudicating inline
- **THEN** the shape list is carried in those agents' own briefs, not only in the orchestrator's sweep
- **AND** the shape text is carried into each prompt in full, never as a pointer to the contract, because a dispatched agent does not load the skill and cannot resolve one
- **AND** a shape whose resolution requires re-reading the change artifacts is stated as not delegable to that dispatch

#### Scenario: The sweep reaches the shapes and is not delegated

- **WHEN** the workflow's verification sweep runs
- **THEN** one numbered check points at the shape list, and every enumeration of the orchestrator's checks names it
- **AND** that check is stated as outside the mechanical portion that defaults to a fact-gathering sub-agent
- **AND** the exclusion appears in the paragraph where the delegation decision is made

### Requirement: Reviewer report severities are reconciled by the evidence behind them

A cla-plugin review workflow that dispatches more than one reviewer and merges their reports SHALL
state how a finding reported by two of them at different severities is graded. Where the reports
disagree, the merged severity SHALL be taken from the report whose evidence for that severity is
**implementation-level** — a source line, a schema, a migration, a query result — over the report
whose evidence is the specification delta or the artifact text alone.

**The rule SHALL key on the evidence attached to the finding, not on which reviewer reported it.**
Where every dispatched reviewer is licensed to read source, the reviewer's role does not identify who
read the implementation, so a role-keyed rule is not decidable from the reports the orchestrator
holds. The evidence is, and it is present because the grounding contract already requires every
finding to carry its resolving evidence.

Where neither report's evidence is implementation-level, or both are, the **higher severity SHALL
stand**. This fallback SHALL NOT be stated as the primary rule: applied unconditionally it converts
every disagreement into an escalation, inflating the counts that the workflow's own verdict rubric
already warns against reading literally.

The tie-break SHALL be recorded on the finding it resolved, so that a reader can see one occurred, and
SHALL NOT add a line to the report, which is budgeted at one line per finding.

**The rule's evidence SHALL be stated with it and SHALL NOT be presented as measured.** It rests on a
single overlapping finding out of eighteen, from one change in one chain in one consuming repository,
and the observed instance was a two-reviewer split under a different workflow rather than the dispatch
this rule governs. The text SHALL state that low overlap is the reviewer split working as intended and
that the rule is therefore expected to fire rarely.

#### Scenario: Two reports grade one finding differently

- **WHEN** two dispatched reviewers report the same finding at different severities
- **THEN** the merged severity is taken from the report whose evidence is implementation-level
- **AND** the report whose evidence is the specification delta or artifact text alone does not set the severity

#### Scenario: Neither report's evidence discriminates

- **WHEN** neither report's evidence for the severity is implementation-level, or both are
- **THEN** the higher severity stands
- **AND** this is stated as the fallback rather than as the rule

#### Scenario: The tie-break is visible without costing a report line

- **WHEN** a severity tie-break is applied
- **THEN** it is recorded on the finding it resolved
- **AND** no additional line is added to the report

#### Scenario: The rule carries its own evidence honestly

- **WHEN** the tie-break rule is stated
- **THEN** it names its single supporting instance and the total it came from
- **AND** it states that the instance came from a different dispatch shape
- **AND** it is not described as measured

### Requirement: A dispatched agent runs its gates in the foreground

A cla-plugin brief SHALL instruct the agent it dispatches to run every gate — build, lint, test, or
any other correctness command — in the foreground and to wait for it, however long it takes. The brief
SHALL state that the agent must not end its turn while a command it started is still running.

The rule SHALL key on **who is running the command**, not on the command's expected duration. A
duration threshold SHALL NOT be used for this decision, because duration is not what makes
backgrounding unsafe: a command of any length that a dispatched agent backgrounds before returning has
an unreachable result. The brief SHALL give the reason rather than only the prohibition — that a
backgrounded command does not survive the agent's return, and that ending its turn is what produces
that return, so no completion notification can reach it afterwards.

This SHALL NOT be stated as a third legitimate condition for ending a turn, and SHALL NOT weaken the
existing rule that an orchestrator session may end a turn with a backgrounded dispatch in flight. That
condition rests on a notification re-invoking the session, which is true of a session and false of a
dispatched agent; this requirement names the actor for whom the condition does not exist.

Where a gate's expected duration approaches or exceeds what a single foreground call permits in the
running harness, the skill SHALL NOT delegate that gate: the orchestrator runs it after the dispatch
returns, or dispatches the work without it and gates afterwards. An agent that meets such a gate SHALL
return the blocked status naming it rather than backgrounding it. The permitted foreground duration
SHALL be resolved against the running harness at dispatch time and SHALL NOT be written into the
shipped prose as a constant, since a constant is wrong in every harness whose limit differs.

#### Scenario: The brief requires foreground gates

- **WHEN** a skill briefs an agent that will run a correctness gate
- **THEN** the brief requires the gate to run in the foreground and to be waited for
- **AND** it forbids ending the turn while a started command is still running

#### Scenario: The rule keys on the runner, not the duration

- **WHEN** the foreground obligation is stated
- **THEN** it applies to the dispatched agent regardless of the gate's expected duration
- **AND** no duration constant is used to decide whether a gate may be backgrounded

#### Scenario: The orchestrator's own backgrounding is unchanged

- **WHEN** the obligation is stated alongside the existing turn-liveness rule
- **THEN** an orchestrator session may still end a turn with a backgrounded dispatch in flight
- **AND** no third legitimate turn-ending condition is introduced

#### Scenario: A gate too long to run in one call is not delegated

- **WHEN** a gate's expected duration approaches what one foreground call permits
- **THEN** the skill does not delegate that gate
- **AND** an agent that meets one returns blocked naming it rather than backgrounding it
- **AND** the permitted duration is resolved against the running harness rather than written as a constant

### Requirement: A return is classified by its evidence, not by its prose

A cla-plugin skill SHALL classify every return from a dispatch **whose brief declares a terminal-status contract** by a scan for the fields that brief required, performed before the return's prose is acted on. The scan SHALL check two things: that the return carries a status token from the closed set the brief named, and that it carries every evidence field the brief's terminal contract required.

**The scope is set by the brief, not by the fact of dispatching.** A dispatch whose brief declares no
status set and no evidence contract — a read-only gatherer returning a pass/fail table, a sweeper
returning a hit list, a reviewer returning severity-prefixed finding lines — is outside this
requirement, and a skill SHALL NOT classify such a return as blocked for lacking a token its brief
never asked for. This is the same test this change applies to its other obligations: a rule is
stated over a dispatch kind only where it is applicable to every instance of that kind. Where a
skill wants this protection for a gatherer-shaped dispatch, the way to get it is to give that brief a
terminal-status contract, not to widen the scan.

A return missing either SHALL be treated as **blocked**, whatever its prose says — including a return
that reads as finished, that reports a result, or that states it is waiting on something. The
classification SHALL be stated as a scan rather than a judgement, because the failure it covers
produces a return that reads exactly like a completion and the reader is the party least able to tell
the difference.

The skill SHALL NOT introduce an additional terminal status for this case. The existing statuses are
declared by the dispatched agent; this classification is made by the orchestrator about an agent that
declared nothing, so a status the agent could select is the wrong mechanism.

An evidence-free return SHALL be recorded as a contract firing in the run's issue record, on the same
footing as a return that claimed completion without evidence, so that the frequency of the failure is
observable rather than absorbed.

#### Scenario: An evidence-free return is blocked

- **WHEN** a dispatched agent returns without a status token or without a required evidence field
- **THEN** the orchestrator classifies the return as blocked
- **AND** it does so regardless of whether the return's prose reads as finished

#### Scenario: A dispatch with no declared status contract is out of scope

- **WHEN** a skill dispatches an agent whose brief declares no status set and no evidence contract
- **THEN** the return is not classified as blocked for lacking a status token
- **AND** the requirement's scope is read from the brief rather than from the fact that a dispatch occurred

#### Scenario: The classification is a scan, not a reading

- **WHEN** the classification rule is stated in a skill
- **THEN** it names the fields to look for and instructs the reader to look for them
- **AND** it does not rest on the reader judging how the return reads

#### Scenario: No status is added for the case

- **WHEN** the rule is stated
- **THEN** the terminal status set is unchanged
- **AND** the evidence-free return is classified as blocked rather than given a status of its own

#### Scenario: The firing is recorded

- **WHEN** a return is classified blocked for missing evidence
- **THEN** the event is recorded as a contract firing in the run's issue record
- **AND** it is not silently absorbed by recovering inline

### Requirement: One checkout has one writer, stated to both parties

A cla-plugin skill whose dispatched agents work in the orchestrator's own checkout SHALL state the
single-writer discipline in **both** directions, because a brief reaches only the agent and the party
that most needs binding is the one writing the brief.

**Agent-facing.** The brief's do-not-touch guidance SHALL name the repository-state-mutating commands
explicitly rather than stating the principle, and the enumeration SHALL include the commit and push
and reset verbs alongside the checkout, switch, branch, stash and worktree verbs, since an
implementing agent commits and a cleanup reset destroys work the orchestrator staged. It SHALL also
forbid two non-git shared resources: killing, restarting or cleaning up a process the agent did not
start, and deleting or regenerating a build, cache or dependency directory the agent did not create.

This guidance SHALL be standard in every dispatch rather than added per brief. The test for making it
standard SHALL be that no dispatch kind exists for which it is inapplicable — every dispatch shares the
orchestrator's checkout — which distinguishes it from a field whose honest content would be "not
applicable" in some dispatches and which therefore teaches readers to skim.

**Orchestrator-facing.** While a dispatch has not returned, or a command started under it may still be
running, the orchestrator SHALL run no repository-state-mutating git command and no gate in that
checkout, and SHALL delete or regenerate nothing that dispatch builds into. This SHALL be stated where
the orchestrator reads, and SHALL be placed as a further case of the skill's existing shared-checkout
guidance rather than as a separate section, because both cases are the same invariant — two agents
writing to one checkout — and separating one invariant into two documents lets them drift.

The skill SHALL additionally state that a failure observed in a checkout the orchestrator disturbed
while a dispatch of its own was live is **not evidence of a regression**, and SHALL require it to be
re-derived from a quiet tree before being investigated as one. This second half SHALL NOT be omitted on
the grounds that the first half prevents the situation: the recorded incident's cost was not the
interference but the investigation of self-inflicted failures as a possible real regression, which is
reached only after the first half has already failed.

#### Scenario: The agent-facing enumeration covers commit, push and reset

- **WHEN** a brief states which commands the dispatched agent may not run
- **THEN** the enumeration names the commit, push and reset verbs as well as checkout, switch, branch, stash and worktree
- **AND** it forbids killing a process the agent did not start
- **AND** it forbids deleting or regenerating a build, cache or dependency directory the agent did not create

#### Scenario: The prohibition is standard, not per-brief

- **WHEN** a skill dispatches any agent into the orchestrator's checkout
- **THEN** the prohibition is part of the standard brief rather than typed for that dispatch
- **AND** the justification given is that no dispatch kind exists for which it is inapplicable

#### Scenario: The orchestrator-facing half lives where the orchestrator reads

- **WHEN** the single-writer rule is written down
- **THEN** the orchestrator-facing half is placed in the skill's own shared-checkout guidance
- **AND** it is a further case of that guidance rather than a separate section
- **AND** it is not left to the brief, which reaches only the agent

#### Scenario: Manufactured failures are not treated as regressions

- **WHEN** a failure is observed in a checkout the orchestrator touched while its own dispatch was live
- **THEN** that failure is not treated as evidence of a regression
- **AND** it is re-derived from a quiet tree before being investigated as one

#### Scenario: The response to a missing return is re-dispatch, gated on quiet

- **WHEN** the orchestrator must act on a return that carried no evidence
- **THEN** it first confirms by read-only means that nothing the dispatch started is still running
- **AND** its default next move is one re-dispatch naming the omitted evidence fields
- **AND** it takes over the checkout only after that confirmation, never before it

### Requirement: A brief legitimises stopping rather than inventing a value

A cla-plugin brief SHALL state, as standard language in every dispatch rather than as a sentence typed
for a particular task, that every value its terminal contract asks for is one the dispatched agent
produced — not one it estimated, inferred, or carried over from an earlier run or another file.

The clause SHALL be placed adjacent to the evidence requirement it qualifies, because that requirement
is what creates the incentive it counteracts: a contract demanding a run summary puts an agent that
cannot run the command in a position where a plausible-looking value is the cheapest compliant output.
Placed elsewhere the clause is a statement of virtue; placed there it is the exception branch of the
rule above it.

An agent that cannot produce a required value SHALL return the blocked status naming the field it could
not fill and why, and the brief SHALL state that such a return is a **successful** return rather than a
failure, so that the honest answer carries no penalty. A value the agent did not itself produce SHALL be
a reportable defect, recorded as a contract firing, rather than treated as a formatting slip.

This SHALL compose with, and SHALL NOT contradict, the rule that a wrong factual claim supplied *in* a
brief is grounds for the agent to reject the proposed remedy. The two govern opposite directions:
inbound claims the orchestrator supplied are corrected or cause a remedy rejection; outbound evidence
the agent supplies is real or causes a blocked return. Neither resolves to proceeding with a guess, and
neither adds a terminal status beyond the shared set.

#### Scenario: The clause is standard and adjacent to the evidence requirement

- **WHEN** a skill states its brief's terminal contract
- **THEN** the no-invented-values clause is part of the standard contract text
- **AND** it sits beside the evidence requirement rather than elsewhere in the brief

#### Scenario: An unobtainable value produces a blocked return

- **WHEN** a dispatched agent cannot produce a value the contract requires
- **THEN** it returns blocked naming the field it could not fill and why
- **AND** the brief states that this is a successful return rather than a failure

#### Scenario: An invented value is a reportable defect

- **WHEN** a returned value was estimated, inferred, or carried over rather than measured
- **THEN** it is treated as a reportable defect and recorded as a contract firing
- **AND** it is not treated as a formatting problem to be tidied up

#### Scenario: Inbound and outbound claim rules do not collide

- **WHEN** both this clause and the inbound wrong-claim rule are stated in one brief format
- **THEN** a wrong claim the brief supplied leads to a correction or a remedy rejection
- **AND** evidence the agent cannot produce leads to a blocked return
- **AND** no terminal status beyond the shared set is introduced by either

### Requirement: A second Revise round asks a different question

A Revise round N ≥ 2 dispatched over a previous round's fix diff SHALL be framed by a question distinct from round 1's, and MUST NOT be dispatched as a repeat of round 1 over a smaller diff.

Two rounds fall outside that condition because neither has a "this fix" to ask about: a round entered
on an empty `PREV_FIX_SHA`, which reviews the whole PR, and a rejection-only re-entry, which
dispatches against open findings rather than a diff. On those the question SHALL be skipped rather
than asked ill-posed, and the round's `sibling_instance` SHALL be `null` rather than `0`, so the skip
is legible in the record instead of resting on prose the record cannot carry.

Round 1 asks whether the diff is correct. A later round exists because the previous round's own fix
is new, unreviewed code written under time pressure by whoever had just diagnosed the defect, and the
defects it produces have a characteristic shape: the fix recreates the defect it removed, at a second
site, or it repairs the reported instance and leaves a sibling instance untouched. The question the
round asks SHALL therefore be, verbatim:

> Does this fix introduce the defect it fixed, somewhere else? Enumerate every other instance of the
> resource or shape the fix concerns.

The **enumeration is the deliverable, not the re-read.** The round's dispatch SHALL name every other
instance of the resource or shape the previous round's fix concerns, and state per instance whether
the defect is present there. An empty enumeration is a stated result — "no other instance exists" —
and SHALL NOT be an omitted step, for the same reason the deferred-findings sections print `(none)`
under an empty heading rather than dropping it: an absent section and an unexamined one read
identically.

The question and its enumeration obligation SHALL appear in the Revise reference's round-N ≥ 2
section, where the round's dispatch is assembled, AND as a load-bearing invariant in the
orchestrator skill's Revise stub, which is required to remain self-sufficient when the reference is
not reloaded.

#### Scenario: A later round is dispatched with the distinct framing

- **WHEN** the Revise loop dispatches a round N ≥ 2 over the previous fix commit's diff
- **THEN** the dispatch carries the round-≥2 question verbatim, not round 1's framing
- **AND** it instructs the reviewer to enumerate every other instance of the resource or shape the
  previous round's fix concerns

#### Scenario: The fix's own safety addition recreates the defect elsewhere

- **WHEN** round 1's fix for a count-versus-match divergence adds a cap that reintroduces the same
  divergence at a second call site
- **THEN** the round-2 enumeration lists that second site as an instance of the same shape
- **AND** the reintroduced divergence is reported as a finding of that round rather than shipping

#### Scenario: No other instance exists

- **WHEN** the round-2 reviewer finds that the resource or shape the fix concerns occurs nowhere else
- **THEN** it reports the enumeration as empty with that statement
- **AND** the empty enumeration is recorded as a result, not treated as a step that was skipped

#### Scenario: Round 1 is not asked the round-2 question

- **WHEN** the Revise loop dispatches round 1
- **THEN** the round-≥2 question is not part of that dispatch, because round 1 has no previous fix
  for it to be adversarial about

#### Scenario: A round with no fix to ask about skips the question

- **WHEN** a round ≥ 2 is entered on an empty `PREV_FIX_SHA`, or as a rejection-only re-entry
  dispatched against open findings
- **THEN** the round-≥2 question is not part of that dispatch, because there is no previous fix for
  it to concern
- **AND** that round's `sibling_instance` is `null`, so the skip is not later read as a measured zero

### Requirement: The enumeration is made answerable, and its answer is checkable

A dispatch carrying the round-≥2 question SHALL supply the three things without which the
enumeration cannot honestly be produced. The question alone is not the mechanism; asking for a list
an agent has no way to build yields a confident list nobody built.

**The orchestrator SHALL name the resource.** It holds the finding, the remedy and the reason that
remedy was chosen; a dispatched agent holds a diff. The resource SHALL be named concretely enough to
bound the search — a function's call sites, a function's branches returning a given value, the
readers of a config key — rather than left for each agent to infer. An unnamed resource yields a
different scope per agent and nothing comparable between them.

**The dispatch SHALL grant the search.** The round's prompt inlines a scoped diff and instructs the
agent not to re-read it, and a sibling instance is by definition outside that diff. The prompt SHALL
therefore state that the agent may read and search the repository to answer this question, under the
read-only discipline the sub-agent brief already carries. Without the grant the question is
unanswerable as briefed.

**The return SHALL cite the search it ran**, and an enumeration that cites none is a **missing**
result rather than an empty one. A confident "no other instance" costs an agent nothing to write, so
the citation, not the conclusion, is what the orchestrator checks — by re-running the cited search
and comparing its hits against the enumerated list.

**That check SHALL resolve into one of three outcomes, each with a stated consequence**, because a
check whose failing branches are unwritten is a check that passes by default:

- **Cited and consistent** — the re-run search's hits are the enumerated list. The enumeration is
  taken as a result, and its confirmed sibling instances are counted into that round's
  `sibling_instance`, restricted to the Critical-plus-Important findings `found` counts, since
  `sibling_instance` is a subset of `found`.
- **Cited but inconsistent** — the re-run search returns hits the enumeration does not list. The
  unlisted hits SHALL be treated as unexamined and checked by the orchestrator before triage, rather
  than being read as instances the agent cleared.
- **Uncited** — the enumeration is missing rather than empty. The agent SHALL be re-dispatched once
  with the resource named; if the return is uncited again, the round's `sibling_instance` SHALL be
  `null` rather than `0`, and the outcome SHALL be captured as a Handoff issue.

That re-dispatch is an ordinary agent dispatch: its findings enter the round's counts and triage the
way any other agent's do, and it counts once toward the run record's dispatch and routing totals.
Only the enumeration *check* is count-neutral — it decides whether the round has an enumeration, and
changes no finding count by itself.

#### Scenario: The prompt names a bounded resource

- **WHEN** a round ≥ 2 is dispatched over a previous fix
- **THEN** the prompt names the specific resource or shape that fix concerns
- **AND** it does not leave each agent to infer the subject of the enumeration

#### Scenario: The agent is told it may search

- **WHEN** the dispatch carries the enumeration question
- **THEN** it states that the agent may read and search the repository to answer it
- **AND** that grant coexists with the instruction not to re-read the inlined diff, which governs the
  diff rather than the repository

#### Scenario: An uncited enumeration is not an empty one

- **WHEN** a return states that no other instance exists but names no search
- **THEN** the result is treated as missing rather than as an empty enumeration
- **AND** the agent is re-dispatched once with the resource named
- **AND** if the second return is still uncited, the round records `sibling_instance` as `null` and
  the outcome is captured as a Handoff issue, rather than recorded as a measured zero

#### Scenario: A cited search that disagrees with its own enumeration

- **WHEN** the orchestrator re-runs the cited search and it returns instances the enumeration does
  not list
- **THEN** those unlisted instances are treated as unexamined and checked before triage
- **AND** they are not read as instances the agent inspected and cleared

#### Scenario: The re-dispatch is an ordinary dispatch

- **WHEN** an agent is re-dispatched because its enumeration was uncited
- **THEN** any findings it returns enter that round's counts and triage like any other agent's
- **AND** the dispatch is counted once in the run record's dispatch and routing totals
- **AND** the enumeration check itself changes no finding count

### Requirement: The Revise round cap is a ceiling, not the loop's exit condition

Wherever the Revise round cap is stated in the Revise reference or the orchestrator skill's Revise stub, the skill SHALL also state that the cap is a ceiling rather than a target.

`--pr-rounds` defaults to `2`. The loop's step "triage every Critical and Important finding" requires
each such finding to be resolved in the round that surfaced it, and the exit gate then counts
*untriaged* Critical and Important findings alongside *open* ones, exiting only when both are zero.
A reader who takes `default 2` as a promise of two rounds is reasoning about the wrong control, which
is precisely the misreading that makes the round-count question look already answered.

**The untriaged count is NOT zero by construction, and this requirement SHALL NOT say that it is.**
An earlier draft did. A rejection carrying no reason that resolves against the brief's own defect or
fact rows counts as untriaged at the gate, and the loop's own step 5 branches on the cap being
exhausted with findings still untriaged — a state a by-construction zero would forbid. The gate is
also two counts, not one: a loop with open findings is ended by the cap, so a zero untriaged count
would not on its own establish what ends the loop.

**That is what the text says, and practice diverges from it.** Measured over
`cla.io/retro/spec-to-pr-runs.jsonl` with `python -c "import json;[print(r.get('change'),p.get('rounds_used'))
for r in map(json.loads,open('cla.io/retro/spec-to-pr-runs.jsonl',encoding='utf-8')) for p in
r['phases'] if p['name']=='Revise']"`: six records, `rounds_used` of `1, 2, 2, 2, (skipped), 2`
against a cap of 2 — **four of the five runs that ran Revise used a second round** the gate as
written should have ended.

So the statement this requirement obliges is deliberately narrow. It SHALL say that the cap is a
ceiling rather than a target, and it SHALL NOT assert what ordinarily ends the loop, because both
available assertions are false: the exit gate as written does not describe four of five logged runs,
and the cap does not describe the fifth. A live specification claiming a behaviour the ledger
contradicts is a false statement with a specification's authority. Reconciling the divergence —
closing it upward or downward — is explicitly NOT this requirement's job: closing it upward is the
default change this change declines, and closing it downward would delete an observed behaviour on
the strength of a document.

This requirement is satisfied by an accurate statement at the two sites that name the cap. It SHALL
NOT oblige an annotation at the exit gate itself: an earlier draft did, and the annotation it asked
for rested on the withdrawn "ordinarily ends at the gate" premise. It SHALL NOT change the cap's
value, the exit gate's threshold, or anything that alters how often a second round runs.

#### Scenario: The cap is named in the reference and in the skill stub

- **WHEN** a reader encounters the `--pr-rounds` default in either the Revise reference or the
  orchestrator skill's Revise stub
- **THEN** the same sentence tells them the default is a ceiling rather than a target
- **AND** it does not claim the untriaged count is zero by construction, because a reason-less
  rejection routes to untriaged and the cap does end a loop that still holds open findings

#### Scenario: The clarification changes no numbers

- **WHEN** the clarification has been applied
- **THEN** the `--pr-rounds` default remains `2`, `--review-rounds` remains `1`, and `--test-rounds`
  remains `3`
- **AND** the per-loop caps table carries the same values it carried before the edit

#### Scenario: A run that stops after one round is not a capped run

- **WHEN** a run's record shows the Revise phase used one round against a cap of two
- **THEN** that run is read as having exited at the gate with every finding triaged, not as having
  been cut short by a budget

### Requirement: A declined default names the ledger evidence that would reverse it

A default this workflow declines to change on thin evidence SHALL carry a reversal condition stated against the run ledger.

The proposal to make a second Revise round unconditional is declined. The evidence for it is a single
chain of three to four changes, one still in flight when it was recorded; every change that reached a
round 2 found something, which is a rate of one hundred percent on a denominator of four and is
suggestive rather than a base rate. A default is a cost every run pays and is priced against a base
rate, so the default stays where it is.

The deferral SHALL name its reversal condition, verbatim:

> Revisit the `--pr-rounds` default when `findings_by_round` covers at least eight changes across at
> least two distinct chains in which a round ≥ 2 ran, and a round ≥ 2 surfaced at least one Critical
> or Important finding on a majority of them.

The two-chain floor is the originating decision's own. The eight-change denominator and the majority
bar are stated judgements rather than measurements, and SHALL be labelled as such where they appear,
so a later pass argues with a written number instead of inventing one.

That condition is not answerable from the run ledger as it stands: the Revise phase record carries
`rounds_used`, and the per-agent finding counts are summed across every round, so nothing attributes
a finding to the round that surfaced it. The Revise phase record SHALL therefore carry
`findings_by_round`: an array, in round order, with one entry per dispatched round, each entry
recording the round number, that round's deduplicated Critical-plus-Important `found` count, and
`sibling_instance` — of that `found`, how many were the shape the round-≥2 question targets, being a
defect the previous round's fix introduced or a sibling instance the previous round's fix missed,
which is `0` on round 1.

The field is optional and additive: records written before it stay valid, and an absent field is
distinguishable from a round that found nothing, which is an entry with `found: 0`.

The schema note SHALL state the relation between the two fields spelled `found` as an **inequality
with its equality case named**, not as a prohibition on equality. Restricted to findings an agent
surfaced, the sum of the per-agent `found` is **greater than or equal to** the sum of
`findings_by_round`'s `found`: the per-agent field credits one finding to every agent that surfaced
it and counts phantoms, while this one is deduplicated after triage. The two are **equal whenever
every finding was surfaced by exactly one agent**, which is common, so a match SHALL NOT be read as
producer drift. The note SHALL also name the one case that inverts the relation: a finding the
orchestrator originates rather than an agent — an INT-CAP/INT-SYC or SIR-TEST re-verification hit, or
a Critical on an orchestrator-specified remedy — enters the per-round total and no per-agent bucket,
because `revise_findings_by_tier` is keyed strictly by canonical agent id. An assumed equality
between two fields spelled `found` is exactly the kind of invariant a later reader would act on, and
an unqualified inequality is the same mistake in the other direction.

`sibling_instance` SHALL have a spelling for "no measurement was produced", distinct from both a
measured `0` and an absent `findings_by_round`. That spelling is JSON `null`. It is written when the
round was never asked the question, and when the round was asked and its enumeration stayed uncited
after the one re-dispatch. A round that was asked and found no sibling instance writes `0`. Round 1
writes `0`, which is a definition rather than a measurement: it has no previous fix.

#### Scenario: The deferral is stated with its reversal condition

- **WHEN** a reader asks why a second Revise round is not the default
- **THEN** the skill states the deferral, the evidence behind it, and the reversal condition verbatim
- **AND** the eight-change denominator and majority bar are labelled as judgements rather than
  measurements

#### Scenario: A run with two rounds is logged with per-round attribution

- **WHEN** the Revise phase runs two rounds and the run record is appended
- **THEN** `findings_by_round` holds one entry per round in round order
- **AND** round 1's entry carries `sibling_instance: 0`
- **AND** round 2's entry carries that round's own deduplicated Critical-plus-Important count and its
  sibling-instance subset

#### Scenario: An older record without the field stays valid

- **WHEN** a run record written before this field existed is read from the ledger
- **THEN** the absent `findings_by_round` is not an error and is not counted as producer drift
- **AND** it is not read as a round that found nothing, which would be an entry with `found: 0`

#### Scenario: The two `found` counts are related by an inequality, not a prohibition

- **WHEN** a reader compares `findings_by_round`'s per-round `found` totals with the per-agent
  finding counts on the same record
- **THEN** the schema states the per-agent sum is greater than or equal to the per-round sum, and
  why: one finding surfaced by two agents is credited twice per-agent and once per-round
- **AND** it names the equality case — every finding surfaced by exactly one agent — so a match is
  not read as producer drift
- **AND** it names the inverting case — a finding the orchestrator originates, which lands in the
  per-round total and in no per-agent bucket

#### Scenario: A round that produced no measurement is not logged as a zero

- **WHEN** a round ≥ 2 was never asked the question, or was asked and its enumeration stayed uncited
  after the one re-dispatch
- **THEN** that round's `sibling_instance` is `null`, not `0`
- **AND** a reader can distinguish it from a round that was asked and found no sibling instance,
  which is `0`, and from a record predating the field, which has no `findings_by_round` at all

### Requirement: A ledger field kept for a deferred decision states the test it qualifies under

The run-log schema's rule is that it lists only fields the aggregator reads. A field kept for a
deferred decision rather than for the aggregator is an exception to that rule, and the schema SHALL
state the exception's qualifying test and its exit rather than asserting the exception for one field.

**The test SHALL be one the field's own change cannot satisfy by itself.** A deferral and the field
that excuses it, authored together, certify each other, and anyone could qualify an unread field by
adding a paragraph naming it. A field therefore qualifies only when a requirement that has been
reviewed and archived into this plugin's live spec names it as the evidence that requirement's own
reversal condition reads — not prose written beside the field in the same change.

**The test SHALL be resolvable by a reader of the shipped file.** The schema ships verbatim into
consuming repos, where a path-shaped test naming this repo's spec tree can never be evaluated. The
test SHALL therefore name the plugin's own spec as the authority rather than a repo-relative
directory the consumer would resolve against their own tree.

**The exception SHALL state its exit**: when the reversal condition is met, or the requirement naming
the field is removed, the field falls back under the main rule — added to the aggregator or dropped.

#### Scenario: The exception names a test the change cannot self-certify

- **WHEN** a reader asks why a field the aggregator never reads is listed in the schema
- **THEN** the schema states that the field qualifies only on a requirement archived into the
  plugin's live spec, not on prose in the same change
- **AND** it gives the reason: a deferral and its own field would otherwise certify each other

#### Scenario: A consumer can evaluate the test

- **WHEN** the schema is read in a repo that installed the plugin from the marketplace
- **THEN** the qualifying test names the plugin's own spec as the authority
- **AND** it does not require the reader to resolve a path against their own repository's spec tree

#### Scenario: The exception states when it lapses

- **WHEN** the requirement naming the field is removed, or its reversal condition is met
- **THEN** the schema says the field loses the exception and returns to the main rule
- **AND** it names when that check happens, since nothing runs it automatically

### Requirement: A MODIFIED block is compared against the live requirement it replaces

A skill that reviews, archives, or sequences a change SHALL compare each `## MODIFIED Requirements` block's scenario set against the live requirement that block will replace, and SHALL NOT treat the block's internal completeness as evidence of retention.

A modified-requirement block replaces its named requirement wholesale rather than patching it, so a scenario present on the live requirement and absent from the block is deleted at sync or archive. A current `openspec` refuses that apply, and a repo on an older version gets no such refusal — so the loss is caught late, by a tool the plugin does not own and may not be running, or not at all. The block is internally consistent either way: it carries a full requirement text and a list of scenarios in both the retaining and the dropping case, so **the omission is not visible in the delta at all** and any instruction phrased as a property of the delta alone cannot be checked.

**The obligation attaches to the block, not to the workflow that produced it.** It SHALL apply wherever a change carrying such a block is reviewed before implementation, prepared for archive, or sequenced within a batch — a change authored and shipped outside any batch passes through no cross-change sequencing step and would otherwise be compared nowhere.

**The comparison baseline SHALL be the live specification as it stands at the moment of the check**, not as the delta was authored. A correct block goes stale when anything else reaches the live specification first — a sibling in the same batch, a change archived from an earlier batch, a small change landed in between, a hand edit.

**Where a step already locates the live requirement for another purpose, the comparison SHALL be carried by that step** rather than added beside it. A step that confirms a modified block's heading exists in the live specification has already resolved the requirement the comparison needs, and stopping at the heading is what leaves scenario retention unchecked.

This requirement is distinct from validating the live specification set's parse integrity after an edit: that concerns whether the document still parses, whereas this concerns content the delta silently omits, which parses correctly and reads correctly. It is also distinct from an enforcing refusal inside the tool that applies the delta — **nothing in this requirement blocks, edits, or refuses a change.**

#### Scenario: A change outside a batch is still compared

- **WHEN** a change carrying a modified-requirement block is taken to a pull request on its own, passing through no cross-change sequencing step
- **THEN** the comparison runs anyway, at that change's own pre-implementation review and again before its archive
- **AND** a comparison available only to batch-sequenced changes does not satisfy this

#### Scenario: Heading existence is not retention

- **WHEN** a step confirms that a modified block's requirement heading exists verbatim in the live specification
- **THEN** that step also compares the scenario headings under it
- **AND** a confirmed heading with an unexamined scenario set is recorded as unchecked, not as a pass

#### Scenario: A delta that looks complete on its own face

- **WHEN** a modified block carries a full requirement text and a list of scenarios, while the live requirement it replaces carries more scenarios than the block does
- **THEN** the comparison reports the difference
- **AND** an instruction satisfied by reading the delta alone is treated as not covering this

#### Scenario: The baseline is current, not as-authored

- **WHEN** the live requirement changed after the delta was written
- **THEN** the comparison reads the live specification as it stands at the moment of the check
- **AND** comparing against the text the delta was authored against does not satisfy this

#### Scenario: A change with no modified block

- **WHEN** a change's delta contains no modified-requirement block
- **THEN** the check is reported as not applicable, naming what was scanned
- **AND** it is not recorded as a passing comparison

### Requirement: Renames are resolved before a comparison reports a loss

A retention comparison SHALL resolve the delta's requirement-rename mapping before matching a modified block to a live requirement, and SHALL treat every remaining difference as a flag for adjudication rather than as a confirmed loss.

A rename and a deletion are byte-identical to a comparison of headings, and exactly one of them destroys a live normative statement. Ordering is therefore load-bearing: a comparison that resolves renames at any later point reports every renamed requirement as missing from the live specification. This was measured — the one real execution of an unordered comparison flagged two items across two changes and both were benign renames, one of them caused precisely by an unresolved rename mapping.

**Rename resolution SHALL NOT be claimed to eliminate false positives.** A rename mapping names requirements, not scenarios, so a scenario renamed in place — its heading rewritten to widen its scope, its content retained — remains indistinguishable from a deleted scenario and remains flagged. That was the second of the two measured flags. A residual false-positive rate is a property of the delta format, not a defect in the procedure.

**Because a flag can be a rename, nothing SHALL refuse, halt, or auto-correct on a flag alone.** Each flagged scenario SHALL be adjudicated to exactly one of: renamed, intentionally removed, or dropped. Only *dropped* is a finding. An intentional removal SHALL cite the change's own artifacts; asserted without a citation it carries a lower severity than a drop but is still reported, because the verdict is then a claim rather than a reference.

**An unadjudicated flag SHALL be treated as dropped, not as waived.** The comparison exists to force an adjudication, and defaulting an unexamined flag to benign returns the situation to the one where the loss is silent.

#### Scenario: A requirement renamed by the same delta

- **WHEN** a modified block names a requirement that does not appear in the live specification, because the same delta's rename section renames it
- **THEN** the rename is resolved first and the block is matched to the live requirement under its old name
- **AND** the requirement is not reported as absent

#### Scenario: A scenario renamed in place is still flagged

- **WHEN** a live scenario's heading was rewritten in the delta to widen its scope, with its behaviour retained
- **THEN** it is flagged as missing and adjudicated as renamed
- **AND** the procedure does not claim to have distinguished it mechanically

#### Scenario: A flag does not block the change

- **WHEN** a comparison flags one or more scenarios
- **THEN** the change is not refused, halted, or edited by the comparison itself
- **AND** the flag is carried to whoever adjudicates it

#### Scenario: An unadjudicated flag is a finding

- **WHEN** a flagged scenario reaches the end of the step with no verdict recorded
- **THEN** it is treated as dropped and reported at the severity a dropped scenario carries
- **AND** it is not recorded as resolved because nothing contradicted it

### Requirement: A retention report states both directions and its denominator

A retention comparison SHALL report added scenario counts alongside missing ones, for every compared requirement, including one where nothing is missing.

A missing-only report cannot separate a widening from a truncation. Both present as "one scenario missing", and telling them apart then costs opening both documents — the work the report exists to remove. Stating the live count, the delta count and both differences on one line makes a block that grew and reorganised distinguishable at a glance from one that lost a normative statement.

**A comparison that found nothing SHALL still report what it examined.** Silence and a clean result are indistinguishable to a reader, and so are a clean result and a step that did not run. The report SHALL name how many modified requirements were compared, across how many capabilities, how many were flagged, and how many flags were adjudicated to each verdict.

**A failed enumeration SHALL be reported as a failed check, not as an empty result.** A command that errors — run from the wrong directory, against a repository that stores its specifications elsewhere, against a capability whose live file is absent — yields no headings, and reading that as "no differences" converts a check that never ran into a confident pass across every requirement it was meant to cover.

#### Scenario: A widening is distinguishable from a truncation

- **WHEN** a modified block carries more scenarios than the live requirement, while one live scenario heading is absent from it
- **THEN** the report states the live count, the delta count, the added count and the missing count together
- **AND** a reader distinguishes the widening from a truncation without opening either document

#### Scenario: A clean requirement is reported, not omitted

- **WHEN** a compared requirement's scenario sets match exactly
- **THEN** the report states its counts with both differences at zero
- **AND** omitting it is not treated as reporting it

#### Scenario: The run states its denominator

- **WHEN** a step finishes comparing a change's modified blocks
- **THEN** it reports how many requirements were compared across how many capabilities, how many were flagged, and how each flag was adjudicated
- **AND** a bare statement that nothing was found does not satisfy this

#### Scenario: An enumeration that errored is not zero differences

- **WHEN** a command enumerating headings from either document exits non-zero
- **THEN** the check is reported as failed for that requirement
- **AND** the absent headings are not read as an empty set, and no requirement covered by that command is reported as clean
