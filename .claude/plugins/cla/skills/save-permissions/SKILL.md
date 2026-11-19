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

4. **Merge + write with a small script — NEVER rewrite the full file via Write.**

   The merge is a JSON-list set-union + sort + write. Doing it via the `Write` tool means re-emitting every existing entry token-by-token, which costs latency on a large allowlist when only a handful of lines actually change. Instead, run ONE call.

   Both forms below make the same change to the settings and stop in the same cases; the JSON they write can differ only in spacing and escapes. Use whichever matches the shells this session actually has. On Windows with Git Bash available, either works.

   Bash + Python one-liner:

   ```bash
   python3 -c "
   import json, sys
   from pathlib import Path
   p = Path('.claude/settings.local.json')
   new = ['Skill(...)', 'WebFetch(domain:...)', '...']  # ONLY the new entries from step 3
   try:
       data = json.loads(p.read_text(encoding='utf-8-sig')) if p.exists() else {}
   except ValueError as e:
       sys.exit(f'stopped, nothing written: {p} is not valid JSON ({e})')
   if not isinstance(data, dict):
       sys.exit(f'stopped, nothing written: {p} does not hold a JSON object')
   perms = data.setdefault('permissions', {})
   if not isinstance(perms, dict):
       sys.exit(f'stopped, nothing written: permissions in {p} is not an object')
   allow = perms.setdefault('allow', [])
   if not isinstance(allow, list):
       sys.exit(f'stopped, nothing written: permissions.allow in {p} is not a list')
   perms['allow'] = sorted(set(allow) | set(new))
   t = p.with_name(p.name + '.tmp')
   try:
       t.write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8')
       t.replace(p)
   finally:
       t.unlink(missing_ok=True)
   n = len(perms['allow'])
   print(f'added {len(new)} new permission(s); allowlist now has {n} entries')
   "
   ```

   PowerShell equivalent (if Python is unavailable):

   ```powershell
   $ErrorActionPreference = 'Stop'
   $p = Join-Path (Get-Location).Path '.claude/settings.local.json'
   $new = @('Skill(...)', 'WebFetch(domain:...)')  # ONLY the new entries from step 3
   $raw = if (Test-Path -LiteralPath $p) { Get-Content -LiteralPath $p -Raw -Encoding utf8 } else { '{}' }
   if ($raw -notmatch '^\s*\{') { throw "stopped, nothing written: $p does not hold a JSON object" }
   try { $data = $raw | ConvertFrom-Json } catch { throw "stopped, nothing written: $p is not valid JSON ($_)" }
   if (-not $data.PSObject.Properties['permissions']) { $data | Add-Member -NotePropertyName permissions -NotePropertyValue ([pscustomobject]@{}) }
   $perms = $data.permissions
   if ($perms -isnot [System.Management.Automation.PSCustomObject]) { throw "stopped, nothing written: permissions in $p is not an object" }
   if (-not $perms.PSObject.Properties['allow']) { $perms | Add-Member -NotePropertyName allow -NotePropertyValue @() }
   if ($perms.allow -isnot [array]) { throw "stopped, nothing written: permissions.allow in $p is not a list" }
   $set = [System.Collections.Generic.SortedSet[string]]::new([System.StringComparer]::Ordinal)
   foreach ($e in @($perms.allow) + $new) { [void]$set.Add($e) }
   $perms.allow = @($set)
   $tmp = "$p.tmp"
   try {
     [System.IO.File]::WriteAllText($tmp, ($data | ConvertTo-Json -Depth 20) + "`n", [System.Text.UTF8Encoding]::new($false))
     Move-Item -LiteralPath $tmp -Destination $p -Force
   } finally {
     if (Test-Path -LiteralPath $tmp) { Remove-Item -LiteralPath $tmp -Force }
   }
   "added $($new.Count) new permission(s); allowlist now has $($set.Count) entries"
   ```

   The script is the single source of truth, and both forms take the same steps: load (a missing file counts as empty; a file that is not valid JSON stops the script before anything is written) → create a missing `permissions` object or `allow` list, and stop without writing when either exists with another type (a string `allow` would otherwise be split into single characters) → set-union with the new entries → sort by code point → write a temporary file beside the original and replace the original in one step, deleting the temporary file if the replace fails. Same outcome as a hand-built rewrite, fraction of the tokens. A `stopped, nothing written` message means the file is as it was: show the message to the user and fix the file with them rather than working around the check.

   **Keep the Bash form free of double quotes, `$` and backticks.** Its body uses only single quotes, so the outer `python3 -c "..."` passes it to Python unchanged on Git Bash and Linux. A `"` added inside would end the shell string, and character-code tricks such as `chr(34)` put literal quotes inside a dict key. If the one-liner still fails to paste, run the same body, unchanged, as a quoted heredoc: `python3 - <<'PYEOF'` on the first line, the body, then `PYEOF` alone on the last line. Or use the PowerShell form.

   Do NOT pause for user confirmation before running the script — just run it. **This applies only to exact, non-wildcard entries** (a literal tool name, a literal skill name, an exact path scope actually exercised this session — nothing containing `*`). For **any** wildcard or broad pattern at all — `Bash(*)`, `Bash(rm *)`, `Bash(cp *)`, `Bash(docker *)`, `Bash(sed *)`, or any other `Bash(<command> *)`-shaped entry, regardless of whether the command "looks" destructive — present it as a question and get explicit confirmation before writing it, even if that exact command family was used and worked fine this session. **Do not self-classify a wildcard as "narrow enough to skip asking" — there is no such exemption.** A wildcard is a wildcard; the confirm-before-write rule does not have a destructiveness threshold. Non-destructive-looking wildcards such as `Bash(grep *)`, `Bash(head *)`, `Bash(wc *)` and `Bash(find *)` are covered too: a wildcard grants every future command of that shape. The harness's auto-mode classifier will independently block broad grants regardless of this skill's instructions, and retrying different wildcard phrasings after a block is itself a bad pattern — ask instead of retrying.

   Do NOT use the `Write` tool on `settings.local.json` — that pattern rewrites all untouched entries token-by-token and is wasteful. The merge script is the documented way.

5. After the script writes, optionally tail the file to confirm the new entries landed (e.g. `tail -5 .claude/settings.local.json` in Bash, or `Get-Content .claude/settings.local.json -Tail 5` in PowerShell).
