# Lesson routing and escalation (full detail)

Read this before assigning a suggestion's target artifact or rung. `SKILL.md`'s "Lesson routing and escalation" carries only the one-line ladder summary and the re-offense-moves-up-a-rung rule; this file is the full reasoning behind both.

## Why routing matters

**Every lesson must land where it will actually change behavior.** The candidate artifacts differ sharply in reach — this is the most common way the loop leaks:

| Artifact | When it loads | Reach |
|---|---|---|
| `failure-modes.md` | only during the next `codify-learnings` run | **retro-time only** — does NOT influence normal work sessions |
| user memory (`memory/*.md`) | every session, as advisory context | broad, cross-project — but advisory, Claude must choose to apply it |
| `CLAUDE.md` / `SKILL.md` | every session touching that repo/skill | scoped, advisory |
| hook / `settings.json` | every matching tool call, deterministically | **enforced** — cannot be forgotten |
| script change | every run of that script | impossible to violate |

**Routing rule.** A lesson MUST land in at least one artifact that auto-loads into future *work* sessions (memory, `CLAUDE.md`, `SKILL.md`, a hook, or a script). Landing a lesson *only* in `failure-modes.md` is permitted **only** when it is genuinely a retro-time review check that cannot be acted on mid-session. `failure-modes.md` is a staging checklist, not a destination: a preventable lesson parked only there cannot prevent anything until it re-offends and a later run finally promotes it.

## The escalation ladder

Rungs from weakest to strongest:

```
failure-modes checklist  →  memory / CLAUDE.md / SKILL.md  →  hook / settings.json  →  script change
   (retro-time only)         (advisory, every session)         (deterministic)          (impossible to violate)
```

- A **new** lesson enters at the lowest rung that can actually prevent it — usually memory or a doc, rarely the checklist alone.
- A lesson that **re-offended this session** (Step 2.5) moves **up one rung**. An advisory rule that keeps being violated needs enforcement, not a louder reminder.
- A re-offending **behavioral** rule that is hook-able — a deterministic precondition on a tool call (compound bash, branch-name length, a forbidden command shape, a path pattern) — MUST be proposed as a `PreToolUse` hook. "Prefer enforcement over reminders" is the behavioral-rule analogue of "Prefer fixes over diagnostics".
- When a lesson graduates to *any* higher rung (memory / `CLAUDE.md` / `SKILL.md` / hook / script), retire the now-redundant lower-rung bullet in the same run (Step 2.6).

## Enforcement tiers (the shared vocabulary behind the ladder)

The ladder above is an *ascent from weakest to strongest enforcement*. Name the four tiers explicitly — the same vocabulary `spec-to-pr`'s guardrails use (`spec-to-pr/references/past-offenses.md`), so both loops graduate re-offenders in one language:

| Tier | What it means | Ladder rung(s) it maps to |
|---|---|---|
| **Instructional** | prose a session may or may not follow (drifts over long contexts) | `failure-modes checklist`, `memory`, `CLAUDE.md`, `SKILL.md` |
| **Structural** | a format/schema/exit-code contract that makes the wrong thing not *fit* (a JSON schema pin, an exit-code contract, a two-sided scope assertion) | usually a `script` change that enforces a shape, not behavior |
| **Prompted** | a hook that *warns* but lets the tool call through (`exit 0` + stderr message) | `hook / settings.json` — the warn variant |
| **Mechanical** | a hook that *blocks* the tool call (`exit 2`), or a script whose logic can't be bypassed | `hook / settings.json` — the block variant; `script change` |

Two consequences worth stating:
- **When graduating a re-offender to a hook, choose Prompted vs Mechanical deliberately.** A rule whose violation is always wrong and cheaply detectable (a forbidden command shape, a path escape) → **Mechanical** (`exit 2`, block). A rule with legitimate exceptions the hook can't distinguish → **Prompted** (`exit 0` + warning) so it flags without false-blocking. Don't default every graduation to a hard block; match the tier to how absolute the rule is. (This repo's existing hooks already split this way — `block-*` are Mechanical, `warn-*` are Prompted.)
- **The rung enum in the Step-7 log record is unchanged** (`checklist|memory|claude_md|skill_md|hook|script` — a data contract with `aggregate.py`). The tier names are a descriptive overlay on top of it, not a new field.
