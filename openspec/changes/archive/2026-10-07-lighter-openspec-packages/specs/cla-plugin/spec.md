## ADDED Requirements

### Requirement: A change is complete without design.md

An authoring or review skill SHALL treat a change as complete with proposal.md, tasks.md and at least one spec delta, or `skip_specs`, whether or not it has a design.md.

#### Scenario: A change without design.md passes the authoring post-check

- **WHEN** multi-spec's authoring agent writes a change that no stock trigger applies to
- **THEN** it writes no design.md and reports `done` with proposal.md, tasks.md and a spec delta present
- **AND** the post-check accepts the change

### Requirement: design.md is written only on a named stock trigger

An authoring skill SHALL write design.md only when a stock OpenSpec trigger applies (a cross-cutting change, a new dependency or data model, security, performance or migration complexity, or real ambiguity), and SHALL name that trigger in its report.

#### Scenario: A design.md names its trigger

- **WHEN** an authoring agent writes design.md
- **THEN** its report names the stock trigger that applied

### Requirement: Review reads an absent design.md as absent

A change review SHALL stop as incomplete only when proposal.md is missing. When design.md is absent, the review SHALL read it as "(absent)" and pass "(no design.md)" to any dispatched agent.

#### Scenario: A change without design.md is reviewed

- **WHEN** review-change reviews a change that has no design.md
- **THEN** the review runs to a verdict instead of stopping
- **AND** every agent prompt carries "(no design.md)" in place of the design content

### Requirement: A pinned-parameters block only for a load-bearing number

The multi-spec authoring brief SHALL require a pinned-parameters block only when design.md exists and the change has a load-bearing number, such as a threshold, cap or weight.

#### Scenario: A change with no load-bearing number

- **WHEN** an authoring agent writes a change with no threshold, cap, weight or similar load-bearing number
- **THEN** it adds no pinned-parameters block

### Requirement: Authoring requires no doc-sync task

The multi-spec authoring brief SHALL NOT require a separate doc-sync task in tasks.md.

#### Scenario: Tasks without a doc-sync task

- **WHEN** an authoring agent writes tasks.md
- **THEN** the post-check accepts it with no doc-sync task

### Requirement: The authoring brief points to the stock limits

The multi-spec authoring brief SHALL state OpenSpec's stock limits in one line and point to the `openspec/config.yaml` rules rather than copy OpenSpec's instruction text.

#### Scenario: The brief states the limits

- **WHEN** an authoring agent reads the brief
- **THEN** it finds the stock limits in one line with a pointer to the `openspec/config.yaml` rules

### Requirement: An oversized or restating artifact is an Important finding

A change review SHALL report an Important finding for a proposal over one page, an ADDED requirement over 500 characters or stating several behaviours, or an artifact that restates the proposal or the specs. A MODIFIED requirement SHALL be exempt from the length check, since OpenSpec forbids trimming it outside a change made to split it.

#### Scenario: An ADDED requirement is too long

- **WHEN** a delta adds a requirement of more than 500 characters
- **THEN** the review reports an Important finding naming it

#### Scenario: A long MODIFIED requirement

- **WHEN** a delta carries a MODIFIED requirement of more than 500 characters
- **THEN** the review reports no size finding for it

### Requirement: Cutting is a FIX FIRST remedy and is preferred

The review verdict rubric SHALL list cutting a restated or redundant section among the FIX FIRST remedies. When a finding can be fixed either by adding text or by cutting it, the review SHALL prefer the cut.

#### Scenario: A finding that a cut resolves

- **WHEN** a finding can be resolved by removing a section that restates another artifact
- **THEN** the recommended fix is the cut

### Requirement: Design headings do not buy the large-change review

The review size gate SHALL NOT count design decisions, however headed, and SHALL select the 3-agent review from files, subtasks, capabilities and claims alone. Its complexity-concentration override SHALL fire only when 15 or more subtasks are concentrated in one or two files.

#### Scenario: Many decision headings in a narrow change

- **WHEN** a change touches two files, has 8 subtasks and 6 `### D` headings in design.md
- **THEN** the size gate selects the small-change path

### Requirement: Every new or modified scenario names its proof

Each scenario a change adds, or whose text it changes, SHALL have a test task whose test carries a `scenario: <spec> / <heading>` comment line, or a tasks.md line `manual: <heading>: <reason>`. A pure heading rename, and a scenario carried forward unchanged in a MODIFIED block, SHALL be exempt. Scenario headings SHALL be unique within one spec, so `<spec> / <heading>` names one scenario.

#### Scenario: Authoring a scenario

- **WHEN** an authoring agent adds or modifies a scenario
- **THEN** its test carries a `scenario: <spec> / <heading>` comment line above it, or tasks.md carries `manual: <heading>: <reason>` for it

#### Scenario: A pure heading rename

- **WHEN** a change renames a scenario heading and leaves the scenario's body unchanged
- **THEN** the renamed scenario needs no new test task or `manual:` line

#### Scenario: Authoring a heading that is already taken

- **WHEN** an authoring agent adds a scenario whose heading already names another scenario in that spec
- **THEN** it renames the new heading so that `<spec> / <heading>` stays unique

### Requirement: A scenario with no proof is an Important finding

A change review SHALL report as an Important finding a scenario the change adds or rewrites that has neither a test task nor a `manual: <heading>: <reason>` line, and a scenario heading the change adds that repeats one in the same spec. It SHALL report a test task that names no `scenario:` marker as a Suggestion.

#### Scenario: A scenario with no proof

- **WHEN** a delta adds a scenario and tasks.md has neither a test task for it nor a `manual: <heading>: <reason>` line
- **THEN** the review reports an Important finding naming the scenario

#### Scenario: A repeated scenario heading

- **WHEN** a delta adds a scenario whose heading already names another scenario in the same spec
- **THEN** the review reports an Important finding naming the heading

#### Scenario: A test task that names no marker

- **WHEN** a test task proves a scenario but does not name the `scenario: <spec> / <heading>` comment its test will carry
- **THEN** the review reports a Suggestion, which does not block the verdict

### Requirement: A ticked task that names a test is checked for that test

spec-to-pr's Implement post-check SHALL search the tree for each test a ticked task names. A miss SHALL be recorded as a Handoff issue and the test finished inline, as for a done claim without evidence.

#### Scenario: A ticked test task whose test is missing

- **WHEN** a ticked task names a test that the search does not find
- **THEN** the run records a Handoff issue and writes the test before leaving Implement

### Requirement: A change multi-spec already reviewed skips the checklist pass

spec-to-pr's Review SHALL skip the checklist pass only when the change directory is clean, its files still match the digest in its `review.json`, and that record says READY, or FIX FIRST with every Critical and Important finding applied and none deferred. It SHALL still run the inherited-obligation check, the MODIFIED-block retention comparison and the doc-sweep, and SHALL log Review as `skip` with the verdict it trusted.

#### Scenario: A change multi-spec passed

- **WHEN** spec-to-pr runs on a clean change whose files match its `review.json` digest
- **AND** the record says `FIX FIRST`, `all_applied: true` and no deferred finding
- **THEN** Review skips the checklist pass and logs `skip` with reason `reviewed by multi-spec: FIX FIRST`

#### Scenario: A change multi-spec did not pass

- **WHEN** the record says `RETHINK`, or `all_applied: false`, or lists a deferred finding
- **THEN** Review runs the full checklist and reports each deferred finding as a known issue

#### Scenario: A change with no usable review record

- **WHEN** the change has no `review.json`, or it does not parse as JSON
- **THEN** Review runs the full checklist

#### Scenario: A change edited after multi-spec's review

- **WHEN** a later commit, or an uncommitted edit, touched the change directory
- **THEN** Review runs the full checklist

#### Scenario: A passed batch merged with a merge commit

- **WHEN** a READY change's proposals PR was merged with a merge commit
- **THEN** its files still match the record's digest, and Review skips the checklist pass

#### Scenario: An edit squashed in after multi-spec's review

- **WHEN** a commit pushed to the proposals PR after its review edited the change, and the PR was squash-merged
- **THEN** the change's files no longer match the record's digest, and Review runs the full checklist

### Requirement: multi-spec records each change's review verdict

multi-spec's review gate SHALL write `review.json` into every change directory it reviews, whatever the verdict, in the commit that applies its fixes. The record SHALL state the verdict, whether every Critical and Important finding was applied, each deferred Critical or Important finding, a digest of the reviewed files, and the date.

#### Scenario: A READY change gets a review record

- **WHEN** multi-spec's gate rates a change READY with nothing to fix
- **THEN** the gate's commit adds that change's `review.json` with `verdict: READY` and `all_applied: true`

#### Scenario: A finding deferred out of scope

- **WHEN** the gate defers an Important finding as out of scope
- **THEN** the change's record lists it under `deferred` and sets `all_applied: false`

#### Scenario: A review record passes strict validation

- **WHEN** a change directory carries its `review.json`
- **THEN** `openspec validate <name> --strict` and `openspec archive` still pass

### Requirement: multi-spec's batch review is size-gated per change

multi-spec's batch review SHALL apply the checklist's size gate to each change, and SHALL dispatch the three review agents only when at least one change in the batch is large.

#### Scenario: A batch of small changes

- **WHEN** every change in a batch grades small
- **THEN** the batch review runs inline with no agent dispatch

### Requirement: The review report carries no parallelism plan and no claim quota

A change review report SHALL NOT include an implementation-parallelism section and SHALL NOT require a minimum number of verified claims. It SHALL keep the claim-shape sweep row in its open questions.

#### Scenario: A small change is reviewed

- **WHEN** a review report is printed
- **THEN** it has no implementation-parallelism section
- **AND** its open questions carry the claim-shape sweep row

### Requirement: cla-init seeds OpenSpec authoring rules without clobbering

cla-init SHALL seed `openspec/config.yaml` with `schema: spec-driven` and a `rules:` block stating the stock limits and the scenario-proof rule when `openspec/` exists and holds neither `config.yaml` nor `config.yml`. This is project data, the one path cla-init writes outside `cla.io/`. Otherwise cla-init SHALL print the block and write nothing.

#### Scenario: No config.yaml

- **WHEN** cla-init runs in a repo with `openspec/` and no `openspec/config.yaml`
- **THEN** it creates the file with the rules block and reports `created`

#### Scenario: An existing config.yaml

- **WHEN** cla-init runs in a repo whose `openspec/config.yaml` exists
- **THEN** the file is byte-identical afterwards and the rules block is printed

#### Scenario: An existing config.yml

- **WHEN** cla-init runs in a repo whose `openspec/config.yml` exists and `openspec/config.yaml` does not
- **THEN** no `openspec/config.yaml` is created, `config.yml` is byte-identical afterwards, and the rules block is printed

### Requirement: A change with no behaviour change carries no spec delta

A change with no externally visible behaviour change, such as a refactor, tooling or docs, SHALL set `skip_specs: true` in its `.openspec.yaml` and write no spec delta, rather than invent a requirement to satisfy validation.

#### Scenario: A docs-only change

- **WHEN** multi-spec's authoring agent writes a change that alters no behaviour
- **THEN** it sets `skip_specs: true` and writes no spec delta
- **AND** the post-check accepts the change

### Requirement: An invented requirement is an Important finding

A change review SHALL report a requirement that describes no observable behaviour change as an Important finding, with dropping it and setting `skip_specs` as the remedy.

#### Scenario: An invented requirement

- **WHEN** a delta adds a requirement that describes no observable behaviour change
- **THEN** the review reports an Important finding whose remedy is to drop it and set `skip_specs`

### Requirement: Live specs are read overview-first

A skill that reads live specs for context SHALL first list them with `openspec list --specs` and read an overview with `openspec show <id> --type spec --json --no-scenarios`, and SHALL read in full only the specs the change touches. A MODIFIED carry-forward SHALL still copy the full live requirement and all its scenarios.

#### Scenario: Authoring a change that touches one capability

- **WHEN** an authoring agent needs context from a repo with several capabilities
- **THEN** it reads the overview first and reads in full only the capability its delta touches

### Requirement: multi-pr records Suggestions by default

multi-pr's recommended no-unresolved-issues policy SHALL fix every Critical and Important finding before a change counts done, and SHALL record Suggestion-level findings in `TODO.md` without fixing them. Fixing Suggestions too SHALL remain available as the full-severity choice at the Phase 1 gate.

#### Scenario: A change ships with a Suggestion open

- **WHEN** a change's Revise leaves only Suggestion-level findings under the default policy
- **THEN** the change counts done and the Suggestions are recorded in `TODO.md`

#### Scenario: The user picks full-severity

- **WHEN** the user picks the full-severity policy at the Phase 1 gate
- **THEN** Suggestion residue triggers a fix round before the change counts done

### Requirement: A change without design.md resumes at the right phase

spec-to-pr's resume probe SHALL report Implement's artifacts ready when OpenSpec reports `isComplete`, or when `applyRequires` is non-empty and every artifact it names has status `done`. A missing or empty `applyRequires` SHALL count as not ready.

#### Scenario: Resume on a change with no design.md

- **WHEN** `openspec status` reports `isComplete: false`, `applyRequires: ["tasks"]` and tasks `done`
- **THEN** the probe reports `implement: true`

#### Scenario: Required artifact not done

- **WHEN** an artifact in `applyRequires` is not `done` and `isComplete` is false
- **THEN** the probe reports `implement: false`

#### Scenario: No applyRequires

- **WHEN** `isComplete` is false and `applyRequires` is missing or empty
- **THEN** the probe reports `implement: false`

## MODIFIED Requirements

### Requirement: Project-data scaffolding via `cla-init`

The `cla` plugin SHALL provide a `cla-init` skill at `.claude/plugins/cla/skills/cla-init/SKILL.md` (a `SKILL.md`, no command wrapper, invoked as `/cla:cla-init` per the plugin's namespacing convention) scoped exclusively to **project-data scaffolding**: the `cla.io/` tree below and, as the one path outside it, a missing `openspec/config.yaml` per the requirement "cla-init seeds OpenSpec authoring rules without clobbering". `cla-init` SHALL bring a fresh or partially-scaffolded destination repo up to the project-data baseline the other cla skills expect, resolving the repo root via `git rev-parse --show-toplevel` (the plugin's standard repo-state resolution seam) so it writes to the correct `cla.io/` regardless of the current working directory.

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
- **AND** a run against a fully-scaffolded repo is a no-op that writes nothing, where fully scaffolded includes an `openspec/config.yaml` or `openspec/config.yml` when `openspec/` exists

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
