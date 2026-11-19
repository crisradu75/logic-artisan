#!/usr/bin/env python3
"""PreToolUse dispatcher for the Bash and PowerShell matchers.

Both shells are wired to this one dispatcher because every hook below reads
`tool_input.command` and matches on the COMMAND SHAPE, not on shell syntax —
`git push --force origin x` is the same text either way. PowerShell is this
harness's primary shell on Windows, and it previously ran exactly one of these
hooks, so a force-push, a push straight to main, or a wrong-identity commit
issued through it bypassed every git guard in the tree.

Runs block-cd-in-bash, ask-destructive-git, block-unsafe-recursive-delete,
block-dishonest-commit, guard-bash-text, ask-broad-git-add, ask-staged-debug-tag,
warn-stacked-pr-merge, warn-stray-scratch-artifact, warn-heredoc-escape-mangling
and warn-lossy-merge-resolution in ONE Python process instead of eleven, reading
the tool-call JSON from stdin once and handing it to each in turn via
`_dispatch_lib`. Cuts per-Bash-call hook overhead from 11 interpreter spawns to
1 — commonly cited as ~100-200ms of process-start cost each on Windows, though
not independently benchmarked for this repo.

Pushes to main/master are NOT guarded here. That check moved to `git/pre-push`,
which git hands the resolved refspec — no command string to parse, so none of
the `git.exe` / `-C` / quoting spellings that defeated the old hook can reach
it differently. See that file's header.

Each sibling hook file is untouched and still independently runnable/importable
exactly as before (loaded here via the same importlib technique the test suite
uses) — this file only orchestrates them; it holds no hook logic of its own.

Order and semantics preserved exactly, except two behaviours: an oversize command
asks before any guard runs, and a guard sees what a shell wrapper hands on.
  - A command longer than `MAX_SCANNED_COMMAND_CHARS` runs NO guard: the dispatcher
    answers with one `ask` naming its size and the cap, before the first hook.
  - WRAPPED FORMS. Before the first hook, `_shell_read.guard_parts` reads the
    command once: each shell wrapper's body (`bash -c "..."`, `sh -c`, `eval
    "..."`, `pwsh -Command`, `Invoke-Expression`, `cmd /c`, nested up to three
    deep) becomes an extra PART: the command the wrapper's shell runs, its own
    option words dropped (`bash -c 'cp a ../b'` is `cp a ../b`). Heredoc text is
    data but for an unquoted body's `$(...)` and backticks, and a wrapper behind
    a remote runner (`docker exec`, `ssh <host>`, ...) is not read, since its
    body does not run here; `_shell_read.py` names the rules. Every guard
    except those in `_READS_COMMAND_ONLY` then runs on the command and again on
    each part, as if the part had been typed bare, so `bash -c "echo hi > ../x"`
    asks and `eval 'git commit -m "Measured-by: none"'` blocks like their bare
    forms. The parts are handed on whole, one run
    each, not joined: a quote left open in one part cannot pair with one in the
    next. Same order, same precedence: the first block wins, asks and warnings
    from every run merge (a repeated text once). A skippable hook's runs each
    need room in the budget, like its first. When the reading raises, stops at
    a cap, or the command plus its parts would pass `MAX_SCANNED_COMMAND_CHARS`,
    the call asks (`_unread_parts_ask`) on top of what the guards decide, since
    part of what the wrapper runs went unchecked. `ask-destructive-git.py`
    reads its own cached expansion and keeps its own asks for what it could
    not read, with reasons unchanged.
  - Any hook returning 2 blocks: its stderr message is shown, prefixed with any
    non-blocking warning text already produced by an earlier hook in this same
    run (not silently dropped), then this process exits 2.
  - If none block but one requests an `ask` escalation (ask-destructive-git.py
    returns 0 and escalates via stdout), the merged decision is re-emitted as
    this process's own stdout JSON. Only one process's stdout is read per call,
    so a child's decision that isn't re-emitted here is silently downgraded to
    an allow. Precedence is deny > ask > allow, matching the documented
    permission evaluation order.
  - If none block, EVERYTHING non-blocking leaves as one stdout JSON object at
    exit 0: `permissionDecision` for an ask, `additionalContext` for advisory
    text — e.g. from warn-stacked-pr-merge.py / warn-stray-scratch-artifact.py.

    This is the only channel that works. Per the documented contract, stderr
    from a hook exiting 0 goes to the debug log and Claude never sees it, so
    writing a warning there delivers it to nobody; and a non-zero exit discards
    stdout entirely while surfacing only the FIRST LINE of stderr, which for
    merged multi-hook output is rarely the useful one. The dispatcher therefore
    never exits non-zero on the non-blocking path — doing so would report LESS.
  - If a hook failed to load or crashed, that's isolated to just that hook
    (the rest still run — see `_dispatch_lib.run_hook_file`) and the failure is
    reported as additionalContext, where it arrives whole.
  - If too little handler budget remains for an ADVISORY or BEST-EFFORT hook's
    own worst case, it is skipped and named in the DEBUG LOG — not in context. That skip is the
    mechanism working as designed (advisory means the loss is acceptable), and
    routine notices on the session's hottest path train the channel to be
    ignored. Enforcing hooks are never skipped at all: a late block still
    blocks, but a block dropped to a handler kill is a silent failure. See
    `_dispatch_lib.Deadline` and `HOOK_WORST_CASE_SECONDS`.
  - Both channels are capped to Claude Code's hook output limit, with a blocking
    hook's reason (or an ask's) budgeted ahead of any advisory text.
"""

from __future__ import annotations

import json
import sys

# Guarded, because every guard this dispatcher runs goes through the library: an
# import failure left uncaught exits 1, which Claude Code treats as a non-blocking
# error, so every block and ask would silently become an allow. `_fail_closed`
# below turns that, and a crash in `main()`, into an `ask` instead.
try:
    from _dispatch_lib import (
        HOOK_WORST_CASE_SECONDS,
        Deadline,
        compose_output,
        fit_json_payload,
    )
    from _dispatch_lib import run_hook_file_each
    # One definition for both dispatchers; the name stays for their callers.
    from _dispatch_lib import extract_ask as _extract_ask
except Exception as _exc:  # noqa: BLE001 -- any load failure must fail closed
    _LIB_ERROR: Exception | None = _exc
else:
    _LIB_ERROR = None

# Guarded on its own: when the shell reading cannot load, the guards still run
# on the command alone, and `ask-destructive-git.py`, which imports the same
# module, fails to load and asks as an enforcing hook that could not run.
try:
    from _shell_read import guard_parts as _guard_parts
except Exception:  # noqa: BLE001 -- see above
    _guard_parts = None

# True after `main()` or `_fail_closed` asked because a guard could NOT run on
# this call (an enforcing hook that failed to load or crashed, or the library
# itself), as opposed to a guard that ran and asked. Claude Code reads only the
# JSON, where both are the same `ask`; the Copilot adapter loads this module,
# calls `main()` and reads this flag to turn an unchecked call into a deny,
# instead of matching words in the reason. Not in the JSON, because Claude Code
# validates that object and a key it does not know is a risk to the ask itself.
GUARD_NOT_RUN = False

# Longest command, counted in the characters Python decodes from stdin (what the
# guards' regexes scan, so the cost driver), that the guards scan. On Windows piped
# stdin can decode as cp1252 (hooks.json passes no `-X utf8`), so raw UTF-8 non-ASCII
# text can count as more than its own character count; that errs toward asking.
# Claude Code kills a hook at the 15 s `timeout` in hooks.json and a killed
# hook lets the command through. Guard cost grows linearly with size: the slowest
# hostile shape measured (a `;` chain) took 3.85 s at 500,000 characters and about
# 7.5 s at 1,000,000 on Windows/Git Bash, so 500,000 keeps a 3x slower or loaded
# machine under 15 s. The longest real command in 67,231 local transcripts was
# 25,270 characters, 20x below the cap. Over it, the dispatcher asks, unscanned.
MAX_SCANNED_COMMAND_CHARS = 500_000

_HOOK_FILES = [
    "block-cd-in-bash.py",
    "ask-destructive-git.py",
    "block-unsafe-recursive-delete.py",
    "block-dishonest-commit.py",
    "guard-bash-text.py",
    "ask-broad-git-add.py",
    "ask-staged-debug-tag.py",
    "warn-stacked-pr-merge.py",
    "warn-stray-scratch-artifact.py",
    "warn-heredoc-escape-mangling.py",
    "warn-lossy-merge-resolution.py",
]

# Hooks that can only ever warn, and so may be dropped when too little handler
# budget remains for them. Every hook that changes the OUTCOME of the call — one
# that can return 2, plus `ask-destructive-git.py`, which returns 0 but escalates
# to a permission prompt via stdout — is deliberately absent from this set AND
# ordered ahead of them in `_HOOK_FILES`, so budget pressure costs warnings
# before it can cost enforcement. Note the ask hook is why the wiring test cannot
# key on `return 2` alone: skipping it would silently downgrade an ask to an
# allow, an enforcement loss no exit code would reveal. The one named exception
# is `_BEST_EFFORT_HOOKS` below.
_ADVISORY_HOOKS = frozenset({
    "warn-stacked-pr-merge.py",
    "warn-stray-scratch-artifact.py",
    "warn-heredoc-escape-mangling.py",
    "warn-lossy-merge-resolution.py",
})

# Hooks that CAN escalate to an ask but are best-effort by their own design: each
# allows the call silently whenever its check cannot run (no git, a git timeout,
# an error). Skipping one under budget pressure is therefore the same outcome as
# its own probe timing out, so the dispatcher treats it like an advisory hook for
# the budget and for a load failure (reported as context, not escalated), while
# re-emitting its ask like any other. Kept apart from `_ADVISORY_HOOKS` so the
# wiring test's "no outcome-changing hook is advisory" rule still holds for every
# hook not named here, and ordered ahead of the advisory hooks so warnings are
# what budget pressure costs first.
#
# `ask-broad-git-add.py` and `ask-staged-debug-tag.py` are here because, when
# they were added, the enforcing hooks above spent the whole budget
# (`HOOK_WORST_CASE_SECONDS`). Since `ask-destructive-git.py`'s probes share one
# 6s deadline, 6s of it is free, but only for ONE more enforcing hook with git
# calls that reads the command alone and is listed in `_READS_COMMAND_ONLY`
# below. Any other hook runs once per wrapper part as well, with no cap on the
# part count, and an enforcing one is never skipped, so it must spawn nothing
# (`test_per_part_enforcing_hooks_spawn_nothing` in `test_hooks_wiring.py`).
# Neither of these two reads the command alone (each checks a `git add` or
# `git commit` inside `bash -c` too), so making one enforcing means giving it one
# deadline across all its parts first. (The text-only half of the commit
# checks, `block-dishonest-commit.py`, costs nothing and is enforcing.)
_BEST_EFFORT_HOOKS = frozenset({
    "ask-broad-git-add.py",
    "ask-staged-debug-tag.py",
})
_SKIPPABLE_HOOKS = _ADVISORY_HOOKS | _BEST_EFFORT_HOOKS

# Guards that read the command alone, not the parts `_shell_read.guard_parts` finds.
# `block-cd-in-bash.py` polices the SESSION shell's directory, which a wrapper's
# child shell (`bash -c "cd sub && make"`) does not change; its own docstring
# allows a subshell for the same reason. Named miss: `eval "cd x"` does change
# it, and is not read. `ask-destructive-git.py` reads the same cached expansion
# itself (`_scan`), joined so its checks see every part at once, and owns the
# asks for what could not be read. Being listed here is also what lets an
# enforcing hook spend from the budget: one that is not runs per part, and must
# cost 0.0 in `HOOK_WORST_CASE_SECONDS`. `warn-lossy-merge-resolution.py` is
# advisory and reads the wrapper bodies itself (`guard_parts`, cached), so its
# git calls run once per command on one shared deadline rather than once per
# part.
_READS_COMMAND_ONLY = frozenset({"block-cd-in-bash.py", "ask-destructive-git.py", "warn-lossy-merge-resolution.py"})


def _oversize_ask(stdin_text: str) -> str | None:
    """The ask reason when the command is longer than `MAX_SCANNED_COMMAND_CHARS`, else None.

    Reads only `tool_input.command`, the same field every guard reads. Unparseable
    input or a missing command returns None: the guards already handle those.
    """
    try:
        payload = json.loads(stdin_text)
    except (ValueError, RecursionError):  # deeply nested input: leave it to the guards
        return None
    tool_input = payload.get("tool_input") if isinstance(payload, dict) else None
    command = tool_input.get("command") if isinstance(tool_input, dict) else None
    if not isinstance(command, str) or len(command) <= MAX_SCANNED_COMMAND_CHARS:
        return None
    return (
        f"this command is {len(command):,} characters, over the {MAX_SCANNED_COMMAND_CHARS:,}-character "
        "limit the cla guards scan, so NO guard checked it (a larger scan could outlast the hook "
        "timeout, and a timed-out hook lets the call through). Confirm only if you know it is "
        "safe, or split it into smaller commands. (hook: dispatch-bash-pretooluse.py)"
    )


def _unread_parts_ask(why: str) -> str:
    """The ask reason when the guards could not read every wrapper body."""
    return (
        "this command hands text to a shell wrapper (`bash -c`, `eval`, `pwsh -Command`, "
        f"...) and {why}, so the cla guards checked the command itself but not all of what "
        "the wrapper runs. Confirm only if you know it is safe, or split it into smaller "
        "commands. (hook: dispatch-bash-pretooluse.py)"
    )


def _part_inputs(stdin_text: str) -> tuple[list[str], str | None]:
    """The hook input for each extra part of the command, in order (the same
    payload with `tool_input.command` replaced by the part), and the reason to
    ask when the guards cannot read all of them, else None.

    No parts and no reason when there is no command or nothing to add. A reason
    when the reading stopped at a cap (the parts it found are still read), when
    the command and its parts together are longer than
    `MAX_SCANNED_COMMAND_CHARS`, the length the guards are timed for (none is
    read), or when the reading raised (none is read). Each of those asks rather
    than allowing what no guard checked."""
    if _guard_parts is None:
        return [], None  # `ask-destructive-git.py` fails to load on the same import and asks
    try:
        payload = json.loads(stdin_text)
        tool_input = payload["tool_input"]
        command = tool_input["command"]
    except (ValueError, RecursionError, TypeError, KeyError):
        return [], None  # no command to read: the guards handle the input as it is
    if not isinstance(command, str) or not command:
        return [], None
    try:
        extra, complete = _guard_parts(command)
    except Exception as exc:  # noqa: BLE001 -- see the docstring
        return [], _unread_parts_ask(f"reading those bodies failed ({type(exc).__name__}: {exc})")
    if len(command) + sum(len(p) for p in extra) > MAX_SCANNED_COMMAND_CHARS:
        return [], _unread_parts_ask(
            f"the command and those bodies together are over the {MAX_SCANNED_COMMAND_CHARS:,}-character "
            "limit the guards scan"
        )
    inputs = [
        json.dumps({**payload, "tool_input": {**tool_input, "command": part}})
        for part in extra
    ]
    return inputs, None if complete else _unread_parts_ask(
        "its bodies are longer than the guards read within their time"
    )

def main() -> int:
    global GUARD_NOT_RUN
    GUARD_NOT_RUN = False
    stdin_text = sys.stdin.read()
    # Before any guard runs, so no guard can be the slow one. An `ask`, never an
    # allow: an unscanned command must reach the user. Same JSON shape as `_fail_closed`.
    oversize = _oversize_ask(stdin_text)
    if oversize:
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "ask",
            "permissionDecisionReason": oversize,
        }}))
        return 0
    deadline = Deadline()
    part_inputs, unread_parts = _part_inputs(stdin_text)
    warnings: list[str] = []
    asks: list[str] = [unread_parts] if unread_parts else []
    skipped: list[str] = []
    errored = False
    errored_enforcing: list[str] = []

    for filename in _HOOK_FILES:
        cost = HOOK_WORST_CASE_SECONDS.get(filename, 0.0)
        if filename in _SKIPPABLE_HOOKS and not deadline.has_room(cost):
            skipped.append(filename)
            continue

        inputs = [stdin_text] + ([] if filename in _READS_COMMAND_ONLY else part_inputs)
        # This hook's own texts, so a warning or ask it repeats on several parts
        # is kept once; another hook's identical text is still its own.
        said: set[str] = set()
        for run, result in enumerate(run_hook_file_each(filename, inputs)):
            errored = errored or result.errored
            # An ENFORCING hook that failed to load did not run its check, and from
            # the outside that is indistinguishable from one that ran and allowed.
            # Tracked separately from `errored` so the escalation below fires only
            # for guards whose absence actually matters.
            if result.errored and filename not in _SKIPPABLE_HOOKS and filename not in errored_enforcing:
                errored_enforcing.append(filename)

            # Precedence is deny > ask > allow, matching the documented permission
            # evaluation order: a block short-circuits, and any pending `ask` is
            # moot once the call is refused outright.
            if result.code == 2:
                # A guard has already blocked: a failure while formatting the message must
                # not turn that block into the crash path's ask, so fall back to the raw text.
                try:
                    sys.stderr.write(compose_output(warnings, must_keep=result.stderr))
                except Exception:  # noqa: BLE001
                    sys.stderr.write(result.stderr)
                return 2

            warning = result.stderr.rstrip("\n")
            if warning.strip() and warning not in said:
                said.add(warning)
                warnings.append(warning)
            ask = _extract_ask(result.stdout)
            if ask and ask not in said:
                said.add(ask)
                asks.append(ask)
            # The next run is on a part: a skippable hook needs room for it too.
            if (
                filename in _SKIPPABLE_HOOKS
                and run + 1 < len(inputs)
                and not deadline.has_room(cost)
            ):
                skipped.append(filename)
                break

    # Skips go to stderr (the debug log) ONLY, deliberately, and are not added
    # to `warnings` — which is what becomes additionalContext below.
    #
    # An advisory hook stepping aside under load is this mechanism working as
    # designed: `_ADVISORY_HOOKS` membership is precisely the statement that
    # losing this hook is acceptable. Announcing it in Claude's context on every
    # busy call is noise on the hottest path in the session, and a channel that
    # carries routine noise stops being read — the same reasoning that keeps the
    # env-override notices off unrelated commands.
    #
    # A hook that CRASHED is the opposite: not designed degradation but a defect,
    # and it does go to context, below. Enforcement is never skipped at all, so
    # nothing load-bearing is being quietly dropped here.
    if skipped:
        print(
            "[dispatch] too little handler budget remained for these advisory "
            f"or best-effort hooks, so they were skipped: {', '.join(skipped)}. "
            "Every enforcing guard still ran — only warnings and best-effort "
            "checks were lost.",
            file=sys.stderr,
        )
    if errored:
        warnings.append(
            "[dispatch] one or more hooks failed to load or crashed on this "
            "call, so their checks did not run. Re-run with `claude --debug` "
            "for the traceback."
        )
    if errored_enforcing:
        GUARD_NOT_RUN = True
        # Escalated to `ask`, not left as a warning. `_dispatch_lib`'s docstring
        # records why exiting non-zero here would be wrong — it USED to ask for
        # it, and was corrected to match what both dispatchers actually do, so
        # this comment cited a requirement the same release had deleted and
        # pointed at a contract whose text now says the reverse. The reasoning
        # is unchanged: a non-zero exit makes Claude Code discard stdout — which
        # would downgrade a pending `ask` to an allow and surface only the first
        # line of merged stderr. `ask` is the one channel that reaches the user,
        # cannot be ignored, and costs nothing when the call was legitimate.
        #
        # Advisory hooks are deliberately excluded: losing a warning is the
        # acceptable half of the trade this dispatcher already makes for budget.
        asks.append(
            "an ENFORCING guard could not run on this call — "
            + ", ".join(sorted(errored_enforcing))
            + ". Its check did NOT happen, so this call is unguarded rather than "
            "approved. Confirm only if you know the action is safe; re-run with "
            "`claude --debug` for the traceback."
        )

    # stderr here reaches the DEBUG LOG ONLY. Per the hook contract, stderr from
    # a hook that exits 0 is never shown in the transcript and Claude never sees
    # it — so everything Claude must act on travels as stdout JSON below, and
    # this write exists purely for `claude --debug`.
    if warnings:
        print(compose_output(warnings), file=sys.stderr)

    # Everything non-blocking leaves through ONE stdout JSON object at exit 0 —
    # the only channel a PreToolUse hook has that Claude actually reads. An
    # `ask` and advisory text coexist in it: `permissionDecision` carries the
    # escalation, `additionalContext` the warnings.
    #
    # A non-zero exit is never used here, and that is deliberate. It discards
    # stdout entirely (so the ask would be downgraded to an allow) and surfaces
    # only the FIRST LINE of stderr, which for merged multi-hook output is
    # almost never the useful one. Exiting 1 to "report" a failed hook would
    # therefore cost more information than it conveys; the failure is reported
    # as context instead, where it arrives whole.
    reason = compose_output(asks) if asks else ""
    context = compose_output(warnings) if warnings else ""
    if not reason and not context:
        return 0

    def _payload(context_text: str) -> dict:
        nested: dict = {"hookEventName": "PreToolUse"}
        if reason:
            nested["permissionDecision"] = "ask"
            nested["permissionDecisionReason"] = reason
        if context_text:
            nested["additionalContext"] = context_text
        return {"hookSpecificOutput": nested}

    # Measured on the SERIALIZED payload, envelope included — clamping only the
    # inner strings left the printed total over the cap once JSON escaping
    # expanded it, which sends the whole thing to a file instead. The advisory
    # context is the part that shrinks; the ask reason is held whole.
    print(fit_json_payload(_payload, context))
    return 0


def _fail_closed(why: str, exc: BaseException) -> int:
    """Ask, at exit 0, when the dispatcher itself cannot run its guards.

    Stdlib only, since it runs when `_dispatch_lib` may be what failed. An `ask` is
    the rule a crashed enforcing hook already follows (see `main()`): it reaches the
    user, and a non-zero exit would discard it and let the call through unguarded.
    """
    global GUARD_NOT_RUN
    import traceback

    GUARD_NOT_RUN = True
    trace = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    print(f"[dispatch] {why}\n{trace}", file=sys.stderr)
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "ask",
        "permissionDecisionReason": (
            f"the cla guard dispatcher could not run ({why}), so NO guard checked this "
            "call. Confirm only if you know it is safe; re-run with `claude --debug` "
            "for the traceback. (hook: " + __file__.replace("\\", "/").rsplit("/", 1)[-1] + ")"
        ),
    }}))
    return 0


if __name__ == "__main__":
    if _LIB_ERROR is not None:
        sys.exit(_fail_closed(f"_dispatch_lib failed to load: {type(_LIB_ERROR).__name__}: {_LIB_ERROR}", _LIB_ERROR))
    try:
        _code = main()
    except Exception as _crash:  # noqa: BLE001 -- a crash must fail closed, not exit 1
        _code = _fail_closed(f"the dispatcher crashed: {type(_crash).__name__}: {_crash}", _crash)
    sys.exit(_code)
