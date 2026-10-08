# Design trade-offs and rationale behind `/cla:spec-to-pr`

Why the skill's rules are shaped as they are. **Not read during a run** — read it when revising the skill, and before deleting a rule that looks redundant. Dated, repo-specific incidents live in the consuming repo's `cla.io/overlays/spec-to-pr.md` "Incident / offense history"; the enforcement-tier vocabulary in `${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/past-offenses.md`.

## Shape of the skill

**Phase stubs carry only gate rules; each phase reads its reference first** (2026-10-08, the plugin-surface simplification's P1). `SKILL.md` had grown to restate every mandatory reference (about 2,600 duplicated words), so each rule had two copies to keep in step and a run read both. A stub now keeps only the rules whose loss is silent and expensive — git state, staging scope, the exit gate, the merge gating, turn liveness, the `<inherits>` resume — and rationale lives here.

**No `Skill()` hops.** `Skill(pr-review-toolkit:review-pr)` is itself a dispatcher of the same agents; `Skill(commit-commands:commit-push-pr)` re-prompted with the diff and asked for the same four shell commands; `Skill(openspec-archive-change)` wraps one CLI call. Each cost a turn or two of indirection for no capability. `Skill(openspec-apply-change)` is the exception: it carries real workflow logic (walk tasks.md, locate the module, edit, tick, re-validate). Inline instead when you already hold the artifacts and source, or need side knowledge the skill lacks — judgment, not a subtask count. Use `Skill()` only for capability the orchestrator lacks.

**No `TaskCreate` for phases or a linear tasks.md walk.** Phase outcomes live in context and surface in the Handoff report; tasks.md checkboxes are the task list. It earns its place only for parallel, externally gated or cross-session sub-work. The harness's nudges are generic; the skill's rule wins.

**Session-model routing.** Inline judgment (Propose authoring, the Review verdict, Revise triage) runs at the session model, which the skill cannot change. On a sub-Opus session the two highest-leverage moments escalate to an `opus` Agent; on Opus that is a no-op. Full table: `model-routing.md`.

**`<base-branch>` is resolved, never assumed.** The harness once hardcoded `master`, which broke every `main`-default repo: `master..HEAD` fails with `unknown revision`, and `git checkout master` cannot succeed.

**`<inherits>`** — GitHub issues #98, #100, #102: one chain in which three consecutive changes dropped the same obligation, each internally consistent and silently wrong. Carrying the obligation into the dependent's own Review is the mechanism; the chain's note of it is not — a note nobody re-reads at the right moment is no note, and the right moment is that change's Review, not its Implement. Its resume rule exists because `probe_state.py` has no review state.

## Continue-on-everything

The orchestrator never halts on a sub-step failure; each becomes a `warn` phase and an Issues line. **Accepted:** a failing `openspec validate` propagates and may yield a PR built on broken artifacts. The user is the safety net, and the report and PR-body callouts make that net usable. The owner chose this policy. `/cla:lite-pr` halts on an unresolved test failure instead; that difference is deliberate.

## Layer-1 wildcard permissions

`Bash(git *)`, `Bash(python *)` and the like trust every invocation. **Accepted:** broader than per-subcommand allowlisting; `required-permissions-narrow.json` exists for stricter users. The default is wide because the user already trusts the orchestrator with autonomous push and PR-open.

## Autonomy gate and turn liveness

A phase-boundary confirmation prompt is a regression against the documented contract; past sessions lost ~5 minutes per pause to model-side gating nothing authorized. "Merge and clean" was once over-read as "skip review"; it is about cleanup after Archive.

**Turn liveness is a check, not a prohibition.** The prohibition asks you to notice mid-flow that what you are writing *reads* as an ending — a judgement, and a real chain lost a round-trip to it: the author wrote the banned shape and then behaved like its reader. "Is there a tool call in this message?" needs no judgement. Incident: the overlay, 2026-08-23.

## Implement

- Post-check: issue #111 records three ticked tasks in one chain that asserted false things — including a mutation test that could not have failed — with every mechanical check passing. The box count is a presence check on a glyph; the artifact-ready flag does not read task state at all. Briefs that demanded numbers are the ones that came back with real ones, hence the inline `measured:` value; a sample re-measure, not exhaustive re-verification, because that would cost as much as the implementation.
- A ticked box with "NOT DONE" beneath it is honest work filed dishonestly, and makes every downstream count wrong.
- A mechanical scan for ticked-but-open tasks was built and withdrawn: over this repo it reached 6 of 173 ticked tasks with 0 true positives against 4 false (issue #105).

## Test

- **The source-affecting suffix list is illustrative.** `.py` was once missing, and in a Python repo a real source change did not register as source-affecting: the run reported a clean docs-only skip having gated nothing. A closed list reproduces that for every language it omits.
- **No commands is `warn`, not `skip`**, because a skip announces a source change as docs-only and runs no gate, with a reason plausible enough that nobody questions it — worse than a missing gate.
- **State a cause before editing:** the round budget bounds attempts, not how well-reasoned each is, and an edit without a stated cause spends a round either way. Two rounds on one cause means the hypothesis is wrong; a third edit against it spends the last round to learn nothing, so `/cla:diagnose` builds a deterministic pass/fail loop and ranks falsifiable hypotheses first. The escalation is counted where it happens because Handoff, at the end of a long run, would rebuild it from memory.
- **Symptom fixes** turn the gate green without touching the defect, and because Test warns and continues, a suppression ships and Revise never sees it.

## Review

- **Sweeps:** a real sweep once returned a silent false-negative over an entire skills tree (`Scanned: 0` on a surface); another reported `No stale references found.` with `Scanned: 121` and `Unresolved: none` while a direct search found 9 hits (GitHub issue #279). Hence the footer check and the zero-count re-search. A stale doc reference can mask a broken key contract in a repo's load-bearing conventions (the overlay names them).

## Ship

Ship runs path-scoped `git add`, `git commit -m "feat: <change-name>"`, `git push`, and a one-line `gh pr create`. **Accepted:** minimal commit subjects and PR bodies — the proposal is the why, the diff the what; commit and PR text are markers. Fit for a single-developer project; with multiple reviewers, replace the one-line body with a `--body-file` build-up. Earlier versions delegated to `commit-commands:commit-push-pr`, which generated verbose text nobody read and cost turns.

**`Measured-by:` trailers are discharged at the commit** because that is where claims are assembled into a message; a rule firing at the keyboard fires hundreds of tool calls before the claim is written, and by the commit it already reads as settled. Standing gates earn no trailer: a block identical on every commit stops being read. Trailers make the corpus queryable — `git log --grep='^Measured-by:'`.

**Why the parse check compares two counts.** `%(trailers:...)` returning nothing looks the same for a broken block and for a commit that rightly carries none. Measured on a controlled pair, three `Measured-by:` lines, once well-formed and once with a blank line before the attribution lines:

| | written | `%(trailers:…)` | `--grep '^Measured-by:'` |
|---|---|---|---|
| well-formed | 3 | 3 | finds it |
| blank line before attribution | 3 | **0** | finds it |

It broke once at fleet scale: a counter built on the parser read 59 of 228 measurements where the messages held 133, and one repo logged 0.0 against a real 0.67.

## Revise

**Fix-round commits stay manual.** `fix: review round N` drives `probe_state.py`'s round counter and round N's diff scoping; a generated subject would break both.

**Round 1 is one `Workflow` fan-out; round ≥2 is direct `Agent`.** `Workflow`'s `agent()` gives per-call effort (opus bug-hunters at `medium`) and schema-forced findings, and the merge runs in code. **Accepted:** a second orchestration mechanism with quieter failures (a crashed reviewer is a `null`), mitigated by the completeness check and the fallback. Round ≥2's one or two scoped dispatches do not repay the script overhead. **Not size-gated:** over a 7-change `multi-pr` run the first 3 changes avoided `Workflow` citing diff size, the last 4 used it cleanly on similar diffs; the variable was how the diff reached the agent. Described, the script carries no diff text; pasted, even a small diff corrupts the template literal. A missing `Workflow` tool is `ok`, not `warn`, because a capability gap is not a run defect, and warning on it would flood the retro's warn-reason signal on every Workflow-less harness.

**Never-demoted bug-hunters.** A cheaper bug-hunter emits more phantom findings, whose triage costs more than the saving, in every round; a prose-promoted `skill-reviewer` sits in the bug-hunter's position on a markdown-behaviour diff. `routing.revise_findings_by_tier` is keyed per agent, so a demoted agent's phantom rate shows against its own name in `/cla:spec-to-pr-retro` — the signal that polices the rule. A body-only prose edit leaves triggering behaviour unchanged, which is why the frontmatter row excludes it. A signal-empty agent on the ambiguous row is by design, not a cost omission.

**Tight `type-design-analyzer` / `comment-analyzer` triggers.** Across a measured multi-change `multi-pr` run, the two opus bug-hunters and `pr-test-analyzer` caught every shipping-bug Critical and every real coverage gap; the two narrow agents earned real Important findings on invasive changes but almost only precedent-inherited Suggestions on additive ones — the largest token sink for the least yield. Firing them on a real signal keeps their catches. **That is the only safe reduction the data supports: Review's 3-agent dispatch is NOT reduced for low-risk changes** — a purely additive change with every low-risk signal still had a Critical caught there.

**Round 2 runs whenever round 1 committed fixes, and the cap stays 2:** in 37 of 37 changes that ran a round ≥ 2, across 16 chains, that round surfaced a Critical or Important (`spec_to_pr_aggregate.py --limit 0` over this repo and the migrated consumer ledgers, 2026-10-08). Those rounds ran while the recipe captured the fix SHA after the commit, so some may have reviewed the whole PR; the orchestrators reported sibling-instance answers on all of them.

**Round 2 asks its own question** because re-asking round 1's question over round 1's fix diff mostly re-confirms the fix. The orchestrator names the resource because an unnamed one yields a different scope per agent; the return cites its search because a confident "nothing else" costs an agent nothing to write, so the search is what gets checked. A mandatory question asked where it is ill-posed (the full-PR fallback, a rejection-only re-entry) is how a check becomes decorative. The orchestrator-specified hunks are named because only those had nobody to argue with.

**The three-status rejection.** A required reason is what keeps `remedy-rejected` from being the cheapest exit from a hard finding. A disproof closes a Critical — the strongest outcome — on a fact row the exiting delegate wrote, so the orchestrator re-derives it; it cannot ask the check's output to change, because nothing was implemented and the output can only reproduce its baseline. A rejection costs no round (the delegate did more work than one applying a wrong fix), so the bound sits on the finding: two rejections of two independently decided remedies means the finding needs a design conversation, which is the user's. Converting it to Deferred-Known-Issue would close it and empty the bucket that withholds `gh pr merge`. Recording a rejection as a delegate failure teaches the next delegate to apply a remedy it believes is wrong.

**Deferred items in three named subsections:** a fix round once returned four items under one "not applied" heading — three legitimate holds and one cheap fix nobody had done — and only a full re-read separated them.

**The rejected-alternatives snapshot `warn`.** Without it every glyph reads ✓, and a round whose check never ran prints `gh pr merge`. The no-`design.md` condition names the missing document, not a missing directory: by Revise, Propose has always created the directory. Marks are per remedy only on the Revise path, where delegated and orchestrator-applied fixes mix; on Review's no-delegate path a mark would be on everything.

**The empty-staging guard.** `git add -- <path>` on an unmodified path exits 0, `git commit` then fails, and `git push` prints "Everything up-to-date" and exits 0. Inspecting only the push reports a clean Revise and leaves the next round reviewing the whole PR. Keying the carve-out on "zero Applied" would suppress the guard exactly when a delegate reported `done` without editing.

**Two exit counts.** Before `remedy-rejected` existed every triaged finding was closed, so one untriaged counter was right by accident. A rejected finding is the first triaged-but-live one; counting only untriaged exits `ok` with an open Critical, and Handoff prints `gh pr merge` over it with every phase genuinely reporting `ok`.

Precedents for SIR-TEST ("reuse an existing helper" re-implemented with the wrong fallback; "gate this like its sibling" shipped with half the gate tested) and for the runtime-harness fidelity rule: the overlay and `review-change/references/checklist.md` "Empirical-verification fidelity".

## Archive — while the PR is still OPEN

Archive commits to the PR branch before the user merges, so the archive lands atomically with the change. **Accepted:** if the PR is later substantially modified or rejected, `openspec/specs/` and `openspec/changes/archive/` on the branch are stale. To unwind, revert the `chore: archive` commit and, if any part merged, move the change from `archive/` back to `changes/` by hand. Acceptable because by then Revise has reviewed the PR.

## Handoff and the run record

- **"Rejected remedies, still open" takes the ✗ branch.** It reaches Handoff with Revise `warn`, and the ⚠ branch names `gh pr merge` as the eventual command — right for an ordinary warn, wrong for a live Critical. The ⚠ branch also lists ⚠ phases, and a rejected remedy is not a phase. Gating on the section rather than the glyph tells the two apart.
- **`TODO.md`** outlives the PR body, which goes stale at merge. A run whose only residue is rejected-open findings still writes it; a two-list trigger skipped exactly that case.
- **The `<inherits>` verdict lines are mirrored** so a chain passing N entries can count N lines; without them it cannot tell an answered run from one that dropped the flag.
- **One counts-only run record, no per-phase logs.** Resume reads repo state through `probe_state.py`, so per-phase logs add nothing; a previous session's phase summaries are lost, but resume still picks the right phase. The record is committed on the feature branch so it merges with the PR, syncs through git, and never needs a direct push to the base branch (the `pre-push` hook refuses that).
- **Built from the example, not memory:** records written from memory late in a long session are how `date` came to replace `ts` and `phases` came to be written as an object. `findings_by_round` is written as each round closes because a reconstruction produces the plausible number, and the retro's round-2 yield reads it.
- **Schema design** (`_shared/references/run-log-schema.md`): every field earns its place by a reader — `spec_to_pr_aggregate.py` reads every field except `mode`, which identifies the run. Add a field only with its reader; an optional field left out passes the check and silently costs the retro that signal. Records written before a field was dropped keep it; the check allows extra keys and nothing reads them.
