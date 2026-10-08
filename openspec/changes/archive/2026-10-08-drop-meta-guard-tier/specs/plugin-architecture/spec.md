## MODIFIED Requirements

### Requirement: Conformance guard for the overlay separation

The plugin SHALL ship a generic checker at `skills/_shared/scripts/check_no_project_tokens.py` that fails when a non-overlay shipped file contains a project token. The token list SHALL be per-repo data at `cla.io/project-tokens.local.md`, never hard-coded in the checker, curated to distinctive repo-specific tokens (not generic words), and matched case-insensitively.

- **How it runs**: as a program (`python3 <path>`), needing no pytest; on demand, never as a hook. It finds the plugin tree from its own file location (any fallback depth matching where it actually sits), never from a repo name or absolute path.
- **What one run does**: all four checks, without stopping at the first failure — project tokens in `SKILL.md` and `references/**/*.md` prose; project tokens in source files (code, JSON config, shell scripts, agent and output-style markdown) under its scan roots; hardcoded absolute developer paths in that source; and that every file it claims to have scanned was readable.
- **What it skips**: overlay files (leaf `project-context.md` or `*.local.md`), bytecode and cache dirs, and a markdown file's leading YAML frontmatter (skill trigger text may name the repo); line numbers stay accurate. Its scan roots SHALL name only directories that ship.
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
