# Spec Delta

## ADDED Requirements

### Requirement: Setup checks that its protected files were left alone

`/cla:cla-setup` SHALL record the repo's instruction files, an existing feedback notes file, the machine-read local files, the terminology file and the overlays before it writes anything, and at the end SHALL report the run as not clean, naming each file, when one of them was changed, created or deleted without the user's yes, or SHALL say the check could not run.

#### Scenario: An instruction file changed during the run

- **WHEN** a setup run leaves `CLAUDE.md` different from how it was when the run started
- **THEN** the setup guard's `verify` exits 1 and names the file as changed, even when the user said yes to it, and setup does not call the run clean

#### Scenario: A change the user agreed to

- **WHEN** the user said yes to a reconcile of the terminology file and the run changed only that file
- **THEN** `verify` with that file passed as `--approved` exits 0 and names the approved change

#### Scenario: A file already edited before the run

- **WHEN** the owner had uncommitted edits in `CLAUDE.md` before the run and the run left it as it found it
- **THEN** `verify` exits 0, and a missing or corrupt snapshot makes it exit 2, never 0

### Requirement: Setup creates no overlay and no terminology file

`/cla:cla-setup` SHALL report the run as not clean when an overlay or the terminology file exists at the end of the run that did not exist at its start, whatever the user agreed to.

#### Scenario: A new overlay

- **WHEN** a setup run writes `cla.io/overlays/spec-to-pr.md` where no such file existed before
- **THEN** the setup guard's `verify` exits 1 and names the overlay as created, with or without `--approved`
