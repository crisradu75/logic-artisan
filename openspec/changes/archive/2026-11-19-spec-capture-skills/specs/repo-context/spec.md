## MODIFIED Requirements

### Requirement: Checking recorded paths

The plugin SHALL ship a checker a consuming repo runs as `python3 <path>` that names the file, line and path of every repo path in `cla.io/project-facts.md` or an overlay that no longer exists, exiting 0 when none is stale, 1 when some are, and 2 when it cannot run.

#### Scenario: A renamed directory

- **WHEN** the facts file names a path under a top-level directory that was since renamed or removed, committed or only staged
- **THEN** the checker reports that file, line and path and exits 1

#### Scenario: A path that was never in this repo

- **WHEN** the facts file names a path whose first part was never a top-level directory of this repo, such as another repo's folder or an owner and name pair
- **THEN** the checker does not report it, and if git cannot give the repo's history it says so on stderr and checks as before

#### Scenario: A machine-local file

- **WHEN** the facts file names a machine-local file such as a local settings file that git does not track and that is absent from this clone
- **THEN** the checker does not report it
