"""Batch 4 — the sync engine's own failure modes.

Every case here was reported by a consuming repo after a real sync, and every
one shares a shape: the run damages or misreports itself while exiting 0. Two
of them stopped an actual sync; one can ship a corrupted asset.
"""

from __future__ import annotations

import importlib.util
import json
import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

_spec = importlib.util.spec_from_file_location("apply_mod", _SCRIPTS / "apply.py")
apply_mod = importlib.util.module_from_spec(_spec)
sys.modules["apply_mod"] = apply_mod
_spec.loader.exec_module(apply_mod)


# --------------------------------------------------------------------------- #
# AA-4(a) — the lockfile was the one CRLF file in the plugin
# --------------------------------------------------------------------------- #


def test_lockfile_is_written_with_lf_on_every_platform(tmp_path):
    """`os.fdopen(fd, "w")` without `newline=""` lets Python translate \\n to
    \\r\\n on Windows, so the same sync produced a different committed file per
    developer OS and a repo pinning `eol=lf` saw it re-dirtied on every apply."""
    apply_mod._update_lock(tmp_path, [("a/b.md", b"x")], "src", "abc123")
    raw = (tmp_path / apply_mod.LOCK_RELATIVE_PATH).read_bytes()
    assert b"\r\n" not in raw, "lockfile must be LF-only regardless of platform"
    assert b"\n" in raw


# --------------------------------------------------------------------------- #
# AA-4(b) — a corrupt-but-PRESENT lockfile silently discarded all provenance
# --------------------------------------------------------------------------- #


def _lock_path(repo: Path) -> Path:
    p = repo / apply_mod.LOCK_RELATIVE_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def test_an_absent_lockfile_is_silent(tmp_path, capsys):
    """Never synced: nothing to lose, so nothing to say. This is the ONLY case
    that should be quiet."""
    assert apply_mod._read_lock(tmp_path) == {}
    assert capsys.readouterr().err == ""


@pytest.mark.parametrize(
    "content, why",
    [
        ("{not json at all", "invalid JSON"),
        ("[1, 2, 3]", "top level is list"),
    ],
)
def test_a_corrupt_lockfile_announces_the_provenance_loss(tmp_path, capsys, content, why):
    """`_update_lock` read-merge-writes, so an empty read REPLACES the whole
    lockfile with this run's entries alone — silently downgrading every future
    `discover` to judgment-only for every asset this run did not touch."""
    _lock_path(tmp_path).write_text(content, encoding="utf-8")
    assert apply_mod._read_lock(tmp_path) == {}
    err = capsys.readouterr().err
    assert "DISCARDED" in err, f"{why}: must announce, not degrade silently"


def test_dropped_malformed_entries_are_counted(tmp_path, capsys):
    _lock_path(tmp_path).write_text(
        json.dumps({"good": {"x": 1}, "bad": "not-a-dict"}), encoding="utf-8"
    )
    assert set(apply_mod._read_lock(tmp_path)) == {"good"}
    assert "dropped 1 malformed" in capsys.readouterr().err


def test_a_valid_lockfile_is_read_silently(tmp_path, capsys):
    """Non-vacuity partner: the warnings above must not fire on the normal path."""
    _lock_path(tmp_path).write_text(json.dumps({"a": {"x": 1}}), encoding="utf-8")
    assert apply_mod._read_lock(tmp_path) == {"a": {"x": 1}}
    assert capsys.readouterr().err == ""


# --------------------------------------------------------------------------- #
# AA-4(c) — a truncated asset shipped anyway
# --------------------------------------------------------------------------- #


def test_a_failed_write_leaves_the_original_intact(tmp_path, monkeypatch):
    """`write_text` truncates then writes, so a failure in between left the file
    TRUNCATED. The run recorded a `failure` and kept it out of the commit
    message, PR body and lockfile — and then `git add -A` staged the whole tree
    and shipped it anyway, with every artifact saying it was not written."""
    dst = tmp_path / "a.md"
    dst.write_text("original content that must survive\n", encoding="utf-8")

    real_replace = apply_mod.os.replace

    def _boom(src, dest):
        raise OSError("disk full")

    monkeypatch.setattr(apply_mod.os, "replace", _boom)
    with pytest.raises(OSError):
        apply_mod._write_file(tmp_path, "a.md", "new content")
    monkeypatch.setattr(apply_mod.os, "replace", real_replace)

    assert dst.read_text(encoding="utf-8") == "original content that must survive\n"
    leftovers = [p.name for p in tmp_path.iterdir() if p.name.startswith(".a.md.")]
    assert leftovers == [], f"temp file left behind: {leftovers}"


def test_a_successful_write_still_lands_with_lf(tmp_path):
    apply_mod._write_file(tmp_path, "x/y.md", "one\ntwo\n")
    assert (tmp_path / "x" / "y.md").read_bytes() == b"one\ntwo\n"


# --------------------------------------------------------------------------- #
# MD-11 — _run had no exception handling at all
# --------------------------------------------------------------------------- #


def test_run_returns_a_failure_result_instead_of_raising(tmp_path, monkeypatch):
    """A `TimeoutExpired` on `git push` propagated as a traceback with files
    already written and a commit already made: rollback never ran and no
    structured summary was printed. Every caller already checks `returncode`."""
    def _raise(*a, **k):
        raise subprocess.TimeoutExpired("git", 120)

    monkeypatch.setattr(apply_mod.subprocess, "run", _raise)
    result = apply_mod._run(["git", "push"], cwd=tmp_path)
    assert result.returncode == 1
    assert "TimeoutExpired" in result.stderr


def test_run_reports_a_missing_binary_rather_than_raising(tmp_path, monkeypatch):
    def _raise(*a, **k):
        raise FileNotFoundError("no gh")

    monkeypatch.setattr(apply_mod.subprocess, "run", _raise)
    result = apply_mod._run(["gh", "pr", "create"], cwd=tmp_path)
    assert result.returncode == 1
    assert "FileNotFoundError" in result.stderr


# --------------------------------------------------------------------------- #
# AA-4(d) — the PR body exceeded GitHub's limit AFTER the push
# --------------------------------------------------------------------------- #


def test_an_oversize_pr_body_is_trimmed_and_says_what_it_dropped():
    """A 154-asset sync produced a body past 65536 chars and `gh pr create`
    failed after the branch was committed and pushed. A silently truncated body
    would be worse than a long one — the reader could not tell 'no summary was
    written' from 'the summary did not fit'."""
    adaptations = [
        {"asset_path": f"a/file-{i}.md", "change_summary": "x" * 900}
        for i in range(200)
    ]
    body = apply_mod._render_pr_body(adaptations)
    assert len(body) <= apply_mod._PR_BODY_LIMIT
    assert "omitted" in body, "must name what was dropped"


def test_a_small_pr_body_is_left_completely_alone():
    """Non-vacuity partner: trimming must not fire on an ordinary sync."""
    adaptations = [{"asset_path": "a.md", "change_summary": "kept local heading"}]
    body = apply_mod._render_pr_body(adaptations)
    assert "omitted" not in body
    assert "kept local heading" in body


def test_a_missing_asset_path_does_not_crash_the_renderer():
    """`a["asset_path"]` was a hard subscript on LLM-authored JSON, beside a
    defensive `.get` for the summary — inconsistent, in the one input this
    module cannot trust."""
    body = apply_mod._render_pr_body([{"change_summary": "no path key"}])
    assert "(unknown)" in body


# --------------------------------------------------------------------------- #
# AA-4(e) — temp/sync-<run-id>/ blocked every subsequent --mode pr run
# --------------------------------------------------------------------------- #


def test_cleanup_removes_the_run_files_and_the_dir(tmp_path):
    """`apply_pr` opens with a whole-tree clean check, so the SECOND pr-mode run
    in any repo refused to start and blamed the user's working tree. The
    documented ignore pattern is `temp/sync-state/`, a different path."""
    d = tmp_path / "temp" / "sync-123"
    d.mkdir(parents=True)
    msg, body = d / "commit-msg.txt", d / "pr-body.md"
    msg.write_text("m", encoding="utf-8")
    body.write_text("b", encoding="utf-8")
    apply_mod._cleanup_temp_dir(d, msg, body)
    assert not d.exists()


def test_cleanup_never_removes_a_directory_it_did_not_empty(tmp_path):
    """Deliberately `rmdir`, never `shutil.rmtree`: `temp_dir` is
    caller-supplied, and a consuming repo's first draft of this used rmtree and
    deleted an entire synthetic repo in test, because a caller had passed the
    enclosing directory. `rmdir` fails harmlessly on anything it should not
    remove."""
    d = tmp_path / "temp" / "sync-123"
    d.mkdir(parents=True)
    msg = d / "commit-msg.txt"
    msg.write_text("m", encoding="utf-8")
    someone_elses = d / "important.txt"
    someone_elses.write_text("do not delete", encoding="utf-8")

    apply_mod._cleanup_temp_dir(d, msg)

    assert d.exists(), "must not remove a non-empty directory"
    assert someone_elses.read_text(encoding="utf-8") == "do not delete"


# --------------------------------------------------------------------------- #
# AA-5 — orchestrate.py under-reported what a run did
# --------------------------------------------------------------------------- #

_ospec = importlib.util.spec_from_file_location("orch_mod", _SCRIPTS / "orchestrate.py")
orch_mod = importlib.util.module_from_spec(_ospec)
sys.modules["orch_mod"] = orch_mod
_ospec.loader.exec_module(orch_mod)


class _Outcome:
    def __init__(self, path, status, reason=None):
        self.asset_path, self.status, self.reason = path, status, reason


class _PR:
    branch, pr_url, reason = "sync/x", "https://example.invalid/pr/1", None


def test_a_discovered_but_unadapted_asset_is_reported_and_fails_the_run(capsys):
    """The summary's denominator was the ADAPTATION count -- self-referential --
    so a file dropped from adaptations.json was never written, never surfaced,
    and the run reported 'wrote N of N' and exited 0. A live risk precisely
    because Phase 2 is done by an LLM: dropping one file from a 150-entry list
    is the most likely mistake in the whole flow."""
    rc = orch_mod._print_worktree_summary(
        [_Outcome("a.md", "wrote")], not_adapted=["b.md", "c.md"]
    )
    out = capsys.readouterr().out
    assert "NOT ADAPTED (2)" in out
    assert "b.md" in out and "c.md" in out
    assert rc == 1, "a dropped asset must fail the run even when other files wrote"


def test_a_complete_run_reports_nothing_extra_and_exits_zero(capsys):
    """Non-vacuity partner: the report above must not fire on a normal run."""
    rc = orch_mod._print_worktree_summary([_Outcome("a.md", "wrote")], not_adapted=[])
    assert "NOT ADAPTED" not in capsys.readouterr().out
    assert rc == 0


def test_the_pr_summary_shows_refused_binaries_and_a_denominator(capsys):
    """`skipped_binary` had no bucket here while `known` DID list it, so a
    refused binary fell out of both and vanished from the PR report entirely --
    and the header carried no denominator, so the count could not reveal it."""
    orch_mod._print_pr_summary(
        [_Outcome("a.md", "wrote"), _Outcome("logo.png", "skipped_binary", "binary asset")],
        _PR(),
        not_adapted=[],
    )
    out = capsys.readouterr().out
    assert "of 2 file(s)" in out, "PR header needs a denominator"
    assert "logo.png" in out, "a refused binary must not vanish from the PR report"


def test_apply_pr_actually_calls_the_cleanup(monkeypatch, tmp_path):
    """Testing `_cleanup_temp_dir` in isolation left the CALL untested: deleting
    it from `apply_pr` passed the whole suite. A helper nobody invokes is the
    same shape as the defect it was written to fix."""
    import inspect
    src = inspect.getsource(apply_mod.apply_pr)
    assert "_cleanup_temp_dir(" in src, (
        "apply_pr must call _cleanup_temp_dir, or temp/sync-<run-id>/ survives "
        "and the next --mode pr run refuses to start on a dirty tree"
    )
    # And it must run on the SUCCESS path, after the PR is created -- cleaning up
    # on failure would delete the body file a human needs to open the PR by hand.
    after_create = src.split("gh", 1)[-1]
    assert "_cleanup_temp_dir(" in after_create


# --------------------------------------------------------------------------- #
# Review findings on THIS branch — every one of these was an untested fix, a
# vacuous assertion, or a defect the fixes introduced.
# --------------------------------------------------------------------------- #


def test_an_atomic_write_preserves_the_destinations_mode(tmp_path):
    """`os.replace` is rename(2): the destination inode is REPLACED by the temp
    one, which `mkstemp` creates at 0600 — where `write_text` wrote THROUGH the
    existing inode and kept its mode. Without preservation an atomic write
    strips the executable bit from `cla`/`claw`, which are tracked 100755 and
    are in SCAN_FILES: a sync touching them ships launchers that do not run.

    Asserted on the raw mode rather than skipped on Windows, so the intent is
    pinned everywhere; the meaningful comparison only happens where POSIX bits
    exist. Its platform-neutral partner below is what actually holds the
    mutation on this repo's own dev machine."""
    dst = tmp_path / "launcher"
    dst.write_text("#!/usr/bin/env bash\n", encoding="utf-8")
    os.chmod(dst, 0o755)
    before = stat.S_IMODE(dst.stat().st_mode)

    apply_mod._write_file(tmp_path, "launcher", "#!/usr/bin/env bash\necho hi\n")

    after = stat.S_IMODE(dst.stat().st_mode)
    assert after == before, f"mode changed {before:04o} -> {after:04o}"


def test_the_atomic_write_chmods_the_temp_file_to_the_destinations_mode(tmp_path, monkeypatch):
    """The same guarantee, asserted where POSIX bits do not exist.

    Measured on Windows: `chmod 0o755` -> reads back 0o666, `mkstemp` default ->
    0o666, after `os.replace` -> 0o666. So `before == after` holds regardless of
    whether the preservation code exists at all, and the test above passes for
    the wrong reason — deleting the capture-and-chmod leaves it green. That is
    the whole mode-preservation guard for `cla`/`claw`'s executable bit running
    with zero regression coverage on the platform this repo is developed on.

    Recording the `os.chmod` call instead needs no POSIX bits, so it kills the
    mutation on every platform.
    """
    dst = tmp_path / "launcher"
    dst.write_text("#!/usr/bin/env bash\n", encoding="utf-8")
    os.chmod(dst, 0o755)
    expected = stat.S_IMODE(dst.stat().st_mode)

    calls: list[int] = []
    real_chmod = apply_mod.os.chmod

    def _recording_chmod(path, mode, *a, **kw):
        calls.append(mode)
        return real_chmod(path, mode, *a, **kw)

    monkeypatch.setattr(apply_mod.os, "chmod", _recording_chmod)
    apply_mod._write_file(tmp_path, "launcher", "#!/usr/bin/env bash\necho hi\n")

    assert expected in calls, (
        f"_write_file must chmod the temp file to the destination's mode "
        f"({expected:04o}); recorded chmod calls: {[f'{m:04o}' for m in calls]}"
    )


def test_a_brand_new_file_still_writes_without_a_mode_to_preserve(tmp_path):
    """Non-vacuity partner: the mode capture must not break the `new` case,
    where there is no destination to stat."""
    apply_mod._write_file(tmp_path, "sub/brand-new.md", "hello\n")
    assert (tmp_path / "sub" / "brand-new.md").read_text(encoding="utf-8") == "hello\n"


def test_a_stale_run_id_is_refused_and_a_missing_one_too(tmp_path, capsys):
    """Untested before: the mutation `if False:` survived the whole file. A
    missing top-level key is the same class of Phase-2 slip as a dropped entry,
    so absent is refused too rather than falsy-gated through."""
    for file_run_id in ("20990101-000000", None):
        divergences = {"run_id": "R", "source": {"name": "s", "commit": None},
                       "local": {"path": str(tmp_path)}, "files": []}
        adaptations = {"adaptations": [{"asset_path": "a.md", "adapted_content": "x"}]}
        if file_run_id:
            adaptations["run_id"] = file_run_id
        state = tmp_path / "temp" / "sync-state" / "R"
        state.mkdir(parents=True, exist_ok=True)
        (state / "divergences.json").write_text(json.dumps(divergences), encoding="utf-8")
        (state / "adaptations.json").write_text(json.dumps(adaptations), encoding="utf-8")
        rc = orch_mod.cmd_apply("R", "worktree", str(tmp_path))
        assert rc == 2, f"run_id={file_run_id!r} must be refused with exit 2"


def test_a_keep_local_entry_accounts_for_a_file_without_rewriting_it(tmp_path):
    """`phases.md` tells Phase 2 to KEEP a `local-advanced` file — which an LLM
    satisfies by omitting the entry, and the completeness check then failed the
    run. An explicit marker accounts for the file without touching it."""
    dst = tmp_path / "kept.md"
    dst.write_text("local content\n", encoding="utf-8")
    outcomes = apply_mod.apply_worktree(
        tmp_path, [{"asset_path": "kept.md", "keep_local": True}], "src", None
    )
    assert [o.status for o in outcomes] == ["skipped_kept_local"]
    assert dst.read_text(encoding="utf-8") == "local content\n", "must not be rewritten"


def _lock_of(repo):
    return json.loads(
        (repo / ".claude" / "plugins" / "cla" / ".cla-sync-lock.json").read_text(encoding="utf-8")
    )


def test_keep_local_persists_the_decision_and_the_source_it_was_made_against(tmp_path):
    """A keep-local decision used to be recorded NOWHERE.

    `apply` skipped the file and left its lock entry alone, reasoning that local
    had not changed so the ancestor was still right. True of the ancestor, false
    of everything else: with no `keep_local` marker and no advance of
    `source_sha256`, the next run re-labels the file and asks again — and the
    reasoning that produced the decision died with the session.
    """
    dst = tmp_path / "kept.md"
    dst.write_text("local content\n", encoding="utf-8")
    outcomes = apply_mod.apply_worktree(
        tmp_path, [{"asset_path": "kept.md", "keep_local": True}], "src", None,
        source_shas={"kept.md": "rawsha"},
    )
    assert [o.status for o in outcomes] == ["skipped_kept_local"]

    entry = _lock_of(tmp_path)["kept.md"]
    assert entry["keep_local"] is True
    assert entry["source_sha256"] == "rawsha", "the source it was decided against must advance"
    assert entry["last_synced_sha256"] == apply_mod._hash_bytes(b"local content\n")


def test_keep_local_alone_still_writes_the_lockfile(tmp_path):
    """`_update_lock`'s early-out was `if not written: return`.

    A run whose entries are ALL keep-local writes no files, so it returned
    before recording anything — the same silent loss this change exists to stop,
    reintroduced one level up. Easy to reintroduce, so pinned separately.
    """
    (tmp_path / "kept.md").write_text("local\n", encoding="utf-8")
    apply_mod.apply_worktree(
        tmp_path, [{"asset_path": "kept.md", "keep_local": True}], "src", None
    )
    assert "kept.md" in _lock_of(tmp_path)


def test_a_later_write_clears_the_keep_local_flag(tmp_path):
    """Otherwise a file kept once is marked kept forever, and a future refactor
    that merges into the existing entry rather than replacing it would strand
    the flag with nothing to signal it had gone stale.

    Driven through `_update_lock` rather than two `apply_worktree` calls: the
    write path runs a clean-tree check that needs a real git repo, and a first
    draft using a bare tmp_path had its second call fail with "not a git
    repository" — so the entry was never rewritten and the test passed its
    setup while proving nothing about clearing. The unit under test here is the
    lock write, so that is what to call.
    """
    (tmp_path / "f.md").write_text("local\n", encoding="utf-8")
    apply_mod._update_lock(tmp_path, [], "src", None, kept_local=[("f.md", "sha-local")])
    assert _lock_of(tmp_path)["f.md"]["keep_local"] is True

    apply_mod._update_lock(tmp_path, [("f.md", b"adopted\n")], "src", None)
    entry = _lock_of(tmp_path)["f.md"]
    assert "keep_local" not in entry
    assert entry["last_synced_sha256"] == apply_mod._hash_bytes(b"adopted\n")


@pytest.mark.parametrize("printer", ["worktree", "pr"])
def test_a_kept_local_file_appears_in_the_summary(capsys, printer):
    """`skipped_kept_local` was listed in `known` — so never flagged as an
    unrecognized status — but had no print bucket, so it appeared NOWHERE in
    either summary. That is the third instance of this exact gap in this file
    (the comments beside `known` already record two), and it matters most here:
    a keep-local decision the operator never sees is one nobody can challenge.
    """
    outcomes = [_Outcome("a.md", "wrote"), _Outcome("kept.md", "skipped_kept_local")]
    if printer == "worktree":
        orch_mod._print_worktree_summary(outcomes, not_adapted=[])
    else:
        orch_mod._print_pr_summary(outcomes, _PR(), not_adapted=[])
    out = capsys.readouterr().out
    assert "kept.md" in out, f"a kept-local file must be visible in the {printer} summary"
    assert "Kept local" in out


def test_keep_local_seeds_a_complete_entry_when_none_existed(tmp_path):
    """`_detect_deletions` reads `last_synced_sha256` off EVERY entry, so a
    partial entry written here would surface as a malformed deletion record
    later. The ancestor is re-hashed from disk rather than left absent."""
    (tmp_path / "f.md").write_text("local\n", encoding="utf-8")
    apply_mod.apply_worktree(tmp_path, [{"asset_path": "f.md", "keep_local": True}], "src", None)
    entry = _lock_of(tmp_path)["f.md"]
    assert entry["last_synced_sha256"] and entry["source"] == "src"


def test_the_pr_summary_also_fails_on_not_adapted(capsys):
    """It printed the block and then returned 0, while worktree mode returned 1.
    If anything it matters MORE here: the incomplete set is already pushed."""
    rc = orch_mod._print_pr_summary([_Outcome("a.md", "wrote")], _PR(), not_adapted=["b.md"])
    assert "NOT ADAPTED" in capsys.readouterr().out
    assert rc == 1


def test_a_failed_rollback_is_announced(tmp_path, monkeypatch, capsys):
    """Once `_run` stopped raising, the old `except` arm became unreachable and
    this failure went completely silent — while orchestrate still printed
    "(rolled back to default branch where possible)"."""
    monkeypatch.setattr(apply_mod, "_run",
                        lambda *a, **k: subprocess.CompletedProcess([], 1, "", "detached HEAD"))
    apply_mod._rollback_branch(tmp_path, "main")
    err = capsys.readouterr().err
    assert "FAILED" in err and "STILL on the sync branch" in err


def test_a_single_oversized_asset_is_still_bounded():
    """The trimming loop never ran when `keep == 1`, and every path measured a
    different string than it returned. Verified before the fix: one asset with an
    oversized summary produced a 71123-char body — still past the limit, so
    `gh pr create` still failed after the push."""
    body = apply_mod._render_pr_body(
        [{"asset_path": "a.md", "change_summary": "x" * 200_000}]
    )
    assert len(body) <= apply_mod._PR_BODY_LIMIT
