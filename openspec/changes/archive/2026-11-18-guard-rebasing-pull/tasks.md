# Tasks

## 1. Guard hook

- [x] 1.1 A pull that rebases asks when it would rewrite a pushed commit and is silent onto its own upstream, as a merge, or unchecked; tests marked `requirement: git-guards / A rebasing pull of pushed commits asks first` cover both ways and the settings.
- [x] 1.2 No command text reaches git as an option: revisions resolve through `rev-parse --end-of-options` to SHAs; tests assert no file is created or truncated for each quoted `--output=` repro.
- [x] 1.3 Add one mutant per changed hook line to the hook's mutation batch under `plugin-tests/mutants/hooks/`.

## 2. Docs

- [x] 2.1 docs and spec map: `.claude/plugins/cla/README.md`, `DEVELOPER-GUIDE.md` and `CHANGELOG.md` updated; root `CLAUDE.md`, `README.md` and `openspec/spec-map.md` none affected: they name no individual guard and the spec map already links git-guards.
