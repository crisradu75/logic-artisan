# Tasks

## 1. Guard hook

- [x] 1.1 Add `guard-bash-text`: a literal `${CLAUDE_PLUGIN_ROOT}/` or `$CLAUDE_PLUGIN_ROOT/` the shell would expand blocks; single quotes, `\$`, a quoted heredoc, a comment, a bare variable and a command that sets it stay silent; tests marked `requirement: guard-hooks / An unresolved plugin root in a command is blocked` cover each.
- [x] 1.2 A redirect, `tee`, `mkdir`, or `cp`/`mv` destination whose path starts with `..` and resolves outside the checkout asks; `cd ..`, a `..` argument, a source operand and a `..` that stays in the checkout are silent; tests marked `requirement: guard-hooks / A write outside the checkout through .. asks first`.
- [x] 1.3 A multi-line `git commit -m` or `gh pr|issue … --body` warns; single-line and repeated `-m` values are silent; tests marked `requirement: guard-warnings / A multi-line inline commit message or pull request body warns`.
- [x] 1.4 The command is found behind global options, chains, subshells, `env`/`command`/`sudo` and quoting; malformed input fails open; a 500,000-character hostile command stays fast.
- [x] 1.5 Run it from the Bash dispatcher as an enforcing hook at no budget cost; dispatcher, wiring and Copilot tests cover the block, the ask and the warning.
- [x] 1.6 No mutation batch (owner rule: lean). Each decision line was broken by hand once and a test failed: the block gate, its exit code, the `..` escape test, the ask branch and its decision value, the warning branch, and the unterminated-input guard; each restored.

## 2. Docs

- [x] 2.1 `.claude/plugins/cla/README.md`, `DEVELOPER-GUIDE.md`, `CHANGELOG.md` and the rule ledger's origin fields updated; root `CLAUDE.md`, `README.md` and `openspec/spec-map.md` none affected: they name no individual guard and the spec map already links both specs.
