"""Apply phase: write adapted files into the local repo.

Two modes:
- `worktree` (default): write adapted files directly into the local working
  tree, per-file skipping any file with uncommitted local edits.
- `pr`: require clean tree, create a sync branch, write files, commit, push,
  and open a PR via `gh`. Rolls back to the default branch if the flow fails
  after the branch was created.

Per-file isolation: a failure on one asset never halts the run.

Since `cla-sync-provenance`, both apply functions also write/update the per-repo
sync-provenance lockfile (`.claude/plugins/cla/.cla-sync-lock.json`) inside their
own write path — this is the only place that has the exact adapted bytes just
written to local, and (for `apply_pr`) the only place that can get the lockfile
staged/committed/pushed in the same PR (Decision B). Only `wrote` outcomes get a
lock entry; the lock write is read-merge-write and best-effort — a lock-write
failure is reported to stderr but never fails the run, commit, or PR.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import os
import stat
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


PR_TEMPLATE_PATH = Path(__file__).resolve().parent.parent / "references" / "pr_template.md"
DEFAULT_TIMEOUT_SECONDS = 120
LOCK_RELATIVE_PATH = ".claude/plugins/cla/.cla-sync-lock.json"


class GitUnavailableError(Exception):
    """Raised when `git status` itself fails — never silently overwrite."""


@dataclass
class ApplyOutcome:
    asset_path: str
    status: str  # "wrote" | "skipped_dirty_worktree" | "skipped_binary" | "skipped_malformed" | "skipped_kept_local" | "failure"
    reason: Optional[str]


@dataclass
class PRResult:
    branch: Optional[str]
    pr_url: Optional[str]
    reason: Optional[str]


def _run(cmd: list[str], cwd: Path, timeout: int = DEFAULT_TIMEOUT_SECONDS) -> subprocess.CompletedProcess:
    """Run `cmd`, returning a CompletedProcess even when it could not start.

    Every caller already checks `returncode`, so a synthetic failure result is
    the shape they all handle. Letting the exception escape instead meant a
    `TimeoutExpired` on `git push` propagated as a traceback with files already
    written and a commit already made: rollback never ran, no structured summary
    was printed, and the caller could not tell what state the repo was left in.
    """
    try:
        return subprocess.run(
            cmd, cwd=str(cwd), capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return subprocess.CompletedProcess(cmd, 1, "", f"{type(exc).__name__}: {exc}")


def _is_clean_tree(repo: Path) -> tuple[bool, str]:
    result = _run(["git", "status", "--porcelain"], cwd=repo)
    if result.returncode != 0:
        return False, f"git status failed: {result.stderr.strip()}"
    return result.stdout.strip() == "", result.stdout


def _file_has_local_edits(repo: Path, asset_path: str) -> bool:
    """True iff the asset has un-committed changes; raises if git itself fails."""
    try:
        result = _run(["git", "status", "--porcelain", "--", asset_path], cwd=repo)
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        raise GitUnavailableError(f"git unavailable: {exc}") from exc
    if result.returncode != 0:
        raise GitUnavailableError(
            f"git status failed (rc={result.returncode}): {result.stderr.strip()}"
        )
    return bool(result.stdout.strip())


def assert_target_is_a_repo_not_an_installed_plugin(local_repo: Path) -> None:
    """Refuse to sync into a read-only marketplace install.

    This tool writes the plugin tree — assets, and the lockfile at
    `LOCK_RELATIVE_PATH`. That is correct for a repo that VENDORS the plugin,
    which is the only arrangement that existed when it was written. It is wrong
    for a repo that INSTALLED the plugin from a marketplace: the tree is then a
    read-only, version-keyed cache, and a write either fails or lands somewhere
    the next `/plugin update` discards.

    The test is a property of the TARGET, not of this script: does the repo
    declare a marketplace install of `cla` in its settings? "Is the plugin
    directory inside the repo?" is the wrong question and was tried first — it
    conflates where *this script* happens to live with what the destination
    wants, so it refused every synthetic test fixture and, worse, refused to
    onboard a fresh repo that has no plugin tree yet, which is precisely a case
    update-cla exists to serve.

    Raises `SystemExit` with the remedy rather than returning a status: there is
    no partial-success reading of "the destination must not be written".
    """
    for name in ("settings.json", "settings.local.json"):
        path = local_repo / ".claude" / name
        try:
            settings = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue  # absent or unreadable: not evidence of an install
        enabled = settings.get("enabledPlugins")
        if not isinstance(enabled, dict):
            continue
        installed = [k for k in enabled if k.split("@")[0] == "cla"]
        if installed:
            raise SystemExit(
                f"error: {local_repo} installs this plugin from a marketplace "
                f"({', '.join(installed)}, per .claude/{name}).\n"
                "Its plugin tree is a read-only, version-keyed cache, so syncing "
                "into it would either fail or be discarded by the next update.\n"
                "update-cla is the pre-marketplace distribution path. Take a new "
                "release with `claude plugin update`, and send fixes back "
                "upstream with /cla:report-upstream."
            )


def _write_file(local_repo: Path, asset_path: str, content: str) -> None:
    """Write an adapted asset atomically.

    `write_text` truncates and then writes, so a failure in between leaves the
    asset TRUNCATED on disk. The run records a `failure` and keeps that file out
    of the commit message, the PR body and the lockfile -- and then `git add -A`
    stages the whole tree and ships the truncated file anyway, with every
    artifact describing the PR saying it was not written.

    `_write_lock` one function below already used mkstemp + os.replace; this is
    the same pattern, so the two agree.
    """
    dst = local_repo / asset_path
    dst.parent.mkdir(parents=True, exist_ok=True)

    # Capture the destination's mode BEFORE replacing it. `os.replace` is
    # rename(2): the destination inode is replaced by the temp one, which
    # `tempfile.mkstemp` creates at 0600 — where the old `write_text` wrote
    # THROUGH the existing inode and kept its mode. Without this, an atomic
    # write silently strips the executable bit from `cla` and `claw`, which are
    # tracked 100755 and are in `SCAN_FILES`: a sync that touched them would
    # produce `mode change 100755 => 100644`, `git add -A` would stage it, and
    # the PR would ship launchers that no longer execute.
    #
    # Invisible on Windows, which has no POSIX mode bits — `mkstemp` reports
    # 0666 there and a test asserting preservation passes for the wrong reason.
    # Exactly the platform-divergence CLAUDE.md warns about.
    try:
        existing_mode: int | None = stat.S_IMODE(dst.stat().st_mode)
    except OSError:
        existing_mode = None

    fd, tmp_name = tempfile.mkstemp(dir=str(dst.parent), prefix=f".{dst.name}.", suffix=".tmp")
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(content)
        if existing_mode is not None:
            try:
                os.chmod(tmp_path, existing_mode)
            except OSError:
                pass  # best-effort: a filesystem without mode support is fine
        os.replace(tmp_path, dst)
    except BaseException:
        tmp_path.unlink(missing_ok=True)
        raise


_BINARY_PLACEHOLDER_PREFIX = "<binary file,"


def _looks_like_binary_placeholder(content: str) -> bool:
    return content.startswith(_BINARY_PLACEHOLDER_PREFIX) and content.rstrip().endswith("bytes>")


def _normalize_line_endings(content: str) -> str:
    """Normalize CRLF/CR to LF before anything else touches `adapted_content`.

    `_write_file` already writes with `newline="\\n"`, so any corruption in a
    file that reaches disk with doubled blank lines happened UPSTREAM of the
    write — between the adapting agent's output and this function. A prior
    sync wrote 19 of 37 files with every `\\r\\n` silently turned into `\\n\\n`
    (a blank line inserted after every line); byte counts stayed identical, so
    nothing caught it — not the hook suite, not the guards, not the apply
    summary. Root cause was never conclusively isolated to one line, so the
    fix is defensive here rather than a point fix at an unproven origin."""
    return content.replace("\r\n", "\n").replace("\r", "\n")


# A file whose newline count is roughly 2x its non-empty line count is never a
# legitimate adaptation — it is the fingerprint of the doubled-newline
# corruption above (every real line gained a spurious blank line after it, so
# total line breaks roughly doubled while real content lines did not).
#
# The math, precisely (this matters — an earlier draft of this constant got
# it backwards): a file with N non-empty lines and ZERO pre-existing blank
# lines lands at EXACTLY ratio 2.0 once corrupted (every one of its N
# newlines becomes two); any pre-existing blank-line formatting only pushes
# the corrupted ratio HIGHER, never lower. So 2.0 is corruption's FLOOR, not
# its ceiling — a threshold set BELOW 2.0 (as a prior draft's 1.8 was) is
# stricter than the corruption signature itself and catches ordinary prose,
# not just corruption. Confirmed empirically against every file in this
# plugin's `skills/`/`agents/`/`hooks/`/`output-styles/` tree with at least
# `_MALFORMED_MIN_NON_EMPTY_LINES` non-empty lines: the most blank-line-heavy
# genuine file sits at ratio **1.6098** (`multi-spec/references/review-gate.md`,
# recomputed over the synced-core tree) — see
# `test_malformed_ratio_never_flags_real_repo_content`, which pins the whole tree
# at once so a future doc in this style can't silently regress this guard.
#
# This comment previously stated 1.955 for this population, and 1.667 a few lines
# below — two different maxima for the same set, both wrong. Worse, 1.955 is ABOVE
# the 1.85 threshold, so a real file sitting there would have been REJECTED,
# contradicting the very test named here. The 1.955 figure is real but belongs to
# `design-tradeoffs.md`, which has 22 non-empty lines and is EXCLUDED by the
# 30-line minimum; that test's own comment states this correctly.
#
# One shape genuinely can't be perfectly separated from corruption by ratio
# alone at ANY length: prose written as one paragraph per line with a blank
# line between every single one asymptotically APPROACHES ratio 2.0 as it
# grows (`(2N-1)/N`, e.g. 1.955 at N=22, 1.99 at N=100) — the same shape a
# corrupted file has. This repo's OWN `design-tradeoffs.md` is written this
# way. The mitigation isn't a perfect discriminator (none exists purely from
# the ratio); it's staying below what real content in this repo's synced
# core actually reaches at a checkable length — see
# `test_malformed_ratio_never_flags_real_repo_content`, which scans every
# real file rather than relying on a hand-built approximation. Empirically,
# every real file with `_MALFORMED_MIN_NON_EMPTY_LINES`-or-more non-empty
# lines in this repo tops out at ratio 1.6098 (the extreme "blank between
# every line" style only appears in a handful of SHORT reference docs,
# already excluded by the minimum). A corrupted file's worst realistic case
# — no pre-existing blank lines AND no trailing newline on its last line —
# still lands at `2(N-1)/N`, ≈1.933 at N=30, comfortably above both knobs.
_MALFORMED_NEWLINE_RATIO = 1.85
_MALFORMED_MIN_NON_EMPTY_LINES = 30


def _looks_malformed_by_doubled_newlines(content: str) -> bool:
    """True iff `content`'s structure matches the doubled-newline corruption
    fingerprint described above, on an ALREADY newline-normalized string (so a
    legitimate CRLF file is never mistaken for this)."""
    non_empty = sum(1 for line in content.splitlines() if line.strip())
    if non_empty < _MALFORMED_MIN_NON_EMPTY_LINES:
        return False
    return content.count("\n") >= non_empty * _MALFORMED_NEWLINE_RATIO


def _read_lock(local_repo: Path) -> dict:
    """Read the sync lockfile; missing/unreadable/corrupt (bad JSON, non-dict top
    level) -> empty map. Also sanitizes at the entry level: a nested value that
    isn't itself a dict is dropped, so `_update_lock`'s read-merge-write never
    chokes on a corrupt per-asset entry."""
    lock_path = local_repo / LOCK_RELATIVE_PATH

    def _discarding(why: str) -> dict:
        """Announce, then degrade. ABSENT is the only legitimately silent case.

        `_update_lock` read-merge-writes, so an empty read REPLACES the whole
        lockfile with just this run's entries -- silently downgrading every
        future `discover` from a real 3-way reconcile to judgment-only, for
        every asset this run did not touch. That is a large, invisible loss of
        provenance from a file that is present but malformed, which is a
        different situation from one that was never written.
        """
        print(
            f"apply: {lock_path} is unusable ({why}) — prior provenance will be "
            "DISCARDED, and future syncs lose their 3-way ancestor for every "
            "asset not written by this run",
            file=sys.stderr,
        )
        return {}

    if not lock_path.exists():
        return {}  # never synced: nothing to lose, nothing to say
    try:
        raw = lock_path.read_text(encoding="utf-8")
    except OSError as exc:
        return _discarding(f"unreadable: {exc}")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        return _discarding(f"invalid JSON: {exc}")
    if not isinstance(data, dict):
        return _discarding(f"top level is {type(data).__name__}, not an object")
    kept = {k: v for k, v in data.items() if isinstance(v, dict)}
    if len(kept) != len(data):
        print(
            f"apply: {lock_path} — dropped {len(data) - len(kept)} malformed "
            "entr(ies); those assets lose their 3-way ancestor",
            file=sys.stderr,
        )
    return kept


def _write_lock(local_repo: Path, lock: dict) -> None:
    """Write the lockfile atomically: serialize to a temp file in the SAME directory
    (so the later `os.replace` is same-filesystem and therefore atomic), then
    `os.replace` it over the real path. A `write_text`-style truncate-then-write would
    leave a destroyed/half-written lockfile behind if the process is interrupted or
    the write fails partway through; this way the previous lockfile (if any) stays
    fully intact until the new content is completely on disk. On failure, the temp
    file is cleaned up and the exception re-raised for `_update_lock`'s existing
    best-effort/stderr-only catch — this function itself never leaves a stray
    `.tmp` file or a corrupt lockfile behind."""
    lock_path = local_repo / LOCK_RELATIVE_PATH
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(lock, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    fd, tmp_name = tempfile.mkstemp(
        dir=str(lock_path.parent), prefix=lock_path.name + ".", suffix=".tmp"
    )
    tmp_path = Path(tmp_name)
    try:
        # `newline=""` so Python does not translate \n -> \r\n on Windows.
        # `_write_file` above already pins it; without it here the committed
        # lockfile is the one CRLF file in the plugin, differs per developer OS
        # from the same sync, and a repo pinning `eol=lf` sees it re-dirtied on
        # every apply.
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as fh:
            fh.write(payload)
        os.replace(tmp_path, lock_path)
    except (OSError, ValueError):
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise


def _hash_bytes(data: bytes) -> str:
    """Line-ending-insensitive content hash, matching `discover._hash_bytes`.

    Extracted from `_update_lock`'s inline expression so the kept-local path
    below cannot hash on different terms from the written path — the two sides
    drifting apart is precisely the bug the normalization was added for.
    """
    return hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()


def _hash_local_file(local_repo: Path, asset_path: str) -> str | None:
    """Hash of the local file as it sits on disk, or None if unreadable.

    Read fresh rather than reused from `divergences.json`: discover ran earlier,
    and a file edited between the two phases would otherwise be recorded under a
    hash it no longer has — an ancestor that matches nothing, which degrades the
    next reconcile to a permanent `both-diverged`.
    """
    try:
        return _hash_bytes((local_repo / asset_path).read_bytes())
    except OSError:
        return None


def _update_lock(
    local_repo: Path,
    written: list[tuple[str, bytes]],
    source_name: str,
    source_commit: str | None = None,
    *,
    source_shas: dict[str, str] | None = None,
    kept_local: list[tuple[str, str]] | None = None,
) -> None:
    """Read-merge-write the lockfile for every `wrote` outcome (Decision B): each
    entry records the sha256 of the exact bytes just written to that local file
    (`last_synced_sha256`) AND the sha256 of the raw source those bytes were
    adapted FROM (`source_sha256`), plus the run's source name.

    Recording BOTH is what makes `discover._classify_status` able to tell "we
    adopted this verbatim" from "we rewrote it". With only the adapted hash, the
    two sides were compared against one shared baseline, `local-advanced` was
    unreachable for every adapted file, and a deliberate divergence silently
    reverted on the next sync. See that function's docstring for the table.

    `source_shas` maps asset_path -> raw source sha256. It comes from
    `divergences.json`, which `discover` already computed with `_hash_bytes` (so
    it is LF-normalized on the same terms) — NOT from the LLM-authored
    adaptations file, where an invented value would reintroduce exactly the
    unreliability the `NOT ADAPTED` completeness check exists to catch. Omitted
    per-asset when unknown, the same way `source_commit` degrades.

    `kept_local` carries `(asset_path, local_sha256)` for assets Phase 2 marked
    `keep_local: true`. Those files are NOT written, but they must still update
    their entry: recording the decision plus the source it was made against is
    what stops the next run from re-labelling them `source-advanced` and asking
    again. `last_synced_sha256` is re-hashed from the local file on disk rather
    than carried over, because a partial entry would break `_detect_deletions`,
    which reads that field off every entry.

    Keyword-only for the two new parameters so existing positional call sites —
    including several in the test suite — keep working unchanged.

    Only entries for files actually written or kept this run are touched — every
    other prior entry survives untouched. This
    is deliberately best-effort: a write failure is reported to stderr but must never
    fail the apply run (nor, in `pr` mode, the commit/push) whose files already
    landed — the lock is provenance, not a correctness gate.

    `source_commit` is the source repo's HEAD at the moment of the sync. Without it
    the lock could answer "does this file still match what was written?" but not
    "written from WHAT?" — the source name alone is a moving target, since the same
    repo produces different content on every commit. Recording the SHA makes a sync
    reproducible after the fact: you can diff the local file against the exact source
    revision it came from rather than against whatever that repo's HEAD happens to be
    now. Optional on purpose — a source that isn't a git repo, or a git that won't
    run, degrades to the previous behavior rather than failing the sync."""
    # `not written` alone was the early-out. With kept-local entries now carrying
    # a decision worth persisting, a run that ONLY kept files would have returned
    # here and recorded nothing — which is the exact silent-revert this change
    # exists to stop, reintroduced one level up.
    if not written and not kept_local:
        return
    source_shas = source_shas or {}
    try:
        lock = _read_lock(local_repo)
        for asset_path, data in written:
            entry = {
                # Line-ending-insensitive, matching `discover._hash_bytes`. The
                # bytes written here are already LF (`_write_file` passes
                # `newline="\n"`), so this normalization is a no-op today — it
                # is here so the two sides cannot drift apart again. They did:
                # discover hashed raw bytes, git checked the file out as CRLF on
                # Windows, and the entry could never match, silently reducing
                # the 3-way reconcile to a 2-way diff for 277 of 527 tracked
                # assets across four consumer repos.
                "last_synced_sha256": _hash_bytes(data),
                "source": source_name,
            }
            raw = source_shas.get(asset_path)
            if raw:
                entry["source_sha256"] = raw
            if source_commit:
                entry["source_commit"] = source_commit
            lock[asset_path] = entry
        for asset_path, local_sha in kept_local or []:
            # A fresh dict, not a merge into the prior entry: a later real write
            # must clear `keep_local` rather than strand it forever.
            entry = {"last_synced_sha256": local_sha, "source": source_name}
            raw = source_shas.get(asset_path)
            if raw:
                entry["source_sha256"] = raw
            if source_commit:
                entry["source_commit"] = source_commit
            entry["keep_local"] = True
            lock[asset_path] = entry
        _write_lock(local_repo, lock)
    except (OSError, ValueError) as exc:
        print(f"update-cla: failed to update sync lockfile: {exc}", file=sys.stderr)


def apply_worktree(
    local_repo: Path,
    adaptations: list[dict],
    source_name: str,
    source_commit: str | None = None,
    source_shas: dict[str, str] | None = None,
) -> list[ApplyOutcome]:
    assert_target_is_a_repo_not_an_installed_plugin(local_repo)
    outcomes: list[ApplyOutcome] = []
    written: list[tuple[str, bytes]] = []
    kept_local: list[tuple[str, str]] = []
    for a in adaptations:
        asset_path = a["asset_path"]
        # An entry may deliberately carry NO content: Phase 2 marks a file
        # `keep_local` to say "I considered this and am keeping local", which
        # accounts for it in the completeness check without rewriting it.
        #
        # Its lock entry used to be left alone, on the reasoning that local did
        # not change so the recorded ancestor was still correct. That is true of
        # the ancestor and false of everything else: with no record that the
        # decision was made, and no advance of `source_sha256`, the next run
        # re-labels the file and asks again — and if nobody notices, adopts
        # source over the divergence the decision existed to protect. So the
        # entry IS updated now: same ancestor (re-read from disk), advanced
        # source, and `keep_local: true` so the intent survives the session.
        if a.get("keep_local") is True:
            local_sha = _hash_local_file(local_repo, asset_path)
            if local_sha is not None:
                kept_local.append((asset_path, local_sha))
            outcomes.append(ApplyOutcome(asset_path, "skipped_kept_local",
                                         "kept local content"))
            continue
        adapted = a.get("adapted_content")
        if adapted is None:
            outcomes.append(ApplyOutcome(asset_path, "failure", "adapted_content is null"))
            continue
        if _looks_like_binary_placeholder(adapted):
            outcomes.append(ApplyOutcome(
                asset_path, "skipped_binary",
                "adapted_content looks like a binary placeholder; not writing",
            ))
            continue
        pre_normalize = adapted
        adapted = _normalize_line_endings(adapted)
        if _looks_malformed_by_doubled_newlines(adapted):
            outcomes.append(ApplyOutcome(
                asset_path, "skipped_malformed",
                "adapted_content's newline count is ~2x its non-empty line "
                "count (doubled-newline corruption fingerprint); not writing",
            ))
            continue
        try:
            if _file_has_local_edits(local_repo, asset_path):
                outcomes.append(ApplyOutcome(
                    asset_path,
                    "skipped_dirty_worktree",
                    "file has un-committed local edits; commit or stash first",
                ))
                continue
        except GitUnavailableError as exc:
            outcomes.append(ApplyOutcome(
                asset_path, "failure",
                f"refusing to overwrite: {exc}",
            ))
            continue
        try:
            _write_file(local_repo, asset_path, adapted)
            # Before this normalization step, `_write_file`'s `newline="\n"`
            # meant no translation at all — a CR in `adapted_content` reached
            # disk byte-for-byte. Report it when normalization actually
            # changed something (a legitimate CRLF-requiring asset, e.g. a
            # Windows `.cmd`, would otherwise be silently rewritten with no
            # trace in the summary) — never on the common case, where it's
            # only noise.
            reason = "line endings normalized (CRLF/CR → LF)" if adapted != pre_normalize else None
            outcomes.append(ApplyOutcome(asset_path, "wrote", reason))
            # Hash the in-memory `adapted` bytes rather than re-reading the file from
            # disk: `_write_file` writes these exact bytes (utf-8, newline="\n" means
            # no translation), so a read-back is redundant — and, worse, a read-back
            # OSError here would land inside this same `try`/outcome-appending block
            # and append a contradictory second "failure" outcome for a file that was
            # already successfully written.
            written.append((asset_path, adapted.encode("utf-8")))
        except (OSError, ValueError) as exc:
            # ValueError as well as OSError: `UnicodeEncodeError` is a
            # `ValueError`, so a lone surrogate in `adapted_content` escaped this
            # handler entirely and aborted the run -- skipping `_update_lock`
            # and losing provenance for every file already written, which
            # contradicts this module's own "a failure on one asset never halts
            # the run" contract.
            outcomes.append(ApplyOutcome(asset_path, "failure", f"write failed: {exc}"))
    _update_lock(local_repo, written, source_name, source_commit,
                 source_shas=source_shas, kept_local=kept_local)
    return outcomes


def _now_branch_name(source_name: str) -> str:
    ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    safe = "".join(c if c.isalnum() or c == "-" else "-" for c in source_name)[:32]
    return f"sync/from-{safe}-{ts}"


def _detect_default_branch(repo: Path) -> Optional[str]:
    try:
        result = _run(
            ["gh", "repo", "view", "--json", "defaultBranchRef", "-q", ".defaultBranchRef.name"],
            cwd=repo,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def _rollback_branch(repo: Path, default_branch: str) -> None:
    """Best-effort return to the default branch after a mid-flow PR failure.

    Checks `returncode` rather than catching. Once `_run` stopped raising and
    started returning a synthetic failure result, the old `except` arm became
    unreachable and a failed rollback went COMPLETELY silent — while
    `orchestrate` still printed "(rolled back to default branch where
    possible)". The user was left checked out on the sync branch, told
    otherwise.
    """
    result = _run(["git", "checkout", default_branch], cwd=repo)
    if result.returncode != 0:
        print(
            f"update-cla: rollback to {default_branch} FAILED "
            f"({result.stderr.strip() or f'rc={result.returncode}'}); "
            "you are STILL on the sync branch",
            file=sys.stderr,
        )


# GitHub rejects a pull-request body over 65536 characters. A 154-asset sync
# produced one past that, and `gh pr create` then failed AFTER the branch was
# already committed and pushed -- so the run reported "PR creation failed",
# rolled the local checkout back to the default branch, and said nothing about
# the surviving REMOTE branch. That reads as "nothing happened", and the obvious
# response (re-run the sync) creates a second branch.
_PR_BODY_LIMIT = 65536
# Headroom for the template around the two substituted sections.
_PR_BODY_BUDGET = 60000


def _render_pr_body(adaptations: list[dict]) -> str:
    template = PR_TEMPLATE_PATH.read_text(encoding="utf-8")
    rows = []
    summaries = []
    for a in adaptations:
        asset_path = a.get("asset_path", "(unknown)")
        rows.append(f"| `{asset_path}` | {a.get('change_summary', '(no summary)') or '(no summary)'} |")
        summary = a.get("change_summary")
        if summary:
            summaries.append(f"### `{asset_path}`\n\n{summary}\n")
    ts = datetime.datetime.now().isoformat(timespec="seconds")

    def _render(row_list: list[str], summary_list: list[str], note: str = "") -> str:
        return (
            template
            .replace("{{ASSET_ROWS}}", "\n".join(row_list) or "| (none) | |")
            .replace("{{CHANGE_SUMMARIES}}", ("\n".join(summary_list) or "(no per-asset summaries)") + note)
            .replace("{{TIMESTAMP}}", ts)
        )

    body = _render(rows, summaries)
    if len(body) <= _PR_BODY_BUDGET:
        return body

    # Over budget: drop the long per-asset prose first, keeping the table, and
    # SAY what was omitted. A silently truncated body is worse than a long one --
    # the reader cannot tell the difference between "no summary was written" and
    # "the summary did not fit".
    dropped = len(summaries)
    body = _render(rows, [], f"\n\n_({dropped} per-asset summar{'y' if dropped == 1 else 'ies'} "
                             f"omitted: the full body exceeded GitHub's {_PR_BODY_LIMIT}-character "
                             f"limit. See the commit for the complete set.)_\n")
    if len(body) <= _PR_BODY_BUDGET:
        return body

    # Still over: the table alone is too long. Keep a prefix and name the count.
    keep = max(1, len(rows) // 2)
    while keep > 1 and len(_render(rows[:keep], [])) > _PR_BODY_BUDGET:
        keep //= 2
    hidden = len(rows) - keep
    body = _render(
        rows[:keep] + [f"| _… {hidden} more asset(s) not listed_ | |"],
        [],
        f"\n\n_({dropped} per-asset summaries and {hidden} table row(s) omitted: the full "
        f"body exceeded GitHub's {_PR_BODY_LIMIT}-character limit. See the commit for the "
        f"complete set.)_\n",
    )
    # Final hard bound. Every path above measures a DIFFERENT string than the one
    # it returns (the loop checks `rows[:keep]` without the extra row or note),
    # and when `keep == 1` the loop never runs at all -- verified: a single asset
    # with an oversized summary returned a 71123-char body, still past the limit,
    # so `gh pr create` still failed after the push. Guarantee the invariant this
    # function is named for rather than approximating it.
    if len(body) > _PR_BODY_LIMIT:
        note = "\n\n_(truncated: body exceeded GitHub's character limit.)_\n"
        body = body[: _PR_BODY_LIMIT - len(note)] + note
    return body


def _cleanup_temp_dir(temp_dir: Path, *files: Path) -> None:
    """Remove the two scratch files this run wrote, then the dir if now empty.

    `temp/sync-<run-id>/` was never cleaned up, and `apply_pr` opens with a
    whole-tree clean check -- so the SECOND `--mode pr` run in any repo refused
    to start and blamed the user's working tree. No ignore rule covers it
    either: the documented pattern is `temp/sync-state/`, the *discover* state
    dir, which is a different path.

    Deliberately NOT `shutil.rmtree`. `temp_dir` is caller-supplied, and the
    first draft of this in a consuming repo did exactly that -- their test suite
    caught it deleting an entire synthetic repo, because a caller had passed the
    enclosing directory. `rmdir` fails harmlessly on anything it should not be
    removing, which is the property worth having here.
    """
    for f in files:
        try:
            f.unlink(missing_ok=True)
        except OSError:
            pass
    try:
        temp_dir.rmdir()
    except OSError:
        pass  # not empty (someone else's files) or already gone — both fine


def apply_pr(
    local_repo: Path,
    adaptations: list[dict],
    source_name: str,
    temp_dir: Path,
    source_commit: str | None = None,
    source_shas: dict[str, str] | None = None,
) -> tuple[list[ApplyOutcome], PRResult]:
    """Requires clean working tree; otherwise refuses."""
    assert_target_is_a_repo_not_an_installed_plugin(local_repo)
    outcomes: list[ApplyOutcome] = []

    clean, _ = _is_clean_tree(local_repo)
    if not clean:
        return outcomes, PRResult(None, None, "dirty working tree — commit or stash before running in --mode pr")

    default = _detect_default_branch(local_repo)
    if default is None:
        return outcomes, PRResult(None, None, "default branch detection via gh failed")

    branch = _now_branch_name(source_name)
    checkout = _run(["git", "checkout", "-b", branch, f"origin/{default}"], cwd=local_repo)
    if checkout.returncode != 0:
        checkout = _run(["git", "checkout", "-b", branch, default], cwd=local_repo)
        if checkout.returncode != 0:
            return outcomes, PRResult(branch, None, f"branch creation failed: {checkout.stderr.strip()}")

    pushed = False
    # Bound up-front because `_fail` closes over it and can run BEFORE the file
    # is created — an early failure (branch creation, no files written) hit an
    # unbound free variable and turned a clean error return into a NameError.
    msg_file: Optional[Path] = None

    def _fail(reason: str) -> tuple[list[ApplyOutcome], PRResult]:
        # `_rollback_branch` returns the LOCAL checkout to the default branch. It
        # cannot un-push. When the failure happened after the push -- which is
        # exactly where the PR-body-length failure happens -- the remote branch
        # survives, and a message that only says "PR creation failed" reads as
        # "nothing happened". The obvious response is to re-run the sync, which
        # produces a SECOND branch. So say what survived and what to do with it.
        _rollback_branch(local_repo, default)
        # Clean the commit message, but deliberately KEEP the PR body: when
        # the failure is `gh pr create` after a successful push, the message
        # below tells the user to open the PR by hand with --body-file, and
        # deleting that file would make the instruction impossible to follow.
        # Without this the next --mode pr run still refuses to start on a
        # dirty tree, which is the symptom cleanup was added to fix -- and the
        # failure path is the MORE likely one to leave debris.
        _cleanup_temp_dir(temp_dir, *([msg_file] if msg_file else []))
        detail = reason
        if pushed:
            detail = (
                f"{reason}\nThe branch '{branch}' WAS pushed and still exists on the "
                f"remote — the local checkout was rolled back, the remote was not. "
                f"Open the PR by hand rather than re-running (a re-run creates a "
                f"second branch):\n"
                f"  gh pr create --base {default} --head {branch} --title <title> "
                f"--body-file {temp_dir / 'pr-body.md'}"
            )
        return outcomes, PRResult(branch, None, detail)

    written: list[dict] = []
    written_bytes: list[tuple[str, bytes]] = []
    kept_local: list[tuple[str, str]] = []
    for a in adaptations:
        asset_path = a["asset_path"]
        # An entry may deliberately carry NO content: Phase 2 marks a file
        # `keep_local` to say "I considered this and am keeping local", which
        # accounts for it in the completeness check without rewriting it.
        #
        # Its lock entry used to be left alone, on the reasoning that local did
        # not change so the recorded ancestor was still correct. That is true of
        # the ancestor and false of everything else: with no record that the
        # decision was made, and no advance of `source_sha256`, the next run
        # re-labels the file and asks again — and if nobody notices, adopts
        # source over the divergence the decision existed to protect. So the
        # entry IS updated now: same ancestor (re-read from disk), advanced
        # source, and `keep_local: true` so the intent survives the session.
        if a.get("keep_local") is True:
            local_sha = _hash_local_file(local_repo, asset_path)
            if local_sha is not None:
                kept_local.append((asset_path, local_sha))
            outcomes.append(ApplyOutcome(asset_path, "skipped_kept_local",
                                         "kept local content"))
            continue
        adapted = a.get("adapted_content")
        if adapted is None:
            outcomes.append(ApplyOutcome(asset_path, "failure", "adapted_content is null"))
            continue
        if _looks_like_binary_placeholder(adapted):
            outcomes.append(ApplyOutcome(
                asset_path, "skipped_binary",
                "adapted_content looks like a binary placeholder; not writing",
            ))
            continue
        pre_normalize = adapted
        adapted = _normalize_line_endings(adapted)
        if _looks_malformed_by_doubled_newlines(adapted):
            outcomes.append(ApplyOutcome(
                asset_path, "skipped_malformed",
                "adapted_content's newline count is ~2x its non-empty line "
                "count (doubled-newline corruption fingerprint); not writing",
            ))
            continue
        try:
            _write_file(local_repo, asset_path, adapted)
            # See apply_worktree's identical comment: report normalization
            # only when it actually changed something, so a legitimate
            # CRLF-requiring asset isn't silently rewritten with no trace.
            reason = "line endings normalized (CRLF/CR → LF)" if adapted != pre_normalize else None
            outcomes.append(ApplyOutcome(asset_path, "wrote", reason))
            written.append(a)
            # See apply_worktree's comment: hash the in-memory adapted bytes rather
            # than re-reading from disk, to avoid a read-back OSError producing a
            # contradictory second outcome for an already-written file.
            written_bytes.append((asset_path, adapted.encode("utf-8")))
        except (OSError, ValueError) as exc:
            # ValueError as well as OSError: `UnicodeEncodeError` is a
            # `ValueError`, so a lone surrogate in `adapted_content` escaped this
            # handler entirely and aborted the run -- skipping `_update_lock`
            # and losing provenance for every file already written, which
            # contradicts this module's own "a failure on one asset never halts
            # the run" contract.
            outcomes.append(ApplyOutcome(asset_path, "failure", f"write failed: {exc}"))

    if not written:
        # Deliberately kept, even though `kept_local` may hold real decisions:
        # a provenance-only PR is a new PR shape nobody asked for. But say so —
        # a silent loss of those decisions is what this whole change is about.
        detail = "no files written; aborting PR"
        if kept_local:
            detail += (
                f" ({len(kept_local)} keep-local decision(s) were NOT persisted, "
                "because no commit was made — re-run in worktree mode to record them)"
            )
        return _fail(detail)

    # Write/update the sync lockfile BEFORE `git add -A` so it is staged, committed,
    # and pushed in the same PR (Decision B) — a write here after `git add -A` (or
    # after this function returns, in cmd_apply) would land the provenance update
    # uncommitted on an already-pushed branch and lose it for pr-mode syncs.
    _update_lock(local_repo, written_bytes, source_name, source_commit,
                 source_shas=source_shas, kept_local=kept_local)

    add = _run(["git", "add", "-A"], cwd=local_repo)
    if add.returncode != 0:
        return _fail(f"git add failed: {add.stderr.strip()}")

    temp_dir.mkdir(parents=True, exist_ok=True)
    msg_file = temp_dir / "commit-msg.txt"
    body_lines = [f"chore: sync .claude/ assets from {source_name}", ""]
    body_lines.append("Assets:")
    for a in written:
        body_lines.append(f"- {a['asset_path']}")
    msg_file.write_text("\n".join(body_lines) + "\n", encoding="utf-8")

    commit = _run(["git", "commit", "-F", str(msg_file)], cwd=local_repo)
    if commit.returncode != 0:
        return _fail(f"git commit failed: {commit.stderr.strip()}")

    push = _run(["git", "push", "-u", "origin", branch], cwd=local_repo)
    if push.returncode != 0:
        return _fail(f"git push failed: {push.stderr.strip()}")
    # From here on a failure leaves a branch on the remote that no rollback can
    # remove — `_fail` must say so instead of implying nothing happened.
    pushed = True

    body_file = temp_dir / "pr-body.md"
    body_file.write_text(_render_pr_body(written), encoding="utf-8")
    title = f"chore: sync .claude/ from {source_name} ({datetime.date.today().isoformat()})"

    pr_create = _run(
        ["gh", "pr", "create",
         "--base", default,
         "--head", branch,
         "--title", title,
         "--body-file", str(body_file)],
        cwd=local_repo,
    )
    if pr_create.returncode != 0:
        return _fail(f"gh pr create failed: {pr_create.stderr.strip()}")

    _cleanup_temp_dir(temp_dir, msg_file, body_file)

    lines = pr_create.stdout.strip().splitlines() if pr_create.stdout else []
    pr_url = lines[-1] if lines else None
    return outcomes, PRResult(branch, pr_url, None)
