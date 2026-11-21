# Diagnose means: state a cause before editing, not pick a plausible edit

Read this from the Test phase, at the failing-gate step, before the one fix. The one-fix-then-one-retry budget stops you firing four changes at once, but it bounds *volume*, not reasoning: a single change made without a stated cause is still a guess, and it spends the whole retry budget. Before the `Edit`:

- **Name the cause in one sentence, specifically enough that the fix follows from it.** "The comparison is case-sensitive but the stored value is lower-cased by the column collation" is a cause. "There's a mismatch in the auth check" is a restatement of the symptom.
- **Read the actual failure output first.** The message usually names the file and line; a stack trace or an assertion diff is the diagnosis, not a hint toward one. Re-reading it beats inferring from the test's name.
- **Say what you expect the re-run to do, before running it.** If the fix is right the named check passes; if it isn't, you have eliminated a cause rather than guessed blind. A red retry goes to the `/cla:diagnose` escalation; a red re-run after `diagnose` goes to the HALT.
- **A fix that makes the check pass without explaining why it was failing is a symptom fix.** Loosening an assertion, widening a type, adding a try/except around the failing call, or bumping a timeout all turn the suite green without touching the defect. If the only account you can give is "this makes it more robust", treat the check as still failing, so it goes to the escalation or the halt, rather than shipping the suppression.

This is the same discipline `/cla:spec-to-pr`'s Revise phase applies to review findings (a finding is discharged only when the defect is *shown* gone), applied to test failures, where lite-pr has no downstream safety net to catch what a symptom fix hides.
