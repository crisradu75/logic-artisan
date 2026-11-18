"""Tests for `ask-secret-in-checkpoint.py`: ask before a secret-shaped string is
written into a committed briefing under `cla.io/`.

No secret-shaped string appears literally in this file. Each sample is joined
from pieces at runtime (`_join`), so a secret scanner reading the repo finds
nothing here, while the hook, which sees the joined text, does. Random bodies
come from a seeded generator, so a run is repeatable.

Each asking shape is pinned with a silent partner one step away from it: a
placeholder in the same position, the same prefix inside a word, the same
characters without the mix a random key has.
"""

from __future__ import annotations

import importlib.util
import io
import json
import os
import random
import string
import subprocess
import sys
import time
from pathlib import Path

import pytest

_HOOKS_DIR = Path(__file__).resolve().parents[3] / ".claude" / "plugins" / "cla" / "hooks"
_HOOK = _HOOKS_DIR / "ask-secret-in-checkpoint.py"
_DISPATCH = _HOOKS_DIR / "dispatch-edit-write-pretooluse.py"


def _load():
    spec = importlib.util.spec_from_file_location("ask_secret_in_checkpoint", _HOOK)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


hook = _load()

_RNG = random.Random(20261118)
_ALNUM = string.ascii_letters + string.digits


def _join(*pieces: str) -> str:
    return "".join(pieces)


def _rand(n: int) -> str:
    """`n` random alphanumerics, opening with one of each class so the body is
    always mixed, as a real key's is."""
    return "aB3" + "".join(_RNG.choice(_ALNUM) for _ in range(n - 3))


# kind fragment the reason must name -> a sample built from pieces
SAMPLES = {
    "AWS access key ID": _join("AK", "IA", "QWERTYUIOP234567"),
    "AWS access key ID (session)": _join("AS", "IA", "QWERTYUIOP234567"),
    "GitHub token (no digit)": _join("gh", "p_", "aBcDeFgHiJkLmNoPqRsTuVwXyZaBcDeFgHiJ"),
    "Google API key (no digit)": _join("AI", "za", "SyAbCdEfGhIjKlMnOpQrStUvWxYz_AbCdEf"),
    "GitHub token": _join("gh", "p_", _rand(36)),
    "GitHub token (OAuth)": _join("gh", "o_", _rand(36)),
    "GitHub token (server)": _join("gh", "s_", _rand(36)),
    "GitHub fine-grained token": _join("github", "_pat_", _rand(22), "_", _rand(59)),
    "Anthropic API key": _join("sk", "-ant-", "api03-", _rand(80)),
    "OpenAI API key": _join("sk", "-proj-", _rand(48)),
    "OpenAI API key (legacy)": _join("sk", "-", _rand(48)),
    "Slack token": _join("xo", "xb-", "123456789012-1234567890123-", _rand(24)),
    "Slack token (user)": _join("xo", "xp-", "123456789012-1234567890123-", _rand(24)),
    "Slack token (refresh)": _join("xo", "xe-", "1-", _rand(30), "7"),
    "Google API key": _join("AI", "za", _rand(35)),
    "Stripe live key": _join("sk", "_live_", _rand(24)),
    "Stripe live key (restricted)": _join("rk", "_live_", _rand(24)),
    "private key": _join("-----BEGIN ", "RSA ", "PRIV", "ATE KEY-----"),
    "private key (PKCS8)": _join("-----BEGIN ", "PRIV", "ATE KEY-----"),
    "private key (OpenSSH)": _join("-----BEGIN ", "OPENSSH ", "PRIV", "ATE KEY-----"),
    "password in a connection URL": _join("postgres://app:", "s3cr3t", "Passw0rd", "@db.internal:5432/app"),
    "password in a connection URL (empty user)": _join("redis://:", "hunter2", "Zq", "@cache:6379"),
    "password in a connection URL (an @ in it)": _join("postgres://app:", "P", "@ssw0rd", "Kq9", "@db:5432/app"),
    "password in a connection URL (a stand-in word, then @)": _join("mysql://root:", "Pass", "@123", "zQ", "@db/app"),
    "password in a connection URL (a colon in it)": _join("postgres://app:", "Pa:ss", "W0rd9", "@db/app"),
    "password in a connection URL (a slash in it)": _join("postgres://app:", "pa/ss", "W0rdQ", "@db:5432/app"),
    "password in a connection URL (dollar, lower case)": _join("postgres://app:", "$ecret", "Pw9", "@db/app"),
    "password in a connection URL (a real token as the password)": _join(
        "https://x-access-token:", "gh", "s_", _rand(36), "@github.com/o/r.git"),
    "JWT": _join("ey", "J", _rand(20), ".", "ey", "J", _rand(40), ".", _rand(43)),
}


def _kind(label: str) -> str:
    return label.split(" (")[0]


def test_the_samples_have_the_lengths_the_formats_have():
    # Fixed-length formats: a sample of the wrong length would test nothing.
    assert len(SAMPLES["GitHub token (no digit)"]) == 4 + 36
    assert len(SAMPLES["Google API key (no digit)"]) == 4 + 35


def _payload(target, text: str, tool: str = "Write", cwd=None) -> dict:
    tool_input = {"file_path": str(target)}
    if tool == "Edit":
        tool_input.update(old_string="placeholder", new_string=text)
    else:
        tool_input["content"] = text
    payload = {"tool_name": tool, "tool_input": tool_input}
    if cwd is not None:
        payload["cwd"] = str(cwd)
    return payload


def _run(monkeypatch, payload) -> tuple[int, str]:
    text = payload if isinstance(payload, str) else json.dumps(payload)
    monkeypatch.setattr(sys, "stdin", io.StringIO(text))
    out = io.StringIO()
    monkeypatch.setattr(sys, "stdout", out)
    rc = hook.main()
    return rc, out.getvalue()


def _asks(monkeypatch, payload) -> str:
    rc, out = _run(monkeypatch, payload)
    assert rc == 0, "an ask exits 0; only a block exits 2"
    assert out, "expected an ask, got silence"
    nested = json.loads(out)["hookSpecificOutput"]
    assert nested["hookEventName"] == "PreToolUse"
    assert nested["permissionDecision"] == "ask"
    return nested["permissionDecisionReason"]


def _silent(monkeypatch, payload) -> None:
    rc, out = _run(monkeypatch, payload)
    assert rc == 0
    assert out == "", out


@pytest.fixture
def repo(tmp_path) -> Path:
    root = tmp_path / "repo"
    (root / "cla.io" / "checkpoints").mkdir(parents=True)
    return root


def _checkpoint(repo: Path) -> Path:
    return repo / "cla.io" / "checkpoints" / "2026-11-18-session.md"


# --------------------------------------------------------------------------- #
# Each shape asks, through each tool, and the value never leaves the hook
# --------------------------------------------------------------------------- #


# requirement: guard-hooks / A secret written into a committed briefing asks first
@pytest.mark.parametrize("tool", ["Edit", "Write"])
@pytest.mark.parametrize("label", sorted(SAMPLES))
def test_each_secret_shape_asks_and_never_echoes_the_value(repo, monkeypatch, tool, label):
    value = SAMPLES[label]
    text = f"# Where things stand\n\nThe service read {value} from its environment.\n"
    reason = _asks(monkeypatch, _payload(_checkpoint(repo), text, tool))
    assert _kind(label) in reason
    assert "on line 3" in reason
    assert value not in reason
    # Not even a long piece of it: the reason carries the kind, never the body.
    assert not any(value[i:i + 12] in reason for i in range(len(value) - 11))


def test_the_reason_points_at_the_rule_and_names_the_target(repo, monkeypatch):
    target = _checkpoint(repo)
    reason = _asks(monkeypatch, _payload(target, SAMPLES["GitHub token"]))
    assert "Name the file, not its value" in reason
    assert "git history" in reason
    assert str(target) in reason
    assert "(hook: ask-secret-in-checkpoint.py)" in reason


def test_the_reason_carries_none_of_the_copilot_failure_markers(repo, monkeypatch):
    # The Copilot adapter turns an ask whose reason says a guard "could not run"
    # or "did not run" into a deny; this ask is a real one and has to stay one.
    reason = _asks(monkeypatch, _payload(_checkpoint(repo), SAMPLES["JWT"])).lower()
    assert "could not run" not in reason
    assert "did not run" not in reason


def test_several_findings_are_named_in_line_order(repo, monkeypatch):
    text = "\n".join([
        "intro",
        SAMPLES["password in a connection URL"],
        "middle",
        SAMPLES["AWS access key ID"],
    ])
    reason = _asks(monkeypatch, _payload(_checkpoint(repo), text))
    url = reason.index("a password in a connection URL on line 2")
    aws = reason.index("an AWS access key ID on line 4")
    assert url < aws
    assert "more" not in reason  # nothing past the cap, so nothing counted


def test_an_anthropic_key_is_named_once_not_also_as_an_openai_key(repo, monkeypatch):
    reason = _asks(monkeypatch, _payload(_checkpoint(repo), SAMPLES["Anthropic API key"]))
    assert "an Anthropic API key on line 1" in reason
    assert "OpenAI" not in reason


def test_new_text_in_either_field_is_read_when_the_other_is_not_a_string(repo, monkeypatch):
    payload = {"tool_input": {"file_path": str(_checkpoint(repo)), "content": None,
                              "new_string": SAMPLES["GitHub token"]}}
    _asks(monkeypatch, payload)


def test_findings_past_the_cap_are_counted_not_named(repo, monkeypatch):
    lines = [SAMPLES["AWS access key ID"]] * 13
    reason = _asks(monkeypatch, _payload(_checkpoint(repo), "\n".join(lines)))
    assert "on line 10;" in reason
    assert "on line 11" not in reason
    assert "and 3 more" in reason


def test_each_new_string_of_a_multi_edit_is_read(repo, monkeypatch):
    payload = {"tool_name": "MultiEdit", "tool_input": {
        "file_path": str(_checkpoint(repo)),
        "edits": [
            {"old_string": "a", "new_string": "clean\n"},
            "not an edit",
            {"old_string": "b", "new_string": None},
            {"old_string": "c", "new_string": "intro\n" + SAMPLES["Stripe live key"]},
        ],
    }}
    reason = _asks(monkeypatch, payload)
    assert "a Stripe live key on line 2 of edit 4" in reason
    assert SAMPLES["Stripe live key"] not in reason


def test_a_multi_edit_with_only_clean_text_stays_silent(repo, monkeypatch):
    payload = {"tool_input": {"file_path": str(_checkpoint(repo)), "edits": [
        {"old_string": SAMPLES["Stripe live key"], "new_string": "moved to `.env`"}]}}
    _silent(monkeypatch, payload)


def test_an_edit_that_removes_a_secret_stays_silent(repo, monkeypatch):
    # Only the new text is checked: taking a key out is the fix, not the leak.
    payload = {"tool_name": "Edit", "tool_input": {
        "file_path": str(_checkpoint(repo)),
        "old_string": SAMPLES["GitHub token"],
        "new_string": "the token lives in `.env` as `GH_TOKEN`",
    }}
    _silent(monkeypatch, payload)


# --------------------------------------------------------------------------- #
# Placeholders and ordinary prose stay silent
# --------------------------------------------------------------------------- #


SILENT_TEXT = [
    # a commit sha and a UUID
    "Landed in 80c3c6e9a1b2c3d4e5f60718293a4b5c6d7e8f90 (#534).",
    "run id 123e4567-e89b-12d3-a456-426614174000",
    # `sk-` inside a word, and too short or unmixed after it
    "a risk-assessment-for-the-guard-hooks-change was skipped",
    "the desk-based review",
    "pip install sk-learn",
    _join("sk", "-this-is-a-very-long-kebab-case-branch-name"),
    # URLs without a password, or with a placeholder one
    "https://github.com/owner/repo/pull/529",
    "ssh://git@github.com/owner/repo.git",
    "http://localhost:8080/path@anchor",
    "https://user@host.example/path",
    _join("postgres://user:", "<password>", "@localhost/db"),
    _join("postgres://user:", "***", "@localhost/db"),
    _join("postgres://user:", "password", "@localhost/db"),
    _join("postgres://user:", "PASS", "@localhost/db"),
    _join("postgres://user:", "ChangeMe", "@localhost/db"),
    _join("postgres://user:", "xxx", "@localhost/db"),
    _join("postgres://user:", "${DB_PASSWORD}", "@localhost/db"),
    _join("postgres://user:", "$DB_PASSWORD", "@localhost/db"),
    _join("postgres://user:", "{password}", "@localhost/db"),
    _join("postgres://", "postgres:postgres", "@localhost:5432/test"),
    _join("postgres://user:", "<your password>", "@localhost/db"),
    _join("postgres://postgres:", "mysecretpassword", "@localhost:5432/postgres"),
    _join("postgres://user:", "%3Cpassword%3E", "@localhost/db"),
    _join("postgresql://user:", "pw", "@/db?host=/cloudsql/p:r:i"),
    _join("https://x-access-token:", "TOKEN", "@github.com/owner/repo.git"),
    _join("https://oauth2:", "token", "@gitlab.example/owner/repo.git"),
    _join("postgres://user:", "", "@localhost/db"),
    "redis://localhost:6379/0",
    _join("sk", "-proj-", "x" * 48),
    _join("https://x-access-token:", "GITHUB_TOKEN", "@github.com/owner/repo.git"),
    _join("postgres://user:pass", "@host:5432/db?replica=a@b"),
    "https://medium.com:443/@someone/a-post",
    "http://[::1]:8080/path@anchor",
    _join("sk", "-Learn2Rank-Model-For-Search-Results-2026-Edition"),
    _join("sk", "-Abcdefghij1234567890ABCDEFGHIJ1234-and-a-suffix"),
    _join("gh", "p_", "aB3", "c" * 34),
    # key prefixes with placeholder bodies, or bodies missing one of the three
    # character classes a random key has
    _join("sk", "-fix-issue-1234-in-the-parser-now"),
    _join("sk", "-ThisIsAnUpperCamelCaseIdentifierName"),
    _join("gh", "p_", "ABC123" * 6),
    _join("github", "_pat_", "x" * 82),
    _join("sk", "-ant-", "api03-", "x" * 40),
    _join("AK", "IA", "XY" * 8),
    _join("gh", "p_", "x" * 36),
    _join("gh", "p_", "X" * 36),
    _join("AK", "IA", "X" * 16),
    _join("xo", "xb-", "your-token-goes-here"),
    _join("sk", "_live_", "x" * 24),
    _join("sk", "_live_", "ABCD1234" * 3),
    _join("AI", "za", "-" * 35),
    # a key prefix glued to a longer word on either side
    _join("XAK", "IA", "QWERTYUIOP234567"),
    _join("AK", "IA", "QWERTYUIOP2345678"),
    # header words that are not a private key
    "-----BEGIN CERTIFICATE-----",
    "-----BEGIN PUBLIC KEY-----",
    # a JWT-like string with only two segments
    _join("ey", "J", "a" * 20, ".", "ey", "J", "b" * 20),
    "Plain prose: the token is in `.env` under `GH_TOKEN`; name the file, not its value.",
]


@pytest.mark.parametrize("text", SILENT_TEXT)
def test_placeholders_and_ordinary_prose_stay_silent(repo, monkeypatch, text):
    _silent(monkeypatch, _payload(_checkpoint(repo), f"line one\n{text}\n"))


# The token shapes whose prefix must open a run: a connection URL is left out
# (a scheme with a letter in front is still a scheme), and so is a private-key
# header, which has no run to open.
_GLUED = sorted(
    label for label in SAMPLES
    if not label.startswith(("password in a connection URL", "private key"))
)


@pytest.mark.parametrize("label", _GLUED)
def test_a_key_shape_inside_a_longer_run_stays_silent(repo, monkeypatch, label):
    # A key-like stretch in the middle of a base64 blob (an embedded image, a
    # hash) is not a key: each prefix must open its run, not sit inside one.
    _silent(monkeypatch, _payload(_checkpoint(repo), "Q" + SAMPLES[label] + "\n"))


# A backslash and a letter, as text: what a JSON string or a shell `printf`
# shows for a newline, a carriage return or a tab. And a percent-escape.
_ESCAPES = ["\\n", "\\r", "\\t", "%3D", "%20"]


@pytest.mark.parametrize("escape", _ESCAPES)
@pytest.mark.parametrize("label", ["GitHub token", "OpenAI API key (legacy)", "AWS access key ID"])
def test_a_key_right_after_a_written_escape_asks(repo, monkeypatch, escape, label):
    text = _join("export TOKEN=", escape, SAMPLES[label], "\n")
    reason = _asks(monkeypatch, _payload(_checkpoint(repo), text))
    assert _kind(label) in reason


def test_the_escapes_are_written_text_not_control_characters():
    assert [len(e) for e in _ESCAPES] == [2, 2, 2, 3, 3]


def test_a_google_shaped_run_one_character_too_long_stays_silent(repo, monkeypatch):
    _silent(monkeypatch, _payload(_checkpoint(repo), SAMPLES["Google API key"] + "Q\n"))


# --------------------------------------------------------------------------- #
# Scope: the four committed briefing directories, nothing else
# --------------------------------------------------------------------------- #


# requirement: guard-hooks / A secret written into a committed briefing asks first
@pytest.mark.parametrize(
    "relative",
    [
        "cla.io/checkpoints/2026-11-18-x.md",
        "cla.io/decisions/topic-2026-11-18.md",
        "cla.io/feedback/feedback-session-2026-11-18.md",
        "cla.io/lessons-learned/lessons-learned.md",
        "cla.io/checkpoints/nested/deeper/x.md",
        "CLA.IO/Checkpoints/x.md",
        "cla.io/checkpoints./x.md",
        "cla.io /decisions /x.md",
        ".claude/worktrees/abc/cla.io/feedback/notes.md",
    ],
)
def test_a_briefing_directory_asks(tmp_path, monkeypatch, relative):
    _asks(monkeypatch, _payload(tmp_path / relative, SAMPLES["Stripe live key"]))


# requirement: guard-hooks / A secret written into a committed briefing asks first
@pytest.mark.parametrize(
    "relative",
    [
        "src/settings.py",
        ".env",
        "cla.io/project-facts.md",
        "cla.io/overlays/spec-to-pr.md",
        "cla.io/audits/x.md",
        "cla.io/checkpoints",  # the directory name as a file, nothing below it
        "checkpoints/x.md",  # no cla.io/ above it
        "cla.io-old/checkpoints/x.md",
        "cla.io/checkpoints-old/x.md",
        "docs/cla.io/x/checkpoints/y.md",  # not adjacent
    ],
)
def test_a_path_outside_the_scope_stays_silent(tmp_path, monkeypatch, relative):
    _silent(monkeypatch, _payload(tmp_path / relative, SAMPLES["Stripe live key"]))


def test_a_relative_path_is_read_against_the_payload_cwd(repo, monkeypatch):
    payload = _payload("cla.io/checkpoints/x.md", SAMPLES["Anthropic API key"], cwd=repo)
    _asks(monkeypatch, payload)
    inner = _payload("checkpoints/x.md", SAMPLES["Anthropic API key"], cwd=repo / "cla.io")
    _asks(monkeypatch, inner)


def test_an_empty_cwd_still_names_the_absolute_target(repo, monkeypatch):
    monkeypatch.chdir(repo)
    payload = _payload("cla.io/checkpoints/x.md", SAMPLES["Anthropic API key"])
    payload["cwd"] = ""
    assert f"'{_checkpoint(repo).parent / 'x.md'}'" in _asks(monkeypatch, payload)


def test_a_windows_style_path_asks(tmp_path, monkeypatch):
    target = "C:\\Users\\me\\repo\\cla.io\\checkpoints\\x.md"
    _asks(monkeypatch, _payload(target, SAMPLES["Stripe live key"], cwd=tmp_path))


def test_a_relative_path_without_a_cwd_uses_the_process_cwd(repo, monkeypatch):
    monkeypatch.chdir(repo)
    payload = _payload("cla.io/checkpoints/x.md", SAMPLES["Anthropic API key"])
    payload["cwd"] = 7
    _asks(monkeypatch, payload)
    payload["cwd"] = ""
    _asks(monkeypatch, payload)


@pytest.mark.skipif(not hasattr(os, "symlink"), reason="no symlinks")
def test_a_symlink_into_a_briefing_directory_asks(repo, monkeypatch):
    link = repo / "notes"
    try:
        link.symlink_to(repo / "cla.io" / "checkpoints", target_is_directory=True)
    except OSError:
        pytest.skip("symlink creation not permitted")
    _asks(monkeypatch, _payload(link / "x.md", SAMPLES["OpenAI API key"]))


@pytest.mark.skipif(not hasattr(os, "symlink"), reason="no symlinks")
def test_a_briefing_directory_that_is_a_symlink_elsewhere_still_asks(repo, tmp_path, monkeypatch):
    # The path names the scope even though the folder it resolves to does not.
    shared = tmp_path / "shared-notes"
    shared.mkdir()
    link = repo / "cla.io" / "decisions"
    try:
        link.symlink_to(shared, target_is_directory=True)
    except OSError:
        pytest.skip("symlink creation not permitted")
    _asks(monkeypatch, _payload(link / "x.md", SAMPLES["OpenAI API key"]))


def test_a_tilde_path_is_expanded(repo, tmp_path, monkeypatch):
    # A home that is itself a briefing directory, so only the expanded `~`
    # names the scope: joined unexpanded, `<cwd>/~/x.md` lies outside it.
    home = repo / "cla.io" / "decisions"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    _asks(monkeypatch, _payload("~/x.md", SAMPLES["OpenAI API key"], cwd=tmp_path))


# --------------------------------------------------------------------------- #
# Malformed input fails open
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "not json",
        "[]",
        "{}",
        json.dumps({"tool_input": None}),
        json.dumps({"tool_input": {}}),
        json.dumps({"tool_input": {"file_path": None, "content": "x"}}),
        json.dumps({"tool_input": {"file_path": 7, "content": "x"}}),
        json.dumps({"tool_input": {"file_path": "cla.io/checkpoints/x.md", "content": None}}),
        json.dumps({"tool_input": {"file_path": "cla.io/checkpoints/x.md", "content": 7}}),
        json.dumps({"tool_input": {"file_path": "cla.io/checkpoints/x.md"}}),
    ],
)
def test_malformed_input_fails_open_silently(monkeypatch, raw):
    _silent(monkeypatch, raw)


def test_an_empty_file_path_is_not_read_as_the_cwd(repo, monkeypatch):
    # Joined to a cwd inside a briefing directory, "" would otherwise name it.
    payload = _payload("", SAMPLES["GitHub token"], cwd=repo / "cla.io" / "checkpoints" / "sub")
    _silent(monkeypatch, payload)


def _broken(text):
    raise RuntimeError("planted")


def test_a_crash_inside_the_scan_is_not_swallowed(repo, monkeypatch):
    # A scanner defect must not pass as "no secret here".
    monkeypatch.setattr(hook, "_findings", _broken)
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(
        _payload(_checkpoint(repo), SAMPLES["GitHub token"]))))
    with pytest.raises(RuntimeError, match="planted"):
        hook.main()


# requirement: guard-hooks / A secret written into a committed briefing asks first
def test_a_crash_inside_the_scan_makes_the_dispatcher_ask(repo, monkeypatch, capsys):
    # The hook is enforcing, so the dispatcher turns its crash into an ask.
    if str(_HOOKS_DIR) not in sys.path:
        sys.path.insert(0, str(_HOOKS_DIR))
    spec = importlib.util.spec_from_file_location("dispatch_edit_write_for_crash", _DISPATCH)
    dispatcher = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(dispatcher)
    import _dispatch_lib as lib

    monkeypatch.setattr(hook, "_findings", _broken)

    def run(filename, stdin_text, argv=None):
        if filename == "ask-secret-in-checkpoint.py":
            return lib.run_hook(hook, stdin_text)
        return lib.HookResult(0, "", "")

    monkeypatch.setattr(dispatcher, "run_hook_file", run)
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(
        _payload(_checkpoint(repo), "clean text\n"))))
    assert dispatcher.main() == 0
    nested = json.loads(capsys.readouterr().out)["hookSpecificOutput"]
    assert nested["permissionDecision"] == "ask"
    assert "ask-secret-in-checkpoint.py" in nested["permissionDecisionReason"]
    assert "ENFORCING" in nested["permissionDecisionReason"]


def test_a_path_that_cannot_be_resolved_fails_open(tmp_path, monkeypatch):
    # Path resolution is input handling: it stays inside the fail-open `try`.
    def broken(path, *a, **k):
        raise OSError("planted")

    monkeypatch.setattr(hook.os.path, "realpath", broken)
    _silent(monkeypatch, _payload(tmp_path / "notes" / "x.md", SAMPLES["GitHub token"]))


# --------------------------------------------------------------------------- #
# Linear time on a large payload
# --------------------------------------------------------------------------- #

_MB = 1 << 20

LARGE = {
    "prose": ("The guard reads the new text of a briefing and asks. " * 20000)[:_MB],
    "jwt prefixes": "eyJ" * (_MB // 3),
    "sk- prefixes": _join("sk", "-") * (_MB // 3),
    "url fragments": "!a://u:" * (_MB // 7),
    "one long user part": "a://" + "b" * _MB,
    "dashes": "-" * _MB,
    "private key prefixes": "-----BEGIN " * (_MB // 11),
    "github prefixes": _join("gh", "p_") * (_MB // 4),
    "newlines": "\n" * _MB,
    "urls with no whitespace": "a://u:" * (_MB // 6),
    "slashes after user:": "a://u:" + "x/" * (_MB // 2),
    "at signs after user:": "a://u:" + "@" * _MB,
    "written escapes": "\\n" * (_MB // 2),
    "percent-escapes": "%3D" * (_MB // 3),
    "github prefixes after escapes": _join("\\n", "gh", "p_") * (_MB // 6),
}


@pytest.mark.parametrize("name", sorted(LARGE))
def test_a_megabyte_payload_is_scanned_in_linear_time(repo, monkeypatch, name):
    text = LARGE[name]
    assert len(text) >= _MB - 16
    started = time.perf_counter()
    _run(monkeypatch, _payload(_checkpoint(repo), text))
    # Measured at about 0.5-0.7 s per payload (Python 3.13, Linux, timing
    # `_findings` on each of these); a scan that backtracks quadratically, or
    # rescans a run from every start, takes minutes on any of them.
    assert time.perf_counter() - started < 5.0


def test_a_megabyte_payload_with_a_secret_at_the_end_still_asks(repo, monkeypatch):
    text = LARGE["prose"] + "\n" + SAMPLES["Google API key"] + "\n"
    started = time.perf_counter()
    reason = _asks(monkeypatch, _payload(_checkpoint(repo), text))
    assert time.perf_counter() - started < 5.0
    assert "a Google API key on line 2" in reason


# --------------------------------------------------------------------------- #
# Through the real dispatcher process
# --------------------------------------------------------------------------- #


def _dispatch(payload: dict, cwd: Path) -> subprocess.CompletedProcess:
    env = dict(os.environ, ALLOW_WORKTREE_PATH_ESCAPE="")
    return subprocess.run(
        [sys.executable, str(_DISPATCH)],
        input=json.dumps(payload), capture_output=True, text=True, encoding="utf-8",
        errors="replace", cwd=str(cwd), env=env, timeout=60,
    )


# requirement: guard-hooks / A secret written into a committed briefing asks first
@pytest.mark.parametrize("tool", ["Edit", "Write"])
def test_the_dispatcher_reemits_the_ask(repo, tool):
    value = SAMPLES["password in a connection URL"]
    r = _dispatch(_payload(_checkpoint(repo), value, tool, cwd=repo), repo)
    assert r.returncode == 0, r.stderr
    nested = json.loads(r.stdout)["hookSpecificOutput"]
    assert nested["permissionDecision"] == "ask"
    assert "ask-secret-in-checkpoint.py" in nested["permissionDecisionReason"]
    assert value not in r.stdout
    assert value not in r.stderr


def test_the_dispatcher_stays_silent_for_a_clean_checkpoint(repo):
    r = _dispatch(_payload(_checkpoint(repo), "# Where things stand\n\nAll merged.\n", cwd=repo), repo)
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == ""
