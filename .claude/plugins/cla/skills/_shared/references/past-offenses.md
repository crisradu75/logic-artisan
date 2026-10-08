# spec-to-pr — enforcement-tier vocabulary

This file carries the durable, generic vocabulary for reasoning about how a spec-to-pr guardrail
graduates when it keeps failing. Dated, repo-specific incidents belong in each repo's
`cla.io/lessons-learned/`, never here; this file stays generic.

**Enforcement tiers.** spec-to-pr's guardrails sit at four enforcement tiers (the same ascent
`codify-learnings`'s escalation ladder climbs), weakest → strongest: **Instructional → Structural →
Prompted → Mechanical**. Knowing a guardrail's tier tells you how it graduates when it keeps failing:

- **Instructional** — the prose rules in `SKILL.md` itself (e.g. autonomy-gate wording, "verify before
  applying a Critical" notes). Weakest; drifts over long contexts.
- **Structural** — deterministic script contracts that make the wrong thing not *fit*: an exit-code
  contract a caller must honor, a two-sided scope assertion, a schema pin.
- **Prompted** — a repo's advisory hooks: they flag on stderr but let the call through.
- **Mechanical** — a repo's blocking hooks: they exit non-zero and stop the tool call outright.

When a spec-to-pr guardrail keeps being violated, the fix is to move it *up* a tier (prose → structural
check → prompted hook → mechanical block) — the same ascent `codify-learnings` applies to session
lessons — not to restate the same prose louder.
