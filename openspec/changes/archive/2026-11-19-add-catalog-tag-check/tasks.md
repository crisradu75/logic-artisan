# Tasks

## 1. Script

- [x] 1.1 Add `check_catalog_tags.py`: exit 0 when every catalog ref is a tag on the remote, 1 naming each missing one (a local-only tag included), 2 on an unreadable catalog or unreachable remote. Tests marked `requirement: plugin-distribution / A catalog never names a missing tag` use a local bare remote.
- [x] 1.2 Break the missing-tag comparison and the unreachable-remote path by hand once each and confirm a test fails, then restore them.

## 2. Skill

- [x] 2.1 Run the script in `/release`'s Step 1 command block and as Step 4's postcondition, and report success only after it exits 0; a test pins both runs in fenced blocks.

## 3. Docs

- [x] 3.1 docs and spec map: `DEVELOPER-GUIDE.md` (layout tree and script table) and `CHANGELOG.md` lines handed to the orchestrator, whose parallel PR edits those files; root `CLAUDE.md`, `README.md`, `.claude/plugins/cla/README.md` and `openspec/spec-map.md` none affected: none names a release script, and the spec map already links plugin-distribution.
