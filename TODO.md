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

**Improvement flows one way: consumer → issue → release.** A retro skill built while working in a
consuming repo has to be contributed back deliberately (`/cla:report-upstream`, or copy the skill
files and open a PR against `logic-artisan`) before it becomes part of the canonical core.

**Related, already established:** the same "don't build it until the ledger justifies it" call was
re-tested for `codify-learnings` and held — the aggregator's own metrics said the current design
was working and the window was below its stated bar. The threshold discipline in this item is the
same one, applied earlier in the lifecycle.

## Consumer migration off the deleted `update-cla` file-sync

The `update-cla` engine and its `.cla-sync-lock.json` were deleted; the GitHub marketplace is the
only distribution route. A consuming repo still on file-sync migrates once:

```bash
claude plugin marketplace add crisradu75/logic-artisan
claude plugin install cla@cris-logic-artisan --scope project
```

Then delete its now-inert `.claude/plugins/cla/.cla-sync-lock.json`, and delete the in-repo
`.claude/plugins/cla/` copy if it kept one — an unreferenced copy is merely dead weight, but a repo
that also launches with `--plugin-dir` pointed at it ends up running two registrations of the same
skills, and nothing detects that.

Two things that used to be handled by the sync, now handled once at migration time:

**1. A per-repo overlay is required or a repo-tuned check silently does nothing.** Any hook or
skill reading a `*.local.md` overlay treats an absent overlay as a no-op. A repo that had such a
check working must author its overlay after installing; nothing warns.

**2. Improvements now flow one way, through releases.** A skill improved while working in a
consuming repo is reported with `/cla:report-upstream` (files an issue against this repo) and
returns in the next release. There is no reverse sync and no per-asset multi-sourcing.

**Known consumer still to migrate: `market-distiller-mcp`.** Last measured against `main` it was
93 files behind with zero local modifications, and it is missing `ask-destructive-git.py`, so it
currently has no force-push / `reset --hard` / PR-merge confirmation. Naming it here on purpose —
a migration nobody is named for is a migration that does not happen.

**If a drift-detection mechanism is ever rebuilt**, these three constraints killed the last
attempt and are worth keeping: treat an asset already identical to source as satisfied (not as
"missing from the group"); check overlay presence against local state rather than only when the
asset is being rewritten (otherwise it never fires for already-synced repos — the entire affected
population); and tolerate any malformed declaration shape, since one bad edit would otherwise
break discovery for every consumer.

## Shipped-but-source-only check scopes fail in a consuming repo

`consistency-checks/` and `launcher-checks/` sit inside `.claude/plugins/cla/`, so the marketplace
ships them, but their assertions are about THIS repo's own source: repo-root `cla`/`cla.cmd`
launchers, `>= 8` overlays, a curated token list, an installed `pre-push` hook. A consuming repo
that runs the shipped `run_tests.py` gets failures it cannot fix and did not cause.

Options, none chosen yet: move both scopes outside the published directory (they would stop being
distributed at all, which is the intent); make each assertion skip when it detects it is not the
source repo; or have `run_tests.py` discover a scope's "source-repo-only" marker and skip it. The
first is cleanest but conflicts with `conformance-checks/` deliberately shipping.

## Remaining unscanned surface after the scan-root widening (small, known)

`SOURCE_SCAN_ROOTS` now covers `skills`, `agents`, `hooks`, `output-styles`, `lib`, and the three
`*-checks/` scopes — everything the marketplace publishes except two deliberate omissions:

- The plugin's own root `README.md`, whose install commands legitimately name this repository.
  Scanning it would flag the one file whose job is to identify the source.
- `run_tests.py` and `mutate.py` at the tree root, which sit outside every scanned root. Adding a
  bare-file traversal for two files was judged not worth a second scan rule.

Neither is a leak today. Revisit only if a third root-level file appears.

## Why the push-to-main guard is a git hook, not a PreToolUse hook

Kept as a one-paragraph note because the question recurs. A PreToolUse hook has to parse a command
string, and every spelling it does not anticipate is a hole: `--all`, `--mirror`, `heads/main`,
`git.exe`, a here-string, a quoted remote. Several were closed one at a time and the list never
felt finished. `hooks/git/pre-push` sees the refspec git has already resolved, so there is no
string left to evade — and it also covers pushes from a terminal or an IDE, which no PreToolUse
hook ever saw. The cost is that git hooks cannot be installed by a plugin, so every clone runs the
`cp` line once (see the plugin README's guardrails section).

## ~~Make the symlink tests run on Windows (use an NTFS junction)~~ - DONE

Three tests called `os.symlink(..., target_is_directory=True)` and `pytest.skip` when it raised -
which on Windows it always does for an unprivileged account (`WinError 1314`). They skipped on the
one platform whose path handling they exist to check, and the suite still reported green.

Shipped as `make_dir_alias(link, real)`: symlink first, NTFS junction (`mklink /J`, no elevation
needed) as the Windows fallback, `pytest.skip` when neither works or the alias does not resolve.
It landed in each test file rather than a per-scope `conftest.py`, and the three copies are
registered in `consistency-checks`' `SIBLING_GROUPS` so they cannot drift.

Two residuals, both deliberate:
- The POSIX branch of that helper is unexercised here. It is gated on `os.name != "nt"`, so on
  this machine the gate itself is what a mutation test cannot kill - the same "only ever
  exercised where you are" limit `CLAUDE.md` records for every platform-divergent path.
- `os.path.islink()` is still False for a junction. Irrelevant to these callers, which all go
  through `realpath`, and exactly why `block-unsafe-recursive-delete` does its own reparse-point
  check instead of trusting `islink`.

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
