# Tasks

## 1. Script

- [x] 1.1 Add `snapshot`: hash every protected path or record its absence, list the overlays, refuse an `--out` in the repo that git does not ignore or at a protected path, exit 2 outside a git repo. Tests marked `requirement: cla-setup / Setup checks that its protected files were left alone`.
- [x] 1.2 Add `verify`: each protected file changed, created or deleted, an approved change passing, an approval that does not cover a never-touched file, a file dirty before the run, a gitignored local file, and a missing or corrupt snapshot exiting 2. Same marker.
- [x] 1.3 Report an overlay or terminology file created as a problem whatever `--approved` says. Tests marked `requirement: cla-setup / Setup creates no overlay and no terminology file`.
- [x] 1.4 Break each comparison by hand once and confirm a test fails, then restore it.

## 2. Skill

- [x] 2.1 `cla-setup/SKILL.md` runs the snapshot before item 1 and `verify` after item 13, passes each yes-confirmed protected file as `--approved`, stops on exit 1 without calling the run clean, and says on exit 2 that the check could not run; ledger rows for each new rule; a test pins the order.

## 3. Docs

- [x] 3.1 docs and spec map: `DEVELOPER-GUIDE.md` (script table) and `CHANGELOG.md` updated; root `CLAUDE.md`, `README.md`, `.claude/plugins/cla/README.md` and `openspec/spec-map.md` none affected: none lists every script (the plugin README names only the checker a repo wires into its own gate, and this one runs inside the skill), and the spec map already links cla-setup.
