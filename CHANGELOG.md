# Changelog

Notable changes to the CLA plugin, by release tag. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[semantic versioning](https://semver.org/) as `CLAUDE.md` defines it for this plugin. Entries link
the pull request that made them. Releases before 2.0.0 are in the git tags;
[docs/history.md](docs/history.md) tells the background.

## [Unreleased]

**Upgrading.** After you update the plugin, re-run `/cla:cla-setup` in each repo that uses it and
accept the update it lists. For a repo with `openspec/`, the run asks you for the new `## Stakes`
section of `cla.io/project-facts.md` (three short questions: who uses the repo, what a bug costs,
and the protected areas) and for the change budget (`lean` or `protected`) its answers point to.
It then lists the changes to `openspec/config.yaml`: the new whole-change budget rule and the new
protected-areas rule, in place of the old per-spec requirement cap and the old five-area wording.
Nothing in that file changes until you say yes to the listed diff. A repo that does not re-run
`/cla:cla-setup` keeps its old seeded rules and its old per-spec cap, and has no Stakes section, so
the skills fall back to the default list of protected areas.

### Added

- **A `setup_guard.py` script** checks that `/cla:cla-setup` left alone the files it promises to:
  `snapshot` records them before the run writes anything, and `verify` at the end reports each
  instruction file, settings file, rules file of the repo's own, existing `notes.md`, `*.local.md`
  file, terminology file or overlay changed, created or deleted without the owner's yes, and every
  overlay or terminology file created. On a problem the skill reports every line the check printed
  and does not call the run clean. Exit 0 passes, 1 is a problem, 2 means it could not check (an
  unreadable file, or a missing, corrupt or stale snapshot) and is never a pass (#534).
- **A `chain_check.py` script** replaces the comparisons `multi-pr` and `multi-lite` made by eye before
  they merge or resume a pull request: `before-merge` (the recorded head against the PR, the remote
  branch and the checkout; a clean tree; the PR open, on the recorded branch, not a fork, against the
  base), `after-merge` (merged into the base at the recorded head, not queued), `fix-pushed` (the chain's own fix committed and pushed),
  `resume` (still on the recorded head) and `deps` (every dependency merged into the base). It reads
  the PR number, branch and head from the run-notes row and prints the reason the chain records. Exit
  0 passes, 1 is a problem, 2 means it could not check and is never a pass (#531).
- **A `ship_check.py` script** replaces the git command lists that Ship, Revise, Archive, `lite-pr`,
  `multi-spec` and `multi-lite` compared by eye: `preflight` before a branch is made (no local,
  remote-tracking or remote branch of that name, no commits to lose on a rename, never a rename of the
  default branch, a stacked parent on the remote), `pushed` after a push (the branch, `HEAD` against the remote, the configured upstream; `push
  not verified` otherwise) and `trailers` before a push (`Measured-by:` lines against git's parsed
  trailers). Exit 0 passes, 1 is a problem, 2 means it could not check and is never a pass (#530).
- **An `ask-plugin-cache-edit` guard hook:** an Edit or Write inside an installed plugin copy (the
  `cache/` or `marketplaces/` part of `~/.claude/plugins`, wherever `CLAUDE_CONFIG_DIR` or
  `CLAUDE_CODE_PLUGIN_CACHE_DIR` puts it, resolved through symlinks and `..`) asks first: the edit
  would be lost on the next update, and a repo's rules go in `cla.io/overlays/<skill>.md` or
  `cla.io/project-facts.md`. A plugin run with `--plugin-dir` and the plugin's `data/` directory
  are not checked. Bad input fails open; if the hook itself fails to load, every Edit and Write
  asks. The Edit/Write dispatcher now passes a hook's ask through (#529).
- **An `ask-broad-git-add` guard hook:** a `git add` of the current directory, the repo root or a bare
  `openspec/` (`-A`, `--all`, `.`, `:/`, `*`) asks first when it would stage untracked files, and
  names up to ten of them. It stays silent for `-u`, named paths and tracked-only changes, and
  whenever it cannot check. It enforces the skills' "stage named paths only" rule (#527).
- **Stakes and a whole-change size budget:** `/cla:cla-setup` asks the owner for a short `## Stakes`
  section in `cla.io/project-facts.md` (who uses the repo, what a bug costs, protected areas) and
  offers a `lean` (12 requirements, 3,000 words) or `protected` (25 requirements, 6,000 words) budget
  per change, written as `- Change budget: lean|protected`. `check_spec_proof.py` reports an active
  change over the budget in `openspec/config.yaml`, counting every `.md` file in the change folder
  and its `### Requirement:` headings. A change may carry one line, `Budget: protected`, in its
  `proposal.md` to be held to the protected budget instead (a second seeded sentence, which the
  checker reads); any other `Budget:` value, or that line with no such sentence, is a problem. A
  budget number in wording the checker can't read exits 2. The numbers are placeholders until tuned
  against the mnemo benchmark (#509).
- **A `Full gate: final-commit-only` repo fact** in `cla.io/project-facts.md`, for a repo whose full
  gate is slow. `/cla:spec-to-pr` Test then runs smoke and touched tests only, and the one full gate
  runs after Archive. `/cla:cla-setup` never proposes it by default (#478).
- **`blocking-findings.md`**, one shared statement of which review findings block a merge (see
  Changed), and one default list of protected areas that a repo's Stakes section replaces (#511,
  #512).
- **A Copilot CLI output style** (`output-styles/COPILOT.md`) and a "Copilot CLI support:
  unsupported" note on the skills that need Claude Code skill chaining and agent delegation, with
  Copilot install, update and troubleshooting steps in the plugin README (#489, #500).

### Changed

- **Review skills fix only blocking findings.** A finding blocks the merge and is fixed when it
  touches a protected area or is a real correctness bug in what the change ships. Every other
  finding goes to `TODO.md` as one line. Security, safe writes to a user's files and honesty claims
  are always protected. A second review round runs only after a protected-area fix or a guard-hook fix. `spec-to-pr`,
  `lite-pr`, `review-change`, `multi-lite`, `multi-pr` and `multi-spec` follow the one rule. The
  round-trigger values in the run log are now `protected`, `reentry` and `unknown`; earlier records
  keep their old values (#511).
- **Protected areas come from each repo's Stakes section,** with one default list when a repo has
  none: money, personal data, accessibility, the user's own files and anything shipped to other
  repos. The seeded `openspec/config.yaml` rule, review dispatch, model routing and the multi-spec
  brief all read that one definition (#512).
- **`lite-pr` is the default path; `spec-to-pr` is for a change that touches a protected area or
  behaviour shipped to other repos.** `multi-spec` sorts each change from a decisions file into
  `spec` or `lite` by path before authoring and writes proposals for the `spec` changes only;
  `multi-lite` takes the lite ones. A path the user states always wins (#515).
- **The seeded spec rules drop the per-spec requirement cap** ("a spec holds at most 8 requirements;
  add a new capability rather than a ninth") and the rule to split into a new capability instead of
  squeezing a clause. Splitting a capability escaped the cap and grew one repo to 41 capabilities. A
  repo whose config still carries the old sentences keeps the old cap until `/cla:cla-setup` is re-run
  and the owner agrees to its listed update (#509).
- **multi-spec's authoring brief is replaced by a tested one** ("think broadly, write narrowly"):
  the author reads the repo's Stakes, turns each protected-area risk into a requirement, notes the
  rest in one line, keeps decided rules as decided and raises a conflict as an open question. It
  drops the pinned-numbers block, "cross-cutting rules go first" and the `blocked` return for a
  vague owner rule. On the mnemo benchmark it covers 7 of 8 critical outcomes; outcome g is a known
  gap (`plugin-tests/benchmarks/mnemo/baseline/brief-v3`) (#510).
- **The output style drops its numeric sentence and paragraph ceilings** (20 and 25 words, six
  sentences): one instruction per sentence, and split a sentence that holds two ideas. The ban on
  "play-by-play narration" becomes a ban on narrating routine steps: say in a line what you are
  about to do, speak during a long task when a finding changes the plan or the answer, and do not
  narrate each tool call (#517).
- **Absolute rules that guard no protected area are softened into guidance.** Every "never",
  "always" and "must" in the shipped skills, references, agents and output styles has a line in the
  repo's rule ledger (it does not ship); rules that guard no protected area now say why and allow a
  judgment call, and those that guard one stay absolute. Five rules that only repeated another were
  removed (#519, #522). A first review of the rules with no known origin removed 7 more and softened 8 (#533).
- **Shipped prose is corrected and reworded to read literally.** Wrong and stale statements are
  fixed across `_shared`, `annotate`, `feedback`, `new-worktree`, `project-review`,
  `report-upstream`, `right-model` and others, and the rest of the prompt audit reworded the
  remaining references (#513, #516, #517).
- **Skill text moves out of `SKILL.md`.** `cla-setup`'s step detail now lives in `references/`
  (facts file, OpenSpec rules, ledgers, overlay reconcile, spec-map scaffold, economy-rules block).
  `precheck.md`, `ship.md`, `subagent-brief.md` and `review-sweeps.md` moved from `spec-to-pr` to
  `_shared/references`, and `multi-lite` and `multi-pr` descriptions are trimmed. Behaviour is
  unchanged (#491, #492, #493, #498, #501).
- **`spec-to-pr` Ship and Revise push in the background and verify the remote head,** and Revise
  round 1 dispatches Agents by default (#479, #485).
- **Read-only agents may run beside the base-branch verification** (no writes to the checkout;
  their own scratch folder is allowed), and a subagent brief tells agents to send one final report
  and set no timers (#481, #497).
- **A dead helper is removed.** The unused `default_base_branch` function leaves `_dispatch_lib.py`;
  `probe_state.py`'s resolver is the one base-branch resolver in the plugin (#499).

### Fixed

- **Guards see executed command substitutions in quoted spans.** `echo "$(git reset --hard)"` and a
  backtick form now reach `ask-destructive-git` and `block-worktree-path-escape`, and the dispatch
  library scans the inside of `$(...)` and backticks (#495).
- **Guard scans are linear on hostile input.** The heredoc scans in `block-unsafe-recursive-delete`
  and `warn-heredoc-escape-mangling` (#502), the tokenizers in `block-cd-in-bash` and
  `block-unsafe-recursive-delete` (#503), and `warn-comment-dates` (#505) no longer grow
  quadratically with input length. `block-unsafe-recursive-delete` no longer tokenizes a very large
  segment: one that may be a recursive delete is blocked rather than allowed (#503).
- **The git guards read global options in linear time.** `ask-destructive-git` and
  `warn-stray-scratch-artifact` matched `git <global options> <subcommand>` with one regex, which
  grew quadratically on a 28 KB `git -c git -c git ... status` (25 s) and exponentially on
  `git -c -c -c ... x` or a run of `--git-dir=x`, past the hook timeout, which lets the command
  through. The shared `GitInvocation` matcher finds the same matches in linear time (#528).
- **The Bash dispatcher asks, unscanned, for a command over 500,000 characters.** A hook killed at
  the timeout lets the command through, so past the cap the dispatcher answers with one `ask`
  naming the size and the cap, before the first guard runs. The Copilot adapter keeps that as an
  ask (#504).
- **The pre-push guard checks a push to a URL** against the default branch of the remote whose
  fetch or push URL matches it, not only a named remote (#482).
- **`check_spec_proof.py`** tracks code fences by marker and drops a closing `#` run from
  requirement and scenario names, including a name that is only a `#` run (#486, #497).
- **Worktree teardown checks for files it cannot recover.** `multi-pr`'s cleanup lists a
  worktree's untracked and gitignored files first and removes it only when the list is empty or the
  user accepts it; `new-worktree`'s manual teardown skips a worktree that holds such files (#485).
- **`/cla:cla-setup` reads the change budget sentence as the checker does.** A config that
  capitalises "At most N requirements" is no longer listed as missing the budget, and a
  commented-out budget line no longer counts as carrying it (#PR).
- **`check_spec_proof.py` budget counts.** A `Budget: protected` line inside a code fence in
  `proposal.md` no longer selects the protected budget, and a byte-order mark no longer adds a word
  or hides a requirement heading on line 1. It still checks every active change whatever `--base`
  or `--tests` says, and now says why (#PR).
- **Proposal size in review and authoring.** The review checklist's ~400-word proposal Suggestion
  leaves out the `## Open questions` and `## Risks noted` sections the `multi-spec` authoring brief
  asks for, and the brief keeps `## Risks noted` to about 5 lines; the seeded rule is unchanged (#PR).
- **The design snapshot is never read with `git show HEAD:<path>`** in the shared review sweeps,
  which had softened it to "avoid"; all three snapshot sites now agree (#PR).
- **`multi-spec` finds an existing `docs/propose-<slug>` branch by its exact name**, through
  `ship_check.py preflight`; `git ls-remote --heads` also matched a longer name ending in it (#PR).
- **`chain_check.py` finds a submodule's run notes** from a relative `--notes`; a bare-repository
  layout still exits 2 and now says to pass an absolute path. The chain merge steps name the fork
  workflow as a known limitation: every merge there stops as `not opened by this chain` (#PR).

### Development

Not shipped to a repo that installs the plugin: test and fixture work (#487 Copilot-guard allow and
deny tests, #496 `warn-comment-dates` branch tests, #508 mnemo spec-writing benchmark and the CLA
foundation decisions, #518 faster suite with cached git fixture repos and the gate at `-n 4`);
specs and docs (#480 and #490 guard decisions and new specs for AGENTS.md, cla-setup, copilot-cli,
git-guards and guard-warnings, #494 drift fixes and the 2.2.3 and 2.3.0 changelog entries, #514 the
foundation checklist, #521 the mnemo benchmark run of the finished plugin, #488 requirement shape in the `plugin-distribution` and `review-agents`
specs); the repo's own OpenSpec skills regenerated for OpenSpec 2.0, with the old
`/opsx:*` command files removed (#506); and the `/release` skill, which now asks one question, with
a "Don't release" option, before any edit (#517), and runs the test gate at `-n 4` (#518). The
rule ledger re-tags its catch-all `shipped to other repos` entries to their real areas, and its
test catches `mustn't`, scans shipped JSON comments and fails on a not-a-rule fragment that spans a
rule (#PR).

## [2.3.0] — 2026-11-04

### Added

- **Copilot CLI guard hooks:** separate Agent Plugins 1.0 `PreToolUse`/`PostToolUse` wiring
  (`com.github.copilot/hooks/hooks.json`, `copilot-pretooluse.py`, `copilot-posttooluse.py`, and a
  PowerShell Python probe) runs the CLA guards under Copilot CLI. Claude's hook configuration is
  unchanged (#474).

### Changed

- The docs record the live validation of the Copilot CLI install and helper agents, and name what
  was not live-tested (#473, #476).

## [2.2.3] — 2026-11-02

### Changed

- Merge prompts name the target; lite-pr's review tier is renamed; the review brief states its
  constraints (#452).
- The final test run is sized to the change, and the `[y/n]` line names the item (#448, #449, #450).
- Shipped prose is written in neutral terms, not one repo's domain and layout (#432, #460), with
  five prose cleanups in lite-pr, spec-to-pr and review-change references (#433, #461).

### Fixed

- `ask-destructive-git`'s stash check has its own handler and a reason that covers several
  directories (#453).
- `check_spec_proof.py` pairs a code span over a lazy continuation line (#455), reports a
  three-part marker that two readings both prove (#456), and exits 2 on a closed stdout under
  Python 3.14 (#451).

## [2.2.2] — 2026-10-30

### Fixed

- `ask-destructive-git`: an inline `ALLOW_PR_MERGE=1` authorizes only the `gh pr merge` it
  heads. A prefix in any other segment of the command used to silence the merge prompt.
- `ask-destructive-git` asks before a push that skips the `pre-push` guard: `--no-verify`,
  `core.hooksPath` set by `-c`, `git config` or `GIT_CONFIG_*`, or an inline `ALLOW_PUSH_TO_MAIN=1`
  (quoted or not).
- The `pre-push` guard also refuses the remote's own default branch, not only `main` and
  `master`.
- Both dispatchers ask instead of failing open when `_dispatch_lib` fails to load or the
  dispatcher crashes; the old exit 1 let every guarded call through.
- `block-cd-in-bash` catches `{ cd x; }`, `builtin cd`, `command cd`, `time cd`, `! cd`, a
  backslash-escaped `cd`, and `cd` after `if`, `then`, `elif`, `else`, `while`, `until` or `do`
  at a command position.
- A dispatcher keeps a guard's block when formatting its message fails, and logs the full
  traceback when it fails closed.
- Two block messages no longer cite a session memory an installing repo does not have.

### Changed

- The plugin is MIT licensed; both manifests say `"license": "MIT"` instead of `"UNLICENSED"`.
- The Claude Code manifest's description no longer calls CLA proprietary or says it loads only
  through `--plugin-dir`.

## [2.2.1] — 2026-10-26

### Changed

- Reviews use the `pr-review-toolkit` agents (`code-reviewer`, `silent-failure-hunter`,
  `comment-analyzer`); CLA's three cloned reviewer agents are removed. The dispatching skill saves
  the diff to a file and forbids git commands and edits in the brief (#426).
- `cla-setup` asks the test-proof question, reports what each seed step did, writes a clean
  spec-map scaffold, and seeds the tasks rule that matches the chosen granularity (#425).
- `codify-learnings` asks one question per turn and compares scores only on matched inputs (#423).

### Fixed

- `check_spec_proof.py` accepts the three-part scenario marker
  `scenario: <spec> / <requirement> / <scenario>` (#427).
- `check_fact_paths.py` hints at where a stale relative example path really lives (#428).
- `probe_state.py` finds a tool through `shutil.which`, so a Windows `.cmd` shim such as
  `openspec` is no longer reported missing (#424).

## [2.2.0] — 2026-10-25

### Added

- Skills read and write both `CLAUDE.md` and `AGENTS.md` in an installing repo (#419).

### Changed

- `shape-decision` stops once the decision is clear, backs each axis with evidence, and moves its
  question forms to a reference file (#417).
- The reviewer agents say which line number the `line` field means (#420).
- OpenSpec skills and commands refreshed for OpenSpec 1.15.0 (#418).
- Docs: the catalog pin, the lite-pr steps and the shared references are current (#421).

## [2.1.2] — 2026-10-24

### Changed

- Prose cleanups across the shipped skills, from the review of the spec-organization research
  (#409, refs #408).

## [2.1.1] — 2026-10-17

### Added

- **GitHub Copilot CLI, experimental and untested in a live Copilot CLI:** a Copilot catalog and an
  Agent Plugins 1.0 manifest (#390), the helper agents as Copilot profiles (#396), and install docs
  that say what is untested (#400). Tracked in #302.
- `check_spec_proof.py`: ties each requirement a branch adds or changes to a test, and checks the
  spec size limits (#365). It also notes a spec Purpose without a `**Serves:**` line (#384).
- A spec map that links capabilities and workflows to the specs, checked by `check_spec_proof.py`
  (#395).
- Every OpenSpec change carries a task to update the repo's docs (#389, #397, #399).
- `ask-destructive-git` asks before a saving `git stash` during a merge, cherry-pick or revert
  (#404).
- `multi-pr` re-checks a later change's `path:line` cites after earlier merges
  (`check_cite_drift.py`, #361).
- spec-to-pr and lite-pr re-review the fix of a high-risk Important finding (#356).
- A change that finds the spec and the code disagree fixes both in the same change (#363).

### Changed

- Mutation testing is opt-in: run when the owner asks or a guard hook is rewritten (#366).
- The `cla` launchers default to Sonnet (#402).
- `cla-setup`'s seed block ships as a Python script, because a Bash command that long is cut off on
  Windows (#388, fixes #385).
- The retro splits Revise's round-2 yield by what started the round (#362).

### Fixed

- The Implement brief's scope is checked against every path `tasks.md` names (#360).
- Robustness gaps in `meter.py`, `check_fact_paths.py` and `probe_state.py` (#359).
- Weak guard tests tightened and two mutation batches repaired (#358).
- `check_spec_proof.py` reports requirements with no scenario and unclosed code fences (#367).
- multi-spec grades a batch's total claims; diagnose handles a retry that fails on a new cause
  (#355).
- shape-decision checks outside services and earlier research (#354).

## [2.1.0] — 2026-10-13

### Added

- **Risk-sized review:** the PR's `Risk:` line picks the reviewers and their models (#324).
- `cla-setup` writes `.claude/rules/cla-economy.md`, so an agent outside any skill still reads the
  cost rules (#326).
- Artifact caps and behaviour-stated tasks in the seeded OpenSpec rules; review-change flags a task
  that names a line and an artifact over its cap (#328).
- `meter.py`, a dev-only meter of the tokens a session transcript records (#327).
- codify-learnings moves its oldest lessons to an archive file that its search still reads (#332).
- annotate opens an OpenSpec change on an overview, shows each MODIFIED requirement's diff against
  the main spec, sets REMOVED requirements apart, and has browser tests for the page (#320).
- Read-only copies of the reviewer agents (#344), later removed in 2.2.1.

### Changed

- lite-pr loads its rare rules (measured-by, mutation gate, diagnose escalation) only when they
  apply (#329).
- lite-pr's Test phase gets one retry, then hands off to `diagnose` (#330).
- spec-to-pr checks remote CI with commands first and checks the archive after it runs (#331); the
  wait is one background watch under a 15-minute watchdog (#343).
- A Review verdict is seconded on RETHINK or a Critical finding, not on a self-judged borderline
  case (#341).

### Fixed

- `check_fact_paths.py` skips machine-local files and reports a path under a renamed or removed
  top-level directory (#333, #342).
- `cla-setup` recognises quoted retired rules; the overlay test is safe in a worktree (#340).
- Review-sizing follow-ups (#334).

## [2.0.0] — 2026-10-09

A simplification release: fewer skills, ledgers and checks, and every one that stayed has a reader.
Unless noted, every change below came in #315.

### Breaking

- `cla-setup` replaces `cla-init` and `sync-context`. Overlays become optional and nothing seeds
  one. Run `/cla:cla-setup` once after upgrading.
- `codify-retro` is deleted; `codify-learnings` escalates a rule that failed again instead.
- project-review's mechanical checks and the Node test suite are deleted.
- `multi-pr` merges through one shared chain-merge reference with head-commit guards, and drops its
  two alternative merge policies.
- Ledgers and fields with no reader are retired; chain run notes stay local and untracked.

### Changed

- The live specs are split into six capabilities and rewritten at outcome level, with authoring
  rules that keep new specs short and plain (#308–#314, from issue #293).
- Run records are validated when written, with a script to migrate old-shape records.
- Revise's second round runs after every fix commit, with a narrower comment-analyzer.
- spec-to-pr-retro is slimmed, and Handoff prints a one-line nudge when recent runs keep hitting a
  cap.
- The always-loaded context shrinks: shorter descriptions, output style and `CLAUDE.md`, measured
  with the new `measure_load.py` (#301, #303–#307).
- `CLAUDE.md` holds rules only; reference and history move to the developer guide.
- OpenSpec upgraded to 1.14.0, then 1.14.1 (#285, #292).

[Unreleased]: https://github.com/crisradu75/logic-artisan/compare/cla--v2.2.2...HEAD
[2.2.2]: https://github.com/crisradu75/logic-artisan/compare/cla--v2.2.1...cla--v2.2.2
[2.2.1]: https://github.com/crisradu75/logic-artisan/compare/cla--v2.2.0...cla--v2.2.1
[2.2.0]: https://github.com/crisradu75/logic-artisan/compare/cla--v2.1.2...cla--v2.2.0
[2.1.2]: https://github.com/crisradu75/logic-artisan/compare/cla--v2.1.1...cla--v2.1.2
[2.1.1]: https://github.com/crisradu75/logic-artisan/compare/cla--v2.1.0...cla--v2.1.1
[2.1.0]: https://github.com/crisradu75/logic-artisan/compare/cla--v2.0.0...cla--v2.1.0
[2.0.0]: https://github.com/crisradu75/logic-artisan/compare/cla--v1.2.4...cla--v2.0.0
