## Context

Stock trigger: a data model — the codify run record, which `lib/log_run.py` checks at write time.

## Decisions

**The record is `{ts, applied: [{target, rung}], re_offenses: [{artifact, escalated_to}]}`, all three
required, lists possibly empty.** Why: it carries the two things a later reader can join on — the
artifact that failed and where its fix went. Rejected: keeping the counts (`suggestions`, `memory`,
`effectiveness`) — the apply count never moved and the tally was self-graded. Rejected: a `scope`
key — the skill no longer states one.

**A rung is one of `checklist`, `doc`, `hook`, `script`.** Why: the ladder has four rungs, and
the old six-value list named artifact types (`memory`, `claude_md`, `skill_md` are one rung), so a
"climb" from `memory` to `claude_md` read as escalation. The target path already says which
artifact. Rejected: keeping the six values for continuity — no reader is left to need it.

**Re-offenses are keyed by the failing artifact's path or hook name.** Why: slugs never joined
(78 distinct over 88). Rejected: a curated slug list — tried in July and did not stick.

**Old records are not migrated.** Why: they counted fixes and never named targets, so mapping
them would invent data. This repo's ledger check skips a codify record that still carries
`suggestions`. Rejected: a one-off mapping with `applied: []` — it would read as "nothing applied".
