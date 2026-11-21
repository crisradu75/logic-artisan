---
name: feedback
description: "Capture the user's notes one at a time, ground each read-only in the repo, and consolidate them into a dated triage doc under cla.io/feedback/ grouped by area with severity. Triage, not a fix or a decision (that is shape-decision). Triggers: /cla:feedback, 'take these notes one at a time', 'capture my feedback'."
argument-hint: "[optional first note | (empty = start interactive capture)]"
allowed-tools: Read, Grep, Glob, Write, AskUserQuestion
---

# /cla:feedback — capture feedback notes → one consolidated, grounded triage doc

Walk through the user's feedback notes **one at a time** until they say they're done. For each note, ask a clarifying question only when the note is genuinely ambiguous, then do a light read-only pass over the repo to attach concrete context (which file/component the note is about, a probable root cause where it's clear). Once the user is done, consolidate everything into a single dated markdown doc under `cla.io/feedback/` — grouped by area/screen, severity-tagged, with near-duplicate notes merged after the user confirms each merge.

This is a **capture-and-triage** skill, not a decision or investigation one. It does not decide *how* to fix anything (that's `/cla:shape-decision`) and does not deep-dive to confirm a root cause (that would be doing the work, not capturing the note). Its output is a triaged backlog ready to hand to `/cla:shape-decision`.

## Relationship to `cla.io/feedback/notes.md`

`cla.io/feedback/notes.md` is the freeform **scratch inbox** — raw bullets, jotted whenever. This skill does **not** own or rewrite it. Instead:

- Each `/cla:feedback` run writes a **new dated deliverable**: `cla.io/feedback/feedback-<slug>-<YYYY-MM-DD>.md` (same one-artifact-per-run convention as `cla.io/decisions/*.md`). Non-destructive — nothing existing is clobbered.
- A run **may consume `notes.md` as input** (see Phase 0) — pulling its unprocessed bullets into the capture loop — but reading it is not the same as owning it. Clearing `notes.md` afterward is the user's explicit call, never automatic.

## Phase 0 — Open the session

1. Derive a short kebab-case `<slug>` for this session (from the user's stated theme, or `session` if none given) and the target path `cla.io/feedback/feedback-<slug>-<YYYY-MM-DD>.md`. If that exact file already exists (same slug, same day), append a numeric suffix (`-2`, `-3`, …) rather than overwriting an earlier run.
2. **Offer to seed from the inbox.** If `cla.io/feedback/notes.md` exists and is non-empty, ask once whether to pull its current bullets into this session as starting notes (each still goes through the clarify + grounding loop below) or to start fresh. Don't silently ingest it.
3. **Create the deliverable file immediately with a "Raw captured notes" section, before entering the loop on any path** — this is the durability guarantee, so it must run before the first note is captured (a mid-session crash then loses nothing, matching the sibling skills' incremental-write ethos). Each note is appended here as it's captured+enriched during the loop; the grouping/merge/consolidation is a final rewrite pass at "done," not something held only in conversation memory.
4. Only after the file exists: if `$ARGUMENTS` carries a first note, treat it as the first captured note and enter the loop with it; otherwise enter the loop and ask for the first note.

## Phase 1 — The capture loop (one note at a time)

Repeat until the user says they're done ("done", "that's all", "finish", etc.):

1. **Take one note.** Ask for the next note (or use the seeded/`$ARGUMENTS` one). One note per turn — don't batch.
2. **Clarify only if genuinely ambiguous.** If the note is already clear and actionable, do **not** invent a question — just proceed. Ask a clarifying question only when the note's target surface, behavior, or expectation genuinely can't be determined (e.g. "which screen?", "is this a bug or a preference?"). Capture the user's answer into the note.
3. **Light read-only grounding pass.** Spend a few `Grep`/`Read`/`Glob` calls (read-only — **never edit or overwrite source files, never run the app**; the only `Write` this skill does is to its own dated deliverable) to attach concrete context to the note:
   - the relevant file(s)/component/symbol (e.g. "`<src>/<area>/<module>.<ext>`"),
   - a **probable** root cause where it's clear from the code (e.g. a known-bad dependency version, a call pattern), explicitly labeled as a hypothesis — `probable cause (unverified):` — so it's never mistaken for a confirmed diagnosis,
   - a severity tag (`bug-crash` / `bug` / `polish` / `enhancement` / `question`) and an area/screen tag.
   This is exactly the shape the best existing `notes.md` entries already have (cf. an entry naming the file, the stack trace, and the likely version regression). Keep it light — a few greps, not a full trace. If grounding is inconclusive, say so and move on; don't escalate into an investigation.
4. **Append the enriched note** to the deliverable's "Raw captured notes" section and confirm it back in one line.
5. Loop.

## Phase 2 — Consolidate (on "done")

Rewrite the deliverable **in place** — the "Raw captured notes" section is consolidated into the final structured form and **replaced** by it (not kept alongside), so the finished file is the clean triage doc, not a transcript plus a summary. (The raw section existed only as the during-loop durability buffer; once consolidation succeeds it has served its purpose.)

1. **Group by area/screen.** Cluster notes under headings for the surface they touch (e.g. "Settings page", "Search results", "Export").
2. **Severity-tag every entry** using the Phase 1 tags, so a downstream `/cla:shape-decision` pass can prioritize.
3. **Merge near-duplicates — but only with per-merge confirmation.** When two or more notes are the same issue (e.g. the same crash reported three times, as really happens in `notes.md`), propose the merge to the user first — show which notes would be fused and the combined entry (union of all repro context) — and merge only on confirmation. If no merge candidates are detected, this step is silent.
4. Write the final doc: a short header (session slug, date, source — including whether `notes.md` was seeded), then the grouped/tagged/merged entries, each with its file/component context and any labeled probable-cause hypothesis.

## Phase 3 — Report & hand off

- Report the deliverable path and a one-line summary (N notes → M consolidated entries across K areas; how many merges were made).
- **Point at the next step explicitly:** the consolidated doc is triage, not decisions — the intended bridge is `/cla:shape-decision` (per entry or per theme), which decides the fix approach; what to do with its output is `/cla:shape-decision`'s call.
- Remind the user that `notes.md` was only read, not modified — clearing the ingested bullets from it is their call.
- **Committing the deliverable is the user's call too.** The during-loop incremental write (Phase 0 step 3) protects against a crash *within the session*, but the file stays uncommitted, and the loss this durability design guards against destroys *uncommitted* files. State that the dated doc is written but uncommitted, and leave committing/pushing it to the user (same non-ownership posture applied to `notes.md`); this skill does not run git, and its frontmatter grants no `Bash` to run it with.

## What this skill deliberately does not do

- Does **not** decide how to fix anything. Fix-approach shaping (which option, what tradeoff) is `/cla:shape-decision`'s job, done deliberately one question at a time — baking it in here would collapse capture and decision into one skill and make silent design calls. The consolidated doc describes problems, not solutions.
- Does **not** edit source, run the app, or do a full root-cause investigation. Grounding is a few read-only greps producing a labeled hypothesis, not a confirmed diagnosis — it's a capture skill, not a debugging one. The frontmatter `allowed-tools` withholds `Edit` and `Bash`, but it grants `Write` for the one deliverable, so the promise not to touch source rests on this instruction, not on the tool list.
- Does **not** own or rewrite `cla.io/feedback/notes.md` — that stays the freeform scratch inbox; this skill only reads it (with permission) and writes its own dated deliverable.
- Does **not** batch notes — one at a time, until the user says done, is the whole interaction model.

## References

- `cla.io/feedback/notes.md` — the freeform scratch inbox this skill reads from (with permission) but never owns; also the model for the enriched-entry shape (file + stack trace + labeled probable cause).
- `${CLAUDE_PLUGIN_ROOT}/skills/shape-decision/SKILL.md` — the intended downstream bridge that turns a consolidated feedback doc into fix-approach decisions.
