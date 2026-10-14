# Retiring specs — fold, don't rewrite

Read when a change replaces internal or platform specs (how the tool works inside) with specs of outcomes the owner can see. The old specs are retired, not rewritten requirement by requirement.

## Retire in one change

1. In the change's `.openspec.yaml`, next to `schema:`, set `retire_capabilities: true`.
2. For each spec to retire, write a delta that REMOVES every requirement it holds. Archive then deletes the spec file. Without the flag, archive refuses a delta that removes a spec's last requirement and says so.
3. Fold each outcome the owner can see into an outcome-level spec: ADD it to an existing product spec, or create one. A requirement that only describes how a skill or script works inside is dropped; its rule stays in the skill's files and tests.
4. Every REMOVED block carries **Reason** and **Migration** lines. Migration names the spec and heading that now holds the outcome, or says `None`.

## Removed requirements table

The change's `tasks.md` ends with a `## Removed requirements` section, one group per retired spec. One line per old requirement: its heading, its scenario count, and either `restated in <spec> / <heading>`, `dropped` (with the reason, usually that it described internals), or `pending <later change>` (see below). The count lets a reviewer see that nothing was lost unnoticed.

## Review: the destination text, not just the heading

For each `restated` row, open the destination requirement and read it. It must state the same outcome the old one did, including any rule on money, security, personal data, honesty or accessibility. A heading that exists proves nothing. For each `dropped` row, ask whether the owner could see the behaviour (a limit, a pause, a refusal): if so, it is not internal, and it moves to a destination.

## Pending rows

A `pending` row means the destination is written by another change in the same batch. That change's brief must search the earlier tasks for `pending` rows naming its specs and restate each one. At the end of the batch no `pending` row is left; the final review checks for them.

## Before archiving: format traps

These were reproduced on OpenSpec 1.14.1. Each one makes the old spec text survive or blocks the retirement, and old specs written by hand often have them.

- **Prose after the last scenario** blocks retiring that spec. Archive aborts, quoting the stray text. Prose before a scenario does not block.
- **Bare `### Name` headings** (no `Requirement:` prefix) are not requirements. REMOVED matches nothing, only prints a "treating it as already removed" warning and exits 0, so the old text stays and the ADDED text is appended after it.
- **A bare `---` line** blocks retiring the spec, like stray prose.
- **A table inside a requirement body** blocks retiring it too.
- **A REMOVED heading that names a real requirement must match it exactly**, in case and inner spacing (trailing spaces are tolerated). Unlike a bare heading, which is not a requirement at all and only warns, a mismatch aborts the archive, and `openspec validate` only prints an `Archive would refuse this delta` line and exits 0. Copy the heading from the live spec.

When an old spec has any of these, make the first commit of the batch a mechanical format fix: add the `Requirement:` prefix, delete the `---` lines, turn tables into lists, move stray prose into the Purpose. Compare `openspec show <spec>` before and after; the requirement and scenario counts must not change. Then author the change.
