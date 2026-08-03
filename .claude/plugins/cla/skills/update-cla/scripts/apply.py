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
    status: str  # "wrote" | "skipped_dirty_worktree" | "skipped_binary" | "skipped_malformed" | "failure"
    reason: Optional[str]


@dataclass
class PRResult:
    branch: Optional[str]
    pr_url: Optional[str]
    reason: Optional[str]


def _run(cmd: list[str], cwd: Path, timeout: int = DEFAULT_TIMEOUT_SECONDS) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd, cwd=str(cwd), capture_output=True, text=True, encoding="utf-8", timeout=timeout
    )


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


def _write_file(local_repo: Path, asset_path: str, content: str) -> None:
    dst = local_repo / asset_path
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(content, encoding="utf-8", newline="\n")


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
# Conservative on both knobs, matching Decision E's "on an ambiguous token, err
# toward NOT flagging" posture (see `test_project_facts_paths.py`): the ratio
# is pinned below the clean 2.0 doubling to tolerate a few incidental blank
# lines, and a minimum line count guards a short file's natural blank-line
# spacing from false-positiving.
_MALFORMED_NEWLINE_RATIO = 1.8
_MALFORMED_MIN_NON_EMPTY_LINES = 20


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
    try:
        raw = lock_path.read_text(encoding="utf-8")
    except OSError:
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    if not isinstance(data, dict):
        return {}
    return {k: v for k, v in data.items() if isinstance(v, dict)}


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
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(payload)
        os.replace(tmp_path, lock_path)
    except OSError:
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise


def _update_lock(local_repo: Path, written: list[tuple[str, bytes]], source_name: str) -> None:
    """Read-merge-write the lockfile for every `wrote` outcome (Decision B): each
    entry records the sha256 of the exact bytes just written to that local file (NOT
    the raw source hash) plus the run's source name. Only entries for files actually
    written this run are touched — every other prior entry survives untouched. This
    is deliberately best-effort: a write failure is reported to stderr but must never
    fail the apply run (nor, in `pr` mode, the commit/push) whose files already
    landed — the lock is provenance, not a correctness gate."""
    if not written:
        return
    try:
        lock = _read_lock(local_repo)
        for asset_path, data in written:
            lock[asset_path] = {
                "last_synced_sha256": hashlib.sha256(data).hexdigest(),
                "source": source_name,
            }
        _write_lock(local_repo, lock)
    except OSError as exc:
        print(f"update-cla: failed to update sync lockfile: {exc}", file=sys.stderr)


def apply_worktree(local_repo: Path, adaptations: list[dict], source_name: str) -> list[ApplyOutcome]:
    outcomes: list[ApplyOutcome] = []
    written: list[tuple[str, bytes]] = []
    for a in adaptations:
        asset_path = a["asset_path"]
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
            outcomes.append(ApplyOutcome(asset_path, "wrote", None))
            # Hash the in-memory `adapted` bytes rather than re-reading the file from
            # disk: `_write_file` writes these exact bytes (utf-8, newline="\n" means
            # no translation), so a read-back is redundant — and, worse, a read-back
            # OSError here would land inside this same `try`/outcome-appending block
            # and append a contradictory second "failure" outcome for a file that was
            # already successfully written.
            written.append((asset_path, adapted.encode("utf-8")))
        except OSError as exc:
            outcomes.append(ApplyOutcome(asset_path, "failure", f"write failed: {exc}"))
    _update_lock(local_repo, written, source_name)
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
    """Best-effort return to the default branch after a mid-flow PR failure."""
    try:
        _run(["git", "checkout", default_branch], cwd=repo)
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        print(f"update-cla: rollback to {default_branch} failed: {exc}", file=sys.stderr)


def _render_pr_body(adaptations: list[dict]) -> str:
    template = PR_TEMPLATE_PATH.read_text(encoding="utf-8")
    rows = []
    summaries = []
    for a in adaptations:
        rows.append(f"| `{a['asset_path']}` | {a.get('change_summary', '(no summary)') or '(no summary)'} |")
        summary = a.get("change_summary")
        if summary:
            summaries.append(f"### `{a['asset_path']}`\n\n{summary}\n")
    ts = datetime.datetime.now().isoformat(timespec="seconds")
    return (
        template
        .replace("{{ASSET_ROWS}}", "\n".join(rows) or "| (none) | |")
        .replace("{{CHANGE_SUMMARIES}}", "\n".join(summaries) or "(no per-asset summaries)")
        .replace("{{TIMESTAMP}}", ts)
    )


def apply_pr(
    local_repo: Path,
    adaptations: list[dict],
    source_name: str,
    temp_dir: Path,
) -> tuple[list[ApplyOutcome], PRResult]:
    """Requires clean working tree; otherwise refuses."""
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

    def _fail(reason: str) -> tuple[list[ApplyOutcome], PRResult]:
        _rollback_branch(local_repo, default)
        return outcomes, PRResult(branch, None, reason)

    written: list[dict] = []
    written_bytes: list[tuple[str, bytes]] = []
    for a in adaptations:
        asset_path = a["asset_path"]
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
        adapted = _normalize_line_endings(adapted)
        if _looks_malformed_by_doubled_newlines(adapted):
            outcomes.append(ApplyOutcome(
                asset_path, "skipped_malformed",
                "adapted_content's newline count is ~2x its non-empty line "
                "count (doubled-newline corruption fingerprint); not writing",
            ))
            continue
        a = {**a, "adapted_content": adapted}
        try:
            _write_file(local_repo, asset_path, adapted)
            outcomes.append(ApplyOutcome(asset_path, "wrote", None))
            written.append(a)
            # See apply_worktree's comment: hash the in-memory adapted bytes rather
            # than re-reading from disk, to avoid a read-back OSError producing a
            # contradictory second outcome for an already-written file.
            written_bytes.append((asset_path, adapted.encode("utf-8")))
        except OSError as exc:
            outcomes.append(ApplyOutcome(asset_path, "failure", f"write failed: {exc}"))

    if not written:
        return _fail("no files written; aborting PR")

    # Write/update the sync lockfile BEFORE `git add -A` so it is staged, committed,
    # and pushed in the same PR (Decision B) — a write here after `git add -A` (or
    # after this function returns, in cmd_apply) would land the provenance update
    # uncommitted on an already-pushed branch and lose it for pr-mode syncs.
    _update_lock(local_repo, written_bytes, source_name)

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

    lines = pr_create.stdout.strip().splitlines() if pr_create.stdout else []
    pr_url = lines[-1] if lines else None
    return outcomes, PRResult(branch, pr_url, None)
