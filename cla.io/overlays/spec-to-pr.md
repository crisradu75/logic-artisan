# spec-to-pr — project context overlay

<!--
Project-specific overlay for the `spec-to-pr` cla skill. This file is repo-local
(never distributed with the plugin). The generic SKILL.md supplies the procedure; this
file holds this skill's own rules and incidents here; facts are in `cla.io/project-facts.md`.
The file is optional.
-->

## Incident / offense history

### 2026-08-23 — the autonomy gate lost to a status report

During a `/cla:multi-pr` chain, the orchestrator committed a Revise round-1 fix,
pushed it, wrote a status block — a phase table, three bulleted findings, a
closing line — and **ended the turn** instead of dispatching round 2. The user's
response: *"what the fuck? you lost all this time! the whole point of multi-pr is
to execute the whole chain unattended"*.

**What makes this worth recording is that the rule was already there, three times
over.** The autonomy gate says "❌ End a turn with a question and wait for user
input between phases", "No finality-suggesting headers between phases either",
and "phase transitions emit AT MOST one brief sentence per boundary". It was not
forgotten — the banned shape was written, and then behaved like its own reader.

The mechanism is the report, not a decision to stop. Having produced something
shaped like a conclusion, the turn ended. So a prohibition on the shape is the
wrong instrument: it asks the author to notice, mid-flow, that what they are
writing reads as an ending. The positive, mechanical form is in the SKILL.md
autonomy gate now — status text and the next tool call go in the SAME message —
because it is checkable at the moment of writing rather than requiring a
judgement about how prose reads.

Also at user memory: `feedback_never_end_a_turn_at_a_phase_boundary`.
