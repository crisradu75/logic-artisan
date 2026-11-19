# Tasks

## 1. Guard hook

- [x] 1.1 A wrapped force-push, hard reset, forced delete, merge or skipped pre-push asks as its bare form does, and a wrapped harmless command stays silent; tests marked `requirement: git-guards / A destructive git command run through a shell wrapper asks first` cover both ways.
- [x] 1.2 A subcommand or push/reset/branch option from a literal assignment reads as the literal, an unresolved one asks, and a branch name from a variable stays silent; tests marked `requirement: git-guards / A git subcommand or flag from an unresolved expansion asks first` cover all three.
- [x] 1.3 Add one mutant per changed hook line to the hook's mutation batch under `plugin-tests/mutants/hooks/`.

## 2. Dispatch plumbing (no spec change)

- [x] 2.1 `Deadline` measures from the probe's `CLA_HOOK_T0` stamp and falls back to the fixed reserve when it is unusable; tests cover a fresh, comma, stale, future and garbage stamp.
- [x] 2.2 The Copilot adapter denies on the dispatchers' `GUARD_NOT_RUN` flag, not on message words; tests cover a reworded failure ask and a dispatcher without the flag.
- [x] 2.3 Both dispatchers use one shared ask reader; a test fails if either carries its own copy.

## 3. Docs

- [x] 3.1 docs and spec map: none affected in this change: `.claude/plugins/cla/README.md`, `DEVELOPER-GUIDE.md`, `README.md` and `CHANGELOG.md` are edited by an open pull request and get their lines from it; `openspec/spec-map.md` already links git-guards.
