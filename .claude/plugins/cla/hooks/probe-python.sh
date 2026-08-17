# Interpreter probe for every wiring in hooks.json. POSIX sh; sourced, not run:
#
#   . "${CLAUDE_PLUGIN_ROOT}/hooks/probe-python.sh"; "$PYEXE" .../some-hook.py
#
# On success it leaves a usable Python 3.8+ in $PYEXE. On failure it prints why
# and `exit 1`s the CALLING shell, so no wiring can proceed with $PYEXE unset.
#
# WHY A FILE AND NOT AN INLINE STRING. This probe used to be a single ~500-char
# line duplicated into all five wirings plus a `_pyexe` reference copy in the
# same JSON. JSON has no substitution, so the copies were held equal only by a
# test — and they had drifted from the reference once already. Every fix meant a
# six-way edit of an unreadable one-liner, which is how the shape below (three
# ordered stages, each commented) was unwritable before. `hooks.json` names this
# path via ${CLAUDE_PLUGIN_ROOT}, and the existing wiring test that every
# ${CLAUDE_PLUGIN_ROOT} reference resolves on disk now covers it too.
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
# WHY THE CHECK IS A VERSION AND NOT LIVENESS. A bare `-c "import sys"` passes
# on Python 2.7 and on any wrapper that swallows `-c` and exits 0. Asserting the
# version via STDOUT rejects both: a silent stub prints nothing, a Python 2
# prints 0.
#
# WHY THERE IS A STAGE 3 AT ALL. Measured on one Windows machine, not assumed:
# the hook's PATH and the PATH a Bash tool call sees are DIFFERENT, and the real
# interpreter is on the second but not the first. Under the hook's PATH,
# `python3` resolved to a wrapper delegating to `python`, which there was the
# Store alias stub; `py` was absent; `python` was the same stub. All three failed
# the version assertion, so the probe correctly reported that nothing was usable
# and every dispatched hook stopped running. The names are the right thing to try
# first and are not sufficient on their own.
#
# NOTE FOR ANYONE TESTING THIS. `test_probe_still_selects_a_working_interpreter`
# can pass while the hooks are dead: it runs the probe under the TEST process's
# PATH, which has a real python on it. A probe that selects an interpreter under
# pytest proves nothing about the interpreter a hook gets. The only evidence that
# counts is a harmless command that MUST be denied, watched being denied, in a
# live session.

PYEXE=

# True iff $1 names a real Python >= 3.8. Prefixed because sourcing leaks it into
# the calling shell.
_cla_py_ok() {
  [ "$("$1" -c 'import sys; print(1 if sys.version_info >= (3,8) else 0)' 2>/dev/null)" = 1 ]
}

# --- 1. explicit override -------------------------------------------------
# The escape hatch, and the answer for any layout stage 3 does not know: pyenv,
# conda, scoop, a company image, a venv. Accepts a path or a bare name. Not a
# security boundary — the version assertion still applies to whatever it names,
# and anyone who can set the environment can already do worse.
if [ -n "${CLA_PYTHON:-}" ]; then
  _p=$(command -v "$CLA_PYTHON" 2>/dev/null) && _cla_py_ok "$_p" && PYEXE=$_p
fi

# --- 2. the usual names, on PATH ------------------------------------------
# ORDER is load-bearing and `python3` must stay first.
if [ -z "$PYEXE" ]; then
  for _c in python3 py python; do
    _p=$(command -v "$_c" 2>/dev/null) || continue
    if _cla_py_ok "$_p"; then PYEXE=$_p; break; fi
  done
fi

# --- 3. known install locations, off PATH ---------------------------------
# Absolute paths only, so a PATH that omits the interpreter's directory (see the
# measurement above) is not fatal. An unmatched glob stays literal, `-x` is then
# false, and the entry is skipped — so the Windows entries are inert on macOS and
# the POSIX ones are inert on Windows. `/c/Program Files/...` needs the escaped
# space: pathname expansion does not re-split its own results, so the match
# survives with the space intact.
#
# CLA_PY_SEARCH replaces this list, and exists mainly so the REFUSAL PATH stays
# testable: two probe tests poison PATH and assert the probe finds nothing, which
# a $HOME-rooted fallback defeats. Clearing the environment does not help, since
# the shell supplies HOME from the passwd entry when it is absent. The test is
# `+set`, not `-n`, so setting it EMPTY suppresses stage 3 entirely while leaving
# it unset keeps the defaults.
if [ -z "$PYEXE" ]; then
  if [ -n "${CLA_PY_SEARCH+set}" ]; then
    # Deliberately unquoted: this argument is a list, and is meant to split and glob.
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
    if _cla_py_ok "$_p"; then PYEXE=$_p; break; fi
  done
fi

# --- refusal --------------------------------------------------------------
# NON-ZERO is deliberate. This block once said "exits 0 (fail-open)" while the
# code did exit 0 — describing, as intended behaviour, exactly the invisible
# degradation the probe exists to prevent. stderr from an exit-0 hook reaches the
# debug log only, so a machine with no usable Python looked protected while
# running no guards at all. `test_probe_announces_failure_and_exits_non_zero`
# pins the 1; this is the sentence a future editor consults before changing it.
if [ -z "$PYEXE" ]; then
  echo "cla: no working python 3.8+ found (tried CLA_PYTHON, python3, py, python, and the usual install paths) — guard hooks are NOT running. Set CLA_PYTHON to your interpreter." >&2
  exit 1
fi
