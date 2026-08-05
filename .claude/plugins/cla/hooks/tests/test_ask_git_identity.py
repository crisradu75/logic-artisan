"""Tests for `ask-git-identity.py`.

The property worth protecting is that this hook is SILENT by default. It runs on
every commit and every push, so a false positive would be seen constantly and the
prompt would stop being read — which is the failure mode that makes a checkpoint
worthless. It speaks in exactly two situations: no identity configured at all
(warn), and a mismatch against an explicitly stated expectation (ask).
"""

from __future__ import annotations

import importlib.util
import io
import json
import subprocess
import sys
from pathlib import Path

import pytest

_HOOKS_DIR = Path(__file__).resolve().parent.parent


def _load():
    spec = importlib.util.spec_from_file_location(
        "ask_git_identity", _HOOKS_DIR / "ask-git-identity.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


hook = _load()


def _git(cwd, *args):
    subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True, text=True)


@pytest.fixture
def repo(tmp_path, monkeypatch):
    """A repo with NO user.email — the identity is set per-test."""
    _git(tmp_path, "init", "-b", "main")
    # Neutralize any ambient expectation/override from the developer's own env.
    monkeypatch.delenv("CLA_EXPECTED_GIT_EMAIL", raising=False)
    monkeypatch.delenv("ALLOW_GIT_IDENTITY_MISMATCH", raising=False)
    return tmp_path


def _run(command: str, cwd, monkeypatch, capsys):
    monkeypatch.setattr(
        sys, "stdin",
        io.StringIO(json.dumps({"tool_input": {"command": command}, "cwd": str(cwd)})),
    )
    code = hook.main()
    assert code == 0, "this hook must never block"
    captured = capsys.readouterr()
    out = captured.out.strip()
    return (json.loads(out) if out else None), captured.err


# --------------------------------------------------------------------------- #
# Silence -- the default, and the property that keeps the prompt worth reading
# --------------------------------------------------------------------------- #


def test_matching_identity_is_silent(repo, monkeypatch, capsys):
    _git(repo, "config", "user.email", "me@example.com")
    monkeypatch.setenv("CLA_EXPECTED_GIT_EMAIL", "me@example.com")
    payload, err = _run("git commit -m x", repo, monkeypatch, capsys)
    assert payload is None and err.strip() == ""


def test_identity_present_with_no_expectation_is_silent(repo, monkeypatch, capsys):
    # Zero-config: the harness cannot know your identity, so an unset
    # expectation must not manufacture one.
    _git(repo, "config", "user.email", "whoever@example.com")
    payload, err = _run("git commit -m x", repo, monkeypatch, capsys)
    assert payload is None and err.strip() == ""


@pytest.mark.parametrize(
    "command",
    ["git status", "git log --oneline", "ls -la", "git add -A", "git checkout -b feature/x"],
)
def test_commands_that_do_not_bake_an_identity_are_ignored(command, repo, monkeypatch, capsys):
    monkeypatch.setenv("CLA_EXPECTED_GIT_EMAIL", "expected@example.com")
    _git(repo, "config", "user.email", "different@example.com")
    payload, err = _run(command, repo, monkeypatch, capsys)
    assert payload is None and err.strip() == ""


# --------------------------------------------------------------------------- #
# The two things it does say
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("command", ["git commit -m x", "git push origin main"])
def test_mismatch_against_an_explicit_expectation_asks(command, repo, monkeypatch, capsys):
    _git(repo, "config", "user.email", "work@company.example")
    monkeypatch.setenv("CLA_EXPECTED_GIT_EMAIL", "me@personal.example")
    payload, _err = _run(command, repo, monkeypatch, capsys)
    assert payload is not None, f"expected an ask for: {command!r}"
    nested = payload["hookSpecificOutput"]
    assert nested["permissionDecision"] == "ask"
    reason = nested["permissionDecisionReason"]
    # Both addresses must appear: which one is wrong is the whole message.
    assert "work@company.example" in reason and "me@personal.example" in reason


def test_missing_identity_warns_even_with_no_expectation_set(repo, tmp_path, monkeypatch, capsys):
    # `git config user.email` reports the EFFECTIVE value, so a fresh repo still
    # inherits whatever global identity the machine has — which is why this case
    # needs git's global and system config explicitly pointed at nothing. Without
    # that, this test passes or fails depending on whose machine runs it.
    absent = tmp_path / "no-such-gitconfig"
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(absent))
    monkeypatch.setenv("GIT_CONFIG_SYSTEM", str(absent))

    payload, err = _run("git commit -m x", repo, monkeypatch, capsys)
    assert payload is None, "a missing identity warns; it does not escalate"
    assert "no `user.email`" in err
    assert "ask-git-identity.py" in err


def test_commit_is_covered_not_just_push(repo, monkeypatch, capsys):
    # Commit is where the email is actually baked in, so catching it only at
    # push time would be catching it after the fact.
    _git(repo, "config", "user.email", "wrong@example.com")
    monkeypatch.setenv("CLA_EXPECTED_GIT_EMAIL", "right@example.com")
    payload, _ = _run("git commit -m 'a message'", repo, monkeypatch, capsys)
    assert payload is not None


def test_a_global_option_before_the_subcommand_is_not_a_bypass(repo, monkeypatch, capsys):
    _git(repo, "config", "user.email", "wrong@example.com")
    monkeypatch.setenv("CLA_EXPECTED_GIT_EMAIL", "right@example.com")
    payload, _ = _run("git -c core.pager=cat commit -m x", repo, monkeypatch, capsys)
    assert payload is not None


# --------------------------------------------------------------------------- #
# Contract
# --------------------------------------------------------------------------- #


def test_override_env_var_silences_everything(repo, monkeypatch, capsys):
    monkeypatch.setenv("CLA_EXPECTED_GIT_EMAIL", "right@example.com")
    monkeypatch.setenv("ALLOW_GIT_IDENTITY_MISMATCH", "1")
    _git(repo, "config", "user.email", "wrong@example.com")
    payload, err = _run("git commit -m x", repo, monkeypatch, capsys)
    assert payload is None and err.strip() == ""


def test_a_commit_mentioned_inside_a_quoted_string_is_not_an_invocation(repo, monkeypatch, capsys):
    monkeypatch.setenv("CLA_EXPECTED_GIT_EMAIL", "right@example.com")
    _git(repo, "config", "user.email", "wrong@example.com")
    payload, err = _run('echo "remember to git commit later"', repo, monkeypatch, capsys)
    assert payload is None and err.strip() == ""


def _break_git(monkeypatch):
    """Force `_git_email` down its None path deterministically.

    `tmp_path` alone is NOT enough: `git config user.email` reports the
    EFFECTIVE value, so outside a repo it still answers from the machine's
    global config. Whether that path was reached at all therefore depended on
    whose machine ran the test.
    """
    def _boom(*_a, **_kw):
        raise subprocess.TimeoutExpired(cmd="git", timeout=1)

    monkeypatch.setattr(hook.subprocess, "run", _boom)


def test_unreadable_git_fails_open_and_silent_with_no_expectation(tmp_path, monkeypatch, capsys):
    # This hook is an identity check, not a git-health monitor — the sibling
    # hooks already report a broken git loudly, and a second voice saying it on
    # every command would be noise.
    monkeypatch.delenv("CLA_EXPECTED_GIT_EMAIL", raising=False)
    monkeypatch.delenv("ALLOW_GIT_IDENTITY_MISMATCH", raising=False)
    _break_git(monkeypatch)
    payload, err = _run("git commit -m x", tmp_path, monkeypatch, capsys)
    assert payload is None and err.strip() == ""


def test_unreadable_git_warns_when_an_expectation_is_configured(tmp_path, monkeypatch, capsys):
    # Setting CLA_EXPECTED_GIT_EMAIL asks for identity to be verified before
    # every commit. Silently skipping the check is the failure this hook exists
    # to prevent, so the skip has to be audible.
    monkeypatch.setenv("CLA_EXPECTED_GIT_EMAIL", "right@example.com")
    monkeypatch.delenv("ALLOW_GIT_IDENTITY_MISMATCH", raising=False)
    _break_git(monkeypatch)
    payload, err = _run("git commit -m x", tmp_path, monkeypatch, capsys)
    assert payload is None, "no evidence of a mismatch, so it warns rather than asks"
    assert "did NOT run" in err
    assert "ask-git-identity.py" in err


def test_malformed_payload_fails_open(monkeypatch, capsys):
    monkeypatch.setattr(sys, "stdin", io.StringIO("not json"))
    assert hook.main() == 0
    assert capsys.readouterr().out.strip() == ""
