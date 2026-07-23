# model + effort routing (single source of truth, repo-wide)

Every dispatched sub-agent in `/cla:spec-to-pr` is routed to a model (and, where the mechanism allows, an
effort level) chosen to keep quality at the judgment-critical points while spending cheaply on the
mechanical bulk. This file is the ONE place the routing table lives — SKILL.md and the workflow
diagram point here; change routing HERE and reflect it in those pointers, never fork the table.

**Shared beyond spec-to-pr.** Despite living under `spec-to-pr/`, this is the repo's single routing
source for *all* dispatched review work, not a spec-to-pr-private table:
`review-change/references/checklist.md` (Step 4 3-agent dispatch) and `project-review/SKILL.md`
(Step 2 5-agent dispatch) both route by the "Review-agent dispatch" section below. Keeping one table
means the "reviewer runs at the top tier, structured-rubric work runs a tier down" posture is
consistent wherever agents review code — see that section for why each review dimension gets the tier
it does.

**Palette:** `opus` / `sonnet` / `haiku` only. (No `fable` — none of these dispatches are
creative-writing-shaped work, so there's no fit for it here.)

**Why routing is possible at all:** the orchestrator's own main-loop turns run at whatever model the
*session* was launched with — the skill cannot change that mid-run. Routing therefore applies only to
**dispatched** work. Effort is dialable in exactly one mechanism:

| Mechanism | Model knob | Effort knob | Used for |
|---|---|---|---|
| `Agent(subagent_type, model:)` | yes (per call) | **no** (inherits session) | Implement delegate, Revise round ≥2, escalate-up dispatches, `fact-gatherer`/`doc-sweeper` dispatches |
| `Workflow` `agent(prompt, {model, effort, agentType, schema})` | yes | **yes** (per call) | Revise round 1 fan-out ONLY |
| `.claude/plugins/cla/agents/*.md` frontmatter | yes (`model:`) | **no** (no effort key exists) | our own `fact-gatherer` / `doc-sweeper` |

The two haiku agents we own (`fact-gatherer`, `doc-sweeper`) get model-only pinning via frontmatter
plus a terse-output instruction in their body — they're read-only (`Read`/`Grep`/`Glob` only) and
caller-scoped (they never guess a documentation surface or a symbol to check; the dispatching phase
always supplies the exact list).

## Routing table

| Dispatch | Model | Effort | Mechanism |
|---|---|---|---|
| Propose authoring, Review verdict, Revise triage | inline (session) | session | main loop — escalate-up (Propose authoring + verdict seconding ONLY; triage never escalated) when session < Opus |
| Review Step-2 fact-gathering offload (large changes) | haiku | low (body-instructed) | `.claude/plugins/cla/agents/fact-gatherer.md` |
| Cross-PR / `.claude/`-meta doc-staleness sweep | haiku | low (body-instructed) | `.claude/plugins/cla/agents/doc-sweeper.md` |
| Revise R1 — `code-reviewer`, `silent-failure-hunter` | opus | medium | `Workflow` `agent()` — **never demoted** |
| Revise R1 — `pr-test-analyzer`, `type-design-analyzer`, `plugin-dev:skill-reviewer` | sonnet | medium | `Workflow` `agent()` |
| Revise R1 — `comment-analyzer` | haiku | low | `Workflow` `agent()` |
| Implement big-mechanical delegate (sized trigger — see SKILL.md Implement) | sonnet | inherited | `Agent(model:)` |
| Revise round ≥2 (scoped fix-diff) | one tier down (opus→sonnet, sonnet→haiku, haiku stays haiku) — **bug-hunters exempt: `code-reviewer` + `silent-failure-hunter` stay opus in every round** | inherited | `Agent(model:)` |
| Ship / Archive / Handoff / prechecks / Test runs | inline, unchanged | — | no dispatch |

All six Revise agents are dispatched by their full registered `subagent_type` (`pr-review-toolkit:code-reviewer`,
`pr-review-toolkit:silent-failure-hunter`, `pr-review-toolkit:pr-test-analyzer`,
`pr-review-toolkit:type-design-analyzer`, `pr-review-toolkit:comment-analyzer`,
`plugin-dev:skill-reviewer`); the run-log ledger key stays the **bare** name for the first five (see
`references/run-log-schema.md`) since `plugin-dev:skill-reviewer` has no bare form.

## Review-agent dispatch (shared: spec-to-pr Review + review-change + project-review)

The `Revise` table above routes the PR-review (post-Ship) agents. The *pre-implementation* review
dispatch — the 3-agent `review-change` fan-out and the 5-agent `project-review` fan-out — routes here
too, on the same "top tier for premise-level judgment, one tier down for structured-rubric
application" principle:

| Dispatch | Model | Effort | Mechanism |
|---|---|---|---|
| `review-change` Agent 1 — **Design Reviewer** (feasibility, premise, allocation-math integrity, "the whole approach is wrong" class) | opus | inherited | `Agent(model:)` |
| `review-change` Agents 2 & 3 — **Task Reviewer**, **Spec & Codebase Reviewer** (structured rubric application over tasks/specs) | sonnet | inherited | `Agent(model:)` |
| `project-review` Agent 1 (**Vision & Clarity**) + Agent 4 (**Architecture & Design**) — the two premise/judgment-heavy dimensions | opus | inherited | `Agent(model:)` |
| `project-review` Agents 2, 3, 5 (**Structure**, **Requirements & Specs**, **Validation & QA**) — rubric-application over structure/specs/tests | sonnet | inherited | `Agent(model:)` |

Rationale mirrors the never-demote-bug-hunters economics: the design/architecture/vision reviewers
catch the expensive "the premise itself is wrong" class, where a cheaper model's miss ships a bad
design; the task/spec/structure/validation reviewers apply a well-specified rubric where sonnet is
sufficient. **These dispatches are `Agent`-based, so effort is not dialable** (inherits the session —
see the mechanism table above); only the Revise round-1 `Workflow` fan-out can set effort per call.

**When the session is already Opus**, routing Agent-1-class dispatches to `opus` is a no-op and the
real economy is routing the rubric-application agents *down* to `sonnet`. When the session is at or
below Sonnet, route the Agent-1-class dispatches *up* to `opus` (the same escalate-up logic as the
inline-verdict rule below) and leave the rubric agents at the session model. Apply the routing
whenever the session model differs from the target tier for a dimension.

## Escalate-up rule (session below Opus)

The judgment-critical moments — Propose artifact authoring and the Review verdict — run inline at the
session model. When the session is **below Opus**, quality at these two highest-leverage moments is
protected by dispatching *up*:

- **Propose authoring** (description / explore-result modes): dispatch the proposal/design/tasks
  authoring to `Agent(subagent_type: "claude", model: "opus")`, giving it the same description/context
  Propose would otherwise pass to `Skill(openspec-propose)` and instructing it to run that same skill
  (or produce equivalent artifacts) itself, then report back. Continue inline once it returns.
- **RETHINK-borderline Review verdict**: when the inline review (executed via
  `.claude/plugins/cla/skills/review-change/references/checklist.md`) lands on a verdict at the FIX-FIRST/RETHINK
  boundary, second it with an `opus` `Agent` fed the context brief before committing to the verdict.

On an **Opus session this rule is a no-op** — the inline model already is Opus. There is no flag;
detection is from the session-model line in the environment context. Revise triage itself is NOT
escalated (it is adjudication over already-structured findings — Sonnet handles it).

Record whether it fired in the run log (`routing.escalate_up_fired`, see `references/run-log-schema.md`).

## Why the bug-hunters are never demoted (phantom-finding economics)

`code-reviewer` and `silent-failure-hunter` stay `opus` even in the cost-conscious routing because a
cheaper model's failure mode here is *expensive*, not cheap: it emits more **phantom findings**
(plausible-but-wrong bugs). Each phantom costs a main-loop verification Read at the session model
plus, if it slips triage, a misleading "fix" commit and a follow-up revert. The savings from demoting
a bug-hunter get eaten by the triage overhead it generates. So demote only where a miss is cheap —
comment nits (`comment-analyzer` → haiku), rubric checks (`pr-test-analyzer`, `type-design-analyzer`,
`plugin-dev:skill-reviewer` → sonnet) — never the two whose job is to find the bug that ships. The
`routing.revise_findings_by_tier` telemetry (found vs phantom **per agent**, see `references/run-log-schema.md`)
is the standing check on this bet; `/cla:spec-to-pr-retro` flags a phantom rate concentrated on any one
agent — including the sonnet/haiku-routed ones (`comment-analyzer`, `pr-test-analyzer`,
`type-design-analyzer`, `plugin-dev:skill-reviewer`) relative to the opus bug-hunters. (The field is
keyed per-agent since the 2026-07-18 schema pin; it is no longer keyed by model tier, so the retro
reads the phantom rate per agent and infers the tier from which model that agent routes to.)
