# Spec Delta

## ADDED Requirements

### Requirement: A multi-line inline commit message or pull request body warns

The guard hooks SHALL warn, without blocking, when a `git commit` message or a `gh pr` or `gh issue` `create`, `edit`, `comment` or `review` body passed on the command line holds a real newline or a `$(cat <<...)` heredoc, and SHALL point at a message file.

#### Scenario: A heredoc commit message

- **WHEN** an agent runs `git commit -m "$(cat <<'EOF' ... EOF)"` with a multi-line message
- **THEN** the commit goes ahead with a warning to write the message to a file and pass `git commit -F`

#### Scenario: A single-line message

- **WHEN** an agent runs `git commit -m "fix: one line"`
- **THEN** no warning is shown
