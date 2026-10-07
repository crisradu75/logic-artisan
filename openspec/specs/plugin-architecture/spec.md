# plugin-architecture Specification

## Purpose

How the `cla` plugin is laid out, shipped, and kept portable: what lives in the plugin versus in each repo, how repo-specific facts are kept out of shared skill text, the skills that set up a repo's `cla.io/` data, and the checks that guard all of this.

## Requirements

### Requirement: Where plugin assets, repo data, and tests live

The plugin at `.claude/plugins/cla/` (manifest `.claude-plugin/plugin.json`, name `cla`) SHALL hold only portable assets a consuming repo can use: `skills/`, `agents/`, `hooks/`, `output-styles/`, and the `lib/` scripts skills call. Nothing repo-local, machine-local, or external SHALL be moved into it. Everything else SHALL live in one of three places:

- **`cla.io/`** (repo root): the plugin's workflow data — retro ledgers (`cla.io/retro/*.jsonl`), `lessons-learned/`, `decisions/`, `feedback/` — kept as ordinary repo content, not inside `.claude/`.
- **`.claude/`**: Claude Code config and host-repo assets — `worktrees/`, `settings.json`, `settings.local.json`, repo-local skills under `.claude/skills/`.
- **`plugin-tests/`** (source repo only): the plugin's tests, mutation batches, mutation runner, pytest config, and checks about this repo's own source. A consuming repo has no counterpart.

#### Scenario: Core assets are in the plugin, state stays project-level

- **WHEN** the repo is inspected
- **THEN** skills, agents, and guard hooks resolve from `.claude/plugins/cla/`
- **AND** workflow data lives under `cla.io/`, and `.claude/worktrees/`, `.claude/settings*.json`, and `.claude/skills/` stay under `.claude/`
- **AND** none of these is inside `.claude/plugins/cla/`

#### Scenario: Validation machinery is a third home, outside the plugin

- **WHEN** the source repo is inspected
- **THEN** the tests, mutation batches, mutation runner, and pytest config live under `plugin-tests/`
- **AND** none of them is inside `.claude/plugins/cla/`, `cla.io/`, or elsewhere under `.claude/`

### Requirement: In-place activation and namespacing

In the source repo the plugin SHALL be loaded live from the working tree with `claude --plugin-dir ./.claude/plugins/cla`. A consuming repo SHALL install it from the marketplace (`claude plugin marketplace add crisradu75/logic-artisan`, then `claude plugin install cla@cris-logic-artisan --scope project`), which runs from a read-only cached snapshot; this works because all repo state lives in the repo's own `cla.io/`.

Each workflow that carries a repo's own work SHALL be a skill (no command wrappers) invoked as `/cla:<skill>`. A workflow about publishing this plugin is not such a workflow: it SHALL be a repo-local skill under `.claude/skills/<name>/` in the source repo, invoked bare as `/<name>`, and SHALL resolve its own files by repo-relative paths rather than `${CLAUDE_PLUGIN_ROOT}`.

#### Scenario: Skills resolve under the cla namespace

- **WHEN** a session runs with `--plugin-dir ./.claude/plugins/cla` (source repo) or with the marketplace install (consuming repo)
- **THEN** each workflow skill is invocable as `/cla:<skill>` (e.g. `/cla:spec-to-pr`)
- **AND** no `.claude/commands/*.md` wrapper exists for any cla skill

#### Scenario: A marketplace install needs no write access to the plugin tree

- **WHEN** a consuming repo runs any cla skill from the cached install
- **THEN** every repo-local read or write targets `cla.io/` or other repo paths, never the plugin cache

#### Scenario: Internal composition uses the namespace

- **WHEN** one skill invokes another (e.g. `multi-pr` runs `spec-to-pr`)
- **THEN** it uses the namespaced form `Skill(cla:<name>)`

#### Scenario: A distribution workflow is invoked without the namespace

- **WHEN** the workflow that cuts this plugin's releases is invoked in the source repo
- **THEN** it resolves from `.claude/skills/` and is invoked as `/release`, not `/cla:release`
- **AND** it refers to its own files by repo-relative paths, not `${CLAUDE_PLUGIN_ROOT}`
- **AND** it is absent from a consuming repo, because it never ships

### Requirement: Scripts find the repo from git, not from their own location

Plugin scripts SHALL find repo locations without depending on where they sit in the plugin tree:

- Scripts that read or write the retro dir (`lib/log_run.py` and each retro aggregator) SHALL use `CLAUDE_RETRO_DIR` when set, otherwise `<git rev-parse --show-toplevel>/cla.io/retro`.
- Scripts that need the repo root (e.g. `probe_state.py` via `_git_common.py`) SHALL use `git rev-parse --show-toplevel`, not a fixed `parents[N]` depth, a walk to a `.claude` ancestor, or `${CLAUDE_PROJECT_DIR}`.
- A file that ships with the skill SHALL be found relative to the script; a repo file, including every overlay under `cla.io/overlays/`, SHALL be found from the repo root.

Each retro aggregator script, and each aggregator's test file, SHALL have a basename distinct from every other one, so the single pytest scope can collect them all.

#### Scenario: A plugin script writes to the repo's retro dir

- **WHEN** a retro script runs from the plugin with `CLAUDE_RETRO_DIR` unset
- **THEN** it finds the repo root with `git rev-parse --show-toplevel` and writes under that repo's `cla.io/retro/`

#### Scenario: Override is honored

- **WHEN** `CLAUDE_RETRO_DIR` is set to an absolute path
- **THEN** the script uses it directly and does not consult git

#### Scenario: A repo-root script resolves independently of depth

- **WHEN** `probe_state.py` runs from `.claude/plugins/cla/skills/spec-to-pr/scripts/`
- **THEN** it finds the repo root with `git rev-parse --show-toplevel`, not `parents[N]`
- **AND** it reads `cla.io/overlays/branch-prefix.local.md` from that root

#### Scenario: The two retro aggregators do not share a module name

- **WHEN** the retro aggregators and their tests are listed
- **THEN** `codify-retro` and `spec-to-pr-retro` each name their aggregator script and its test file distinctly, and no test file is named `test_aggregate.py`
- **AND** every skill instruction, test, and path list that names an aggregator uses its distinct name

### Requirement: Per-skill project-context overlay

Repo-specific content for a skill (repo-tuned checks, repo paths, the skill's own incident history, its permission-set intent) SHALL live in that skill's overlay at `cla.io/overlays/<skill>.md`, plus any `*.local.md` files beside it for narrower settings. Overlays live in the repo, not the plugin, because the installed plugin is read-only. A skill's text SHALL refer to its overlay by that fixed path, with no repository name in it.

An overlay SHALL open with a heading naming its skill and its role, and SHALL group its content under headed sections for the fact categories that skill uses, so it can be generated as an empty stub and checked. A missing or empty overlay is the normal unconfigured state: the skill's generic procedure SHALL still run, only without the repo detail. An overlay SHALL hold only facts specific to its skill; a repo-wide fact shared across skills SHALL appear only as a pointer to `cla.io/project-facts.md`.

An overlay at the old location, a skill's `references/project-context.md`, SHALL still be recognised as an overlay so a repo that has not migrated keeps its checks; new overlays SHALL NOT be created there.

#### Scenario: Repo checks live in a repo-neutral overlay

- **WHEN** `review-change` or `project-review` runs
- **THEN** it reads its repo-specific checks from `cla.io/overlays/<skill>.md` in the repo it runs in

#### Scenario: A generic skill references its overlay without naming the repo

- **WHEN** a `SKILL.md` or one of its references points at its overlay
- **THEN** it uses the fixed path `cla.io/overlays/<skill>.md`, with no repository name in it

#### Scenario: A skill carries multiple local overlay files

- **WHEN** a skill needs more than one overlay file
- **THEN** each extra file ends in `*.local.md` and is recognised as an overlay

#### Scenario: An empty or absent overlay does not gate the procedure

- **WHEN** a skill runs in a repo whose overlay is an empty stub (a heading plus empty fact sections) or is absent
- **THEN** the skill's generic procedure still runs to completion
- **AND** only the repo-specific detail is missing

#### Scenario: A per-skill overlay holds only skill-specific facts

- **WHEN** an overlay is written or trimmed
- **THEN** it holds only facts specific to that skill, plus pointers to `cla.io/project-facts.md` for any repo-wide fact it needs
- **AND** it does not restate a fact that lives in `cla.io/project-facts.md`

### Requirement: Guard hooks provided by the plugin

The plugin's guard hooks SHALL be wired in `.claude/plugins/cla/hooks/hooks.json` using the top-level `{"hooks": {…}}` wrapper (a bare event map loads but never fires). The file SHALL use only keys Claude Code's plugin loader recognises, at the top level and in each matcher group, since any other key prints a warning at every session start in every consuming repo. The check SHALL take the recognised keys from the installed Claude Code, fail when a required key is missing, and accept any other key the loader recognises. Commentary that does not fit `description` SHALL live in a scanned source file. Hook commands SHALL find their scripts via `${CLAUDE_PLUGIN_ROOT}` and the repo via `${CLAUDE_PROJECT_DIR}`. Hooks specific to a host repo SHALL stay in that repo's `.claude/settings.json`.

#### Scenario: A plugin guard hook fires

- **WHEN** a session with the plugin loaded makes a matching tool call
- **THEN** the guard hook runs (shown in `/hooks` as Source: Plugin)
- **AND** it finds its script through `${CLAUDE_PLUGIN_ROOT}` and the repo through `${CLAUDE_PROJECT_DIR}`

#### Scenario: Wrapper shape is enforced

- **WHEN** `hooks.json` is written
- **THEN** its top level is a `"hooks"` object keyed by event name, not a bare event map

#### Scenario: A commentary key is added to the hook wiring

- **WHEN** `hooks.json` gains a key the loader does not recognise (e.g. a top-level `_comment`, or one inside a matcher group)
- **THEN** the hook-wiring check fails, naming the key and the recognised set for that level
- **AND** the rationale belongs in `hooks/probe-python.sh`, with a one-line pointer in `description`

#### Scenario: A loader-recognised optional key is added

- **WHEN** `hooks.json` gains a top-level key the loader accepts, such as `$schema`
- **THEN** the check passes and no session-start warning appears

### Requirement: Skill fact/procedure separation

Every cla skill SHALL keep only generic procedure in its shipped text (`SKILL.md` and non-overlay `references/`) and put every repo-specific fact in its overlay, or in `cla.io/project-facts.md` when the fact is repo-wide. The rule is "extract a fact, keep a procedure."

- **Fact**: anything whose value is specific to this repo — repo commands, package/app/directory names and paths, repo-scoped permission sets, incident history, product or domain prose, ports, service and env-var names, lists of this repo's files or docs.
- **Procedure**: anything repo-independent — phases and their order, discipline and stop/continue rules, verdict and size-gate logic, schemas, the shape of a review/plan/report, generic tool use.
- **Mixed content** SHALL be split: the generic rule stays, reworded to be repo-neutral, with a pointer to the overlay where the detail helps; the incident or concrete command moves to the overlay. A reference file that is wholly fact moves into the overlay.
- A fact goes to `cla.io/project-facts.md` when it serves two or more skills or names a repo-wide command, port, workspace member, or path map; otherwise it stays in the skill's overlay.

Moving facts SHALL NOT change behaviour: with the overlay filled in, a skill gives the same guidance it did before. A skill with no repo facts needs no overlay.

#### Scenario: A synced skill body carries no repo-specific facts

- **WHEN** a skill's `SKILL.md` or non-overlay reference is inspected
- **THEN** it contains no repo-specific fact
- **AND** every fact it used to carry is in its overlay or in `cla.io/project-facts.md`

#### Scenario: Procedure is preserved generically

- **WHEN** a skill's phases, rules, verdict logic, or schemas are inspected after facts are moved out
- **THEN** they are still in `SKILL.md` or non-overlay references, reworded to be repo-neutral
- **AND** the skill's guidance is unchanged for a repo whose overlay is filled in

#### Scenario: A blended incident-justified rule is split

- **WHEN** a skill rule is justified by a specific past incident in this repo
- **THEN** the repo-neutral rule stays in `SKILL.md` with a pointer to the overlay
- **AND** the incident detail moves to `cla.io/overlays/<skill>.md`

#### Scenario: A reference file containing repo facts

- **WHEN** a non-overlay reference file is wholly repo fact
- **THEN** its content moves into the overlay (or a `*.local.md` beside it) and no wholly-fact reference file remains
- **AND** when the file mixes a generic shape (checklist, rubric, schema) with repo bullets, the shape stays, the bullets move to the overlay, and the file points there

### Requirement: Project-data scaffolding via `cla-init`

The plugin SHALL provide `/cla:cla-init` (`skills/cla-init/SKILL.md`), which sets up a repo's project data and nothing else. It SHALL find the repo root with `git rev-parse --show-toplevel` and create, only where missing:

- the directories `cla.io/decisions/`, `cla.io/feedback/`, `cla.io/retro/`, `cla.io/lessons-learned/`;
- empty (0-byte) ledgers `cla.io/retro/spec-to-pr-runs.jsonl` and `cla.io/retro/codify-runs.jsonl`, and no ledger for a loop that has no reader;
- `cla.io/feedback/notes.md` and `cla.io/lessons-learned/lessons-learned.md`, each with a short header;
- an empty overlay stub `cla.io/overlays/<skill>.md` (heading plus empty fact-category sections) for each skill that reads its own overlay for repo facts — not for a skill that only mentions the overlay path;
- `openspec/config.yaml`, per "cla-init seeds OpenSpec authoring rules without clobbering".

It SHALL NOT overwrite, truncate, or merge anything that exists, SHALL NOT fill stubs with real facts, SHALL NOT touch skill, agent, or hook files, and SHALL NOT touch `.claude-plugin/plugin.json` or `.claude/settings*.json` (those stay manual). Its SKILL.md and sync-context's SKILL.md SHALL state the onboarding order — marketplace install, then `cla-init`, then `/cla:sync-context` — and that the install provides skills but no project data.

#### Scenario: A fresh repo is scaffolded

- **WHEN** `cla-init` runs in a repo with no `cla.io/` tree
- **THEN** it creates the four directories, the two empty ledgers, the seeded `notes.md` and `lessons-learned.md`, and a stub for each skill that reads its own overlay
- **AND** it writes under the git repo root regardless of the working directory

#### Scenario: Re-run is idempotent and never clobbers existing project data

- **WHEN** `cla-init` runs where some or all of the scaffold exists (e.g. a ledger with history, a filled `notes.md`, a populated overlay)
- **THEN** every existing file and directory is left untouched, even if its content differs from the seed
- **AND** only missing pieces are created
- **AND** on a fully set-up repo (including `openspec/config.yaml` or `config.yml` when `openspec/` exists) it writes nothing

#### Scenario: Overlay stubs match the skills that consume an overlay

- **WHEN** `cla-init` seeds overlay stubs
- **THEN** it seeds exactly the skills that read their own overlay and lack one, and not a skill that only mentions the overlay path
- **AND** each stub is an empty skeleton, and no skill, agent, or hook file is read or changed

#### Scenario: cla-init does not wire the manifest or settings

- **WHEN** `cla-init` runs
- **THEN** it does not create, read, or modify `.claude-plugin/plugin.json`, `.claude/settings.json`, or `.claude/settings.local.json`

#### Scenario: Onboarding order is documented

- **WHEN** the SKILL.md files of `cla-init` and `sync-context` are read
- **THEN** both state the order: marketplace install → `cla-init` → `/cla:sync-context`
- **AND** they say the install provides the skills, `cla-init` creates the structure, and `sync-context` fills in the facts

### Requirement: Conformance guard for the overlay separation

The plugin SHALL ship a generic checker at `skills/_shared/scripts/check_no_project_tokens.py` that fails when a non-overlay shipped file contains a project token. The token list SHALL be per-repo data at `cla.io/project-tokens.local.md`, never hard-coded in the checker, curated to distinctive repo-specific tokens (not generic words), and matched case-insensitively.

- **How it runs**: as a program (`python3 <path>`), needing no pytest; on demand, never as a hook. It finds the plugin tree from its own file location (any fallback depth matching where it actually sits), never from a repo name or absolute path.
- **What one run does**: all four checks, without stopping at the first failure — project tokens in `SKILL.md` and `references/**/*.md` prose; project tokens in source files (code, JSON config, shell scripts, agent and output-style markdown) under its scan roots; hardcoded absolute developer paths in that source; and that every file it claims to have scanned was readable.
- **What it skips**: overlay files (leaf `project-context.md` or `*.local.md`), bytecode and cache dirs, and a markdown file's leading YAML frontmatter (skill trigger text may name the repo); line numbers stay accurate. Its scan roots SHALL name only directories that ship. A shipped file no scanner reaches SHALL be listed as an exemption with a reason, and that listing SHALL fail once a scanner reaches the file.
- **Output**: each violation as repo-relative path, token, line number, and excerpt, one per line, all in one run, with a non-zero exit. A clean run exits 0 and says what and how many files it scanned. "Could not run" (bad arguments, unreadable input) SHALL have its own exit status, separate from "violations found".
- **Token list states**: absent → exit 0 with a reason; present but yielding no tokens → fail, saying that deleting the file is how to turn the check off.

#### Scenario: A project token in a synced core file fails the guard

- **WHEN** a non-overlay `SKILL.md` or `references/**/*.md` under `skills/` contains a listed token
- **THEN** the checker exits non-zero and reports the repo-relative path, token, line number, and excerpt

#### Scenario: A skill's frontmatter description is exempt from the scan

- **WHEN** a `SKILL.md` names a token only in its frontmatter (e.g. `description:`)
- **THEN** that occurrence is not flagged
- **AND** the same token in the body is reported with its correct 1-based line number

#### Scenario: A project token in a shipped JSON file fails the guard

- **WHEN** a `.json` file under a scan root contains a listed token (e.g. in a `_comment` key)
- **THEN** the checker exits non-zero and reports it
- **AND** a `.json` file outside every scan root, such as the plugin manifest, is not scanned

#### Scenario: Overlay files are exempt from the scan

- **WHEN** a file named `project-context.md` or `*.local.md` contains a listed token
- **THEN** the checker does not scan it and does not fail

#### Scenario: The token list is per-repo data, not hard-coded

- **WHEN** the checker runs
- **THEN** it reads tokens from `cla.io/project-tokens.local.md` in the repo, outside the plugin, not from its own source

#### Scenario: An absent token list is a trivial pass

- **WHEN** no token list exists
- **THEN** the checker exits 0 with a stated reason

#### Scenario: A present-but-empty token list fails

- **WHEN** the token list exists but yields no tokens
- **THEN** the checker exits non-zero
- **AND** the message says deleting the file is how to turn the check off

#### Scenario: The plugin tree is resolved relative to the checker's own location

- **WHEN** the checker locates the plugin tree
- **THEN** it walks up from its own file, using no repo name or absolute path
- **AND** its fallback depth lands on the plugin root from where the checker actually is

#### Scenario: The checker is a program, not an authoring-time hook

- **WHEN** the checker is inspected
- **THEN** it runs as `python3 <path>` without pytest
- **AND** it is not wired as a hook and never blocks editing

#### Scenario: A single run performs every check and reports all of them

- **WHEN** more than one check finds violations
- **THEN** all of them are reported in that run

#### Scenario: An unreadable file is a failure, not a clean result

- **WHEN** a file under the scan roots cannot be read
- **THEN** the checker reports it and does not exit 0

#### Scenario: Every scan root names a directory that still ships

- **WHEN** the scan roots are listed
- **THEN** each one is a directory in the shipped plugin tree

### Requirement: Consolidated project-facts file

The plugin SHALL support one per-repo file, `cla.io/project-facts.md`, holding facts shared across skills — at least the workspace members, dev/build/test commands, ports, the affected-file map, the doc-sweep path list, and package and path names. Each repo owns its own; it is outside the plugin, so no install carries it between repos. A shared fact SHALL exist only in this file; overlays and skills SHALL point to it rather than copy it. When the file is missing, a pointer SHALL tell the reader to run `/cla:sync-context`, never fall back to an inline copy, and the skill SHALL still run.

#### Scenario: Shared facts live in one file

- **WHEN** a repo-wide fact (e.g. a dev command, a port, the doc-sweep path list) is recorded
- **THEN** it is written once in `cla.io/project-facts.md` and not copied into any overlay

#### Scenario: The consolidated file is per-repo and never distributed

- **WHEN** the plugin is installed or updated
- **THEN** the repo's `cla.io/project-facts.md` and `cla.io/terminology.md` are untouched

#### Scenario: A pointer degrades gracefully when the file is absent

- **WHEN** a skill points to `cla.io/project-facts.md` and the file does not exist
- **THEN** the reader is told to run `/cla:sync-context`, with no inline copy of the fact
- **AND** the skill still runs

### Requirement: Consolidated domain-terminology file

The plugin SHALL support one per-repo file, `cla.io/terminology.md`, defining this repo's own internal names: one-sentence entries in the form `**Term**: what it IS. _Avoid_: alias-1, alias-2`. It SHALL NOT hold external, regulatory, or business reference terms, and no cla skill SHALL read, change, or replace a repo's own glossary of that kind. It lives in `cla.io/`, outside the plugin.

Any skill that settles a naming question SHALL write the entry right away, in the same session, with its own edit — not deferred to a later pass and not by calling `/cla:sync-context`. The file is created by the first skill that needs it, not by `cla-init` or `sync-context`. `sync-context` SHALL document the entry format and the de-duplication and conflict rules. A pointer to this file is optional: a skill uses the term if the file has it, and otherwise proceeds on its own judgement, without prompting anyone to populate it.

#### Scenario: A resolved term is written inline, not batched

- **WHEN** a skill (e.g. `shape-decision`) settles a naming question during a session
- **THEN** it writes the entry to `cla.io/terminology.md` in that session
- **AND** it does not leave the write for a later `/cla:sync-context` run

#### Scenario: The terminology file is lazily created

- **WHEN** the first term is settled and `cla.io/terminology.md` does not exist
- **THEN** that skill creates it using the format `sync-context` documents
- **AND** `cla-init` does not create an empty one

#### Scenario: The terminology file never duplicates an external glossary

- **WHEN** a repo has its own external or business glossary (e.g. `docs/glossary.md`)
- **THEN** `cla.io/terminology.md` holds only internal naming
- **AND** no cla skill reads, edits, or replaces that glossary

#### Scenario: A pointer degrades gracefully without prompting a populate step

- **WHEN** a skill points to `cla.io/terminology.md` and the file is absent or lacks the term
- **THEN** the skill runs to completion using its own judgement for naming
- **AND** it does not ask for the file to be populated first

#### Scenario: sync-context owns the format, not exclusive writes

- **WHEN** a skill writes a terminology entry
- **THEN** it follows the format and de-duplication/conflict rules in `sync-context`'s SKILL.md
- **AND** it writes the entry itself rather than invoking `/cla:sync-context`

### Requirement: Context-refresh skill

The plugin SHALL provide `/cla:sync-context` (`skills/sync-context/SKILL.md`), which reads the repo's own manifests and config, with no stack-specific parser, and creates or updates `cla.io/project-facts.md`. It SHALL find the repo root with `git rev-parse --show-toplevel` and create `cla.io/` and the facts file when missing, so it works on a fresh repo alone.

It SHALL write only fact content: `cla.io/project-facts.md` and the pointer lines in overlays. It SHALL NOT create the `cla.io/` ledgers, inboxes, or overlay stubs (that is `cla-init`'s job) and SHALL NOT write the skill-specific body of an overlay. It SHALL propose, never silently add, new entries for `cla.io/project-tokens.local.md` when it finds a new distinctive app or package name. It SHALL document the `cla.io/terminology.md` format and may optionally reconcile near-duplicate or conflicting entries, but SHALL NOT write that file's content from scratch.

#### Scenario: Refresh populates the consolidated facts file

- **WHEN** `/cla:sync-context` runs
- **THEN** it reads the repo's own manifests and config, with no stack-specific parser, and writes the repo-wide facts into `cla.io/project-facts.md`

#### Scenario: Refresh acts as fact-init on a fresh repo

- **WHEN** `cla.io/project-facts.md` (and possibly `cla.io/`) is absent
- **THEN** it creates what is missing and fills the file, without needing `cla-init` to have run first

#### Scenario: Refresh resolves the repo root regardless of working directory

- **WHEN** it runs from a subdirectory
- **THEN** it writes `cla.io/project-facts.md` under the git repo root

#### Scenario: Refresh proposes new token-list entries for confirmation

- **WHEN** it finds a new distinctive app or package name not in `project-tokens.local.md`
- **THEN** it proposes the addition for the user to confirm and does not add it silently

#### Scenario: Refresh owns content, not structure

- **WHEN** it runs
- **THEN** it writes only `cla.io/project-facts.md` and overlay pointer lines
- **AND** it creates no ledgers, inboxes, or overlay stubs, and does not write an overlay's skill-specific body

### Requirement: Project-facts staleness guard

The plugin SHALL ship `skills/sync-context/scripts/check_fact_paths.py`, run as `python3 <path>` without pytest, which fails when a repo-relative path named in `cla.io/project-facts.md` or an overlay no longer exists as a file or directory.

- It SHALL find the repo root with `git rev-parse --show-toplevel`, never accepting the user's global `~/.claude` as a fallback, and never from its own location in the plugin.
- It SHALL check existence only, parse no stack-specific config, and take its recognised top-level prefixes from the repo's actual top-level entries.
- It SHALL treat a token as a path only when it clearly is one — contains a separator; is not a URL, `~` path, glob, or placeholder; and starts with a real top-level entry — after stripping backticks, punctuation, and any `:line[:col]` suffix. When unsure, it SHALL not flag.
- It SHALL report every stale path (file, line, path) in one run and exit non-zero. A clean run exits 0 and says what and how many files it scanned. "Could not run" SHALL have its own exit status. A missing `cla.io/project-facts.md` SHALL exit 0 with a reason.
- It SHALL state in its own text that it does not check commands, ports, or counts, nor detect a fact duplicated between the facts file and an overlay.

#### Scenario: A stale path in the facts file fails the guard

- **WHEN** the facts file or an overlay names a repo-relative path that no longer exists
- **THEN** the checker exits non-zero
- **AND** it reports the file, line, and path for every stale path in one run

#### Scenario: The guard is stack-agnostic and repo-derived

- **WHEN** the checker runs
- **THEN** it only checks whether paths exist, parsing no stack-specific config
- **AND** its recognised top-level prefixes come from the repo's own top-level entries

#### Scenario: An ambiguous non-path token is not flagged

- **WHEN** a token has no separator, is a URL, glob, or placeholder, or does not start with a real top-level entry
- **THEN** it is not flagged
- **AND** a directory path, or a path with a `:line` suffix or surrounding punctuation, is still checked correctly

#### Scenario: The checker runs as a program against the consuming repo

- **WHEN** a consuming repo runs the checker from inside that repo
- **THEN** it scans that repo's `cla.io/` files, with no pytest or setup needed

#### Scenario: A clean run states what it scanned

- **WHEN** no stale path is found
- **THEN** it exits 0 and reports how many files it scanned, so a run that scanned nothing is visible

### Requirement: Skill token-efficiency disciplines

Skills SHALL be written to keep their always-loaded text small, and orchestrator skills SHALL keep the context they accumulate small, without weakening any check that guards correctness.

1. **Load detail on demand.** A skill's `SKILL.md` SHALL keep inline only what every run needs: correctness checks, skill-wide rules, phase order, caps, and when to stop or ask — one line each where possible. Step-by-step mechanics, rationale, templates, and examples SHALL live in `references/*.md`, and each phase of a multi-phase skill SHALL start with a required "read its reference first" step. Correctness checks SHALL NOT move out of `SKILL.md`; each phase's inline text SHALL be enough to enforce its own check even if the reference is not read. Repo-specific examples moved out SHALL go to an overlay or `cla.io/project-facts.md`, not to a shared reference. The how-to is in `skills/_shared/references/skill-authoring.md`.
2. **Thin orchestrators.** A skill that drives other skills or agents across phases SHALL hand raw material (files, diffs, grep output) to sub-agents so only conclusions return; read slices, trim long output with `head`/`tail`, and pass large material via a scratch file; batch independent tool calls in one message; and ask agents for short structured output. When a sub-agent applies fixes, the orchestrator SHALL still verify that each fixed defect is gone.

A claimed size cut SHALL be checked with a `wc` before/after on `SKILL.md`, and the retro loop guards against regrowth; no automatic size limit SHALL be added. A size cut that came from moving correctness checks out of `SKILL.md` SHALL NOT count as a saving.

#### Scenario: A skill definition progressively discloses its mechanics

- **WHEN** a multi-phase skill's `SKILL.md` is inspected
- **THEN** correctness checks, skill-wide rules, phase order, caps, and stop/ask rules are inline
- **AND** step-by-step mechanics, rationale, templates, and examples are in `references/*.md`, each phase starting with a required read of its reference
- **AND** any moved repo-specific example lives in an overlay, not a shared reference

#### Scenario: Correctness-gating invariants stay inline

- **WHEN** content is moved out of `SKILL.md`
- **THEN** no correctness check (a skill-wide rule, a git-state or staging rule, the autonomy rule, a loop cap) is among it
- **AND** each phase's inline text states its check itself, not just a pointer to the reference

#### Scenario: An orchestrator skill runs thin

- **WHEN** an orchestrator handles bulk material (a large diff, many files, long command output)
- **THEN** it hands it to a sub-agent, reads slices, trims output, or uses a scratch file, so only conclusions return
- **AND** it batches independent tool calls and gets short structured output from agents

#### Scenario: Efficiency is measured, not size-gated

- **WHEN** an edit claims to shrink a `SKILL.md`
- **THEN** the claim is backed by a `wc` before/after
- **AND** there is no automatic size limit; the retro loop is the guard against regrowth

### Requirement: Shipped-asset boundary

The plugin directory SHALL contain only assets a consuming repo can use — skills, agents, hooks, output styles, the scripts they call, and the manifest and README — because the marketplace entry has no exclusion field and everything in the directory ships.

- The plugin's validation machinery SHALL live in `plugin-tests/` as one pytest scope with one `pyproject.toml`. The test gate SHALL be a single `pytest` run over that scope, with no aggregating runner. A Node test suite MAY live there with its own command.
- There SHALL be no source-repo-only marker files, nor a guard or runner logic that reads them.
- When an asset is moved out or deleted, every shipped file that names it (a skill instruction, a precondition, a scanner root list) SHALL be updated in the same change.
- The boundary SHALL be checked by the release-time scan, not by a test-suite guard; drift between releases is accepted until the next release.
- **Docs.** Consumer-facing docs SHALL say the release ships no test tree; give each shipped checker's command, flags, and exit statuses; say the consuming repo decides when they run (the plugin itself runs only the staleness checker, after `/cla:sync-context` writes); name any retired test path a consumer was told to wire in, and its replacement; and say which checker reads the consuming repo and which reads the plugin, without recommending the plugin-reading one as a gate for the repo. A statement about what reaches a consuming repo SHALL be true of the published tree, or be deleted or replaced — not softened.
- A named list of consumer-facing docs SHALL be checked automatically against the tracked files in the plugin directory, with retired top-level entries taken from published release tags. A retired path named in a migration note passes only through a recorded exemption that fails once the note stops naming it.

#### Scenario: The published tree carries no validation machinery

- **WHEN** the files in `.claude/plugins/cla/` are listed
- **THEN** there is no test directory, mutation batch, `pyproject.toml`, or mutation runner
- **AND** every file is one a consuming repo can invoke, read, or have run for it

#### Scenario: Consumer-facing guidance names no plugin path that does not ship

- **WHEN** the listed consumer docs are checked against the tracked plugin files
- **THEN** every plugin path they name exists there, and the check fails naming the doc and the path when one does not
- **AND** a path written without a plugin prefix is still caught when its first segment is a top-level entry a release tag shipped and the current tree lacks
- **AND** a tree diagram in those docs lists nothing absent from the tree
- **AND** a retired path in a migration note passes only via a recorded exemption, which fails once the doc stops naming it

#### Scenario: The documentation distinguishes the two checkers' subjects

- **WHEN** the docs present the shipped checkers to a consuming repo
- **THEN** they say no test tree ships, give each checker's command and exit statuses, and say the repo decides when to run them
- **AND** they say which checker reads the repo and which reads the plugin, and do not recommend the latter as a gate for the repo
- **AND** they name the retired test path an earlier release told consumers to wire in, and what to run instead

#### Scenario: The dev tree is one pytest scope

- **WHEN** the repo's tests are run
- **THEN** a single `pytest` run over `plugin-tests/` runs them, with no aggregating runner
- **AND** the dev tree has exactly one `pyproject.toml`

#### Scenario: No source-repo-only marker mechanism survives

- **WHEN** the plugin and dev tree are inspected
- **THEN** there is no source-repo-only marker file, and no guard or runner that reads one

#### Scenario: A scan root removed from the tree is removed from the scanner

- **WHEN** a directory in a shipped scanner's root list is moved out of the plugin
- **THEN** the entry is removed from that list in the same change

#### Scenario: The boundary is checked at the publication gate

- **WHEN** a release is prepared
- **THEN** the release-time scan checks the boundary before any tag is cut
- **AND** the test suite has no second guard duplicating it

#### Scenario: A false claim about the consumer's tree is deleted, not reworded

- **WHEN** a doc says an asset ships to or runs in a consuming repo and it no longer does
- **THEN** the statement is removed, not narrowed or qualified
- **AND** the surrounding text that is still true is kept unchanged

### Requirement: Release-time shipped-asset scan

Before cutting a tag, the release workflow SHALL check the shipped-asset boundary with a scan, alongside its other preconditions (on the default branch, clean tree, up to date with the remote, tests green, work reviewed and merged).

- The scan SHALL list the files git tracks under the plugin directory (not the working directory) and fail every file that matches no entry on an allowlist of permitted shapes. It SHALL NOT be a list of forbidden shapes.
- Each allowlist entry SHALL record why its shape is a consumer-usable asset. A separate check SHALL cap the number of entries, so adding one means raising the cap in the same change.
- Each entry SHALL be narrow enough that a test file, pytest config, or mutation batch placed inside a shipped directory is still rejected, and this SHALL be shown with test files of each excluded kind.
- On failure the workflow SHALL stop, name every offending file in one run, and not offer to continue or delete the file.
- The scan SHALL report how many files it checked, and SHALL return a separate "could not run" status when the listing is empty or fails.
- The scan SHALL live with the repo-local release skill, outside the plugin.

#### Scenario: An undeclared file shape blocks the release

- **WHEN** a tracked file under the plugin matches no allowlist entry
- **THEN** the workflow stops and names the file by repo-relative path
- **AND** no version bump is written and no tag is cut

#### Scenario: Every offending file is named in one run

- **WHEN** several tracked files match no entry
- **THEN** all of them are reported in one run

#### Scenario: The scan refuses to certify an empty enumeration

- **WHEN** the file listing is empty or the listing command fails
- **THEN** the scan reports "could not run", distinct from clean and from violations, and does not report zero violations

#### Scenario: A clean scan states what it examined

- **WHEN** every file matches an entry
- **THEN** the scan reports how many files and patterns it checked
- **AND** the workflow moves on to its other preconditions

#### Scenario: The allowlist is enumerated with a reason per entry

- **WHEN** the allowlist is inspected
- **THEN** each entry records why its shape is a consumer-usable asset
- **AND** a separate check caps the entry count, so an entry is added only by raising the cap in the same change

#### Scenario: The scan enumerates tracked files, not the working directory

- **WHEN** the plugin directory holds untracked cache or build files
- **THEN** the scan does not report them
- **AND** a tracked file of an unlisted shape is still reported

#### Scenario: The scan lives outside the published tree

- **WHEN** the plugin directory is listed
- **THEN** the scan is not in it, and it lives in the repo-local release skill's directory

#### Scenario: A dev-asset shape inside an allowed directory is still rejected

- **WHEN** a test file, pytest config, or mutation batch is placed inside an otherwise-shipped directory
- **THEN** the scan rejects and names it, because no broad directory or extension wildcard admits it

### Requirement: cla-init seeds OpenSpec authoring rules without clobbering

When `openspec/` exists and has neither `config.yaml` nor `config.yml`, cla-init SHALL create `openspec/config.yaml` with `schema: spec-driven` and a `rules:` block stating the stock limits and the scenario-proof rule. This is the one project-data path cla-init writes outside `cla.io/`. Otherwise it SHALL print the block and write nothing.

#### Scenario: No config.yaml

- **WHEN** cla-init runs in a repo with `openspec/` and neither `openspec/config.yaml` nor `openspec/config.yml`
- **THEN** it creates the file with the rules block and reports `created`

#### Scenario: An existing config.yaml or config.yml

- **WHEN** cla-init runs in a repo whose `openspec/config.yaml` or `openspec/config.yml` exists
- **THEN** no new config file is created, the existing one is byte-identical afterwards, and the rules block is printed
