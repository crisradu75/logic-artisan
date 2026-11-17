# improve-run

## Purpose

**Serves:** the owner, who starts maintenance of one domain when they choose. It sets what starts a run, when a run stops early, which query-log lines it reads, and that the session's own working tree stays untouched.

## ADDED Requirements

### Requirement: Started only on request
The improve skill SHALL run only when the owner asks for it in a domain session, for example by saying "run Mnemo maintenance", and no hook, schedule, GitHub workflow or other Mnemo skill SHALL start it.

#### Scenario: Owner asks for maintenance
- **GIVEN** a domain session on a repo the setup skill created
- **WHEN** the owner says "run Mnemo maintenance"
- **THEN** the improve skill runs

#### Scenario: Recall finishes
- **GIVEN** a domain whose query log holds `not-found` lines
- **WHEN** recall answers a question
- **THEN** the improve skill does not run

#### Scenario: Hook file names no run
- **WHEN** the plugin's tests read the plugin's hook file
- **THEN** it names no step that starts the improve skill

### Requirement: Stops outside a Mnemo domain
Before it reads the query log, the improve skill SHALL check that it runs inside a git repo whose top level holds `mnemo.schema.yml`, and when it does not SHALL say so and stop, changing nothing.

#### Scenario: Repo without a schema
- **GIVEN** a git repo with no `mnemo.schema.yml` at its top level
- **WHEN** the owner asks to run Mnemo maintenance
- **THEN** the skill says this is not a Mnemo domain repo, and `git status` and `HEAD` are unchanged

### Requirement: Stops when the loop's layout is missing
When the domain lacks the `hubs` folder, the `archive` folder or the test-set file, the improve skill SHALL name each missing item, say that a setup top-up adds it, and stop, changing nothing.

#### Scenario: Domain set up before this change
- **GIVEN** a domain repo with no `hubs` folder and no test-set file
- **WHEN** the owner asks to run Mnemo maintenance
- **THEN** the skill names both, points to the setup skill, and creates no branch

### Requirement: One open run at a time
When the domain repo has an open pull request from an earlier run, the improve skill SHALL name it and stop before reading the log, and when it cannot find out whether one is open SHALL say so and stop.

#### Scenario: Earlier loop pull request still open
- **GIVEN** an open pull request from an earlier run on the domain repo
- **WHEN** the owner asks to run Mnemo maintenance
- **THEN** the skill names that pull request, says a run waits until it is merged or closed, and creates no branch

#### Scenario: GitHub cannot be reached
- **GIVEN** a session where the domain repo's pull requests cannot be listed
- **WHEN** the owner asks to run Mnemo maintenance
- **THEN** the skill says it could not check for an open run and stops, creating no branch

### Requirement: Log lines since the last run
The improve skill SHALL read the query-log lines dated on or after the date of the newest closed pull request from an earlier run, merged or not, and every line when no earlier run's pull request was ever closed.

#### Scenario: Earlier run closed
- **GIVEN** a loop pull request from a run on an invented date D, now closed, and log lines dated before and after D
- **WHEN** a new run reads the log
- **THEN** it uses only the lines dated D or later

#### Scenario: First run
- **GIVEN** a domain with no earlier loop pull request
- **WHEN** a run reads the log
- **THEN** it uses every line in every month file

### Requirement: No signals ends the run
When the lines a run covers hold no readable line, the improve skill SHALL say "no signals" and end, creating no branch, pull request or issue.

#### Scenario: Empty query log
- **GIVEN** a domain whose query-log folder holds no line
- **WHEN** the owner asks to run Mnemo maintenance
- **THEN** the skill says "no signals", and the repo and GitHub are unchanged

### Requirement: Unreadable lines are counted
A covered log line that a standard JSON reader cannot parse, or that lacks one of the six keys the query log defines, SHALL be counted with its file and line number and never used as a signal, and the count SHALL appear in the run summary and in every pull request body.

#### Scenario: One broken line
- **GIVEN** a covered month file holding two valid lines and one line cut off mid-object
- **WHEN** a run reads the log
- **THEN** the summary says one line was unreadable and names its file and line number, and no proposal cites it

### Requirement: Session working tree untouched
The improve skill SHALL make its changes only in separate working copies, so the session's own working tree, its query log included, holds no change from the run when any turn ends.

#### Scenario: Turn ends during a run
- **GIVEN** a run that has edited a note on its branch
- **WHEN** the turn ends and the end-of-turn hook runs
- **THEN** the hook finds no change from the run to save, and the remote's main branch gains no commit from it

#### Scenario: Run finished
- **WHEN** a run ends, with or without pull requests
- **THEN** `git status` in the session's working tree shows no change from the run, and the run's extra working copies are removed
