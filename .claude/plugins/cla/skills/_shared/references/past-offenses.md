# spec-to-pr — enforcement-tier vocabulary

This file carries the durable, generic vocabulary for reasoning about how a spec-to-pr guardrail
graduates when it keeps failing. The dated, repo-specific incident writeups that used to sit below it
have been folded into `cla.io/overlays/spec-to-pr.md` (Decision B, `cla-skill-context-extraction`) — read
that file for the concrete "why" behind any given rule; this file stays generic.

**Enforcement tiers.** spec-to-pr's guardrails sit at four enforcement tiers (this vocabulary is shared
with `codify-learnings`'s escalation ladder), weakest → strongest: **Instructional → Structural →
Prompted → Mechanical**. Knowing a guardrail's tier tells you how it graduates when it keeps failing:

- **Instructional** — the prose rules in `SKILL.md` itself (e.g. autonomy-gate wording, "verify before
  applying a Critical" notes). Weakest; drifts over long contexts.
- **Structural** — deterministic script contracts that make the wrong thing not *fit*: an exit-code
  contract a caller must honor, a two-sided scope assertion, a schema pin.
- **Prompted** — a repo's advisory hooks: they flag on stderr but let the call through.
- **Mechanical** — a repo's blocking hooks: they exit non-zero and stop the tool call outright.

When a spec-to-pr guardrail keeps being violated, the fix is to move it *up* a tier (prose → structural
check → prompted hook → mechanical block) — the same ascent `codify-learnings` applies to session
lessons — not to restate the same prose louder. See `cla.io/overlays/spec-to-pr.md` for this repo's own
worked examples of each tier.
