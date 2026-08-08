@echo off
REM cla — launch Claude Code with the cla (Cris Logic Artisan) harness plugin
REM loaded in-place, so the /cla:* skills and the guard hooks are active.
REM
REM Windows counterpart to the POSIX `cla` bash script (macOS/Linux/Git Bash).
REM On native Windows (cmd/PowerShell) typing `cla` runs THIS file; on macOS/Linux
REM it runs the extension-less `cla`. Keep the two in sync.
REM
REM Usage (from anywhere):  path\to\repo\cla [extra claude args...]
REM The plugin path is resolved relative to THIS script (%~dp0), so it works from
REM any cwd -- but NOT through a symlink/junction pointing at this file.
REM
REM NOTE: this launches with --permission-mode auto, which bypasses Claude Code's
REM normal per-action confirmation prompts. That's intentional for this harness,
REM but worth knowing before you run it.
setlocal
REM %~dp0 ends with a backslash, so no separator before .claude.
set "PLUGIN_DIR=%~dp0.claude\plugins\cla"
if not exist "%PLUGIN_DIR%\" (
  echo cla.cmd: plugin directory not found: %PLUGIN_DIR% 1>&2
  echo cla.cmd: expected .claude\plugins\cla next to this script - check it exists 1>&2
  exit /b 1
)
where claude >nul 2>nul
if errorlevel 1 (
REM The ^( ^) escapes are load-bearing, not cosmetic. cmd parses a parenthesised
REM block as ONE unit before executing any of it, so a bare `(` inside this echo
REM aborts the whole script at PARSE time with "was was unexpected at this
REM time." -- whether or not the branch is ever taken. This file shipped exactly
REM that way and never launched on native Windows; `claw.cmd` carries the same
REM hazard note because it shipped broken the same way first. Verified in real
REM cmd.exe: unescaped gives EXIT=255 and no launch.
  echo cla.cmd: 'claude' ^(the Claude Code CLI^) was not found on PATH. 1>&2
  echo cla.cmd: install it, or make sure it's on PATH, then re-run this script. 1>&2
  exit /b 127
)
REM Print the exact command being run so it's easy to confirm what launches.
>&2 echo + claude --plugin-dir "%PLUGIN_DIR%" --permission-mode auto --model sonnet --effort medium %*
call claude --plugin-dir "%PLUGIN_DIR%" --permission-mode auto --model sonnet --effort medium %*
REM Capture ERRORLEVEL immediately -- do not insert commands between the claude
REM call and this line, or the real exit code would be lost.
exit /b %ERRORLEVEL%
