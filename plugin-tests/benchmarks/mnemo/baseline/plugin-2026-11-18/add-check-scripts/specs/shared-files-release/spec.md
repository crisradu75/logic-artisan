# Spec Delta

## Purpose

**Serves:** the owner's domain repos, which receive a copy of `mnemo-plugin/` from a release tag. It keeps that folder holding only the shared files, and each tag carrying the version it names.

## ADDED Requirements

### Requirement: The shared folder holds only shared files
The shipped-layout test SHALL fail when `mnemo-plugin/` holds a file outside its fixed folder shape (`skills/mnemo-*/` except `skills/mnemo-setup/`, `skills/README.md`, `mnemo/scripts/`, `mnemo/conventions/`, `mnemo/hooks/`), including a test, an eval, a per-domain file, the setup skill or a plugin manifest.

#### Scenario: Stray test file
- **WHEN** a `test_*.py` file is placed in `mnemo-plugin/mnemo/scripts/`
- **THEN** the shipped-layout test fails and names it

#### Scenario: Per-domain file
- **WHEN** a `mnemo.schema.yml` is placed in `mnemo-plugin/`
- **THEN** the shipped-layout test fails and names it

#### Scenario: Setup skill in the shared folder
- **WHEN** a `skills/mnemo-setup/` folder is placed in `mnemo-plugin/`
- **THEN** the shipped-layout test fails and names it

### Requirement: Domain paths in shared files resolve
The shipped-layout test SHALL fail when a file in `mnemo-plugin/` names a domain path under `.claude/mnemo/` or `.claude/skills/mnemo-*` whose matching file does not exist in `mnemo-plugin/`, except `.claude/mnemo/stamp.json`, which setup generates per domain; a path holding a `*` resolves when it matches at least one file.

#### Scenario: Missing script
- **WHEN** a shared file names `.claude/mnemo/scripts/absent.py`
- **THEN** the shipped-layout test fails and names the path

#### Scenario: Existing script
- **WHEN** a shared file names `.claude/mnemo/scripts/mnemo_check.py`
- **THEN** the shipped-layout test passes for that path

#### Scenario: Per-domain stamp named
- **WHEN** a shared file names `.claude/mnemo/stamp.json`
- **THEN** the shipped-layout test passes for that path

### Requirement: VERSION matches every release tag
The version test SHALL fail when `VERSION` is not one semver line, or when any tag `v<semver>` points at a commit whose `VERSION` differs from that tag's version.

#### Scenario: Tag and file agree
- **WHEN** a scratch repo has tag `v1.2.3` on a commit whose `VERSION` is `1.2.3`
- **THEN** the version test passes

#### Scenario: Tag and file differ
- **WHEN** a scratch repo has tag `v1.2.4` on a commit whose `VERSION` is `1.2.3`
- **THEN** the version test fails and names the tag

### Requirement: Shared scripts need only standard Python
The tests SHALL fail when a Python file in `mnemo-plugin/` imports a module outside the Python standard library or uses syntax that Python 3.8 cannot parse.

#### Scenario: Third-party import
- **WHEN** a shared script imports `yaml`
- **THEN** the tests fail and name the script and module

#### Scenario: Newer syntax
- **WHEN** a shared script uses a `match` statement
- **THEN** the tests fail and name the script
