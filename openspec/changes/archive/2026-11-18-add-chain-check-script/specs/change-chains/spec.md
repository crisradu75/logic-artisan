# Spec Delta

## ADDED Requirements

### Requirement: A chain checks a pull request's head before it merges it

Before a chain merges a pull request, the chain check's `before-merge` SHALL exit 1 with the reason the chain records when the run notes hold no head for it, it is not on the branch the run recorded or comes from a fork, it targets another base, it is not open, its head or the remote branch differs from the recorded head, or the checkout is on another commit or has uncommitted changes, and SHALL exit 2, never 0, when it cannot ask the host or the remote.

#### Scenario: Commits pushed after the head was recorded

- **WHEN** the remote branch holds a commit the run notes did not record as the head
- **THEN** `before-merge` exits 1 with `head moved` and the pull request is not merged

#### Scenario: A pull request the chain did not open

- **WHEN** the run notes name a pull request whose branch is not the one the run recorded
- **THEN** `before-merge` exits 1 with `not opened by this chain`

#### Scenario: The host cannot be asked

- **WHEN** `gh` is missing or fails
- **THEN** `before-merge` exits 2 and the pull request is not merged

### Requirement: A chain counts a merge only when the host reports it merged

After a chain's merge command, the chain check's `after-merge` SHALL exit 0 and name the merge commit only when the host reports the pull request merged into the base at the recorded head, SHALL exit 1 with `queued: merges later outside this run` when an automatic merge is pending and with another reason in every other case, and SHALL exit 2 when the host names no merge commit.

#### Scenario: Auto-merge turned on instead of a merge

- **WHEN** the merge command exits 0 but the pull request is still open with auto-merge pending
- **THEN** `after-merge` exits 1 with `queued: merges later outside this run` and the item does not count as merged

#### Scenario: Someone else merged other commits

- **WHEN** the pull request is merged but at a head other than the one the run notes recorded
- **THEN** `after-merge` exits 1 with `merged at a head this run did not check` and the item does not count as merged

### Requirement: A chain's own fix becomes the recorded head only once it is committed and pushed

After a chain commits and pushes its own fix, the chain check's `fix-pushed` SHALL exit 0, naming the commit to record as the new head, only when a commit was made past the recorded head, nothing outside the run notes is uncommitted and the remote branch holds that commit, and SHALL exit 1 with `fix not committed` or `push not verified` otherwise.

#### Scenario: A hook rejected the commit

- **WHEN** the fix's commit was refused, so the checkout is still on the recorded head
- **THEN** `fix-pushed` exits 1 with `fix not committed` and the recorded head is unchanged

#### Scenario: The push did not land

- **WHEN** the fix was committed but the remote branch does not hold it
- **THEN** `fix-pushed` exits 1 with `push not verified`

### Requirement: A resumed chain acts only on its own pull request at the recorded head

When a chain resumes an item whose pull request it recorded, the chain check's `resume` SHALL exit 0 only when that pull request is open on the recorded head or already merged into the base at that head, and SHALL exit 1 with the reason otherwise, such as `head moved since review`, `head unverifiable (ledger lost)`, `PR closed without merging`, `recorded PR not found` or `not opened by this chain`.

#### Scenario: Commits pushed while the run was stopped

- **WHEN** a resumed item's pull request head differs from the head the run notes recorded
- **THEN** `resume` exits 1 with `head moved since review` and the item is neither handed back nor merged

#### Scenario: Merged while the run was stopped

- **WHEN** a resumed item's pull request was merged into the base at the recorded head in the meantime
- **THEN** `resume` exits 0 and names the merge commit for the run notes
