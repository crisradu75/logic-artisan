#!/usr/bin/env python3
"""PreToolUse (Agent): warn when a subagent dispatch breaks a dispatch rule.

Three checks over the Agent tool's own arguments, each a presence test on text.
None of them judges what the dispatch is for, so each only warns: the call runs,
and the warning reaches Claude as `additionalContext` beside it.

1. No `model`. The skills pass `model:` on every dispatch, chosen by task. A call
   without one runs on the agent file's model, and for an agent file that says
   `inherit`, or a built-in agent, on the session model: the cost is silent.
   A warning and not a prompt, because the owner's own ad-hoc dispatch on the
   session model is legitimate, and a prompt would stop an unattended chain.
2. Diff text in the prompt. A review dispatch writes the diff to a file and passes
   its path. A line that starts `diff --git ` is the header git prints at the top
   of every file's diff, so it marks pasted diff text. Matched at the start of a
   line only, so a prompt that names the header in prose stays silent.
3. `(none recorded)` in the protected-areas slot. A review brief's protected-area
   placeholder is filled with the default list when the repo records none, never
   with `(none recorded)` (review-change's dispatch reference). Matched only as the
   whole slot after `protected area (`, so the other placeholders, which may say
   `(none recorded)`, stay silent.

Bad input is silent: input that is not JSON, not an object, not an Agent call,
or with no usable `tool_input` exits 0 with no output. It does not reach a
`Workflow` script's `agent()` calls, which are not Agent tool calls. The hook runs no subprocess and reads no
file, and every pattern is linear in the prompt's length.
"""

from __future__ import annotations

import json
import re
import sys

# A line that starts with git's per-file diff header: `diff --git a/x b/x`, or
# with `--no-prefix`, `diff --git x x`. Leading blanks allowed, for a diff pasted
# indented. The anchor is what keeps prose naming the header silent.
_DIFF_HEADER = re.compile(r"^[ \t]*diff --git \S", re.MULTILINE)

# The protected-areas slot of review-change's check 2, `touches a protected area
# (<inject: ...>)`, filled with `(none recorded)`, with or without backticks.
_NONE_RECORDED_SLOT = re.compile(r"protected areas? \(\s*`?\(none recorded\)`?\s*\)")

_TAG = "[warn-agent-dispatch]"


def _missing_model(tool_input: dict) -> bool:
    """True when the call names no model: the key is absent, null or blank."""
    model = tool_input.get("model")
    if model is None:
        return True
    return isinstance(model, str) and not model.strip()


def _warnings(tool_input: dict) -> list[str]:
    found: list[str] = []
    if _missing_model(tool_input):
        found.append(
            f"{_TAG} This Agent call passes no `model`, so the subagent runs on its agent "
            "file's model or, where that says `inherit`, on the session model. The plugin's "
            "dispatch rules pass `model:` on every dispatch, chosen by task (the economy "
            "rules' \"Model by task\"). Name one on this skill's next dispatch; an ad-hoc call "
            "meant to run on the session model can ignore this."
        )
    prompt = tool_input.get("prompt")
    if isinstance(prompt, str):
        if _DIFF_HEADER.search(prompt):
            found.append(
                f"{_TAG} This Agent prompt holds diff text (a line starting `diff --git `). "
                "Write the diff to a file outside the working tree and pass its absolute path "
                "instead; pasted diff text bloats the prompt and breaks a Workflow script's "
                "template literal."
            )
        if _NONE_RECORDED_SLOT.search(prompt):
            found.append(
                f"{_TAG} This Agent prompt fills the protected-areas slot with `(none recorded)`. "
                "That slot takes the protected areas from blocking-findings.md (\"What is "
                "protected\") with the repo's Stakes section, or the line \"no Stakes section: "
                "the default list applies\"; a review told nothing is protected skips them."
            )
    return found


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (ValueError, RecursionError):
        # ValueError covers a JSON error and undecodable bytes; RecursionError is
        # input nested deeper than the decoder's recursion limit.
        return 0
    if not isinstance(payload, dict) or payload.get("tool_name") != "Agent":
        return 0
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return 0

    found = _warnings(tool_input)
    if found:
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "additionalContext": "\n\n".join(found),
            }
        }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
