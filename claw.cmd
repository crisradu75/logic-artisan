@echo off
REM claw — create a git worktree, THEN launch Claude Code already inside it.
REM
REM Windows counterpart to the POSIX `claw` bash script (macOS/Linux/Git Bash).
REM On native Windows (cmd/PowerShell) typing `claw` runs THIS file. Keep the
REM two in sync.
REM
REM Usage (from anywhere):  path\to\repo\claw <name> [extra claude args...]
REM
REM Why this exists: guard-worktree-isolation.py writes a presence heartbeat at
REM SessionStart for any session whose cwd is the PRIMARY CLONE — before you can
REM type anything. A session that starts there and only then runs
REM /cla:new-worktree has already registered as a contender; after it migrates,
REM the beat stops refreshing but is not removed, and another session working in
REM the primary clone is blocked from committing until it ages out (an hour).
REM A session launched by this script has git_dir != git_common_dir from its
REM first instant, so no heartbeat is ever written and nobody is blocked.
REM
REM NOTE: like cla.cmd, this launches with --permission-mode auto, which bypasses
REM Claude Code's normal per-action confirmation prompts.
REM
REM NOTE: dependencies are NOT installed and gitignored env files are NOT copied
REM — those commands are per-repo facts in new-worktree's project-context.md
REM overlay, so a portable launcher cannot know them. Ask the launched session to
REM finish setup; from inside the worktree that writes no heartbeat.
setlocal enabledelayedexpansion

REM %~dp0 ends with a backslash, so no separator before .claude.
set "PLUGIN_DIR=%~dp0.claude\plugins\cla"
set "WORKTREE_SCRIPT=%PLUGIN_DIR%\skills\new-worktree\scripts\manual_worktree.py"
set "REPO_ROOT=%~dp0."

REM A missing name must NOT fall through to launching in the primary clone —
REM that is precisely what this script exists to avoid.
if "%~1"=="" (
  echo claw.cmd: a worktree name is required. 1>&2
  echo usage: claw ^<name^> [extra claude args...] 1>&2
  echo   ^<name^>  worktree name; becomes .claude\worktrees\^<name^> on branch worktree-^<name^> 1>&2
  exit /b 1
)

REM `claw --help` names a flag where a name belongs. A worktree name can never
REM start with a dash, so treat it as a missing name rather than passing it on.
set "FIRST=%~1"
if "!FIRST:~0,1!"=="-" (
  echo claw.cmd: expected a worktree name, got the flag '%~1'. 1>&2
  echo usage: claw ^<name^> [extra claude args...] 1>&2
  exit /b 1
)

set "NAME=%~1"
shift

REM Collect the REMAINING args by hand. `shift` renumbers %1..%9 but leaves %*
REM holding the ORIGINAL, unshifted command line — so passing %* after a shift
REM would hand the worktree name to `claude` as a trailing positional, which it
REM reads as an initial prompt. Every launch would auto-submit the worktree name
REM as a user turn. Verified: `t.cmd myfeature --resume` yields
REM NAME=[myfeature] STAR=[myfeature --resume].
REM `%1` unquoted (not `%~1`) so the caller's own quoting is preserved.
set "EXTRA="
:collect_args
if "%~1"=="" goto :args_done
set "EXTRA=!EXTRA! %1"
shift
goto :collect_args
:args_done

if not exist "%PLUGIN_DIR%\" (
  echo claw.cmd: plugin directory not found: %PLUGIN_DIR% 1>&2
  echo claw.cmd: expected .claude\plugins\cla next to this script - check it exists 1>&2
  exit /b 1
)
if not exist "%WORKTREE_SCRIPT%" (
  echo claw.cmd: worktree script not found: %WORKTREE_SCRIPT% 1>&2
  exit /b 1
)
where claude >nul 2>nul
if errorlevel 1 (
  echo claw.cmd: 'claude' (the Claude Code CLI) was not found on PATH. 1>&2
  echo claw.cmd: install it, or make sure it's on PATH, then re-run this script. 1>&2
  exit /b 127
)

REM Interpreter probe. Each candidate is RUN before being accepted: on Windows
REM `python3` commonly resolves to the Store alias stub in WindowsApps, which
REM prints nothing, exits non-zero, and would surface later as an unexplained
REM "worktree creation failed". `py` is tried first here because on native
REM Windows it is the launcher that actually exists.
set "PYEXE="
for %%P in (py.exe python.exe python3.exe) do (
  if not defined PYEXE (
    for /f "delims=" %%I in ('where %%P 2^>nul') do (
      if not defined PYEXE (
        "%%I" -c "import sys" >nul 2>nul && set "PYEXE=%%I"
      )
    )
  )
)
if not defined PYEXE (
  echo claw.cmd: no working python interpreter found on PATH (tried py, python, python3). 1>&2
  echo claw.cmd: note a non-functional shim (e.g. the Windows Store python3 alias) is skipped, not used. 1>&2
  exit /b 127
)

REM Creation is delegated, never reimplemented: manual_worktree.py resolves the
REM base branch, validates the name, refuses a duplicate branch with an
REM actionable message, and carries the Windows path-casing fallback. Its
REM --print-path mode puts the bare path on stdout and errors on stderr, so
REM there is no JSON to parse in batch.
set "WORKTREE_PATH="
for /f "usebackq delims=" %%I in (`"%PYEXE%" "%WORKTREE_SCRIPT%" --repo "%REPO_ROOT%" --name "%NAME%" --print-path`) do (
  set "WORKTREE_PATH=%%I"
)
if not defined WORKTREE_PATH (
  echo claw.cmd: worktree creation failed; not launching. 1>&2
  exit /b 1
)
if not exist "%WORKTREE_PATH%\" (
  echo claw.cmd: worktree script reported success but "%WORKTREE_PATH%" is not a directory; not launching. 1>&2
  exit /b 1
)

REM The launched session must use the WORKTREE's own copy of the plugin, not the
REM primary clone's — loading it from outside would put hook-relative paths back
REM in the clone this script is trying to stay out of.
set "WORKTREE_PLUGIN_DIR=%WORKTREE_PATH%\.claude\plugins\cla"
if not exist "%WORKTREE_PLUGIN_DIR%\" (
  echo claw.cmd: the new worktree has no .claude\plugins\cla ^(%WORKTREE_PLUGIN_DIR%^). 1>&2
  echo claw.cmd: is the plugin committed on the base branch? Not launching. 1>&2
  exit /b 1
)

REM `cd` BEFORE announcing anything, and check it. Batch has no `set -e`: a
REM failed `cd` prints an error and CONTINUES, so `call claude` would then run
REM in whatever cwd the user invoked from — usually the primary clone, which
REM writes the SessionStart heartbeat this whole script exists to avoid. The
REM banner also has to come after, or it would name the worktree while the
REM session is actually somewhere else.
cd /d "%WORKTREE_PATH%"
if errorlevel 1 (
  echo claw.cmd: could not enter "%WORKTREE_PATH%"; not launching. 1>&2
  exit /b 1
)

REM Assert the ONE property this launcher promises, rather than assuming the
REM `cd` implied it: a linked worktree has git_dir != git_common_dir. If they
REM are equal we are in the primary clone and must not launch.
for /f "delims=" %%I in ('git rev-parse --absolute-git-dir 2^>nul') do set "GD=%%I"
for /f "delims=" %%I in ('git rev-parse --git-common-dir 2^>nul') do set "GCD=%%I"
if not defined GD (
  echo claw.cmd: could not resolve the git dir after entering the worktree; not launching. 1>&2
  exit /b 1
)
if /i "%GD%"=="%GCD%" (
  echo claw.cmd: cwd resolves to the PRIMARY CLONE, not a linked worktree; not launching. 1>&2
  echo claw.cmd: launching here would write the presence heartbeat this script exists to avoid. 1>&2
  exit /b 1
)

echo claw.cmd: worktree ready at "%WORKTREE_PATH%" 1>&2
echo claw.cmd: dependencies are NOT installed and env files are NOT copied. 1>&2
echo claw.cmd: run /cla:new-worktree in the session to finish setup ^(it detects the existing worktree and runs setup only^). 1>&2
>&2 echo + claude --plugin-dir "%WORKTREE_PLUGIN_DIR%" --permission-mode auto --model sonnet --effort medium!EXTRA!
call claude --plugin-dir "%WORKTREE_PLUGIN_DIR%" --permission-mode auto --model sonnet --effort medium!EXTRA!
REM Capture ERRORLEVEL immediately -- do not insert commands between the claude
REM call and this line, or the real exit code would be lost.
exit /b %ERRORLEVEL%
