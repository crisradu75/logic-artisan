## 1. Specs

- [x] 1.1 Remove every live requirement and add the restated set under seven capabilities (`retire_capabilities: true` retires `change-authoring`, `change-review`, `orchestration` and `plugin-architecture`)
- [x] 1.2 After archive, give each new spec a one-sentence Purpose and run `openspec validate --specs --strict` with no warning

## 2. Proof per requirement

Each test below carries a `requirement: <spec> / <heading>` comment line above it.

- [x] 2.1 plugin-distribution: `test_marketplace_manifest.py` (Installing a pinned release), `test_log_run.py` (Repo data stays in the repo), `test_check_shipped_tree.py` (What a release contains; Publishing a release), `test_release_preconditions.py` (Publishing a release)
- [x] 2.2 guard-hooks: `test_hooks_wiring.py`, `test_block_unsafe_recursive_delete.py`, `test_block_worktree_path_escape.py`, `test_block_cd_in_bash.py`, `test_ask_destructive_git.py`, `test_warn_wholesale_rewrite.py`, `test_pre_push.py`
- [x] 2.3 repo-context: `test_cla_init_rules_match_config.py` (re-pointed from plugin-architecture), `test__git_common.py` (Per-skill overlays), `test_project_facts_paths.py`, `test_no_project_tokens.py`
- [x] 2.4 change-workflow: `test_probe_state.py` (re-pointed from orchestration), `test_scenario_proof_format.py` (re-pointed from change-authoring and change-review), `test_cla_init_rules_match_config.py` (Specs follow the repo's authoring rules)
- [x] 2.5 change-chains: `test_multi_lite_policy_names_agree.py`, `test_chain_obligation_carry.py`, `test_orchestrators_state_turn_liveness.py`
- [x] 2.6 run-ledgers: `test_log_run.py`, `test_spec_to_pr_aggregate.py`, `test_codify_aggregate.py`
- [x] 2.7 annotate: `test_render_doc.py`, `test_render_change.py`, `test_render_html.py` (re-pointed), `test_annotate_server.py`, `test_annotations_store.py`

manual: Skills are invoked under the cla namespace: the namespace and the by-name-only start are applied by Claude Code's plugin loader from each skill's frontmatter; checked by invoking a skill in a session.
manual: Setting up a repo's cla.io directory: the scaffold is run by the model from the skill text; checked by running `/cla:cla-init` in a scratch repo.
manual: Shared repo facts: sync-context is a read-and-reason pass over the repo's manifests with no script to test.
manual: Internal terminology: entries are written by whichever skill settles the name; no script writes them.
manual: A change becomes an opened pull request: an end-to-end run needs a real repo, `gh` and a model; checked by running `/cla:spec-to-pr` on a change.
manual: Round caps and a dry run: the flags are read by the model from the skill text; checked in a run with each flag.
manual: The run's report: the report is written by the model at the end of a run; checked by reading one.
manual: A small change without OpenSpec: an end-to-end run; checked by running `/cla:lite-pr`.
manual: Reviewing a change before implementation: the review is a model pass; checked by running `/cla:review-change` on a change.
manual: Proposing a batch of changes: an end-to-end run; checked by running `/cla:multi-spec` on a decisions file.
manual: Running a batch of OpenSpec changes: an end-to-end chain run; checked by running `/cla:multi-pr`.
manual: A failure stops only what depends on it: chain behaviour on a failed change needs a real chain run; checked from a chain's report.
manual: The spec-to-pr run record: the record is assembled by the model at the end of a run; the reader's tests use hand-written records.

## 3. Follow-through

- [x] 3.1 `test_scenario_proof_format.py`: scan the live specs for the retired per-scenario marker too, and update its mutation batch
- [x] 3.2 Point the test docstrings and shipped references that cited a retired requirement at what now holds the rule
- [x] 3.3 `findings_by_round` no longer has a live requirement naming it as reversal evidence, so its exception in `run-log-schema.md` lapses by that file's own exit rule; the next change to the Revise record (decision D7/D8a of `retro-and-learning-loop-simplification-2026-10-08.md`) adds it to the aggregator or drops it

## 4. Removed requirements

Every live requirement before this change, with its scenario count. "Restated" names the new requirement that now holds its outcome or interface; "dropped" means it described skill internals, so its scenarios are dropped with it.

**annotate**

- A document is shown as its author designed it (3) — restated in annotate / The document is shown as written and never changed
- The skill adds markup to a copy and changes nothing else (3) — restated in annotate / The document is shown as written and never changed
- A document already using the skill's attributes is refused (1) — restated in annotate / A document using the page's own attributes is refused
- Annotatable blocks are chosen by structure, not by a fixed tag list (4) — dropped
- A block's recorded text matches what the browser reports (1) — restated in annotate / Existing comments are reported when the page is rebuilt
- A block records the source line it came from, in every supported format (1) — restated in annotate / Comments are saved with their source line
- The annotation interface is isolated from the document's styles and scripts (2) — restated in annotate / The document is shown as written and never changed
- A change to a rendering path shared by several formats proves the existing format is unchanged (1) — dropped

**change-authoring**

- design.md is optional and written only for a named reason (2) — restated in the `rules.design` block of `openspec/config.yaml`
- A pinned-parameters block only for a number that changes behaviour (1) — dropped
- The authoring brief points to the stock limits and asks for no doc-sync task (2) — restated in change-workflow / Specs follow the repo's authoring rules
- Every new or modified scenario names its proof (2) — restated in change-workflow / Each requirement names its proof
- A change with no behaviour change carries no spec delta (1) — restated in change-workflow / Specs follow the repo's authoring rules
- Live specs are read overview-first (1) — restated in change-workflow / Specs follow the repo's authoring rules
- Change artifacts are short and plain (1) — restated in change-workflow / Specs follow the repo's authoring rules

**change-review**

- Review reads an absent design.md as absent (1) — dropped
- An oversized or restating artifact is an Important finding (2) — restated in change-workflow / Specs follow the repo's authoring rules
- Cutting is a FIX FIRST remedy and is preferred (1) — dropped
- Design headings do not buy the large-change review (1) — dropped
- A scenario with no proof is an Important finding (1) — restated in change-workflow / Each requirement names its proof
- A test task naming no marker is a Suggestion (1) — restated in change-workflow / Each requirement names its proof
- multi-spec's batch review is size-gated per change (1) — dropped
- The review report carries no parallelism plan and no claim quota (1) — dropped
- An invented requirement is an Important finding (1) — restated in change-workflow / Specs follow the repo's authoring rules
- Hidden claims are verified (1) — restated in change-workflow / Reviewing a change before implementation
- A MODIFIED block keeps its live scenarios (1) — restated in change-workflow / Specs follow the repo's authoring rules
- The same finding at two severities keeps the higher (1) — dropped

**orchestration**

- A review fix is proven by breaking it and watching a test fail (3) — dropped
- A batch orders changes by shared state and stale specs, not only by code dependencies (5) — restated in change-chains / Shared environment state merges first
- A small-change chain merges only what it tested and reviewed, under a policy confirmed per run (6) — restated in change-chains / What a small-change chain merges
- An obligation one change creates for a later change is delivered to it (8) — restated in change-chains / Obligations reach the change that owes them
- An unattended run does not end a turn while work is pending (4) — restated in change-chains / An unattended chain keeps running
- A task list is not reported complete on tick marks alone (2) — dropped
- A measurement names the command that produced it (5) — dropped
- Deferred findings are separated by reason (1) — dropped
- The test-quality rules are read where tests are written (5) — dropped
- A fix brief makes the defect binding and the proposed fix rejectable (7) — dropped
- The fix loop handles a rejected fix (5) — dropped
- A brief's factual claims are checkable and carry their source (5) — dropped
- A fix the orchestrator chose itself is checked against rejected alternatives (5) — dropped
- A dispatched agent waits for its checks to finish (3) — dropped
- A return without a status is treated as blocked (4) — dropped
- Only one party writes to a shared checkout at a time (4) — dropped
- A dispatched agent stops rather than inventing evidence (3) — dropped
- A second Revise round asks a different question (4) — dropped
- A later Revise round's search for other instances is possible and checked (4) — dropped
- The Revise round cap is a ceiling, not the loop's exit condition (3) — dropped
- multi-pr records Suggestions by default (2) — restated in change-chains / Running a batch of OpenSpec changes
- A change without design.md resumes at the right phase (3) — restated in change-workflow / Resuming a partly done change
- The live specification set is validated where it is written (4) — dropped

**plugin-architecture**

- Where plugin assets, repo data, and tests live (2) — restated in plugin-distribution / What a release contains and plugin-distribution / Repo data stays in the repo
- In-place activation and namespacing (4) — restated in plugin-distribution / Installing a pinned release and plugin-distribution / Skills are invoked under the cla namespace
- Scripts find the repo from git, not from their own location (4) — restated in run-ledgers / Ledger files
- Per-skill project-context overlay (5) — restated in repo-context / Per-skill overlays
- Guard hooks provided by the plugin (4) — restated in guard-hooks / Guard hooks load with the plugin
- Skill fact/procedure separation (4) — restated in repo-context / Checking the plugin text for repo names
- Project-data scaffolding via `cla-init` (5) — restated in repo-context / Setting up a repo's cla.io directory
- Conformance guard for the overlay separation (12) — restated in repo-context / Checking the plugin text for repo names
- Consolidated project-facts file (3) — restated in repo-context / Shared repo facts
- Consolidated domain-terminology file (5) — restated in repo-context / Internal terminology
- Context-refresh skill (5) — restated in repo-context / Shared repo facts
- Project-facts staleness guard (5) — restated in repo-context / Checking recorded paths
- Skill token-efficiency disciplines (4) — dropped
- Shipped-asset boundary (8) — restated in plugin-distribution / What a release contains
- Release-time shipped-asset scan (8) — restated in plugin-distribution / Publishing a release
- cla-init seeds OpenSpec authoring rules without clobbering (3) — restated in repo-context / cla-init seeds OpenSpec authoring rules without clobbering

**run-ledgers**

- A malformed record costs one record, and the loss is counted (3) — restated in run-ledgers / Retro reports
- An aggregator reads several ledgers in one run (2) — restated in run-ledgers / Retro reports
- A declined default names the ledger evidence that would reverse it (1) — dropped
- The Revise record counts findings per round (4) — restated in run-ledgers / The spec-to-pr run record
- A ledger field kept for a deferred decision states when it qualifies and when it lapses (3) — dropped
