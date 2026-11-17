# Prompt audit: logic-artisan Claude Code configuration (2026-11-17)

## Assumptions

- **Target model:** Claude Opus 5.5 (this session). CLA sessions launch on Sonnet (`./cla`), so CLA skill bodies were also read against Sonnet 5.5, and the two helper agents that pin `haiku` against Haiku 5.5.
- **Scope audited:**
  - project `CLAUDE.md`
  - `.claude/skills/release/`
  - the user-level configuration (any edit there affects all projects)
  - the CLA plugin loaded from `.claude/plugins/cla/`: every skill, its references, the helper agents, the output styles, and the rule text that `seed_openspec_rules.py` seeds into each repo
- **Report-only:** CLA is loaded as a plugin, so its hunks are proposals for the owner's trim PRs, not edits to apply here.
- **Skipped:**
  - settings files, `.mcp.json` and credentials (the audit rule)
  - the user-level synced skills, the Anthropic skills synced from claude.ai
  - the plugins installed from the official marketplace; none of these can be edited from here
- **Not applicable:** Groups 3 and 4. The scope holds no tool definitions and no request-building code.

## Highest-impact findings

1. **The review skills still contradict the owner's 2026-11-17 decisions (high).**
   - `spec-to-pr/references/revise.md:126` says "a finding never exits unaddressed", and the review checklist treats every Critical and Important finding as a required fix. There is no filter by stakes and no TODO.md route.
   - A second round and the by-hand mutation check are keyed on severity, not on protected areas: six sites, and the gate is stated twice.
   - multi-lite and multi-spec's review gate repeat the same rules.
   - (B F1-F3; C top 3)
2. **There are three different lists of protected areas (high).**
   - The seeded rules hard-code five areas into every repo (`seed_openspec_rules.py:54`).
   - The Stakes section names a different set.
   - The new authoring brief uses a third.
   - Per-repo stakes should be the one source. (C F7)
3. **Stale facts and contradictions in the files (high):**
   - `new-worktree/SKILL.md:91` starts with a `cd`, which the plugin's own guard blocks.
   - `facts-file.md:33` says no skill reads Stakes, but the brief merged in #510 does.
   - `skill-authoring.md:3` names a moved file.
   - `model-routing.md:49-50` describes agent bodies inaccurately.
   - `new-worktree/SKILL.md:34` cites a memory entry that doesn't exist.
   - (A top 3; C F1)
4. **Text that current models read too literally (medium):**
   - The output style's numeric sentence ceilings and its "play-by-play narration" ban (Group 1f/1d update suppressor).
   - "Fewest possible tool calls" in new-worktree (Group 1d tool-use discouragement).
5. **Duplication and archaeology (medium):**
   - The release section of `CLAUDE.md` restates the `/release` skill, and it loads every session.
   - The release skill carries version-incident stories and a stale "tag 0.10.0" trigger example.
6. **Flag only (conflicts across layers):**
   - Conflicts between this repo's rules and an owner rule outside the repo; detail kept out of the repo with Part D.
   - (D)

Copies of the review-sizing and never-end-a-turn rules agree across files. They are protected by keep-list item 8 and not reported as findings.

## Counts

| Part | Files | High | Medium | Low/flag | Hunks |
|---|---|---|---|---|---|
| A | `_shared`, agents, output styles, 11 small skills | 5 | 18 | 6 | 25 |
| B | spec-to-pr, lite-pr, review-change | 5 | 7 | 5 | 36 |
| C | multi-pr, multi-lite, multi-spec, cla-setup, project-review, seeded rules | 2 | 13 | 3 | 23 |
| D | project CLAUDE.md, /release, user CLAUDE.md | 0 | 13 | 10 | 15 |
| **Total** | | **12** | **51** | **24** | **99** |

By group: Group 1 (dated text) 25, Group 2 (brittle files) 62; Groups 3 and 4 not applicable.

Never-invoked skills in scope: annotate, codify-retro, diagnose, save-permissions, spec-to-pr-retro and sync-context. The audit makes no retirement recommendation; that is the owner's call.

The full findings and diffs follow, part by part.

Part D (the project `CLAUDE.md`, `/release` and the user-level configuration) was kept out of the repo because it quotes a private file; its counts stay in the table above.
