"""`warn-agent-reply-format`: warn (never block) after a completed Agent call whose reply lacks
a line its contract requires — a `doc-sweeper` reply with no `Scanned:` footer, or a reply with no
`Fact corrections:` field when the brief asked for one.

Presence checks only: a footer with a wrong count passes, by design. The response shape follows
the documented PostToolUse input for the Agent tool (`status`, `content` as text blocks).
`handback` and `handbackReport` are undocumented fields of the same object, read best-effort.
"""

from __future__ import annotations

import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parents[3] / ".claude" / "plugins" / "cla" / "hooks"
HOOK_PATH = HOOKS_DIR / "warn-agent-reply-format.py"

_spec = importlib.util.spec_from_file_location("warn_agent_reply_format", HOOK_PATH)
hook = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hook)

FOOTER = "Scanned: 12 files from 3 supplied paths/globs. Unresolved: none.\n- `old_name`: 0"
CLEAN = "No stale references found.\n"
FIX_BRIEF = "Fix the finding. Report `Fact corrections:` in every return, or `(none)`."
FIX_REPLY = "status: done\ndefect check: clean\n12 passed\n3/3 tasks\nFact corrections: (none)"


def _response(*texts: str, **extra) -> dict:
    body = {"status": "completed", "agentId": "a1",
            "content": [{"type": "text", "text": t} for t in texts]}
    body.update(extra)
    return body


def _call(prompt="Sweep these paths.", subagent_type="cla:doc-sweeper", response=None) -> dict:
    return {
        "hook_event_name": "PostToolUse",
        "tool_name": "Agent",
        "tool_input": {"description": "sweep", "prompt": prompt,
                       "subagent_type": subagent_type, "model": "haiku"},
        "tool_response": _response(CLEAN + FOOTER) if response is None else response,
    }


def _run_main(monkeypatch, capsys, payload) -> str:
    text = payload if isinstance(payload, str) else json.dumps(payload)
    monkeypatch.setattr(sys, "stdin", io.StringIO(text))
    assert hook.main() == 0, "the hook only ever warns"
    out = capsys.readouterr().out
    if not out.strip():
        return ""
    nested = json.loads(out)["hookSpecificOutput"]
    assert nested["hookEventName"] == "PostToolUse"
    assert set(nested) == {"hookEventName", "additionalContext"}, "a warning, never a decision"
    assert nested["additionalContext"].strip(), "output only when there is something to say"
    return nested["additionalContext"]


# --------------------------------------------------------------------------- #
# doc-sweeper footer
# --------------------------------------------------------------------------- #


# requirement: guard-warnings / A doc sweep reply without its footer warns
@pytest.mark.parametrize("subagent_type", ["doc-sweeper", "cla:doc-sweeper", "x:y:doc-sweeper"])
@pytest.mark.parametrize(
    "texts",
    [
        (CLEAN,),
        ("- `a.md:3` — `old` — old here\n",),
        ("Scanned files: none\n",),  # the word, not the line
        ("I Scanned: 3 files\n",),  # not at the start of a line
        ("No stale references found. Scanned: 0 files\n",),  # mid-line
        (),  # no text blocks at all
    ],
)
def test_a_sweep_reply_with_no_footer_warns(monkeypatch, capsys, subagent_type, texts):
    warning = _run_main(monkeypatch, capsys, _call(subagent_type=subagent_type,
                                                   response=_response(*texts)))
    assert "no `Scanned:` footer line" in warning
    assert "SubagentHandback" in warning, "the warning says a hand-back may be why"
    assert "Fact corrections" not in warning


@pytest.mark.parametrize(
    "texts",
    [
        (CLEAN + FOOTER,),
        ("- `a.md:3` — `old` — hit\n" + FOOTER,),
        (CLEAN.rstrip("\n"), FOOTER),  # footer in its own text block, which starts a line
        ("  " + FOOTER,),
        ("**Scanned:** 4 files from 1 supplied paths/globs. Unresolved: none.",),
        ("```\n" + CLEAN + "```\n`Scanned: 4 files`",),
        ("> Scanned: 4 files",),
        ("_Scanned:_ 4 files",),
        ("- Scanned: 4 files",),
        ("Scanned: 0 files from 2 supplied paths/globs. Unresolved: docs/*.md",),  # a wrong count passes
        ("x\r\nScanned: 1 files",),
    ],
)
def test_a_sweep_reply_holding_the_footer_is_silent(monkeypatch, capsys, texts):
    assert _run_main(monkeypatch, capsys, _call(response=_response(*texts))) == ""


@pytest.mark.parametrize("subagent_type", ["general-purpose", "doc-sweeper-v2", "cla:fact-gatherer",
                                           "doc-sweeper:other", "my-doc-sweeper", "", None, 3])
def test_another_agent_needs_no_footer(monkeypatch, capsys, subagent_type):
    assert _run_main(monkeypatch, capsys, _call(subagent_type=subagent_type,
                                                response=_response(CLEAN))) == ""


def test_a_sweep_still_in_the_background_is_silent(monkeypatch, capsys):
    response = {"status": "async_launched", "agentId": "a1", "description": "sweep",
                "prompt": "Sweep.", "outputFile": "/tmp/out", "resolvedModel": "haiku"}
    assert _run_main(monkeypatch, capsys, _call(response=response)) == ""


# --------------------------------------------------------------------------- #
# Fact corrections
# --------------------------------------------------------------------------- #


# requirement: guard-warnings / A fix reply without its fact-corrections field warns
@pytest.mark.parametrize(
    "reply",
    [
        "status: done\n12 passed\n3/3 tasks",
        "status: done\nFact corrections (none)",  # no colon
        "status: done\nfact corrections: (none)",  # the field's own spelling is capitalised
        "status: done\nFact correction: (none)",
    ],
)
def test_a_fix_reply_without_the_field_warns(monkeypatch, capsys, reply):
    warning = _run_main(monkeypatch, capsys, _call(prompt=FIX_BRIEF, subagent_type="general-purpose",
                                                   response=_response(reply)))
    assert "no such field" in warning
    assert "not `(none)`" in warning
    assert "SubagentHandback" in warning, "the warning says a hand-back may be why"
    assert "Scanned" not in warning


@pytest.mark.parametrize(
    "reply",
    [
        FIX_REPLY,
        "status: done\n**Fact corrections:** (none)",
        "status: done\n**Fact corrections**: (none)",
        "status: blocked\nFact corrections:\n- row 2 did not resolve",
        "Fact corrections: (none)",  # content is not judged
    ],
)
def test_a_fix_reply_holding_the_field_is_silent(monkeypatch, capsys, reply):
    assert _run_main(monkeypatch, capsys, _call(prompt=FIX_BRIEF, subagent_type="general-purpose",
                                                response=_response(reply))) == ""


@pytest.mark.parametrize("prompt", ["Fix the finding.", "Report fact corrections if any.",
                                    "Report Fact corrections in every return.", None, ["Fact corrections:"]])
def test_a_brief_that_never_names_the_field_needs_none(monkeypatch, capsys, prompt):
    assert _run_main(monkeypatch, capsys, _call(prompt=prompt, subagent_type="general-purpose",
                                                response=_response("status: done"))) == ""


def test_both_warnings_arrive_together(monkeypatch, capsys):
    warning = _run_main(monkeypatch, capsys, _call(prompt=FIX_BRIEF, response=_response(CLEAN)))
    assert warning.count("[warn-agent-reply-format]") == 2
    assert warning.index("Scanned") < warning.index("Fact corrections")


# --------------------------------------------------------------------------- #
# Hand-back
# --------------------------------------------------------------------------- #


def test_a_delivered_hand_back_report_is_what_gets_checked(monkeypatch, capsys):
    note = "The agent delivered its report through SubagentHandback."
    with_footer = _response(note, handback="send", handbackReport={"text": CLEAN + FOOTER})
    without = _response(note, handback="send", handbackReport={"text": CLEAN})
    assert _run_main(monkeypatch, capsys, _call(response=with_footer)) == ""
    assert "no `Scanned:` footer" in _run_main(monkeypatch, capsys, _call(response=without))


@pytest.mark.parametrize("state", ["send", "flagged", "withheld"])
def test_a_hand_back_with_no_report_in_view_is_silent(monkeypatch, capsys, state):
    """The report is not in front of the hook, so it cannot say whether the line is there."""
    response = _response("The agent handed its report back.", handback=state)
    assert _run_main(monkeypatch, capsys, _call(prompt=FIX_BRIEF, response=response)) == ""


@pytest.mark.parametrize("report", [None, "text", {"warning": "x"}, {"text": 5}])
def test_a_malformed_hand_back_report_is_not_read(monkeypatch, capsys, report):
    response = _response("note", handback="send", handbackReport=report)
    assert _run_main(monkeypatch, capsys, _call(response=response)) == ""


# --------------------------------------------------------------------------- #
# Bad input fails open; size stays linear
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "payload",
    [
        "",
        "not json",
        "[]",
        "null",
        '{"tool_name": "Agent"}',
        json.dumps({"tool_name": "Agent", "tool_input": {"subagent_type": "doc-sweeper"}}),
        json.dumps({"tool_name": "Agent", "tool_input": [], "tool_response": _response(CLEAN)}),
        json.dumps({"tool_name": "Agent", "tool_input": {"subagent_type": "doc-sweeper"},
                    "tool_response": "No stale references found."}),
        json.dumps({"tool_name": "Write", "tool_input": {"subagent_type": "doc-sweeper"},
                    "tool_response": _response(CLEAN)}),
    ],
)
def test_malformed_or_foreign_input_is_silent(monkeypatch, capsys, payload):
    assert _run_main(monkeypatch, capsys, payload) == ""


@pytest.mark.parametrize(
    "response",
    [
        {"content": [{"type": "text", "text": CLEAN}]},  # no status
        {"status": "failed", "content": [{"type": "text", "text": CLEAN}]},
        {"status": "completed"},  # no content
        {"status": "completed", "content": 7},
        {"status": "completed", "content": {"text": CLEAN}},
    ],
)
def test_a_response_with_no_readable_reply_is_silent(monkeypatch, capsys, response):
    assert _run_main(monkeypatch, capsys, _call(response=response)) == ""


def test_odd_blocks_are_skipped_and_the_rest_read(monkeypatch, capsys):
    response = {"status": "completed",
                "content": [5, {"type": "image"}, {"type": "image", "text": FOOTER},
                            {"type": "text", "text": 9}, {"type": "text", "text": CLEAN}]}
    assert "no `Scanned:`" in _run_main(monkeypatch, capsys, _call(response=response))
    response["content"].append({"type": "text", "text": FOOTER})
    assert _run_main(monkeypatch, capsys, _call(response=response)) == ""


def test_a_string_content_is_read(monkeypatch, capsys):
    response = {"status": "completed", "content": CLEAN + FOOTER}
    assert _run_main(monkeypatch, capsys, _call(response=response)) == ""
    response["content"] = CLEAN
    assert "no `Scanned:`" in _run_main(monkeypatch, capsys, _call(response=response))


@pytest.mark.parametrize("io_encoding", ["utf-8:strict", "utf-8:surrogateescape"])
def test_bad_bytes_on_stdin_are_silent(io_encoding):
    """Strict decoding raises UnicodeDecodeError while reading; a POSIX locale's
    surrogateescape turns the same bytes into a JSON error instead. Both are silent."""
    env = dict(os.environ, PYTHONIOENCODING=io_encoding)
    r = subprocess.run([sys.executable, str(HOOK_PATH)], input=b"\xff\xfe{", capture_output=True, env=env)
    assert r.returncode == 0 and r.stdout == b"", r.stderr


@pytest.mark.parametrize(
    "reply",
    [
        "*" * 3_000_000,
        "\n".join(["> " * 100] * 20_000),
        "Fact corrections" * 200_000,
        "Fact corrections" + "*" * 3_000_000,
    ],
    ids=["emphasis", "quote-lines", "field-names", "field-emphasis"],
)
def test_a_large_reply_stays_fast(reply):
    start = time.monotonic()
    found = hook._warnings({"subagent_type": "doc-sweeper", "prompt": "Fact corrections:"}, reply)
    assert time.monotonic() - start < 2.0
    assert len(found) == 2


# --------------------------------------------------------------------------- #
# The process and the wiring
# --------------------------------------------------------------------------- #


def test_the_process_warns_at_exit_zero():
    r = subprocess.run([sys.executable, str(HOOK_PATH)],
                       input=json.dumps(_call(response=_response(CLEAN))),
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert r.returncode == 0, r.stderr
    assert "Scanned" in json.loads(r.stdout)["hookSpecificOutput"]["additionalContext"]


def test_the_hook_never_decides_the_call():
    source = HOOK_PATH.read_text(encoding="utf-8")
    assert "permissionDecision" not in source
    assert '"decision"' not in source and "return 2" not in source and "exit(2)" not in source
    assert "import subprocess" not in source, "the hook runs no subprocess"


def _agent_wiring(event: str) -> dict:
    config = json.loads((HOOKS_DIR / "hooks.json").read_text(encoding="utf-8"))
    groups = [g for g in config["hooks"].get(event, []) if g.get("matcher") == "Agent"]
    assert len(groups) == 1, f"expected one Agent group on {event}, found {len(groups)}"
    return groups[0]


def test_the_hook_is_wired_on_the_agent_matcher():
    commands = [h["command"] for h in _agent_wiring("PostToolUse")["hooks"]]
    assert len(commands) == 1 and commands[0].endswith('/hooks/warn-agent-reply-format.py"')


_BASH = shutil.which("bash")


@pytest.mark.skipif(_BASH is None, reason="no POSIX shell available")
@pytest.mark.parametrize("reply", [CLEAN, CLEAN + FOOTER])
def test_the_real_wiring_runs_the_hook(reply):
    command = _agent_wiring("PostToolUse")["hooks"][0]["command"]
    env = dict(os.environ)
    env["CLAUDE_PLUGIN_ROOT"] = str(HOOKS_DIR.parent).replace("\\", "/")
    r = subprocess.run([_BASH, "-c", command], input=json.dumps(_call(response=_response(reply))),
                       capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)
    assert r.returncode == 0, r.stderr
    if "Scanned:" in reply:
        assert r.stdout.strip() == ""
    else:
        assert "no `Scanned:` footer" in r.stdout
