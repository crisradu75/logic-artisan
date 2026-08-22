## ADDED Requirements

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

## MODIFIED Requirements

### Requirement: Conformance guard for the overlay separation

The `cla` plugin SHALL include a conformance checker that mechanically enforces the fact/procedure separation (the Skill fact/procedure separation and Project-specific overlay convention requirements). The checker SHALL be a generic, repo-agnostic program that fails when any **non-overlay synced core file** contains a project-specific token, where the token list is itself a per-repo project overlay. The checker SHALL obey the same fact/procedure split it enforces: the checker is generic *procedure*; the token list is a repo-specific *fact* held in an overlay.

**Home and portability.** The checker SHALL live at `.claude/plugins/cla/skills/_shared/scripts/check_no_project_tokens.py` — in the shared area that belongs to no single skill, because it enforces a rule about the whole plugin — and SHALL be invocable directly as `python3 <path-to-checker>`, requiring no pytest and no test scope in the repo that runs it. It reads the **consuming repo's** data (the token-list overlay in that repo's `cla.io/` tree), which is why it is a skill helper rather than a test: a consuming repo has no test gate over the plugin cache, so a checker filed as a pytest module is unreachable there in practice. Because the marketplace install distributes the entire `.claude/plugins/cla/` directory as one versioned snapshot, the checker reaches every destination repo by construction, with no per-file enumeration required. **Known coverage gap:** that same whole-directory distribution means files outside the checker's scan roots — `lib/`, the `*-checks/` scopes, `run_tests.py`, `mutate.py` — ship to consumers unscanned; widening the scan roots is deliberately NOT attempted here, because those scopes legitimately contain project tokens as test fixtures and would need a fixture-aware exemption first. The gap SHALL be recorded as a tracked follow-up rather than silently carried. The checker SHALL NOT be implemented as a Claude Code hook and SHALL NOT block or interrupt authoring; it runs on demand — notably at skill-authoring time, per the authoring validation checklist. The checker SHALL resolve the plugin tree relative to its own file location (a fixed internal layout identical in every repo), not via any repo-specific absolute path or repository name; any positional fallback depth it uses SHALL correspond to its actual location in the tree.

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

### Requirement: Repo-state resolution seam

Plugin scripts SHALL resolve repo locations independently of their own position in the tree, because the plugin's nested position under `.claude/plugins/cla/…` breaks any position-dependent resolver. Specifically: (a) scripts that read/write the retro dir (the shared writer `lib/log_run.py` and each retro loop's aggregator — `codify-retro/scripts/codify_aggregate.py` and `spec-to-pr-retro/scripts/spec_to_pr_aggregate.py`) SHALL resolve it as `CLAUDE_RETRO_DIR` when set, otherwise `<git rev-parse --show-toplevel>/cla.io/retro`; (b) scripts that resolve a repo root for other repo files (`probe_state.py` via `_git_common.py`) SHALL resolve it via `git rev-parse --show-toplevel`, NOT a fixed `Path(__file__).resolve().parents[N]` depth. Scripts MUST NOT rely on walking to a `.claude` ancestor of the script nor on `${CLAUDE_PROJECT_DIR}` (empty in the script environment). A skill-bundled file (one that ships WITH the plugin, e.g. `references/required-permissions.json`) SHALL be resolved skill-relative to the script, while a project-level target — including every overlay under `cla.io/overlays/` — SHALL be resolved from the repo root.

Each retro loop's aggregator SHALL carry a module name distinct from every other aggregator in the plugin, so that no two of them collide when imported in one process.

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
- **THEN** `codify-retro` and `spec-to-pr-retro` each name their aggregator distinctly
- **AND** every skill instruction, test, and cross-file path list that names an aggregator names the distinct one
