# Tasks

## 1. Guard hook

- [x] 1.1 A rebase that would rewrite a commit on a remote-tracking branch asks; local-only rebases, rebase actions and `git pull --rebase` are silent; tests marked `requirement: git-guards / A rebase of pushed commits asks first` cover both ways.
- [x] 1.2 `switch -C` / `checkout -B` over a branch with commits no other ref reaches asks; new branches and resets that orphan nothing are silent; tests marked `requirement: git-guards / A branch reset that would orphan commits asks first`.
- [x] 1.3 A merging switch asks only with staged changes; tests marked `requirement: git-guards / A merging branch change over staged work asks first` cover staged, unstaged and non-merging forms.
- [x] 1.4 The new probes fail open and spend only what the hook's existing probes left of its budget; tests pin the shrinking timeouts, a spent budget, the override and the construct matrix.
- [x] 1.5 Add one mutant per changed hook line to the hook's mutation batch under `plugin-tests/mutants/hooks/`.

## 2. Docs

- [x] 2.1 docs and spec map: `.claude/plugins/cla/README.md`, `DEVELOPER-GUIDE.md` and `CHANGELOG.md` updated; root `CLAUDE.md`, `README.md` and `openspec/spec-map.md` none affected: they name no individual guard and the spec map already links git-guards.
