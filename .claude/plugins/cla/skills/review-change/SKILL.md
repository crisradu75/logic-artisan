---
name: review-change
description: "Pre-implementation review of an OpenSpec change in this repo. Verifies claims, checks symbol/file/reference reality, sizes the change, and either reviews directly (small) or dispatches three parallel agents (large). Aware of the repo's structure via its project-context overlay. Triggers on /cla:review-change or natural language like 'review the openspec change', 'check the change before I implement it'."
argument-hint: "[change-name]"
---

# review-change — pre-implementation review of an OpenSpec change

The full review workflow lives in `references/checklist.md` (single source of truth, also read directly by `/cla:spec-to-pr`'s Review phase).

**Resolving `${CLAUDE_PLUGIN_ROOT}`.** Commands in this skill and its reference
files name plugin files as `${CLAUDE_PLUGIN_ROOT}/...`. That placeholder is this
plugin's install directory, and Claude Code substitutes it into skill content --
but it is **not** an environment variable in the Bash tool. If you ever see the
literal text `${CLAUDE_PLUGIN_ROOT}` in a command you are about to run, resolve
it yourself first; never pass it through to a shell, where an unset variable
expands to nothing and the command silently runs against `/skills/...`.

To resolve it: the harness prepends a `Base directory for this skill: <absolute
path>` line when it loads a skill. The plugin root is that path with the trailing
`/skills/<skill-name>` removed. Failing that, take the absolute path of any file
you have already read from this plugin and cut it at the `.../plugins/cla`
segment. If you cannot establish it either way, say so and stop rather than
guessing a path.

Measured, so you know which half is load-bearing: a `SKILL.md` body arrives with
the placeholder ALREADY substituted, so commands written here are safe. A
`references/` file is opened with `Read`, which returns the raw bytes — the
placeholder arrives literal there, and that is the case this rule exists for.

<<<<<<< HEAD
**Read `${CLAUDE_PLUGIN_ROOT}/skills/review-change/references/checklist.md` and follow it end-to-end.** It defines: change selection, parallel artifact reads, the 12 high-yield verification checks (`0a`–`0l`), the context-brief table format, the size gate (small vs large), the 3-agent dispatch (with full agent prompts), the parallelism analysis, and the final report shape + verdict rubric (READY / FIX FIRST / RETHINK).
=======
**Read `${CLAUDE_PLUGIN_ROOT}/skills/review-change/references/checklist.md` and follow it end-to-end.** It defines: change selection, parallel artifact reads, the 12 high-yield verification checks (`0a`–`0l`), the context-brief table format, the size gate (small vs large), the 3-agent dispatch (with full agent prompts), the parallelism analysis, and the final report shape + verdict rubric (READY / FIX FIRST / RETHINK).
>>>>>>> origin/main

Pass `$ARGUMENTS` (the change name, optional) through to Step 1 of the checklist.

To revise review behavior, edit `references/checklist.md` — do NOT add workflow logic to this shell.
