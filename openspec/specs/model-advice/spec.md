# model-advice Specification

## Purpose

**Serves:** users who want a task run on the cheapest model and effort that do it well.

What the right-model skill recommends and when it starts the task.

## Requirements

### Requirement: The cheapest tier that clears the bar is recommended

`/cla:right-model` SHALL judge a task by its ambiguity, reasoning depth, stakes, scope and output shape, SHALL recommend the cheapest model and effort that meet the bar, naming the signal behind the model and the effort separately, and SHALL escalate only on a signal that the cheaper tier would fail.

#### Scenario: A mechanical rename

- **WHEN** the task is a narrow, well-specified, low-stakes edit
- **THEN** the cheapest tier is recommended with the signals that put it there

#### Scenario: A design tradeoff in many files

- **WHEN** the task has real ambiguity and a wide scope
- **THEN** the escalated tier is recommended and the signals are named

### Requirement: A task starts only on the user's yes

`/cla:right-model` SHALL ask for the task when none was given instead of inferring one, SHALL start it with the recommended settings only after the user's yes, and SHALL stop after the recommendation when the user declines.

#### Scenario: A task that needs this conversation

- **WHEN** the user accepts and the task needs the conversation's context
- **THEN** the skill tells the user which model and effort to set and proceeds once they confirm
