---
name: shape-decision
description: "Shape a decision by walking through choices one at a time with pros/cons and a recommended pick. Triggers on /cla:shape-decision or natural language like 'help me decide between X and Y', 'shape this decision', 'walk me through the options'."
argument-hint: "[topic]"
allowed-tools: Read, Grep, Glob, Write, Edit, Bash
---

**Topic:** $ARGUMENTS

If no arguments were provided, infer the topic from the conversation context — the most recent discussion, open question, or problem being explored. State what you inferred before starting.

Follow this protocol strictly:

## Rules

1. **One question at a time.** Ask a single question, wait for the answer, then proceed.
2. **Multiple-choice options as markdown text.** Render each question as plain markdown using the format below — do NOT use the `AskUserQuestion` tool; its 4-option cap and short label/description slots can't carry the Pros/Cons + `[Recommended]` rationale this protocol needs. Each question MUST present numbered options, and each option MUST include:
   - A short label
   - Pros
   - Cons
   - Prefix your recommended option's label with `[Recommended]` and append a one-line rationale
   - **Recommend the soundest and cleanest option, not the most expedient/lowest-cost one.** When one option is architecturally sounder, more correct, or cleaner but costs more (more code, a migration, a bigger change) and another is cheaper but more of a hack/shortcut/heuristic, default your `[Recommended]` pick to the sound-and-clean one and let its one-line rationale name the tradeoff (e.g. "sounder and cleaner despite the larger change"). Cost/effort is a real con to list, never the tie-breaker that decides the recommendation. The human is the approver and can always choose the cheaper path — but the recommendation should point at the option that will age best, not the one that ships fastest. Surface a genuinely cleaner option even if it wasn't in the original option set the moment it becomes relevant (e.g. a capability a just-made decision unlocks).
3. **Interpret answers flexibly.** An answer may be a bare option number, a number plus a modification ("2, but also do X"), or free-form prose. Capture the user's actual intent — if they attach a caveat or change to their chosen option, carry it into later questions and into the Decision Summary, not just the raw number. If an answer is genuinely ambiguous, ask a brief clarifying follow-up before moving on.
4. **Adaptive flow.** After each answer:
   - If the answer makes upcoming questions redundant, skip them silently.
   - If the answer raises new questions, insert them next.
5. **Right-size the question count.** Scope questions to what's actually load-bearing for the decision — typically 3-8. Don't pad with questions that wouldn't change the outcome. For a genuinely high-stakes or multi-axis topic (e.g. spanning multiple apps/packages, hard to reverse once implemented, or with several independently-load-bearing constraints), the 3-8 range is a floor, not a cap — err on the side of asking one more question over silently skipping an axis that matters. Depth where it matters, not exhaustiveness for its own sake.
6. **Track progress.** Show a compact progress line at the top of each question: `[3/~7]` (update the estimate as questions are added or removed).
7. **Support revising earlier answers.** At any point the user can revise a prior answer — loosely matched ("actually, for Q2..." or "go back on the one about X" both work; no rigid syntax required). Update that answer, then re-apply the adaptive-flow rule to everything after it (drop questions it now makes redundant, insert new ones it raises). Mention this ability once, right after stating the topic and progress estimate, before question 1 — do not repeat it on every question.
8. **Summarize at the end.** When all questions are answered, output a **Decision Summary** — a compact table of all decisions made, with the question, the chosen option, and its one-line rationale.
9. **Offer to persist.** After the summary, ask one closing question — not another round — offering to write the exploration to a decisions file (see "Persisting the decision" below). Phrase it as a plain **y/n** prompt (e.g. "Write this to `cla.io/decisions/<file>`? (y/n)"), not a verbose or hedged offer. Do not write the file without an explicit affirmative.

## Getting started

1. Analyze the topic provided in the arguments (or inferred from context).
2. **Ground the questions in this repo.** If the topic concerns product/engine behavior, do a quick read/grep before formulating questions so the options and pros/cons reflect real constraints instead of generic possibilities — state briefly what you checked. See `cla.io/overlays/shape-decision.md` for this repo's own useful starting points (capability specs, architecture/convention docs, deliberately-deferred/postponed-item trackers — a topic may already have a parked decision worth surfacing as context rather than re-litigating from scratch). Skip the repo-grounding read for topics that are purely abstract or preference-based (personal tradeoffs, etc.) — **except** when the topic concerns naming: also read `cla.io/terminology.md` if present in that case (see "Domain-terminology capture" below for how it's used during the session), since a naming-shaped decision is exactly what that file exists to inform.
3. Formulate the question set per the "Right-size the question count" rule above.
4. State the topic, the progress estimate, and the one-time revision-support note, then ask the first question.

## Format for each question

```
[{n}/~{total}]

**{Question text}**

1. **{Option A}**
   - Pros: ...
   - Cons: ...

2. [Recommended] **{Option B}** — {one-line rationale}
   - Pros: ...
   - Cons: ...

3. **{Option C}** (if applicable)
   - Pros: ...
   - Cons: ...
```

## Domain-terminology capture (soft — skip cleanly if not applicable)

While asking or discussing a question, watch for a term the user's answer disambiguates, sharpens, or resolves a conflict on — most decisions don't have one (build tooling, workflow ordering, file locations rarely hinge on internal-naming disambiguation). When one does:

- **Check the user's phrasing against `cla.io/terminology.md`** (read once at grounding, per Getting Started step 2) — a term used inconsistently with an existing entry is worth surfacing as a clarifying question ("your terminology file defines X as Y — is that still what you mean here?") rather than silently drifting.
- **Write the resolution inline, the moment it resolves** — do not batch it to the end of the session or fold it into the Decision Summary. Follow the entry format `sync-context`'s SKILL.md documents — do not re-derive or paraphrase it here, since `sync-context` is that format's single owner. Create `cla.io/terminology.md` lazily if it doesn't exist yet.
- **Only terms specific to this repo's own product/codebase belong** — a general programming or process concept doesn't, even if the conversation uses it a lot.
- **This is a side-effect, not a goal.** Don't force a term into the file looking for something to write — most runs of this skill won't touch it at all.

## Persisting the decision

If the user accepts the closing offer, use the `Write` tool to save the exploration to `cla.io/decisions/{topic-slug}-{date}.md` in the repo root (not under `apps/*` or `packages/*`, since a decision can span multiple workspace projects). The `Write` tool creates the `decisions/` folder automatically — there is no separate mkdir step. Derive a short kebab-case slug from the topic and use today's date (`YYYY-MM-DD`). If a file with that exact name already exists (same topic, same day), append a numeric suffix (`-2`, `-3`, …) rather than overwriting the earlier run.

Keep the file lean enough to resume cold in a future session — do NOT include the full pros/cons trail for rejected options. Include only:

- The topic (and what was inferred, if it was inferred rather than given)
- Each question asked, the chosen option, and its one-line rationale
- The final Decision Summary table
- A short closing note on why the decision matters and what the natural next step is (e.g. "feeds into `/cla:spec-to-pr` or `/cla:lite-pr` for change X", or resolves a postponed item in this repo's own deferred-items tracker — see `cla.io/overlays/shape-decision.md`)

## Log the run (counts-only ledger)

Always done, after the decision is persisted (or declined). One counts-only JSON line:

```bash
echo '<record-json>' | python3 ${CLAUDE_PLUGIN_ROOT}/lib/log_run.py shape-decision-runs.jsonl
```

```json
{
  "ts": "<ISO-8601>",
  "topic_slug": "<the kebab-case slug, or omit if nothing was persisted>",
  "questions": N,
  "options_total": N,
  "took_recommendation": N,
  "persisted": true|false
}
```

**`took_recommendation` against `questions` is the field this ledger exists for.** This
skill names a recommended option on every question, and if the recommendation is taken
every single time, that is either a skill with excellent judgement or a user waving it
through — and the counts cannot tell you which, but they can tell you it is happening.
The same shape as `codify-learnings`' apply gate, which ran at 219 applied of 219
proposed before anybody counted.

Read it back with the generic summariser:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/lib/ledger_summary.py --fleet --ledger shape-decision-runs.jsonl
```

Best-effort: a failed write is noted and the run continues.
