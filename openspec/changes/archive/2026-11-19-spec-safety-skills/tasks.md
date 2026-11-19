# Tasks

## 1. Skill fixes

- [x] 1.1 `/cla:save-permissions`: its merge script creates a missing `permissions` or `allow` key and replaces the file in one step. Regression test: the extracted script keeps other settings, and an invalid file stays byte-identical.
- [x] 1.2 `/cla:report-upstream` holds a tool to write the issue body file it asks for. Regression test: its allowed tools include `Write`.
- [x] 1.3 `/cla:save-permissions`: both forms stop before writing on invalid JSON or a `permissions`/`allow` of the wrong type, and remove the temp file if the replace fails. Test: the extracted script on each case; the PowerShell form checked statically.

## 2. Tests

- [x] 2.1 Test `worktree-setup / A new worktree is ready to work in`: the skill enters, installs, copies env files, reports path, branch and base, and skips a missing env file without failing.
- [x] 2.2 Test `worktree-setup / Inside a worktree only setup runs` and `Work stays inside the worktree`: the skill's text states setup-only, no second worktree, worktree-relative paths and the manual-worktree notice.
- [x] 2.3 Test `worktree-setup / A casing refusal falls back without deleting anyone's files`: the fallback script's existing tests carry the marker; the text forbids renaming the repo.
- [x] 2.3a Test `worktree-setup / The fallback keeps a worktree inside the repo`: the fallback's existing name and folder validation tests carry the marker, plus a CLI test that a climbing name creates nothing.
- [x] 2.4 Test `worktree-setup / Removing a worktree lists what it would delete`: the skill and the cleanup reference list untracked and ignored files first.
- [x] 2.5 Test the five `upstream-reports` requirements: the skill text carries the admission test, the read-this-run rule, the manifest target, the duplicate handling, and the body-file issue ending in its URL.
- [x] 2.6 Test the three `permission-saving` requirements: the extracted script on temporary settings files, plus the skill's wildcard-confirmation text.

## 3. Docs

- [x] 3.1 docs and spec map: `openspec/spec-map.md` (the three specs linked from workflow steps); `CHANGELOG.md`, `README.md`, `DEVELOPER-GUIDE.md` and `.claude/plugins/cla/README.md` left to the orchestrator's PR; root `CLAUDE.md` none affected: it names no spec.
