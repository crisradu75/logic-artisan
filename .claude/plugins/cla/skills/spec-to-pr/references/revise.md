# revise — PR-review loop (full mechanics)

The Revise phase's step-by-step procedure, agent-selection table, dispatch snippet, and the full prose behind each triage invariant. `SKILL.md`'s Revise stub carries the load-bearing invariants as one-liners (never-demote, SEV-MAX, the Applied/Deferred triage requirement, SIR-TEST, INT-CAP/INT-SYC, verify-before-applying-a-control-flow-Critical, the exit gate, the fix-delegate default); this file carries the recipes and the reasoning.

Cap: `--pr-rounds N` (default `2`).

## Dispatch mechanism differs by round (per `${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/model-routing.md`)

- **Round 1** runs as ONE `Workflow` fan-out (per-call effort dialing + schema-validated findings — see "Round 1 — Workflow fan-out" below).
- **Round N ≥ 2** dispatches directly via `Agent` (a small scoped re-check; the Workflow-script overhead isn't worth it), each agent one model tier down.

Either way, do NOT chain through `Skill(pr-review-toolkit:review-pr)` — that skill is a thin layer that itself dispatches the same `pr-review-toolkit:*` agents; the orchestrator does it one hop more directly.

## Round 1 — agent selection + routing

Based on the diff content. Model + effort per `${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/model-routing.md`; the **diff slice** column is the specialty-scoping rule (pass each agent only the hunks its specialty needs — the two bug-hunters get the full diff, the narrow agents get a filtered slice):

| Diff contains | Dispatch | Model | Effort | Diff slice passed |
|---|---|---|---|---|
| logic / behavior code | `code-reviewer`, `silent-failure-hunter` | opus | medium | **full diff** |
| a new **exported** type carrying a **non-trivial invariant** — a discriminated union, a branded/opaque type, a field-pair where one gates the other's validity (e.g. a `reliable` flag next to the value it qualifies), a closed-set narrowing — NOT merely any changed type annotation or a plain data-shape DTO | + `type-design-analyzer` | sonnet | medium | new/changed typed signatures + their files |
| a **substantial block** of new comment/doc prose (a multi-paragraph rationale or a new `.md` section, not a single sentence), OR a comment/design-doc asserting a **load-bearing decision or invariant** a future maintainer would trust (a "why this and not that") — NOT one-line inline comments | + `comment-analyzer` | haiku | low | comment/docstring/`.md` hunks only |
| new tests | + `pr-test-analyzer` | sonnet | medium | test files + the code-under-test they exercise |
| a `${CLAUDE_PLUGIN_ROOT}/skills/*/SKILL.md` **frontmatter** (`description` / `argument-hint`) changed, OR a **new** skill/SKILL.md created, OR a new command under `.claude/commands/` created | + `plugin-dev:skill-reviewer` | sonnet | medium | the SKILL.md file. Frontmatter/new-skill-scoped: a body prose edit that leaves the frontmatter unchanged does not alter triggering behaviour, so it does not qualify **under this row** — see the prose-dominant row below, which catches it for a different reason. |
| **prose-dominant diff** — more changed lines in `SKILL.md` / `references/*.md` than in executable files. Decide it mechanically: `git diff --numstat <base>...HEAD` and compare the summed changed lines of `*.md` under `skills/` against everything else | + `plugin-dev:skill-reviewer` | **opus — never demoted** | medium | the changed `.md` files |
| docs / config only (no logic) | `code-reviewer`, plus `comment-analyzer` **only if** the docs edit meets the `comment-analyzer` trigger above (a substantial prose block or a load-bearing "why") — a one-line doc/config-value tweak gets `code-reviewer` alone; skip the rest | per rows above | per rows above | per rows above |
| ambiguous / mixed / can't tell | `code-reviewer`, `silent-failure-hunter`, `pr-test-analyzer` — the broadest-signal trio. Also `type-design-analyzer` when the diff has any new typed signatures (`class `, `Protocol`, `TypedDict`, `dataclass`, `def .*->.*:`), and `comment-analyzer` when it has any docstrings, `# `-comment blocks, or `.md` files. | per rows above | per rows above | when scoping is unclear, pass the full diff — a signal-empty agent is by design, not a cost omission |

**Row precedence.** Use the specific rows first — the `ambiguous / mixed` row is the fallback for a diff you genuinely *can't* classify, NOT for one that classifies cleanly but falls below a tightened bar. A new plain-DTO type or a one-line comment is "classifiable, below the bar" (→ no `type-design-analyzer`/`comment-analyzer`), not "ambiguous" (which would wrongly pull them in via the wider net). Fall to the ambiguous row only when the diff's shape is truly unclear, and accept its deliberately wider dispatch there.

**`code-reviewer` and `silent-failure-hunter` are never demoted — in ANY round** (the round-≥2 tier-down rule below exempts them), and so is `plugin-dev:skill-reviewer` whenever the prose-dominant row promoted it to opus: on a markdown-behaviour diff it occupies the bug-hunter's position and inherits the same economics — a cheaper bug-hunter emits more phantom findings, whose triage cost exceeds the saving, and that economics is not round-scoped (see `${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/model-routing.md` rationale). And because `routing.revise_findings_by_tier` is keyed per AGENT (not per model tier — schema pinned in `${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/run-log-schema.md`), a demoted bug-hunter's degraded accuracy lands under its own agent key, so a rising phantom rate shows up directly against `code-reviewer`/`silent-failure-hunter` in `/cla:spec-to-pr-retro` — exactly the signal that polices this rule.

**Why the `type-design-analyzer` / `comment-analyzer` triggers are tighter than "any new type" / "any new comment" (the Revise token-efficiency lever).** Across a measured multi-change `multi-pr` run in this repo (see `cla.io/overlays/spec-to-pr.md` "Incident history" for the data point), the two bug-hunters (opus) and `pr-test-analyzer` caught every shipping-bug Critical/High and every real coverage gap; `type-design-analyzer` and `comment-analyzer` earned real Important findings *on invasive changes* but produced almost only precedent-inherited Suggestions on purely-additive changes — the run's single largest token sink for the least severity-weighted yield. Firing them on a genuine signal (a new invariant-bearing type / a load-bearing "why" comment) rather than run-always keeps their real catches while cutting the Revise fan-out on a clean additive change. The `code-reviewer + silent-failure-hunter + pr-test-analyzer` trio remains the floor for any change with logic/behavior code. This is the ONLY safe fan-out reduction the data supports: **Review's 3-agent dispatch is NOT reduced for low-risk changes** — see `cla.io/overlays/spec-to-pr.md` for the named precedent where a purely-additive change with every low-risk signal still had a real Critical caught by the 3-agent Review, the reason the size gate stays as-is.

## Round 1 — Workflow fan-out

Author one inline `Workflow` script that dispatches the selected agents in parallel, each with its diff slice baked into the prompt, and returns a merged findings list.

**Diff-embedding discipline (the load-bearing rule for a clean Workflow run).** In each agent's prompt, **describe the diff by file + symbol + the focus questions** (e.g. "`<module>`'s `<function>` now accepts a new parameter — check the caller passes the page's already-computed value, not a re-derived one") and tell the agent to read the actual hunks itself via `git diff <base-branch>..<branch> -- <paths>` (on a stacked child — `--pr-base` passed — the range is `<pr-base>..<branch>`, per `SKILL.md`'s `<pr-base>` rule). **Do NOT paste the raw diff text verbatim into the `Workflow` script string.** A raw diff routinely contains backticks, `${...}`, and unbalanced quotes that break the JS template-literal the script is embedded in — this is the *real* reason early runs fell back to direct `Agent` calls, misattributed at the time to diff *size*. Described-not-pasted, the `Workflow` path handles arbitrarily large diffs cleanly; pasted-verbatim, even a small diff can corrupt the script. So the Workflow-vs-Agent choice is **not** size-gated: default to `Workflow` for round 1 regardless of diff size, and only take the documented fallback below if the `Workflow` call itself actually fails. The merged findings list is built as:

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

- Each agent is forced to return the structured `FINDINGS_SCHEMA` (no prose essays to re-parse); the script dedupes per the merge policy in the snippet (severity-max wins; distinct summaries preserved), so the main loop receives one clean list.
- **Completeness rule (mandatory).** If `reported < launched`, a dispatched reviewer crashed and silently dropped out. Don't just accept the shortfall: read the run's `journal.jsonl` (the `Workflow` tool's own ground truth — it records each agent's actual return value, per the Workflow tool description). Its directory is the `transcriptDir` path the `Workflow` tool result itself reports back on the call you just made — read `<that transcriptDir>/journal.jsonl` — to confirm which agents genuinely failed versus which the top-level summary merely *reported* as missing. **The top-level summary is not fully trustworthy on its own** — encountered for real: a Workflow round reported 3 of 5 agents failed, but the journal showed one of the three had actually succeeded on a retry the summary didn't reflect. Re-dispatch ONLY the agents the journal confirms genuinely never returned, individually via `Agent` (not a full Workflow re-run), before triaging findings. Only if a re-dispatched agent still doesn't return, mark Revise **`warn`** with reason `"revise fan-out shortfall: {reported} of {launched} reviewers reported"` and capture it for the Handoff Issues section — a crashed reviewer must NEVER vanish silently from the merged list. (Continue the loop; do not halt — same continue-on-everything policy as the rest of the skill.)
- **Workflow-fallback (mandatory) — but distinguish capability-gap from failure.** Round 1 review always happens by one mechanism or the other; never skip it. Either way, fall back to dispatching the same round-1 table via direct `Agent` calls (explicit `model:` per the table; effort inherits the session). The status depends on *why* the fallback fired:
  - **`Workflow` tool unavailable** (the tool isn't present in this session — a harness *capability gap*, detectable up front, not a run problem) → mark Revise **`ok`** with a one-line note (e.g. `"workflow tool unavailable — used direct Agent dispatch"`). Do NOT `warn`: an absent capability is not a run-quality defect, and warning on it pollutes `/cla:spec-to-pr-retro`'s warn-reason signal (every Revise round would warn on a Workflow-less harness).
  - **`Workflow` call FAILS** (the tool IS present but the call errors, is killed, or the script is malformed) → mark Revise **`warn`** with reason `"workflow fan-out failed — fell back to Agent dispatches"`; a genuine failure worth surfacing.
- An **empty `findings` array** from any agent — including a full-diff bug-hunter — is accepted at face value (it logs as `found: 0` for that agent in `routing.revise_findings_by_tier`); do not re-dispatch to fish for findings.
- Triage, phantom-verification, fixes, and commits stay in the **main loop** exactly as below — the Workflow only produces the findings list.

## Round N (N ≥ 2)

Dispatch via `Agent` (not Workflow), each agent one model tier down (`opus→sonnet`, `sonnet→haiku`; `haiku` stays `haiku`) — **EXCEPT the never-demoted set — `code-reviewer`, `silent-failure-hunter`, and a `plugin-dev:skill-reviewer` promoted by the prose-dominant row — which all stay `opus` per the rule above**. Scope to the diff added by the previous fix commit. Inline the scoped diff into each agent's prompt — do NOT make agents re-read it. Capture the previous fix commit's sha **before** triggering the next round:
```
PREV_FIX_SHA=$(git rev-parse HEAD)   # captured immediately after pushing the round-(N-1) fix commit
git diff $PREV_FIX_SHA..HEAD          # NB: `git diff`, NOT `gh pr diff` — gh pr diff does not accept commit ranges
```
Pass the captured diff to each Agent prompt. If `PREV_FIX_SHA` is empty or the diff is empty, fall back to a full PR review (defensive — never review nothing and call it "all clean").

## For each round

1. Aggregate Critical / Important / Suggestion counts (round 1: over the Workflow's merged findings list; round ≥2: across the individual `Agent` returns).
   - **Severity divergence → take the max (SEV-MAX).** When two agents flag the *same underlying finding* at *different* severities — e.g. `silent-failure-hunter` calls it Important while `code-reviewer` calls the identical issue a Suggestion — triage it at the **higher** severity, always. The `dedupeByFileAndLine` merge in the Workflow snippet already does this mechanically when both agents key the finding to the same `(file, line)`, but two agents often describe one issue at slightly different lines (or one gives no line at all), so the human aggregation step must apply the same rule by hand: a real finding one agent rated higher is not silently downgraded because another agent (or the mechanical dedup) rated it lower. This is the aggregation analogue of the never-demote-a-real-finding principle.
2. **Triage every Critical and Important finding into one of two buckets:**
   - **Applied** — fix lands in this round via Edit/Write.
   - **Deferred-Known-Issue** — fix is out-of-scope (architectural, requires separate change, blocked by external dependency, etc.). Capture a one-line rationale per item; these MUST be listed under "Issues encountered" in the Handoff report and mirrored to the PR body.

   A finding cannot exit the loop as "unaddressed" — it must be Applied OR explicitly Deferred with rationale. Suggestion-level findings flow to the optional `docs: TODO.md` commit.

   **Fix-delegate default (thin-orchestrator, per `${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/runtime-rules.md`).** When the round's fix-set is large — past the existing sized-trigger (> ~15 subtasks-equivalent OR > ~8 files) — delegate the mechanical EDIT APPLICATION to the existing generic coding `Agent(model: sonnet)` (the same escape-hatch delegate Implement uses; there is NO separate "fix-applier" agent), with its evidence-based `done`/`blocked` terminal contract. **Delegation covers edit application ONLY — the orchestrator retains its own post-fix re-verification (INT-CAP/INT-SYC/SIR-TEST below); that discipline is never delegated.** Below the trigger, apply inline.

   **Subtle-implementation-risk findings need a proving test to count as Applied (SIR-TEST).** When a Revise finding is the "implementer followed the letter of a prior fix but missed its spirit" class — the pre-implementation Review's `review-change/references/checklist.md` names this class and mandates a proving-test *task* for it, but the Implement delegate can still ship an incomplete version, which is exactly why it resurfaces here — the fix is not fully Applied until a **dedicated regression test that would fail on the letter-but-not-spirit implementation** exists and passes. A prose/code edit that corrects the current instance without a test guarding the invariant leaves the defect one refactor away from returning. (Concrete precedents in this repo — a "reuse an existing helper" fix re-implemented with the wrong fallback value; a "gate this control like its true sibling" fix shipped with only half the gate tested — are in `cla.io/overlays/spec-to-pr.md` "Incident history".) For a SIR finding, "Applied" = the correcting edit **plus** the proving test, both landed and passing.

   **No capitulation on discharge (INT-CAP).** A Critical/Important finding counts as **Applied** only when the *defect is shown gone* — verified against the corrected code (a re-read of the fixed hunk confirming the problem is actually removed), not merely because an edit was made where the finding pointed, because a round budget is running out, or because the change "needs to ship." An edit that touches the right line without removing the issue is still an open finding, not an Applied one. Likewise **no sycophancy (INT-SYC):** do not accept "that's already handled" or "the delegate fixed it" without the confirming read. This mirrors `review-change/references/checklist.md`'s "Verdict integrity" clauses. The only honest exits are Applied-and-verified, Deferred-with-rationale, or (at cap exhaustion) captured-as-untriaged-residue; a finding never silently evaporates.

   **Verify before applying any Critical that claims internal control-flow behavior.** When an agent's Critical finding asserts "code path X runs in context Y" or "step A happens before step B" or "function Z is called from path W" — verify against the actual code by reading the surrounding flow before applying a fix. Agent reasoning over code can produce phantom findings even with verbatim source pasted into the prompt (the agent reads the bytes but builds the wrong mental model). Cost of verification: 1 Read call; cost of applying the wrong fix: a misleading "fix" commit + a follow-up revert. **If the Critical instead claims RUNTIME or DB semantics (a race, a constraint-timing behavior, an RPC return shape) and you resolve it by *running* a scratch check, the harness MUST structurally mirror the real object** — same columns/constraint shape, a genuinely non-unique grouping column where the real constraint is a partial/grouped unique index — never a simplified stand-in that is accidentally already unique. A verification built on a structurally-wrong harness produces false confidence in *either* direction; when faithful verification is hard, prefer deferring to the change's own implementation test (faithful by construction). See `review-change/references/checklist.md`'s "Empirical-verification fidelity" note for the full rationale and the past offense it comes from.
2b. **Mutation gate (required before the commit in step 3).** A fix for a Critical/Important
   finding is a change like any other and earns the same evidence the original code needed —
   "the reviewer's finding is now handled" is not that evidence. Break **what the fix
   touches**, not only what it targets: correcting one return path routinely breaks another, which
   is how a real fix here once traded a silent no-op on the default path for the identical no-op on
   the overlay path. Do each one by hand: edit the code so the defect is back, run the affected
   test, confirm it FAILS, then restore the edit exactly — a test that still passes has not been
   shown to catch anything, and an unrestored edit ships the defect.
   Fix a surviving mutant, or name it in the Handoff report with a reason. A clean
   run is evidence about the mutants you thought of and nothing else — two commits in this repo each
   recorded "three mutations checked, all caught" and each shipped a critical a later review found.
3. Stage + commit as `fix: review round <N>`. The fix-round commit subject is structurally meaningful (it drives `probe_state.py`'s round counter and the round-N-on-fix-diff scoping above). Before staging, verify git-state:
   ```
   python3 ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/git_state.py --expect-branch <branch>
   ```
   Exit 0 → proceed; exit 2/3 → halt and surface. Then stage the explicit changed-paths list (never `-A`), **confirm something was actually staged**, and commit — the subject is one line, passed inline:
   ```
   git add -- <changed-paths>
   git diff --cached --name-only
   git commit -m "fix: review round <N>"
   git push
   ```
   **`git diff --cached --name-only` must list at least one path. Empty output means NOTHING was staged — stop there.** Do not commit, do not push. Name which of `<changed-paths>` produced nothing and mark Revise `warn`.

   (`--name-only`, not `--quiet`, deliberately: `--quiet` signals through its exit code, and the *healthy* case — differences present — is exit **1**, which this skill's own hoisted rule would read as a failure and halt on. Inverting a check into halting every successful round is no better than not having it.)

   This check is not decoration. `git add -- <path>` on a path that exists but was never modified exits **0** and stages nothing — the quiet case, and the likely one when a delegated fix-applier reports success without touching the file it named. `git commit` then fails with "nothing to commit", and **`git push` prints "Everything up-to-date" and exits 0**. Inspecting only the push — the one exit code that cannot fail here — reports a clean Revise, opens the PR without the round-N fixes in it, and captures the PREVIOUS commit as `PREV_FIX_SHA`, so the next round scopes its diff against the wrong base. The deleted `commit.py` refused this case explicitly; nothing replaced the refusal until now.

   Inspect the `git push` exit code in the orchestrator's own context (do NOT chain `|| { ... }` — that compound shell form breaks the permission-allowlist matching per root `CLAUDE.md`). On non-zero exit, mark Revise `warn`, capture the failure for the Handoff Issues section, and emit a prominent warning that round-N fixes are local-only. On success, capture `git rev-parse HEAD` for use as `PREV_FIX_SHA` in the next round's diff scoping.
4. **Exit gate.** Count *un-triaged* Critical and Important findings (Applied and Deferred-Known-Issue both count as triaged). If 0 untriaged → status `ok`, exit loop. Suggestions still recorded for the optional `docs:` commit.
5. Otherwise decrement budget. **If the cap is exhausted before all findings are triaged** (the only scenario where untriaged residue exists — step 2's rule otherwise prevents it), status `warn`, exit loop with the untriaged residue captured for the Handoff "Deferred to TODO.md" section.
