## ADDED Requirements

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

## MODIFIED Requirements

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
