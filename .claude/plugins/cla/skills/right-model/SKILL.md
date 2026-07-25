---
name: right-model
description: "Given a description of a task, recommend the cheapest model + reasoning-effort combination that can plausibly do it well, then offer to start the task with those settings. Optimizes for token/cost budget, not raw capability. Triggers on /cla:right-model or natural language like 'right-model', 'what model should I use for this', 'pick the right model and effort', 'is this a Sonnet or Opus task', 'am I overspending on this task'."
argument-hint: "[task description]"
allowed-tools: Read, Agent, AskUserQuestion
---

# Right-model: cost-aware model + effort picker

Generic skill — not project-specific. Recommends the least expensive model/effort
combination likely to succeed at a given task, then optionally starts the task with
that recommendation applied. The default bias is *downward*: pick the cheapest tier
that plausibly works, and only escalate when the task shows a concrete signal that
demands it. "It would probably do a bit better on Opus" is not a reason to escalate —
"it will probably get this wrong on Sonnet" is.

**Quality floor, not a race to the bottom.** Cost-consciousness is a tiebreaker
between tiers that would each plausibly deliver the quality the task actually needs —
never a reason to hand over a task to a tier that would underdeliver. If the honest
classification in Step 2 says the task needs the escalated tier, recommend the
escalated tier — don't talk yourself down to the cheaper one "to save budget" once
the task has already told you it needs more. Getting a high-stakes or genuinely hard
task wrong and having to redo it (or worse, shipping the wrong answer) costs far more
than the tokens saved by under-provisioning it. Optimize spend by not *over*-buying
capability the task doesn't need, not by rationing capability it does.

## Step 1: Get the task description

If the user invoked this with a task description already attached (as a slash-command
argument or inline in their message), use that. Otherwise ask for one directly — don't
guess at a task from vague conversation context.

## Step 2: Classify the task, not the topic

Judge the task along these axes. None of them map to "the domain sounds hard" —
a gnarly-sounding refactor with a clear, mechanical recipe is cheap; a two-line
prompt with no clear success criterion can be expensive.

- **Ambiguity** — is the task fully specified, or does it require judgment calls,
  weighing tradeoffs, or inferring unstated intent?
- **Reasoning depth** — is this pattern-matching/lookup/mechanical transformation,
  or does it require multi-step inference, planning, or holding several constraints
  in tension?
- **Stakes / reversibility** — cheap-to-verify-and-redo (a draft, a local edit you'll
  review) vs. expensive-to-get-wrong (production config, security-sensitive code,
  something that ships without further review)?
- **Scope** — single well-defined edit vs. something spanning many files/systems
  where a shallow pass would miss real issues?
- **Output shape** — short/structured/mechanical output vs. long-form, creative, or
  conversational output where a smaller model's phrasing quality would visibly suffer?

Map the answer to a tier, biased toward the cheapest that clears the bar:

- **Cheapest tier (small/fast model, low effort)** — narrow, mechanical, low-stakes,
  single-file-or-smaller, well-specified. Renames, formatting, boilerplate, simple
  lookups, short well-scoped edits, straightforward Q&A.
- **Default tier (mid-size model, default/medium effort)** — the bulk of normal
  software-engineering work: a scoped bug fix, a moderate feature, a multi-file but
  well-understood change, typical code review. This is the tier to land on when
  nothing pushes you off it in either direction.
- **Escalated tier (largest/most capable model, high or higher effort)** — genuine
  ambiguity requiring judgment, architectural/design tradeoffs, high-stakes or
  hard-to-reverse changes, large-scope refactors/audits, anything where a shallow
  pass would plausibly ship a real bug or bad decision.
- **Long-form/creative tier** — pick whichever currently-available model in this
  environment is positioned for extended natural writing/conversational output, if
  the task is centrally about prose quality rather than code correctness or
  multi-step reasoning. Pair it with whatever effort level matches the actual
  length/complexity of the piece — same downward bias as the other tiers, not
  automatically the highest effort available just because the model differs.

Use whatever models are actually available in the current session — the `Agent`
tool's own `model` parameter schema exposes the live roster as an enum (e.g.
`sonnet`/`opus`/`haiku`/`fable`); that's the structural source of truth for what's
switchable, not the system prompt's environment section, which only names the one
*currently active* model. Do not hardcode a model list in this skill itself, it will
go stale as the lineup changes. There's no equivalent enum for effort levels: use
whatever the session's own model/effort-switch UI currently exposes (commonly
low/medium/high, sometimes finer-grained) and land on the lowest one the task's
classification supports.

## Step 3: Present the recommendation

Model and effort are two separate dials — they don't always move together (e.g. a
small model at high effort for a narrow-but-deep task, or a large model at low effort
for a broad-but-shallow one). Justify each on its own, don't fold them into one vague
sentence:

- **Model** — name it, and give the specific signal from Step 2 that drove the pick
  (e.g. "default tier: multi-file but well-understood change, no real ambiguity").
- **Effort** — name the level, and give the specific signal that drove *that* pick
  independently of the model choice (e.g. "high effort: the task has several
  interacting constraints to hold at once even though each file's edit is simple").

Not a generic "this seems complex" hand-wave for either — if you can't point to the
concrete axis from Step 2 that justifies a pick, that's a sign you haven't actually
classified the task yet.

If the task is a genuine toss-up between two tiers *that would both meet the quality
bar*, say so and pick the cheaper one — state that you're erring cheap and why. If
the toss-up is instead "cheaper tier might not meet the bar," that's not a toss-up —
recommend the tier that meets the bar, per the quality-floor principle above.

## Step 4: Offer to start the task with those settings

Ask the user (a short yes/no is enough — use AskUserQuestion only if there's a real
branch to choose between) whether to proceed now under the recommended settings.
How "starting the task" actually works depends on where the work should happen:

- **If the task is self-contained and can be delegated to a subagent** (doesn't need
  the ongoing back-and-forth of this conversation): launch it with the `Agent` tool,
  passing `model` set to the recommended model. `Agent` sets model only — effort
  always inherits the session (see
  `.claude/plugins/cla/skills/spec-to-pr/references/model-routing.md` for the live
  capability table this skill treats as authoritative). Don't reach for `Workflow`'s
  `agent()` helper as a workaround to dial effort for an arbitrary one-off task: this
  plugin's own convention reserves `Workflow` for its own internal fan-out (see
  `multi-spec/SKILL.md`'s explicit "do not introduce `Workflow` as a workaround"
  rule), and `Workflow` frequently isn't even available as a tool in a given session.
  If the recommended effort genuinely matters and doesn't just match what the
  subagent would inherit anyway, say so plainly to the user — state the caveat, don't
  engineer around it.
- **If the task is better done inline in this conversation** (needs the existing
  context, or is genuinely interactive): the skill itself cannot change the running
  session's model or effort — only the user can, via the session's own switch
  command(s) (check current session docs/UI for the exact mechanism — e.g. a
  `/model` command that may prompt for model and effort together in one flow, or
  separate commands for each; don't hardcode exact syntax here, it can change). The
  running session's *model* is visible (check the system prompt); its *effort level*
  generally isn't — so don't assume a match on effort. Tell the user what to run for
  both, and once they confirm they've switched (or the model already matches and they
  confirm the effort is already right), proceed with the task immediately — don't
  make them ask twice.

If the user declines to start now, stop after the recommendation — don't push.
