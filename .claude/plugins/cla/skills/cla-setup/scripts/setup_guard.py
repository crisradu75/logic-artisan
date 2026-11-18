#!/usr/bin/env python3
"""Check that /cla:cla-setup left alone the files it promises to leave alone.

cla-setup promises, in prose, that a run leaves the repo's instruction files byte-identical, always
skips an existing feedback ``notes.md``, never reshapes a machine-read ``*.local.md`` file, never
creates the terminology file or an overlay, and changes an existing terminology file, local file or
overlay only on the owner's yes. Nothing checked those promises. This script records the files at
the start of a run and compares them at the end::

    python3 "${CLAUDE_PLUGIN_ROOT}/skills/cla-setup/scripts/setup_guard.py" snapshot --out <file> [--root <dir>]
    python3 "${CLAUDE_PLUGIN_ROOT}/skills/cla-setup/scripts/setup_guard.py" verify --snapshot <file> [--approved <path> ...] [--root <dir>]

``--root`` (default: the working directory) may be anywhere inside the checkout; the script works
on its top level.

WHY A SNAPSHOT AND NOT GIT. ``git diff`` and ``git status`` compare with the last commit, not with
the start of the run, so they cannot tell three cases apart: a protected file the owner had already
edited before the run (git shows it changed whether or not the run touched it), a gitignored file
(``cla.io/fleet.local.md`` is usually ignored, so git shows nothing whatever the run did) and an
untracked overlay that existed before the run (``??`` either way). The snapshot hashes the files on
disk, so it sees each of those. Git is used only to find the checkout's top level, nested
instruction files git can see, and whether ``--out`` is ignored.

PROTECTED PATHS (repo-relative) and what may happen to each during a run:
  instruction files  ``CLAUDE.md``, ``AGENTS.md``, ``CLAUDE.local.md`` and ``.claude/CLAUDE.md`` at
                     the root, plus any file of the first three names deeper in the tree that git
                     tracks or sees as untracked. No change, creation or deletion; ``--approved``
                     does not cover them, since the skill never asks to touch them.
  feedback notes     ``cla.io/feedback/notes.md``. Created when absent (item 3's seed); an existing
                     one is never changed or deleted, approved or not.
  local files        every ``*.local.md`` under ``cla.io/``. Any change, creation or deletion needs
                     ``--approved`` (item 12 adds token-list entries on a yes).
  terminology        ``cla.io/terminology.md``. Never created, approved or not; a change or deletion
                     needs ``--approved`` (item 11 reconciles it on a yes).
  overlays           ``cla.io/overlays/*.md`` other than ``*.local.md``. Never created, approved or
                     not; a change or deletion needs ``--approved`` (item 13 edits or deletes one on
                     a yes).

SNAPSHOT FILE. JSON: ``{"version": 1, "root": <absolute top level>, "files": {<path>: <sha256 hex>
or null}, "overlays": [<path>, ...]}``. ``null`` means absent. ``--out`` must not be inside the
checkout unless git ignores it, and must not be a protected path.

OUTPUT. The first line is the verdict, and its first word is ``OK``, ``FAIL`` or ``UNCHECKED``.
Each later line is one finding: ``PROBLEM <kind>: <path> (<why>)``, where the kind is ``changed``,
``created`` or ``deleted``, or ``UNCHECKED <kind>: <detail>``. Callers read the exit code and the
first line; keep both stable. A passing ``verify`` names each approved change on its first line.

EXIT CODES (both subcommands):
  0 = every check ran and passed
  1 = a protected file changed without the owner's yes, or an overlay or the terminology file was
      created (``PROBLEM`` lines say which); a found problem wins over a check that could not run
  2 = no problem found, but a check could not run (not a repository, a missing or corrupt snapshot,
      a snapshot of another checkout, an unreadable file, a bad argument). Never a pass.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import traceback
from pathlib import Path

VERSION = 1
INSTRUCTION_NAMES = ("CLAUDE.md", "AGENTS.md", "CLAUDE.local.md")
ROOT_INSTRUCTION_FILES = ("CLAUDE.md", "AGENTS.md", "CLAUDE.local.md", ".claude/CLAUDE.md")
NOTES = "cla.io/feedback/notes.md"
TERMINOLOGY = "cla.io/terminology.md"
OVERLAY_DIR = "cla.io/overlays"
LOCAL_SUFFIX = ".local.md"


class Unchecked(Exception):
    """A check that could not run. Carries (kind, detail)."""

    def __init__(self, kind: str, detail: str) -> None:
        super().__init__(f"{kind}: {detail}")
        self.kind = kind
        self.detail = detail


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            ["git", *args], cwd=cwd, capture_output=True, text=True,
            encoding="utf-8", errors="replace",
        )
    except FileNotFoundError:
        raise Unchecked("git", "the git binary was not found") from None
    except OSError as exc:
        raise Unchecked("git", f"git could not be started: {exc}") from None


def _first_err(r: subprocess.CompletedProcess[str]) -> str:
    text = (r.stderr or r.stdout or "").strip().splitlines()
    return text[0] if text else f"exit {r.returncode}"


def _toplevel(start: Path) -> Path:
    if not start.is_dir():
        raise Unchecked("repo", f"{start} is not a directory")
    r = _git(start, "rev-parse", "--show-toplevel")
    if r.returncode != 0 or not r.stdout.strip():
        raise Unchecked("repo", f"{start} is not inside a git working tree: {_first_err(r)}")
    return Path(r.stdout.strip()).resolve()


# ---------------------------------------------------------------- what is protected


def kind_of(rel: str) -> str:
    """The class of a protected repo-relative path: instruction, notes, local, terminology, overlay."""
    if rel in ROOT_INSTRUCTION_FILES or rel.rsplit("/", 1)[-1] in INSTRUCTION_NAMES:
        return "instruction"
    if rel == NOTES:
        return "notes"
    if rel.startswith("cla.io/") and rel.endswith(LOCAL_SUFFIX):
        return "local"
    if rel == TERMINOLOGY:
        return "terminology"
    if rel.startswith(OVERLAY_DIR + "/") and rel.count("/") == 2 and rel.endswith(".md"):
        return "overlay"
    raise ValueError(f"not a protected path: {rel}")


def _is_protected(rel: str) -> bool:
    try:
        kind_of(rel)
        return True
    except ValueError:
        return False


def _overlays_on_disk(root: Path) -> list[str]:
    d = root / OVERLAY_DIR
    if not d.is_dir():
        return []
    return sorted(
        f"{OVERLAY_DIR}/{p.name}" for p in d.iterdir()
        if p.name.endswith(".md") and not p.name.endswith(LOCAL_SUFFIX) and not p.is_dir()
    )


def _local_files_on_disk(root: Path) -> list[str]:
    base = root / "cla.io"
    found: list[str] = []
    if not base.is_dir():
        return found
    for dirpath, dirnames, filenames in os.walk(base, followlinks=False):
        dirnames.sort()
        for name in filenames:
            if name.endswith(LOCAL_SUFFIX):
                found.append((Path(dirpath) / name).relative_to(root).as_posix())
    return sorted(found)


def _nested_instruction_files(root: Path) -> list[str]:
    """Instruction files git tracks or sees as untracked, at any depth."""
    r = _git(root, "ls-files", "-z", "--cached", "--others", "--exclude-standard")
    if r.returncode != 0:
        raise Unchecked("git", f"git ls-files failed: {_first_err(r)}")
    return sorted({p for p in r.stdout.split("\0") if p and p.rsplit("/", 1)[-1] in INSTRUCTION_NAMES})


def protected_paths(root: Path) -> set[str]:
    paths = set(ROOT_INSTRUCTION_FILES) | {NOTES, TERMINOLOGY}
    paths.update(_nested_instruction_files(root))
    paths.update(_local_files_on_disk(root))
    paths.update(_overlays_on_disk(root))
    return paths


def _digest(root: Path, rel: str) -> str | None:
    """The file's SHA-256, or None when absent. A non-file at the path hashes as a fixed marker."""
    p = root / rel
    if not os.path.lexists(p):
        return None
    if p.is_dir():
        return "not-a-file:directory"
    h = hashlib.sha256()
    try:
        with open(p, "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 16), b""):
                h.update(chunk)
    except FileNotFoundError:
        # A symlink whose target is gone: present as a link, absent as a file.
        return "not-a-file:dangling-link"
    except OSError as exc:
        raise Unchecked("read", f"{rel}: {exc}") from None
    return h.hexdigest()


# ---------------------------------------------------------------- snapshot


def _inside(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def snapshot(root: Path, out: Path) -> tuple[int, int, int]:
    """Write the snapshot. Returns (paths recorded, present, overlays)."""
    out = out.resolve()
    if _inside(out, root):
        rel = out.relative_to(root).as_posix()
        if _is_protected(rel):
            raise Unchecked("out", f"{rel} is a protected path; write the snapshot to the session scratchpad")
        r = _git(root, "check-ignore", "-q", "--", rel)
        if r.returncode == 1:
            raise Unchecked("out", f"{rel} is inside the repo and git does not ignore it; "
                                   "write the snapshot to the session scratchpad or a gitignored folder")
        if r.returncode != 0:
            raise Unchecked("out", f"git check-ignore failed on {rel}: {_first_err(r)}")
    if out.is_dir():
        raise Unchecked("out", f"{out} is a directory")
    files = {rel: _digest(root, rel) for rel in sorted(protected_paths(root))}
    data = {"version": VERSION, "root": str(root), "files": files, "overlays": _overlays_on_disk(root)}
    tmp = out.with_name(out.name + ".tmp")
    try:
        out.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_text(json.dumps(data, indent=1, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(tmp, out)
    except OSError as exc:
        try:
            tmp.unlink()
        except OSError:
            pass
        raise Unchecked("out", f"cannot write {out}: {exc}") from None
    present = sum(1 for v in files.values() if v is not None)
    return len(files), present, len(data["overlays"])


# ---------------------------------------------------------------- verify


def _is_digest(v: object) -> bool:
    if v is None:
        return True
    if not isinstance(v, str):
        return False
    if v.startswith("not-a-file:"):
        return True
    return len(v) == 64 and all(c in "0123456789abcdef" for c in v)


def load_snapshot(path: Path, root: Path) -> dict:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except FileNotFoundError:
        raise Unchecked("snapshot", f"{path} does not exist; was the snapshot step run?") from None
    except OSError as exc:
        raise Unchecked("snapshot", f"cannot read {path}: {exc}") from None
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise Unchecked("snapshot", f"{path} is not valid JSON: {exc}") from None
    if not isinstance(data, dict) or data.get("version") != VERSION:
        raise Unchecked("snapshot", f"{path} is not a version-{VERSION} setup snapshot")
    files, overlays, snap_root = data.get("files"), data.get("overlays"), data.get("root")
    if not isinstance(files, dict) or not files or not all(
        isinstance(k, str) and _is_digest(v) for k, v in files.items()
    ):
        raise Unchecked("snapshot", f"{path} has no valid 'files' map")
    if not isinstance(overlays, list) or not all(isinstance(o, str) for o in overlays):
        raise Unchecked("snapshot", f"{path} has no valid 'overlays' list")
    for rel in files:
        try:
            kind_of(rel)
        except ValueError:
            raise Unchecked("snapshot", f"{path} records {rel!r}, which is not a protected path") from None
    if not all(rel in files for rel in (*ROOT_INSTRUCTION_FILES, NOTES, TERMINOLOGY)):
        raise Unchecked("snapshot", f"{path} does not record every fixed protected path")
    if not isinstance(snap_root, str) or os.path.normcase(str(Path(snap_root).resolve())) != os.path.normcase(str(root)):
        raise Unchecked("snapshot", f"{path} was taken in {snap_root!r}, not in {root}")
    return data


def _normalise_approved(root: Path, raw: list[str]) -> set[str]:
    out: set[str] = set()
    for item in raw:
        p = Path(item)
        if not p.is_absolute():
            p = root / p
        p = Path(os.path.normpath(p))
        if not _inside(p, root):
            # normpath keeps a symlinked root unresolved; try the resolved form too.
            q = p.resolve()
            if not _inside(q, root):
                raise Unchecked("approved", f"{item} is outside the repo {root}")
            p = q
        out.add(p.relative_to(root).as_posix())
    return out


_WHY = {
    "instruction": "an instruction file; cla-setup never touches it, so a yes does not cover it",
    "notes": "the feedback notes file; an existing one is always skipped, so a yes does not cover it",
    "local": "a machine-read local file; changed without the owner's yes",
    "terminology": "the terminology file; changed without the owner's yes",
    "overlay": "an overlay; changed without the owner's yes",
}


def verify(root: Path, snap: dict, approved: set[str]) -> tuple[int, list[str], list[str], list[str]]:
    """Returns (paths compared, problems, unchecked, approved changes)."""
    before: dict[str, str | None] = snap["files"]
    overlays_before = set(snap["overlays"])
    problems: list[str] = []
    unchecked: list[str] = []
    taken: list[str] = []
    compared = sorted(set(before) | protected_paths(root))
    for rel in compared:
        kind = kind_of(rel)
        old = before.get(rel)
        try:
            new = _digest(root, rel)
        except Unchecked as exc:
            unchecked.append(f"UNCHECKED {exc.kind}: {exc.detail}")
            continue
        if old == new:
            continue
        action = "created" if old is None else "deleted" if new is None else "changed"
        if kind == "overlay" and action == "created" and rel not in overlays_before:
            problems.append(f"PROBLEM created: {rel} (an overlay; cla-setup never creates one, "
                            "so a yes does not cover it)")
            continue
        if kind == "terminology" and action == "created":
            problems.append(f"PROBLEM created: {rel} (the terminology file; cla-setup never creates it, "
                            "so a yes does not cover it)")
            continue
        if kind == "notes" and action == "created":
            continue  # item 3 seeds it when absent
        if kind in ("local", "terminology", "overlay") and rel in approved:
            taken.append(f"{rel} {action}")
            continue
        problems.append(f"PROBLEM {action}: {rel} ({_WHY[kind]})")
    return len(compared), problems, unchecked, taken


# ---------------------------------------------------------------- main


def _report(first: str, lines: list[str]) -> None:
    print(first)
    for line in lines:
        print(line)


def main(argv: list[str] | None = None) -> int:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--root", default=".", help="a directory inside the checkout (default: the working directory)")
    ap = argparse.ArgumentParser(
        description="Check that cla-setup left its protected files alone. Exit 0 pass, 1 problem, 2 could not check.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("snapshot", parents=[common], help="at the start of a run: record the protected files")
    p.add_argument("--out", required=True, help="the snapshot file, outside the repo or in a gitignored folder")
    p = sub.add_parser("verify", parents=[common], help="at the end of a run: compare with the snapshot")
    p.add_argument("--snapshot", required=True, help="the file the snapshot step wrote")
    p.add_argument("--approved", action="append", default=[], metavar="PATH",
                   help="a protected file the owner said yes to changing in this run (repeatable)")
    args = ap.parse_args(argv)

    try:
        root = _toplevel(Path(args.root).resolve())
        if args.cmd == "snapshot":
            n, present, overlays = snapshot(root, Path(args.out))
            _report(f"OK snapshot: {n} protected path(s) recorded, {present} present, "
                    f"{overlays} overlay(s), in {Path(args.out).resolve()}", [])
            return 0
        approved = _normalise_approved(root, args.approved)
        snap = load_snapshot(Path(args.snapshot), root)
        compared, problems, unchecked, taken = verify(root, snap, approved)
    except Unchecked as exc:
        _report(f"UNCHECKED {exc.kind}: {exc.detail}", [])
        return 2
    except Exception as exc:  # noqa: BLE001 - a crash must read as "could not check", never as a verdict
        _report(f"UNCHECKED error: unexpected {type(exc).__name__}: {exc}", [])
        print(traceback.format_exc(), file=sys.stderr)
        return 2
    if problems:
        _report(f"FAIL verify: {len(problems)} protected file problem(s)", problems + unchecked)
        return 1
    if unchecked:
        _report(unchecked[0], unchecked[1:])
        return 2
    approved_note = f"; approved: {', '.join(taken)}" if taken else ""
    _report(f"OK verify: {compared} protected path(s) as promised{approved_note}", [])
    return 0


if __name__ == "__main__":
    sys.exit(main())
