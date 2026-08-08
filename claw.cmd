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
REM overlay, so a portable launcher cannot know them. Run /cla:new-worktree in
REM the launched session to finish setup; it detects the existing worktree and
REM runs setup only.
REM
REM ---------------------------------------------------------------------------
REM Three cmd.exe hazards this file has already been bitten by. Do not "tidy"
REM any of them away without re-running `claw.cmd <name>` on real Windows.
REM
REM 1. PARENTHESES INSIDE A PARENTHESISED BLOCK MUST BE ESCAPED. cmd parses an
REM    `if (...)` block as a unit, so an unescaped `(` in an `echo` inside one
REM    aborts the whole script with `was was unexpected at this time.` — at
REM    PARSE time, whether or not the branch is taken. Shipped broken exactly
REM    this way: every real invocation died, while `claw.cmd` with no args
REM    appeared to work because it exits before cmd reaches the block. Use
REM    `^(` and `^)` in every echo below.
REM
REM 2. DELAYED EXPANSION IS DELIBERATELY OFF. With it on, an argument containing
REM    `!` is mangled: `claw x -p "fix the bug!"` reached claude as
REM    `fix the bug`, and `"wow! amazing! done"` silently lost ` amazing` as an
REM    undefined variable name. `if defined` is a RUNTIME test, so the probes
REM    below still work without it.
REM
REM 3. `shift` DOES NOT AFFECT `%*`. It renumbers %1..%9 and leaves %* holding
REM    the original line, so passing %* after consuming the name handed the
REM    worktree name to claude as a trailing positional — which it reads as an
REM    initial prompt. The args are collected explicitly instead.
REM ---------------------------------------------------------------------------
setlocal disabledelayedexpansion

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
if "%FIRST:~0,1%"=="-" (
  echo claw.cmd: expected a worktree name, got the flag '%~1'. 1>&2
  echo usage: claw ^<name^> [extra claude args...] 1>&2
  exit /b 1
)

set "NAME=%~1"
shift

REM Collect the REMAINING args by hand — see hazard 3 above. `%1` unquoted
REM (not `%~1`) so the caller's own quoting is preserved.
set "EXTRA="
:collect_args
if "%~1"=="" goto :args_done
set "EXTRA=%EXTRA% %1"
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
  echo claw.cmd: 'claude' ^(the Claude Code CLI^) was not found on PATH. 1>&2
  echo claw.cmd: install it, or make sure it's on PATH, then re-run this script. 1>&2
  exit /b 127
)

REM Interpreter probe. Each candidate is RUN before being accepted: on Windows
REM `python3` commonly resolves to the Store alias stub in WindowsApps, which
REM prints nothing, exits non-zero, and would surface later as an unexplained
REM "worktree creation failed". `py` is tried first because on native Windows it
REM is the launcher that actually exists. `if defined` is a runtime test, so
REM this works with delayed expansion off.
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
  echo claw.cmd: no working python interpreter found on PATH ^(tried py, python, python3^). 1>&2
  echo claw.cmd: note a non-functional shim ^(e.g. the Windows Store python3 alias^) is skipped, not used. 1>&2
  exit /b 127
)

REM Creation is delegated, never reimplemented: manual_worktree.py resolves the
REM base branch, validates the name, refuses a duplicate branch with an
REM actionable message, and carries the Windows path-casing fallback. Its
REM --print-path mode puts the bare path on stdout and errors on stderr, so
REM there is no JSON to parse in batch.
REM
REM The whole backquoted command is wrapped in ONE extra quote pair. A backquoted
REM command whose FIRST token is a quoted exe path otherwise makes cmd emit
REM "The filename, directory name, or volume label syntax is incorrect.",
REM leaving WORKTREE_PATH empty so this reports a creation failure that never
REM happened. Only bites when the interpreter path contains a space.
set "WORKTREE_PATH="
for /f "usebackq delims=" %%I in (`""%PYEXE%" "%WORKTREE_SCRIPT%" --repo "%REPO_ROOT%" --name "%NAME%" --print-path"`) do (
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
REM writes the SessionStart heartbeat this whole script exists to avoid.
cd /d "%WORKTREE_PATH%"
if errorlevel 1 (
  echo claw.cmd: could not enter "%WORKTREE_PATH%"; not launching. 1>&2
  exit /b 1
)

REM Assert the ONE property this launcher promises: a linked worktree has
REM git_dir != git_common_dir.
REM
REM CANONICALIZE BOTH FIRST, or this guard is dead code. `--absolute-git-dir` is
REM always absolute and git prints forward slashes; `--git-common-dir` prints a
REM bare RELATIVE `.git` in a primary clone. Measured: `C:/repo/.git` vs `.git`
REM — never string-equal, so the refusal was unreachable in the one state it
REM exists to detect, and the guard read as coverage while providing none.
REM `%%~f` makes both absolute with backslashes, resolving the relative form
REM against the directory just entered. The POSIX twin does the same with
REM `cd ... && pwd`. Normalizing only GCD would leave an absolute FORWARD-slash
REM GD compared against a backslash value, which also never matches — both, or
REM neither.
REM Pre-cleared, like PYEXE and WORKTREE_PATH above. A `for /f` over a command
REM that produces NO output leaves the variable at whatever it already held, so
REM an inherited value from the parent environment satisfies the `if not defined`
REM guards below and feeds stale paths into the primary-clone assertion --
REM turning a fail-closed check into a launch. These were the one variable pair
REM in this file not following the rule the file already applies twice.
set "GD="
set "GCD="
for /f "delims=" %%I in ('git rev-parse --absolute-git-dir 2^>nul') do set "GD=%%I"
for /f "delims=" %%I in ('git rev-parse --git-common-dir 2^>nul') do set "GCD=%%I"
if not defined GD (
  echo claw.cmd: could not resolve the git dir after entering the worktree; not launching. 1>&2
  exit /b 1
)
REM Fail closed: without a common dir the assertion cannot be made at all, and
REM launching unverified is the exact failure this script prevents.
if not defined GCD (
  echo claw.cmd: could not resolve the git common dir; not launching. 1>&2
  exit /b 1
)
for %%A in ("%GD%") do set "GD=%%~fA"
for %%A in ("%GCD%") do set "GCD=%%~fA"
if /i "%GD%"=="%GCD%" (
  echo claw.cmd: cwd resolves to the PRIMARY CLONE, not a linked worktree; not launching. 1>&2
  echo claw.cmd: launching here would write the presence heartbeat this script exists to avoid. 1>&2
  exit /b 1
)

echo claw.cmd: worktree ready at "%WORKTREE_PATH%" 1>&2
echo claw.cmd: dependencies are NOT installed and env files are NOT copied. 1>&2
echo claw.cmd: run /cla:new-worktree in the session to finish setup ^(it detects the existing worktree and runs setup only^). 1>&2
>&2 echo + claude --plugin-dir "%WORKTREE_PLUGIN_DIR%" --permission-mode auto --model sonnet --effort medium%EXTRA%
call claude --plugin-dir "%WORKTREE_PLUGIN_DIR%" --permission-mode auto --model sonnet --effort medium%EXTRA%
REM Capture ERRORLEVEL immediately -- do not insert commands between the claude
REM call and this line, or the real exit code would be lost.
exit /b %ERRORLEVEL%
