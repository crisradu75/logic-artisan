# note-saving

## Purpose

**Serves:** the capture skill and the end-of-turn hook, which save notes with one call. It defines what one `save` call does, and what it leaves behind when a step fails.

## ADDED Requirements

### Requirement: One call saves
The `save` subcommand SHALL, in one call, pull the current branch from its remote with rebase, run all four checks on the files being saved, commit them, and push, and SHALL exit 0 only when the commit has reached the remote.

#### Scenario: Clean save
- **GIVEN** a domain repo with one changed note that breaks no rule
- **WHEN** `save` runs
- **THEN** the remote holds a new commit with that note and `save` exits 0

#### Scenario: Remote moved ahead
- **GIVEN** the remote has a commit the local branch lacks, touching other files
- **WHEN** `save` runs with one changed note
- **THEN** the new commit sits on top of the remote's commit, the push succeeds and `save` exits 0

### Requirement: Nothing to save
When the working tree has no changes, `save` SHALL exit 0 at once, without contacting the remote and without making a commit.

#### Scenario: Clean working tree
- **GIVEN** a domain repo with no changed or untracked files
- **WHEN** `save` runs
- **THEN** it exits 0, says there is nothing to save, and makes no network call

### Requirement: A failed check commits nothing
When any check reports a problem or cannot run, `save` SHALL commit nothing, leave every file where and as it was, print each problem, and exit with that check's status.

#### Scenario: Secret blocks the save
- **GIVEN** a changed note holding a card number
- **WHEN** `save` runs
- **THEN** it exits 1, makes no commit, prints the secrets problem, and leaves the note in place and unchanged, with nothing moved to `inbox`

#### Scenario: Check cannot run
- **GIVEN** a domain schema file with a construct outside the YAML subset
- **WHEN** `save` runs with a changed note
- **THEN** it exits 2 and makes no commit

### Requirement: Named paths only
`save` SHALL stage and commit only the paths it is given, each by name, and when given none SHALL name each changed path itself, never staging by wildcard and never committing a path it was not given just because it was already staged.

#### Scenario: One of two changed notes
- **GIVEN** two changed notes
- **WHEN** `save` runs with only the first note's path
- **THEN** the commit holds only the first note, and the second stays changed and uncommitted

#### Scenario: Already-staged file left out
- **GIVEN** a staged file that `save` was not given
- **WHEN** `save` runs with another note's path
- **THEN** the commit does not hold the staged file

### Requirement: One push retry
When the push fails, `save` SHALL pull with rebase and push once more, and if that also fails SHALL keep the commit in the local branch, say it was not pushed, and exit 3.

#### Scenario: Remote moved during the save
- **GIVEN** the remote gains a commit between `save`'s pull and its push
- **WHEN** the first push is rejected
- **THEN** `save` pulls with rebase, pushes again and exits 0

#### Scenario: Remote unreachable
- **GIVEN** a remote that refuses every push
- **WHEN** `save` runs with a changed note that breaks no rule
- **THEN** it exits 3, the commit is in the local branch, and the message says it was committed but not pushed

### Requirement: Pull conflict stops the save
When the pull with rebase hits a conflict, `save` SHALL stop the rebase, leave the owner's changes in the working tree, commit nothing, name the conflicting files and exit 2.

#### Scenario: Same line changed on both sides
- **GIVEN** a local uncommitted edit and a remote commit that change the same line of one note
- **WHEN** `save` runs
- **THEN** it exits 2, names the note, makes no commit, leaves no rebase in progress, and the local edit is still in the working tree

### Requirement: Bounded run time
Every network step in `save` SHALL give up after the time limit set by `MNEMO_NET_TIMEOUT_SECONDS`, so that one call ends within a fixed worst-case time that a hook timeout can be sized to.

#### Scenario: Remote never answers
- **GIVEN** `MNEMO_NET_TIMEOUT_SECONDS` is 2 and a remote that accepts the connection but never answers
- **WHEN** `save` runs with a changed note
- **THEN** it ends within 15 seconds, exits 2 or 3, and says which network step timed out
