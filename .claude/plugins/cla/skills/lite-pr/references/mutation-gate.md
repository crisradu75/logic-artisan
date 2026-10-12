# Mutation gate for review fixes (moved from Review step 2b of SKILL.md; "step 3" is SKILL.md's Review step 3, the fix commit)

2b. **Mutation gate (required before the commit in step 3).** A fix for a Critical/Important
   finding is a change like any other and earns the same evidence the original code needed —
   "the reviewer's finding is now handled" is not that evidence. Break **what the fix
   touches**, not only what it targets: correcting one return path routinely breaks another, which
   is how a real fix here once traded a silent no-op on the default path for the identical no-op on
   the overlay path. Do each one by hand: edit the code so the defect is back, run the affected
   test, confirm it FAILS, then restore the edit exactly — a test that still passes has not been
   shown to catch anything, and an unrestored edit ships the defect. Stage the fix first (`git add
   <path>`), then restore each mutant with `git checkout -- <path>`. Unstaged, that checkout
   discards the fix along with the mutant, and so does `git stash`. Re-stage after every further
   edit to the fix, or the next restore reverts that edit. The `ask-destructive-git` hook prompts
   before this checkout, because the mutated file differs from the index. Unattended, take the
   other route. Back up the fixed file, before any mutant, to the session scratchpad. Copy it
   back after each mutant. Never put a backup anywhere else outside the checkout. A delegate
   briefed per `subagent-brief.md` follows that brief's own mutation route instead. It mutates a
   scratchpad copy, never the live file. Its result is not verified against the live tree. The
   orchestrator treats it as unverified and runs the mutant itself before committing. **A test that DOES fail is
   not thereby correct: read the assertion that killed the mutant and confirm it states the
   behaviour you want.** A test written from a wrong mental model kills mutants exactly as
   reliably as a right one, and the green result reads as confirmation. Worst where the mutant
   is the *simpler* form of the code: if the simpler form is right, the test defending the
   original is defending the bug. Full rule and the case that produced it:
   `${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/test-quality-gates.md`, "How planting goes wrong".
   Fix a surviving mutant, or name it in the final report with a reason. A clean
   run is evidence about the mutants you thought of and nothing else — two commits in this repo each
   recorded "three mutations checked, all caught" and each shipped a critical a later review found.
