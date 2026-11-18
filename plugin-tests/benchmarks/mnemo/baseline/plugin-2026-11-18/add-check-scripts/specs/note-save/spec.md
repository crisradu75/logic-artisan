# Spec Delta

## Purpose

**Serves:** the owner, whose captures must reach GitHub before a cloud VM is reclaimed. It checks, commits and pushes the changed notes in one call, and never loses them when something fails.

## ADDED Requirements

### Requirement: Save checks, commits and pushes in one call
The `save` subcommand SHALL pull with rebase, run every check on the changed files, commit them with the message given on its command line or a default one, and push the current branch to its upstream, or to the branch of the same name on `origin` when it has none, exiting 0; with no changes it SHALL still push a commit that waits to be pushed, and with neither it SHALL change nothing and exit 0.

#### Scenario: Changed notes saved
- **WHEN** `save` runs with a valid new note on a branch with no upstream and a reachable `origin`
- **THEN** the note is committed with the given message, the commit is on `origin` under the same branch name, and it exits 0

#### Scenario: Only an unpushed commit
- **WHEN** the working tree is clean and one commit waits to be pushed
- **THEN** `save` pushes it and exits 0

#### Scenario: Nothing to do
- **WHEN** the working tree is clean and nothing waits to be pushed
- **THEN** `save` makes no commit, contacts no remote and exits 0

### Requirement: A failing check saves nothing
When any check fails or cannot run, `save` SHALL commit nothing, leave every changed file and the index exactly as they were, print why, and exit with that check's status.

#### Scenario: Secret in a capture
- **WHEN** `save` runs and a changed note holds an IBAN
- **THEN** nothing is committed, the note is unchanged in the working tree, and `save` exits 3

#### Scenario: Broken link
- **WHEN** `save` runs and a changed note has a broken link
- **THEN** nothing is committed and `save` exits 1

### Requirement: Save commits exactly what it checked
`save` SHALL commit exactly the files its checks passed, with the bytes its checks read, a deleted file as a deletion, and no other file, ignored files included.

#### Scenario: Ignored file left out
- **WHEN** `save` runs with a changed note and a new ignored file
- **THEN** the commit holds the note and not the ignored file

#### Scenario: Committed bytes match
- **WHEN** a checked note is rewritten after the checks read it and before the commit
- **THEN** the commit holds the bytes that were checked, and the working-tree file keeps its new bytes, uncommitted

#### Scenario: Deletion saved
- **WHEN** `save` runs after a note that nothing links to is deleted
- **THEN** the commit records the deletion and `save` exits 0

### Requirement: Waiting commits are checked before they are pushed
Before pushing, `save` SHALL run the `secrets` check on every line that a commit waiting to be pushed adds, and on a hit SHALL push nothing, keep the local commits as they are, name the commit and file, and exit 3.

#### Scenario: Secret in a waiting commit
- **WHEN** a commit made outside `save` adds an IBAN and waits to be pushed
- **THEN** `save` pushes nothing, exits 3 and names the commit and file

#### Scenario: Secret added then removed
- **WHEN** one waiting commit adds a private key and a later waiting commit removes it
- **THEN** `save` pushes nothing and exits 3

### Requirement: A pull conflict leaves notes untouched
When pulling would conflict with an uncommitted change or a waiting commit, `save` SHALL leave the working tree, the index and the history as they were before the run, with no conflict markers and no rebase in progress, commit nothing, name the conflicting files, and exit 2.

#### Scenario: Same note changed elsewhere
- **WHEN** the remote has a new commit changing a note that is also changed but uncommitted here
- **THEN** the local note keeps its exact content, no commit is made, no rebase is in progress, and `save` exits 2 naming the note

#### Scenario: Waiting commit conflicts
- **WHEN** a waiting local commit and a remote commit change the same lines
- **THEN** the local history is as before the run, no rebase is in progress, and `save` exits 2

### Requirement: An unpushed commit gets its own notice
When the commit is made but the remote cannot be reached or rejects the push, `save` SHALL keep the commit locally, print that it was committed but not pushed, and exit 4, and the next `save` SHALL push it.

#### Scenario: Remote unreachable
- **WHEN** `save` runs with a valid change and the remote cannot be reached
- **THEN** the change is committed locally, `save` exits 4 and says it was not pushed

#### Scenario: Next run pushes
- **WHEN** `save` runs again with the remote reachable
- **THEN** the waiting commit reaches the remote and `save` exits 0

### Requirement: An unfinished repo state blocks the save
When the run starts with a rebase or merge in progress, unresolved conflicts, a detached head or a git lock file, `save` SHALL commit nothing, change nothing, remove nothing, name the state, and exit 2; a lock file that the run's own git steps create SHALL not outlive the run.

#### Scenario: Rebase in progress
- **WHEN** `save` runs while a rebase is in progress
- **THEN** it makes no commit, leaves the rebase as it was and exits 2

#### Scenario: Leftover lock
- **WHEN** `save` runs while a git index lock file exists
- **THEN** it exits 2, names the lock file and does not delete it

### Requirement: Save never hangs
`save` SHALL never wait for input, a credential prompt included, and SHALL end within its time limit when the remote does not answer, keeping every change either uncommitted or committed and never part-applied.

#### Scenario: Silent remote
- **WHEN** `save` runs and the remote accepts the connection but never answers
- **THEN** `save` ends within 90 seconds, no rebase is in progress, no lock file created by the run remains, and the notes are intact

#### Scenario: Remote asks for a password
- **WHEN** the remote asks for credentials
- **THEN** `save` does not wait, ends with a non-zero exit, and the notes are intact
