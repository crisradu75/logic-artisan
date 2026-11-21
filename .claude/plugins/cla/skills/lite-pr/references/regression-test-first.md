# Showing a new test fail before you trust it

Read this from Implement, when the change adds or changes a test. `SKILL.md` step 1 holds the bug-fix rule (the regression test comes before the fix, per `/cla:diagnose` Phase 5). This file holds the rest: why a new test needs to be seen failing, and what to do when reverting the fix is impractical.

A test written after the code passes whether the code is right or not. A test that never failed against the unfixed code is
evidence of nothing, so watch it go red first. Read the failure before accepting it: an import error, a
broken fixture, or an unrelated test in the same run is a failure of the *test*,
not proof the test can catch this defect.

**A bug-fix test written after the fix:** stash or revert the fix and watch the new test go red before you trust it.

Where reverting is impractical — a guard, a scanner, any check whose "feature" is
detecting something — get the same guarantee structurally instead, with a test
asserting the check can still fire at all (`test_the_outcome_detector_is_not_vacuous`,
`test_the_scanner_is_not_vacuous`). That is the stronger form: watching a test fail
is evidence at one moment, whereas a non-vacuity test keeps holding after a later
refactor quietly turns the check into a no-op. Prefer it for anything guard-shaped;
this repo has shipped a guard whose only test would have passed had the function
returned nothing at all.
