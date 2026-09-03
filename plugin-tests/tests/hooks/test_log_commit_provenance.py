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
    ],
)
def test_a_non_commit_is_not_recognised(command):
    """Over-recording corrupts the ratio this hook exists to report."""
    assert mod._is_commit_command(command) is False


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
        # part of a filename. This is the exclusion's own branch, which no
        # earlier case reached: the two before it exit on `--dry-run` first.
        "git status\ngit show HEAD -- cla.io/retro/commit-provenance.jsonl",
    ],
)
def test_splitting_does_not_admit_a_non_commit(command):
    """Splitting must not turn the exclusions into a way through.

    Each case fails a DIFFERENT test in the loop — leads-with-git, `--dry-run`,
    then the history read. Three cases exiting by the same branch would look
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
    (tmp_path / "cla.io" / "retro").mkdir(parents=True)
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
    (repo / "cla.io" / "retro").rmdir()
    assert _run(repo, "git commit -m 'fix: review round 1'").returncode == 0
    assert not (repo / "cla.io" / "retro").exists()


def test_it_is_silent_and_exits_zero_outside_a_git_repo(tmp_path):
    """Best-effort: a telemetry hook must never disrupt a workflow."""
    (tmp_path / "cla.io" / "retro").mkdir(parents=True)
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
    # Asserted against that constant rather than against 12: `< 12` was the
    # original, and it is satisfied by the cap alone, so it held whether the loop
    # ran or not.
    assert len(row["measured_by"]) == mod._MAX_TRAILERS, "the list is capped at _MAX_TRAILERS"
    assert all(len(v) <= mod._MAX_TRAILER_CHARS for v in row["measured_by"])
    line_bytes = len(json.dumps(row, ensure_ascii=False).encode("utf-8")) + 1
    assert line_bytes <= mod._MAX_LINE_BYTES
    # This fixture does NOT reach the shedding loop, and saying so is the point.
    # Measured: 1801 bytes against a 2048 ceiling. The loop is reachable in
    # production only in a narrow corner — every field at its cap plus a very
    # long branch name reaches 2197 — so a fixture built from realistic trailers
    # cannot get there. `..._sheds_when_the_line_would_not_fit` below is what
    # actually exercises it.
    assert line_bytes < mod._MAX_LINE_BYTES, (
        "this fixture is under the ceiling, so it exercises the CAP, not the "
        "shedding loop; if this ever fails, the two tests have merged and the "
        "one below is no longer the only thing covering the loop"
    )


def test_the_shedding_loop_is_unreachable_under_the_current_caps(tmp_path):
    """Records WHY no test drives the shedding loop through the real hook, so the
    next reader does not spend the round trip this one cost.

    The loop below `_line()` cannot execute in production as the constants stand.
    Every contributing field is capped — `subject[:120]`, `_MAX_TRAILERS` = 10
    values of `_MAX_TRAILER_CHARS` = 160 — and the only unbounded one is the
    branch name. Measured: a realistic record is 1801 bytes against a 2048
    ceiling, and reaching 2048 needs roughly 250 characters of branch, which git
    refuses to create here (single-segment past ~100 chars, and a 264-char
    multi-segment ref, both rejected).

    Two dead ends worth not repeating. Monkeypatching `_MAX_LINE_BYTES` does
    nothing: the hook runs as a separate process, so the subprocess reads the
    shipped constant and returns an unpatched 1801-byte row. And
    `..._terminates_on_a_record_that_can_never_fit` below re-implements the loop
    in its own body rather than calling the hook, so it proves the algorithm
    terminates and nothing about the hook.

    The loop is therefore defence against a future cap change rather than live
    code, which is a legitimate thing to keep — but it is NOT covered, and the
    batch entry that would have covered it was dropped as unkillable rather than
    left as a survivor nobody can act on. If the caps ever rise, delete this test
    and write the real one.
    """
    assert mod._MAX_TRAILERS * mod._MAX_TRAILER_CHARS + 120 < mod._MAX_LINE_BYTES, (
        "the caps no longer keep a record under the ceiling on their own, so the "
        "shedding loop may now be reachable — write the real test and delete this"
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
