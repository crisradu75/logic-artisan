## Why

None of the 13 guard modules in `plugin-tests/tests/hooks/` has ever had a mutant written for it, so
no hook guard has been shown able to fail. `test_guards_have_mutant_batches.py` derives its policed
set from the subdirectories present under `mutants/`, which means `hooks` is unpoliced *precisely
because* it is empty — the mechanism discouraged the behaviour it exists to encourage. Creating the
directory for one guard demanded a batch for all 13 at once, so the affordable move was to write
none.

That has already cost something concrete. `test_guards_have_mutant_batches.py:54` records that the
area was adopted once and lost: deleting its one batch took `_guard_files()` from 30 to 17 with all
three assertions still green, and the batch proving `ask-destructive-git` catches `git branch -D`
now exists nowhere. `log_commit_provenance`'s two gates from PR #204 were verified by hand only.

`_PENDING_ADOPTION` was built to unblock exactly this case and has been unused since. Closes #207.

## What Changes

- Create `plugin-tests/mutants/hooks/` with mutant batches for **six** guards — every guard whose
  failure lets a destructive or prohibited action through: `test_block_cd_in_bash.py`,
  `test_block_unsafe_recursive_delete.py`, `test_block_worktree_path_escape.py`,
  `test_ask_destructive_git.py`, `test_pre_push.py`, `test_log_commit_provenance.py`.
- List the remaining **seven** in `_PENDING_ADOPTION` with a stated reason each: `test_dispatch.py`,
  `test_dispatch_lib.py`, `test_hooks_wiring.py`, `test_warn_heredoc_escape_mangling.py`,
  `test_warn_stacked_pr_merge.py`, `test_warn_stray_scratch_artifact.py`,
  `test_warn_wholesale_rewrite.py`.
- Raise `_PENDING_ADOPTION_CEILING` from **3 to 10** in the same commit, which is the only place
  that file permits the number to move up.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

(none — `skip_specs: true`)

The guard↔batch pairing convention this change acts under has **no requirement in
`openspec/specs/cla-plugin/spec.md`** — verified by grep for `pairing`, `guard.*batch`, `adoption`
and `grandfather`, which returns one unrelated line about sample-size preconditions. This change
adopts an area *under* that convention without altering it, adds no shipped asset, and changes no
behaviour a consuming repo can observe. Inventing a requirement to satisfy validation is what the
proposal template explicitly forbids.

## Impact

Dev tree only; nothing here ships to a consuming repo.

- **New:** `plugin-tests/mutants/hooks/` — six batch modules.
- **Modified:** `plugin-tests/tests/consistency/test_guards_have_mutant_batches.py` —
  `_PENDING_ADOPTION` gains 7 entries, `_PENDING_ADOPTION_CEILING` 3 → 10.
- **Read but not modified:** the six guards under `plugin-tests/tests/hooks/` and the hook sources
  under `.claude/plugins/cla/hooks/` that they exercise. A batch mutates the hook source or the
  guard; it never edits the guard's assertions.

**The ceiling figure corrects the decisions doc**, which said 3 → 7.
`test_adoption_debt_only_shrinks` asserts `len(_PENDING_ADOPTION) <= _PENDING_ADOPTION_CEILING`
**globally**, not per area, and the map already holds 3 annotate entries. 3 + 7 = 10.

## Out of scope

- The seven grandfathered guards in `_EXEMPT` (#176) — that is piece B and lands separately.
- Any change to the four scanners or their exemption maps.
- The remaining seven hook guards' batches, which this change deliberately files as counted debt
  rather than paying now.
