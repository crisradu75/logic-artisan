---
name: codify-learnings
description: "Review the current conversation for lessons that would make a future, similar session go better. Propose interactive improvements to docs, slash commands, skills, hooks/settings, and user memory in this repo. Append the annotated report to the rolling log at cla.io/lessons-learned/lessons-learned.md. Triggers on natural language like 'review this session', 'codify what we learned', 'propose improvements from this conversation', or via the /cla:codify-learnings slash command."
argument-hint: "[scope-note]"
---

# Codify learnings

Review the current conversation. Identify lessons that would make a future, similar session go better. Propose concrete improvements to `.claude/`-scoped artifacts. Walk each suggestion interactively. Append the full report (applied + rejected) to the rolling log at `cla.io/lessons-learned/lessons-learned.md`.

## Inputs

- `$ARGUMENTS` — optional free-form scope note (e.g. a subsystem or an app/package) to focus the review. See `cla.io/project-facts.md` ("Workspace shape") for this repo's own monorepo shape (its app/package list; run `/cla:sync-context` to populate it; falls back to `references/project-context.md` if absent); scope is the whole repo unless you narrow it.
- Always-in-scope: root `CLAUDE.md`, the relevant per-app guidance doc (e.g. a sub-app's own `CLAUDE.md`, if the session touched it), `.claude/commands/`, `.claude/settings.json` / `settings.local.json`, the touched app/package source under `apps/*/src/` or `packages/*/src/`, user memory dir.

## Step 1 — Determine scope and reconstruct the session arc

Review the **entire session**, not just its tail. Do NOT sample only the last N tool calls — a root-cause lesson is often set up early and only paid for late, so a tail sample misses exactly the multi-phase sessions most worth codifying. Reconstruct the arc: the intended plan, every user correction or pushback, every reverted edit / abandoned approach, the design changes made mid-flight, and the final outcome.

This repo is a monorepo, so scope is normally repo-wide. State it in one line as a `Scope:` note — see `references/project-context.md` for this repo's default scope note and its worked narrowing examples. If the session was dominated by one subsystem or app, you may narrow. If `$ARGUMENTS` is set, use it as the scope note.

## Step 2 — Read context (parallel)

In a single message, issue parallel Read calls for:
- `.claude/plugins/cla/skills/codify-learnings/references/failure-modes.md` — checklist of things to look for (non-exhaustive; surface lessons not on the list too).
- `cla.io/lessons-learned/lessons-learned.md` — prior log; note any lesson proposed in multiple prior runs. (Older entries live in `cla.io/lessons-learned/lessons-learned-archive.md` once the live log is trimmed — Step 2.6; not read by default.)
- The user memory index — see `references/project-context.md` for this repo's memory-index glob. Try that glob via Bash; if none found, skip dedup and note "memory dedup skipped (index not found)" in the report. If the glob matches multiple dirs, resolve to the canonical one per the overlay's guidance before writing new memory files + index lines there.

Reading the memory **index** (one file) is enough for dedup — do not grep every memory file per candidate.

## Step 2.5 — Effectiveness check (close the loop)

A learning loop that never reads back its own output is open — it writes lessons forever and never learns whether they worked. Before building the report, cross-check this session against the artifacts prior runs produced.

For each `failure-modes.md` bullet and each memory-index entry, classify how it fared this session:

- **prevented** — the rule was visibly followed, or a mistake it warns about was consciously avoided. No action; an optional one-line note in the log's "Recurring patterns" is enough.
- **re-offended** — the mistake happened anyway, despite the rule already existing. **Action required:** feed it to the escalation ladder (see "Lesson routing and escalation"). A re-offense is the loop's single most important signal — it means the current artifact is too weak. It is NOT resolved by re-stating the same bullet.
- **n/a** — not exercised this session.

Name every **re-offense** explicitly in the log's "Recurring patterns" section, with the artifact that failed to prevent it and the rung it is being escalated to.

## Step 2.6 — Maintenance pass (retire-on-escalation, then size-triggered)

**Retire-on-escalation runs EVERY time, not only when a size threshold trips.** For each lesson this run escalates *off* the checklist (Step 2.5 produced a re-offense routed to memory / `CLAUDE.md` / `SKILL.md` / a hook / a script), name the `failure-modes.md` bullet it supersedes and decide, in one line each:

- **Retire** it — the escalated artifact now covers the same ground. Fold the retirement into the same numbered suggestion as the escalation, so a graduated lesson never leaves a duplicate behind.
- **Keep** it, with the reason — the bullet is genuinely broader than what graduated. This is common and not a failure: a bullet covering a whole class ("a platform-divergent default") outlives an escalation that fixed one instance of it, and a bullet about parallel *sessions* is not superseded by a rule about *sub-agents*.

Skipping this decision is what makes the checklist grow monotonically while its lessons live elsewhere — a retro-time-only file accumulating items that no work session ever loads. If a run escalates nothing off the checklist, say so in one line and move on.

Then the size-triggered checks. Check sizes during Step 2; if a threshold is crossed, include maintenance edits in this run's report as numbered suggestions (accepted/rejected via Step 4 like any other):

- **`failure-modes.md` over ~60 bullets** — the threshold is a bloat alarm, not a hard target to force the count under. Merge only *genuine overlap* (bullets making the same point from the same angle), and **retire** any bullet whose lesson has graduated to a hook or a load-bearing doc (it is now enforced elsewhere — see the escalation ladder). Do not delete distinct checks just to hit a number — a checklist of legitimately diverse, section-organized items is fine; an unbounded one that nobody can hold in working memory is not.
- **`lessons-learned.md` over ~12 entries** — move the oldest entries to `cla.io/lessons-learned/lessons-learned-archive.md` (create if absent), keeping the newest ~12 in the live log. The archive stays grep-able for deep history; the live log stays skimmable.

## Lesson routing and escalation

**Read `references/routing.md` first** — the artifact-reach table, the full routing rule, and the four enforcement tiers behind the ladder. Load-bearing summary (hold this even if the reference isn't reloaded):

**Every lesson must land where it will actually change behavior** — an artifact that auto-loads into future *work* sessions (memory, `CLAUDE.md`, `SKILL.md`, a hook, or a script), not just `failure-modes.md` (retro-time only; a valid landing spot ONLY for a genuine retro-time-only check). Escalation ladder, weakest to strongest:

```
failure-modes checklist  →  memory / CLAUDE.md / SKILL.md  →  hook / settings.json  →  script change
```

A **new** lesson enters at the lowest rung that can prevent it. A lesson that **re-offended this session** (Step 2.5) moves **up one rung** — never just re-stated; a re-offending behavioral rule that's hook-able MUST be proposed as a `PreToolUse` hook. Retire the now-redundant lower-rung bullet in the same run when a lesson graduates (Step 2.6).

## Step 3 — Build the report

**Read `references/step3-template.md` first** — the exact markdown shape to reproduce. Correctness-gating rules (hold these even if the reference isn't reloaded):

- **Number every suggestion sequentially**, ordered by payoff (most valuable first), across the whole list — memory candidates included, no category sections — so Step 4 can reference them by index (e.g. "y 1,3,5").
- Every suggestion is **routed** (targets an artifact satisfying the routing rule above — a re-offense targets one rung higher than the artifact that just failed) and leads with a **plain-language benefit** — what this concretely saves next time — not a `[cost: ...]` tag (found confusing in practice; priority order plus a stated benefit carries the same signal without the jargon).
- **Skills: SKILL.md-only edits — no script edits.**
- **Hard exclusions — never propose edits to** `**/scripts/**/*.py` (the skills' own bundled tooling), `openspec/**` (including `opsx:*`), or any vendored framework directory.
- Memory writes are always proposals, never automatic — they go through Step 4 like any other suggestion.
- Only the suggestions are shown, no preamble; session-summary/meta-lessons/recurring-patterns are log-only (Step 5).

## Step 3.5 — Codify-process self-check (self-improvement)

The loop must be able to improve *itself* between runs, not only the artifacts it audits — `codify-learnings/SKILL.md` and `references/failure-modes.md` are valid suggestion targets (neither is hard-excluded), but nothing prompts a self-edit unless this step does. **Read `references/steps.md`** ("Step 3.5 triggers") for the full trigger list. Fold any resulting suggestion into the Step 3 report (numbered, benefit-led, routed) so it flows through Step 4 apply. Record non-actionable process observations in the log's `### Codify-process notes` (Step 5) — a clean run gets one line saying so, not an invented self-edit.

## Step 4 — Interactive apply

Show the full report. Then prompt for the apply mode, presenting "apply all" as the default:

```
N suggestions + M memory candidates proposed.
Apply? (Y = apply all [default] / n = reject all / s = step through individually / "y 1,3,5" = apply specific items by index)
```

- `Y` (or empty/`yes`/`all`) → apply every suggestion in order; mark each **APPLIED**.
- `n` (or `none`/`reject`) → mark every suggestion **REJECTED**, write nothing.
- `s` (or `step`/`one`) → fall back to one-at-a-time:
  ```
  [3/12] {this repo's own load-bearing-convention example — see references/project-context.md} (CLAUDE.md)
    Benefit: today's session needed this and didn't have it.
  Apply? (y/n/edit)
  ```
  - `y` → apply, mark **APPLIED**. `n` → mark **REJECTED**. `edit` → ask for revised wording, apply.
- `y 1,3,5` (indices) → apply only the listed suggestions, mark the rest **REJECTED**.

(Use the tools you actually need — Edit for in-place edits, Write for new files, Bash for memory writes.)

## Step 5 — Append to the rolling log

Read `cla.io/lessons-learned/lessons-learned.md` (already done in Step 2; reuse), prepend the annotated report (with APPLIED / REJECTED markers) above the existing entries, and Write the full file back. Newest-first; entries separated by `---`.

The log entry **may** include a brief `### Session summary` and `### Lessons (meta)` for future-you context — those sections are log-only and were intentionally suppressed in the user-facing display in Step 3.

The log entry **may** also include a `### Codify-process notes` section (log-only) capturing the Step 3.5 self-check outcome: any mis-routing, effectiveness-check weakness, repeatedly-rejected suggestion type, or workflow snag observed *in the codify process itself* this run — even when it did not rise to an actionable self-edit. A future run (and the Step 7 ledger / `codify-retro`) reads this to see whether the loop's own machinery is drifting. A clean run records one line ("no codify-process issues this run").

The log entry's `### Recurring patterns` section MUST record every Step 2.5 **re-offense**: name the failing artifact and the rung it was escalated to. This section is the loop's effectiveness ledger — a future run reads it to see which lessons keep failing.

If Step 2.6 triggered a `lessons-learned.md` trim, move the oldest entries to `cla.io/lessons-learned/lessons-learned-archive.md` as part of this write.

## Step 6 — Closing summary

One paragraph:
- N suggestions proposed, X applied, Y rejected
- M memory candidates proposed, X applied
- Any lesson rejected ≥2 times in the prior log → flag for removal from `references/failure-modes.md`
- Any lesson that **re-offended** this session (Step 2.5) → confirm it was escalated up a rung, not merely re-stated; name the new rung
- Suggested next step if appropriate (e.g. "consider `/commit-commands:commit` for the applied edits")

## Step 7 — Log the run (counts-only ledger)

This step is always done. After the rolling-log write, append one counts-only JSON record of this run so the loop can be reviewed in aggregate by `/cla:codify-retro`. **Read `references/steps.md`** ("Step 7 ledger schema") for the exact fields. Assemble the record from this run's outcomes and pipe it to `log_run.py`:

```bash
echo '<record-json>' | python3 .claude/plugins/cla/skills/codify-learnings/scripts/log_run.py
```

The record lands in the repo's `cla.io/retro/codify-runs.jsonl` (a tracked repo file — include it when you next commit, so it syncs across machines via git; override the dir with `CLAUDE_RETRO_DIR`). Best-effort: if `log_run.py` exits non-zero, note it and continue — a missing ledger line never blocks the run.

## Style

- One suggestion per bullet — no bundling.
- Every suggestion has a **why** tied to something concrete that happened *this session* (a user correction, a wasted turn, a denied tool). The failure-modes checklist is a prompt, not a license to propose abstract best practices.
- Quote the actual user message or your own action when possible. Concrete > abstract.
- Default to terse. The log is for future-you skimming, not reading.

## Prefer fixes over diagnostics

When a session lesson is "I had to diagnose X manually," the first-class fix is to make the *tool* (an npm script, a config file, the smoke test, a hook) handle X automatically — not just to write a doc/memory entry telling future-Claude how to diagnose it. Always ask: **could a config or script change have prevented this entire detour?** If yes, propose that edit *first*, with the doc/memory entry as a secondary aid.

**Read `references/steps.md`** ("Prefer-fixes trigger examples") for the four recurring trigger shapes (stale dev-server/port state, a skipped build/lint gate, a smoke test drifted from the UI, a SKILL.md fix that applies to sibling skills too) and this repo's own pointers for each.

Hard exclusions still apply (`**/scripts/**/*.py` — the skills' own bundled tooling — plus `openspec/**` and vendored frameworks), but **the app's own tooling (smoke scripts, `package.json` scripts, bundler/TS/lint config, each app's/package's own source) is in scope** — propose edits to it when warranted.

## References

- `references/failure-modes.md` — retro-time checklist of things to look for (Step 2 mandatory read)
- `references/routing.md` — full artifact-reach table, routing rule, and enforcement-tier vocabulary behind the escalation ladder (mandatory-read from "Lesson routing and escalation")
- `references/step3-template.md` — the exact Step-3 suggestion-list shape, numbering, and hard-exclusion detail (mandatory-read from Step 3)
- `references/steps.md` — Step 3.5 trigger list, the Step 7 ledger JSON schema, and the Prefer-fixes trigger examples (mandatory-read from each of those stubs)
- `references/project-context.md` — this repo's project-context overlay: default scope note, memory-index glob, worked examples, and dated incidents (read alongside the stubs that point here; a repo adopting `cla` replaces this file with its own)
