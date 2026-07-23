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
REM any cwd.
setlocal
REM %~dp0 ends with a backslash, so no separator before .claude.
set "PLUGIN_DIR=%~dp0.claude\plugins\cla"
REM Print the exact command being run so it's easy to confirm what launches.
echo + claude --plugin-dir "%PLUGIN_DIR%" --permission-mode auto --model sonnet --effort medium %*>&2
claude --plugin-dir "%PLUGIN_DIR%" --permission-mode auto --model sonnet --effort medium %*
exit /b %ERRORLEVEL%
