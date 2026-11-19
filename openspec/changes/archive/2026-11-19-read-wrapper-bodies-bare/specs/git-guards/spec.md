## MODIFIED Requirements

### Requirement: A push that skips the pre-push guard asks first

The guard hooks SHALL ask the user before a `git push` that skips the `pre-push` guard, by `--no-verify`, a different `core.hooksPath`, or `ALLOW_PUSH_TO_MAIN=1` or `ALLOW_TAG_REWRITE=1` typed into the command, in shell or PowerShell `$env:` form.

#### Scenario: A push with no-verify

- **WHEN** an agent runs `git push --no-verify origin main`
- **THEN** the user is asked before it runs

#### Scenario: An ordinary push

- **WHEN** an agent runs `git push origin feature/x`
- **THEN** no prompt about the pre-push guard is shown

#### Scenario: A push carrying the tag override

- **WHEN** an agent runs `ALLOW_TAG_REWRITE=1 git push origin :refs/tags/v1` or `$env:ALLOW_TAG_REWRITE='1'; git push origin v1`
- **THEN** the user is asked before it runs
