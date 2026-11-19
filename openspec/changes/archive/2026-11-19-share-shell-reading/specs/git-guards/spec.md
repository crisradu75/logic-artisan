## MODIFIED Requirements

### Requirement: A push that skips the pre-push guard asks first

The guard hooks SHALL ask the user before a `git push` that skips the `pre-push` guard, by `--no-verify`, a different `core.hooksPath`, or `ALLOW_PUSH_TO_MAIN=1` or `ALLOW_TAG_REWRITE=1` typed into the command.

#### Scenario: A push with no-verify

- **WHEN** an agent runs `git push --no-verify origin main`
- **THEN** the user is asked before it runs

#### Scenario: An ordinary push

- **WHEN** an agent runs `git push origin feature/x`
- **THEN** no prompt about the pre-push guard is shown

#### Scenario: A push carrying the tag override

- **WHEN** an agent runs `ALLOW_TAG_REWRITE=1 git push origin :refs/tags/v1`
- **THEN** the user is asked before it runs

## ADDED Requirements

### Requirement: A mirror push asks first

The guard hooks SHALL ask the user before a `git push --mirror`, which can delete remote branches and tags that the `pre-push` guard is never asked about, and SHALL NOT ask about `--mirror` on any other git command.

#### Scenario: A mirror push

- **WHEN** an agent runs `git push --mirror origin` or `bash -c "git push --mirror"`
- **THEN** the user is asked before it runs

#### Scenario: A mirror clone

- **WHEN** an agent runs `git clone --mirror https://example.com/x.git`
- **THEN** no prompt is shown
