# Proposal

## Why

Every Mnemo skill and hook needs one trusted way to check notes and save them. Without it there is no base note schema, no secret scan, and no single `save` call, and nothing to block a bad commit. The plugin also has no test harness. `README.md` says `marketplace.json` points at a release tag, but the file still uses a plain folder source. This is the first change of the plugin-structure batch. It sets the cross-cutting contracts that later changes cite: the base schema, the check exit codes, "a skipped check is a failure", and how the repo root is found.

## What Changes

- Add the plugin's base note schema under `plugins/mnemo/conventions/`:
  - five required fields and four optional ones
  - the `inbox` rules
  - the add-only rule
- Add `plugins/mnemo/scripts/mnemo_check.py`. It is Python 3 with the standard library only, and it has five subcommands: `links`, `schema`, `deletions`, `secrets` and `save`. There is no `index` subcommand.
  - The checks cover changed files only, plus any note that links to a path the change deletes.
  - `save` pulls with rebase, runs the checks, commits the named paths and pushes, all in one call.
- Define the script interface that the next change (`add-guard-hooks`) will call: subcommands, selection options, exit codes, and the stderr and stdout contract.
- Add a `unittest` harness in `tests/` at the repo root. Nothing in it ships in `plugins/mnemo/`.
- Point `marketplace.json` at a release tag (`git-subdir` source with a `ref`). Add a test that the plugin version recorded at that tag equals the tag's version.
- Add tests for the packaging invariants:
  - every `${CLAUDE_PLUGIN_ROOT}/...` path exists
  - the scripts import only the standard library
  - there are no GitHub workflows
  - each shared file exists once
- Bump `plugin.json` to `0.2.0`.

## Capabilities

### New Capabilities

Cross-cutting first:
- `check-interface`: covers four things:
  - the check command's subcommands, exit codes and output contract
  - "a skipped check is a failure"
  - finding the repo root from the working directory
  - which files are notes and which files a run covers
- `note-schema`: covers the base fields, field values, the `inbox` rules, the domain type rules, the domain schema file, the YAML subset and the add-only rule.
- `note-checks`: covers what the `links`, `deletions` and `secrets` checks report.
- `note-saving`: covers what one `save` call does and what it leaves behind when a step fails.
- `plugin-release`: covers the tag-pinned release pointer, the packaged-path, stdlib-only and no-GitHub-workflow invariants, and that tests stay out of the shipped plugin.

### Modified Capabilities

None. There are no existing specs.

## Impact

- New files:
  - `plugins/mnemo/conventions/base-schema.yml`
  - `plugins/mnemo/scripts/mnemo_check.py`
  - `tests/`
- Changed files:
  - `.claude-plugin/marketplace.json`: becomes a tag pointer
  - `plugins/mnemo/.claude-plugin/plugin.json`: version bump
  - `README.md`
  - `CLAUDE.md`: adds the release and test rules
  - `cla.io/project-facts.md`: adds the test command and test locations
- Owner actions:
  - cut the first release tag from the Mac or GitHub's web page
  - run the device checks listed in `tasks.md` group 1
- Out of scope:
  - hooks, the Python probe and `hooks.json` (`add-guard-hooks`)
  - the trigger evals
  - the deferred metadata from structure Q14
  - the per-folder write-rules file
  - any skill
- Design: see `design.md`. It is written because this change is cross-cutting, adds data formats and covers a security scan.
