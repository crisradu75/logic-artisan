# Tasks

Measurement-bearing tasks record the measured value inline on the ticked line — the tick is not the
evidence, the number is.

## 1. Author the six batches

Each batch lives at `plugin-tests/mutants/hooks/<same name as its guard>.py`, defines `MUTANTS`,
resolves paths from `Path(__file__).resolve().parents[N]`, anchors within a single line (CRLF
checkout), and targets the narrowest test file that could catch the mutation.

- [x] 1.1 `test_ask_destructive_git.py` — must include a mutant re-breaking `git branch -D`
      detection, which `test_guards_have_mutant_batches.py:54` records as proven nowhere.
      Measured: 9 mutants. The ninth was added after review named `_holds_work`'s fail-closed
      arm as the highest-value capability the batch had missed — the decision that turns the
      whole working-tree-discard layer from shape-matching into a conditional probe.
- [x] 1.2 `test_log_commit_provenance.py` — must cover both gates from PR #204: the row-only-on-a-real-commit
      gate (`05355ff`) and the split-a-Bash-call-into-commands gate (`e805870`).
      Measured: 7 mutants (one was dropped as unkillable and restored after review — task 3.2);
      gate 1 neuters `_head_moved_by_commit`, gate 2 reverts `_SEGMENTS`.
- [x] 1.3 `test_pre_push.py` — the no-push-to-main enforcement.
      Measured: 7 mutants, including the `refs/heads/maintenance` false-positive case. Hook is LF, not CRLF.
- [x] 1.4 `test_block_cd_in_bash.py` — must include the `shadows_cd` evasion detection.
      Measured: 7 mutants; both the no-space `cd(){...}` and `alias cd=` shadow forms covered.
- [x] 1.5 `test_block_unsafe_recursive_delete.py`
      Measured: 7 mutants, incl. the heredoc-prose regression (`rm -rf` inside a commit message).
- [x] 1.6 `test_block_worktree_path_escape.py`
      Measured: 7 mutants; #6 is the junction/symlink trap — `os.path.samestat` replaced by string
      equality, which passes every other test in the file.

**Three mutants were considered and deliberately left out** as unkillable. Review checked all
three: two hold, and the third was the wrong diagnosis of a real defect.

  - **Holds.** `block_cd_in_bash`: dropping `\n` from `cd_outside_quotes`'s separator class. The
    pattern carries `re.MULTILINE`, under which `^` already matches after every newline, so the two
    forms agree on every real input. Verified with a standalone `re` check.
  - **Holds.** `block_worktree_path_escape`: the positive branch of the in-worktree check. The
    `worktree_pair` fixture places the worktree as a SIBLING of the primary clone, so every allowed
    target returns early via the repo-family check and nothing can reach that line with a True
    result.
  - **Wrong diagnosis — now issue #215.** `block_unsafe_recursive_delete`: dropping the
    `_is_link_like(str(resolved))` half of `_contains_symlink`'s guard clause. Recorded here as "a
    real coverage gap". It is not a coverage gap: the branch is **unreachable from the hook's only
    call site**, which always passes a `.resolve()`d path, and `resolve()` folds a junction away.
    Worse, the clause encodes the wrong intent — "target is itself a link → allow" is the git-bash
    recursion case — so a test covering it as written would pin the defect while reporting green.
    Review then measured the consequence: **`rm -rf <a junction>` is ALLOWED** while `rm -rf` on
    its parent is blocked, in a shipped blocking guard. Out of scope for this change (a hook
    behaviour fix needs its own tests and review), so it is filed as #215 rather than folded in.

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
      Measured, after the review fixes: `ask_destructive_git 9/9`, `log_commit_provenance 7/7`,
      `pre_push 7/7`, `block_cd_in_bash 7/7`, `block_unsafe_recursive_delete 7/7`,
      `block_worktree_path_escape 7/7` — 44 mutants, all killed. Two batches note in their
      docstrings that their count overstates DISTINCT capabilities by one (a duplicate kill
      set), so read them as 6 each: worktree #2/#5 and pre_push #2/#3.
- [x] 3.2 For every mutant that SURVIVED, decide between fixing the guard and dropping the mutant
      with its reason recorded in the batch. Never leave an unkillable mutant in a batch.
      Measured — one survivor. It was first dropped as unkillable **and that was wrong**; review
      caught it and it is now restored and killed.

      The survivor was `log_commit_provenance`'s "the shedding loop rewrites measured_by_count".
      The reasoning that dropped it: one fixture measured 1801 bytes against a 2048 ceiling, so
      the loop "cannot execute". That generalised a single measurement, then looked only for what
      SUPPORTED it (branch-name length limits) rather than what refutes it.

      The lever nothing considered is a byte/character confusion: `subject[:120]` slices
      CHARACTERS while `json.dumps(ensure_ascii=False)` writes UTF-8 BYTES, so a 120-character CJK
      subject contributes 360 bytes. Measured through the real hook: **1980 bytes, shed from 10
      values to 9.** A long branch name reaches it too, but its limit is a filesystem artefact
      (MAX_PATH here, 255 bytes per component on POSIX), so a branch-length fixture would mean
      something different in a consuming repo — the CJK subject is arithmetic and holds everywhere.

      Two dead ends recorded so nobody repeats them: monkeypatching `_MAX_LINE_BYTES` does nothing,
      because the hook runs as a separate process and reads the shipped constant; and
      `..._terminates_on_a_record_that_can_never_fit` re-implements the loop in its own body rather
      than calling the hook. The mutant is killed by the new
      `test_an_oversize_record_sheds_through_the_real_hook`.
- [x] 3.3 Read the killing assertion for a sample of at least 2 mutants per batch and confirm it
      states the wanted behaviour. A kill proves the suite reacts, not that the test is right.
      Measured: `git branch -D feature/x` is asserted flagged across six spellings including
      `-Dr`, `git -C <path>`, and a line-continuation form; `refs/heads/maintenance` is asserted
      to return 0, pinning the exact-ref comparison against a substring match. Both state the
      wanted behaviour. Three mutants were rejected by their authors as unkillable BEFORE the run
      (recorded under task 1), which is the same judgement applied earlier.
- [x] 3.4 Confirm `git status --porcelain` shows no `.mutate-backup` and no unintended modification
      after every run — a batch restores byte-exactly, and a leftover means a run died mid-flight.
      Measured: no `.mutate-backup` residue. The only paths this change leaves modified besides its
      own are the provenance hook's rows in `cla.io/retro/commit-provenance.jsonl`, which the hook
      appends for this branch's own commits and which land in a separate housekeeping PR.

## 4. Gates

- [x] 4.1 `pytest plugin-tests/tests/consistency -q -n auto --dist loadfile` — the guard being
      changed lives here, and `test_every_batch_is_loadable_and_declares_real_targets` is what
      catches a bad anchor. Measured: 200 passed, 1 skipped in 24.70s.
- [x] 4.2 `pytest plugin-tests/tests/hooks -q -n auto --dist loadfile` — the area being adopted.
      Measured: 777 passed, 6 skipped in 72.91s (up from 776 — the one added test).
- [x] 4.3 Before the PR, each once: `pytest plugin-tests -q -n auto --dist loadfile` and
      `node --test plugin-tests/node/mechanical-checks.test.mjs`. Confirm the parallel run's pass
      AND skip counts match a serial run of the same tree.
      Measured before review: parallel 1577 passed / 14 skipped in 97.47s; serial 1577 / 14 in
      216.22s — counts identical, which is the adoption rule's requirement.
      Measured after the review fixes: parallel 1578 passed / 14 skipped in 97.80s (one added
      test — the hatch-value one); node 70 pass / 0 fail.
