# revise — PR-review loop

The Revise phase's procedure. Why its rules are shaped as they are: `design-tradeoffs.md` "Revise".

Cap: `--pr-rounds N` (default `2`). Round 2 runs whenever round 1 committed fixes, scoped to that fix diff; `--pr-rounds 1` opts out, `0` skips Revise.

## Dispatch mechanism by round (`${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/model-routing.md`)

- **Round 1** runs as ONE `Workflow` fan-out (per-call effort, schema-forced findings).
- **Round N ≥ 2** dispatches directly via `Agent`, each agent one model tier down except the never-demoted set.

Never chain through `Skill(pr-review-toolkit:review-pr)`; dispatch its agents yourself.

## Round 1 — agent selection + routing

Pick by the diff's content. Model and effort per `model-routing.md`; the **diff slice** column is what each agent is given — the two bug-hunters get the full diff, the narrow agents a filtered slice:

| Diff contains | Dispatch | Model | Effort | Diff slice passed |
|---|---|---|---|---|
| logic / behavior code | `code-reviewer`, `silent-failure-hunter` | opus | medium | **full diff** |
| a new **exported** type carrying a **non-trivial invariant** — a discriminated union, a branded/opaque type, a field-pair where one gates the other's validity (e.g. a `reliable` flag next to the value it qualifies), a closed-set narrowing — NOT merely any changed type annotation or a plain data-shape DTO | + `type-design-analyzer` | sonnet | medium | new/changed typed signatures + their files |
| a **substantial block** of added or changed comment, docstring or `.md` prose (a multi-paragraph rationale or a new `.md` section, not a single sentence), OR a comment asserting a **load-bearing decision or invariant** (a "why this and not that") — never when no comment, docstring or `.md` hunk changed | + `comment-analyzer` | haiku | low | comment/docstring/`.md` hunks only |
| new tests | + `pr-test-analyzer` | sonnet | medium | test files + the code-under-test they exercise |
| a `${CLAUDE_PLUGIN_ROOT}/skills/*/SKILL.md` **frontmatter** (`description` / `argument-hint`) changed, OR a **new** skill/SKILL.md created, OR a new command under `.claude/commands/` created | + `plugin-dev:skill-reviewer` | sonnet | medium | the SKILL.md file. A body-only prose edit does not qualify **under this row** — see the prose-dominant row below. |
| **prose-dominant diff** — more changed lines in `SKILL.md` / `references/*.md` than in executable files. Decide it mechanically: `git diff --numstat <base>...HEAD`, summing changed lines of `*.md` under `skills/` against everything else | + `plugin-dev:skill-reviewer` | **opus — never demoted** | medium | the changed `.md` files |
| docs / config only (no logic) | `code-reviewer`, plus `comment-analyzer` **only if** the docs edit meets its row above — a one-line doc/config-value tweak gets `code-reviewer` alone | per rows above | per rows above | per rows above |
| ambiguous / mixed / can't tell | `code-reviewer`, `silent-failure-hunter`, `pr-test-analyzer`; also `type-design-analyzer` when the diff has any new typed signatures (`class `, `Protocol`, `TypedDict`, `dataclass`, `def .*->.*:`), and `comment-analyzer` only on its own row's trigger | per rows above | per rows above | the full diff when scoping is unclear |

**Row precedence.** Use the specific rows first. The ambiguous row is for a diff you genuinely *can't* classify, not one that classifies cleanly below a row's bar: a plain-DTO type or a one-line comment gets no `type-design-analyzer` / `comment-analyzer`.

**Dispatch every row the diff matches** — no budget-based reduction, no degraded mode. `code-reviewer` + `silent-failure-hunter` are the floor for any logic or behaviour code.

**Never demoted, in ANY round:** `code-reviewer`, `silent-failure-hunter`, and a `plugin-dev:skill-reviewer` the prose-dominant row promoted to opus.

## Round 1 — Workflow fan-out

Author one inline `Workflow` script that dispatches the selected agents in parallel and returns one merged findings list.

**Describe the diff; never paste it.** In each agent's prompt, describe the diff by file + symbol + the focus questions (e.g. "`<module>`'s `<function>` now accepts a new parameter — check the caller passes the page's already-computed value, not a re-derived one") and tell the agent to read the hunks itself with `git diff <base-branch>..<branch> -- <paths>` (`<pr-base>..<branch>` for a stacked child). Raw diff text in the script string breaks its template literal (backticks, `${...}`, unbalanced quotes). Described, the `Workflow` handles any diff size, so round 1 uses it regardless of size and falls back only when the call itself fails.

```js
// DISPATCHES: [{agent, model, effort, prompt}, ...] built from the table above.
//   `agent` is the full registered subagent_type, e.g. "pr-review-toolkit:code-reviewer",
//   "pr-review-toolkit:silent-failure-hunter", "pr-review-toolkit:pr-test-analyzer",
//   "pr-review-toolkit:type-design-analyzer", "pr-review-toolkit:comment-analyzer",
//   "plugin-dev:skill-reviewer".
// FINDINGS_SCHEMA: object {findings: [{severity:"Critical"|"Important"|"Suggestion", file, line, summary}]}
//   — an OBJECT wrapping the array, so each result exposes r.findings below.
const results = await parallel(DISPATCHES.map(d => () =>
  agent(d.prompt, {agentType: d.agent, model: d.model, effort: d.effort, schema: FINDINGS_SCHEMA})
));
const reported = results.filter(Boolean);
// dedupe: group by (file, line); keep the HIGHEST-severity entry per group and append any
// distinct summaries from dropped entries — a Critical is never displaced by a lower-severity
// duplicate, and no distinct issue text is lost.
const findings = dedupeByFileAndLine(reported.flatMap(r => r.findings));
return {findings, launched: DISPATCHES.length, reported: reported.length};
```

- **Completeness (mandatory).** If `reported < launched`, a reviewer dropped out. Read `<transcriptDir>/journal.jsonl` — the `transcriptDir` the `Workflow` result reports — which records each agent's actual return; the top-level summary alone is not trustworthy (it has reported a retried agent as failed). Re-dispatch ONLY the agents the journal confirms never returned, individually via `Agent`, before triage. One that still does not return → Revise **`warn`**, reason `"revise fan-out shortfall: {reported} of {launched} reviewers reported"`, captured for Handoff. A crashed reviewer never vanishes silently.
- **Workflow fallback (mandatory).** Round 1 always happens. If the `Workflow` tool is **unavailable** in the session (a capability gap), dispatch the same table via direct `Agent` calls (explicit `model:`) and mark Revise **`ok`** with the note `"workflow tool unavailable — used direct Agent dispatch"`; an absent capability is not a run problem. If a **present** `Workflow` call **fails** (errors, is killed, malformed script), the same fallback → **`warn`**, reason `"workflow fan-out failed — fell back to Agent dispatches"`.
- An **empty `findings` array** from any agent is accepted at face value (`found: 0` for that agent); do not re-dispatch to fish for findings.
- Triage, verification, fixes and commits stay in the main loop below; the Workflow only produces the findings list.

## Round N (N ≥ 2)

Dispatch via `Agent`, each agent one tier down (`opus→sonnet`, `sonnet→haiku`, `haiku` stays) except the never-demoted set, which stays `opus`. Scope it to the diff the previous fix commit added, inlined into each prompt:

```
PREV_FIX_SHA=$(git rev-parse HEAD)   # captured immediately BEFORE the round-(N-1) fix commit (step 3)
git diff $PREV_FIX_SHA..HEAD          # NB: `git diff`, NOT `gh pr diff` — gh pr diff does not accept commit ranges
```

On a resume, where the held SHA is lost, take `PREV_FIX_SHA` as the parent of the previous round's `fix: review round <N-1>` commit (`git rev-parse <that commit>^`). An empty `PREV_FIX_SHA` or an empty diff → a full PR review instead; never review nothing and call it clean.

**Ask this round its own question, in each agent's prompt:**

> Does this fix introduce the defect it fixed, somewhere else? Enumerate every other instance of the resource or shape the fix concerns.

- **You name the resource**, concretely: "every call site of `<function>`", "every branch of `<function>` that returns the args tuple", "every place `<key>` is read from config". You hold the finding and the remedy; an agent holds a diff.
- **You grant repo search.** A sibling instance is outside the inlined diff, so the prompt says: read and grep the repository freely to answer this question, under the read-only discipline in `${CLAUDE_PLUGIN_ROOT}/skills/spec-to-pr/references/subagent-brief.md` slot 3.
- **The enumeration is the deliverable:** every other instance, and per instance whether the defect is present there. An empty enumeration is a stated result — "no other instance exists" — never a skipped step.
- **The return cites its search:** the command or paths scanned, then the list, then a verdict per instance. Nothing found returns `enumerated: no other instance of <the named resource>; searched: <the command>`. **An enumeration with no search behind it is not an empty result — it is a missing one.**

Skip the question on the two rounds it does not fit: a round entered on an empty `PREV_FIX_SHA` or diff (the full-PR fallback), and a rejection-only re-entry dispatched against open findings. It raises no cap.

**Name the orchestrator-specified hunks to each agent.** Tell it which hunks of the previous fix commit carry `remedy: orchestrator-specified` and ask it to check each against the change's `design.md` rejected-alternatives content (the round-start snapshot), on top of its normal review.

## For each round

1. **Aggregate** Critical / Important / Suggestion counts (round 1: the merged list; round ≥2: across the `Agent` returns).

   **On a round ≥2, check each return's enumeration first.** Re-run the `searched:` command it cites and compare the hits with its list:
   - **Cited and consistent** → take it; each confirmed sibling instance is a finding, triaged like any other.
   - **Cited but inconsistent** — the search finds hits the list omits → check the omissions yourself before triaging.
   - **No citation** → the enumeration is **missing, not empty**. Re-dispatch that agent once with the resource named; uncited again → Handoff Issue `round N enumeration uncited`.

   The comparison changes no counts. A re-dispatch it triggers is an ordinary dispatch: its findings enter this round's counts and triage.

   **SEV-MAX:** the same underlying finding rated differently by two agents is triaged at the **higher** severity, always. The Workflow's merge does this when both key it to the same `(file, line)`; apply it by hand when they describe one issue at different lines or with none.

2. **Triage every Critical and Important finding into one of three buckets:**
   - **Applied** — the fix lands this round via Edit/Write. *Closed.*
   - **Deferred-Known-Issue** — out of scope (architectural, needs a separate change, blocked externally). One-line rationale each, listed under "Issues encountered" in Handoff and mirrored to the PR body. *Closed.*
   - **Remedy-Rejected** — a fix delegate returned `remedy-rejected` for it: a **successful** return that discharges this round's attempt. Whether the finding closes depends on what the rejection cites (below). **It raises no cap; its re-attempt is bounded per finding, not charged to the round budget** ("What a rejection costs").

   A finding never exits "unaddressed". Suggestions flow to the optional `docs: TODO.md` commit.

   **Route a rejection by what it cites:**
   - **The remedy** (the defect stands, the proposed fix is wrong) → **re-decide the remedy**; the finding stays **open** and is re-attempted.
   - **A disproved defect** (a fact row the defect rested on was wrong, and the defect does not survive its correction) → **close** it as *closed-by-disproof*, with the corrected row as evidence. Never record it as Applied.

   **A rejection whose reason resolves against none of the brief's own defect or fact rows is not a rejection** — it counts as **untriaged** in the exit gate.

   **Check a disproof yourself; the delegate's word is not the evidence.** The tree is unchanged, so re-running the defect check only reproduces its baseline output. Instead, **re-resolve the corrected fact row against its named source**, then re-read the defect check's own output against the corrected row. Close only if both hold: the row really is wrong as briefed, and with it corrected the output no longer demonstrates the named defect. The row stands → an ordinary rejection, re-decide it. The row is wrong but the output still shows a real defect → correct the row and keep going.

   **What a rejection costs — the termination bound.** A rejection consumes no fix round, so the bound sits on the finding:
   - **A finding may be re-attempted with a re-decided remedy once.** That re-attempt is free.
   - **A second rejection exhausts its re-attempts.** It stays in **Remedy-Rejected**, **open**, marked re-attempt-exhausted with both delegates' reasons, and is not re-attempted again. It does NOT convert to Deferred-Known-Issue: that is a closed outcome, and closing it would empty the "Rejected remedies, still open" bucket that withholds `gh pr merge`. Revise ends `warn`.

   **Deferred items are reported under three named subsections, never one bucket.** Verbatim headings, "(none)" under an empty one:

   ```
   **Blocked on a missing artifact** — name the artifact it waits on.
   **Trigger condition not yet fired** — name the condition.
   **Skipped** — no reason above applies.
   ```

   The first two are legitimate holds; `Skipped` is a policy breach under the full-severity default, and Handoff fails on it.

   **Fix-delegate default (thin orchestrator, `${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/runtime-rules.md`).** A fix-set past the sized trigger (> ~15 subtasks-equivalent OR > ~8 files) delegates the EDIT APPLICATION to the generic coding `Agent(model: sonnet)` Implement uses — there is no separate fix-applier agent. **The orchestrator keeps its own post-fix re-verification (INT-CAP / INT-SYC / SIR-TEST below); that is never delegated.** Below the trigger, apply inline.

   **Brief it in the fix-brief form:** `${CLAUDE_PLUGIN_ROOT}/skills/spec-to-pr/references/subagent-brief.md` §2's `Defect (binding)` / `Facts this defect rests on (checkable)` / `Candidate remedy (rejectable)` fields and §5's three-status terminal contract — never the two-status `done`/`blocked` form, which lets a compliant delegate implement a wrong remedy. The brief enumerates every finding; the return carries a **per-finding outcome list** beside the overall status.

   **Route each row of that list, not the overall status:**
   - **`done`** — valid only with §5's defect-gone evidence for that finding. "The remedy was applied" alone is **not done**: re-verify it yourself and keep it open if the defect stands. No per-finding list at all → recount inline.
   - **`blocked`** — resolve the blocker and re-dispatch once, or apply the rest inline; the blocker is a Handoff Issue either way.
   - **`remedy-rejected`** — a successful return, routed by what it cites (above). Never recorded as a delegate failure.

   A contract firing — a `done` row without defect-gone evidence, a missing per-finding list, **a missing `Fact corrections:` field**, or `(none)` there beside an `unresolved:` row — is a Handoff Issue, as in Implement; recover inline, but never silently. **Never read a missing `Fact corrections:` field as `(none)`.** It is the only channel for a fact row that was wrong while the defect survived, so treat its absence as an unanswered question: re-resolve the rows yourself, or re-dispatch.

   **SIR-TEST — subtle-implementation-risk findings.** A finding of the "followed the letter of a prior fix but missed its spirit" class is Applied only when the correcting edit **plus** a dedicated regression test that would fail on the letter-but-not-spirit implementation have both landed and pass.

   **INT-CAP — no capitulation on discharge.** A Critical/Important is **Applied** only when the defect is shown gone by a re-read of the corrected hunk — never because an edit was made where the finding pointed, the budget is running out, or the change "needs to ship". **INT-SYC — no sycophancy:** "that's already handled" and "the delegate fixed it" need the same confirming read. The only exits are Applied-and-verified, Deferred-with-rationale, Remedy-Rejected-with-a-resolving-reason, or captured residue at cap exhaustion; a finding never silently evaporates.

   **A remedy the ORCHESTRATOR specified gets one extra read**: re-reading its fix, also check it against the change's `design.md` rejected-alternatives content and confirm it reintroduces none.
   - **Capture the snapshot FIRST.** Before applying **any** fix this round, read `design.md`'s rejected-alternatives section and hold it in context for the round. Never `git show HEAD:<path>` — it fails wherever the change directory is not yet committed. A re-read after the fixes returns the post-edit file, which would judge a remedy that edited that section against itself. **A check with no snapshot has not run:** mark **Revise `warn`** and record under *Issues encountered* `rejected-alternatives check did not run (no snapshot captured) — N orchestrator-specified remedies unchecked`.
   - **No `design.md`** → no such document, so neither the check nor the marking binds; out of scope, not a breach.
   - **A hit is a Critical on the fix itself.** Withdraw or re-specify the remedy; it does not stand on having resolved the original finding. Where the design's rejection is what now looks wrong, amend `design.md` explicitly.
   - **Mark it** `remedy: orchestrator-specified` on that finding's triage record. Where no later round reads the diff, the marks surface in the terminal report. **This control is weaker than an independent reader and raises no cap.**

   **Verify before applying any Critical claiming internal control flow** ("path X runs in context Y", "A happens before B", "Z is called from W"): read the surrounding flow first (1 Read) — agents build wrong mental models even from verbatim source. **A Critical claiming RUNTIME or DB semantics** (a race, constraint timing, an RPC return shape) checked by *running* a scratch harness needs a harness that structurally mirrors the real object — same columns and constraint shape, a genuinely non-unique grouping column where the real constraint is a partial/grouped unique index. When that is hard, defer to the change's own implementation test. See `review-change/references/checklist.md` "Empirical-verification fidelity".

2b. **Mutation gate (required before the commit in step 3).** A fix for a Critical/Important
   finding earns the same evidence the original code needed — "the reviewer's finding is now
   handled" is not that evidence. Break **what the fix touches**, not only what it targets:
   correcting one return path routinely breaks another. Do each one by hand: edit the code so the
   defect is back, run the affected test, confirm it FAILS, then restore the edit exactly — a test
   that still passes has not been shown to catch anything, and an unrestored edit ships the defect.
   Stage the fix first (`git add <path>`), then restore each mutant with `git checkout -- <path>`.
   Unstaged, that checkout discards the fix along with the mutant, and so does `git stash`.
   Re-stage after every further edit to the fix, or the next restore reverts that edit. The
   `ask-destructive-git` hook prompts before this checkout, because the mutated file differs from
   the index. Unattended, take the other route. Back up the fixed file, before any mutant, to the
   session scratchpad. Copy it back after each mutant. Never put a backup anywhere else outside the
   checkout. A delegate briefed per `subagent-brief.md` follows that brief's own mutation route
   instead. It mutates a scratchpad copy, never the live file. Its result is not verified against
   the live tree. The orchestrator treats it as unverified and runs the mutant itself before
   committing. **A test that DOES fail is not thereby correct:
   read the assertion that killed the mutant and confirm it states the behaviour you want.** A test written from a wrong mental model
   kills mutants exactly as reliably as a right one. Worst where the mutant is the *simpler* form
   of the code: if the simpler form is right, the test defending the original is defending the
   bug. Full rule: `${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/test-quality-gates.md`, "How
   planting goes wrong". Fix a surviving mutant, or name it in the Handoff report with a reason. A
   clean run is evidence about the mutants you thought of and nothing else.

3. **Commit `fix: review round <N>`.** The subject drives `probe_state.py`'s round counter and round N's diff scoping. Verify git state first:
   ```
   python3 ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/git_state.py --expect-branch <branch>
   ```
   Exit 0 → proceed; 2/3 → halt and surface. Then stage the explicit changed paths (never `-A`), **confirm something was staged**, and commit:
   ```
   git add -- <changed-paths>
   git diff --cached --name-only
   git rev-parse HEAD                    # hold as PREV_FIX_SHA: the next round reviews PREV_FIX_SHA..HEAD
   git commit -m "fix: review round <N>"
   git push
   ```
   **Every measurement this round asserts names its command**, exactly as Ship does: one `Measured-by: <command> — <claim>` trailer per claim in a single second `-m`, with the `Co-Authored-By:` / `Claude-Session:` lines directly under it, and the parse check (`git log -1 --format=%B | grep -c '^Measured-by:'` equal to `git log -1 --format='%(trailers:key=Measured-by,valueonly=true,unfold=true)' | grep -c .`) before pushing — rules and recipe in `ship.md` §2b and §3. A fix round is where mutation results and counts get written, so it binds here; the standing pre-PR gates are not claims this round asserts.

   **`git diff --cached --name-only` must list at least one path. Empty output means NOTHING was staged — stop.** Do not commit or push; name which of `<changed-paths>` produced nothing and mark Revise `warn`. (`--name-only`, not `--quiet`: `--quiet`'s healthy exit code is 1, which the hoisted rule would read as a failure.) `git add` on an unmodified path exits 0, and `git push` then prints "Everything up-to-date" and exits 0, so the push exit code cannot catch this.

   **One carve-out: every finding's row in the per-finding outcome list is `remedy-rejected`.** The delegate declined every edit for stated reasons, so nothing to stage is a **successful** round: skip the commit and push, do **not** `warn`, and **go on to step 4** so the exit gate sees the open findings. Discriminate by what the delegate RETURNED, never by "zero findings triaged Applied" — a `done` row with nothing staged also yields zero Applied, and is still a contract firing.

   **A carved-out round leaves no `fix: review round <N>` commit**, and `probe_state.py` counts rounds by those subjects. Record it in the Handoff report — "round N: all findings remedy-rejected, no commit" — and on a resume treat a reported rejection-only round as spent. Never manufacture an empty commit for the counter.

   **A round with no fix commit leaves no usable `PREV_FIX_SHA`**: it still marks the previous round's start, so `$PREV_FIX_SHA..HEAD` is a diff already reviewed. Dispatch the re-attempt **against the open findings themselves**, with their re-decided remedies, not against a diff.

   Inspect the `git push` exit code in your own context (no `|| { ... }` compound). Non-zero → Revise `warn`, the failure to Handoff Issues, and a prominent warning that round-N fixes are local-only.

4. **Record the round now:** append `{"round": N, "found": <this round's deduplicated Critical+Important count after triage>}` to Revise's `findings_by_round`. Handoff reads it; it is never reconstructed there.

   **Exit gate — TWO counts, and both must be zero to exit clean.**
   - **Untriaged** — Critical/Important findings in no bucket.
   - **Open** — in a bucket but not closed. Applied and Deferred-Known-Issue are closed. **Remedy-Rejected citing the remedy is triaged and OPEN**; Remedy-Rejected citing a disproved defect is closed.

   **Both 0** → status `ok` and exit the loop, **unless this round committed fixes and the cap allows another round** — then run it, scoped to that fix diff. When the last allowed round committed fixes, Revise still ends `ok`, and the Handoff report says in one line that those fixes were not reviewed again.

   **Open > 0** → decide by whether a re-attempt is still available:
   - **Some open finding still has its free re-attempt** AND the round budget allows → **re-enter the loop** with re-decided remedies for those findings.
   - **Every open finding is re-attempt-exhausted, or the budget is spent** → exit, status `warn`, the open findings to the "Rejected remedies, still open" bucket.

   **The round budget decrements for any round that applied fixes**; only a round in which every finding was rejected is free. Both bounds are needed: the per-finding bound stops one finding looping forever, the round budget stops mixed rounds generating fresh findings forever. Suggestions are still recorded for the optional `docs:` commit.

5. Otherwise decrement the budget. **Cap exhausted with Critical/Important still untriaged or still open** → status `warn` (the only cap outcome that warns); exit with both captured for Handoff — untriaged residue to "Deferred to TODO.md", open rejected findings to their own bucket.
