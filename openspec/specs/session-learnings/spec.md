# session-learnings Specification

## Purpose

**Serves:** maintainers who want a session's mistakes turned into fixes the next session runs under.

What the codify-learnings skill proposes from a session's failures, when it writes, and what it logs.

## Requirements

### Requirement: Failures come from the whole session

`/cla:codify-learnings` SHALL review the session from its first message, listing each user correction, reverted edit, denied tool call and wasted turn with a short quote, and when it finds none SHALL say so and propose no fix.

#### Scenario: A correction early in a long session

- **WHEN** the user corrected the agent in the session's first turns
- **THEN** that correction is listed, quoted, among the failures

### Requirement: At most three fixes, each answering a quoted failure

`/cla:codify-learnings` SHALL propose at most three fixes, most valuable first, each quoting the session failure it answers, and SHALL drop any candidate that answers no failure of the session.

#### Scenario: Five candidate fixes

- **WHEN** the review finds five candidate fixes
- **THEN** only the three most valuable are proposed

#### Scenario: A fix with no failure behind it

- **WHEN** a candidate fix answers no failure of the session
- **THEN** it is not proposed

### Requirement: A tool fix before a doc note

`/cla:codify-learnings` SHALL place a new lesson at the lowest rung that would have prevented it, and when the failure was something done by hand that a script, config, hook or test could have done SHALL propose that change first, with a doc or memory note at most a second aid.

#### Scenario: A cause found by hand

- **WHEN** the session lost turns diagnosing by hand what a script could check
- **THEN** the first fix proposed is that script, not a note

### Requirement: A rule that failed again is escalated

`/cla:codify-learnings` SHALL treat a failure that an existing instruction, hook or logged lesson should have prevented as a re-offense of that artifact, and SHALL propose its fix one rung above that artifact, or move it to a home of better reach when nothing mechanical can enforce it, never restating it on the same artifact.

#### Scenario: An instruction-file rule broken again

- **WHEN** a session breaks a rule its instruction file already states and a hook could detect the breach
- **THEN** the proposed fix is a hook, and the proposal names the instruction file as the artifact that failed

### Requirement: One prompt before anything is written

`/cla:codify-learnings` SHALL show each proposed fix's exact before and after text, then ask once which fixes to apply, all, none or chosen ones, SHALL write nothing, memory included, before the answer, and SHALL treat an empty answer as no consent, asking once more and taking a second empty answer as none.

#### Scenario: An empty answer twice

- **WHEN** the user answers the prompt with nothing, twice
- **THEN** no fix is applied and each is logged as rejected

#### Scenario: The text is shown first

- **WHEN** fixes are proposed
- **THEN** each one's exact before and after text appears above the prompt

### Requirement: A plugin fix goes upstream when the plugin is read-only

`/cla:codify-learnings` SHALL check whether the plugin is writable from the repo, and when it is not SHALL send a fix to a plugin file, including a shipped skill's bundled script, to `/cla:report-upstream` instead of editing the installed copy or a local overlay.

#### Scenario: An installed plugin

- **WHEN** the plugin is an installed copy outside the repo and a fix targets one of its skills
- **THEN** the fix's line names `/cla:report-upstream` as its target and the installed copy is not edited

#### Scenario: A bundled script

- **WHEN** a fix would change a shipped skill's bundled script and the plugin is read-only here
- **THEN** the fix is routed to `/cla:report-upstream`, not dropped and not edited

### Requirement: Each run is logged, and the log stays small

`/cla:codify-learnings` SHALL prepend one dated entry to the repo's lessons log naming each applied and rejected fix and each re-offense, and when the live log grows past its word limit SHALL move its oldest entries, whole and unedited, to the archive beside it without losing or duplicating an entry.

#### Scenario: A run with one applied and one rejected fix

- **WHEN** the user applies the first of two proposed fixes
- **THEN** the new entry at the top of the log lists the first as applied and the second as rejected

#### Scenario: The log grows past its limit

- **WHEN** the new entry takes the live log over its word limit
- **THEN** its oldest entries move whole to the archive and the entry count over both files is unchanged
