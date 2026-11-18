# Tasks

## 1. Guard hook

- [x] 1.1 Add `ask-broad-git-add`: a broad `git add` asks when `git status` lists untracked files in its scope, and is silent otherwise; tests marked `requirement: git-guards / A broad git add that would stage untracked files asks first` cover each broad form both ways.
- [x] 1.2 Keep it best-effort and linear: silent outside a repository, without git, on a timeout or an error, and fast on a long hostile command; tests cover each.
- [x] 1.3 Run it from the Bash and PowerShell dispatcher as a best-effort hook, skipped under a spent budget and reported as context on a load failure; dispatcher and wiring tests cover the ask, the skip and the budget sum.
- [x] 1.4 Write a mutation batch for the hook's lines under `plugin-tests/mutants/hooks/`.

## 2. Docs

- [x] 2.1 docs and spec map: `.claude/plugins/cla/README.md`, `DEVELOPER-GUIDE.md` and `CHANGELOG.md` updated; root `CLAUDE.md`, `README.md` and `openspec/spec-map.md` none affected: they name no individual guard and the spec map already links git-guards.
