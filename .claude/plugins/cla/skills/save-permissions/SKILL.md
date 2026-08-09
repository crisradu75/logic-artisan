---
name: save-permissions
description: "Collect every tool permission granted during the current conversation and persist them to .claude/settings.local.json. Triggers on /cla:save-permissions or natural language like 'save my permissions', 'persist allowed tools', 'reduce permission prompts for next session'."
---

# Save session permissions

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

4. **Merge + write with a small script — NEVER rewrite the full file via Write.**

   The merge is a JSON-list set-union + sort + write. Doing it via the `Write` tool means re-emitting every existing entry token-by-token, which costs latency on a large allowlist when only a handful of lines actually change. Instead, run ONE call.

   Both forms below produce the identical result — use whichever matches the shells this session actually has. On Windows with Git Bash available, either works.

   Bash + Python one-liner:

   ```bash
   python3 -c "
   import json
   from pathlib import Path
   p = Path('.claude/settings.local.json')
   data = json.loads(p.read_text(encoding='utf-8')) if p.exists() else {'permissions': {'allow': []}}
   new = ['Skill(...)', 'WebFetch(domain:...)', '...']  # ONLY the new entries from step 3
   data['permissions']['allow'] = sorted(set(data['permissions']['allow']) | set(new))
   p.write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8')
   print(f'added {len(new)} new permission(s); allowlist now has {len(data[\"permissions\"][\"allow\"])} entries')
   "
   ```

   PowerShell equivalent (if Python is unavailable):

   ```powershell
   $p = '.claude/settings.local.json'
   $data = if (Test-Path $p) { Get-Content $p -Raw | ConvertFrom-Json } else { [pscustomobject]@{ permissions = [pscustomobject]@{ allow = @() } } }
   $new = @('Skill(...)', 'WebFetch(domain:...)')  # ONLY the new entries from step 3
   $merged = @($data.permissions.allow + $new | Sort-Object -Unique)
   $data.permissions.allow = $merged
   $data | ConvertTo-Json -Depth 20 | Set-Content $p -Encoding utf8
   "allowlist now has $($merged.Count) entries"
   ```

   The script is the single source of truth: load → set-union with the new entries → sort → atomic write. Same outcome as a hand-built rewrite, fraction of the tokens.

   **In the Bash form, use the `\"key\"` escape verbatim.** On Git Bash the `\"permissions\"`/`\"allow\"` escapes inside the outer `python3 -c "..."` work correctly — DO NOT substitute `chr(34)` / `chr(39)` / other character-code tricks (they end up putting literal quotes inside the dict key and crash with `KeyError`). If escaping ever fails on a copy-paste run, switch to a heredoc form (`python3 << 'PYEOF'`) or use the PowerShell variant — never invent character-code workarounds.

   Do NOT pause for user confirmation before running the script — just run it. **This applies only to exact, non-wildcard entries** (a literal tool name, a literal skill name, an exact path scope actually exercised this session — nothing containing `*`). For **any** wildcard or broad pattern at all — `Bash(*)`, `Bash(rm *)`, `Bash(cp *)`, `Bash(docker *)`, `Bash(sed *)`, or any other `Bash(<command> *)`-shaped entry, regardless of whether the command "looks" destructive — present it as a question and get explicit confirmation before writing it, even if that exact command family was used and worked fine this session. **Do not self-classify a wildcard as "narrow enough to skip asking" — there is no such exemption.** A wildcard is a wildcard; the confirm-before-write rule does not have a destructiveness threshold. (Recurred once already on 2026-07-11 with `Bash(rm *)`/`Bash(cp *)`; recurred again on 2026-07-16 when several non-destructive-looking wildcards — `Bash(docker *)`, `Bash(sed *)`, `Bash(grep *)`, `Bash(head *)`, `Bash(wc *)`, `Bash(find *)` — were judged "narrow" and nearly written unprompted, caught only by the harness's auto-mode classifier.) The harness's auto-mode classifier will independently block broad grants regardless of this skill's instructions, and retrying different wildcard phrasings after a block is itself a bad pattern — ask instead of retrying.

   Do NOT use the `Write` tool on `settings.local.json` — that pattern rewrites all untouched entries token-by-token and is wasteful. The merge script is the documented way.

5. After the script writes, optionally tail the file to confirm the new entries landed (e.g. `tail -5 .claude/settings.local.json` in Bash, or `Get-Content .claude/settings.local.json -Tail 5` in PowerShell).
