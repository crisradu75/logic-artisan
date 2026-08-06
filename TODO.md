# TODO

Deferred items — things intentionally not done now, kept here so they aren't lost.

## Add a `/diagnose` skill to CLA

Postponed mid-`shape-decision` on 2026-07-26. Ported idea from the peer repo `mattpocock/skills`
(idea #3 in the original comparison) — see
`cla.io/decisions/domain-terminology-glossary-2026-07-26.md` for the full comparison and for
sibling ideas #1 (adopted) and #2 (skipped, ADRs) from the same review.

**Confirmed gap, not yet shaped:** CLA has no disciplined bug-diagnosis loop today. `diagnose`
appears in `lite-pr`/`spec-to-pr` only as a bare, undefined verb ("any failure → diagnose ... via
Edit"), and `feedback`'s SKILL.md explicitly refuses the job ("never a confirmed diagnosis... it's
a capture skill, not a debugging one") with nothing downstream to hand off to.

**What the peer repo's version does** (would need shaping, not just porting, before landing in
CLA): a 6-phase discipline — (1) build a fast, deterministic, agent-runnable pass/fail feedback
loop first, trying strategies in priority order (failing test, curl/HTTP script, CLI diff,
headless-browser script, captured-trace replay, throwaway harness, fuzz loop, bisection harness,
differential loop, last-resort human-in-the-loop script) — stop and say so explicitly if no loop
can be built; (2) reproduce and confirm it's the actual reported bug; (3) generate 3–5 ranked,
*falsifiable* hypotheses before touching anything, shown to the user first; (4) instrument one
variable at a time, tagged debug logs (`[DEBUG-xxxx]`) for guaranteed cleanup, a separate
baseline-then-bisect branch for perf regressions; (5) write the regression test *before* the fix,
only at a genuinely correct seam — "no correct seam exists" is itself a finding, not a reason to
skip; (6) cleanup + post-mortem — confirm the original repro is gone, remove all debug tags, state
the confirmed hypothesis in the commit message, then ask what would have prevented this bug
(architectural answers hand off to `project-review`).

**Open questions when this gets picked back up** (was mid-Q1 of shaping when postponed):

- Standalone skill (peer repo's own positioning) vs. an escalation wired into `lite-pr`/
  `spec-to-pr`'s existing Test-phase failure handling vs. both (leading candidate — covers a
  bug reported with no PR in flight *and* a stubborn failure mid-build).
- Which lifecycle phase it belongs to in CLA's skill table (doesn't cleanly fit any of the
  existing five phases — possibly phase-agnostic like `right-model`).
- Whether/how a "no correct test seam" or "this needs an architectural fix" finding hands off to
  `project-review`, mirroring the peer repo's own end-of-loop hand-off.
- The bundled `scripts/hitl-loop.template.sh` (peer repo's last-resort human-in-the-loop driver)
  is bash; CLA's own convention is stdlib-only Python for bundled scripts — needs a port or a
  documented exception if adopted.

## Build `multi-lite-retro` / `multi-pr-retro` / `multi-spec-retro` / `project-review-retro`

Folded in from PR #7, which was closed in favour of this entry (it created `TODO.md` as a new
file and so conflicted once this one existed).

**The gap:** all four skills already log every run to `cla.io/retro/*-runs.jsonl` with a
documented schema, but none has an analyzer skill. Each schema doc states the same "log now,
build the retro once the sample justifies it" threshold that `spec-to-pr-retro` and
`codify-retro` were themselves held to before they existed.

**This repo will never produce the data, and that is expected — not a blocker.** `logic-artisan`
holds no product code, so it does not accumulate `multi-*`/`project-review` runs. `spec-to-pr-retro`
and `codify-retro` already exist here despite this repo's own ledgers being nearly empty; both
were authored as portable procedure and validated against a *consuming* repo's real log
(`cla.io/` is deliberately per-repo state and is never synced).

**Which means the data has to be gathered deliberately.** Check the consuming repos on the current
`.claude/plugins/cla/` + `cla.io/` layout before concluding the threshold hasn't been crossed —
older snapshots using the pre-extraction `.claude/skills/` + `.claude/retro/` layout predate
`multi-lite`/`multi-pr`/`multi-spec` entirely and carry no signal for them. Deliberately no
run-count snapshot is recorded here: PR #7 carried one and it was the first thing to go stale.
`project-review` is the weakest case — it had never logged a run anywhere checked.

**`update-cla` only flows source → consumer.** There is no reverse sync. A retro skill built while
working in a consuming repo has to be contributed back manually (copy the skill files, open a PR
against `logic-artisan`) before it becomes part of the canonical synced core.

**Related, already established:** the same "don't build it until the ledger justifies it" call was
re-tested for `codify-learnings` and held — the aggregator's own metrics said the current design
was working and the window was below its stated bar. The threshold discipline in this item is the
same one, applied earlier in the lifecycle.

## Make the symlink tests run on Windows (use an NTFS junction)

Three tests call `os.symlink(..., target_is_directory=True)` and `pytest.skip` when it raises —
which on Windows it always does for an unprivileged account (`WinError 1314`,
SeCreateSymbolicLinkPrivilege). So they skip on the platform whose path handling they exist to
check, and the suite still reports green:

- `hooks/tests/test_block_worktree_path_escape.py` — a worktree reached by an aliased spelling is
  still recognised as inside it
- `skills/new-worktree/tests/test_manual_worktree.py` (×2) — worktree path canonicalisation, and
  `casing_mismatch` detecting path indirection

**Solution is verified, not speculative.** An NTFS junction (`mklink /J`) needs no elevation,
`os.path.realpath` resolves it exactly like a symlink, and all three call sites only need a
*directory* alias. Confirmed on a real Windows box: `os.symlink` → `WinError 1314`, `mklink /J` →
rc 0, `realpath` resolves to the target, child paths reachable. (`os.path.islink()` is False for a
junction — irrelevant here since every caller goes through `realpath`, and it is exactly why
`block-unsafe-recursive-delete` does its own reparse-point check instead of trusting `islink`.)

**Shape:** a `make_dir_alias(target, link) -> bool` helper trying `os.symlink` then falling back to
`mklink /J`, in a `conftest.py` per scope. The two scopes cannot share a module (see
`run_tests.py`), so the copies would need adding to `consistency-checks`' `SIBLING_GROUPS` to stay
in lockstep.

## Adopt the Agent Brief durability discipline for `tasks.md` authoring

Postponed mid-`shape-decision` on 2026-07-26. Ported idea from the peer repo `mattpocock/skills`
(idea #4 in the original comparison, from its `triage/AGENT-BRIEF.md`) — see
`cla.io/decisions/domain-terminology-glossary-2026-07-26.md` for the full comparison and sibling
ideas #1 (adopted), #2 (skipped, ADRs), #3 (postponed, `/diagnose` skill, above).

**The idea:** write `tasks.md` subtasks as behavioral contracts, not directions to a specific
code location — describe *what* should be true ("the retry mechanism gives up after N attempts"),
never *where* to edit it ("line 42 of `anaf-client.ts`"). Pair with testable acceptance criteria
per subtask and an explicit out-of-scope list, so an implementing agent neither works from a
stale reference nor gold-plates adjacent work.

**Confirmed real gap, not speculative:** `multi-spec`'s own SKILL.md confirms the risk window is
real — its batch review runs once, right after all N proposals are authored ("a batch of exactly
one change skips the 3-agent dispatch... there's no cross-change staleness class to catch,"
implying multi-change batches do have one). `multi-pr` then implements each change later, one at
a time, in dependency order — so change #8 of 8 can sit authored-and-reviewed while #1–7 land
first, each potentially renaming files or shifting lines underneath #8's `tasks.md`.

**A real constraint already surfaced:** the tool that actually writes `tasks.md`
(`openspec-propose`/`openspec-apply-change`) is a vendored external skill, hard-excluded from CLA
edits by `codify-learnings`'s own rule ("never propose edits to... any vendored framework
directory"). So this can't be a change to the OpenSpec skill itself — it has to be guidance CLA
injects into its own orchestration around it: the authoring-agent prompt `multi-spec`/`spec-to-pr`
dispatch, and/or a new `review-change`/`fact-gatherer` check (which already does adjacent work —
verifying file/line claims against source — so flagging file-path/line-number references in
`tasks.md` would be a natural extension, not a new mechanism).

**Open questions when this gets picked back up** (was mid-Q1 of shaping when postponed):

- Enforce at authoring-time only (inject into the authoring-agent prompt), review-time only
  (extend `fact-gatherer`'s existing check), or both (leading candidate — mirrors the
  prevent-then-gate shape `multi-spec` already uses elsewhere: Phase 1 discipline + Phase 4 gate).
- Scope: apply universally to all `tasks.md` authoring (including single-change `spec-to-pr`/
  `lite-pr`, where the staleness window is usually short), or only where the risk is proven
  (`multi-spec`/`multi-pr` batch chains)?
- Which of the three sub-rules to adopt: just the anti-file-path/line-number rule, or the full
  three-part discipline (also testable acceptance criteria and explicit out-of-scope per subtask)?
