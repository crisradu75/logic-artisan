# Tasks

Measurement-bearing tasks record the measured value inline on the ticked line — the tick is not the
evidence, the number is.

## 1. Author the six batches

Each batch lives at `plugin-tests/mutants/hooks/<same name as its guard>.py`, defines `MUTANTS`,
resolves paths from `Path(__file__).resolve().parents[N]`, anchors within a single line (CRLF
checkout), and targets the narrowest test file that could catch the mutation.

- [x] 1.1 `test_ask_destructive_git.py` — must include a mutant re-breaking `git branch -D`
      detection, which `test_guards_have_mutant_batches.py:54` records as proven nowhere.
- [x] 1.2 `test_log_commit_provenance.py` — must cover both gates from PR #204: the row-only-on-a-real-commit
      gate (`05355ff`) and the split-a-Bash-call-into-commands gate (`e805870`).
      Measured: 6 mutants after one was dropped as unkillable (task 3.2); gate 1 neuters
      `_head_moved_by_commit`, gate 2 reverts `_SEGMENTS`.
- [x] 1.3 `test_pre_push.py` — the no-push-to-main enforcement.
      Measured: 7 mutants, including the `refs/heads/maintenance` false-positive case. Hook is LF, not CRLF.
- [x] 1.4 `test_block_cd_in_bash.py` — must include the `shadows_cd` evasion detection.
      Measured: 7 mutants; both the no-space `cd(){...}` and `alias cd=` shadow forms covered.
- [x] 1.5 `test_block_unsafe_recursive_delete.py`
      Measured: 7 mutants, incl. the heredoc-prose regression (`rm -rf` inside a commit message).
- [x] 1.6 `test_block_worktree_path_escape.py`
      Measured: 7 mutants; #6 is the junction/symlink trap — `os.path.samestat` replaced by string
      equality, which passes every other test in the file.

**Three mutants were considered and deliberately left out**, each because it could not be killed —
a survivor nobody acts on trains the next reader to skip the list:

  - `block_cd_in_bash`: dropping `\n` from `cd_outside_quotes`'s separator class. The pattern
    carries `re.MULTILINE`, under which `^` already matches after every newline, so the two forms
    agree on every real input. Verified with a standalone `re` check.
  - `block_unsafe_recursive_delete`: dropping the `_is_link_like(str(resolved))` half of
    `_contains_symlink`'s guard clause. It only binds when the TARGET ITSELF is a link, which no
    assertion in the guard covers — a real coverage gap, recorded rather than papered over.
  - `block_worktree_path_escape`: the positive branch of the in-worktree check. The `worktree_pair`
    fixture places the worktree as a SIBLING of the primary clone, so every allowed target returns
    early via the repo-family check and nothing can reach that line with a True result.

## 2. Adopt the area in the guard

- [x] 2.1 Add the seven remaining `tests/hooks/` guards to `_PENDING_ADOPTION`, each with a stated
      reason: `test_dispatch.py`, `test_dispatch_lib.py`, `test_hooks_wiring.py`,
      `test_warn_heredoc_escape_mangling.py`, `test_warn_stacked_pr_merge.py`,
      `test_warn_stray_scratch_artifact.py`, `test_warn_wholesale_rewrite.py`.
      Measured: `len(_PENDING_ADOPTION)` = 10.
- [x] 2.2 Raise `_PENDING_ADOPTION_CEILING` 3 → 10 in the same commit, with a comment recording that
      the bound is global (3 annotate + 7 hooks) and that a raise is legal only here.
      Measured: ceiling = 10, entries = 10 — exactly at the bound, as the convention requires.
- [x] 2.3 Update the header comment that says `mutants/hooks/` does not exist and explains why the
      area came to have none — it becomes false with this change.

## 3. Verify each batch, serially

`mutate.py` rewrites files in place: run one batch at a time, with no agent reading the tree.

- [x] 3.1 Run all six batches. Record per batch: `<name> — N of N killed`.
      Measured: `ask_destructive_git 8/8`, `log_commit_provenance 6/6`, `pre_push 7/7`,
      `block_cd_in_bash 7/7`, `block_unsafe_recursive_delete 7/7`,
      `block_worktree_path_escape 7/7` — 42 mutants, all killed.
- [x] 3.2 For every mutant that SURVIVED, decide between fixing the guard and dropping the mutant
      with its reason recorded in the batch. Never leave an unkillable mutant in a batch.
      Measured — one survivor, dropped: `log_commit_provenance`'s "the shedding loop rewrites
      measured_by_count". It targets a real invariant but mutates a loop that **cannot execute
      under the current caps** — a realistic record is 1801 bytes against a 2048 ceiling, and
      reaching the ceiling needs ~250 chars of branch name, which git refuses (single-segment
      past ~100, and a 264-char multi-segment ref, both rejected). Two dead ends recorded so
      nobody repeats them: monkeypatching `_MAX_LINE_BYTES` does nothing because the hook runs as
      a separate process and reads the shipped constant; and the existing terminate-test
      re-implements the loop in its own body rather than calling the hook. The gap is kept as
      `test_the_shedding_loop_is_unreachable_under_the_current_caps`, which fails if the caps rise.
- [x] 3.3 Read the killing assertion for a sample of at least 2 mutants per batch and confirm it
      states the wanted behaviour. A kill proves the suite reacts, not that the test is right.
      Measured: `git branch -D feature/x` is asserted flagged across six spellings including
      `-Dr`, `git -C <path>`, and a line-continuation form; `refs/heads/maintenance` is asserted
      to return 0, pinning the exact-ref comparison against a substring match. Both state the
      wanted behaviour. Three mutants were rejected by their authors as unkillable BEFORE the run
      (recorded under task 1), which is the same judgement applied earlier.
- [x] 3.4 Confirm `git status --porcelain` shows no `.mutate-backup` and no unintended modification
      after every run — a batch restores byte-exactly, and a leftover means a run died mid-flight.
      Measured: no `.mutate-backup` residue; the only modified paths are the ones this change owns.

## 4. Gates

- [x] 4.1 `pytest plugin-tests/tests/consistency -q -n auto --dist loadfile` — the guard being
      changed lives here, and `test_every_batch_is_loadable_and_declares_real_targets` is what
      catches a bad anchor. Measured: 200 passed, 1 skipped in 24.70s.
- [x] 4.2 `pytest plugin-tests/tests/hooks -q -n auto --dist loadfile` — the area being adopted.
      Measured: 777 passed, 6 skipped in 72.91s (up from 776 — the one added test).
- [x] 4.3 Before the PR, each once: `pytest plugin-tests -q -n auto --dist loadfile` and
      `node --test plugin-tests/node/mechanical-checks.test.mjs`. Confirm the parallel run's pass
      AND skip counts match a serial run of the same tree.
      Measured: parallel 1577 passed / 14 skipped in 97.47s; serial 1577 passed / 14 skipped in
      216.22s — counts identical, which is the adoption rule's requirement; node 70 pass / 0 fail.
