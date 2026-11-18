# Tasks

## 1. Script

- [x] 1.1 Add `before-merge`: recorded head present; PR on the recorded branch, not a fork; base; state open; PR head, remote branch and local `HEAD` equal the recorded head; clean tree outside the run notes. Tests marked `requirement: change-chains / A chain checks a pull request's head before it merges it`, including `gh` missing or failing and a malformed row.
- [x] 1.2 Add `after-merge`: merged, queued or not confirmed. Tests marked `requirement: change-chains / A chain counts a merge only when the host reports it merged`.
- [x] 1.3 Add `fix-pushed`: a commit past the recorded head, a clean tree, the remote branch at `HEAD`. Tests marked `requirement: change-chains / A chain's own fix becomes the recorded head only once it is committed and pushed`.
- [x] 1.4 Add `resume`: open on the recorded head or merged passes; moved, unrecorded, closed, missing or foreign fails. Tests marked `requirement: change-chains / A resumed chain acts only on its own pull request at the recorded head`.
- [x] 1.5 Add `deps`: every dependency's row merged, with a merge commit the base holds. Tests marked `requirement: small-change-chains / A small change runs only after the changes it depends on merged`.
- [x] 1.6 Break each core comparison by hand once and confirm a test fails, then restore it.

## 2. Skills

- [x] 2.1 Replace the by-eye comparisons in chain-merge's "Record the head", pre-merge checks and merge confirmation, `multi-lite` steps 2, 3 and 7 and `multi-pr` steps 1, 4 and 5 with script calls, keeping each rule and the reaction to each exit code; update the rule ledger, the two reports' reason lists and the tests that pin the old prose.

## 3. Docs

- [x] 3.1 docs and spec map: `DEVELOPER-GUIDE.md` (script table), `CHANGELOG.md` and `TODO.md` updated; root `CLAUDE.md`, `README.md`, `.claude/plugins/cla/README.md` and `openspec/spec-map.md` none affected: none names an individual chain script, and the spec map already links both specs.
