# Spec Delta

## Purpose

**Serves:** the owner as maintainer, and every domain repo that receives a copy. It keeps the shipped folder copyable as is, ties each release to one version, and runs the tests that hold both.

## ADDED Requirements

### Requirement: The shipped folder holds only shared files
`mnemo-plugin/` SHALL hold only the files every domain repo shares, laid out as they will sit under a domain repo's `.claude/`, and never tests, evals, plugin or marketplace manifests, or a per-domain file such as `CLAUDE.md`, `mnemo.schema.yml`, `settings.json` or the stamp file.

#### Scenario: Per-domain file in the shipped folder
- **WHEN** a file named `mnemo.schema.yml` or `stamp.json` is added anywhere under `mnemo-plugin/`
- **THEN** the shipped-layout test fails and names it

#### Scenario: Plugin manifest returns
- **WHEN** a `plugin.json` or `marketplace.json` exists anywhere in the repo
- **THEN** the shipped-layout test fails

#### Scenario: Folder outside the destination shape
- **WHEN** a top-level folder under `mnemo-plugin/` is neither `skills/` nor `mnemo/`
- **THEN** the shipped-layout test fails and names it

### Requirement: Every named domain path ships
Every `.claude/skills/...` or `.claude/mnemo/...` path that a file under `mnemo-plugin/` names SHALL map to an existing file under `mnemo-plugin/`.

#### Scenario: Missing target
- **WHEN** a shipped file names `.claude/mnemo/scripts/missing.py` and `mnemo-plugin/mnemo/scripts/missing.py` does not exist
- **THEN** the test suite fails and names the shipped file and the path

### Requirement: The version equals the tag
A release tag SHALL be `v<major>.<minor>.<patch>`, the root `VERSION` file at that tag SHALL hold the same version without the `v`, and a published tag is never moved.

#### Scenario: Tagged commit with a matching version
- **WHEN** the tests run on a commit tagged `v0.2.0` whose `VERSION` reads `0.2.0`
- **THEN** the version test passes

#### Scenario: Mismatch
- **WHEN** the tests run on a commit tagged `v0.2.0` whose `VERSION` reads `0.1.9`
- **THEN** the version test fails and shows both values

#### Scenario: Malformed version
- **WHEN** `VERSION` holds anything other than three dot-separated numbers
- **THEN** the version test fails

### Requirement: A shipped change bumps the version
A branch that changes anything under `mnemo-plugin/` or `.claude/skills/mnemo-setup/` SHALL carry a `VERSION` higher than the one on `main`.

#### Scenario: Shipped change without a bump
- **WHEN** the tests run on a branch that edits a file under `mnemo-plugin/` and leaves `VERSION` equal to `main`'s
- **THEN** the version test fails

#### Scenario: Docs-only change
- **WHEN** a branch changes only `README.md`
- **THEN** the version test passes without a bump

### Requirement: Tests run locally on scratch data
`python -m unittest discover -s tests` from the repo root SHALL run every test, locally only; tests SHALL use invented content in temporary folders, never a real note, and leave nothing behind outside them; the repo SHALL hold no GitHub workflow.

#### Scenario: One command
- **WHEN** the owner runs the test command from the repo root
- **THEN** every test under `tests/` runs and the command exits 0 only when all pass

#### Scenario: Nothing left behind
- **WHEN** the full suite finishes
- **THEN** `git status --porcelain --ignored` shows nothing the tests created

#### Scenario: Workflow added
- **WHEN** a file exists under `.github/workflows/`
- **THEN** the test suite fails
