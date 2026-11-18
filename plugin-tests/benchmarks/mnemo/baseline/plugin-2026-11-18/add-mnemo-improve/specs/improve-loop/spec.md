# Spec Delta

## Purpose

**Serves:** the owner of a Mnemo domain repo, who improves recall by merging the loop's PRs. On request it turns the domain's query log into proposals the owner reviews, without ever touching the notes' bodies.

## ADDED Requirements

### Requirement: A run starts only when the owner asks
The improve skill SHALL start a run only when the owner asks for one in a session on a domain repo, for example with "run Mnemo maintenance", SHALL set up no schedule or GitHub workflow, and in a repo without `mnemo.schema.yml` at its top level SHALL say so and stop, changing nothing.

#### Scenario: Owner asks
- **WHEN** the owner says "run Mnemo maintenance" in a session on a domain repo
- **THEN** a run starts and reads that domain's query log

#### Scenario: Nothing scheduled
- **WHEN** a run ends
- **THEN** the domain repo and the session hold no scheduled task and no GitHub workflow that the run added

#### Scenario: Not a Mnemo repo
- **WHEN** maintenance is asked for in a repo without `mnemo.schema.yml`
- **THEN** the skill says so, and the working tree, branches and remote are unchanged

### Requirement: One loop PR at a time
When the domain already has an open loop PR, or a loop branch with no PR, a run SHALL name it and stop before reading the log, creating no branch, PR or issue.

#### Scenario: Loop PR open
- **WHEN** a run starts while a loop PR is open in the domain
- **THEN** it names the PR and stops, and nothing new exists afterwards

#### Scenario: Branch left by an interrupted run
- **WHEN** a run starts and a loop branch exists on the remote with no PR
- **THEN** it names the branch, stops, and does not delete the branch

#### Scenario: Merged PR's branch remains
- **WHEN** the only loop branch belongs to a merged or closed PR
- **THEN** the run proceeds

### Requirement: An empty log ends the run
When the query log holds no line for the run to read, the run SHALL report "no signals" and end without creating a branch, PR or issue.

#### Scenario: No log yet
- **WHEN** a run starts in a domain whose query-log folder is missing or empty
- **THEN** it reports "no signals" and nothing new exists afterwards

#### Scenario: Only blank or malformed lines
- **WHEN** every log line is blank or not valid JSON
- **THEN** it reports "no signals" with the count of skipped lines

### Requirement: Notes keep their bodies
A loop PR SHALL never delete or move a note, change any byte below a note's frontmatter, or change any file under `sources/` or `attachments/`, and in frontmatter SHALL change only `aliases`, `summary`, `questions` and `links`; a run whose change would break this SHALL open no PR and name the file.

#### Scenario: Alias added
- **WHEN** a loop change adds an alias to a note with Windows line endings
- **THEN** the PR diff changes only that note's frontmatter, and its body is byte-identical, line endings included

#### Scenario: Body edit refused
- **WHEN** a proposed change would reword a sentence below a note's frontmatter, or change its `title`
- **THEN** no PR is opened and the run names the note

#### Scenario: Sources and deletions refused
- **WHEN** a proposed change touches a file under `sources/` or `attachments/`, or deletes or moves a note
- **THEN** no PR is opened and the run names the file

### Requirement: Each change goes where it belongs
A domain-specific rule SHALL reach the domain only through a loop PR on `_meta/conventions.md`, and a change to Mnemo itself or to the domain's Mnemo copy (its `mnemo-*` skills, `.claude/mnemo/` and the Mnemo hook entries in `.claude/settings.json`), SHALL go out only as an issue on `mnemo`, never in a PR.

#### Scenario: Domain rule
- **WHEN** the log shows a naming rule that only this domain needs
- **THEN** the run proposes it as a PR changing `_meta/conventions.md`

#### Scenario: Change to a Mnemo skill
- **WHEN** the log points to a fix in the recall skill
- **THEN** the run drafts an issue on `mnemo`, and no PR changes any file of the Mnemo copy

### Requirement: Every change shows its evidence
Every change in a loop PR SHALL be cited in its description by the query-log lines behind it, each by log file and line with its date, result, and opened and cited paths, and a change with no supporting line SHALL appear in no PR and no issue.

#### Scenario: Provenance in a PR
- **WHEN** a loop PR adds an alias because of two `not-found` lines
- **THEN** its description lists both lines by file and line with date, result, opened and cited paths

#### Scenario: Unsupported change dropped
- **WHEN** a candidate change cites no log line
- **THEN** it appears in no PR and no issue

### Requirement: A loop PR is complete when opened
Each loop PR SHALL hold the diff, the scorecard and the provenance in its description from the moment it is opened against main, and a run that cannot produce all three SHALL open no PR and leave no loop branch on the remote.

#### Scenario: Complete PR
- **WHEN** a run opens a loop PR
- **THEN** its description already holds the scorecard and the provenance of every change in its diff

#### Scenario: Scoring cut off
- **WHEN** scoring fails or is interrupted partway
- **THEN** no PR is opened, no loop branch is on the remote, and the run says why

### Requirement: Loop branches pass the note checks
Before a loop branch is pushed, the run SHALL run the check script's `links`, `schema` and `secrets` checks on every file the branch changes, and on any failure SHALL push nothing, open no PR and name the file.

#### Scenario: Secret in a loop change
- **WHEN** a loop change would add a line holding an IBAN to a note's summary
- **THEN** nothing is pushed, no PR is opened, and the run names the note

### Requirement: Meta changes get their own PR
A change to the loop's scorer, thresholds, guardrails or test set held in the domain SHALL go in a PR whose title starts with `[meta]` and which holds no content change, and a run SHALL open at most one content PR and one `[meta]` PR.

#### Scenario: Mixed run
- **WHEN** one run proposes an alias and an edit to the test set
- **THEN** it opens two PRs: a content PR with the alias, and a `[meta]` PR with the test-set edit only

#### Scenario: Content PR stays clean
- **WHEN** a PR title has no `[meta]` prefix
- **THEN** its diff holds no change to the test set

### Requirement: Owner-only rules stay
No loop PR or issue SHALL propose removing or weakening the rule against note-body edits or the rule that only counts leave a domain.

#### Scenario: Log pushes for a body fix
- **WHEN** log lines show answers failing because of wording inside a note body
- **THEN** the run proposes at most frontmatter or conventions changes and never a change to either owner-only rule

### Requirement: The run never writes to the session's folder
A run, whether it finishes, fails or is interrupted, SHALL never check out, stage, commit or add a file in the session's folder, nor change the branch the session has checked out.

#### Scenario: Capture waiting during a run
- **WHEN** a run happens while a captured note is uncommitted
- **THEN** the run made no commit and staged nothing in the session's folder, the note is byte-identical, and the session is on the branch it started on

#### Scenario: Run interrupted
- **WHEN** a run is stopped partway
- **THEN** the session is on its starting branch and holds no file the run added, a bytecode cache included

### Requirement: Only the owner merges
The run SHALL never commit on, push to or merge into the domain's main branch, its own PRs included.

#### Scenario: Run complete
- **WHEN** a run opens a loop PR
- **THEN** no commit the run made is on the remote main, and the PR is unmerged
