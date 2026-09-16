"""The commit-provenance hook records what happened and never guesses.

This ledger exists to supply a denominator the retro loops have never had: how
many commits went through a skill versus around one. Two failure shapes would
destroy that number, and both are worse than the hook not existing:

  - OVER-recording. A line written for something that was not a commit (a
    `--dry-run`, a `git log --grep="git commit"`, a failed commit) inflates the
    total and makes bypass look better than it is.
  - WRONG attribution. Guessing a skill from an unrecognised subject inflates
    the numerator, which is the exact figure the loops would act on.

So the tests below are mostly about what it declines to write.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

_HOOK = Path(__file__).resolve().parents[3] / ".claude" / "plugins" / "cla" / "hooks" / "log-commit-provenance.py"


def _load():
    spec = importlib.util.spec_from_file_location("_log_commit_provenance", _HOOK)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


mod = _load()


# ---------- command recognition ----------


@pytest.mark.parametrize(
    "command",
    [
        "git commit -m 'x'",
        'git commit -m "feat: y"',
        "git -C /some/path commit -m 'x'",
        "git.exe commit -m 'x'",
        "GIT commit -m 'x'",
        # Global options before the subcommand, including quoted values.
        'git -C "/some path" commit -m "fix: x"',
        "git -c user.name='a b' commit --amend --no-edit",
        "git --no-pager commit -m x",
        "git --git-dir=/x/.git --work-tree /x commit -q",
        "GIT_AUTHOR_DATE=now git commit -q -F msg.txt",
        # Values the earlier whole-segment search recorded and a plain `\S+`
        # value would split in two.
        "git -C $(git rev-parse --show-toplevel) commit -m x",
        "git -C my\\ dir commit -m x",
        # A message file named after a history command is still a commit; the
        # old whole-segment `log|show|rev-list` exclusion dropped these.
        "git commit -F show.txt",
        "git commit -F log",
    ],
)
def test_a_real_commit_is_recognised(command):
    assert mod._is_commit_command(command) is True


@pytest.mark.parametrize(
    "command",
    [
        'git log --grep="git commit"',
        "git commit --dry-run",
        "git show HEAD --format='git commit'",
        "echo 'run git commit later'",
        "git rev-list --all",
        "git status",
        # The post-commit push/verify traffic issue #219 reports rows piling up
        # behind. `git status` was the only member of that family here, and it
        # is the one a recogniser is least likely to get wrong.
        "git push origin main",
        "git branch -a",
        "gh pr view 1 --json state",
        # "commit" inside an ARGUMENT, not as the subcommand. The first is the
        # command that stages this hook's own ledger, and a stash of that path
        # is what produced a duplicate row once the dedupe's last row was gone.
        "git add cla.io/retro/commit-provenance.jsonl",
        'git stash push -q -m "x" -- cla.io/retro/commit-provenance.jsonl',
        "git diff -- src/commit.py",
        "git checkout -- src/commit.py",
        "git commit-tree HEAD^{tree} -m x",
        "git log --oneline commit",
        "gh pr merge 1 --merge --match-head-commit abc123",
    ],
)
def test_a_non_commit_is_not_recognised(command):
    """Over-recording corrupts the ratio this hook exists to report."""
    assert mod._is_commit_command(command) is False


def test_a_long_run_of_value_taking_options_does_not_backtrack():
    """Each option that takes a separate value could, without a no-leading-dash
    rule, also read the NEXT option as its value, so a non-matching run of them
    backtracks exponentially. This runs in a PostToolUse hook, where a stall
    holds up the session. Measured before the rule: ~0.15s at 26 repeats,
    growing ~1.6x per word."""
    import time

    command = "git " + "--git-dir " * 34 + "status"
    started = time.monotonic()
    assert mod._is_commit_command(command) is False
    assert time.monotonic() - started < 1.0


# ---------- one call, several commands (issue #206) ----------
#
# Each check in `_is_commit_command` is about ONE command, so a call holding
# several must be split first. The separator set is the whole subject here: it
# was `|;&` and did NOT include the newline, so a `git commit` on one line and a
# `git log` on the next read as a single command and the commit was dropped.
# Under-recording costs the same denominator as over-recording.


@pytest.mark.parametrize(
    "command",
    [
        "git commit -m 'x'\ngit log -1 --pretty=%s",
        "git log -1 --pretty=%s\ngit commit -m 'x'",
        "git commit -m 'x'\r\ngit show HEAD",
        "git commit -m 'x'\ngit push --dry-run",
        "git add -- f.txt\ngit commit -m 'x'\ngit rev-list --count HEAD",
        # `&&` is the commonest multi-command idiom and had no case at all.
        "git commit -m 'x' && git log -1",
        # A backslash before a line break is a line CONTINUATION, so these two
        # physical lines are one command. Splitting there loses the commit.
        "git \\\n  commit -m 'x'",
        # The quoted body is blanked before the split, so its newline is not a
        # separator. This repo's own commit messages are multi-line.
        "git commit -m 'line one\nline two'",
    ],
)
def test_a_commit_beside_another_command_is_still_a_commit(command):
    """The exact shape that dropped this repo's own commits.

    Verifying a commit's trailers right after making it is what
    `spec-to-pr/references/ship.md` §2b encourages, so this call shape is the
    one an author following the skills is most likely to write.
    """
    assert mod._is_commit_command(command) is True


@pytest.mark.parametrize(
    "command",
    [
        # Prose, not a command. `strip_quoted_spans` does not blank heredoc
        # bodies, so this line reaches the loop as its own segment; only the
        # leads-with-git test rejects it. Before the split it was suppressed by
        # accident, because the `git log` line matched the whole-string
        # exclusion.
        "cat <<'EOF'\nReminder: run git commit once tests pass\nSee git log for context\nEOF",
        # A dry run in the same segment as the commit text.
        "git commit --dry-run\ngit status",
        # A history read in the same segment as the word commit — here it is
        # part of a filename. The subcommand match rejects it: `show`, not
        # `commit`, is the subcommand. (A separate history-command exclusion
        # used to catch this, and was removed because it also dropped real
        # commits like `git commit -F show.txt`.)
        "git status\ngit show HEAD -- cla.io/retro/commit-provenance.jsonl",
    ],
)
def test_splitting_does_not_admit_a_non_commit(command):
    """Splitting must not turn the exclusions into a way through.

    Each case fails a DIFFERENT test in the loop — leads-with-git, `--dry-run`,
    then the subcommand match. Three cases exiting by the same branch would look
    like coverage while proving one thing.
    """
    assert mod._is_commit_command(command) is False


# ---------- skill attribution ----------


@pytest.mark.parametrize(
    "subject,expected",
    [
        ("fix: review round 2", "spec-to-pr"),
        ("chore: archive add-thing", "spec-to-pr"),
        ("chore: spec-to-pr run log", "spec-to-pr"),
        ("fix: address review findings", "lite-pr"),
    ],
)
def test_a_known_skill_subject_is_attributed(subject, expected, monkeypatch):
    monkeypatch.delenv("CLAUDE_SKILL", raising=False)
    monkeypatch.delenv("CLA_ACTIVE_SKILL", raising=False)
    assert mod._detect_skill(subject) == expected


@pytest.mark.parametrize(
    "subject",
    [
        "docs: tidy the readme",
        "feat: something a human typed",
        "Merge pull request #12 from x",
        "release: 1.2.3",
    ],
)
def test_an_unrecognised_subject_is_null_not_guessed(subject, monkeypatch):
    """`null` is the honest answer. A guess here inflates the numerator, which is
    the one number a retro would act on."""
    monkeypatch.delenv("CLAUDE_SKILL", raising=False)
    monkeypatch.delenv("CLA_ACTIVE_SKILL", raising=False)
    assert mod._detect_skill(subject) is None


def test_an_explicit_env_skill_wins_over_subject_inference(monkeypatch):
    monkeypatch.setenv("CLAUDE_SKILL", "multi-pr")
    assert mod._detect_skill("fix: review round 1") == "multi-pr"


# ---------- end to end, against a real repo ----------


def _repo(tmp_path: Path) -> Path:
    def git(*a):
        subprocess.run(["git", *a], cwd=tmp_path, check=True, capture_output=True)

    git("init", "-q", "-b", "main")
    git("config", "user.email", "t@t")
    git("config", "user.name", "t")
    (tmp_path / "f.txt").write_text("x\n", encoding="utf-8")
    git("add", "f.txt")
    git("commit", "-q", "-m", "fix: review round 1")
    retro = tmp_path / "cla.io" / "retro"
    retro.mkdir(parents=True)
    # OPT IN. The ledger file's existence is the consent (issue #219), so a
    # fixture that only made the directory would exercise the off path and every
    # positive assertion below would pass for the wrong reason.
    (retro / "commit-provenance.jsonl").touch()
    return tmp_path


def _run(repo: Path, command: str, env_extra=None):
    import os

    env = {**os.environ, **(env_extra or {})}
    env.pop("CLAUDE_SKILL", None)
    env.pop("CLA_ACTIVE_SKILL", None)
    env.pop("CLAUDE_RETRO_DIR", None)
    payload = json.dumps({"tool_input": {"command": command}, "cwd": str(repo)})
    return subprocess.run(
        [sys.executable, str(_HOOK)],
        input=payload,
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )


def _git_out(repo: Path, *args: str) -> str:
    r = subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=True,
    )
    return r.stdout.strip()


def _ledger(repo: Path):
    f = repo / "cla.io" / "retro" / "commit-provenance.jsonl"
    if not f.is_file():
        return []
    return [json.loads(l) for l in f.read_text(encoding="utf-8").splitlines() if l.strip()]


def test_it_writes_one_line_for_a_real_commit(tmp_path):
    repo = _repo(tmp_path)
    r = _run(repo, "git commit -m 'fix: review round 1'")
    assert r.returncode == 0, r.stderr
    rows = _ledger(repo)
    assert len(rows) == 1
    assert rows[0]["subject"] == "fix: review round 1"
    assert rows[0]["skill"] == "spec-to-pr"
    assert rows[0]["branch"] == "main"
    assert rows[0]["sha"]


def test_a_commit_verified_in_the_same_call_is_recorded(tmp_path):
    """End to end for issue #206, not just the recogniser.

    The recogniser tests above pin `_is_commit_command`; this one shows a row
    actually lands, so a later refactor cannot satisfy them while the write path
    still drops the commit.
    """
    repo = _repo(tmp_path)
    r = _run(repo, "git commit -m 'fix: review round 1'\ngit log -1 --pretty=%s")
    assert r.returncode == 0, r.stderr
    rows = _ledger(repo)
    assert len(rows) == 1
    assert rows[0]["subject"] == "fix: review round 1"


def test_a_repeated_command_does_not_re_record_the_same_head(tmp_path):
    """The failed-commit shape: HEAD is real, but this command did not make it.

    A `git commit` with nothing staged exits non-zero and moves nothing, so the
    hook sees the PREVIOUS commit's HEAD and the reflog's top entry is still
    that commit — `_head_moved_by_commit` cannot tell the difference. Only the
    ledger's last row can. Issue #199: `f3735db` was recorded three times,
    byte-identically, from exactly this.
    """
    repo = _repo(tmp_path)
    assert _run(repo, "git commit -m 'fix: review round 1'").returncode == 0
    assert len(_ledger(repo)) == 1
    assert _run(repo, "git commit -m 'fix: review round 1'").returncode == 0
    assert len(_ledger(repo)) == 1


def test_read_only_git_calls_after_a_commit_add_no_further_rows(tmp_path):
    """Issue #219's own repro, which no existing test walks end to end.

    The reported shape is not a repeated COMMIT -- it is one commit followed by
    the ordinary read-only traffic a push/verify sequence makes: `git status`,
    `git log`, `git branch -a`, `gh pr view`. Three rows landed for one commit.

    WHAT THIS DOES AND DOES NOT PIN, because the first version of this docstring
    got it wrong and the test still passed. Measured by mutation: neutering the
    `_already_recorded` gate in `main()` leaves this test GREEN. It has to —
    none of these commands is commit-shaped, so `_is_commit_command` rejects
    them and `main()` returns before the dedupe is ever consulted. The dedupe is
    not under test here; the recogniser is, end to end and against a populated
    ledger.

    It earns its place on the traffic it names rather than on the gate: `git
    push`, `git branch -a` and `gh pr view` appear in no other test in this
    file, and they are exactly what the reported sequence was making when the
    rows piled up. A recogniser that admitted any of them would over-record,
    which this hook's own docstring calls worse than not existing.
    """
    repo = _repo(tmp_path)
    assert _run(repo, "git commit -m 'fix: review round 1'").returncode == 0
    assert len(_ledger(repo)) == 1
    recorded = _ledger(repo)[0]

    for command in (
        "git status",
        "git log -1 --pretty=%s",
        "git branch -a",
        "git push origin main",
        "gh pr view 1 --json state",
    ):
        assert _run(repo, command).returncode == 0, command
        rows = _ledger(repo)
        assert len(rows) == 1, f"{command!r} appended a row for a commit it did not make"
        assert rows[0] == recorded, f"{command!r} rewrote the recorded row"


def test_two_distinct_commits_each_earn_a_row(tmp_path):
    """The invariant no test in this file states by name: two commits, two rows.

    Every other multi-row test reaches two rows through an AMEND, which keeps
    one logical commit. The over-correction worth guarding is a dedupe that
    suppresses on any prior row rather than on a MATCHING sha: it deduplicates
    perfectly and drops the second commit of every pair.

    Stated honestly, because a redundant test that reads as unique coverage is
    its own defect: mutating the dedupe to `return True` is killed by the amend
    test too, so this adds no detection the suite lacked. It is kept for the
    invariant it names, not for a mutant only it catches.
    """
    repo = _repo(tmp_path)
    assert _run(repo, "git commit -m 'fix: review round 1'").returncode == 0
    first = _ledger(repo)
    assert len(first) == 1

    # `_run` only feeds the hook a PostToolUse payload -- it does not run the
    # command. The real second commit has to be made first, the way
    # `test_an_amended_commit_is_recorded_and_not_re_recorded` does, or HEAD
    # never moves and the dedupe suppresses for the right reason.
    (repo / "f.txt").write_text("second\n", encoding="utf-8")
    subprocess.run(
        ["git", "commit", "-q", "-a", "-m", "fix: review round 2"],
        cwd=repo, check=True, capture_output=True,
    )
    assert _run(repo, "git commit -m 'fix: review round 2'").returncode == 0

    rows = _ledger(repo)
    assert len(rows) == 2, "a second, genuinely different commit must earn its own row"
    assert rows[0]["sha"] != rows[1]["sha"]
    assert rows[1]["subject"] == "fix: review round 2"


def test_it_writes_nothing_when_head_last_moved_by_a_checkout(tmp_path):
    """The other half: HEAD belongs to work this command had no part in.

    Issue #199's second shape — a merge commit made days earlier on another
    branch, re-recorded under the branch that had just been checked out. The
    ledger holds a DIFFERENT sha here on purpose: with an empty ledger the
    dedupe would pass vacuously and this would not show the two gates acting
    independently. The dedupe genuinely lets this through; the reflog rejects it.
    """
    repo = _repo(tmp_path)
    _commit_with(repo, "fix: review round 1", None)
    assert _run(repo, "git commit -m 'fix: review round 1'").returncode == 0
    assert len(_ledger(repo)) == 1
    recorded = _ledger(repo)[0]["sha"]

    subprocess.run(["git", "checkout", "-q", "-b", "other"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "reset", "-q", "--hard", "HEAD~1"], cwd=repo, check=True, capture_output=True)
    assert _run(repo, "git commit -m 'fix: review round 1'").returncode == 0
    rows = _ledger(repo)
    assert len(rows) == 1, "HEAD moved by checkout/reset, so nothing new may be recorded"
    assert rows[0]["sha"] == recorded


def test_an_amended_commit_is_recorded_and_not_re_recorded(tmp_path):
    """`commit (amend):` is an accepted reflog reason and needs its own test.

    Nothing else in this file amends, so without this the entry could be
    dropped from `_COMMIT_REFLOG_REASONS` and every test would still pass.
    """
    repo = _repo(tmp_path)
    _commit_with(repo, "fix: review round 1", None)
    assert _run(repo, "git commit -m 'fix: review round 1'").returncode == 0
    assert len(_ledger(repo)) == 1

    subprocess.run(
        ["git", "commit", "-q", "--amend", "-m", "fix: review round 2"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    assert _run(repo, "git commit --amend -m 'fix: review round 2'").returncode == 0
    rows = _ledger(repo)
    assert len(rows) == 2, "an amend is a real commit and earns a row"
    assert rows[1]["subject"] == "fix: review round 2"

    assert _run(repo, "git commit --amend -m 'fix: review round 2'").returncode == 0
    assert len(_ledger(repo)) == 2, "the same amended sha is not recorded twice"


def test_a_repo_without_a_reflog_still_records_its_commits(tmp_path):
    """An empty reflog is "cannot tell", never "not a commit".

    `core.logAllRefUpdates=false`, an expired reflog and a deleted
    `.git/logs/HEAD` all leave `rev-parse` and `log -1` working while
    `git reflog` succeeds with no output. Reading that as a negative would drop
    every row for the life of the repo, and the ledger would be indistinguishable
    from a repo that never commits.
    """
    repo = _repo(tmp_path)
    subprocess.run(
        ["git", "config", "core.logAllRefUpdates", "false"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    # The whole tree, not just `logs/HEAD`: git falls back to the per-branch log
    # at `logs/refs/heads/<branch>` and the reflog comes back populated.
    shutil.rmtree(repo / ".git" / "logs")
    assert _git_out(repo, "reflog", "-1", "--format=%gs") == ""

    _commit_with(repo, "fix: review round 1", None)
    assert _run(repo, "git commit -m 'fix: review round 1'").returncode == 0
    assert len(_ledger(repo)) == 1


def test_the_dedupe_survives_a_shorter_stored_sha(tmp_path):
    """`rev-parse --short` has no fixed width, so equality is not enough.

    Git recomputes the abbreviation from the object count, so a sha stored at
    one width can come back wider in the same repo. An equality test would stop
    deduplicating at exactly that point, which is the duplicate this fix exists
    to prevent.
    """
    repo = _repo(tmp_path)
    _commit_with(repo, "fix: review round 1", None)
    assert _run(repo, "git commit -m 'fix: review round 1'").returncode == 0
    ledger = repo / "cla.io" / "retro" / "commit-provenance.jsonl"

    row = _ledger(repo)[0]
    row["sha"] = row["sha"][:4]
    ledger.write_text(json.dumps(row) + "\n", encoding="utf-8")

    assert _run(repo, "git commit -m 'fix: review round 1'").returncode == 0
    assert len(_ledger(repo)) == 1, "a shorter stored prefix is still the same commit"


def test_a_corrupt_last_row_does_not_suppress_the_write(tmp_path):
    """The dedupe fails OPEN: unreadable means "cannot tell", so the row lands.

    Failing closed here would mean one truncated line silently ends recording
    for that repo, which is the far worse defect.
    """
    repo = _repo(tmp_path)
    ledger = repo / "cla.io" / "retro" / "commit-provenance.jsonl"
    ledger.write_text("{not json at all\n", encoding="utf-8")

    _commit_with(repo, "fix: review round 1", None)
    assert _run(repo, "git commit -m 'fix: review round 1'").returncode == 0
    # Counted as raw lines: `_ledger` parses every line and would choke on the
    # corrupt one this test deliberately planted.
    lines = ledger.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2, "the corrupt line stays, and the real row lands after it"
    assert json.loads(lines[1])["subject"] == "fix: review round 1"


def test_it_writes_nothing_for_a_non_commit(tmp_path):
    repo = _repo(tmp_path)
    assert _run(repo, "git status").returncode == 0
    assert _ledger(repo) == []


def test_it_writes_nothing_when_the_retro_dir_does_not_exist(tmp_path):
    """A repo that never ran `cla-init` has not opted into per-repo state; the
    hook must not create the tree to satisfy itself."""
    repo = _repo(tmp_path)
    (repo / "cla.io" / "retro" / "commit-provenance.jsonl").unlink()
    (repo / "cla.io" / "retro").rmdir()
    assert _run(repo, "git commit -m 'fix: review round 1'").returncode == 0
    assert not (repo / "cla.io" / "retro").exists()


def test_the_ledger_is_off_until_its_file_exists(tmp_path):
    """Default OFF, per issue #219: the directory is not consent for THIS ledger.

    The directory is shared with `spec-to-pr-runs.jsonl` and `codify-runs.jsonl`,
    which are written once per skill run by the skill itself. This one is written
    by a hook on every commit and is the only one that can land mid-merge and
    abort a `git checkout`, so a repo that wanted either of the others used to
    get this one's cost along with them.
    """
    repo = _repo(tmp_path)
    (repo / "cla.io" / "retro" / "commit-provenance.jsonl").unlink()

    assert _run(repo, "git commit -m 'fix: review round 1'").returncode == 0

    assert not (repo / "cla.io" / "retro" / "commit-provenance.jsonl").exists(), \
        "the hook must never create the ledger it was not asked for"
    # The directory survives -- only this ledger is off, not the tree.
    assert (repo / "cla.io" / "retro").is_dir()


def test_touching_the_ledger_file_is_the_opt_in(tmp_path):
    """The other half of the switch, so neither direction passes vacuously.

    Without this, `test_the_ledger_is_off_until_its_file_exists` is satisfied by
    a hook that never writes at all.
    """
    repo = _repo(tmp_path)
    ledger = repo / "cla.io" / "retro" / "commit-provenance.jsonl"
    ledger.unlink()
    assert _run(repo, "git commit -m 'fix: review round 1'").returncode == 0
    assert _ledger(repo) == []

    ledger.touch()
    _git_out(repo, "commit", "-q", "--allow-empty", "-m", "fix: review round 2")
    assert _run(repo, "git commit -m 'fix: review round 2'").returncode == 0

    rows = _ledger(repo)
    assert len(rows) == 1, rows
    assert rows[0]["subject"] == "fix: review round 2"


def test_an_empty_ledger_file_takes_its_first_row(tmp_path):
    """A zero-byte file is the opt-in state, so the first append must work.

    `_already_recorded_fh` reads a tail that is empty here; reading that as
    "something is already recorded" would mean an opted-in repo never gets a
    single row.
    """
    repo = _repo(tmp_path)
    ledger = repo / "cla.io" / "retro" / "commit-provenance.jsonl"
    assert ledger.stat().st_size == 0
    assert _run(repo, "git commit -m 'fix: review round 1'").returncode == 0
    assert len(_ledger(repo)) == 1


def test_it_is_silent_and_exits_zero_outside_a_git_repo(tmp_path):
    """Best-effort: a telemetry hook must never disrupt a workflow."""
    retro = tmp_path / "cla.io" / "retro"
    retro.mkdir(parents=True)
    # Opted in, so the silence below is attributable to "not a git repo" rather
    # than to the ledger switch being off.
    (retro / "commit-provenance.jsonl").touch()
    r = _run(tmp_path, "git commit -m 'x'")
    assert r.returncode == 0
    assert _ledger(tmp_path) == []


def test_malformed_stdin_exits_zero(tmp_path):
    r = subprocess.run(
        [sys.executable, str(_HOOK)],
        input="not json",
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )
    assert r.returncode == 0


# ---------- the Measured-by column ----------
#
# The Ship and Revise commit steps require one `Measured-by:` trailer per
# measurement a change asserts, and nothing gates a single commit. Whether that
# rule is followed is therefore answerable only from this ledger, which makes
# these columns the evidence — so they are tested for the two ways a count goes
# wrong: reading nothing when trailers exist, and reporting a shortened list as
# though it were the whole one.


def _commit_with(repo: Path, subject: str, trailer_block: str | None) -> None:
    (repo / "f.txt").write_text(subject + "\n", encoding="utf-8")
    args = ["git", "commit", "-q", "-a", "-m", subject]
    if trailer_block is not None:
        args += ["-m", trailer_block]
    subprocess.run(args, cwd=repo, check=True, capture_output=True)


def test_trailers_are_recorded_with_an_exact_count(tmp_path):
    repo = _repo(tmp_path)
    _commit_with(
        repo,
        "fix: review round 2",
        "Measured-by: pytest plugin-tests -q — 1237 passed\n"
        "Measured-by: node --test x.mjs — 70 pass",
    )
    assert _run(repo, "git commit -m 'fix: review round 2'").returncode == 0
    row = _ledger(repo)[-1]
    assert row["measured_by_count"] == 2
    assert row["measured_by"] == [
        "pytest plugin-tests -q — 1237 passed",
        "node --test x.mjs — 70 pass",
    ]


def test_a_commit_asserting_nothing_records_an_empty_list_not_a_missing_key(tmp_path):
    """The rule says a change asserting no measurement writes no trailer, so
    zero is a real reading rather than an absence. A missing key would be
    indistinguishable from a hook that could not parse the commit."""
    repo = _repo(tmp_path)
    _commit_with(repo, "chore: no claims here", None)
    assert _run(repo, "git commit -m 'chore: no claims here'").returncode == 0
    row = _ledger(repo)[-1]
    assert row["measured_by_count"] == 0
    assert row["measured_by"] == []


def test_a_wrapped_trailer_is_one_value_not_two_fragments(tmp_path):
    """`unfold=true`. A long command wrapped across lines is still one claim;
    recorded as fragments it would inflate the count it exists to report."""
    repo = _repo(tmp_path)
    _commit_with(
        repo,
        "feat: wrapped",
        "Measured-by: git log -8 -p --format= --unified=0\n"
        "  | grep -cE '^[+]' — 7280 added lines",
    )
    assert _run(repo, "git commit -m 'feat: wrapped'").returncode == 0
    row = _ledger(repo)[-1]
    assert row["measured_by_count"] == 1
    assert "7280 added lines" in row["measured_by"][0]


def test_an_oversize_record_sheds_values_but_never_the_count(tmp_path):
    """The ceiling must cost detail, not the commit. Dropping the whole line
    would remove the commit from the denominator too — the number this hook was
    built to supply."""
    repo = _repo(tmp_path)
    trailers = "\n".join(
        f"Measured-by: {'c' * 300} — claim {i}" for i in range(12)
    )
    _commit_with(repo, "feat: many claims", trailers)
    assert _run(repo, "git commit -m 'feat: many claims'").returncode == 0
    rows = _ledger(repo)
    # One hook invocation, one line. The fixture's own commit predates the hook
    # and writes nothing, so a dropped line would leave the ledger empty.
    assert len(rows) == 1, "the line must still be written, not dropped"
    row = rows[-1]
    assert row["measured_by_count"] == 12, "the count is exact regardless of shedding"
    # `_MAX_TRAILERS` capped the list at 10 BEFORE the shedding loop was reached.
    # The literal, not `mod._MAX_TRAILERS`: asserting against the constant under
    # test means a cap change from 10 to 3 leaves this green with 3 values from a
    # 12-trailer fixture. The original `< 12` was worse still — satisfied by the
    # cap alone, so it held whether the loop ran or not, and it would also have
    # passed at 0, 5 or 11.
    assert len(row["measured_by"]) == 10, "the list is capped at _MAX_TRAILERS (10)"
    assert all(len(v) <= mod._MAX_TRAILER_CHARS for v in row["measured_by"])
    line_bytes = len(json.dumps(row, ensure_ascii=False).encode("utf-8")) + 1
    assert line_bytes <= mod._MAX_LINE_BYTES
    # This ASCII fixture stays under the ceiling — measured at 1801 bytes — so it
    # exercises the CAP and not the shedding loop. That is a property of this
    # fixture, NOT a claim that the loop is unreachable: an earlier version of
    # this file said so and was wrong.
    # `test_an_oversize_record_sheds_through_the_real_hook` below reaches the loop
    # with a non-ASCII subject.
    assert line_bytes < mod._MAX_LINE_BYTES, (
        "this fixture is meant to sit under the ceiling so it isolates the cap; "
        "if it ever crosses, it has stopped being the cap-only case and the "
        "shedding test below is no longer the only thing covering the loop"
    )


def test_an_oversize_record_sheds_through_the_real_hook(tmp_path):
    """The shedding loop, driven through the hook rather than reasoned about.

    This test replaces one asserting the loop was UNREACHABLE. That claim was
    wrong, and the way it was wrong is the point: it came from measuring one
    fixture at 1801 bytes against a 2048 ceiling and generalising, then looking
    only for what supported the conclusion (branch-name length limits) instead of
    what refutes it. Two reviewers ran the loop.

    THE LEVER IS A NON-ASCII SUBJECT, and it is a byte/character confusion.
    `subject[:120]` slices CHARACTERS; `json.dumps(..., ensure_ascii=False)`
    writes UTF-8 BYTES. A CJK subject is 3 bytes per character, so a 120-char
    subject contributes 360 bytes where the arithmetic assumed 120. Measured
    through the real hook: 1980 bytes, shed from 10 values to 9.

    Chosen over the other reachability routes deliberately. A long branch name
    also works, but its limit is a filesystem artefact — `MAX_PATH` on Windows,
    255 bytes per component on POSIX — so a branch-length fixture passes here and
    means something different in a consuming repo. This one is arithmetic, so it
    holds everywhere.

    Two dead ends, recorded so nobody repeats them. Monkeypatching
    `_MAX_LINE_BYTES` does nothing: the hook runs as a separate process and reads
    the shipped constant, so a patched ceiling returns an unpatched row. And
    `..._terminates_on_a_record_that_can_never_fit` below re-implements the loop
    in its own body rather than calling the hook, so it proves the algorithm
    terminates and nothing at all about this hook.
    """
    repo = _repo(tmp_path)
    # 120 CJK characters — exactly the subject cap in CHARACTERS, 360 in bytes.
    trailers = "\n".join(
        f"Measured-by: {'c' * 300} — claim {i}" for i in range(12)
    )
    _commit_with(repo, "改" * 120, trailers)
    assert _run(repo, "git commit -m 'x'").returncode == 0
    rows = _ledger(repo)
    assert len(rows) == 1, "the line must still be written, not dropped"
    row = rows[-1]

    assert len(row["measured_by"]) < mod._MAX_TRAILERS, (
        "the loop must have shed BEYOND the _MAX_TRAILERS cap — that is what "
        "distinguishes this test from the cap-only one above"
    )
    line_bytes = len(json.dumps(row, ensure_ascii=False).encode("utf-8")) + 1
    assert line_bytes <= mod._MAX_LINE_BYTES, "it must have shed until the record fit"
    # The invariant the loop exists to preserve, and the one the restored mutant
    # breaks: shedding costs DETAIL, never the adoption number. A row whose count
    # tracked its shortened list would understate every measurement in the retro
    # aggregate, silently, while still looking like a well-formed row.
    assert row["measured_by_count"] == 12, (
        "the count is exact AFTER real shedding, not merely after the cap"
    )


def test_the_shedding_loop_terminates_on_a_record_that_can_never_fit(monkeypatch):
    """A subject alone over the ceiling exhausts the list and must then return
    without writing, rather than looping. Reached by shrinking the ceiling,
    since no real subject is 2 KiB."""
    monkeypatch.setattr(mod, "_MAX_LINE_BYTES", 10)
    record = {"subject": "x" * 50, "measured_by_count": 3, "measured_by": ["a", "b", "c"]}
    while (
        len(json.dumps(record, ensure_ascii=False).encode("utf-8")) > mod._MAX_LINE_BYTES
        and record["measured_by"]
    ):
        record["measured_by"] = record["measured_by"][:-1]
    assert record["measured_by"] == []
    assert record["measured_by_count"] == 3


def test_measurements_still_count_when_attribution_follows_them(tmp_path):
    """THE defect this scan replaced git's trailer parser for.

    Git recognises only the LAST contiguous `Key: value` block as trailers. Every
    commit here ends with `Co-Authored-By` / `Claude-Session`, so the moment a
    blank line separates the measurements from those — the natural way to write a
    long message — git saw the attribution block and nothing else.

    Measured when found: 35 of 184 ledger rows undercounted their own commit, and
    the adoption rate the ledger reported was 0.38 where the messages gave 0.61.
    Every test above passes with the bug present, because none of them appended an
    attribution block.
    """
    repo = _repo(tmp_path)
    _commit_with(
        repo,
        "feat: real shape",
        "Measured-by: pytest -q — 1718 passed\n"
        "Measured-by: node --test x.mjs — 70 pass",
    )
    # A SECOND block, after a blank line — what git treats as the trailers.
    subprocess.run(
        ["git", "commit", "-q", "--amend", "-m", "feat: real shape",
         "-m", "Measured-by: pytest -q — 1718 passed\n"
               "Measured-by: node --test x.mjs — 70 pass",
         "-m", "Co-Authored-By: Someone <x@example.com>\n"
               "Claude-Session: https://example.com/s"],
        cwd=repo, check=True, capture_output=True)
    (repo / "f.txt").write_text("again\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", "feat: real shape 2",
         "-m", "Measured-by: pytest -q — 1718 passed\n"
               "Measured-by: node --test x.mjs — 70 pass",
         "-m", "Co-Authored-By: Someone <x@example.com>\n"
               "Claude-Session: https://example.com/s"],
        cwd=repo, check=True, capture_output=True)
    assert _run(repo, "git commit -m 'feat: real shape 2'").returncode == 0
    row = _ledger(repo)[-1]
    assert row["measured_by_count"] == 2, (
        "the measurements were separated from the attribution block by a blank "
        "line, which is what git's trailer parser could not see"
    )
    assert row["measured_by"] == [
        "pytest -q — 1718 passed",
        "node --test x.mjs — 70 pass",
    ]


def test_attribution_lines_are_never_counted_as_measurements(tmp_path):
    """Non-vacuity partner: scanning the whole message must not sweep up every
    `Key: value` line it finds. Only `Measured-by:` counts."""
    repo = _repo(tmp_path)
    _commit_with(repo, "chore: attribution only", None)
    subprocess.run(
        ["git", "commit", "-q", "--amend", "-m", "chore: attribution only",
         "-m", "Co-Authored-By: Someone <x@example.com>\n"
               "Claude-Session: https://example.com/s\n"
               "Signed-off-by: Someone <x@example.com>"],
        cwd=repo, check=True, capture_output=True)
    (repo / "f.txt").write_text("more\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", "chore: attribution only 2",
         "-m", "Co-Authored-By: Someone <x@example.com>\n"
               "Claude-Session: https://example.com/s"],
        cwd=repo, check=True, capture_output=True)
    assert _run(repo, "git commit -m 'chore: attribution only 2'").returncode == 0
    row = _ledger(repo)[-1]
    assert row["measured_by_count"] == 0
    assert row["measured_by"] == []


def test_a_wrapped_value_still_folds_when_attribution_follows(tmp_path):
    """The continuation rule has to survive the new scan, not just the old
    `unfold=true` — a wrapped command recorded as fragments inflates the very
    count this field exists to report."""
    repo = _repo(tmp_path)
    _commit_with(repo, "feat: wrapped again", None)
    (repo / "f.txt").write_text("w\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", "feat: wrapped again 2",
         "-m", "Measured-by: git log -8 -p --format= --unified=0\n"
               "  | grep -cE '^[+]' — 7280 added lines",
         "-m", "Co-Authored-By: Someone <x@example.com>"],
        cwd=repo, check=True, capture_output=True)
    assert _run(repo, "git commit -m 'feat: wrapped again 2'").returncode == 0
    row = _ledger(repo)[-1]
    assert row["measured_by_count"] == 1
    assert "7280 added lines" in row["measured_by"][0]


def test_an_indented_line_far_below_is_not_folded_into_a_measurement(tmp_path):
    """The continuation fold must require ADJACENCY, which it first shipped without.

    Without it `values[-1]` stayed the fold target for the rest of the message, so
    any indented line below — a code block, a quoted diff, an example — was welded
    onto the last measurement across blank lines and unrelated paragraphs.
    Measured on this repo when found: 5 of 56 commits carrying a trailer had a
    value corrupted this way, one by 1296 characters.
    """
    repo = _repo(tmp_path)
    _commit_with(repo, "docs: seed", None)
    (repo / "f.txt").write_text("body\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", "docs: with a code block",
         "-m", "Measured-by: pytest -q — 20 passed",
         "-m", "Some unrelated paragraph.",
         "-m", "    an indented code block\n    a second indented line",
         "-m", "Co-Authored-By: Someone <x@example.com>"],
        cwd=repo, check=True, capture_output=True)
    assert _run(repo, "git commit -m 'docs: with a code block'").returncode == 0
    row = _ledger(repo)[-1]
    assert row["measured_by_count"] == 1
    assert row["measured_by"] == ["pytest -q — 20 passed"], (
        "an indented line separated from the trailer by a blank line and a "
        "paragraph was folded into the measurement"
    )


def test_a_valueless_trailer_is_not_resurrected_by_a_later_indented_line(tmp_path):
    """`Measured-by:` with nothing after it asserts no measurement. Folding onto
    it rescued it from the empty-string filter and recorded a fabricated one,
    inflating the exact numerator `measurement_rate` is built on."""
    repo = _repo(tmp_path)
    _commit_with(repo, "docs: seed two", None)
    (repo / "f.txt").write_text("body2\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    # ONE `-m` for both lines. Separate `-m` blocks are joined by a BLANK line,
    # which ends the fold on its own and made an earlier version of this test
    # vacuous — it passed with the defect present. A mutation run caught that:
    # `folding = True` on the empty value survived, because the message shape
    # never reached the branch it breaks.
    subprocess.run(
        ["git", "commit", "-q", "-m", "docs: empty trailer",
         "-m", "Measured-by:\n    ls -la",
         "-m", "Co-Authored-By: Someone <x@example.com>"],
        cwd=repo, check=True, capture_output=True)
    assert _run(repo, "git commit -m 'docs: empty trailer'").returncode == 0
    row = _ledger(repo)[-1]
    assert row["measured_by_count"] == 0
    assert row["measured_by"] == []


# ---------- the dedupe read and the append share one handle (#219) ----------


def test_the_dedupe_reads_the_ledger_as_it_is_at_write_time(tmp_path):
    """The property the one-handle order buys, stated as behaviour.

    The check used to run before `_measured_by`, putting three git subprocess
    calls between "not yet recorded" and acting on it. A row appended by another
    process inside that window was invisible, and both rows landed.

    This pins the narrower claim the fix actually supports: a read through the
    handle the append will use sees whatever is on disk NOW, including a row
    written after the handle was opened. It does not claim the race is closed --
    nothing here takes a lock, and two processes can still both read a tail
    lacking the sha before either writes.
    """
    ledger = tmp_path / "commit-provenance.jsonl"
    ledger.write_text('{"sha": "aaaa111"}\n', encoding="utf-8")

    with ledger.open("a+b") as fh:
        assert not mod._already_recorded_fh(fh, "bbbb222")
        # Another process commits and records, after our handle was opened.
        with ledger.open("ab") as other:
            other.write(b'{"sha": "bbbb222"}\n')
        assert mod._already_recorded_fh(fh, "bbbb222"), \
            "the check must read current state, not a snapshot from open time"


def test_the_handle_form_and_the_path_form_agree(tmp_path):
    """Splitting the body must not let the two forms drift.

    `main()` uses the handle form; the unit tests and any standalone caller use
    the path form. A divergence would be silent -- the hook would dedupe on one
    rule while every test asserted the other.
    """
    ledger = tmp_path / "commit-provenance.jsonl"
    for content, sha, expected in [
        ("", "abc1234", False),                                  # empty: opted in, no rows yet
        ('{"sha": "abc1234"}\n', "abc1234", True),               # exact
        ('{"sha": "abc1234"}\n', "abc12345", True),              # stored is a prefix
        ('{"sha": "abc12345"}\n', "abc1234", True),              # sha is a prefix
        ('{"sha": "abc1234"}\n', "def5678", False),              # different commit
        ('not json\n', "abc1234", False),                        # corrupt last row
        ('{"sha": "abc1234"}\n{"sha": "def5678"}\n', "abc1234", False),  # not the LAST row
    ]:
        ledger.write_text(content, encoding="utf-8")
        via_path = mod._already_recorded(ledger, sha)
        with ledger.open("rb") as fh:
            via_handle = mod._already_recorded_fh(fh, sha)
        assert via_path == via_handle == expected, (content, sha, via_path, via_handle)


def test_an_unreadable_ledger_at_write_time_writes_nothing(tmp_path):
    """The handle form raises where the path form swallows, and that is the point.

    Inside `main()` the read shares the append's `try`, so a read failure takes
    the same exit as a write failure. Swallowing it there would read as "not
    recorded" and append anyway -- turning an unreadable ledger into a duplicate
    rather than into silence.
    """
    class _Boom:
        def seek(self, *a):
            raise OSError("unreadable")

    with pytest.raises(OSError):
        mod._already_recorded_fh(_Boom(), "abc1234")
