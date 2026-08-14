# Decision: the /cla:diagnose skill

Shaped 2026-08-14 via `/cla:shape-decision`. Resolves the postponed item "Add a `/diagnose` skill
to CLA" (TODO.md, parked mid-shaping 2026-07-26; origin: mattpocock/skills idea #3, see
`cla.io/decisions/domain-terminology-glossary-2026-07-26.md`).

**The gap, confirmed:** "diagnose" appears in `lite-pr`/`spec-to-pr` only as a bare verb
(`lite-pr/SKILL.md:83`, `spec-to-pr/SKILL.md:282,285` — spec-to-pr adds a state-a-cause rule but
no method), and `feedback` refuses debugging by design, mechanically (`feedback/SKILL.md:61`,
no Edit/Bash in `allowed-tools`) with nothing downstream to hand off to.

## Decisions

| # | Question | Decision | Rationale |
|---|---|---|---|
| 1 | Packaging | Standalone `skills/diagnose/` + a thin escalation hook in both Test phases | Covers both entry points (reported bug with no PR in flight; stubborn mid-run failure); defines the verb once, orchestrators cite it |
| 2 | Escalation trigger | Two Test rounds spent on the SAME stated cause with the gate still red → offer `/cla:diagnose` | Fires on "my hypothesis isn't working," before the cap exhausts; requires `lite-pr` to adopt spec-to-pr's state-a-cause rule (one sentence) |
| 3 | Lifecycle slot | "Any phase (utility)" row, beside `right-model` | An interrupt with two entry points, not a lifecycle stage |
| 4 | Hypothesis gate | Mode-aware: invoked standalone → show 3–5 ranked falsifiable hypotheses and let the user prune; escalated from a running flow → proceed autonomously, hypotheses written into the report | Invoker presence is the honest signal; an escalation inherits the parent run's autonomy contract; the discipline (ranked, falsifiable, before touching) holds in both modes |
| 5 | Bundled HITL script | Not shipped. The Phase-1 strategy priority list survives as prose (failing test → curl/HTTP script → CLI diff → headless browser → trace replay → throwaway harness → fuzz → bisection → differential → ad-hoc HITL driver, stop-and-say-so if none is buildable) | The survivor bar: a template for the rarest strategy, untested and rarely exercised, is the profile of the seven scripts already deleted |
| 6 | Escape findings ("no correct seam" / "needs an architectural fix") | Written as a dated finding into `cla.io/feedback/`, naming `/cla:shape-decision` as the next step | CLA's existing capture→shape pipeline; `project-review` is a five-agent whole-repo pass, wrong size for one finding, and reads `cla.io/` anyway |
| 7 | `[DEBUG-xxxx]` cleanup | The skill's cleanup phase requires a zero-hit grep of the tag; PLUS one line in `spec-to-pr` Ship's existing pre-staging hygiene scan (ship.md §2a) so a leaked tag from ANY interrupted run is caught at the commit choke point | The guarantee lives where every commit passes; two files carry the tag pattern — a rename must touch both |

## Retained from the peer's six-phase shape (unchanged)

Deterministic pass/fail feedback loop FIRST; reproduce and confirm it is the reported bug;
ranked falsifiable hypotheses before touching anything; one-variable-at-a-time instrumentation
with tagged `[DEBUG-xxxx]` logs; regression test written BEFORE the fix at a genuinely correct
seam ("no correct seam" is itself a finding, per decision 6); cleanup + post-mortem stating the
confirmed hypothesis in the commit message.

## Why it matters / next step

Closes the harness's only refused-by-everyone job. Natural next step: `/cla:spec-to-pr` (or
`lite-pr`) for a change implementing `skills/diagnose/SKILL.md` plus the two escalation hooks and
the Ship hygiene line — the decisions above are its design constraints. Remove the TODO.md entry
in the same change.
