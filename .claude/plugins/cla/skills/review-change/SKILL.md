---
name: review-change
description: "Pre-implementation review of an OpenSpec change: verify its claims and file and symbol references, size it, then review directly (small) or with three parallel agents (large). Triggers: /cla:review-change, 'review the openspec change', 'check the change before I implement it'."
argument-hint: "[change-name]"
---

# review-change — pre-implementation review of an OpenSpec change

The full review workflow lives in `references/checklist.md` and, for a large change's agent prompts, `references/dispatch.md` (the single source of truth, also read directly by `/cla:spec-to-pr`'s Review phase).

**Resolving `${CLAUDE_PLUGIN_ROOT}`.** This `SKILL.md` arrives with the placeholder substituted, but a
`references/` file opened with `Read` carries it literally, and it is not an environment variable in
Bash — an unset variable silently runs the command against `/skills/...`. Before running a command
that contains the literal text, replace it with the plugin root: the `Base directory for this skill`
path with `/skills/<name>` removed, or the absolute path of any plugin file you have read, cut
at `.../plugins/cla`. If neither works, say so and stop. Detail:
`${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/plugin-root.md`.

**Read `${CLAUDE_PLUGIN_ROOT}/skills/review-change/references/checklist.md` and follow it end-to-end.** It defines: change selection, parallel artifact reads, the 12 high-yield verification checks (`0a`–`0l`), the context-brief table format, the size gate (small vs large), the 3-agent dispatch (pointer to `references/dispatch.md`, read only for a large change), the weight and proof checks, and the final report shape + verdict rubric (READY / FIX FIRST / RETHINK).

Pass `$ARGUMENTS` (the change name, optional) through to Step 1 of the checklist.

To revise review behavior, edit `references/checklist.md` (or `references/dispatch.md` for the dispatched agents) — do NOT add workflow logic to this shell.
