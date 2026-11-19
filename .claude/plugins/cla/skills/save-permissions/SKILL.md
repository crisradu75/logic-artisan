---
name: save-permissions
description: "Persist every tool permission granted this conversation to .claude/settings.local.json. Run with /cla:save-permissions."
# Slash-command only (writes settings; run on request): keeps this description out of the
# always-loaded skill listing. Nothing invokes it programmatically.
disable-model-invocation: true
---

# Save session permissions

> **Copilot CLI support: unsupported.** This skill edits Claude Code's `.claude/settings.local.json`
> permission state, which Copilot CLI does not use.

Collect every tool permission the user granted during this conversation session and persist them to the project's `.claude/settings.local.json`.

## Steps

1. **Scan the conversation** for every tool call that was executed (approved by the user). Extract the tool name and any scope/pattern from each. Include:
   - `Bash(command)` — save as `Bash(*)` or a tighter pattern like `Bash(git log *)` when the command family recurs
   - `Read(path:...)` — if paths share a common prefix, save as `Read(path:/common/prefix/**)`
   - `Write` / `Edit` — save as-is
   - `Skill(name)` — save with the skill name
   - `WebFetch(domain:...)` — save with the domain
   - `WebSearch` — save as-is
   - `mcp__*` — save the full tool name
   - `Glob(path:...)` — if paths share a common prefix, save as `Glob(path:/common/prefix/**)`
   - Any other tool — save as `ToolName` or `ToolName(scope)` as appropriate

2. **Read** the current settings file at `.claude/settings.local.json` (just to extract the existing `allow` list — do NOT pull all 100+ entries into your reasoning context; you do not need to think about them individually).

3. **Present the diff** to the user: list the NEW permissions (the ones not already in the file). If there are none, say so and stop.

4. **Merge + write with the bundled script — NEVER rewrite the full file via Write.** From the project root, pass ONLY the new entries from step 3, each as its own single-quoted argument (or one per line on stdin, through a quoted heredoc, when an entry holds a single quote):

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/skills/save-permissions/scripts/merge_permissions.py" 'Skill(...)' 'WebFetch(domain:...)'
   ```

   Exit 1 prints `stopped, nothing written: <why>` and leaves the file as it was (a symlinked `.claude/` or settings file is refused this way too): show the message to the user and fix the file with them rather than working around the check. Exit 2 means no usable entry reached the script (none given, one empty once trimmed, or stdin not UTF-8) and nothing was written: re-run it with the entries from step 3.

   Do NOT pause for user confirmation before running the script — just run it. **This applies only to exact, non-wildcard entries** (a literal tool name, a literal skill name, an exact path scope actually exercised this session — nothing containing `*`). For **any** wildcard or broad pattern at all — `Bash(*)`, `Bash(rm *)`, `Bash(cp *)`, `Bash(docker *)`, `Bash(sed *)`, or any other `Bash(<command> *)`-shaped entry, regardless of whether the command "looks" destructive — present it as a question and get explicit confirmation before writing it, even if that exact command family was used and worked fine this session. **Do not self-classify a wildcard as "narrow enough to skip asking" — there is no such exemption.** A wildcard is a wildcard; the confirm-before-write rule does not have a destructiveness threshold. Non-destructive-looking wildcards such as `Bash(grep *)`, `Bash(head *)`, `Bash(wc *)` and `Bash(find *)` are covered too: a wildcard grants every future command of that shape. The harness's auto-mode classifier will independently block broad grants regardless of this skill's instructions, and retrying different wildcard phrasings after a block is itself a bad pattern — ask instead of retrying.

   Do NOT use the `Write` tool on `settings.local.json` — that pattern rewrites all untouched entries token-by-token and is wasteful. The merge script is the documented way.

5. After the script writes, optionally tail the file to confirm the new entries landed (e.g. `tail -5 .claude/settings.local.json` in Bash, or `Get-Content .claude/settings.local.json -Tail 5` in PowerShell).
