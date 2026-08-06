"""Top-level orchestrator for the pull-from-destination sync workflow.

Subcommands:

    orchestrate.py discover <source> [<asset-path>] [--local <path>]
        Walks source `.claude/plugins/cla/`, compares to local. Writes divergences.json.

    orchestrate.py apply --run <id> [--mode worktree|pr] [--local <path>]
        Reads adaptations.json (written by conversation Claude between phases)
        and applies adapted files to the local repo, either to the working tree
        (default) or via a branch+PR.

Conversation Claude does the Phase-2 adaptation between the two subcommands
by reading divergences.json and writing adaptations.json.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional


def _force_utf8_stdout() -> None:
    """Force UTF-8 on Windows so non-ASCII asset names don't trip cp1252."""
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if stream is not None and hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except (OSError, ValueError):
                pass


_force_utf8_stdout()

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import apply as apply_mod  # noqa: E402
import config as cfg_mod  # noqa: E402
import discover as discover_mod  # noqa: E402


STATE_ROOT_RELATIVE = "temp/sync-state"


def _state_root(local_repo: Path) -> Path:
    return (local_repo / STATE_ROOT_RELATIVE).resolve()


def _source_commit(source_repo: Path) -> Optional[str]:
    """The source repo's HEAD sha, or None if it cannot be read.

    Provenance, not a gate: a source that isn't a git checkout (a plain
    directory, an export) is a legitimate sync source, so failure here degrades
    to "no commit recorded" rather than blocking the run.

    A sha from a DIRTY source gets a `-dirty` suffix. The whole value of this
    field is "diff the local file against the revision it came from", and CLA is
    designed to be loaded live from a working tree (`--plugin-dir`), so syncing
    mid-edit is the normal case, not the exotic one. Recording a bare sha then
    would point at a revision that does not contain the bytes actually copied —
    worse than recording nothing, because it looks authoritative.
    """
    try:
        r = subprocess.run(
            ["git", "-C", str(source_repo), "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if r.returncode != 0:
        return None
    sha = (r.stdout or "").strip()
    if not sha:
        return None

    try:
        status = subprocess.run(
            ["git", "-C", str(source_repo), "status", "--porcelain"],
            capture_output=True, text=True, timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        # Cannot tell clean from dirty. Say so rather than implying clean.
        return f"{sha}-unknown"
    if status.returncode != 0:
        return f"{sha}-unknown"
    return f"{sha}-dirty" if (status.stdout or "").strip() else sha


def _state_dir(local_repo: Path, run_id: str) -> Path:
    return _state_root(local_repo) / run_id


def _read_json(path: Path) -> Optional[dict]:
    """Returns the parsed JSON; prints a friendly error and returns None on failure."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(
            f"error: {path} is not valid JSON ({exc}); re-run discover or fix the file by hand",
            file=sys.stderr,
        )
        return None
    except OSError as exc:
        print(f"error: cannot read {path}: {exc}", file=sys.stderr)
        return None


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def _resolve_local(arg: Optional[str]) -> Path:
    if arg:
        return Path(arg).expanduser().resolve()
    return Path.cwd().resolve()


# --- Phase 1: discover ---------------------------------------------------


def cmd_discover(source_arg: str, filter_pattern: Optional[str], local_arg: Optional[str]) -> int:
    cfg = cfg_mod.resolve()
    try:
        source_repo = cfg_mod.resolve_repo_arg(source_arg, cfg)
    except cfg_mod.ConfigError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    local_repo = _resolve_local(local_arg)

    if not source_repo.exists():
        print(f"error: source repo {source_repo} does not exist", file=sys.stderr)
        return 2
    if not (source_repo / ".claude" / "plugins" / "cla").is_dir():
        print(f"error: {source_repo} has no .claude/plugins/cla/ directory (not a cla source)", file=sys.stderr)
        return 2
    if not local_repo.exists():
        print(f"error: local repo {local_repo} does not exist", file=sys.stderr)
        return 2
    if source_repo == local_repo:
        print(f"error: source and local are the same repo ({source_repo})", file=sys.stderr)
        return 2

    print(f"update-cla: source={source_repo}")
    print(f"update-cla: local={local_repo}")
    if filter_pattern:
        print(f"update-cla: filter={filter_pattern}")

    result = discover_mod.discover(source_repo, local_repo, filter_pattern)
    counts = discover_mod.summary_counts(result)

    print(
        f"Discovered {counts['total']} file(s): "
        f"{counts['divergent']} divergent, {counts['new']} new, "
        f"{counts['source_advanced']} source-advanced, {counts['local_advanced']} local-advanced, "
        f"{counts['both_diverged']} both-diverged "
        f"({counts['skills']} skills, {counts['agents']} agents, {counts['hooks']} hooks, "
        f"{counts['output_styles']} output-styles)."
    )
    if counts["skipped"]:
        print(f"Skipped {counts['skipped']} file(s) — see stderr for reasons.")
    if counts["deletions"]:
        print(f"{counts['deletions']} local asset(s) appear deleted in source — see divergences.json 'deletions' (never auto-deleted).")

    if counts["total"] == 0 and counts["deletions"] == 0:
        print("Nothing to sync — local is already in sync with source for this scope.")
        return 0

    run_id = datetime.now().strftime("%Y%m%d-%H%M%S")
    state_dir = _state_dir(local_repo, run_id)
    state_dir.mkdir(parents=True, exist_ok=True)

    payload = {
        "run_id": run_id,
        "source": {
            "name": source_repo.name,
            "path": str(source_repo),
            # Captured at DISCOVER time, not apply time: the source repo could be
            # committed to in between, and the lock has to name the revision the
            # adapted content was actually derived from. Best-effort — a source
            # that isn't a git repo simply has no commit to record.
            "commit": _source_commit(source_repo),
        },
        "local": {"path": str(local_repo)},
        "filter": filter_pattern,
        "files": [
            {
                "asset_path": r.asset_path,
                "status": r.status,
                "source_content": r.source_content,
                "source_sha256": r.source_sha256,
                "local_content": r.local_content,
                "local_sha256": r.local_sha256,
            }
            for r in result.files
        ],
        "skipped": [
            {"asset_path": s.asset_path, "reason": s.reason, "detail": s.detail}
            for s in result.skipped
        ],
        "deletions": [
            {
                "asset_path": d.asset_path,
                "status": d.status,
                "local_sha256": d.local_sha256,
                "last_synced_sha256": d.last_synced_sha256,
                "source": d.source,
            }
            for d in result.deletions
        ],
    }
    divergences_path = state_dir / "divergences.json"
    _write_json(divergences_path, payload)

    print()
    print(f"Wrote divergences to: {divergences_path}")
    print()
    print("NEXT — conversation Claude:")
    print("  1. Read divergences.json above.")
    print("  2. For each file, read source_content and local_content (null for new files).")
    print("     Read local CLAUDE.md and surrounding local context to understand conventions.")
    print("  3. Produce adapted_content following references/adaptation_prompt.md.")
    print("     Non-negotiable: preserve any local strengths missing from source.")
    print(f"  4. Write adaptations.json to: {state_dir / 'adaptations.json'}")
    print("     Shape: {\"run_id\": \"" + run_id + "\", \"adaptations\": [")
    print("                {\"asset_path\": \"...\", \"adapted_content\": \"...\", \"change_summary\": \"...\"}, ...]}")
    print(f"  5. Run: python3 {Path(__file__).name} apply --run {run_id} [--mode worktree|pr]")
    return 0


# --- Phase 3: apply -------------------------------------------------------


def cmd_apply(run_id: str, mode: str, local_arg: Optional[str]) -> int:
    local_repo = _resolve_local(local_arg)
    state_dir = _state_dir(local_repo, run_id)
    adaptations_path = state_dir / "adaptations.json"
    divergences_path = state_dir / "divergences.json"

    if not divergences_path.exists():
        print(f"error: {divergences_path} not found — re-run discover", file=sys.stderr)
        return 2
    if not adaptations_path.exists():
        print(
            f"error: {adaptations_path} not found — conversation Claude must write adaptations first",
            file=sys.stderr,
        )
        return 2

    adaptations_data = _read_json(adaptations_path)
    if adaptations_data is None:
        return 2
    divergences_data = _read_json(divergences_path)
    if divergences_data is None:
        return 2

    source_name = divergences_data["source"]["name"]
    # `.get` rather than `[...]`: a divergences file written by an older run
    # predates this key, and a resumed apply must not crash on it.
    source_commit = divergences_data["source"].get("commit")
    adaptations = adaptations_data.get("adaptations", [])

    if not adaptations:
        print("No adaptations to apply.")
        return 0

    if mode == "worktree":
        outcomes = apply_mod.apply_worktree(local_repo, adaptations, source_name, source_commit)
        return _print_worktree_summary(outcomes)

    if mode == "pr":
        temp_dir = (local_repo / "temp" / f"sync-{run_id}").resolve()
        outcomes, pr_result = apply_mod.apply_pr(
            local_repo, adaptations, source_name, temp_dir, source_commit
        )
        return _print_pr_summary(outcomes, pr_result)

    print(f"error: unknown mode {mode!r}", file=sys.stderr)
    return 2


def _print_worktree_summary(outcomes: list) -> int:
    wrote = [o for o in outcomes if o.status == "wrote"]
    skipped_dirty = [o for o in outcomes if o.status == "skipped_dirty_worktree"]
    skipped_binary = [o for o in outcomes if o.status == "skipped_binary"]
    skipped_malformed = [o for o in outcomes if o.status == "skipped_malformed"]
    failed = [o for o in outcomes if o.status == "failure"]
    # A status this printer doesn't recognize must never disappear silently —
    # that is exactly the failure class `skipped_malformed` itself was almost
    # introduced as (a new ApplyOutcome status with no bucket here prints
    # nowhere and is invisible in the count).
    known = {"wrote", "skipped_dirty_worktree", "skipped_binary", "skipped_malformed", "failure"}
    unrecognized = [o for o in outcomes if o.status not in known]

    print()
    print(f"Wrote {len(wrote)} of {len(outcomes)} file(s) to the working tree.")
    for o in wrote:
        print(f"  - wrote {o.asset_path}")
    if skipped_dirty:
        print("Skipped (un-committed local edits — commit or stash first):")
        for o in skipped_dirty:
            print(f"  - {o.asset_path}")
    if skipped_binary:
        print("Skipped (binary placeholder — not safe to write):")
        for o in skipped_binary:
            print(f"  - {o.asset_path}")
    if skipped_malformed:
        print("Skipped (doubled-newline corruption fingerprint — NOT written):")
        for o in skipped_malformed:
            print(f"  - {o.asset_path}: {o.reason}")
    if failed:
        print("Failed:")
        for o in failed:
            print(f"  - {o.asset_path}: {o.reason}")
    if unrecognized:
        print("Unrecognized outcome status (report this as a bug):")
        for o in unrecognized:
            print(f"  - {o.asset_path}: status={o.status!r} reason={o.reason}")
    if wrote:
        print()
        print("Review with: git diff")
    if (failed or skipped_malformed or unrecognized) and not wrote:
        return 1
    return 0


def _print_pr_summary(outcomes: list, pr_result) -> int:
    wrote = [o for o in outcomes if o.status == "wrote"]
    skipped_malformed = [o for o in outcomes if o.status == "skipped_malformed"]
    failed = [o for o in outcomes if o.status == "failure"]
    known = {"wrote", "skipped_dirty_worktree", "skipped_binary", "skipped_malformed", "failure"}
    unrecognized = [o for o in outcomes if o.status not in known]

    print()
    if pr_result.reason and pr_result.pr_url is None:
        print(f"PR creation failed: {pr_result.reason}")
        if pr_result.branch:
            print(f"Branch: {pr_result.branch} (rolled back to default branch where possible)")
        for o in failed:
            print(f"  - {o.asset_path}: {o.reason}")
        if skipped_malformed:
            print("Refused (doubled-newline corruption fingerprint — NOT written):")
            for o in skipped_malformed:
                print(f"  - {o.asset_path}: {o.reason}")
        return 1

    print(f"Wrote {len(wrote)} file(s) and opened PR.")
    for o in wrote:
        print(f"  - wrote {o.asset_path}")
    if failed:
        print("Per-file failures:")
        for o in failed:
            print(f"  - {o.asset_path}: {o.reason}")
    if skipped_malformed:
        print("Refused (doubled-newline corruption fingerprint — NOT written):")
        for o in skipped_malformed:
            print(f"  - {o.asset_path}: {o.reason}")
    if unrecognized:
        print("Unrecognized outcome status (report this as a bug):")
        for o in unrecognized:
            print(f"  - {o.asset_path}: status={o.status!r} reason={o.reason}")
    print()
    print(f"Branch: {pr_result.branch}")
    if pr_result.pr_url:
        print(f"PR:     {pr_result.pr_url}")
    return 0


# --- CLI -----------------------------------------------------------------


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="update-cla",
        description="Pull cla plugin (.claude/plugins/cla/) updates from a source repo into the local destination.",
    )
    sub = p.add_subparsers(dest="phase", required=True)

    disc = sub.add_parser("discover", help="Phase 1: source-vs-local diff -> divergences.json")
    disc.add_argument("source", help="Source repo path or short name from sync-config.json")
    disc.add_argument("filter", nargs="?", default=None, help="Optional asset-path filter (file, dir, or glob)")
    disc.add_argument("--local", default=None, help="Local repo path (default: CWD)")

    appl = sub.add_parser("apply", help="Phase 3: write adapted files to working tree or open a PR")
    appl.add_argument("--run", required=True, help="run-id from `discover` output")
    appl.add_argument("--mode", choices=["worktree", "pr"], default="worktree")
    appl.add_argument("--local", default=None, help="Local repo path (default: CWD)")

    return p.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    args = parse_args(argv if argv is not None else sys.argv[1:])

    if args.phase == "discover":
        return cmd_discover(args.source, args.filter, args.local)
    if args.phase == "apply":
        return cmd_apply(args.run, args.mode, args.local)
    return 2


if __name__ == "__main__":
    sys.exit(main())
