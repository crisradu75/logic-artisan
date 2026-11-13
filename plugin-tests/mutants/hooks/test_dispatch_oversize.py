"""Mutant batch for the oversize-command ask in `dispatch-bash-pretooluse.py`.

Run: python3 plugin-tests/mutate.py plugin-tests/mutants/hooks/test_dispatch_oversize.py

Each entry re-breaks one changed line of the size check. All are killed by the
oversize tests at the end of `tests/hooks/test_dispatch.py`.
"""

from pathlib import Path

DEV = Path(__file__).resolve().parents[2]                      # <repo>/plugin-tests
PLUGIN = DEV.parent / ".claude" / "plugins" / "cla"
DISPATCH = PLUGIN / "hooks" / "dispatch-bash-pretooluse.py"
TARGETS = [DEV / "tests" / "hooks" / "test_dispatch.py"]

MUTANTS = [
    (
        # Killed by the over-cap ask tests and the 3 MB timing test.
        "the size check never fires",
        DISPATCH,
        "    if oversize:",
        "    if False:",
        TARGETS,
    ),
    (
        # Killed by the cap-exactly case of the at-or-below test.
        "a command exactly at the cap is asked about",
        DISPATCH,
        "len(command) <= MAX_SCANNED_COMMAND_CHARS:",
        "len(command) < MAX_SCANNED_COMMAND_CHARS:",
        TARGETS,
    ),
    (
        # Killed by the cap+1 ask test.
        "a command one over the cap is still scanned",
        DISPATCH,
        "len(command) <= MAX_SCANNED_COMMAND_CHARS:",
        "len(command) <= MAX_SCANNED_COMMAND_CHARS + 1:",
        TARGETS,
    ),
    (
        # Killed by the cap-range test and the 3 MB timing test.
        "the cap is ten times too large to protect the timeout",
        DISPATCH,
        "MAX_SCANNED_COMMAND_CHARS = 500_000",
        "MAX_SCANNED_COMMAND_CHARS = 5_000_000",
        TARGETS,
    ),
    (
        # Killed by the reason-text assertions.
        "the ask reason drops the thousands separator on the size",
        DISPATCH,
        'f"this command is {len(command):,} characters, over',
        'f"this command is {len(command)} characters, over',
        TARGETS,
    ),
    (
        # Killed by the equality on the whole hookSpecificOutput dict.
        "the reason is sent under the wrong key",
        DISPATCH,
        '"permissionDecisionReason": oversize,',
        '"reason": oversize,',
        TARGETS,
    ),
    (
        # Killed by the malformed-stdin case.
        "malformed stdin crashes the size check instead of reaching the guards",
        DISPATCH,
        "    except (ValueError, RecursionError):",
        "    except (KeyError, RecursionError):",
        TARGETS,
    ),
    (
        # Killed by the non-dict tool_input cases.
        "a non-dict tool_input crashes the size check",
        DISPATCH,
        'command = tool_input.get("command") if isinstance(tool_input, dict) else None',
        'command = tool_input.get("command")',
        TARGETS,
    ),
    (
        # Killed by the non-string command case.
        "a non-string command is measured as text",
        DISPATCH,
        "if not isinstance(command, str) or len(command)",
        "if len(command)",
        TARGETS,
    ),
]
