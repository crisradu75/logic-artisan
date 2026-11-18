#!/usr/bin/env python3
"""PostToolUse (Agent): warn when a subagent's reply lacks a line its contract requires.

Two presence checks, each a string match on the reply. Neither says the line's
content is true: a `Scanned:` footer can carry a wrong count, and a
`Fact corrections:` field can say `(none)` over a fact that did not resolve.
They only catch the line that is not there, which is the failure the caller
otherwise has to notice by reading.

1. A `doc-sweeper` dispatch (`subagent_type` `doc-sweeper`, or a plugin-scoped
   name ending `:doc-sweeper`) must end with a footer line starting `Scanned:`.
   Without it a "No stale references found." reply cannot be told apart from a
   sweep that searched nothing.
2. A dispatch whose prompt names `Fact corrections:` must get that field back.
   A missing field is not `(none)`: it is the one channel for a fact row that
   was wrong while the defect survived.

The warning reaches the orchestrator as `additionalContext` beside the result.
The call has already run, so this hook can only warn.

WHAT IT READS. The documented `tool_response` of a completed foreground Agent
call has `status: "completed"` and `content`, a list of text blocks. Anything
else is skipped: a background launch (`async_launched`) has no reply yet.

A subagent that reports through `SubagentHandback` leaves only a short note in
`content`. When the response also carries the delivered report
(`handbackReport.text`, an undocumented field) that text is checked; when it
says a hand-back happened (`handback`) but carries no report, the hook stays
silent, since the report is not in front of it. Where neither field arrives the
warning itself says a hand-back may be why, so it never reads as proof.

Bad input is silent: input that is not JSON, not an object, not an Agent call,
or with no usable `tool_input` or `tool_response` exits 0 with no output. The
hook runs no subprocess and reads no file, and each check is linear in the
reply's length.
"""

from __future__ import annotations

import json
import re
import sys

# The footer line, allowing leading blanks and Markdown emphasis or a list or
# quote marker before it, since a model may format the footer.
_SCANNED_LINE = re.compile(r"^[ \t>*_`-]*Scanned:", re.MULTILINE)

# The field name, allowing emphasis between the name and its colon.
_FACT_FIELD = re.compile(r"Fact corrections[*_`]*:")

_FACT_FIELD_IN_PROMPT = "Fact corrections:"

_TAG = "[warn-agent-reply-format]"

_HANDBACK_NOTE = (
    " If this agent handed its report back through SubagentHandback, this result holds "
    "only a note about it; check the delivered report for the line instead."
)


def _is_doc_sweeper(subagent_type: object) -> bool:
    return isinstance(subagent_type, str) and subagent_type.rsplit(":", 1)[-1] == "doc-sweeper"


def _reply_text(tool_response: dict) -> str | None:
    """The reply to check, or None when there is none in front of this hook."""
    if tool_response.get("status") != "completed":
        return None
    report = tool_response.get("handbackReport")
    if isinstance(report, dict) and isinstance(report.get("text"), str):
        return report["text"]
    if "handback" in tool_response:
        return None
    content = tool_response.get("content")
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return None
    return "\n".join(
        block["text"]
        for block in content
        if isinstance(block, dict) and block.get("type") == "text" and isinstance(block.get("text"), str)
    )


def _warnings(tool_input: dict, reply: str) -> list[str]:
    found: list[str] = []
    if _is_doc_sweeper(tool_input.get("subagent_type")) and not _SCANNED_LINE.search(reply):
        found.append(
            f"{_TAG} This doc-sweeper reply has no `Scanned:` footer line. Without it a "
            "clean reply cannot be told apart from a sweep that searched nothing: check the "
            "supplied paths and re-dispatch before trusting it." + _HANDBACK_NOTE
        )
    prompt = tool_input.get("prompt")
    if isinstance(prompt, str) and _FACT_FIELD_IN_PROMPT in prompt and not _FACT_FIELD.search(reply):
        found.append(
            f"{_TAG} The brief asked for `Fact corrections:` and the reply has no such field. "
            "A missing field is not `(none)`: re-resolve the brief's fact rows yourself or "
            "re-dispatch." + _HANDBACK_NOTE
        )
    return found


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError):
        return 0
    if not isinstance(payload, dict) or payload.get("tool_name") != "Agent":
        return 0
    tool_input = payload.get("tool_input")
    tool_response = payload.get("tool_response")
    if not isinstance(tool_input, dict) or not isinstance(tool_response, dict):
        return 0
    reply = _reply_text(tool_response)
    if reply is None:
        return 0

    found = _warnings(tool_input, reply)
    if found:
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "additionalContext": "\n\n".join(found),
            }
        }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
