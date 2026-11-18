"""`warn-agent-dispatch`: warn (never block or ask) before an Agent call that names no model,
pastes diff text into its prompt, or fills a review brief's protected-areas slot with
`(none recorded)`.

Each check is pinned both ways: the warning fires on the slip and stays silent on the correct
form and on the near-miss spelling. The hook is also run through its real `hooks.json` wiring,
since a dropped wiring would leave every unit test here green.
"""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parents[3] / ".claude" / "plugins" / "cla" / "hooks"
HOOK_PATH = HOOKS_DIR / "warn-agent-dispatch.py"

_spec = importlib.util.spec_from_file_location("warn_agent_dispatch", HOOK_PATH)
hook = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hook)

FILLED_SLOT = (
    "A missing edge case or risk that touches a protected area (money, personal data, "
    "accessibility, the user's own files, anything shipped to other repos) needs a requirement."
)

# Marks a key left out of the call entirely, as opposed to sent as null.
_DROP = object()


def _call(**tool_input) -> dict:
    base = {"description": "review", "subagent_type": "general-purpose", "model": "sonnet",
            "prompt": "Review the change. " + FILLED_SLOT}
    base.update(tool_input)
    return {"hook_event_name": "PreToolUse", "tool_name": "Agent",
            "tool_input": {k: v for k, v in base.items() if v is not _DROP}}



def _run_main(monkeypatch, capsys, payload) -> str:
    """Run `main()` in-process on a payload (a dict, or raw text) and return the warning."""
    text = payload if isinstance(payload, str) else json.dumps(payload)
    monkeypatch.setattr(sys, "stdin", __import__("io").StringIO(text))
    assert hook.main() == 0, "the hook only ever warns"
    out = capsys.readouterr().out
    if not out.strip():
        return ""
    parsed = json.loads(out)
    nested = parsed["hookSpecificOutput"]
    assert nested["hookEventName"] == "PreToolUse"
    assert set(nested) == {"hookEventName", "additionalContext"}, "a warning, never a decision"
    assert nested["additionalContext"].strip(), "output only when there is something to say"
    return nested["additionalContext"]


def _run_process(payload: dict) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(HOOK_PATH)], input=json.dumps(payload),
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )


# --------------------------------------------------------------------------- #
# Model
# --------------------------------------------------------------------------- #


# requirement: guard-warnings / A subagent dispatch without a model warns
@pytest.mark.parametrize("model", [_DROP, None, "", "   "])
def test_a_dispatch_with_no_model_warns(monkeypatch, capsys, model):
    warning = _run_main(monkeypatch, capsys, _call(model=model))
    assert "passes no `model`" in warning
    assert "diff" not in warning and "(none recorded)" not in warning, "only the model warning"


@pytest.mark.parametrize("model", ["sonnet", "opus", "haiku", "claude-sonnet-4-5"])
def test_a_dispatch_that_names_its_model_is_silent(monkeypatch, capsys, model):
    assert _run_main(monkeypatch, capsys, _call(model=model)) == ""


def test_a_non_string_model_is_left_alone(monkeypatch, capsys):
    """Not a missing model: the tool rejects a malformed one itself."""
    assert _run_main(monkeypatch, capsys, _call(model=5)) == ""


# --------------------------------------------------------------------------- #
# Diff text
# --------------------------------------------------------------------------- #

DIFF = (
    "diff --git a/src/app.py b/src/app.py\n"
    "index 1111111..2222222 100644\n"
    "--- a/src/app.py\n+++ b/src/app.py\n@@ -1 +1 @@\n-x = 1\n+x = 2\n"
)


# requirement: guard-warnings / A subagent prompt holding diff text warns
@pytest.mark.parametrize(
    "prompt",
    [
        "Review this change:\n" + DIFF,
        DIFF,  # header on the very first line
        "Review:\n```diff\n" + DIFF + "```\n",
        "Review:\n    " + DIFF.replace("\n", "\n    "),  # pasted indented
        "Review:\n\tdiff --git x/a.py x/a.py\n",  # tab-indented, --no-prefix style
        "Review:\r\ndiff --git a/a.py b/a.py\r\n",  # CRLF
    ],
)
def test_diff_text_in_the_prompt_warns(monkeypatch, capsys, prompt):
    warning = _run_main(monkeypatch, capsys, _call(prompt=prompt + "\n" + FILLED_SLOT))
    assert "holds diff text" in warning
    assert "pass its absolute path" in warning


@pytest.mark.parametrize(
    "prompt",
    [
        "The diff is at /tmp/scratch/review-round-1-main.diff; read it with Read.",
        "Write the diff to a file; a line starting `diff --git ` marks pasted text.",
        "Never paste diff --git output here.",  # mid-line
        "Review:\ndiff --git\n",  # header word with nothing after it
        "Review:\ndiff --cached a b\n",  # another diff command
        "Review:\n> diff --git a/x b/x\n",  # quoted in a blockquote, not pasted
    ],
)
def test_a_diff_path_or_a_mention_of_the_header_is_silent(monkeypatch, capsys, prompt):
    assert _run_main(monkeypatch, capsys, _call(prompt=prompt + "\n" + FILLED_SLOT)) == ""


# --------------------------------------------------------------------------- #
# (none recorded) in the protected-areas slot
# --------------------------------------------------------------------------- #


# requirement: guard-warnings / A review brief that says no area is protected warns
@pytest.mark.parametrize(
    "slot",
    [
        "touches a protected area ((none recorded)) needs a requirement",
        "touches a protected area (`(none recorded)`) needs a requirement",
        "touches a protected area ( (none recorded) ) needs a requirement",
        "touches one of the protected areas ((none recorded)) needs a requirement",
    ],
)
def test_none_recorded_in_the_protected_areas_slot_warns(monkeypatch, capsys, slot):
    warning = _run_main(monkeypatch, capsys, _call(prompt="Check 2. A risk that " + slot + "."))
    assert "protected-areas slot with `(none recorded)`" in warning
    assert "no Stakes section: the default list applies" in warning


@pytest.mark.parametrize(
    "prompt",
    [
        FILLED_SLOT,
        # The other placeholders may legitimately say `(none recorded)`.
        FILLED_SLOT + " 3. Core-calculation integrity: (none recorded). Lockstep files: (none recorded).",
        "touches a protected area (no Stakes section: the default list applies) needs a requirement",
        # Near misses: the slot holds more than the placeholder, or another word precedes it.
        "touches a protected area (money; formulas: (none recorded)) needs a requirement",
        "touches a protected zone ((none recorded))",
        "touches a protected area ((none recorded) and money) needs a requirement",
        "protected area: (none recorded)",
    ],
)
def test_a_filled_slot_or_another_none_recorded_is_silent(monkeypatch, capsys, prompt):
    assert _run_main(monkeypatch, capsys, _call(prompt=prompt)) == ""


def test_all_three_warnings_arrive_together(monkeypatch, capsys):
    warning = _run_main(monkeypatch, capsys, _call(
        model=_DROP, prompt=DIFF + "touches a protected area ((none recorded))"))
    assert warning.count("[warn-agent-dispatch]") == 3
    assert warning.index("`model`") < warning.index("diff text") < warning.index("(none recorded)")


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
        '{"tool_name": "Agent", "tool_input": "x"}',
        '{"tool_name": "Agent", "tool_input": []}',
        json.dumps({"tool_name": "Bash", "tool_input": {"command": "ls"}}),
        json.dumps({"tool_input": {"prompt": "x"}}),  # no tool name
        json.dumps({"tool_name": "Write", "tool_input": {"prompt": DIFF}}),
    ],
)
def test_malformed_or_foreign_input_is_silent(monkeypatch, capsys, payload):
    assert _run_main(monkeypatch, capsys, payload) == ""


def test_a_non_string_prompt_still_gets_the_model_check(monkeypatch, capsys):
    warning = _run_main(monkeypatch, capsys, _call(model=_DROP, prompt=["diff --git a/x b/x"]))
    assert "passes no `model`" in warning and "diff text" not in warning


@pytest.mark.parametrize("io_encoding", ["utf-8:strict", "utf-8:surrogateescape"])
def test_bad_bytes_on_stdin_are_silent(io_encoding):
    """Strict decoding raises UnicodeDecodeError while reading; a POSIX locale's
    surrogateescape turns the same bytes into a JSON error instead. Both are silent."""
    env = dict(os.environ, PYTHONIOENCODING=io_encoding)
    r = subprocess.run([sys.executable, str(HOOK_PATH)], input=b"\xff\xfe{", capture_output=True, env=env)
    assert r.returncode == 0 and r.stdout == b"", r.stderr


@pytest.mark.parametrize(
    "prompt",
    [
        "\n" * 2_000_000,
        " " * 2_000_000 + "x",
        "\n".join([" " * 200] * 10_000),
        "diff --git" * 300_000,
        "protected area (" * 200_000,
        "protected area (" + " " * 2_000_000,
        "protected area (`(none recorded)" * 100_000,
    ],
    ids=["newlines", "blanks", "blank-lines", "headers", "slot-openers", "slot-blanks", "slot-near"],
)
def test_a_large_prompt_stays_fast(prompt):
    """Every pattern is linear: a multi-megabyte prompt finishes far inside the handler timeout."""
    start = time.monotonic()
    found = hook._warnings({"model": "sonnet", "prompt": prompt})
    assert time.monotonic() - start < 2.0
    assert found == []


# --------------------------------------------------------------------------- #
# The process and the wiring
# --------------------------------------------------------------------------- #


def test_the_process_warns_at_exit_zero():
    r = _run_process(_call(model=_DROP))
    assert r.returncode == 0, r.stderr
    assert "passes no `model`" in json.loads(r.stdout)["hookSpecificOutput"]["additionalContext"]


def test_the_hook_never_decides_the_call():
    """Advisory only: no permission decision anywhere in the source, and no exit 2."""
    source = HOOK_PATH.read_text(encoding="utf-8")
    assert "permissionDecision" not in source
    assert "return 2" not in source and "exit(2)" not in source
    assert "import subprocess" not in source, "the hook runs no subprocess"


def _agent_wiring(event: str) -> dict:
    config = json.loads((HOOKS_DIR / "hooks.json").read_text(encoding="utf-8"))
    groups = [g for g in config["hooks"].get(event, []) if g.get("matcher") == "Agent"]
    assert len(groups) == 1, f"expected one Agent group on {event}, found {len(groups)}"
    return groups[0]


def test_the_hook_is_wired_on_the_agent_matcher():
    group = _agent_wiring("PreToolUse")
    commands = [h["command"] for h in group["hooks"]]
    assert commands == [c for c in commands if c.endswith('/hooks/warn-agent-dispatch.py"')]
    assert len(commands) == 1


_BASH = shutil.which("bash")


@pytest.mark.skipif(_BASH is None, reason="no POSIX shell available")
@pytest.mark.parametrize("model", [_DROP, "sonnet"])
def test_the_real_wiring_runs_the_hook(model):
    """The command in hooks.json, run as Claude Code runs it, reaches the hook."""
    command = _agent_wiring("PreToolUse")["hooks"][0]["command"]
    env = dict(os.environ)
    env["CLAUDE_PLUGIN_ROOT"] = str(HOOKS_DIR.parent).replace("\\", "/")
    r = subprocess.run([_BASH, "-c", command], input=json.dumps(_call(model=model)),
                       capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)
    assert r.returncode == 0, r.stderr
    if model is _DROP:
        assert "passes no `model`" in r.stdout
    else:
        assert r.stdout.strip() == ""


def test_copilot_cli_does_not_run_the_agent_warnings():
    """Documented, not an oversight: the Copilot adapter handles shell and file tools only.

    If the Copilot wiring ever gains an Agent matcher, its adapter would deny every Agent call as
    an unsupported tool, so the two have to change together with the README's caveat."""
    copilot = json.loads((HOOKS_DIR.parent / "com.github.copilot" / "hooks" / "hooks.json")
                         .read_text(encoding="utf-8"))
    matchers = {g["matcher"] for groups in copilot["hooks"].values() for g in groups}
    assert matchers and not any("Agent" in m.split("|") for m in matchers)
    adapter = (HOOKS_DIR / "copilot-pretooluse.py").read_text(encoding="utf-8")
    assert '"Agent"' not in adapter
    readme = (HOOKS_DIR.parent / "README.md").read_text(encoding="utf-8")
    assert "do not run under Copilot CLI" in readme
