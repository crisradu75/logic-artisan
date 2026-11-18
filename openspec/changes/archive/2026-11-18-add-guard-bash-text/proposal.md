# Proposal

## Why

About six shipped rules govern the text of a shell command, and nothing enforces them (check 8 of
`cla.io/audits/rule-enforcement-2026-11-18.md`): `plugin-root.md` "never pass it through to a
shell" and the Copilot output style's "never run an unresolved placeholder"; bash-discipline's
"Never write to `..`, which in a consuming repo holds the user's other projects" and its forbidden
multi-line `--body` and heredoc-subshell commit; report-upstream's "never an inline multi-line
string". Claude Code does not export `CLAUDE_PLUGIN_ROOT` to the Bash tool's shell (its plugins
reference, "Where each variable resolves"), so a literal placeholder copied from a `references/`
file expands to nothing and the command runs against `/skills/...`.

## What Changes

- Add an enforcing guard hook, `guard-bash-text`, to the Bash/PowerShell dispatcher. It reads only
  the command text, in one linear pass that knows quotes, substitutions and heredocs, and runs no
  subprocess.
- It blocks a `${CLAUDE_PLUGIN_ROOT}/` or `$CLAUDE_PLUGIN_ROOT/` path the shell would expand. Single
  quotes, a `\$` escape, a quoted heredoc, a comment and a command that sets the variable stay silent.
- It asks before a write redirect, `tee`, `mkdir`, or a `cp`/`mv` destination whose path starts with
  `..` and resolves outside the checkout that holds the working directory.
- It warns when a `git commit -m` or `gh pr|issue create|edit|comment|review --body` value holds a
  real newline or a `$(cat <<...)` heredoc, pointing at `-F` / `--body-file`.
- Not checked: a PR-body temp file inside the repo. spec-to-pr deliberately passes an in-repo,
  gitignored `temp/` file to `--body-file`, so only "untracked and not ignored" would be a signal,
  and that needs git, which would make the hook best-effort.

## Capabilities

### Modified Capabilities

- `guard-hooks`: add requirements that an unresolved plugin root in a command is blocked and that a
  write outside the checkout through `..` asks first.
- `guard-warnings`: add a requirement that a multi-line inline commit message or PR body warns.

## Impact

The new hook file, the Bash dispatcher's hook list, the budget table in `_dispatch_lib.py`, tests
and a mutation batch under `plugin-tests/`, the guard tables in the plugin README and the developer
guide, and the rule ledger's origin fields. Copilot CLI picks the guard up through the same
dispatcher. No new dependency.
