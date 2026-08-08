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

## Run `/cla:update-cla` inside `market-distiller-mcp` (must be run THERE, not from here)

Its plugin is several generations stale and, uniquely among the consumers, carries **no local
modifications at all** — so the sync is a pure fast-forward with nothing to reconcile. Measured
against current `main`: **93 pending — 18 files it does not have, 75 source-advanced, 0
local-advanced, 0 both-diverged.** That matches its own `cla-upstream.md`, which says its synced
core is byte-clean and should stay that way.

The gap that matters: it has no `skills/new-worktree/scripts/manual_worktree.py`, which `claw`
hard-depends on (`claw` exits 1 without it). That is why it has no `claw` at all — not a choice,
just a sync that predates the script. It is also missing `ask-destructive-git.py` and
`ask-git-identity.py`, so it currently has no force-push, `reset --hard`, or PR-merge
confirmation.

**Why this is not done from here.** `update-cla` is deliberately pull-based, and the skill's own
rationale says why: a prior push design "forced the source-side Claude to adapt blind, sampling
each target through thin slices — the result was mechanical copies." Running it from
`logic-artisan` against that repo would reproduce exactly the failure mode the design rejects,
across 93 files. Run it from inside `market-distiller-mcp`, where the adapting session has that
repo's own `CLAUDE.md` and conventions loaded.

**One manual step after, since the launchers now sync:** that repo will receive `cla`/`claw` for
the first time, and `apply.py` writes content but not file mode — so `git update-index --chmod=+x cla claw`
once, or `./claw` fails on any POSIX machine.

## Migration notes for consumers on the next `update-cla` sync

Two things a consuming repo needs to know when it pulls the current baseline. Both were once a
detection mechanism in `update-cla` (reverted — it warned spuriously on the commonest sync shape,
never fired for the consumers it existed for, and crashed on a malformed declaration). Handle them
by hand until something better is built.

**1. `warn-smoke-test-drift.py` needs a per-repo overlay or it silently does nothing.** It used to
hardcode one consumer's paths; it now reads them from `hooks/smoke-test-drift.local.md`, and an
absent overlay is a silent no-op. A repo that had the check working loses it on sync with no
warning. To restore the previous behaviour exactly, create that file with:

```
---
component_path_substring: src/components/
component_ext: .tsx
i18n_path_substring: src/i18n/
i18n_ext: .json
smoke_test_relpath: test-app.mjs
---
```

A `*.local.md` leaf is never synced or overwritten, so this survives future updates.

**2. Apply `hooks/` as a set, not file-by-file.** `block-worktree-path-escape.py` and
`guard-worktree-isolation.py` import `run_git`/`clone_paths` from `_dispatch_lib.py`; five hooks
import `GIT_GLOBAL_OPTS`/`strip_quoted_spans` from it as well. Applying an importer without a
compatible `_dispatch_lib.py` is an ImportError at hook load — the dispatcher reports it, so it is
audible rather than silent, but that guard does not run.

**If a detection mechanism is rebuilt**, it must: treat an asset already identical to source as
satisfied (not as "missing from the group"); check overlay presence against local state rather
than only when the asset is being rewritten (otherwise it never fires for already-synced repos —
the entire affected population); and tolerate any malformed declaration shape, since the file is
read from the source and one bad edit would break discovery for every consumer.

## `block-direct-push-to-main` — remaining non-coverage (was: known gaps)

Five shapes were listed here. **Three are now blocked**, each with a regression test and a
mutation check: `--all`/`--mirror`, `heads/main`, and `git.exe` (closed earlier by the
shared `GIT_CMD` constant).

**`--repo <remote> main` was NOT a gap** — the entry was wrong. Measured against real git:
`git push --repo origin main` fails with `'main' does not appear to be a git repository`,
because the first positional is always the repository and `--repo` only applies when none is
given. A rule written for it was added and reverted the same day: it blocked a shape git
refuses, un-blocked `git push --repo origin origin` (a real push of the default branch),
and false-positived on any repo with a remote named `main`. The lesson is the one the
reverted redesign already taught — a rule derived from reading the code rather than
exercising the tool it models.

**Two remain open, deliberately** — both evasion-shaped rather than reachable by ordinary use,
which is the distinction that justified fixing `git.exe` and not these:

| Shape | Why it stays open |
|---|---|
| `bash <<< '<push> origin main'` | the herestring body IS quoted, so `strip_quoted_spans` blanks it before matching. Un-blanking quoted spans after `<<<` adds parsing complexity to an *enforcing* guard for a vector nobody reaches by accident |
| `GIT push origin main` | command-name case, matching the `gh` precedent; pinned by a contract test so widening it is deliberate |

Still open, and unchanged: the `3.0` budget entry in `_dispatch_lib.HOOK_WORST_CASE_SECONDS` is
the realistic bound, not a proven ceiling — the branch cache is keyed on cwd, so several pushes
with distinct `-C` values each spawn a `rev-parse` (verified: three `-C` paths → 9s). The fix is
to make the hook resolve at most one branch per command, not to raise the handler timeout.

**If the 3-state (BLOCK/ALLOW/ASK) redesign is retried**, it was attempted and reverted — see the
revert commit for the full failure analysis. The short version: a `shlex`-based rewrite was
validated against a 44-command corpus containing **only push commands**, so it shipped six
regressions (`shlex` treats a newline as whitespace, collapsing multi-line commands into one
segment; shell grouping and wrapper prefixes like `sudo` also bypassed it) and six spurious
permission prompts (the ASK arm was gated on a hand-maintained subcommand list, so
`git rev-list main..HEAD` and friends began prompting). The corpus added alongside the four fixes
above is a starting point — it is deliberately half ALLOW cases, most of them non-push git
commands — but a retry still needs multi-line commands, shell grouping, wrapper prefixes, and
multiple heredocs before it ships.

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
