## Context

`test_guards_have_mutant_batches.py` pairs each guard with a same-named batch under
`mutants/<area>/`, and derives the policed areas from the directories actually present. That
derivation is deliberate — a fixed tuple went silently unpoliced the moment a new area appeared —
but it has a consequence nobody priced: an area with no batches is not "not yet adopted", it is
**invisible**. `hooks` has been in that state since the convention landed.

`_PENDING_ADOPTION` exists to make adoption affordable, and has never been used. This change is its
first real exercise.

## Goals

- Every hook guard whose failure lets a destructive or prohibited action through has a batch.
- The rest become **counted, bounded debt** rather than invisible absence.
- The adoption is one reviewable commit, which is what the ceiling rule asks for.

## Non-goals

- Batches for the remaining seven. Writing thirteen at once is the cost that produced zero.
- Touching `_EXEMPT` (#176, piece B).

## Decisions

### D1 — Six batches, drawn on severity, not on count

The six are every **block** (`block_cd_in_bash`, `block_unsafe_recursive_delete`,
`block_worktree_path_escape`), the one **ask** (`ask_destructive_git`), plus `pre_push` and
`log_commit_provenance`.

The line is *what gets through if the guard is vacuous*. A broken block or ask lets a destructive
git operation, an unsafe recursive delete, a cross-worktree write, or a push to `main` proceed. A
broken warn prints nothing, and CLAUDE.md already records that warn output never reaches a
transcript — so a warn's batch is the only evidence it works, which is an argument for covering
them *eventually*, not for covering them ahead of the blocks.

`pre_push` earns its place because it is the sole thing preventing a push to the default branch in a
repo with no CI. `log_commit_provenance` earns its because PR #204 added two gates verified by hand.

**Rejected: all thirteen at once.** That is the cost that produced zero batches for the life of the
convention. Rejecting it is the whole point of `_PENDING_ADOPTION`.

**Rejected: two batches (`ask_destructive_git` + `log_commit_provenance`).** Cheapest, and it does
cover the two the issue names — but it leaves all three blocking guards unproven and parks a
ceiling of 12 that nothing pushes down.

### D2 — The ceiling goes to 10, not 7

`test_adoption_debt_only_shrinks` reads:

```python
assert len(_PENDING_ADOPTION) <= _PENDING_ADOPTION_CEILING
```

`_PENDING_ADOPTION` is one flat map across all areas, so the bound is **global**. It already holds
three `annotate` entries; seven more makes ten.

The decisions doc said 3 → 7, reasoning as though the ceiling were per-area. It is not. Recorded
here because the doc is the artifact a future reader will trust, and the code is the authority.

### D3 — Mutate the hook source, not the guard, wherever both are possible

A mutant against the guard's own assertions tests the guard's text. A mutant against the hook
re-creates the defect the guard exists to catch, which is the thing worth proving. CLAUDE.md's
converse rule still applies: where a guard's two candidate rules agree on every correct input,
mutate the *input* instead — a batch against `check_labels_agree` had to do exactly that.

### D4 — Batches are authored in parallel; `mutate.py` runs serially

The six batch files are independent, so authoring fans out. Running does not:
`mutate.py` edits real files in place, and CLAUDE.md records two reproductions of a concurrent run
corrupting another reader's view — one agent read a mutated source, another aborted on a leftover
`.mutate-backup`. Every batch is therefore run one at a time, by the orchestrator, after all
authoring is complete and with no agent reading the tree.

### D5 — No spec delta

The guard↔batch pairing convention has no requirement in `openspec/specs/cla-plugin/spec.md`
(grepped for `pairing`, `guard.*batch`, `adoption`, `grandfather` — one unrelated hit). This change
acts *under* the convention without changing it, adds no shipped asset, and alters nothing a
consuming repo can observe. `skip_specs: true`, rather than inventing a requirement to satisfy
validation.

## Risks

- **A batch whose mutants all die tells you less than it appears to.** A kill proves the suite
  reacts, not that the assertion is right. Each batch's mutants are read against the assertion that
  killed them before the run counts as evidence — worst where the mutant is the *simpler* form of
  the code, since if the simpler form is correct, the test defending the original defends a defect.
- **An unkillable mutant is worse than a missing one**, because a survivor nobody acts on trains the
  next reader to skip the list. Any mutant that cannot die is dropped with its reason recorded,
  which is what the `check_labels_agree` batch did with its floor constant.
- **Platform divergence.** Several hook guards branch on Windows vs POSIX, and three
  directory-alias tests take a junction path here and a symlink path elsewhere. A mutant whose only
  killer skips on this machine will survive here and mean nothing; those are dropped rather than
  banked.
- **Ceiling of 10 is a large standing debt.** It is bounded and visible, which is the trade this
  mechanism exists to make, but nothing forces it down. Piece B (#176) is the counterweight.
