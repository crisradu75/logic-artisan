"""Mutation batch for test_cla_launcher.py.

The launchers are the one asset in this repo that ships broken LOUDLY rather than
silently: `cla.cmd` once carried unescaped parentheses in an `echo`, which makes
`cmd.exe` abort the whole script at PARSE time with "was unexpected at this
time". Mutant 1 re-breaks exactly that, and it is the only mutant here that
re-breaks a defect that actually shipped.

**READ THIS BEFORE JUDGING A SURVIVOR — the kills split by platform, and that is
a property of the guard, not a gap in the batch.**

  * Mutants 3 and 4 edit the POSIX `cla` and are killed by TEXT assertions, so
    they die on every platform.
  * Mutants 1 and 2 edit `cla.cmd` and are killed by
    `test_cla_cmd_parses_in_real_cmd`, which carries
    `@pytest.mark.skipif(os.name != "nt")`. **On POSIX that test skips and these
    two mutants will be reported as SURVIVORS.** That is the killing test
    skipping, not a hole in the guard — the same shape as the annotate browser
    suite, which skips without Playwright. Do not "fix" them by deleting them;
    re-run the batch on Windows.

**And a scope-wide skip above that one.** `plugin-tests/tests/launcher/conftest.py`
skips EVERY test in the directory unless the plugin root sits inside a real git
working tree — i.e. unless this is the source checkout rather than a
marketplace-installed copy. In an installed copy the whole batch reports four
survivors and means nothing.

**THE POSIX `cla` IS NEVER EXECUTED BY ANY TEST, ON ANY PLATFORM**, which bounds
this batch hard. Its two guards — missing plugin dir exits 1, `claude` not on
PATH exits 127 — and its `set -euo pipefail` line are asserted by nothing, so no
mutant to its runtime behaviour is killable anywhere. Only the two greps over its
`exec` line can fail, and mutants 3 and 4 are those. The asymmetry is worth
naming: `cla.cmd` has a real end-to-end parse test BECAUSE it shipped broken, and
the same class of defect in `cla` would today be caught by nothing.

**DELIBERATELY NOT MUTANTS:** any change to a flag's VALUE in either launcher —
`--model opus` -> `--model sonnet`, `--permission-mode auto` -> `plan`.
`test_both_cla_launchers_pass_the_same_flag_vector` compares a set of `--`-prefixed
flag NAMES; values are invisible to it and nothing else reads them. Guaranteed
survivors, and a real gap: `--permission-mode auto` is the safety-relevant choice
CLAUDE.md calls out, and it is pinned by no assertion at all.

Run: python3 plugin-tests/mutate.py plugin-tests/mutants/launcher/test_cla_launcher.py
"""

from pathlib import Path

DEV = Path(__file__).resolve().parents[2]
REPO = DEV.parent

CMD = REPO / "cla.cmd"
POSIX = REPO / "cla"

TARGETS = [DEV / "tests" / "launcher" / "test_cla_launcher.py"]

# Mutants 3 and 4 share this anchor. `mutate.py` applies one at a time and
# restores between, so that is fine — but it does mean neither may be widened
# into a multi-line anchor without the other being re-checked.
_EXEC_LINE = (
    'exec claude --plugin-dir "$plugin_dir" --permission-mode auto '
    '--model opus --effort medium "$@"'
)

MUTANTS = [
    (
        # THE HISTORICAL DEFECT, VERBATIM. cmd.exe parses the whole block before
        # running any of it, so unescaped parens inside an echo abort the script
        # before the guard they belong to ever runs.
        "the `^(` escapes come off the not-found echo, so cmd aborts the whole "
        "script at parse time — the shape that shipped and never launched",
        CMD,
        "  echo cla.cmd: 'claude' ^(the Claude Code CLI^) was not found on PATH. 1>&2",
        "  echo cla.cmd: 'claude' (the Claude Code CLI) was not found on PATH. 1>&2",
        TARGETS,
    ),
    (
        "the missing-claude guard stops reporting 127, so a missing CLI is "
        "indistinguishable from an ordinary failure to whoever reads the code",
        CMD,
        "  exit /b 127",
        "  exit /b 1",
        TARGETS,
    ),
    (
        "the POSIX launcher quietly loses a flag, so the two launchers start "
        "different sessions and `keep the two in sync` is a comment nobody enforces",
        POSIX,
        _EXEC_LINE,
        'exec claude --plugin-dir "$plugin_dir" --permission-mode auto --model opus "$@"',
        TARGETS,
    ),
    (
        "the POSIX launcher loses the caller's quoting, so `./cla -p 'two words'` "
        "arrives as two arguments and the launcher rewrites what the user typed",
        POSIX,
        _EXEC_LINE,
        'exec claude --plugin-dir "$plugin_dir" --permission-mode auto '
        "--model opus --effort medium $*",
        TARGETS,
    ),
]
