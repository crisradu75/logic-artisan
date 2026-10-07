---
name: right-model
description: "Recommend the cheapest model and effort that can plausibly do a described task well, then offer to start it with those settings. Run with /cla:right-model."
argument-hint: "[task description]"
allowed-tools: Read, Agent, AskUserQuestion
# Slash-command only (consulted on request): keeps this description out of the
# always-loaded skill listing. Nothing invokes it programmatically.
disable-model-invocation: true
---

# Right-model: cost-aware model + effort picker

Recommend the cheapest model and effort likely to do a described task well, then optionally start
it. Bias downward: "it will probably get this wrong on Sonnet" justifies escalating; "it would do a
bit better on Opus" does not. **Quality floor, not a race to the bottom:** cost breaks ties only
between tiers that would each meet the bar. If the task needs the escalated tier, recommend it.
Redoing a hard task, or shipping a wrong answer, costs more than the tokens saved.

## Step 1: Get the task description

Use the one attached to the invocation. Otherwise ask for it; don't infer a task from vague context.

## Step 2: Classify the task, not the topic

Judge five axes. "The domain sounds hard" is not one of them.

- **Ambiguity** — fully specified, or judgment calls and unstated intent?
- **Reasoning depth** — lookup and mechanical transformation, or multi-step inference holding
  several constraints at once?
- **Stakes** — cheap to verify and redo, or expensive to get wrong (production, security, unreviewed)?
- **Scope** — one well-defined edit, or many files where a shallow pass misses real issues?
- **Output shape** — short and structured, or long-form prose where phrasing quality shows?

Map to the cheapest tier that clears the bar:

- **Cheapest** (small model, low effort) — narrow, mechanical, low-stakes, well-specified.
- **Default** (mid-size model, medium effort) — most engineering work. Land here unless something
  pushes you off it.
- **Escalated** (largest model, high or above) — real ambiguity, design tradeoffs, hard-to-reverse
  or large-scope work where a shallow pass would ship a real bug.
- **Long-form** — the model positioned for extended writing, when the task is about prose quality;
  effort still matches the piece's real length and complexity.
- **Split** (plan on the largest model, execute on a mid-size one) — when deciding what to do is the
  expensive part. Often missed; check the session actually offers such an alias.

Take the live model roster from the `Agent` tool's `model` enum, never from a list written here.
For effort, use what the session exposes and pick the lowest level the classification supports:

- The scale runs past `high`, and `high` is often the default — "recommend high" may change nothing.
- A level means different things on different models; calibrate to the model you recommend.
- The top levels can overthink: more latency and tokens for a worse-shaped answer.

## Step 3: Present the recommendation

Model and effort are two dials that need not move together: a small model at high effort for a
narrow-but-deep task, a large model at low effort for a broad-but-shallow one. Name each
separately, with the Step 2 signal that drove it. "This seems complex" is not a signal; if you
cannot point to an axis, you have not classified the task yet. A toss-up between two tiers that both meet the bar → pick the cheaper and
say so. "The cheaper tier might not meet the bar" is not a toss-up.

**When the task will run through a `cla` orchestrator, say what the session switch will and won't
change.** `spec-to-pr` routes every dispatched agent per
`${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/model-routing.md`; `multi-spec` reuses it, and
`multi-pr` never dispatches an `Agent` itself, only whole `spec-to-pr` runs. For those, escalating the session changes only the inline judgment moments
(Propose authoring, a borderline Review verdict). Check the actual file before citing it.

**One expensive turn does not need a session change.** When one judgment or diagnosis is the hard
part, an in-prompt reasoning keyword raises effort for that turn alone, if the session supports one.
Check the real keyword; vague encouragement is inert. Wrong tool for a long unattended run.

## Step 4: Offer to start the task with those settings

Ask a short yes/no; use `AskUserQuestion` only when there is a real branch to choose. Then:

- **Self-contained task** → launch it with `Agent`, `model` set to the recommendation. `Agent` sets
  the model only; effort inherits the session (capability table: `model-routing.md`). If the
  effort difference matters, say so — don't use `Workflow` as a workaround.
- **Task that needs this conversation** → only the user can switch the session's model and effort
  (e.g. `/model`; check the current mechanism). The model is visible to you, the effort usually is
  not. Tell them what to set, and proceed as soon as they confirm.

If they decline, stop after the recommendation.
