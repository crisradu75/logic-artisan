# Interpreter probe for every wiring in hooks.json. POSIX sh; sourced, not run.
# The wiring is a postcondition, not a `||` chain — see WHY THE CALLER CHECKS
# $PYEXE below:
#
#   P="${CLAUDE_PLUGIN_ROOT}/hooks/probe-python.sh"; [ -r "$P" ] && . "$P"
#   [ -n "$PYEXE" ] || { echo "cla: ... NOT running" >&2; exit 1; }
#   "$PYEXE" .../some-hook.py
#
# On success it leaves a usable Python 3.8+ in $PYEXE. On failure it prints why
# and `exit 1`s the CALLING shell.
#
# WHY A FILE AND NOT AN INLINE STRING. This probe used to be a 350-char line
# (measured off `main`: `_pyexe` was 350 chars, the probe half of each command
# 349) duplicated into all five wirings plus a `_pyexe` reference copy in the
# same JSON. JSON has no substitution, so the copies were held equal only by a
# test — and they had drifted from the reference once already. Every fix meant a
# six-way edit of an unreadable one-liner, which is how the shape below (three
# ordered stages, each commented) was unwritable before. `hooks.json` names this
# path via ${CLAUDE_PLUGIN_ROOT}, and the existing wiring test that every
# ${CLAUDE_PLUGIN_ROOT} reference resolves on disk now covers it too.
#
# WHY THE CALLER CHECKS $PYEXE INSTEAD OF THIS SCRIPT'S EXIT STATUS. Extracting
# the probe created a failure the inlined form could not have: a probe file that
# is PRESENT but empty or truncated. `.` returns 0 on a zero-byte file, so an
# `|| { ... }` clause never fires, and the wiring runs `"" some-hook.py`.
# Measured — bash, sh and dash all gave rc=127, the tool call proceeded, and the
# only output was `: command not found`, naming neither cla nor the probe. That
# is precisely the silent degradation this probe exists to prevent. A truncated
# `hooks.json` was invalid JSON and loaded nothing; a truncated `.sh` degrades to
# silence, so the caller asserts the POSTCONDITION it actually needs.
#
# The same check fixes a second one: sh and dash abort on a failed `.` and never
# reach a trailing `||` clause, so on the shells Claude Code documents for
# macOS/Linux (`sh -c`) the plugin's own diagnostic was never printed. Guarding
# the source with `[ -r "$P" ]` keeps `.` from failing at all, so every shell
# reaches the same message. Measured across bash, sh and dash: identical output
# and rc=1 for both a missing and a zero-byte probe.
#
# WHY IT RUNS EACH CANDIDATE INSTEAD OF TRUSTING `command -v`. The original form
# was `command -v python3 || command -v py || command -v python`, and on Windows
# that is actively wrong: `python3` commonly resolves to the Store alias stub in
# WindowsApps, which exists and is executable, so `command -v` SUCCEEDS and the
# fallbacks never fire. Every dispatched hook was then invoked through an
# interpreter that cannot run it — the hook exited non-zero with no output, and
# because a PreToolUse hook that fails to run is indistinguishable from one that
# ran and allowed, the entire guard set silently did nothing.
#
# WHY THERE IS A STAGE 3 AT ALL. Observed on one Windows machine while debugging
# a consuming repo: the hook's PATH and the PATH a Bash tool call sees are
# DIFFERENT, and the real interpreter was on the second but not the first. Under
# the hook's PATH, `python3` resolved to a wrapper delegating to `python`, which
# there was the Store alias stub; `py` was absent; `python` was the same stub.
# All three failed the version assertion, so the probe correctly reported that
# nothing was usable and every dispatched hook stopped running.
#
# That PATH capture was not saved, so treat the mechanism as reported rather than
# as evidence in this tree. What IS checkable here today: the WindowsApps stubs
# exist, `py` is absent, and `command -v python3` under the tool PATH resolves to
# a wrapper rather than a real interpreter. The names are the right thing to try
# first and are not sufficient on their own.
#
# NOTE FOR ANYONE TESTING THIS. `test_probe_still_selects_a_working_interpreter`
# can pass while the hooks are dead: it runs the probe under the TEST process's
# PATH, which has a real python on it. A probe that selects an interpreter under
# pytest proves nothing about the interpreter a hook gets. The only evidence that
# counts is a harmless command that MUST be denied, watched being denied, in a
# live session.
#
# WHAT SOURCING LEAKS into the calling shell: the function `_cla_py_ok` and the
# variables `_p` and `_c`, all `_cla`/`_`-prefixed for that reason. NOT `$@` —
# stage 3 runs its `set --` inside a command substitution precisely so the
# caller's positional parameters survive.

PYEXE=

# --- 0. the cache -----------------------------------------------------------
# WHY THIS EXISTS. Stages 1-3 below decide which interpreter to use by RUNNING
# candidates, and that is the whole point — `command -v` cannot tell a real
# Python from the WindowsApps stub. But the answer is stable for the life of a
# machine, and this probe is sourced by EVERY PreToolUse and PostToolUse wiring,
# so the cost is paid per tool call forever.
#
# On a machine where process creation is expensive this dominates everything.
# Reproduce with `for i in $(seq 10); do time python -c pass; done` and compare
# against `time cmd //c exit`: where the second is already ~1.7s, a bare Python
# start measured 1456ms median and the PreToolUse:Bash hook 2710ms — two
# interpreter starts, one here to version-check and one for the dispatcher.
# Caching removes the first. Aggregate the hook's own figure from the
# `durationMs` on `hook_*` attachment lines in `~/.claude/projects/*/*.jsonl`.
#
# WHAT THE KEY COVERS, and why each part is in it. A cache hit skips the version
# assertion, so it must miss whenever the answer could differ:
#   - PATH, because stage 2 resolves candidate NAMES against it. This is the
#     load-bearing one: the probe's own tests poison PATH and require refusal,
#     and a cache keyed without PATH would hand them a good interpreter found
#     under a different one. That is the same class of silent wrong-answer the
#     probe exists to prevent, so it would be a poor trade for latency.
#   - CLA_PYTHON, so an override that changed is re-validated rather than
#     overruled by a stale entry — stage 1 refuses on a bad override precisely so
#     a typo is visible, and a cache must not hide it.
#   - CLA_PY_SEARCH, distinguishing UNSET from SET-BUT-EMPTY, because stage 3
#     reads it with `+set` and empty means "skip stage 3 entirely".
#
# WHAT IT DOES NOT COVER, stated rather than discovered later: an interpreter
# REPLACED IN PLACE by something else at the same path is trusted on `-x` alone
# until PATH or an override changes. That is the one guarantee weakened here.
# Every other staleness — uninstalled, moved, PATH reordered — either fails `-x`
# or misses the key.
#
# The read uses shell builtins only: four `read`s and string compares, no
# process spawned on the hit path, which is the entire point. HOME is used
# rather than a shared temp dir so another local user cannot plant an entry.
# CLA_PROBE_NO_CACHE=1 disables it; CLA_PROBE_CACHE relocates it.
_cla_cache=${CLA_PROBE_CACHE:-"${HOME:-}/.cache/cla/pyexe"}
_cla_key="${CLA_PY_SEARCH+set}:${CLA_PY_SEARCH:-}"
_cla_hit=
if [ -z "${CLA_PROBE_NO_CACHE:-}" ] && [ -r "$_cla_cache" ]; then
  _c_path= _c_exe= _c_over= _c_search=
  { read -r _c_path; read -r _c_exe; read -r _c_over; read -r _c_search; } < "$_cla_cache" 2>/dev/null
  if [ "$_c_path" = "$PATH" ] && [ "$_c_over" = "${CLA_PYTHON:-}" ] \
     && [ "$_c_search" = "$_cla_key" ] && [ -x "$_c_exe" ]; then
    PYEXE=$_c_exe
    _cla_hit=1
  fi
fi

# True iff $1 names a real Python >= 3.8.
#
# The version comes back on STDOUT rather than as an exit code: a bare
# `-c "import sys"` passes on Python 2.7 and on any wrapper that swallows `-c`
# and exits 0. A silent stub prints nothing and fails; a Python 2 has no
# `sys.stdout.buffer`, raises, prints nothing, and fails.
#
# `sys.stdout.buffer.write` and not `print`, because `print` on Windows emits
# `1\r\n` and whether the `\r` survives is up to the shell. Measured on the same
# interpreter: bash and sh strip it, DASH DOES NOT — so under dash the old
# `print`-based check compared `1\r` against `1` and rejected a perfectly good
# Python 3.13, refusing with advice (`Set CLA_PYTHON`) that ran through the same
# check and could not help. A binary write emits one byte and no newline, so
# there is nothing for a shell to disagree about.
_cla_py_ok() {
  [ "$("$1" -c 'import sys; sys.stdout.buffer.write(b"1" if sys.version_info >= (3,8) else b"0")' 2>/dev/null)" = 1 ]
}

# --- 1. explicit override -------------------------------------------------
# The escape hatch, and the answer for any layout stage 3 does not know: pyenv,
# conda, scoop, a company image, a venv. Accepts a path or a bare name. Not a
# security boundary — the version assertion still applies to whatever it names,
# and anyone who can set the environment can already do worse.
#
# An unusable CLA_PYTHON REFUSES rather than falling through to stages 2 and 3.
# Falling through looks kinder and is worse: this variable is what a user reaches
# for BECAUSE the automatic stages already picked wrong, so silently overruling
# it hands every hook the interpreter they were trying to replace, with no signal
# that their override was discarded. A typo must be visible.
if [ -z "$PYEXE" ] && [ -n "${CLA_PYTHON:-}" ]; then
  _p=$(command -v "$CLA_PYTHON" 2>/dev/null) || _p=
  if [ -n "$_p" ] && _cla_py_ok "$_p"; then
    PYEXE=$_p
  else
    echo "cla: CLA_PYTHON=$CLA_PYTHON is not a working Python 3.8+ — guard hooks are NOT running. Fix it or unset CLA_PYTHON to fall back to the search." >&2
    exit 1
  fi
fi

# --- 2. the usual names, on PATH ------------------------------------------
# ORDER is load-bearing and `python3` must stay first, as is the `break`: without
# it the LAST working name wins instead of the first.
if [ -z "$PYEXE" ]; then
  for _c in python3 py python; do
    _p=$(command -v "$_c" 2>/dev/null) || continue
    if _cla_py_ok "$_p"; then PYEXE=$_p; break; fi
  done
fi

# --- 3. known install locations, off PATH ---------------------------------
# Absolute paths only, so a PATH that omits the interpreter's directory (see the
# measurement above) is not fatal. Two different mechanisms make an entry inert,
# and they are not the same: the Windows entries are GLOBS, and an unmatched glob
# stays literal so `-x` fails; the POSIX entries carry no glob at all and are
# skipped simply because `-x` fails on a path that does not exist. (Glob-stays-
# literal is the calling shell's default and would not hold under `nullglob` or
# `failglob`, which a sourced script does not control.) `/c/Program Files/...`
# needs the escaped space: pathname expansion does not re-split its own results,
# so the match survives with the space intact.
#
# CLA_PY_SEARCH replaces this list, and exists mainly so the REFUSAL PATH stays
# testable: three of the six defaults (`/usr/bin/python3`, `/usr/local/bin/...`,
# `/opt/homebrew/...`) are unconditional absolute paths that exist on a normal
# macOS or Linux box, so a test that only poisons PATH still finds an
# interpreter. Stage 3 has to be switched off, not routed around. The test is
# `+set`, not `-n`, so setting it EMPTY suppresses stage 3 entirely while leaving
# it unset keeps the defaults.
#
# The whole stage runs in a command substitution so its `set --` cannot clobber
# the positional parameters of the shell that sourced this file. The `break` is
# load-bearing for the same reason: without it every match is printed and $PYEXE
# becomes the paths concatenated.
#
# `-x` here is a cheap PRE-FILTER, not the gate — `_cla_py_ok` is the gate.
# Relaxing it to `-e` survives a mutation run and that is accepted rather than
# tested: a candidate that exists but is not executable simply fails the version
# check one step later, at the cost of one wasted exec. Recorded so the survivor
# is a decision rather than a gap someone re-discovers.
if [ -z "$PYEXE" ]; then
  PYEXE=$(
    if [ -n "${CLA_PY_SEARCH+set}" ]; then
      # Deliberately unquoted: this is a LIST, and is meant to split and glob.
      set -- $CLA_PY_SEARCH
    else
      set -- "$HOME"/AppData/Local/Programs/Python/Python3*/python.exe \
             /c/Program\ Files/Python3*/python.exe \
             /c/Python3*/python.exe \
             /opt/homebrew/bin/python3 \
             /usr/local/bin/python3 \
             /usr/bin/python3
    fi
    for _p do
      [ -x "$_p" ] || continue
      if _cla_py_ok "$_p"; then printf '%s' "$_p"; break; fi
    done
  )
fi

# --- refusal --------------------------------------------------------------
# FAIL-OPEN IS A DECISION, not an inherited property, and it was re-confirmed
# when this file was reviewed. Claude Code treats exit 2 as the only blocking
# code; exit 1 is a non-blocking error, so the tool call PROCEEDS UNGUARDED and
# the user gets one notice per invocation. Fail-closed (exit 2) was offered and
# declined: a machine with no usable Python would be unable to Edit, Write or run
# Bash at all. The cost accepted in exchange is that `block`-severity guards
# block nothing on exactly the machine where the harness is broken, which is why
# the message has to be loud and has to say what to do.
#
# What is NOT negotiable is that it stays non-zero. This block once said
# "exits 0 (fail-open)" while the code did exit 0 — describing, as intended
# behaviour, exactly the invisible degradation the probe exists to prevent.
# stderr from an exit-0 hook reaches the debug log only, so a machine with no
# usable Python looked protected while running no guards at all.
# `test_probe_announces_failure_and_exits_non_zero` pins the 1; this is the
# sentence a future editor consults before changing it.
#
# `-x` as well as `-n`: a $PYEXE that is set but not executable is the shape a
# CRLF checkout produces on a strict shell, where the first line parses as
# `PYEXE=$'\r'` rather than erroring.
if [ -z "$PYEXE" ] || [ ! -x "$PYEXE" ]; then
  echo "cla: no working python 3.8+ found (tried CLA_PYTHON, python3, py, python, and the usual install paths) — guard hooks are NOT running. Set CLA_PYTHON to your interpreter." >&2
  exit 1
fi

# --- store the answer -------------------------------------------------------
# Only on a MISS: a hit already read this file, and rewriting it every tool call
# would trade the spawn this cache removes for an I/O the hit path avoids.
#
# Written only once the refusal check above has passed, so the file can never
# hold a path that failed the version assertion — which is what lets the hit
# path trust `-x` alone. Every failure here is deliberately silent and
# non-fatal: an unwritable HOME costs the cache, never the probe, and the next
# invocation simply probes again. `mkdir` is the one spawn on this path and it
# runs once per machine.
if [ -z "$_cla_hit" ] && [ -z "${CLA_PROBE_NO_CACHE:-}" ] && [ -n "${HOME:-}${CLA_PROBE_CACHE:-}" ]; then
  ( mkdir -p "${_cla_cache%/*}" 2>/dev/null &&
    printf '%s\n%s\n%s\n%s\n' "$PATH" "$PYEXE" "${CLA_PYTHON:-}" "$_cla_key" \
      > "$_cla_cache" 2>/dev/null ) || :
fi
