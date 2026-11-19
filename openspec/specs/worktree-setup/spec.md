# worktree-setup Specification

## Purpose

**Serves:** developers who start an isolated copy of a repo to work in.

What the new-worktree skill sets up, and how it protects the files around a worktree.

## Requirements

### Requirement: A new worktree is ready to work in

`/cla:new-worktree` SHALL enter a new isolated worktree, run the repo's install command there, copy the repo's gitignored env files from the main checkout, and report the worktree path, its branch and base, and the result of each step.

#### Scenario: A repo with an env file

- **WHEN** the user runs `/cla:new-worktree` in a repo whose facts name an install command and an env file
- **THEN** the worktree holds the installed dependencies and the env file, and the report names the path, branch, base and both results

#### Scenario: An env file missing from the main checkout

- **WHEN** the main checkout has no such env file
- **THEN** the copy is skipped, the report says so and the rest of the setup still runs

### Requirement: Inside a worktree only setup runs

When the session is already inside a worktree, `/cla:new-worktree` SHALL create no second worktree, SHALL run the install and env-file copy in the current one, and SHALL say in its report that it ran setup only.

#### Scenario: A session started inside a worktree

- **WHEN** the entry is refused because the session is already in a worktree
- **THEN** the install and env copy run there and the report says the worktree already existed

### Requirement: Work stays inside the worktree

After entering a worktree, `/cla:new-worktree` SHALL direct every later file read, write and edit at the worktree's own path and never at the primary clone, and SHALL tell the user when a manual worktree gives the session no such redirection.

#### Scenario: A manual worktree

- **WHEN** a worktree was created by the plain-git fallback
- **THEN** the report says the session is not redirected and every path must name the worktree

### Requirement: A casing refusal falls back without deleting anyone's files

When the entry tool refuses because two spellings of one path differ only in letter case, `/cla:new-worktree` SHALL offer a plain-git fallback that creates the worktree, clears only the stale registration a failed entry left, and fails the add rather than delete a non-empty directory git does not track, and SHALL NOT rename the repo's directory.

#### Scenario: A leftover directory with someone's work

- **WHEN** the target path holds files that git does not track
- **THEN** the fallback leaves them in place and the add fails with a message

### Requirement: The fallback keeps a worktree inside the repo

The plain-git fallback SHALL refuse, before creating anything, a worktree name that is not a single folder name and a worktree folder that is empty, absolute or holds a `..` step, so that the path as written stays inside the repo.

#### Scenario: A name that climbs out

- **WHEN** the fallback is given a worktree name such as `../escape`
- **THEN** it stops with a message and creates no worktree

#### Scenario: A folder outside the repo

- **WHEN** the fallback is given a worktree folder that is an absolute path or climbs out with `..`
- **THEN** it stops with a message and creates no worktree

### Requirement: Removing a worktree lists what it would delete

Before a worktree is removed by hand or with the exit tool's remove option, `/cla:new-worktree` SHALL have the untracked and gitignored files in it listed, because removal deletes them silently.

#### Scenario: A worktree with ignored files

- **WHEN** the user asks to remove a worktree that holds gitignored files
- **THEN** those files are listed before anything is removed
