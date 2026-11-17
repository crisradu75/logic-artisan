# Spec Delta

## Purpose

**Serves:** the owner, who saves notes from several locations and must never lose one. It checks, commits and pushes a domain repo's changes in one call, so capture and the end-of-turn backup save the same way.

## ADDED Requirements

### Requirement: Save checks, commits and pushes in one call
`mnemo_check.py save` SHALL pull the current branch with rebase, run `links`, `schema`, `deletions` and `secrets` on the changed files, commit those files with the text given by `--message` (default `mnemo: save`), and push, exiting 0 only when the commit is on the remote.

#### Scenario: Clean save
- **WHEN** `save --message "capture(idea): Rates"` runs on a scratch repo with one valid new note
- **THEN** the remote branch holds one new commit with that message containing that note, and save exits 0

#### Scenario: Default message
- **WHEN** `save` runs without `--message` on a valid change
- **THEN** the commit message is `mnemo: save`

### Requirement: A failing check commits nothing
When any check fails, `save` SHALL commit nothing, push nothing, print every problem, exit non-zero, and leave every changed file exactly as it was.

#### Scenario: Secret blocks the save
- **WHEN** `save` runs and a changed note contains an IBAN
- **THEN** no commit is made, the note is unchanged on disk, and the output names the note and line

#### Scenario: Broken link blocks the save
- **WHEN** `save` runs and a changed note links to a missing path
- **THEN** no commit is made and save exits non-zero

### Requirement: Save commits only what it checked
`save` SHALL commit exactly the changed files it checked, and never stage or commit an ignored file or a file it did not check.

#### Scenario: Ignored file stays out
- **WHEN** `save` runs while an ignored file has changed alongside a valid note
- **THEN** the commit contains the note and not the ignored file

### Requirement: Save stops safely on a conflict
When the pull cannot rebase cleanly, or a rebase or merge is already in progress, `save` SHALL stop without committing, leave the repo with no rebase in progress and every note's content as it was before the call, and say which files conflict.

#### Scenario: Remote edited the same note
- **WHEN** the remote holds a different edit to a note that is also changed locally
- **THEN** save commits nothing, the local edit is still on disk, no rebase is in progress, and the output names the note

#### Scenario: Rebase left from an interrupted run
- **WHEN** `save` starts while a rebase is in progress
- **THEN** it commits nothing and says a rebase must be finished or aborted first

### Requirement: Unpushed commits are pushed later
When a push fails or runs out of time, `save` SHALL keep the commit locally, exit non-zero and say it was not pushed; a later `save` SHALL push every local commit the remote lacks, even when nothing new has changed.

#### Scenario: Push fails
- **WHEN** the remote is unreachable during a save of a valid note
- **THEN** the commit stays on the local branch and save exits non-zero saying it was not pushed

#### Scenario: Next save pushes the earlier commit
- **WHEN** `save` runs with a clean working tree while the branch is one commit ahead of its remote
- **THEN** that commit is pushed and save exits 0

#### Scenario: Nothing to do
- **WHEN** `save` runs with a clean working tree and nothing unpushed
- **THEN** it makes no commit and exits 0

### Requirement: Save never hangs
Each network step of `save` (pull and push) SHALL give up after 60 seconds and never wait for typed input such as a password; giving up counts as a failure under the rules above.

#### Scenario: Remote never answers
- **WHEN** the pull gets no answer within 60 seconds
- **THEN** save stops, commits nothing and exits non-zero saying the pull timed out

#### Scenario: Credentials would be asked for
- **WHEN** the remote asks for a password
- **THEN** save fails at once instead of waiting
