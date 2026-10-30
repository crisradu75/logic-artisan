# Changelog

Notable changes to the CLA plugin, by release tag. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[semantic versioning](https://semver.org/) as `CLAUDE.md` defines it for this plugin. Entries link
the pull request that made them. Releases before 2.0.0 are in the git tags;
[docs/history.md](docs/history.md) tells the background.

## [Unreleased]

### Fixed

- `ask-destructive-git`: an inline `ALLOW_PR_MERGE=1` authorizes only the `gh pr merge` it
  heads. A prefix in any other segment of the command used to silence the merge prompt.
- `ask-destructive-git` asks before a push that skips the `pre-push` guard: `--no-verify`,
  `-c core.hooksPath=...`, or an inline `ALLOW_PUSH_TO_MAIN=1`.
- The `pre-push` guard also refuses the remote's own default branch, not only `main` and
  `master`.
- Both dispatchers ask instead of failing open when `_dispatch_lib` fails to load or the
  dispatcher crashes; the old exit 1 let every guarded call through.
- `block-cd-in-bash` catches `{ cd x; }`, `builtin cd`, `command cd`, and `cd` after `if`,
  `then`, `elif`, `else`, `while`, `until` or `do`.
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

[Unreleased]: https://github.com/crisradu75/logic-artisan/compare/cla--v2.2.1...HEAD
[2.2.1]: https://github.com/crisradu75/logic-artisan/compare/cla--v2.2.0...cla--v2.2.1
[2.2.0]: https://github.com/crisradu75/logic-artisan/compare/cla--v2.1.2...cla--v2.2.0
[2.1.2]: https://github.com/crisradu75/logic-artisan/compare/cla--v2.1.1...cla--v2.1.2
[2.1.1]: https://github.com/crisradu75/logic-artisan/compare/cla--v2.1.0...cla--v2.1.1
[2.1.0]: https://github.com/crisradu75/logic-artisan/compare/cla--v2.0.0...cla--v2.1.0
[2.0.0]: https://github.com/crisradu75/logic-artisan/compare/cla--v1.2.4...cla--v2.0.0
