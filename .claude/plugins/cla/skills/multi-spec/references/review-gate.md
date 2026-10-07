# multi-spec — batch review gate (Phase 4)

Adapts `${CLAUDE_PLUGIN_ROOT}/skills/review-change/references/checklist.md` — this repo's single source of truth for change review — from its single-change shape to a whole-batch dispatch. Reuse its verification checks and verdict rubric, and the agent prompts and model routing in `dispatch.md` beside it, **verbatim**; only the scope (one change → N changes in one dispatch) and the report grouping (by change name) differ. Do not fork a second review methodology — if the checklist changes, this adaptation should be re-read, not independently maintained.

## Why one review for the whole batch, not N single-change reviews

Two reasons, both from the real precedent this skill automates:

1. **Cross-change staleness is the batch-specific defect class.** A rescoped change (e.g. #3 folding in a nullable-columns rework) can leave a stale cross-reference in a sibling change (e.g. #4's caveat still describing the old model) — this is invisible to a reviewer that only ever sees one change directory at a time. PR #119's actual follow-up commit fixed exactly this shape of finding six times over.
2. **Cost.** Three agents × N single-change dispatches is N times the cost of three agents × one dispatch fed all N changes' artifacts. The verification work (checks `0a`–`0l`) is naturally batchable — read all N proposal/design/tasks/specs sets once, verify claims once, dispatch once. <!-- enumerates-checks -->

## Step 1 — Skip this whole gate for a batch of exactly 1

If the plan (`references/plan-schema.md`) has only one change, there is no cross-change staleness class to catch — invoke the single-change `review-change` checklist directly on that one change instead of this adaptation. Its own size gate then decides inline or dispatch. Then go to Step 7 with that change's verdict, so it still gets its fixes applied and its review record written.

## Step 2 — Read artifacts and pre-gather facts, across every change

Read every change's `openspec/changes/<name>/{.openspec.yaml,proposal.md,design.md,tasks.md,specs/*/spec.md}` — design.md and `specs/` may be absent (design.md is written only on a stock trigger; a `skip_specs` change has no delta), and an absent one reads as "(absent)", never as an incomplete change. Batch the reads into as few messages as possible (all N changes' artifacts in one parallel batch, same "maximize parallelism in pre-gathering" rule the checklist itself states).

Run the same high-yield checks **per change** — note that `0a`–`0e` and `0j`–`0l` live in `checklist.md` itself; only the domain-specific checks (`0f`–`0i`) and the allocation-math/i18n/mock-data checks (1–9) live in the project overlay `cla.io/overlays/review-change.md`, which the checklist reads alongside itself. Read that overlay here too, or the batch gate silently skips exactly the repo-specific checks (the overlay's domain-specific 0f–0i and 1–9 checks) that catch the most repo-specific defects. Then add one check this adaptation introduces:

**B1 — Cross-change cross-reference check (the reason this gate is batched at all).** *(Labelled `B1`, outside the `0[a-z]` namespace entirely, because this check is **batch-only** and the checklist's own labels are not. `checklist.md` defines `0a`–`0l`, and it grows by taking the next free letter — so any `0`-prefixed label chosen here is a collision waiting for the checklist to reach it. This one was `0j`, collided, was moved to `0m`, and `0m` was the very next label the checklist would have taken. A collision here is not cosmetic: an orchestrator that already ran the checklist's check of that name reads "add it" as work already done and skips the one check this gate exists for. `B` is for batch; the checklist will never issue one.)* For every claim in one change's artifacts that references another change in this same batch (by name, by a shared data model, by "depends on X" prose), verify it against that OTHER change's actual authored artifacts, not just against the referencing change's own assumptions. This is the direct analogue of checks 0a-0b but pointed across change boundaries instead of at source code — a claim like "change B's new nullable columns are read by this change" must be checked against change B's actual `design.md`/`specs/`, not assumed correct because change B "should have" done that. <!-- enumerates-checks -->

Build ONE context brief covering all N changes (same table format as the checklist, with a `Change` column prepended so findings are attributable).

## Step 3 — Size gate, per change

Apply the checklist's Step 3 size gate to **each** change on its own counts. Then:

- **Every change grades small** → no dispatch. Review the batch inline: the per-change checks above, B1 across the batch, and the checklist's weight and proof checks, then go to Step 5.
- **Any change grades large** → Step 4, one dispatch over the whole batch, so B1 still sees every change at once.

Record each change's grade in the batch report.

## Step 4 — Dispatch three agents, once, over the whole batch (when any change is large)

Same model routing as `review-change/references/dispatch.md` (the checklist's Step 4), per `${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/model-routing.md`'s "Review-agent dispatch" table:

- **Agent 1 (Design Reviewer) → `opus`**
- **Agents 2 & 3 (Task Reviewer, Spec & Codebase Reviewer) → `sonnet`**

Use the same three agent prompts verbatim from `${CLAUDE_PLUGIN_ROOT}/skills/review-change/references/dispatch.md`, with these adaptations:

- **"Change:"** becomes a list of all N change names.
- **"Affected area:"** becomes the union of affected apps/packages across the batch.
- **Content fields** (Proposal/Design/Tasks/Delta specs content) carry the FULL text of every change's corresponding artifact, or "(no design.md)" / "(skip_specs)" where it is absent, clearly delimited by a `## Change: <name>` heading per change, so the agent can attribute findings to the right one.
- **Add check B1** (cross-change cross-reference verification) to each agent's existing check list, framed the same way `dispatch.md`'s agent prompts frame their own domain-specific checks.
- **Output format** — same line kinds as the checklist, including its `- [Open] …` kind for a row that carries no severity, but each line is prefixed with `[<change-name>]` so Phase 4's fix-application step can route each finding to the right change directory: `- [<change-name>] [Critical/Important/Suggestion] Issue description`, and `- [<change-name>] [Open] <what could not be settled>: <what it would take to settle it>`. **The mandatory sweep row is emitted once per change, with the prefix** — `- [<change-name>] [Open] swept for claim shapes: …` — because Step 5 groups this section by change and the checklist treats a change with no sweep row as one where the sweep was skipped. One unprefixed row for the whole batch leaves N-1 changes looking unswept..

## Step 5 — Aggregate and report, grouped by change

Same deduplication and report shape as the checklist's Step 5, with one addition: group the `### Fix before implementing` / `### Fix during implementation` / `### Suggestions` / `### Open questions` sections by `[<change-name>]` prefix so Phase 4's fix step can work through them change-by-change. Compute the READY / FIX FIRST / RETHINK verdict **per change** (a batch can have one change RETHINK-worthy while the rest are READY — do not collapse to a single batch-wide verdict, since Phase 4's fix step needs to know which specific change(s) need edits).

## Step 6 — Verdict integrity

The checklist's "no capitulation, no sycophancy" (INT-CAP / INT-SYC) rules apply exactly as written, per change. A finding cannot exit this gate as "unaddressed" — apply it or explicitly note it's out of scope, same as the checklist demands.

## Step 7 — Apply fixes and commit (after the dispatch reports)

1. **Capture the rejected-alternatives snapshot — before applying anything.** For each change you are about to touch, read its `design.md` rejected-alternatives / explicitly-rejected-decisions content and hold it for the rest of the gate. Step 7.3's check is worthless without it, and Step 7.2's fixes routinely edit `design.md` itself. Not `git show HEAD:<path>` — a change authored in this same batch may not be committed yet. **No snapshot captured ⇒ Step 7.3's check has not run**: report that, and never record it clean.
2. Apply every Critical/Important finding as a direct `Edit`/`Write` fix to the relevant change's artifacts (routed by its `[<change-name>]` prefix from Step 5).
3. **Check each applied remedy against the alternatives that change already rejected.** Every fix here is one the orchestrator specified: there is no delegate to reject it, and the party that decided the remedy is the party judging it. The check is defined once, for every skill that applies orchestrator fixes to a change's artifacts, in `${CLAUDE_PLUGIN_ROOT}/skills/spec-to-pr/references/review-sweeps.md` ("Applying a round's fixes"; the Review fix loop) — **read the rule there rather than maintaining a second copy of it**, the same reuse-not-fork policy this file already applies to `review-change/references/checklist.md`. What it requires, in brief:

   - **The snapshot is Step 7.1** — captured before Step 7.2 applies anything, for the reasons stated there.
   - **A hit is a Critical finding on the fix itself, not a note.** Withdraw or re-specify that remedy; it does not stand on having resolved the original finding. Where the rejection is what now looks wrong, amend that change's `design.md` explicitly rather than contradicting it silently.
   - A change with no `design.md` has no such document and is out of scope for the check rather than in breach of it.

   **Withdrawing a remedy leaves the original finding unfixed, and this gate has no loop to catch it.** Step 6 permits only "apply it or explicitly note it's out of scope", and a withdrawal is neither, so a withdrawn remedy would otherwise reach Step 7.6's commit and Phase 5's PR with a live Critical — and the resume note below then reads the commit as "review is done". So: after withdrawing, either **re-specify the remedy and apply it in this same gate**, or record the finding as an explicit out-of-scope deferral with the withdrawal reason as its rationale, in that change's review record (Step 7.5). A finding never leaves this gate merely because its first remedy was wrong.

   Every remedy in this gate is orchestrator-specified, so per-remedy marking would discriminate nothing — state the fact once for the gate in the batch report instead. **The check is weaker than an independent reader and adds no round** — one extra read per touched change, and the report says so rather than implying parity.
4. Re-validate each touched change: `openspec validate <name> --strict`.
5. **Write a review record into every reviewed change, whatever its verdict**, as `openspec/changes/<name>/review.json`. `/cla:spec-to-pr` reads it to decide whether its own Review may skip the checklist pass, and treats a missing or unreadable record as "review again". Stage the fixes first, `git add -- openspec/changes/`, because `artifacts` digests the staged files. One JSON object, nothing else:
   ```json
   {"verdict": "FIX FIRST", "all_applied": true, "deferred": [], "artifacts": "<sha>", "date": "2026-10-07"}
   ```
   - `verdict` — the change's verdict from Step 5 (or from the single-change checklist, for a batch of one), before fixes: `READY`, `FIX FIRST` or `RETHINK`.
   - `all_applied` — `true` only when every Critical and Important finding for this change was applied in this gate and none was withdrawn (Step 7.3) without being re-applied. A change with none has `true`.
   - `deferred` — every Critical or Important finding this gate did not apply, one string each, as `"<severity>: <finding> — <why it was deferred>"`. Suggestions are not recorded.
   - `artifacts` — the output of `git ls-files -s -- openspec/changes/<name>/ ':(exclude)openspec/changes/<name>/review.json' | git hash-object --stdin`: one digest of the reviewed files as staged. spec-to-pr recomputes it, so any later edit to the change, however it is merged, stops the skip.
   - `date` — today, `YYYY-MM-DD`.

   A separate file, not a key in `.openspec.yaml`: OpenSpec warns on an unknown key there, and `openspec validate --strict` fails on the warning.
6. Commit all fixes and every review record as **one** follow-up commit (mirrors the real precedent's two-commit-class shape). There is always something to commit, because every change now has a new record:
   ```
   python3 ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/git_state.py --expect-branch docs/propose-<batch-slug>
   git add -- openspec/changes/
   git commit -m "docs(openspec): apply review fixes to <batch-slug> proposals"
   git push
   ```
   `openspec/changes/` is safe to path-scope broadly here specifically because this is the ONE point in the run where every change in the batch — and nothing else — is expected to be dirty; if `git status --porcelain` outside `openspec/changes/` is non-empty, name those paths explicitly instead of widening the add.
7. Run the push post-check (`references/phases.md`) before proceeding to Phase 5.

**Resume note:** if a commit matching `docs(openspec): apply review fixes to <batch-slug> proposals` already exists on this branch, review is done — skip straight to Phase 5.
