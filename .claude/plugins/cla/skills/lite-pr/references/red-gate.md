# A red test gate: labelling, the one rerun, long logs (read when a test fails; "step 3" and "step 4" mean SKILL.md's Test phase)

Read this when a **test** fails, before spending step 3's one fix. It does not apply to a build or typecheck failure, which keeps step 3 as written.

## 1. The one rerun

When the log shows no failed assertion, no compiler error and no test error, and names an unreachable network or service (a refused connection, an unresolved host), rerun the failing check once with no edit. A timeout alone is no trigger. Do it at most once per run, before any label, and spend none of step 3's fix on it. Report it as a suspected flake. Green on the rerun: go on to Ship, and the `Checks:` line says so. Red again: the log is now the one step 3 reads, the one fix is still available, and no second rerun happens.

## 2. The label

Judge by reading alone: no extra test run, no stash, no second worktree, no checkout of another branch. A failing test, and every file its code reaches through other modules, whether or not the test names them, is read against the changed paths from step 1's `git status --porcelain`. When none of those files is in the change, label it `probably already failing on the base branch: <test>`. If the test, or code it reaches even through an untouched module, is a file the change added or edited, there is no label. Reading cannot see every path, so when unsure, leave it unlabelled. Make no edit to fix a labelled test.

## 3. When a failure is labelled

- **User present:** ask whether to open the pull request with `Known failing before this change: <test>, not fixed here` in its body. Yes: continue to Ship with that line in the body. No: treat the test as an unlabelled failure, so it gets the one fix, then the diagnose offer, then step 4's HALT.
- **Run by `/cla:multi-lite`:** halt without opening a pull request. The reason names the labelled test. An unattended run never ships a red gate.

With a labelled and an unlabelled failure in one run, the one fix goes to the unlabelled one first, then the ask or the halt for the labelled one. A labelled test is not sent to `/cla:diagnose`; a red rerun of the unlabelled one returns to the one fix and its normal escalation (`diagnose-escalation.md`).

## 4. A long log

Over 4,000 characters: read the first error and the final summary, not the whole log.
