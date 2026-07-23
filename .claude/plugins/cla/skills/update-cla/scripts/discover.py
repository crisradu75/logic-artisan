"""Discovery phase: source-vs-local diff over the `cla` plugin tree.

Compares the source repo's `.claude/plugins/cla/` tree (optionally filtered) against the
local repo — this is how `update-cla` pulls newer core `cla` into a repo. Files
matching the repo-neutral overlay marker (an exact `project-context.md` leaf name, or a
`*.local.md` leaf suffix, per the cla-overlay-convention change) are treated as local
overlay and NEVER synced/overwritten.

Since `cla-sync-provenance`, a per-repo sync lockfile (`.claude/plugins/cla/.cla-sync-lock.json`,
see LOCK_RELATIVE_PATH) records, per asset, the sha256 of the content last written to
local by `apply.py` — the common ancestor a real 3-way reconcile needs. Each file
currently divergent is classified against that ancestor:

- identical: same sha256 -> dropped silently
- new: local file does not exist
- divergent: local differs from source, no lock entry for this asset (2-way fallback)
- source-advanced: local unchanged since last sync (local == ancestor), source moved on
- local-advanced: source unchanged since last sync (source == ancestor), local moved on
- both-diverged: both source and local differ from the ancestor and from each other

This is a label only — no auto-merge; `apply.py` writes every to-write file identically
regardless of status.

After the source walk, `discover()` also walks the local tree (same `SCAN_DIRS`,
`_is_excluded`, and `_matches_filter` filters as the source walk) to find local assets
the source walk did not yield. A lock-tracked asset absent from source surfaces as a
`deleted-in-source` record for manual review — `apply.py` never auto-deletes.

Binary files (non-UTF-8) are listed under `skipped` with `reason: binary`
rather than included in `files` — Phase 2's LLM should never see placeholder
content that could round-trip back to disk and corrupt the asset.
"""

from __future__ import annotations

import fnmatch
import hashlib
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Optional


# The `cla` plugin subtree this tool keeps in sync with the canonical source.
# Skills-only (no commands/); the plugin manifest under .claude-plugin/ is synced
# manually. Repo-specific overlay files (project-context.md / *.local.md) are
# preserved, see _is_excluded.
SCAN_DIRS = (".claude/plugins/cla/skills", ".claude/plugins/cla/agents", ".claude/plugins/cla/hooks")
EXCLUDED_FILE_NAMES = ("settings.json", "settings.local.json")
EXCLUDED_PART_NAMES = ("__pycache__", ".pytest_cache")
# The repo-neutral overlay marker: a file whose leaf name is exactly
# OVERLAY_FILE_NAME, or ends with OVERLAY_LOCAL_SUFFIX, is a per-repo overlay
# artifact and is NEVER synced from source — it is local, and update-cla must
# not overwrite it (cla-overlay-convention decision).
OVERLAY_FILE_NAME = "project-context.md"
OVERLAY_LOCAL_SUFFIX = ".local.md"
# The per-repo sync-provenance lockfile (cla-sync-provenance). A dotfile living
# outside SCAN_DIRS — already excluded from the sync scan by both the dotfile
# rule in _is_excluded and by living outside SCAN_DIRS. Never a sync candidate,
# never lock-tracked itself.
LOCK_RELATIVE_PATH = ".claude/plugins/cla/.cla-sync-lock.json"


class BinaryAssetError(Exception):
    """Raised by _read_text when the file isn't UTF-8 decodable."""

    def __init__(self, path: Path, size: int):
        super().__init__(f"binary asset: {path} ({size} bytes)")
        self.path = path
        self.size = size


@dataclass
class FileRecord:
    asset_path: str
    # "divergent" | "new" | "source-advanced" | "local-advanced" | "both-diverged"
    status: str
    source_path: Path
    source_content: str
    source_sha256: str
    local_path: Path
    local_content: Optional[str]
    local_sha256: Optional[str]


@dataclass
class SkippedRecord:
    asset_path: str
    reason: str  # "binary" | "source_unreadable" | "local_unreadable"
    detail: str


@dataclass
class DeletionRecord:
    asset_path: str
    status: str  # always "deleted-in-source"
    local_sha256: str
    last_synced_sha256: Optional[str]
    source: Optional[str]


@dataclass
class DiscoverResult:
    files: list[FileRecord]
    skipped: list[SkippedRecord]
    deletions: list[DeletionRecord] = field(default_factory=list)


def _hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _read_text(path: Path) -> tuple[str, str]:
    """Read a UTF-8 text file; raises BinaryAssetError on non-decodable content."""
    raw = path.read_bytes()
    sha = _hash_bytes(raw)
    try:
        return raw.decode("utf-8"), sha
    except UnicodeDecodeError as exc:
        raise BinaryAssetError(path, len(raw)) from exc


def _is_excluded(item: Path) -> bool:
    if item.name in EXCLUDED_FILE_NAMES:
        return True
    if item.name.startswith(".") and item.name != ".gitkeep":
        return True
    if any(part in EXCLUDED_PART_NAMES for part in item.parts):
        return True
    # Preserve the repo's own overlay: a leaf name that is exactly
    # OVERLAY_FILE_NAME, or that ends with OVERLAY_LOCAL_SUFFIX, is local and
    # never synced. Matched on the leaf name only (not any path component), and
    # case-insensitively — on a case-insensitive filesystem (macOS APFS, Windows)
    # a differently-cased overlay (`Project-Context.md`) exists on disk but a
    # case-sensitive predicate would miss it and let it be clobbered on sync.
    # NOTE: `project-context.md` and any `*.local.md` are RESERVED overlay leaf
    # names — a core asset must never use one, or it is silently skipped from
    # sync. This marker is leaf-name-based only: a *wholly* project-specific
    # skill DIRECTORY is not expressible (accepted narrowing, per the
    # cla-overlay-convention design Non-Goals; no such skill exists today).
    leaf = item.name.lower()
    if leaf == OVERLAY_FILE_NAME:
        return True
    if leaf.endswith(OVERLAY_LOCAL_SUFFIX):
        return True
    return False


def _iter_source_assets(repo_root: Path) -> Iterable[tuple[str, Path]]:
    """Walk SCAN_DIRS under `repo_root`, yielding (asset_path, abs_path) for every
    non-excluded file. Despite the name (this walker predates the deletion-detection
    arm), it is repo-generic — `discover()` reuses it for BOTH the source walk and the
    local-tree deletion walk (Decision D), since the exclusion rule is identical either
    side."""
    for sub in SCAN_DIRS:
        root = repo_root / sub
        if not root.is_dir():
            continue
        for item in root.rglob("*"):
            if not item.is_file() or _is_excluded(item):
                continue
            yield item.relative_to(repo_root).as_posix(), item


def _read_lock(local_repo: Path) -> dict:
    """Read `.claude/plugins/cla/.cla-sync-lock.json` from the local repo.

    Missing, unreadable, or corrupt (bad JSON, non-dict top level) -> empty ancestor
    map (no crash; every divergence then classifies via today's 2-way fallback,
    `divergent`). Also sanitizes at the entry level: a nested value that isn't itself
    a dict (e.g. `{"some/path": "corrupt"}`) is dropped rather than kept, so a
    downstream `.get(...)` on a per-asset lock entry never raises — that asset simply
    behaves as "no ancestor" (`divergent` fallback) instead of crashing `discover`."""
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


def _classify_status(local_sha: str, source_sha: str, lock_entry: Optional[dict]) -> str:
    """3-way classification (Decision C) for a file whose local/source shas differ
    (identical shas never reach this — they're dropped as "identical" before
    classification). `lock_entry` is this asset's `.cla-sync-lock.json` entry, or
    None if the asset has never been synced/recorded."""
    if lock_entry is None:
        return "divergent"
    ancestor = lock_entry.get("last_synced_sha256")
    if local_sha == ancestor and source_sha != ancestor:
        return "source-advanced"
    if source_sha == ancestor and local_sha != ancestor:
        return "local-advanced"
    return "both-diverged"


def _normalize_filter(pattern: Optional[str]) -> Optional[str]:
    """Accept Windows backslashes — the asset_path side is always posix."""
    if pattern is None:
        return None
    return pattern.replace("\\", "/")


def _matches_filter(asset_path: str, filter_pattern: Optional[str]) -> bool:
    """The filter accepts:
    - exact path: `.claude/plugins/cla/skills/foo.md`
    - directory prefix: `.claude/plugins/cla/skills/foo/` (trailing slash optional)
    - glob: `.claude/plugins/cla/skills/*.md`
    """
    if filter_pattern is None:
        return True
    pat = filter_pattern.rstrip("/")
    if any(ch in pat for ch in "*?["):
        return fnmatch.fnmatch(asset_path, pat)
    if asset_path == pat:
        return True
    return asset_path.startswith(pat + "/")


def _detect_deletions(
    local_repo: Path,
    source_seen: set[str],
    lock: dict,
    norm_filter: Optional[str],
) -> list[DeletionRecord]:
    """Walk the local tree (same SCAN_DIRS/_is_excluded/_matches_filter filters the
    source walk uses, Decision D) for in-scope local assets the source walk did not
    yield. A lock-tracked asset absent from source surfaces as `deleted-in-source`;
    an asset with no lock entry is left alone (overlay or genuinely local content the
    source never had — overlay files are additionally never reached here at all,
    since _is_excluded already drops them)."""
    deletions: list[DeletionRecord] = []
    for rel_path, local_abs in _iter_source_assets(local_repo):
        if not _matches_filter(rel_path, norm_filter):
            continue
        if rel_path in source_seen:
            continue
        lock_entry = lock.get(rel_path)
        if lock_entry is None:
            continue
        try:
            local_sha = _hash_bytes(local_abs.read_bytes())
        except OSError as exc:
            print(f"update-cla: cannot read {rel_path} for deletion check: {exc}", file=sys.stderr)
            continue
        deletions.append(DeletionRecord(
            asset_path=rel_path,
            status="deleted-in-source",
            local_sha256=local_sha,
            last_synced_sha256=lock_entry.get("last_synced_sha256"),
            source=lock_entry.get("source"),
        ))
    return deletions


def discover(
    source_repo: Path,
    local_repo: Path,
    filter_pattern: Optional[str] = None,
) -> DiscoverResult:
    """Walk source repo, compare each in-scope file against the local repo.

    Uses `.claude/plugins/cla/.cla-sync-lock.json` (read once, at the start) as the
    common ancestor for a real 3-way classification of each divergent file (Decision
    C), and additionally walks the local tree to surface source-side deletions
    (Decision D)."""
    files: list[FileRecord] = []
    skipped: list[SkippedRecord] = []
    source_seen: set[str] = set()
    norm_filter = _normalize_filter(filter_pattern)
    lock = _read_lock(local_repo)
    for rel_path, source_abs in _iter_source_assets(source_repo):
        if not _matches_filter(rel_path, norm_filter):
            continue
        source_seen.add(rel_path)
        try:
            source_text, source_sha = _read_text(source_abs)
        except BinaryAssetError as exc:
            msg = f"binary asset (size {exc.size})"
            print(f"update-cla: skipping {rel_path}: {msg}", file=sys.stderr)
            skipped.append(SkippedRecord(rel_path, "binary", msg))
            continue
        except OSError as exc:
            msg = f"source unreadable: {exc}"
            print(f"update-cla: skipping {rel_path}: {msg}", file=sys.stderr)
            skipped.append(SkippedRecord(rel_path, "source_unreadable", str(exc)))
            continue

        local_abs = local_repo / rel_path
        if local_abs.exists() and local_abs.is_file():
            try:
                local_text, local_sha = _read_text(local_abs)
            except BinaryAssetError as exc:
                msg = f"binary local asset (size {exc.size})"
                print(f"update-cla: skipping {rel_path}: {msg}", file=sys.stderr)
                skipped.append(SkippedRecord(rel_path, "binary", msg))
                continue
            except OSError as exc:
                msg = f"local unreadable: {exc}"
                print(f"update-cla: skipping {rel_path}: {msg}", file=sys.stderr)
                skipped.append(SkippedRecord(rel_path, "local_unreadable", str(exc)))
                continue
            if local_sha == source_sha:
                continue
            status = _classify_status(local_sha, source_sha, lock.get(rel_path))
            files.append(FileRecord(
                asset_path=rel_path,
                status=status,
                source_path=source_abs,
                source_content=source_text,
                source_sha256=source_sha,
                local_path=local_abs,
                local_content=local_text,
                local_sha256=local_sha,
            ))
        else:
            files.append(FileRecord(
                asset_path=rel_path,
                status="new",
                source_path=source_abs,
                source_content=source_text,
                source_sha256=source_sha,
                local_path=local_abs,
                local_content=None,
                local_sha256=None,
            ))

    deletions = _detect_deletions(local_repo, source_seen, lock, norm_filter)
    return DiscoverResult(files=files, skipped=skipped, deletions=deletions)


def summary_counts(result: DiscoverResult) -> dict[str, int]:
    divergent = sum(1 for r in result.files if r.status == "divergent")
    new = sum(1 for r in result.files if r.status == "new")
    source_advanced = sum(1 for r in result.files if r.status == "source-advanced")
    local_advanced = sum(1 for r in result.files if r.status == "local-advanced")
    both_diverged = sum(1 for r in result.files if r.status == "both-diverged")
    skills = sum(1 for r in result.files if r.asset_path.startswith(".claude/plugins/cla/skills"))
    agents = sum(1 for r in result.files if r.asset_path.startswith(".claude/plugins/cla/agents"))
    hooks = sum(1 for r in result.files if r.asset_path.startswith(".claude/plugins/cla/hooks"))
    return {
        "divergent": divergent,
        "new": new,
        "source_advanced": source_advanced,
        "local_advanced": local_advanced,
        "both_diverged": both_diverged,
        "skills": skills,
        "agents": agents,
        "hooks": hooks,
        "total": len(result.files),
        "skipped": len(result.skipped),
        "deletions": len(result.deletions),
    }
