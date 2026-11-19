"""Mutant batch for the Copilot pre-tool adapter's "a guard did not run" path,
held by `tests/hooks/test_copilot_hooks.py`.

Run:
    python3 plugin-tests/mutate.py plugin-tests/mutants/hooks/test_copilot_hooks.py

WHAT IT COVERS. The structured flag that replaced wording markers: each
dispatcher sets `GUARD_NOT_RUN` when it asks because a guard could not run
(the enforcing-guard escalation in `main()`, and `_fail_closed`) and clears it
at the start of `main()`; the adapter denies on the flag, before it reads
the output, keeping the dispatcher's reason when it printed one, and denies a
dispatcher that has no flag at all. A mutant that loses the flag turns a
Copilot call no guard checked into an `ask` its user may approve blind.

WHAT IT LEAVES OUT: the rest of the adapter (event validation, malformed
dispatcher output), which this change did not touch.

Paths resolve from this file's own location, never an absolute developer path.
"""

from pathlib import Path

DEV = Path(__file__).resolve().parents[2]
PLUGIN = DEV.parent / ".claude" / "plugins" / "cla"
HOOKS = PLUGIN / "hooks"
ADAPTER = HOOKS / "copilot-pretooluse.py"
BASH = HOOKS / "dispatch-bash-pretooluse.py"
EDIT = HOOKS / "dispatch-edit-write-pretooluse.py"
GUARD = DEV / "tests" / "hooks" / "test_copilot_hooks.py"
TARGETS = [GUARD]

MUTANTS = [
    # killed by test_copilot_pretooluse_turns_a_failure_ask_into_a_deny and
    # test_the_adapter_denies_each_dispatcher_failure_ask_end_to_end
    ("the adapter ignores the flag and passes a failure ask through",
     ADAPTER, "    if not_run:\n", "    if False:\n", TARGETS),
    # killed by test_copilot_pretooluse_denies_a_dispatcher_without_the_flag
    ("a dispatcher with no flag is trusted",
     ADAPTER, "    if not isinstance(not_run, bool):\n", "    if False:\n", TARGETS),
    # killed by test_copilot_pretooluse_denies_a_dispatcher_without_the_flag
    ("a missing flag reads as False",
     ADAPTER, "getattr(module, _FLAG, None)", "getattr(module, _FLAG, False)", TARGETS),
    # killed by test_the_adapter_denies_each_dispatcher_failure_ask_end_to_end
    ("the adapter drops the flag it read",
     ADAPTER, "return _normalize(stdout_text, stderr_text, code, not_run)",
     "return _normalize(stdout_text, stderr_text, code, False)", TARGETS),
    # killed by test_every_dispatcher_flags_each_way_a_guard_did_not_run
    ("the Bash dispatcher's escalation leaves the flag down",
     BASH, "    if errored_enforcing:\n        GUARD_NOT_RUN = True\n",
     "    if errored_enforcing:\n        GUARD_NOT_RUN = False\n", TARGETS),
    ("the Edit/Write dispatcher's escalation leaves the flag down",
     EDIT, "    if errored_enforcing:\n        GUARD_NOT_RUN = True\n",
     "    if errored_enforcing:\n        GUARD_NOT_RUN = False\n", TARGETS),
    ("the Bash dispatcher's _fail_closed leaves the flag down",
     BASH, "    GUARD_NOT_RUN = True\n    trace =", "    GUARD_NOT_RUN = False\n    trace =", TARGETS),
    ("the Edit/Write dispatcher's _fail_closed leaves the flag down",
     EDIT, "    GUARD_NOT_RUN = True\n    trace =", "    GUARD_NOT_RUN = False\n    trace =", TARGETS),
    ("the Bash dispatcher keeps a flag left from an earlier call",
     BASH, "    global GUARD_NOT_RUN\n    GUARD_NOT_RUN = False\n    stdin_text",
     "    global GUARD_NOT_RUN\n    stdin_text", TARGETS),
    ("the Edit/Write dispatcher keeps a flag left from an earlier call",
     EDIT, "    global GUARD_NOT_RUN\n    GUARD_NOT_RUN = False\n    stdin_text",
     "    global GUARD_NOT_RUN\n    stdin_text", TARGETS),
    # killed by test_copilot_pretooluse_denies_a_flagged_call_whatever_it_printed
    ("a flagged call that printed no JSON crashes the adapter",
     ADAPTER, "    except (ValueError, KeyError, TypeError):\n", "    except (KeyError, TypeError):\n", TARGETS),
    ("a flagged call's own reason is dropped",
     ADAPTER, "    return reason if isinstance(reason, str) else",
     "    return reason if False else", TARGETS),
]
