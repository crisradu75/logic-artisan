# Tasks

## 1. Script

- [x] 1.1 Add `preflight`: collisions by exact name locally, as a remote-tracking ref and on the remote; commits to lose in the rename case; the stacked parent's upstream on the remote; exit 2 when the remote does not answer. Tests marked `requirement: change-workflow / A new branch is checked for collisions before it is made`.
- [x] 1.2 Add `pushed`: branch, head against the remote, upstream set and equal; `push not verified` on the first line of every failure. Tests marked `requirement: change-workflow / A push is verified against the remote`, including a detached head and an unreachable remote.
- [x] 1.3 Add `trailers`: written `Measured-by:` lines against git's parsed trailers. Tests marked `requirement: change-workflow / Measurement trailers are checked before a push` cover a parsed block, a blank line, a bare line and no trailer.
- [x] 1.4 Break each subcommand's core comparison by hand once and confirm a test fails, then restore it.

## 2. Skills

- [x] 2.1 Replace the command lists in Ship's preflight, trailer and push checks, Revise's and Archive's push checks, lite-pr's trailer check, and the multi-spec and multi-lite push checks with one script call each, keeping each rule and the reaction to each exit code; update the rule ledger and the tests that pin the old prose.

## 3. Docs

- [x] 3.1 docs and spec map: `DEVELOPER-GUIDE.md` (script table) and `CHANGELOG.md` updated; root `CLAUDE.md`, `README.md`, `.claude/plugins/cla/README.md` and `openspec/spec-map.md` none affected: none names an individual ship script, and the spec map already links change-workflow.
