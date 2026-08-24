# TODO

Deferred items — things intentionally not done now, kept here so they aren't lost.

## Build the `/cla:diagnose` skill (shaped, ready to implement)

**Shaped 2026-08-14** — all four open questions resolved. The design constraints lived in
`cla.io/decisions/diagnose-skill-2026-08-14.md`, deleted 2026-08-24 in a decisions-directory
cleanup. Recover it first — `git show eaa579b:cla.io/decisions/diagnose-skill-2026-08-14.md` — and
read that, not this entry, before building.

In one line each: a standalone skill PLUS a thin escalation hook in both Test phases; the trigger
is two rounds on the same stated cause with the gate still red; it sits in the "Any phase
(utility)" row; the hypothesis gate is interactive standalone and autonomous-but-logged when
escalated; no bundled HITL script (the strategy list is prose); "no correct seam" findings go to
`cla.io/feedback/` pointing at `/cla:shape-decision`; `[DEBUG-xxxx]` cleanup is a zero-hit grep
plus a line in Ship's pre-staging hygiene scan.

`lite-pr`'s half of the escalation already landed (its Test step now states a cause and offers
`/cla:diagnose` on same-cause repetition). What remains: the skill itself, the `spec-to-pr` Test
hook, and the Ship hygiene line. Natural next step: `/cla:spec-to-pr`.

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

## Source-repo-only scopes — closed, the mechanism has no subject

**Closed by `extract-dev-tree-from-plugin`, not by being done.** Source-repo-only became
*structural*: the whole dev tree now lives at `<repo>/plugin-tests/` and never ships, so every
asset in it is source-repo-only by construction and there is nothing left to mark or skip. The
three `SOURCE-REPO-ONLY.md` files, the guard that pinned them, and the runner's skip logic were
all deleted together — the decision this entry recorded is moot rather than discharged.

The cost it recorded — a directory-granular skip losing 78 of 103 portable assertions in a
consuming repo — describes a skip that no longer exists. See the entry below for what became of
the follow-up it proposed.

## Remaining unscanned surface (small, known)

`SOURCE_SCAN_ROOTS` covers `skills`, `agents`, `hooks`, `output-styles`, `lib` — **five roots, down
from eight**, since the three `*-checks/` scopes left the plugin with the dev tree. Re-measured
against the shipped tree rather than adjusted by arithmetic (`git ls-files .claude/plugins/cla`
against both scanners' own file iterators): **101 files ship, 96 are reached by at least one
scanner, 5 by none.**

Two of the five are prose a scanner would otherwise read, and are watched by hand:

- The plugin's own root `README.md`, whose install commands legitimately name this repository.
  Scanning it would flag the one file whose job is to identify the source.
- `skills/_shared/README.md`, which sits directly under a skills subdirectory rather than beneath a
  `references/` ancestor, so the token scanners' rule does not reach it. (The hardcoded-path
  scanner does cover it — `.md` under `skills/`.)

`run_tests.py` and `mutate.py` used to be the third and fourth. The first is deleted and the second
moved to the dev tree, so neither ships and neither is a gap any more.

The other three are not prose at all: `.claude-plugin/plugin.json` and `.gitattributes` sit outside
every scan root, and `hooks/git/pre-push` is covered below.

None is a leak today. Revisit if a third prose file appears, or if one of these grows
repo-specific content.

Separately, TWO shipped files sit inside a scan root and are outside **both** scanner families:
`hooks/probe-python.sh` and `hooks/git/pre-push`. The two rules do not have the same reach, and an
earlier version of this paragraph got that wrong in a way worth recording, because the
counterexample was a comment in the scanner itself — and the same error was made again, in the
opposite direction, while reconciling these docs for `extract-dev-tree-from-plugin`:

- `plugin-tests/tests/conformance/test_no_hardcoded_plugin_paths.py` scans `.md`/`.py`/`.mjs`/`.json`
  under five roots including `hooks/`. So `hooks.json` and a skill's `.mjs` **are** covered — this
  paragraph once claimed they were not, and a later edit briefly claimed it again.
- `check_no_project_tokens.py`'s own scanners really are `.py`/`.md` only.
- `hooks/git/pre-push` has NO suffix, so the suffix-keyed rule skips it as surely as `.sh`. It was
  never named here; the count above is the first measurement that caught it.

Neither reaches `.sh`. Adding it would be the scanner's **fifth** suffix, not its third. Nor would
either rule flag what is actually in the file: the hardcoded-path rule looks for the literal
`.claude/plugins/cla`, and the developer-path rule looks for `C:\Users\<name>`-shaped paths. The
absolute install paths in `probe-python.sh` (`$HOME/AppData/...`, `/usr/local/bin/...`) are generic
and match neither pattern, so there is nothing to flag today.

## Why the push-to-main guard is a git hook, not a PreToolUse hook

Kept as a one-paragraph note because the question recurs. A PreToolUse hook has to parse a command
string, and every spelling it does not anticipate is a hole: `--all`, `--mirror`, `heads/main`,
`git.exe`, a here-string, a quoted remote. Several were closed one at a time and the list never
felt finished. `hooks/git/pre-push` sees the refspec git has already resolved, so there is no
string left to evade — and it also covers pushes from a terminal or an IDE, which no PreToolUse
hook ever saw. The cost is that git hooks cannot be installed by a plugin, so every clone runs the
`cp` line once (see the plugin README's guardrails section).

## Adopt the Agent Brief durability discipline for `tasks.md` authoring

Postponed mid-`shape-decision` on 2026-07-26. Ported idea from the peer repo `mattpocock/skills`
(idea #4 in the original comparison, from its `triage/AGENT-BRIEF.md`) — see
`cla.io/decisions/domain-terminology-glossary-2026-07-26.md` for the full comparison and sibling
ideas #1 (adopted), #2 (skipped, ADRs), #3 (postponed, `/diagnose` skill, above). That doc was
deleted 2026-08-24; recover it with
`git show eaa579b:cla.io/decisions/domain-terminology-glossary-2026-07-26.md`.

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

## Report the stale `TodoWrite` reference upstream to OpenSpec

`openspec-propose`'s SKILL.md instructs the model to use the `TodoWrite` tool, which does not exist
in this harness (it is `TaskCreate`/`TaskUpdate`). It is a vendored skill, so CLA must not edit it —
file it against OpenSpec instead. Observed 2026-08-14 during a real `spec-to-pr` run.

## Deferred candidates from the mattpocock/skills comparison (2026-08-14)

Third contact with that repo. Adopted this round: the skill-authoring doctrine move + completion
criteria, the conflict-resolution procedure, the two test-quality rules, the deletion test and
earned-seam rule. Still open, in rough priority:

- **Session-handoff compaction** — a way to compact a session into a briefing for the next one.
  Real but narrow gap; CLA's own `handoff.md` is spec-to-pr's terminal report, a different artifact.
  Revisit after `/diagnose`.
- **Invocation-model labels** (user-invoked vs model-invoked) in the skills table — adopt the
  label as documentation; reject the accompanying "user-invoked skills never call each other" rule,
  which CLA's orchestrators deliberately violate.

Deliberately rejected, recorded so they do not resurface: a router skill over 19 skills (CLAUDE.md's
lifecycle table plus descriptions already route); the avoid-negation authoring rule (it contradicts
~470 load-bearing "do NOT" constructions — CLA's guardrail idiom IS prohibition); ADRs (rejected at
first contact, unchanged); research-as-procedure (user memory already carries it); and the interview
primitive extraction — measured overlap between `shape-decision` and `feedback` is two sentences of
principle, below the shared-reference bar.

## Write mutant batches for the 8 grandfathered guards

`plugin-tests/tests/consistency/test_guards_have_mutant_batches.py` requires every guard in the
`conformance` and `consistency` areas to ship a same-named batch under `mutants/<area>/`, so a new
guard cannot land unproven. Eight predate the convention and are listed individually in that file's
`_EXEMPT` map — countable debt, not a softened rule. The count here and the bound in
`test_the_grandfather_list_only_shrinks` both move down when an entry is deleted; nothing in the
suite reads this file, so that pairing is a convention rather than a check.

**The count shrank without anyone writing a batch, and the reason matters:** it was twelve when
this entry was written and ten after `decouple-skills-from-dev-assets` (which brought two batches
with it); `extract-dev-tree-from-plugin` then deleted `test_runner_stream_encoding` along with the
runner it tested. A guard that disappears pays no debt — it just stops existing.

Four batches exist and kill everything they fire at (`test_skill_lint`, `test_doc_facts`,
`test_no_project_tokens`, `test_project_facts_paths`); `test_source_only_markers`' batch was deleted
with its guard.

Delete an `_EXEMPT` line the moment its batch lands. A companion test caps the list at its
original size, so it can only shrink. Highest value first: `test_check_script_drift` — CLAUDE.md
names it as guarding a *silent* failure, which is exactly the class where an unproven guard is
worth least.
