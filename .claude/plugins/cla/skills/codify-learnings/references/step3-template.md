# Step 3 suggestion-list template (full detail)

Read this before drafting the Step 3 suggestion list. `SKILL.md`'s Step 3 stub carries only the correctness-gating rules (numbering, routed, benefit-led, the hard exclusions, skills-scope limit); this file is the exact shape to reproduce plus the mechanics behind those rules.

**This shape replaced an earlier `[cost: high|med|low]`-tagged, category-header-heavy version** after direct user feedback that it read as "a wall of text full of details that are hard to parse; there is no clear benefit highlighted for every change" — the fix was priority ordering plus a stated plain-language benefit per item, not a jargon tag. Don't regress to the old shape. (If this shape is ever revised again, replace this paragraph rather than appending a second one — one line of "this is why the current shape looks like this" is enough context; a stack of superseded-format histories is clutter, not precedent.)

## Shape

Produce a flat, numbered markdown list in this shape — **only the suggestions, no preamble, no category headers**, aside from the one allowed status line below. Order by payoff, most valuable first. Skip session-summary, meta-lessons, and recurring-patterns commentary in the displayed output (they go into the rolling log only, see Step 5).

```markdown
## Lessons learned — {YYYY-MM-DD HH:MM} — scope: {"repo-wide" or subsystem note}

*(optional: one italic status line, e.g. "memory dedup skipped (index not found)" — omit when nothing to report)*

**1. {short imperative title}** (`{path}`) — {the concrete fix, one line}. *Benefit: {plain-language payoff — what this saves next time}.*

**2. {short imperative title}** (`{path}`) — ...

**{N}. Memory: {short title}** (type: {user|feedback|reference}) — {one-line rule}. **How to apply:** {when/where this kicks in}. *Benefit: {plain-language payoff}.*
```

Each item is self-contained: title, target path inline (not as a section header), the fix itself, and a benefit sentence that names the concrete payoff — not a restated version of the fix. If you can't state a benefit in one plain sentence without jargon, the suggestion probably isn't concrete enough yet.

## Numbering and ordering

**Number every suggestion sequentially, ordered by payoff (most valuable first)**, across the whole list — memory candidates sort into that same payoff order, not pinned to the end — so the user can reference them by index in Step 4 (e.g. "y 1,3,5"). Don't group by artifact type (docs/skills/hooks/memory); a flat priority order reads faster than category-sorted sections and is what the user actually wants to see first.

## The per-suggestion requirement

- **Routed** — it targets an artifact that satisfies the routing rule (`references/routing.md`). If the natural target is `failure-modes.md`, first ask whether a load-bearing target (memory / `CLAUDE.md` / `SKILL.md` / hook) would prevent the failure instead, and prefer that. A re-offense (Step 2.5) targets one rung *higher* than the artifact that just failed to prevent it.
- **Benefit-led, not cost-tagged.** State what concretely improves next time in one plain sentence — "skip re-diagnosing a failure that hit N times this session" beats "[cost: med]". If you're tempted to write a cost/severity tag, translate it into the concrete thing it would have saved instead.

## Hard exclusions — never propose edits to

- `**/scripts/**/*.py` — the skills' own bundled Python tooling.
- `openspec/**` — OpenSpec is an external framework with its own upgrade cycle; never propose changes to its commands, skills, AGENTS.md, config, specs, or any other openspec/ file. This includes both the global OpenSpec and the experimental `opsx:*` variant.
- Any vendored framework directory (anything pulled from an external source with its own release cadence).

Memory writes are always proposals, never automatic — they go through Step 4 like any other suggestion.
