---
name: shape-decision
description: "Shape a decision by walking through choices one at a time with pros/cons and a recommended pick. Triggers on /cla:shape-decision or natural language like 'help me decide between X and Y', 'shape this decision', 'walk me through the options'."
argument-hint: "[topic]"
allowed-tools: Read, Grep, Glob, Write, Edit
---

**Topic:** $ARGUMENTS

If no topic was given, infer it from the conversation (the latest open question or problem) and say what you inferred.

A good decision covers every load-bearing concern and spends no question on detail that would not change the outcome. Stop on clarity, never on a question count.

Before the first question, read `references/question-form.md`. Every question follows it.

## Start

**Model signal.** If the session model is below Opus, test the topic: is it hard to reverse? Does it ship to other repos or users? Does it have several independent constraints? If any answer is yes, say once that a stronger model or higher effort would help. Name the switch: `/model` for the model; you usually cannot see the effort setting, so tell the user to raise it if their session allows. Wait for the reply, then proceed either way. On Opus, or when all three are no, say nothing.

**Ground in this repo.** Unless the topic is purely abstract or a personal preference, read before the first question, and say what you read:

- Always: the repo's instruction files, the root `CLAUDE.md` (or `AGENTS.md`) and `cla.io/project-facts.md` if present, including for a topic about the repo's own tooling or workflow.
- For code behaviour: the capability specs, the docs `cla.io/project-facts.md` lists under "Doc-sweep paths", and any deferred-items tracker (a parked decision is context, not something to re-litigate).
- For naming: `cla.io/terminology.md`, if present.

## The axis list

Before the first question, list the axes this decision turns on, starting from this checklist. The first three are always listed, and the opening shows each as an upcoming question or with its own Noted line:

- **Reversibility**: what undoing it costs once shipped, including anything published that cannot be withdrawn.
- **Downstream consumers**: who reads, calls, installs or depends on what changes, in this repo and beyond it.
- **Release**: how it ships to others and what version class the repo's rules give it, or that nothing ships.
- **Smaller option**: should this be built at all, and is there a smaller thing that does the job?
- **Edge cases**: the inputs, states, platforms and orderings the decision must survive.
- **Design elegance**: does the option fit the existing design, or bolt onto it?
- **Invariants**: the owner's rules and the written repo rules the decision must keep, as checkable statements a later spec can test ("an unknown is null, never a confident zero").
- **Outside service**: a topic that adds a call to a vendor, an API or a model provider lists these six as axes, each with its own level:
  - rate limits
  - timeout and retry
  - cost or usage caps
  - logging and personal data in payloads
  - abuse and injection
  - testing output that is not deterministic

Leave off any other axis that plainly cannot apply.

Add any axis specific to the topic. These enter at Partial: each rule in the instruction files that bears on an option, named with its source, and every concern that earlier research in this conversation (a file read, an agent's report) or your repo read surfaced. A fact already in hand must never silently drop out.

Each axis has one level:

- **Clear**: it shows its evidence, either `Qn: "<the fragment of the user's answer that settles this axis>"`, or the text of its line `**Noted, not asked:** <concern> — <why no plausible answer could change the decision, or that the user declined to answer>` (a Noted line). A range or a bare question number is not evidence; if no fragment can be quoted, the axis is Partial. Accepting or deferring a risk is an answer; quote it.
- **Partial**: something is known, but a plausible answer could still change the decision.
- **Missing**: nothing is known yet.

A checklist axis that applies gets its own question or its own Noted line. One Noted line may cover several axes only if it names each with its own reason; a line that recites the checklist clears nothing.

## Opening

State the topic. Say once that the user can revise any earlier answer, in their own words. Show the axis list with levels and the Noted lines. Name the research you mapped: "Prior research: <the reads and reports mapped>", or "Prior research: none." Then ask the first question.

## Asking

Ask one question at a time and wait for the answer. Pick the Partial or Missing axis whose answer would most change the decision. If you cannot name the decision a question unlocks, do not ask it; give the axis a Noted line instead.

After each answer, show one line per axis whose level changed, with its evidence; an answer clears only the axes it settles. A new axis an answer raises enters at Missing. When an answer changes the chosen option, or the user revises an earlier answer, re-check every Clear axis and Noted line; one whose reason no longer holds goes back to Partial.

Stop asking when every axis is Clear by the rule above.

## Cold check

Before the summary, test the decisions cold: "Assume this failed in six months: why?" and "What simpler option exists?" For each, show one line citing what you examined; a citation is a file this run read or an answer by question number. Dismissing an option needs a reason that points at a citable fact; a dismissal without one is a finding. A real finding becomes one more question, then this check runs once more; a finding still open after the second run, or one the user declines to answer, becomes a Noted line.

## Decision Summary

Show a compact table: each question, the chosen option with any caveat the user attached, and its one-line rationale. Under it, list every Noted line, then the final axis list with each axis's level and evidence, so the user sees why the questions stopped.

Then ask one plain y/n question, for example "Write this to `cla.io/decisions/<file>`? (y/n)". Write nothing without an explicit yes.

## Persisting the decision

On a yes, use `Write` to save `cla.io/decisions/{topic-slug}-{date}.md` at the repo root, with a short kebab-case slug and today's date as `YYYY-MM-DD`. If that name exists, append `-2`, `-3`, and so on; never overwrite. Keep it lean enough to resume cold, without the pros and cons of rejected options. Include only:

- The topic, and what was inferred if it was not given
- Each question asked, the chosen option, and its one-line rationale
- The final Decision Summary table, with its **Noted, not asked** lines
- A short closing note on why the decision matters and the natural next step (for example "feeds `/cla:spec-to-pr` for change X")

## Domain terminology

Most runs touch no term; do not hunt for one. Only a term specific to this repo's own product or code counts, never a general programming idea. If the user uses such a term differently from its entry in `cla.io/terminology.md`, ask which meaning holds. When an answer settles such a term, write the entry at once, creating the file if absent, in the format of `${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/terminology-format.md`.
