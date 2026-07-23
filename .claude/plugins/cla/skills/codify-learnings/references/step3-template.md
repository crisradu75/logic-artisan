# Step 3 suggestion-list template (full detail)

Read this before drafting the Step 3 suggestion list. `SKILL.md`'s Step 3 stub carries only the correctness-gating rules (numbering, routed + cost-tagged, the hard exclusions, skills-scope limit); this file is the exact shape to reproduce plus the mechanics behind those rules.

## Shape

Produce a markdown list in this shape — **only the suggestions, no preamble**. Omit any heading whose body is empty. Skip session-summary, meta-lessons, and recurring-patterns commentary in the displayed output (they go into the rolling log only, see Step 5).

```markdown
## Lessons learned — {YYYY-MM-DD HH:MM} — scope: {"repo-wide" or subsystem note}

### Suggested edits

#### Docs
1. `[cost: high]` **`{path}`** — {what to add/change} — *(why: {one-line tied to this session})*

#### Slash commands (`.claude/commands/`)
2. `[cost: med]` **`{path}`** — ...

#### Skills (SKILL.md only — no script edits)
3. `[cost: low]` **`{path}`** — ...

#### Hooks / settings
4. `[cost: high]` **`.claude/settings.json`** — ...

### Memory candidates
*(checked against MEMORY.md — duplicates excluded)*
5. `[cost: med]` type: feedback — {one-line rule} — **Why:** ... **How to apply:** ...
```

## Numbering

**Number every suggestion sequentially** across all sections (1, 2, 3, ... continuing through Memory candidates) so the user can reference them by index in Step 4 (e.g. "y 1,3,5").

## The two per-suggestion requirements

- **Routed** — it targets an artifact that satisfies the routing rule (`references/routing.md`). If the natural target is `failure-modes.md`, first ask whether a load-bearing target (memory / `CLAUDE.md` / `SKILL.md` / hook) would prevent the failure instead, and prefer that. A re-offense (Step 2.5) targets one rung *higher* than the artifact that just failed to prevent it.
- **Cost-tagged** — prefixed with `[cost: high|med|low]` = the blast radius of the failure it prevents. `high` = cost many turns, shipped a bug, or corrupted state; `med` = a noticeable detour; `low` = minor friction. Cost drives triage order and escalation priority.

## Hard exclusions — never propose edits to

- `**/scripts/**/*.py` — the skills' own bundled Python tooling.
- `openspec/**` — OpenSpec is an external framework with its own upgrade cycle; never propose changes to its commands, skills, AGENTS.md, config, specs, or any other openspec/ file. This includes both the global OpenSpec and the experimental `opsx:*` variant.
- Any vendored framework directory (anything pulled from an external source with its own release cadence).

Memory writes are always proposals, never automatic — they go through Step 4 like any other suggestion.
